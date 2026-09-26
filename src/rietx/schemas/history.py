"""Schemas for the refinement history DAG.

A refinement is a walk through parameter space made of discrete, addressable
steps.  Each node records the *state* the refinement was in — enough to
reconstruct it exactly — plus the action that produced it and the agreement
statistics it achieved.  Nodes are immutable; named refs (``head``, tags) are
the mutable pointers into them, the split git uses between objects and refs.

Nodes deliberately store **state, not results**: ``y_calc`` and the agreement
indices are a pure function of ``(state, pattern)`` and are recomputed on
demand.  On the 11-BM NAC acceptance case a state-only node is ~10 kB against
~1.24 MB for one carrying the fitted curves, which is what makes wide
branching (and tree search) affordable.

Branch points sit at stage boundaries because that is where the compiled model
is legitimately regenerated — the frozen-per-stage discreteness invariant (see
``model/forward.py``) forbids changing the reflection list, symmetry-op
subsets, FCJ node counts or window ranges *within* a least-squares run.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field

from .common import SCHEMA_VERSION, Base, Diagnostic, Mode, Parameter
from .instrument import Instrument

# ``StageSpec``/``PlanSpec`` used to be *defined* here, in parallel with a second
# copy in ``agent.py`` that had a ``strain_seed`` field this one lacked — so a
# Stephens stage lost its seed on the way through a history tree.  One schema
# lives in ``schemas/plan.py`` (WP-1004); the compat re-export was deleted
# pre-freeze (WP-1003), so import both from there.
from .params import TieSpec
from .plan import PlanSpec
from .results import Statistics
from .structure import Structure

#: What produced a node.  **Every member is committed by some verb** — a
#: vocabulary is a claim about what the package does, and one member is not a
#: reservation for later.  It carried a ``"lebail_update"`` until WP-1076 that
#: no code path ever committed: a Le Bail stage refreshes its intensities
#: inside itself, and the refreshed values ride on the ``"stage"`` node's
#: ``ReflectionState``, so a node of that kind had nothing left to record.
NodeKind = Literal["root", "stage", "set_vary", "set_value", "set_tie",
                   "set_variable", "set_hold", "edit_model", "merge"]


class NodeAction(Base):
    """The edge operation that produced a node from its parent(s).

    For a ``"stage"`` action the fields are the stage's *own* arguments, because
    ``Refinement.cherry_pick`` reconstructs a ``Stage`` from them and re-runs it
    elsewhere — so a field missing here is a stage that replays differently from
    the one recorded.  ``seed``/``strain_seed`` were added in WP-1004 for exactly
    that reason: without them a cherry-picked extinction stage left its softplus
    coefficient on the dead-gradient floor, and a Stephens stage started from the
    all-zero block the seed exists to avoid.  Both are additive with a 0.0
    default, which is the no-seed behaviour, so pre-v1.0 nodes replay unchanged.
    ``restraint_weight_scale`` (WP-1074) is the same rule for eq (7)'s c_w: a
    stiff early stage cherry-picked without it would run its restraints at the
    weight the *schedule* had already relaxed to.  Additive with a 1.0 default,
    which is the no-scaling behaviour.

    ``ftol``/``window_slack_deg`` (WP-1123) close the same gap for the two
    fields WP-1113 and WP-1112 added to ``Stage``, and ``ftol`` records the
    tolerance the stage **ran** at rather than the one it declared: under a
    plan's schedule an intermediate stage declares nothing and still stops at
    1e-6, so a node holding ``None`` would replay the one thing the original
    run did not do.  Additive, both defaulting to the solver/compiler default,
    so a pre-WP-1123 node replays exactly as it did.

    ``ties``/``untied`` (WP-1070) are the ``"set_tie"`` action's own arguments,
    additive under the same rule.  They record what the action *did*, not the
    state it left: the whole tie register lives on
    :attr:`RefinementState.ties`, which is what a checkout restores — exactly as
    ``turn_on`` describes a ``set_vary`` whose result is read off ``free_paths``.
    ``held``/``unheld`` (WP-1435) are ``"set_hold"``'s, on that same pattern,
    against :attr:`RefinementState.holds`.
    """

    kind: NodeKind
    name: str = ""
    turn_on: list[str] = Field(default_factory=list)
    turn_off: list[str] = Field(default_factory=list)
    values: dict[str, float] = Field(default_factory=dict)
    max_iter: int = 100
    lebail_cycles: int = 3
    seed: float = 0.0
    strain_seed: float = 0.0
    restraint_weight_scale: float = 1.0
    ftol: float | None = None
    window_slack_deg: float | None = None
    ties: dict[str, TieSpec] = Field(default_factory=dict)
    untied: list[str] = Field(default_factory=list)
    #: ``"set_variable"``'s own arguments (WP-1119), by the same rule as
    #: ``ties``/``untied``: what the action *did*, with the whole register on
    #: :attr:`RefinementState.variables`, which is what a checkout restores.
    #: Keyed by bare name — ``"A"``, not ``"vars.A"`` — because that is what
    #: ``Refinement.add_variable``/``remove_variable`` take.
    variables: dict[str, Parameter] = Field(default_factory=dict)
    removed_variables: list[str] = Field(default_factory=list)
    #: ``"set_hold"``'s own arguments (WP-1435), by the same rule as
    #: ``ties``/``untied``: the paths this action held and released, with the
    #: whole register on :attr:`RefinementState.holds`, which is what a
    #: checkout restores.  Resolved paths rather than the globs the caller
    #: typed, because that is what ``Refinement.hold`` matched and returned,
    #: and a log replaying the glob against a later model would hold a
    #: different set.
    held: list[str] = Field(default_factory=list)
    unheld: list[str] = Field(default_factory=list)

    def api_call(self) -> str:
        """The equivalent public-API call, so a log doubles as a session script.

        Computed rather than stored: a persisted copy would drift out of sync
        with the structured fields it describes.
        """
        if self.kind == "root":
            return "rx.Refinement(structure, instrument)"
        if self.kind == "stage":
            # each extra is printed only when it differs from the Stage default,
            # so a plain stage's line keeps its pre-WP-1004 text exactly
            extras = "".join(
                f", {n}={v!r}" for n, v, off in
                (("seed", self.seed, 0.0),
                 ("strain_seed", self.strain_seed, 0.0),
                 ("restraint_weight_scale", self.restraint_weight_scale, 1.0),
                 ("ftol", self.ftol, None),
                 ("window_slack_deg", self.window_slack_deg, None))
                if v != off)
            return (f"ref.run_stage(data, rx.Stage({self.name!r}, {self.turn_on!r}, "
                    f"max_iter={self.max_iter}{extras}))")
        if self.kind == "set_vary":
            parts = []
            if self.turn_on:
                parts.append(f"ref.set_vary({self.turn_on!r}, True)")
            if self.turn_off:
                parts.append(f"ref.set_vary({self.turn_off!r}, False)")
            return "; ".join(parts)
        if self.kind == "set_value":
            return f"ref.set_values({self.values!r})"
        if self.kind == "set_tie":
            parts = []
            for path, spec in self.ties.items():
                if not spec.terms:
                    # a derived tie with no sources is not something a verb
                    # declares, so the log says what it is rather than
                    # rendering a call that does not exist
                    parts.append(f"# {path} = {spec.describe()}")
                    continue
                if len(spec.terms) == 1:
                    # the one-source spelling, kept byte for byte: it is what
                    # `ref.tie(path, source, scale=…)` prints, and a log is
                    # read as a session script
                    src, scale = spec.terms[0]
                    args = f"{path!r}, {src!r}"
                    if scale != 1.0:
                        args += f", scale={scale!r}"
                else:
                    # WP-1119 gave `tie` a multi-source form, so this renders a
                    # call that runs rather than the comment it used to
                    args = f"{path!r}, {dict(spec.terms)!r}"
                if spec.const:
                    args += f", offset={spec.const!r}"
                parts.append(f"ref.tie({args})")
            if self.untied:
                parts.append(f"ref.untie({self.untied!r})")
            return "; ".join(parts)
        if self.kind == "set_variable":
            parts = []
            for name, prm in self.variables.items():
                args = f"{name!r}, {prm.value!r}"
                for field, default in (("vary", False), ("min", -math.inf),
                                       ("max", math.inf), ("transform", "identity"),
                                       ("unit", None)):
                    got = getattr(prm, field)
                    if got != default:
                        args += f", {field}={got!r}"
                parts.append(f"ref.add_variable({args})")
            for name in self.removed_variables:
                parts.append(f"ref.remove_variable({name!r})")
            return "; ".join(parts)
        if self.kind == "set_hold":
            parts = []
            if self.held:
                parts.append(f"ref.hold({self.held!r})")
            if self.unheld:
                parts.append(f"ref.unhold({self.unheld!r})")
            return "; ".join(parts)
        if self.kind == "merge":
            return f"ref.merge(...)  # {self.name}"
        return f"# model edited: {self.name or 'structure/instrument replaced'}"


class ReflectionState(Base):
    """Per-hkl intensities, the state that is *not* in the parameter vector.

    Le Bail (Le Bail, Duroy & Fourquet, 1988, Mater. Res. Bull. 23, 447)
    extracts intensities by iterated partitioning of the observed profile.
    They are seeded flat and refined by a fixed-point loop, so they are
    **path-dependent**: they cannot be recovered from
    ``(structure, instrument, pattern)`` alone, and storing them is a
    correctness requirement for restoring a Le Bail checkpoint, not an
    optimisation.

    Pawley (1981, J. Appl. Cryst. 14, 357) puts the same quantities *into* the
    parameter vector instead.  Both live here, tagged by ``kind``, so that the
    v0.3 Pawley mode does not have to push one dot-path per reflection into
    :attr:`RefinementState.free_paths` on every node.
    """

    phase_index: int
    hkl: list[list[int]] = Field(default_factory=list)  # (N, 3)
    #: m of Q = H + m·k per row, for a phase carrying a propagation vector
    #: (WP-1326).  ``None`` — every phase that declares no k — is not the same
    #: as a list of zeros: it says the phase has no satellites, so ``hkl``
    #: alone is a complete key.  With a k it is not: H + k and H − k share one
    #: H.  A node written without satellites is what it was **apart from the
    #: new** ``"satellite_order": null``, as ``stderr`` beside it and every
    #: other optional field in these schemas serialize: none is excluded when
    #: ``None`` (pydantic's ``exclude_if`` postdates the ``pydantic>=2.6``
    #: floor), and SCHEMA 0.32's paragraph says so.
    satellite_order: list[int] | None = None
    intensity: list[float] = Field(default_factory=list)  # (N,)
    kind: Literal["lebail_extracted", "pawley_refined"] = "lebail_extracted"
    stderr: list[float] | None = None  # Pawley has esds; Le Bail does not
    varied: bool = False  # were these free in θ?


class RefinementState(Base):
    """Everything needed to reconstruct a refinement exactly."""

    structure: Structure
    instrument: Instrument
    mode: Mode = "rietveld"
    # Named scalar parameters only — never one entry per reflection.
    # ``apply_to_models`` writes values but not vary flags, so the free set has
    # to be carried alongside the models.
    free_paths: list[str] = Field(default_factory=list)
    two_theta_limits: tuple[float, float] | None = None
    reflections: list[ReflectionState] = Field(default_factory=list)
    # User constraints (WP-1070), path → the affine dependence declared for it.
    # Carried for the same reason as ``free_paths``: a tie is not a property of
    # the models — ``ParameterTable`` derives the *symmetry* ties from the space
    # group on every build and knows nothing about a user's — so a node that did
    # not carry them would restore a state with the constraints silently gone,
    # and the parameter count with them.
    ties: dict[str, TieSpec] = Field(default_factory=dict)
    # Named variables (WP-1119), bare name → its declaration.  Carried for the
    # reason ``ties`` is, one step further along: a variable is not a property
    # of the models *at all* — it has no field for ``apply_to_models`` to write
    # to — so the document is its only source of truth, and a node that did not
    # carry it would restore a state whose ties reference a parameter that no
    # longer exists.
    variables: dict[str, Parameter] = Field(default_factory=dict)
    # Caller-declared holds (WP-1435), the paths a plan's ``turn_on`` may not
    # free.  Carried for the reason ``ties`` is: a hold is not a property of
    # the models, ``vary`` cannot express it (a plan replaces the vary flags),
    # and a node that did not carry it would restore a state where the
    # declaration had silently lapsed.  A hold that does not survive reopening
    # a ``.rex`` is worse than no hold, being a promise that expires quietly.
    holds: list[str] = Field(default_factory=list)


class NodeMetrics(Base):
    """Cached scalars so queries (``best``, ``compare``) need no recompute.

    These are *as-optimised* values: the agreement the least squares actually
    reached on the model it was minimising, whose reflection list, windows and
    FCJ node counts were frozen at the parameter values the stage *started*
    from.  Recomputing the same state with a fresh compile (``refine.replay``)
    can differ slightly, because the refreshed freeze is built at the values
    the stage *ended* on.

    The gap is itself informative: a large one means the stage travelled far
    enough that its frozen discreteness went stale, which is a reason to split
    the stage rather than a bug.
    """

    statistics: Statistics | None = None
    #: the solver's termination, copied from the stage's own ``StageResult``,
    #: so it carries that type's three-value vocabulary and nothing more.
    #: ``None`` is a node that ran no fit — a ``set_vary``, a ``set_value``, a
    #: ``root`` — which is the only extra state there is; the spare
    #: ``"skipped"`` this admitted until WP-1076 had no meaning left to take.
    status: Literal["converged", "max_iter", "diverged"] | None = None
    n_iterations: int = 0
    cost_initial: float | None = None
    cost_final: float | None = None
    stderr: dict[str, float] = Field(default_factory=dict)  # physical esds by path


class HistoryNode(Base):
    """One immutable checkpoint in the refinement DAG."""

    id: str
    # A list, not a scalar: combining branches ("cell from A, background from
    # B") is a genuine refinement move with two parents.  Allowing it in the
    # schema costs nothing now; retrofitting it would be a format break.
    parents: list[str] = Field(default_factory=list)
    action: NodeAction
    state: RefinementState
    metrics: NodeMetrics = Field(default_factory=NodeMetrics)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    label: str = ""
    created_utc: str = ""
    scores: dict[str, float] = Field(default_factory=dict)  # agent bookkeeping
    notes: dict[str, str] = Field(default_factory=dict)

    @property
    def parent(self) -> str | None:
        return self.parents[0] if self.parents else None

    @property
    def rwp(self) -> float | None:
        return self.metrics.statistics.rwp if self.metrics.statistics else None


class TreeHeader(Base):
    """Identifies the tree and the pattern every node is fitted against."""

    tree_id: str
    created_utc: str = ""
    data_fingerprint: str = ""  # sha256 of two_theta + intensity bytes
    data_source: str = ""
    n_points: int = 0
    plan: PlanSpec | None = None
    package_version: str = ""
    schema_version: str = SCHEMA_VERSION


class Annotation(Base):
    """An append-only overlay: labels, refs and scores, applied after nodes."""

    node_id: str = ""
    label: str | None = None
    refs: dict[str, str] = Field(default_factory=dict)  # name → node id
    scores: dict[str, float] = Field(default_factory=dict)
    notes: dict[str, str] = Field(default_factory=dict)


class HistoryRecord(Base):
    """One JSONL line.  Tagged union so the log stays append-only."""

    record: Literal["header", "node", "annotation"]
    header: TreeHeader | None = None
    node: HistoryNode | None = None
    annotation: Annotation | None = None
