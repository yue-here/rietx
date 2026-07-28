"""The public refinement API: :class:`Refinement` and :func:`refine`."""

from __future__ import annotations

import warnings
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .io.exporters import ReflectionRow

from .backend.api import backend_dtype_note
from .history.events import as_event_stream
from .history.store import fingerprint
from .history.tree import RefinementTree
from .model.absorption import (
    CYLINDER_MU_R_MAX,
    equivalent_delta_biso,
    equivalent_delta_biso_from_transmission,
    mu_t_identifiable_fraction,
    transmission_intensity_fraction,
)
from .model.forward import CompiledModel, Mode, compile_model
from .model.restraints import summarise_restraints
from .optimize.least_squares import run_least_squares
from .optimize.qpa import (
    compute_qpa,
    estimate_capillary_mu_r,
    estimate_flat_plate_mu_t,
    microabsorption_diagnostics,
)
from .optimize.statistics import compute_statistics
from .params.vector import ParameterTable
from .schemas.common import Diagnostic, Provenance
from .schemas.history import NodeAction, NodeMetrics, RefinementState, ReflectionState
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData
from .schemas.results import (
    AbsorptionCorrection,
    RefinedParameter,
    RefinementResult,
    StageResult,
)
from .schemas.structure import Structure
from .strategy.staged import PLAN_PRESETS, RefinementPlan, Stage, check_guards

try:
    _VERSION = version("pxrd-refine")
except PackageNotFoundError:  # editable/dev fallback
    _VERSION = "0.0.0+dev"

def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Refinement:
    """Refine ``structure`` + ``instrument`` against a powder pattern.

    The input models are deep-copied; refined values are exposed on
    ``fitted_structure`` / ``fitted_instrument`` after :meth:`fit`.

    Borrowing git's split: this object is the *working tree* (mutable, holds
    the current parameter values), while :attr:`history` is an append-only DAG
    of immutable checkpoints.  Each stage auto-commits a node, so any
    intermediate state can be restored with :meth:`checkout` and continued
    down a different branch with :meth:`run_stage`.

    Pass ``history=False`` for the light path: no snapshots, no per-stage
    statistics, no serialisation.
    """

    def __init__(self, structure: Structure, instrument: Instrument, *,
                 backend: str = "numpy",
                 history: bool | str | Path | RefinementTree = True):
        if backend != "numpy":
            # fail fast (with the install hint) instead of at the first stage;
            # resolve_backend caches the instance, so this costs one import
            from .backend import resolve_backend

            try:
                resolve_backend(backend)
            except ValueError as exc:
                raise NotImplementedError(str(exc)) from exc
        self._backend = backend
        self.structure = structure.model_copy(deep=True)
        self.instrument = instrument.model_copy(deep=True)
        # Resolve a capillary µR from composition once, here, rather than per
        # stage: µR is a property of the specimen as mounted, so it must not
        # chase the refinement.  Writing it onto the (already copied)
        # instrument makes the value visible in ``fitted_instrument`` and in
        # every history snapshot instead of hiding inside the compiled model.
        self._mu_r_source, self._mu_r_skipped = _resolve_specimen_absorption(
            self.structure, self.instrument)
        self.result_: RefinementResult | None = None
        self._model: CompiledModel | None = None

        # history state
        self.history: RefinementTree | None = None
        self._history_spec = history
        self._head_id: str | None = None
        if isinstance(history, RefinementTree):
            self.history = history
            self._head_id = history.head

        # carried across calls so a checkout can be continued
        self._mode: Mode = "rietveld"
        self._two_theta_limits: tuple[float, float] | None = None
        self._free_paths: list[str] = []
        self._pending_reflections: list[ReflectionState] = []

    # ------------------------------------------------------------------
    # history plumbing
    # ------------------------------------------------------------------
    def _ensure_history(self, data: PatternData,
                        plan: RefinementPlan | None = None) -> RefinementTree | None:
        """Create the tree on first use (it needs the pattern to fingerprint)."""
        spec = self._history_spec
        if self.history is None:
            if not spec:
                return None
            path = None if spec is True else spec
            self.history = RefinementTree.for_data(
                data, path=path, plan=plan, package_version=_VERSION)
        if len(self.history) == 0:
            root = self.history.add(
                parents=[], action=NodeAction(kind="root"), state=self.snapshot())
            self._head_id = root.id
        return self.history

    def _require_history(self) -> RefinementTree:
        if self.history is None:
            raise RuntimeError(
                "this Refinement has no history; construct it with "
                "history=True (the default) or history='path.jsonl' to enable "
                "checkpoints and branching")
        return self.history

    def snapshot(self, *, model: CompiledModel | None = None) -> RefinementState:
        """The full state needed to reconstruct this refinement exactly."""
        return RefinementState(
            structure=self.structure.model_copy(deep=True),
            instrument=self.instrument.model_copy(deep=True),
            mode=self._mode,
            free_paths=list(self._free_paths),
            two_theta_limits=self._two_theta_limits,
            reflections=_extract_reflections(model or self._model),
        )

    def _record(self, tree: RefinementTree, action: NodeAction, model: CompiledModel,
                table: ParameterTable, outcome, diagnostics) -> str:
        values = table.decode(outcome.theta)
        y_calc = model.evaluate(values)
        stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                   n_free=len(table.free_paths) + _pawley_n(model),
                                   y_background=model.background(values))
        stderr = (table.stderr_physical(outcome.theta, outcome.stderr_internal,
                                        outcome.correlation)
                  if outcome.stderr_internal is not None else {})
        metrics = NodeMetrics(
            statistics=stats, status=outcome.status, n_iterations=outcome.n_iterations,
            cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
            stderr=stderr)
        node = tree.add(
            parents=[self._head_id] if self._head_id else [],
            action=action, state=self.snapshot(model=model),
            metrics=metrics, diagnostics=diagnostics)
        self._head_id = node.id
        return node.id

    # ------------------------------------------------------------------
    # branching
    # ------------------------------------------------------------------
    def checkout(self, node_id: str) -> "Refinement":
        """Restore the state recorded at ``node_id`` (a node id or a tag).

        Mutates this object's working state, like ``git checkout``.  The node
        itself is untouched.
        """
        tree = self._require_history()
        node = tree[node_id]
        self.structure = node.state.structure.model_copy(deep=True)
        self.instrument = node.state.instrument.model_copy(deep=True)
        self._mode = node.state.mode
        self._two_theta_limits = node.state.two_theta_limits
        self._free_paths = list(node.state.free_paths)
        self._pending_reflections = [r.model_copy(deep=True) for r in node.state.reflections]
        self._head_id = node.id
        self._model = None
        self.result_ = None
        tree.set_head(node.id)
        return self

    def branch(self, node_id: str | None = None) -> "Refinement":
        """A second working tree over the same history, for a rival strategy."""
        tree = self._require_history()
        ref = Refinement(self.structure, self.instrument,
                         backend=self._backend, history=tree)
        ref._mode = self._mode
        ref._two_theta_limits = self._two_theta_limits
        ref._free_paths = list(self._free_paths)
        ref._head_id = self._head_id
        ref._pending_reflections = [r.model_copy(deep=True) for r in self._pending_reflections]
        if node_id is not None:
            ref.checkout(node_id)
        return ref

    def edit(self, *, structure: Structure | None = None,
             instrument: Instrument | None = None, label: str = "") -> str | None:
        """Record a change to the model itself — adding an impurity phase,
        raising the background order, swapping the geometry.

        Structural edits are refinement moves too: they belong in the history
        beside the stages, so a branch that adds a phase can be compared
        against one that does not.  Returns the new node id (``None`` when
        history is disabled).
        """
        if structure is not None:
            self.structure = structure.model_copy(deep=True)
        if instrument is not None:
            self.instrument = instrument.model_copy(deep=True)
        self._model = None
        self.result_ = None
        if self.history is None:
            return None
        node = self.history.add(
            parents=[self._head_id] if self._head_id else [],
            action=NodeAction(kind="edit_model", name=label or "model edited"),
            state=self.snapshot(), label=label)
        self._head_id = node.id
        return node.id

    @classmethod
    def from_node(cls, tree: RefinementTree, node_id: str, *,
                  backend: str = "numpy") -> "Refinement":
        """Open a refinement positioned at an existing checkpoint."""
        node = tree[node_id]
        ref = cls(node.state.structure, node.state.instrument,
                  backend=backend, history=tree)
        return ref.checkout(node_id)

    def merge(self, other: str, *, prefer: str = "theirs",
              label: str = "") -> str:
        """Three-way merge of another branch into the current state.

        Parameter values are merged per dot-path against the two branches'
        **common ancestor** (git semantics): a path changed on only one side
        takes that side's value; a path changed on both takes ``prefer``
        ("ours" = current head, "theirs" = the merged branch).  The merged
        node records *both* parents — the reason ``HistoryNode.parents`` has
        always been a list.

        Only parameter values merge; the model *composition* (which phases,
        background type, free set, mode) comes from ``prefer``'s side whole —
        merging a phase-added branch into a phase-removed one path-by-path is
        not meaningful.  Returns the merge node's id.
        """
        tree = self._require_history()
        ours_id = self._head_id
        if ours_id is None:
            raise RuntimeError("nothing committed yet on this branch")
        theirs_id = tree.resolve(other)
        base = tree.common_ancestor(ours_id, theirs_id)
        if base is None:
            raise ValueError(f"{ours_id} and {theirs_id} share no ancestor")
        if prefer not in ("ours", "theirs"):
            raise ValueError("prefer must be 'ours' or 'theirs'")

        values_base = tree._values(tree[base])
        values_ours = tree._values(tree[ours_id])
        values_theirs = tree._values(tree[theirs_id])

        # composition from the preferred side
        if prefer == "theirs":
            self.checkout(theirs_id)
        merged = dict(values_ours if prefer == "ours" else values_theirs)
        for path in set(values_base) & set(values_ours) & set(values_theirs):
            b, o, t = values_base[path], values_ours[path], values_theirs[path]
            if o != b and t == b:
                merged[path] = o
            elif t != b and o == b:
                merged[path] = t
            # both changed → keep the preferred side (already in `merged`)

        table = ParameterTable(self.structure, self.instrument)
        for e in table.entries:
            if e.path in merged:
                e.value = merged[e.path]
        table.apply_to_models(self.structure, self.instrument)
        self._model = None
        self.result_ = None

        node = tree.add(
            parents=[ours_id, theirs_id],
            action=NodeAction(kind="merge",
                              name=label or f"merge {theirs_id} (prefer {prefer})"),
            state=self.snapshot(), label=label)
        self._head_id = node.id
        return node.id

    def cherry_pick(self, node_id: str, data: PatternData) -> RefinementResult:
        """Re-run another node's *stage action* on top of the current state.

        Takes the recorded action (stage name, turn-on globs, iteration
        budget) — not the recorded parameter values — and executes it from
        here, exactly like ``git cherry-pick`` replays a commit's diff.  This
        is the enabling verb for reusing a refined strategy on a different
        branch (and, in v0.5, on a different sample via
        ``SequentialRefinement``).
        """
        tree = self._require_history()
        node = tree[node_id]
        if node.action.kind != "stage":
            raise ValueError(
                f"{node.id} records a {node.action.kind!r} action; only stage "
                "nodes can be cherry-picked")
        stage = Stage(node.action.name or "cherry-pick",
                      list(node.action.turn_on),
                      max_iter=node.action.max_iter or 100,
                      lebail_cycles=node.action.lebail_cycles or 3)
        return self.run_stage(data, stage)

    # ------------------------------------------------------------------
    # fitting
    # ------------------------------------------------------------------
    def _prepare_table(self, *, restore: bool) -> ParameterTable:
        table = ParameterTable(self.structure, self.instrument)
        table.set_vary(["*"], False)
        if restore and self._free_paths:
            missing = [p for p in self._free_paths if not table.set_vary([p], True)]
            if missing:
                # set_vary reports no hits for a path that no longer exists
                # (e.g. a phase was removed); dropping it silently would lose
                # refinement state without a trace.
                warnings.warn(
                    f"{len(missing)} restored parameter path(s) no longer exist "
                    f"and were dropped: {missing[:5]}"
                    f"{'…' if len(missing) > 5 else ''}",
                    UserWarning, stacklevel=3)
        return table

    def _run_stage(self, stage: Stage, data: PatternData, mode: Mode,
                   table: ParameterTable, model: CompiledModel | None,
                   two_theta_limits: tuple[float, float] | None,
                   correlation_guard: float, events=None):
        """One stage: free params, recompile, solve, commit, guard.

        The recompile is what keeps the residual smooth *within* the stage —
        the hkl list, symmetry-op subsets, FCJ node counts and windows are
        frozen here and never move until the next stage.
        """
        freed = table.set_vary(stage.turn_on, True)
        if stage.seed:
            # lift softplus coefficients (e.g. extinction) off the zero floor
            # so TRF has a live gradient this stage
            table.seed_softplus(freed, stage.seed)
        if stage.strain_seed:
            # the Stephens DOFs are identity-transform, so the softplus seed
            # above never sees them; put an all-zero block on the isotropic ray
            table.seed_stephens(freed, stage.strain_seed)
        if mode in ("lebail", "pawley"):
            # never refine structural parameters, the phase scale (degenerate
            # with the per-hkl intensities) or the line-intensity ratio (which
            # those intensities can absorb pairwise) against the intensity
            # model; drop them from the reported freed list too — it must
            # describe the set actually left free
            for path in list(freed):
                if ".atoms." in path or path.endswith(".scale") \
                        or ".source.lines." in path:
                    table.set_vary([path], False)
                    freed.remove(path)

        # regenerate reflection list/windows/FCJ nodes with current values
        # (between-stage refresh; frozen within the stage); the free-path
        # set lets the compiler allocate FCJ nodes for axial parameters
        # that are about to refine from zero
        table.apply_to_models(self.structure, self.instrument)
        new_model = compile_model(self.structure, self.instrument, data, mode=mode,
                                  two_theta_limits=two_theta_limits,
                                  free_paths=set(table.free_paths))
        carried = False
        if model is not None and mode in ("lebail", "pawley") and model.mode == mode:
            _carry_lebail(model, new_model)
            carried = True
        elif mode in ("lebail", "pawley") and self._pending_reflections:
            # first stage after a checkout: re-seed the per-hkl intensities
            _restore_lebail(self._pending_reflections, new_model)
            carried = True
        self._pending_reflections = []
        model = new_model

        if mode == "lebail":
            values = table.decode(table.x0())
            model.lebail_update(values, n_cycles=stage.lebail_cycles)
        elif mode == "pawley":
            if not carried:
                # seed the intensity block from one Le Bail partition — a good
                # warm start for the joint solve; refined values carry onward
                model.lebail_update(table.decode(table.x0()), n_cycles=stage.lebail_cycles)
            # equal-split restraint on overlapped groups, scaled to the current
            # intensities (constant within the coming least-squares run)
            model.build_pawley_restraint()

        if events is not None:
            events.emit("stage_start", stage=stage.name, turn_on=list(stage.turn_on),
                        freed=freed, n_free=len(table.free_paths),
                        n_points=len(model.tt))
        outcome = run_least_squares(model, table, max_iter=stage.max_iter,
                                    events=events, stage=stage.name,
                                    backend=self._backend)
        table.commit(outcome.theta)

        if mode == "lebail":
            model.lebail_update(table.decode(outcome.theta), n_cycles=stage.lebail_cycles)

        guard = check_guards(table, outcome, correlation_guard, model=model)
        if events is not None:
            events.emit("stage_end", stage=stage.name, status=outcome.status,
                        n_iterations=outcome.n_iterations,
                        cost_initial=outcome.cost_initial,
                        cost_final=outcome.cost_final)
        return model, outcome, guard, freed

    def fit(self, data: PatternData, *, mode: Mode = "rietveld",
            plan: RefinementPlan | str = "mccusker_default",
            two_theta_limits: tuple[float, float] | None = None,
            events=None) -> RefinementResult:
        """Run a staged refinement.

        ``events`` — optional per-iteration telemetry: a path (JSONL appended),
        a callable (called per event dict), or an
        :class:`~pxrdref.history.events.EventStream`.  See that module for the
        record format; ``pxrdref watch`` tails it live.
        """
        if isinstance(plan, str):
            if plan == "mccusker_default" and mode == "lebail":
                plan = "profile_only"
            elif plan == "mccusker_default" and mode == "pawley":
                plan = "pawley_default"
            try:
                plan = PLAN_PRESETS[plan]()
            except KeyError:
                raise ValueError(
                    f"unknown plan preset {plan!r}; available: {sorted(PLAN_PRESETS)}"
                ) from None

        self._mode = mode
        self._two_theta_limits = two_theta_limits
        self._free_paths = []
        tree = self._ensure_history(data, plan)
        stream = as_event_stream(events)
        if stream is not None:
            stream.emit("fit_start", mode=mode,
                        stages=[s.name for s in plan.stages],
                        n_points=len(data.two_theta))

        # stages are cumulative: start from everything the user left vary=True…
        # …but the staged plan drives the turn-on sequence explicitly
        table = self._prepare_table(restore=False)

        diagnostics: list[Diagnostic] = _dispersion_diagnostics(
            self.structure, self.instrument)
        stage_results: list[StageResult] = []
        outcome = None
        model = None

        for stage in plan.stages:
            model, outcome, guard, freed = self._run_stage(
                stage, data, mode, table, model, two_theta_limits,
                plan.correlation_guard, events=stream)
            stage_diagnostics = _guard_diagnostics(guard)
            diagnostics.extend(stage_diagnostics)
            stage_results.append(StageResult(
                name=stage.name, status=outcome.status, n_iterations=outcome.n_iterations,
                cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
                freed=freed,
            ))
            if stream is not None and hasattr(stream, "write_snapshot"):
                # live monitoring (viz.live.LiveSession): rewrite the HTML view
                stream.write_snapshot(model, table, outcome, stage.name)
            if tree is not None:
                table.apply_to_models(self.structure, self.instrument)
                self._free_paths = list(table.free_paths)
                self._record(tree, NodeAction(
                    kind="stage", name=stage.name, turn_on=list(stage.turn_on),
                    max_iter=stage.max_iter, lebail_cycles=stage.lebail_cycles,
                ), model, table, outcome, stage_diagnostics)

        assert model is not None and outcome is not None
        self._model = model
        table.apply_to_models(self.structure, self.instrument)
        self._free_paths = list(table.free_paths)

        if mode == "pawley":
            diagnostics.extend(_pawley_unresolved_diagnostics(model, self.structure))

        self.result_ = _build_result(
            model, table, outcome.theta, mode=mode, status=outcome.status,
            stage_results=stage_results, diagnostics=diagnostics,
            structure=self.structure, stderr_internal=outcome.stderr_internal,
            correlation=outcome.correlation, backend=self._backend,
            mu_r_source=self._mu_r_source, mu_r_skipped=self._mu_r_skipped)
        _apply_esds(table, self.result_, self.structure, self.instrument)
        self._stamp(self.result_, tree)
        if stream is not None:
            stream.emit("fit_end", status=self.result_.status,
                        rwp=self.result_.statistics.rwp,
                        gof=self.result_.statistics.gof,
                        node_id=self.result_.node_id)
            if stream is not events:  # we created it from a path/callable
                stream.close()
        return self.result_

    def run_stage(self, data: PatternData, stage: Stage, *,
                  mode: Mode | None = None,
                  two_theta_limits: tuple[float, float] | None = None,
                  correlation_guard: float = 0.98) -> RefinementResult:
        """Run a single stage from the current state, recording a child node.

        This is the incremental verb: after ``checkout``, it continues down a
        new branch.  (``fit`` is the other verb — it resets the free set and
        runs a whole plan from wherever the working state currently is.)
        """
        mode = mode or self._mode
        ttl = two_theta_limits if two_theta_limits is not None else self._two_theta_limits
        self._mode = mode
        self._two_theta_limits = ttl
        tree = self._ensure_history(data)

        table = self._prepare_table(restore=True)
        model, outcome, guard, freed = self._run_stage(
            stage, data, mode, table, self._model, ttl, correlation_guard)
        diagnostics = _guard_diagnostics(guard)
        if mode == "pawley":
            diagnostics.extend(_pawley_unresolved_diagnostics(model, self.structure))

        self._model = model
        table.apply_to_models(self.structure, self.instrument)
        self._free_paths = list(table.free_paths)

        stage_result = StageResult(
            name=stage.name, status=outcome.status, n_iterations=outcome.n_iterations,
            cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
            freed=freed)
        if tree is not None:
            self._record(tree, NodeAction(
                kind="stage", name=stage.name, turn_on=list(stage.turn_on),
                max_iter=stage.max_iter, lebail_cycles=stage.lebail_cycles,
            ), model, table, outcome, diagnostics)

        self.result_ = _build_result(
            model, table, outcome.theta, mode=mode, status=outcome.status,
            stage_results=[stage_result], diagnostics=diagnostics,
            structure=self.structure, stderr_internal=outcome.stderr_internal,
            correlation=outcome.correlation, backend=self._backend,
            mu_r_source=self._mu_r_source, mu_r_skipped=self._mu_r_skipped)
        _apply_esds(table, self.result_, self.structure, self.instrument)
        self._stamp(self.result_, tree)
        return self.result_

    def _stamp(self, result: RefinementResult, tree: RefinementTree | None) -> None:
        if tree is not None:
            result.node_id = self._head_id
            result.tree_id = tree.header.tree_id

    # ------------------------------------------------------------------
    def predict(self, two_theta=None) -> np.ndarray:
        """y_calc at the fitted parameters.

        With no argument, evaluates on the fit grid.  With an array of 2θ
        values, compiles a fresh model on that grid (Le Bail extracted
        intensities are carried over by hkl).
        """
        if self._model is None or self.result_ is None:
            raise RuntimeError("call fit() first")
        table = ParameterTable(self.structure, self.instrument)
        if two_theta is None:
            return self._model.evaluate(table.decode(table.x0()))
        tt = np.asarray(two_theta, dtype=np.float64)
        grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
        model = compile_model(self.structure, self.instrument, grid,
                              mode=self._mode, free_paths=set(table.free_paths))
        if self._mode in ("lebail", "pawley"):
            _carry_lebail(self._model, model)
        return model.evaluate(table.decode(table.x0()))

    def report(self, *, plan: RefinementPlan | str | None = None, **kw):
        """The full :class:`~pxrdref.report.FitReport` for the last fit.

        Unlike ``build_report(result)``, this has the compiled model in hand,
        so Layers 1-2 (misfit attribution and typed suggested actions) are
        computed — subject to their gates.  ``plan`` supplies the Layer-2
        strategy veto; pass the plan you ran (or its preset name).
        """
        from .report import build_report

        if self._model is None or self.result_ is None:
            raise RuntimeError("call fit() first")
        if isinstance(plan, str):
            plan = PLAN_PRESETS[plan]()
        table = ParameterTable(self.structure, self.instrument)
        return build_report(self.result_, model=self._model,
                            values=table.decode(table.x0()), plan=plan,
                            free_paths=list(self._free_paths), **kw)

    # ------------------------------------------------------------------
    # exporters (WP-0309): reflection table, refinement CIF, QPA table
    # ------------------------------------------------------------------
    def reflection_table(self) -> list["ReflectionRow"]:
        """Every (emission line, reflection) of the last fit as typed rows.

        See :func:`pxrdref.io.exporters.reflection_table`.  In Le Bail/Pawley
        mode the intensities are the extracted/refined ones held on the model.
        """
        from .io.exporters import reflection_table

        if self._model is None or self.result_ is None:
            raise RuntimeError("call fit() first")
        table = ParameterTable(self.structure, self.instrument)
        values = table.decode(table.x0())
        return reflection_table(self._model, values, self.structure)

    def write_reflection_table(self, path, **kw) -> None:
        """Write the reflection table to CSV/TSV (delimiter from the suffix)."""
        from .io.exporters import write_reflection_table

        write_reflection_table(self.reflection_table(), path, **kw)

    def write_cif(self, path) -> None:
        """Write a refinement CIF: structure with esds, R-factors, wavelength,
        profile/background description, and the observed/calculated pattern."""
        from .io.exporters import write_refinement_cif

        if self.result_ is None:
            raise RuntimeError("call fit() first")
        write_refinement_cif(self.result_, self.structure, self.instrument, path)

    def write_qpa_table(self, path, **kw) -> None:
        """Write the QPA weight-fraction table (crystalline-only caveat included)."""
        from .io.exporters import write_qpa_table

        if self.result_ is None or self.result_.qpa is None:
            raise RuntimeError("no QPA on this result (Rietveld fits only)")
        write_qpa_table(self.result_.qpa, path, **kw)

    @property
    def fitted_structure(self) -> Structure:
        return self.structure

    @property
    def fitted_instrument(self) -> Instrument:
        return self.instrument


# ----------------------------------------------------------------------
# module-level helpers
# ----------------------------------------------------------------------
def _guard_diagnostics(guard) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for msg in guard.high_correlations:
        out.append(Diagnostic(
            level="warning", code="HIGH_CORRELATION", message=msg,
            suggestion="consider fixing one of the correlated parameters",
        ))
    for path in guard.at_bounds:
        out.append(Diagnostic(
            level="warning", code="BOUND_HIT", where=[path],
            message=f"{path} refined to its bound",
            suggestion="widen the bound or fix the parameter",
        ))
    for msg in guard.nonpositive_adps:
        path = msg.split(" ")[0]
        out.append(Diagnostic(
            level="warning", code="ADP_NOT_POSITIVE_DEFINITE", where=[path],
            message=f"the anisotropic displacement tensor of {msg} is not "
                    "positive definite — it is not an ellipsoid, and its "
                    "Debye-Waller factor grows without bound at high Q",
            suggestion="the data probably do not support this many "
                       "displacement parameters: revert the site to an "
                       "isotropic biso, check the occupancy and species "
                       "assignment, or extend the fit range; do not report "
                       "the tensor as measured",
        ))
    for msg in guard.nonpositive_strain:
        path = msg.split(" ")[0]
        out.append(Diagnostic(
            level="warning", code="STEPHENS_STRAIN_NOT_POSITIVE", where=[path],
            message=f"the Stephens strain coefficients of {msg} — σ²(M) is a "
                    "variance, so a negative value is not a large anisotropy "
                    "but coefficients outside the physical cone, and those "
                    "reflections silently get no strain broadening at all",
            suggestion="the data do not support this many strain patterns in "
                       "this direction: restart from the isotropic limit "
                       "(StephensStrain.isotropic), refine fewer patterns (a "
                       "higher-symmetry Laue class has fewer), or extend the "
                       "fit range; do not report the S_HKL as measured",
        ))
    for msg in guard.background_correlations:
        path = msg.split(" ")[0]
        out.append(Diagnostic(
            level="warning", code="BACKGROUND_ABSORPTION", where=[path],
            message=f"the background can reproduce most of {msg}",
            suggestion="stiffen the background (fewer Chebyshev terms, larger "
                       "P-spline lambda_smooth, coarser knots) or hold an "
                       "estimated curve additively; ADPs, scales and any QPA "
                       "fractions from this fit are biased even though Rwp "
                       "looks good",
        ))
    for msg in guard.roughness_correlations:
        path = msg.split(" ")[0]
        rough = "surface_roughness" in path
        out.append(Diagnostic(
            level="warning", code="ROUGHNESS_ABSORPTION", where=[path],
            message=(f"surface roughness is not separable from the "
                     f"displacement/scale/background block here — {msg} of the "
                     f"roughness column is reproducible by it"
                     if rough else
                     f"most of {msg} is reproducible by the surface-roughness "
                     f"block: this displacement parameter is hiding in it"),
            suggestion=("extend the fit to lower 2θ, where roughness has a "
                        "lever arm the displacement parameters do not, or hold "
                        "roughness fixed at an independently measured value; "
                        "refining both against this range reports two numbers "
                        "where the data support one, and their esds understate "
                        "it (Pitschke et al. 1993 Table III: uncorrected "
                        "roughness drives Biso negative, so neither leaving it "
                        "out nor freeing it blind is safe)"),
        ))
    return out


def _apply_esds(table: ParameterTable, result: RefinementResult,
                structure: Structure, instrument: Instrument) -> None:
    """Carry the fitted esds into the models, so exporters can quote them.

    Parameters the fit did not estimate get ``stderr = None`` rather than a
    stale value from an earlier stage — that is why the whole map is rewritten
    instead of only the entries that have one.
    """
    table.apply_to_models(structure, instrument, stderr={
        p.path: p.stderr for p in result.parameters if p.stderr is not None})


def _resolve_specimen_absorption(structure: Structure,
                            instrument: Instrument) -> tuple[str, str | None]:
    """Fill in ``Geometry.mu_r`` **or** ``Geometry.mu_t`` from composition, in
    place.  Returns ``(source, skipped_reason)``.

    Only acts when the geometry declares a specimen dimension (capillary radius
    or flat-specimen thickness) and no explicit dimensionless product — an
    explicit value always wins, because the user measured their specimen and we
    did not.  Failure to estimate leaves the field at ``None`` (correction off)
    and returns the reason, which the result then reports: silently running with
    no absorption after the user asked for it would be the worst of the three
    outcomes.
    """
    geom = instrument.geometry
    if geom.kind == "debye_scherrer":
        if geom.capillary_radius_mm is None or geom.mu_r is not None:
            return "given", None
        table = ParameterTable(structure, instrument)
        mu_r, reason = estimate_capillary_mu_r(
            structure, table.decode(table.x0()),
            instrument.source.primary_wavelength,
            geom.capillary_radius_mm, geom.packing_fraction)
        if mu_r is None:
            return "estimated", reason
        geom.mu_r = mu_r
        return "estimated", None

    if geom.thickness_mm is None or geom.mu_t is not None:
        return "given", None
    table = ParameterTable(structure, instrument)
    mu_t, reason = estimate_flat_plate_mu_t(
        structure, table.decode(table.x0()),
        instrument.source.primary_wavelength,
        geom.thickness_mm, geom.packing_fraction)
    if mu_t is None:
        return "estimated", reason
    geom.mu_t = mu_t
    return "estimated", None


#: |ΔBiso| (Å²) above which a declared flat-specimen thickness is worth telling
#: the user about.  Gated on the **bias**, not on the identifiable fraction:
#: that fraction is 3-47 % for every flat-plate µt worth declaring — including
#: µt ≥ 2, where A is within 1 % of 1 everywhere and there is nothing to say —
#: so a fence on it would fire always, which WP-0502 established is a fence
#: that measures nothing.  0.05 Å² is roughly a typical Biso esd and ~10 % of a
#: typical Biso: below it the correction cannot move a quoted displacement
#: parameter outside its own uncertainty.
FLAT_PLATE_BIAS_MIN = 0.05


def _absorption_record(model: CompiledModel, source: str, skipped: str | None,
                       values: dict[str, float] | None = None):
    """The :class:`AbsorptionCorrection` record, or None when nothing applies."""
    if model.mode != "rietveld":
        return None
    lam = model.line_wavelengths[0] if model.line_wavelengths else model.wavelength
    if model.geometry_kind == "debye_scherrer":
        if not model.mu_r and skipped is None:
            return None
        return AbsorptionCorrection(
            mu_r=float(model.mu_r), mu_r_source=source, wavelength=float(lam),
            equivalent_delta_biso=equivalent_delta_biso(model.mu_r, lam),
            skipped=skipped, out_of_range=model.mu_r > CYLINDER_MU_R_MAX)

    transmission = model.geometry_kind == "flat_plate_transmission"
    # transmission always applies its factor (sec θ survives at µt = 0), so it
    # always gets a record; reflection with no declared thickness applied
    # nothing and says nothing
    if not transmission and model.mu_t is None and skipped is None:
        return None
    mu_t = 0.0 if model.mu_t is None else float(model.mu_t)
    delta_biso = unabsorbed = identifiable = None
    positions = _reflection_positions(model, values)
    if (model.mu_t is not None or transmission) and positions.size:
        a = np.asarray(model._absorption(positions), dtype=np.float64)
        delta_biso, unabsorbed = equivalent_delta_biso_from_transmission(
            positions, a, lam)
        identifiable = mu_t_identifiable_fraction(positions, mu_t,
                                                  model.geometry_kind)
    return AbsorptionCorrection(
        method=("flat_plate_transmission" if transmission
                else "flat_plate_reflection"),
        mu_r=mu_t, mu_r_source=source, wavelength=float(lam),
        equivalent_delta_biso=delta_biso or 0.0, skipped=skipped,
        unabsorbed_fraction=unabsorbed, identifiable_fraction=identifiable,
        intensity_fraction_of_optimal=(
            transmission_intensity_fraction(mu_t) if transmission else None))


def _reflection_positions(model: CompiledModel,
                          values: dict[str, float] | None) -> np.ndarray:
    """In-range Bragg 2θ of every modelled reflection, primary line.

    Where an intensity correction is *judged* — never on the fitted grid, which
    can start far below the first peak and make a correction look enormous that
    no modelled reflection ever experienced (WP-0502 measured exactly that on
    the round-robin patterns).
    """
    if not model.phases or values is None:
        return np.empty(0)
    positions = np.concatenate(
        [np.asarray(model.phase_peaks(ip, values)[0][0], dtype=np.float64)
         for ip in range(len(model.phases))])
    positions = positions[np.isfinite(positions)]
    return positions[(positions >= model.tt_min) & (positions <= model.tt_max)]


def _absorption_diagnostics(record) -> list[Diagnostic]:
    """Surface the ways a specimen absorption correction can mislead."""
    out: list[Diagnostic] = []
    flat = record.method != "rouse_cylinder"
    where = ["instrument.geometry." + ("mu_t" if flat else "mu_r")]
    if record.skipped is not None:
        out.append(Diagnostic(
            level="warning", code="ABSORPTION_ESTIMATE_UNAVAILABLE",
            where=where,
            message=(("a specimen thickness" if flat else "a capillary radius")
                     + " was given but "
                     + ("µt" if flat else "µR")
                     + f" could not be estimated ({record.skipped}); the "
                     "pattern was fitted with NO absorption correction"),
            suggestion=(f"set {where[0]} explicitly, or use a wavelength away "
                        "from an absorption edge of the specimen")))
    if record.out_of_range:
        out.append(Diagnostic(
            level="warning", code="ABSORPTION_MU_R_OUT_OF_RANGE", where=where,
            message=(f"µR = {record.mu_r:.2f} is outside the Rouse et al. "
                     f"(1970) fit's range (µR ≤ {CYLINDER_MU_R_MAX:g}); the "
                     "transmission factor is an extrapolation there"),
            suggestion=("dilute the specimen, use a narrower capillary, or a "
                        "shorter wavelength — pxrdref.estimate_mu_r() shows "
                        "what each choice buys")))
    if flat and abs(record.equivalent_delta_biso) > FLAT_PLATE_BIAS_MIN:
        # Not a fence — the opposite.  It says the correction is doing something
        # to the displacement parameters that is worth the user knowing the size
        # of, so µt is worth measuring rather than taken from a nominal
        # thickness and a guessed packing.  "At least" because the projected
        # bias understates what a weighted fit absorbs, by a factor that grows
        # with the unabsorbed fraction quoted beside it (model/absorption.py).
        residue = record.identifiable_fraction or 0.0
        out.append(Diagnostic(
            level="info", code="ABSORPTION_THICKNESS_MATTERS", where=where,
            message=(f"µt = {record.mu_r:.3f} shifts every Biso by at least "
                     f"{record.equivalent_delta_biso:+.3f} Å², and "
                     f"{100 * residue:.0f} % of its angular signature is not "
                     "reproducible by the scale and the ADPs — so an error in "
                     "the specimen thickness or packing lands partly in the fit "
                     "and partly in the displacement parameters"),
            suggestion=("measure the specimen thickness rather than assuming a "
                        "nominal one; µt is held fixed by design (it is not "
                        "refinable) precisely because it would otherwise "
                        "re-apportion the ADPs")))
    if record.method == "flat_plate_transmission" \
            and record.intensity_fraction_of_optimal is not None \
            and record.intensity_fraction_of_optimal < 0.7:
        out.append(Diagnostic(
            level="info", code="ABSORPTION_PLATE_THICKNESS", where=where,
            message=(f"a transmission plate is brightest at µt = 1, so this one "
                     f"(µt = {record.mu_r:.3f}) delivered "
                     f"{100 * record.intensity_fraction_of_optimal:.0f} % of the "
                     "counts it could have"),
            suggestion=("a plate far from t = 1/µ fits just as well and simply "
                        "measures fewer counts — a specimen-preparation note, "
                        "not a fit problem")))
    return out


def _build_result(model: CompiledModel, table: ParameterTable, theta: np.ndarray, *,
                  mode: Mode, status: str, stage_results: list[StageResult],
                  diagnostics: list[Diagnostic], structure: Structure,
                  stderr_internal=None, correlation=None,
                  backend: str = "numpy",
                  mu_r_source: str = "given",
                  mu_r_skipped: str | None = None) -> RefinementResult:
    values = table.decode(theta)
    y_calc = model.evaluate(values)
    y_bkg = model.background(values)
    stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                               n_free=len(table.free_paths) + _pawley_n(model),
                               y_background=y_bkg)

    stderr_phys = (table.stderr_physical(theta, stderr_internal, correlation)
                   if stderr_internal is not None else {})
    params = []
    for e in table.entries:
        if e.vary or e.tie is not None:
            params.append(RefinedParameter(
                path=e.path, value=e.value, vary=e.vary,
                stderr=stderr_phys.get(e.path),
            ))

    # Tick positions cover **every** emission line, not just the primary one.
    # The calculated pattern really does have a peak at each Kα2 position, and
    # a tick list that omitted them would make the FitReport flag every Kα2
    # peak as an unindexed impurity.
    ticks = {}
    for ip, cp in enumerate(model.phases):
        name = structure.phases[ip].name
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        rows = [cp.reflections.two_theta(cell, lam) + values["instrument.zero_shift"]
                for lam in model.line_wavelengths]
        pos = np.concatenate(rows) if rows else np.array([])
        ticks[name] = sorted(float(p) for p in pos if np.isfinite(p))

    # Quantitative phase analysis from the refined scales.  Le Bail scales are
    # degenerate with the extracted intensities, so QPA is Rietveld-only.  σ(W)
    # comes from the correlated scale block of the covariance (physical_covariance
    # reuses the same Cov_free as stderr_physical → consistent conditioning).
    qpa = None
    if mode == "rietveld":
        scale_paths = [f"phases.{ip}.scale" for ip in range(len(structure.phases))]
        scale_cov = (table.physical_covariance(theta, stderr_internal, correlation,
                                                scale_paths)
                     if stderr_internal is not None else None)
        # Site multiplicities frozen on the compiled model (never re-derived
        # from refined coordinates, which could have drifted near a special
        # position and collapsed an orbit).  The primary emission line feeds
        # the Brindley microabsorption attenuation (µ ∝ λ³ makes the Kα₂
        # offset sub-percent in µ, far smaller in τ).
        multiplicities = [[len(op[0]) for op in cp.sites.ops] for cp in model.phases]
        wavelength = model.line_wavelengths[0] if model.line_wavelengths else None
        qpa = compute_qpa(structure, values, scale_cov, multiplicities,
                          wavelength=wavelength)
        diagnostics = diagnostics + microabsorption_diagnostics(qpa)

    # Soft-restraint summary (bond/angle/value deviations).  Rietveld-only, so
    # model.restraints is None outside it and this is naturally skipped.  A
    # restraint fighting the data (|dev/σ| large) becomes a RESTRAINT_TENSION
    # diagnostic — never hide a bad sub-fit.
    restraints_report = summarise_restraints(model.restraints, values)
    if restraints_report is not None:
        diagnostics = diagnostics + _restraint_tension_diagnostics(
            restraints_report, structure)

    # Specimen absorption: report what was applied and, crucially, the Biso
    # bias it removed — for a capillary Rwp is provably unchanged by it, so
    # nothing else in the result would show that the correction did anything.
    absorption = _absorption_record(model, mu_r_source, mu_r_skipped, values)
    if absorption is not None:
        diagnostics = diagnostics + _absorption_diagnostics(absorption)

    # Surface-roughness regime fences (WP-0502): whether the fitted range can
    # see the correction at all, and whether it left its derivation's domain.
    diagnostics = diagnostics + _roughness_regime_diagnostics(model, values)

    return RefinementResult(
        status=status, mode=mode,
        parameters=params, statistics=stats,
        stages=stage_results, diagnostics=diagnostics,
        provenance=Provenance(package_version=_VERSION, created_utc=_utcnow(),
                              backend=backend, dtype=backend_dtype_note(backend)),
        two_theta=model.tt.tolist(), y_obs=model.y_obs.tolist(),
        y_calc=y_calc.tolist(), y_background=y_bkg.tolist(),
        sigma=model.sigma.tolist(),
        ticks=ticks, qpa=qpa, restraints=restraints_report,
        absorption=absorption,
    )


def _extract_reflections(model: CompiledModel | None) -> list[ReflectionState]:
    """Capture the per-hkl state that is not in the parameter vector.

    Le Bail intensities are tagged ``lebail_extracted`` (no esds); Pawley
    intensities are ``pawley_refined`` and carry their per-reflection esds and
    ``varied=True`` — the distinction is what lets a checkout reseed a Le Bail
    fixed point but restore a Pawley refinement's actual values.
    """
    if model is None or model.mode not in ("lebail", "pawley"):
        return []
    is_pawley = model.mode == "pawley"
    stderr_all = model.pawley.stderr if (is_pawley and model.pawley is not None) else None
    out: list[ReflectionState] = []
    for ip, cp in enumerate(model.phases):
        if cp.hkl_intensity is None:
            continue
        state = ReflectionState(
            phase_index=ip,
            hkl=[[int(v) for v in h] for h in cp.reflections.hkl],
            intensity=[float(v) for v in cp.hkl_intensity],
            kind="pawley_refined" if is_pawley else "lebail_extracted",
            varied=is_pawley,
        )
        if is_pawley and stderr_all is not None:
            a, b = model.pawley.phase_slices[ip]
            state.stderr = [float(v) for v in stderr_all[a:b]]
        out.append(state)
    return out


def _scatter_lebail(lookup: dict[tuple, float], cp_new) -> None:
    """Write intensities into a freshly compiled phase, matching by hkl."""
    if cp_new.hkl_intensity is None:
        return
    for i, h in enumerate(map(tuple, cp_new.reflections.hkl)):
        value = lookup.get(h)
        if value is not None:
            cp_new.hkl_intensity[i] = value


def _carry_lebail(old: CompiledModel, new: CompiledModel) -> None:
    """Carry per-hkl intensities across a stage recompile (match by hkl)."""
    for cp_old, cp_new in zip(old.phases, new.phases, strict=True):
        if cp_old.hkl_intensity is None:
            continue
        lookup = {tuple(h): float(cp_old.hkl_intensity[i])
                  for i, h in enumerate(map(tuple, cp_old.reflections.hkl))}
        _scatter_lebail(lookup, cp_new)


def _restore_lebail(states: list[ReflectionState], model: CompiledModel) -> None:
    """Re-seed per-hkl intensities from a checkpoint (match by hkl)."""
    for state in states:
        if not 0 <= state.phase_index < len(model.phases):
            continue
        lookup = {tuple(h): state.intensity[i] for i, h in enumerate(state.hkl)}
        _scatter_lebail(lookup, model.phases[state.phase_index])


#: a Pawley overlap group is reported unresolved when *any* member carries a
#: relative esd above this — that reflection's intensity is not apportioned by
#: the data even though the group sum is fixed
PAWLEY_UNRESOLVED_REL = 0.3


def _pawley_n(model: CompiledModel | None) -> int:
    """Free-parameter count contributed by the Pawley intensity block."""
    return model.pawley.n if (model is not None and model.pawley is not None) else 0


def _pawley_unresolved_diagnostics(model: CompiledModel,
                                   structure: Structure) -> list[Diagnostic]:
    """Flag overlapped groups whose intensity *split* the data cannot resolve.

    The summed intensity of an overlapped group is determined; its partition is
    not, and the equal-split restraint leaves that ambiguity visible as a large
    per-reflection esd.  A group is reported when *any* member's relative esd
    exceeds :data:`PAWLEY_UNRESOLVED_REL` — a reflection the data cannot pin is a
    confident-wrong-singleton risk even when a stronger neighbour in the same
    group is well determined, so flagging the whole group is the safe report.
    """
    pb = model.pawley
    if pb is None or pb.stderr is None or not pb.groups:
        return []
    intens = model.pawley_x0()
    out: list[Diagnostic] = []
    for g in pb.groups:
        inten = intens[list(g)]
        sd = np.asarray(pb.stderr)[list(g)]
        rel = sd / np.maximum(np.abs(inten), 1e-10)
        if float(np.max(rel)) < PAWLEY_UNRESOLVED_REL:
            continue  # every member is pinned by the data — the split is real
        labels = []
        for gi in g:
            ip, k = _pawley_locate(pb, gi)
            h = tuple(int(v) for v in model.phases[ip].reflections.hkl[k])
            labels.append(f"{structure.phases[ip].name} {h}")
        total = float(np.sum(inten))
        out.append(Diagnostic(
            level="info", code="PAWLEY_OVERLAP_UNRESOLVED", where=labels,
            message=(f"{len(g)} reflections overlap too strongly to split: their "
                     f"summed intensity ({total:.4g}) is determined but at least "
                     f"one individual value is not (relative esd up to "
                     f"{float(np.max(rel)):.0%})"),
            suggestion="treat the group's summed intensity as the datum; the "
                       "per-reflection split is not resolved by these data",
        ))
    return out


#: a species whose |f|² at k = 0 moves by more than this fraction when f′, f″
#: are applied is reported as a neglected correction.  2 % is set by what it
#: costs: the v0.3 QPA acceptance carries a several-wt-% bias whose sign and
#: size the neglected corrections reproduce (WP-0504), and the phases driving
#: it sit at 5-16 %.
DISPERSION_NEGLECT_FRAC = 0.02
#: above this the effect is large enough that the numbers should not be
#: quoted without it, so the diagnostic escalates from info to warning
DISPERSION_NEGLECT_SEVERE = 0.05


def _dispersion_diagnostics(structure: Structure,
                            instrument: Instrument) -> list[Diagnostic]:
    """Flag anomalous corrections the model is *not* applying.

    ``Source.dispersion`` is opt-in, which keeps a file read from silently
    changing everyone's numbers — but "off" must never be a quiet wrong
    answer.  The size reported is the change in |f|² at k = 0,
    ((Z + f′)² + f″²)/Z², which is the fraction by which every reflection of
    that species' contribution is mis-scaled.  A refinement is never blocked
    by a lookup failure here: an untabulated element or an on-edge wavelength
    is skipped, because enabling the block is what should raise, not
    describing it.
    """
    import gemmi

    from .crystallography.dispersion import dispersion, normalize_element

    if instrument.source.dispersion is not None:
        return []
    lam = instrument.source.primary_wavelength
    effects: dict[str, float] = {}
    for phase in structure.phases:
        for atom in phase.atoms:
            try:
                sym = normalize_element(atom.species)
                if sym in effects:
                    continue
                z = float(gemmi.Element(sym).atomic_number)
                fp, fpp = dispersion(sym, lam)
            except (KeyError, ValueError):
                continue
            if z <= 0.0:
                continue
            effects[sym] = abs(((z + fp) ** 2 + fpp ** 2) / z ** 2 - 1.0)
    flagged = {s: v for s, v in effects.items() if v >= DISPERSION_NEGLECT_FRAC}
    if not flagged:
        return []
    worst = max(flagged.values())
    named = ", ".join(f"{s} {v:.0%}" for s, v in
                      sorted(flagged.items(), key=lambda kv: -kv[1]))
    return [Diagnostic(
        level="warning" if worst >= DISPERSION_NEGLECT_SEVERE else "info",
        code="DISPERSION_NEGLECTED",
        message=(f"anomalous scattering is off, but at lambda = {lam:.5f} A it "
                 f"changes the scattering power of {named}"),
        suggestion="set instrument.source.dispersion = Dispersion() — the "
                   "correction is a fixed constant, not a refined parameter, "
                   "and unequal effects across phases bias QPA weight "
                   "fractions directly",
    )]


#: a soft restraint is flagged in tension when its computed value sits more
#: than this many σ from the target — the data and the prior disagree, which
#: must be visible rather than silently averaged into a slightly-worse Rwp
RESTRAINT_TENSION_SIGMA = 3.0


def _restraint_tension_diagnostics(report, structure: Structure) -> list[Diagnostic]:
    """Flag restraints the data fights (|deviation/σ| beyond the threshold)."""
    out: list[Diagnostic] = []
    for row in report.rows:
        if abs(row.deviation_over_sigma) <= RESTRAINT_TENSION_SIGMA:
            continue
        out.append(Diagnostic(
            level="warning", code="RESTRAINT_TENSION",
            where=_restraint_where(row, structure),
            message=(f"{row.kind} restraint deviates "
                     f"{row.deviation_over_sigma:+.1f}σ from its target "
                     f"({row.computed:.4g} vs {row.target:.4g})"),
            suggestion="the data and this restraint disagree: loosen its sigma, "
                       "correct the target, or accept that the measured pattern "
                       "should override the prior (raise sigma so it does)",
        ))
    return out


#: below this modelled depression at the lowest fitted angle, a refined
#: roughness correction is doing nothing the fit could have noticed.  Chosen
#: against the counting statistics it competes with: 1 % of the strongest
#: low-angle peak is at or under the noise of a typical lab scan, so a
#: "correction" that small is a number the data did not constrain.
ROUGHNESS_MIN_DEPRESSION = 0.01


def _roughness_regime_diagnostics(model: CompiledModel,
                                  values: dict[str, float]) -> list[Diagnostic]:
    """Fences on where the roughness models are meaningful (WP-0502).

    Two distinct failures, both invisible in Rwp:

    ``ROUGHNESS_UNCONSTRAINED`` — the refined correction barely departs from
    1.0 anywhere in the fitted range, so its value is arbitrary.  This is
    measured on the *modelled depression*, not on the parameters, because the
    Suortti model reaches the identity from **both** ends (b → 0 and b → ∞ —
    see :class:`~pxrdref.schemas.instrument.RoughnessSuortti`); a test on ``b``
    alone would catch only one of the two dead branches.  It also fires for the
    legitimate case of data that simply starts too high in 2θ to see roughness.

    ``ROUGHNESS_OUTSIDE_REGIME`` — Pitschke only, and taken from that paper's
    own Eq (18): the derivation holds for sinθ ≥ τ.  Between τ and 2τ the
    depression turns back over, and below τ the "correction" *amplifies*
    intensity.  Reported rather than clamped, because clamping would put a kink
    in the residual (the frozen-per-stage smoothness invariant).
    """
    if model.roughness is None or not len(model.tt):
        return []
    import numpy as np

    base = "instrument.geometry.surface_roughness"
    # Evaluated at the **reflection** positions, not over the 2θ grid.  Real
    # data forced this (WP-0502): the IUCr round-robin patterns start at 5° 2θ
    # but their first reflection is at 25-32°, and a grid-based fence happily
    # reported a 27 % depression that no modelled peak ever experienced.
    # Roughness is constrained by low-angle reflections, so that is where it
    # has to be judged.
    positions = np.concatenate(
        [np.asarray(pos) for ip in range(len(model.phases))
         for pos, *_ in [model.phase_peaks(ip, values)[0]]]) \
        if model.phases else np.empty(0)
    positions = positions[np.isfinite(positions)]
    positions = positions[(positions >= model.tt_min) & (positions <= model.tt_max)]
    if not positions.size:
        return []
    tt_min = float(np.min(positions))
    factor = np.asarray(model._roughness_factor(positions, values))
    depression = float(1.0 - np.min(factor))

    out: list[Diagnostic] = []
    if model.roughness == "pitschke":
        tau = values[f"{base}.tau"]
        sin_min = float(np.sin(np.radians(0.5 * tt_min)))
        if tau > sin_min:
            out.append(Diagnostic(
                level="warning", code="ROUGHNESS_OUTSIDE_REGIME",
                where=[f"{base}.tau"],
                message=(f"Pitschke roughness tau={tau:.4f} exceeds "
                         f"sin(theta) = {sin_min:.4f} at the lowest fitted "
                         f"angle ({tt_min:.2f}° 2θ): past that point the model "
                         f"amplifies rather than depresses intensity"),
                suggestion="restrict the fit to 2θ above "
                           f"{2 * np.degrees(np.arcsin(min(tau, 1.0))):.1f}°, or "
                           "switch to kind='suortti', which is bounded ≤ 1 "
                           "everywhere (Pitschke et al. 1993 Eq 18)",
            ))
        elif tau > 0.5 * sin_min:
            out.append(Diagnostic(
                level="info", code="ROUGHNESS_OUTSIDE_REGIME",
                where=[f"{base}.tau"],
                message=(f"Pitschke roughness is past its turnover at the low "
                         f"end of the fit (tau={tau:.4f} vs sin(theta)="
                         f"{sin_min:.4f} at {tt_min:.2f}° 2θ): the depression "
                         f"stops deepening there"),
                suggestion="the model is empirical rather than geometric in "
                           "this range (the paper says so); treat tau as a "
                           "fitting parameter, not a measured roughness",
            ))

    if depression < ROUGHNESS_MIN_DEPRESSION:
        out.append(Diagnostic(
            level="warning", code="ROUGHNESS_UNCONSTRAINED",
            where=[f"{base}.{n}" for n in ("a", "b", "c", "tau")
                   if f"{base}.{n}" in values],
            message=(f"the refined surface roughness depresses intensity by at "
                     f"most {depression:.2%} at any modelled reflection "
                     f"(lowest at {tt_min:.2f}° 2θ) — the data cannot see it"),
            suggestion="drop the roughness block, or extend the measurement to "
                       "lower 2θ where the depression has a lever arm; note "
                       "the Suortti model reaches the identity from both ends, "
                       "so a large b is as inert as a zero one",
        ))
    return out


def _restraint_where(row, structure: Structure) -> list[str]:
    if row.path is not None:
        return [row.path]
    if row.phase_index is None or row.atoms is None:
        return []
    phase = structure.phases[row.phase_index]
    return [f"{phase.name} {phase.atoms[j].label}" for j in row.atoms]


def _pawley_locate(pb, gi: int) -> tuple[int, int]:
    """Map a flat intensity index to (phase index, in-phase reflection index)."""
    for ip, (a, b) in enumerate(pb.phase_slices):
        if a <= gi < b:
            return ip, gi - a
    raise IndexError(gi)


def replay(tree: RefinementTree, node_id: str, data: PatternData) -> RefinementResult:
    """Recompute the curves and statistics of a recorded node.

    The model is compiled fresh at the node's own parameter values, so the
    statistics returned here can differ marginally from
    ``node.metrics.statistics``, which the optimiser measured on a model
    frozen at the values its stage *started* from.  See :class:`NodeMetrics`.

    Strictly evaluate-only: it never calls ``lebail_update``, which mutates
    the extracted intensities in place — inspecting a checkpoint must not
    change it.
    """
    node = tree[node_id]
    expected = tree.header.data_fingerprint
    if expected:
        actual = fingerprint(data.two_theta, data.intensity)
        if actual != expected:
            raise ValueError(
                f"pattern does not match this history: fingerprint {actual[:8]} "
                f"but the tree was recorded against {expected[:8]}")

    state = node.state
    structure = state.structure.model_copy(deep=True)
    instrument = state.instrument.model_copy(deep=True)
    table = ParameterTable(structure, instrument)
    table.set_vary(["*"], False)
    for path in state.free_paths:
        table.set_vary([path], True)

    model = compile_model(structure, instrument, data, mode=state.mode,
                          two_theta_limits=state.two_theta_limits,
                          free_paths=set(table.free_paths))
    if state.mode in ("lebail", "pawley"):
        _restore_lebail(state.reflections, model)

    result = _build_result(
        model, table, table.x0(), mode=state.mode,
        status=node.metrics.status or "converged", stage_results=[],
        diagnostics=list(node.diagnostics), structure=structure)
    result.node_id = node.id
    result.tree_id = tree.header.tree_id
    return result


def estimate_mu_r(structure: Structure, instrument: Instrument) -> float | None:
    """Starting µR for a packed capillary, from composition and geometry.

    Combines each phase's linear attenuation coefficient (McMaster tables, via
    :mod:`pxrdref.crystallography.attenuation`) into a volume-fraction-weighted
    bulk µ, scales it by ``Geometry.packing_fraction`` — voids do not absorb —
    and multiplies by ``Geometry.capillary_radius_mm``.

    Returns ``None`` rather than raising when µ is unavailable (a wavelength
    whose tabulation interval straddles an absorption edge, an element outside
    the compilation, an energy outside 2-120 keV) or when the geometry carries
    no capillary radius.  Use it to *populate* ``Geometry.mu_r``; a refinement
    will do the same thing itself at compile time if ``mu_r`` is left ``None``.

    µR is not refinable, deliberately — see :mod:`pxrdref.model.absorption`.
    """
    geom = instrument.geometry
    if geom.kind != "debye_scherrer" or geom.capillary_radius_mm is None:
        return None
    table = ParameterTable(structure, instrument)
    mu_r, _ = estimate_capillary_mu_r(
        structure, table.decode(table.x0()),
        instrument.source.primary_wavelength,
        geom.capillary_radius_mm, geom.packing_fraction)
    return mu_r


def refine(data: PatternData, structure: Structure, instrument: Instrument,
           *, mode: Mode = "rietveld", plan: RefinementPlan | str = "mccusker_default",
           two_theta_limits: tuple[float, float] | None = None,
           backend: str = "numpy",
           history: bool | str | Path | RefinementTree = False) -> RefinementResult:
    """One-shot functional API: ``refine(data, structure, instrument)``.

    History defaults to *off* here: this call discards the ``Refinement``, so
    an in-memory tree would be unreachable.  Pass a path to keep one.
    """
    ref = Refinement(structure, instrument, backend=backend, history=history)
    return ref.fit(data, mode=mode, plan=plan, two_theta_limits=two_theta_limits)
