# The refinement history

This page gives what a refinement's history records: the fields of a node, the actions that commit one, what a checkout restores, the queries a tree answers and the format of the `history.jsonl` log.

Every stage, model edit and parameter change commits a node to a directed graph of checkpoints.
The split is git's.
`Refinement` is the working tree, holding the values the next fit moves.
`Refinement.history` is a `RefinementTree`, holding immutable nodes and named refs that point into them.
[How to branch a refinement](../guides/branch.md) goes back to a node, forks from it and compares the branches.
A project keeps its tree in `history.jsonl` ([About the project](../concepts/project.md)), and `Project.history` returns it.

## The history setting

`history` is an argument of the `Refinement` constructor, because one tree spans many fits.

| `history=` | What you get |
|---|---|
| `True` (the default) | nodes in memory |
| a path, as `str` or `Path` | the same nodes, each appended to that file as it is committed |
| `False` | no tree: no snapshots, no per-stage statistics, nothing written, and `RefinementResult.node_id` is `None` |
| a `RefinementTree` | commits into that tree, on top of its head, so two refinements can share one history |

`refine` takes the same argument with `False` as its default.
It discards the `Refinement`, so an in-memory tree would be unreachable.
Pass it a path to keep the history.

A tree is pinned to its pattern by a fingerprint, so with `True` or a path it is created on the first `Refinement.fit` or `Refinement.run_stage`.
Its root node is the working state at that moment.
Until then `Refinement.history` is `None`.
A recording verb such as `Refinement.set_vary` or `Refinement.edit` changes the working state and commits nothing, so its change arrives in the root.
`Refinement.checkout`, `Refinement.branch`, `Refinement.merge` and `Refinement.cherry_pick` raise `RuntimeError` until the tree exists.

A path that already holds a log gains a second tree after the first, with its own header and node ids that start again at `n0000`.
`RefinementTree.load` reads such a file as one tree that holds each id twice.
To continue a saved log, load it and open a refinement on it with `Refinement.from_node`.
A `RefinementTree` passed to the constructor takes new nodes on top of its head, with the models you passed as the working state.

## Nodes

`HistoryNode` is one immutable checkpoint.

| Field | Type | Holds |
|---|---|---|
| `HistoryNode.id` | `str` | `n0000`, `n0001` and onwards, in commit order |
| `HistoryNode.parents` | `list[str]` | the ids this node was made from: none for the root, two for a merge |
| `HistoryNode.action` | `NodeAction` | the operation that produced it |
| `HistoryNode.state` | `RefinementState` | everything needed to restore the refinement |
| `HistoryNode.metrics` | `NodeMetrics` | the agreement the solver reached, empty where no fit ran |
| `HistoryNode.diagnostics` | `list[Diagnostic]` | what the stage reported |
| `HistoryNode.label` | `str` | a short name from `Refinement.edit`, `Refinement.merge` or `RefinementTree.annotate` |
| `HistoryNode.created_utc` | `str` | when it was committed, as `2026-10-19T23:58:38Z` |
| `HistoryNode.scores` | `dict[str, float]` | numbers attached to the node afterwards |
| `HistoryNode.notes` | `dict[str, str]` | strings attached to the node afterwards |
| `HistoryNode.schema_version` | `str` or `None` | the data-contract version of the release that committed it; `None` on a node written before the field |

`HistoryNode.parent` returns the first parent, or `None` at the root.
A linear history follows first parents.
`HistoryNode.rwp` returns the Rwp from the node's metrics, or `None` on a node that ran no fit.

A node stores state and no curves.
The calculated pattern and the agreement indices follow from the state and the pattern, so `replay` recomputes them on demand.
On the 11-BM NAC pattern fitted over 2–24°, 22 003 of its 59 498 points, a node is 10 to 15 kB, and the calculated curve alone would add about 430 kB.

## Action kinds

`NodeAction.kind` names the operation, from a closed vocabulary of nine kinds.

| `kind` | Committed by |
|---|---|
| `root` | the first `Refinement.fit` or `Refinement.run_stage`, and `Project.create` |
| `stage` | `Refinement.run_stage`, `Refinement.cherry_pick` and each stage of a plan |
| `set_vary` | `Refinement.set_vary` |
| `set_value` | `Refinement.set_values` |
| `set_tie` | `Refinement.tie`, `Refinement.tie_equal` and `Refinement.untie` |
| `set_variable` | `Refinement.add_variable` and `Refinement.remove_variable` |
| `set_hold` | `Refinement.hold` and `Refinement.unhold` |
| `edit_model` | `Refinement.edit`, and the verbs that edit the model through it: `Refinement.fix_special_positions`, `Refinement.hold_floating_origin`, and `Refinement.unhold` on a floating-origin hold |
| `merge` | `Refinement.merge` |

Every kind is committed by a verb you can call.
A Le Bail intensity refresh has no kind of its own.
A Le Bail stage refreshes the intensities inside itself, and the refreshed values are part of that `stage` node's state.

## Action fields

The other fields of `NodeAction` are the arguments of the operation, and the kind decides which are set.

| Field | Type | Set on | Holds |
|---|---|---|---|
| `NodeAction.name` | `str` | `stage`, `edit_model`, `merge` | the stage's name; the edit's label, or `model edited`; the merge's label, or `merge n0005 (prefer theirs)` |
| `NodeAction.turn_on` | `list[str]` | `stage`, `set_vary` | the globs the stage freed; the paths `set_vary` freed |
| `NodeAction.turn_off` | `list[str]` | `set_vary` | the paths `set_vary` fixed |
| `NodeAction.values` | `dict[str, float]` | `set_value` | the values `set_values` was called with |
| `NodeAction.ties` | `dict[str, TieSpec]` | `set_tie` | the ties declared, by dependent path |
| `NodeAction.untied` | `list[str]` | `set_tie` | the paths untied |
| `NodeAction.variables` | `dict[str, Parameter]` | `set_variable` | the variables declared, by bare name (`B`, without `vars.`) |
| `NodeAction.removed_variables` | `list[str]` | `set_variable` | the names removed |
| `NodeAction.held` | `list[str]` | `set_hold` | the paths held |
| `NodeAction.unheld` | `list[str]` | `set_hold` | the paths released |

Each defaults to empty.
`set_vary`, `hold` and `unhold` record the paths their globs matched rather than the globs you typed.
A glob matched one model, and replayed against a later one it could match a different set.
A stage records its globs, because those are the stage's own arguments.

A stage node also records its solver settings, so that `Refinement.cherry_pick` can rebuild the `Stage` and run it somewhere else.
These are the fields of `Stage`, and [stage settings](settings.md#stage-settings) describes each in full.

| Field | Default | Holds |
|---|---|---|
| `NodeAction.max_iter` | `100` | the iteration budget |
| `NodeAction.lebail_cycles` | `3` | the intensity-partitioning cycles before each solve in `lebail` mode |
| `NodeAction.seed` | `0.0` | the starting value for a freed parameter sitting on a lower bound of 0 |
| `NodeAction.strain_seed` | `0.0` | the microstrain in ppm that starts an all-zero Stephens block |
| `NodeAction.restraint_weight_scale` | `1.0` | the weight on the geometric restraints |
| `NodeAction.ftol` | `None` | the tolerance the stage stopped at; `None` is the solver's 1e-9 |
| `NodeAction.window_slack_deg` | `None` | the extra 2θ on each side of a reflection's window, in degrees |

`NodeAction.ftol` records the tolerance the stage ran at, which can differ from the one it declared.
A stage that takes the plan's schedule (`RefinementPlan.intermediate_ftol`) declares nothing and stops at 1e-6.
A node holding `None` there would replay at the solver's tolerance, which the original run did not use.

A stage node also records the two plan settings its stage ran under, so a cherry-pick replays them too.

| Field | Default | Holds |
|---|---|---|
| `NodeAction.phase_support_sigma` | `3.0` | the absent-phase hold's threshold in esds; `None` means the significance hold was off (a phase with no line in range is held either way) |
| `NodeAction.correlation_guard` | `0.98` | the \|ρ\| above which the stage reported a correlated pair |
| `NodeAction.window_area_tol` | `None` | the fraction of each peak's area the stage's windows dropped; a plan's closing stage records `closing_window_tol`, a stage run by hand the fraction it ran at, and `None` a declared stage's 2 % |

A node written before 1.10 has neither field and reads as the defaults, which are what it ran at unless its plan set them.
`api_call()` adds either setting to the stage's line only where it differs from the default.

## Actions as calls

`NodeAction.api_call` renders an action as the public call that repeats it, so a log reads as a session script:

```python
import rietx as rx

action = rx.NodeAction(kind="stage", name="cell",
                       turn_on=["phases.*.cell.*"], max_iter=200)
assert action.api_call() == (
    "ref.run_stage(data, rx.Stage('cell', ['phases.*.cell.*'], max_iter=200), "
    "window_area_tol=0.02)")
```

A node that records no window fraction is a declared stage, which dropped 2 %
of each peak. `run_stage` defaults to the closing stage's fraction, so the line
names the 2 % to repeat the stage that ran.

The line is computed from the fields, so it cannot disagree with them.
A stage's line always carries `max_iter`.
It carries `seed`, `strain_seed`, `restraint_weight_scale`, `ftol` and `window_slack_deg` where they differ from the `Stage` default, and it never carries `lebail_cycles`.
Two kinds render a line that does not run.
An `edit_model` node renders a comment naming the edit, because the models it installed are in its state and in no argument.
A `merge` renders `ref.merge(...)` followed by its name as a comment.

## Restored state

`RefinementState` is what `Refinement.checkout` puts back.
`Refinement.snapshot` returns the working state in the same form.

| Field | Holds |
|---|---|
| `RefinementState.structure` | the structure |
| `RefinementState.instrument` | the instrument |
| `RefinementState.mode` | `rietveld`, `lebail` or `pawley` |
| `RefinementState.free_paths` | the dot-paths free at this node |
| `RefinementState.free_declared` | whether `free_paths` is a declaration, an empty list included |
| `RefinementState.two_theta_limits` | the fitted range in degrees 2θ, or `None` for the whole pattern |
| `RefinementState.ties` | the ties you declared, by dependent path |
| `RefinementState.variables` | the named variables, by bare name |
| `RefinementState.holds` | the paths held against every plan |
| `RefinementState.reflections` | the intensities of each Le Bail or Pawley phase |

The models do not hold the last six fields, so the node carries them.
A vary flag survives in the models, but the free set a plan's globs produced does not.
A symmetry tie is derived again from the space group on every table build.
A tie you declared follows from nothing in the models.
A [named variable](../guides/tie.md#tie-to-a-quantity-of-your-own) has no field in the models at all, so the node is its only record.
A hold stops a plan freeing a path, and a plan replaces the vary flags, so no flag can carry a hold.
A checkout without these fields would restore a model whose constraints and holds had silently gone, and the parameter count with them.

`RefinementState.free_declared` makes an empty `free_paths` readable.
Until something declares a free set, the models' own `vary` flags are the free set.
`Refinement.set_vary`, a tie or hold edit and every stage declare one, and from then on the list is the free set, empty or not.
A `set_value`, `edit_model`, `set_variable` or `merge` node copies the free set without declaring one, so the kind of a node cannot answer the question.
A non-empty list always counts as declared, and a node written before the field reads as not declared.

On a stage node, `free_paths` includes any path the stage held because the data could not see its phase.
That hold is one stage's reading of the data.
A checkout starts without it, and the next stage decides again.

A checkout restores every field in the table.
It also drops the last fit's result (`Refinement.result_`), moves this refinement's position to the node and moves the tree's `head` ref there.
The wavelengths that the `WAVELENGTH_CALIBRATION` check measures a refined λ against stay the ones the `Refinement` was built with.

### Extracted intensities

`RefinementState.reflections` holds one `ReflectionState` for each phase whose intensities are not computed from the structure.

| Field | Holds |
|---|---|
| `ReflectionState.phase_index` | which phase these belong to |
| `ReflectionState.hkl` | the reflection indices, one triple per row |
| `ReflectionState.intensity` | the intensity of each row |
| `ReflectionState.satellite_order` | m in Q = H + m·k for each row, with k the phase's propagation vector; `None` for a phase with no propagation vector |
| `ReflectionState.kind` | `lebail_extracted` or `pawley_refined` |
| `ReflectionState.stderr` | the esd of each intensity, which Pawley has and Le Bail does not |
| `ReflectionState.varied` | whether the intensities were free parameters |

Le Bail intensities start flat and are refined by a fixed-point loop, so they depend on the path the fit took.
The structure, the instrument and the pattern cannot reproduce them, so a Le Bail checkpoint can be restored only because the node stores them.
In the walkthrough of [A first fit in Python](../start/first-fit.md#worked-example-a-synchrotron-pattern-with-an-impurity), the Le Bail node carries 129 extracted intensities and the Rietveld nodes carry none.

## Cached metrics

`NodeMetrics` holds the numbers `RefinementTree.best` and `RefinementTree.compare` read, so neither recomputes anything.

| Field | Holds |
|---|---|
| `NodeMetrics.statistics` | the `Statistics` block, or `None` on a node that ran no fit |
| `NodeMetrics.status` | `converged`, `max_iter` or `diverged`, copied from the stage's `StageResult`; `None` on a node that ran no fit |
| `NodeMetrics.n_iterations` | the residual evaluations the solve made, counted as `StageResult.n_iterations` counts them |
| `NodeMetrics.cost_initial` | the cost the stage started from |
| `NodeMetrics.cost_final` | the cost it reached |
| `NodeMetrics.stderr` | esds by dot-path, in physical units |
| `NodeMetrics.held_scale_phases` | the phases whose own scale the stage held, which `replay` reads to quote them no fraction |
| `NodeMetrics.window_loss` | the stage's `StageResult.window_loss`, the share of the Bragg intensity its windows dropped at its answer; `None` on any other node and on a replay |

The cost is half the sum of squared weighted residuals, ½‖r‖², restraint and penalty rows included.
On the walkthrough's last node it fell from 144 805 to 137 594 in 10 evaluations.

These metrics are as-optimised.
They are the agreement the least squares reached on the model it minimised.
That model's reflection list, peak windows and quadrature node counts were fixed at the values the stage started from.
`replay` compiles the model afresh at the node's values, so its statistics can differ slightly.
A large difference means the stage moved far enough for its fixed reflection list and windows to go stale, and splitting the stage removes it.

The `RefinementResult` a fit returns is measured the second way, by one more compile at the values it returns.
So a result reproduces from its own parameters.
The node it produced keeps the as-optimised figure.
When the two χ² differ by more than 1 %, the result carries [`FROZEN_COMPILE_STALE`](diagnostics-refinement.md#frozen_compile_stale).

A node that ran no fit has empty metrics: `root`, `set_vary`, `set_value`, `set_tie`, `set_variable`, `set_hold`, `edit_model` and `merge`.
A stage whose globs matched nothing is not one of them.
It still runs, refines the free set it inherited, and converges.

## The tree

A `RefinementTree` holds the nodes, their commit order and the named refs.

| Attribute | Holds |
|---|---|
| `RefinementTree.nodes` | node id → `HistoryNode` |
| `RefinementTree.order` | the node ids in commit order |
| `RefinementTree.refs` | ref name → node id, `head` included |
| `RefinementTree.head` | the id `head` points at, or `None` in an empty tree |
| `RefinementTree.header` | the `TreeHeader` |
| `RefinementTree.path` | the log the tree appends to, or `None` for a tree held only in memory |

`tree[key]` takes a node id or a ref name and returns the node.
`RefinementTree.resolve` returns the id a key points at.
It raises `KeyError` listing the known refs when the key points at nothing.
`len(tree)` counts the nodes, `key in tree` accepts either kind of key, and `print(tree)` prints `RefinementTree.summary`.

`RefinementTree.for_data` builds an empty tree for a pattern.
`RefinementTree.add` commits a node into it and moves `head` to the new node.
`Refinement` and `Project` call both for you.
Here they build a tree with no fitting in it:

```python
import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))],
)])
data = rx.PatternData(two_theta=[10.0, 10.02, 10.04], intensity=[120.0, 480.0, 90.0])

tree = rx.RefinementTree.for_data(data)
ref = rx.Refinement(lab6, rx.Instrument.debye_scherrer(wavelength=0.4139),
                    history=tree)
tree.add(parents=[], action=rx.NodeAction(kind="root"), state=ref.snapshot())
ref.checkout("head")

ref.set_vary(["phases.*.cell.*"])
ref.set_values({"phases.0.cell.a": 4.157})

assert [tree[n].action.kind for n in tree.order] == ["root", "set_vary", "set_value"]
assert tree.head == "n0002"
assert tree["n0001"].action.turn_on == ["phases.0.cell.a"]   # the path, not the glob
assert tree["head"].action.api_call() == "ref.set_values({'phases.0.cell.a': 4.157})"
assert tree.diff("n0000", "head") == {
    "phases.0.cell.a": (4.15689, 4.157),
    "phases.0.cell.b": (4.15689, 4.157),   # cubic: b and c follow a
    "phases.0.cell.c": (4.15689, 4.157),
}
```

Every commit and every checkout moves `head`, whichever `Refinement` made it.
Each `Refinement` keeps its own position, so after `Refinement.branch` the two objects commit on separate lines.
Read `RefinementTree.head` as the node a reopened session resumes at.

### Walking the graph

| Call | Returns |
|---|---|
| `RefinementTree.root` | the first node with no parents, or `None` in an empty tree |
| `RefinementTree.children` | the nodes that name a given node among their parents |
| `RefinementTree.leaves` | the nodes no other node names as a parent, one per open branch |
| `RefinementTree.lineage` | the nodes from the root to a given node, following first parents |
| `RefinementTree.ancestors` | the set of ids of a given node and every node it descends from, following all parents |
| `RefinementTree.common_ancestor` | the id of the latest node two given nodes both descend from, or `None` |

`Refinement.merge` uses `RefinementTree.common_ancestor` as its merge base.
On its own it answers where two strategies diverged.

### Comparing nodes

`RefinementTree.best` returns the node with the lowest Rwp.
It takes the name of any other `Statistics` field, such as `"gof"` or `"chi2"`, and `minimize=False` takes the highest instead.
It skips nodes without statistics, and raises `ValueError` on a tree where no node has any.

`RefinementTree.compare` returns one row per node you name, as a dict.
The keys are `id`, `label`, `action` (the kind and name, as `stage:biso`), `status`, `n_free`, `rwp`, `gof` and `chi2`.
A node that ran no fit has `None` under the last five.

`RefinementTree.diff` returns the parameter values that differ between two nodes, as `path: (first, second)` pairs.
It reads every entry of each node's parameter table, named variables included as `vars.` followed by the name.
A path that exists on one side only, such as a phase added between the two nodes, has `None` on the other.
Two values count as equal within a relative 1e-12 (the `rtol` argument).
In the walkthrough, 44 paths differ between the Le Bail node and the last one, and 22 of them belong to the CaF₂ phase the model edit added.

### Printing a tree

`RefinementTree.summary` prints one line per node, with its id, its `kind:name` and its Rwp.
A `*` marks the head, and tags follow in brackets.
A straight run of nodes stays in one column, and each branch of a fork is indented one level.
The first line gives the tree's id, its node count and the pattern's file name.
[How to branch a refinement](../guides/branch.md#roll-back-and-carry-on) shows a forked tree printed this way.

`RefinementTree.to_mermaid` prints the same tree as a mermaid `graph TD`, one box per node and one arrow per parent.
Paste it into any markdown that renders mermaid.

## Tags and annotations

`RefinementTree.tag` names a node, and every call that takes a node id accepts the name instead.
The name `head` is reserved, and tagging with it raises `ValueError`.
`RefinementTree.annotate` writes a label, scores, notes or refs onto a node after the fact.
`RefinementTree.set_head` moves `head` without touching any refinement's working state.
It is the low-level half of a checkout.

Each of the three is recorded as an `Annotation` and applied on top of the node.

| Field | Holds |
|---|---|
| `Annotation.node_id` | the node it applies to |
| `Annotation.label` | a new label, or `None` to leave the label alone |
| `Annotation.refs` | ref names, each mapped to the node id it points at |
| `Annotation.scores` | numbers merged into the node's `scores` |
| `Annotation.notes` | strings merged into the node's `notes` |

Scores and notes survive a save and a reload.
Nothing in the package writes scores, so they are free for your own bookkeeping.
A search over strategies can score each leaf as it commits, and sort the leaves afterwards without a table of node ids anywhere else.

The package writes notes in two places.
A Le Bail fit with `RefinementPlan.lebail_passes` above 1 marks every node a pass created with `lebail_pass`, and with `lebail_kept` or `lebail_discarded`.
A series marks each pattern's root with `series_position` and `series_label`.
It adds `series_warm_start_tree` and `series_warm_start_node`, naming where that pattern's starting values came from.

`RefinementResult.node_id` is the node a fit or a stage committed, and `RefinementResult.tree_id` is the id of its tree.
Both are `None` when the history is off.

## Checkout, branch and merge

[How to branch a refinement](../guides/branch.md) shows these verbs at work.

| Call | Returns | Does |
|---|---|---|
| `Refinement.checkout` | the same `Refinement` | restores a node's state as the working state |
| `Refinement.branch` | a new `Refinement` | opens a second working state over the same tree |
| `Refinement.from_node` | a new `Refinement` | opens a refinement at a node of a tree you hold |
| `Refinement.cherry_pick` | a `RefinementResult` | runs a `stage` node's stage again from the current state |
| `Refinement.merge` | the merge node's id | combines another node's parameter values with the current state |

`Refinement.checkout` takes a node id or a ref name.
The node is untouched, and the next stage commits on top of it, which forks the graph.

`Refinement.branch` takes a node to start from, or starts at this object's own position when given none.
The new object carries the same ties, named variables, holds, free set, mode, fitted range, backend and solver.

`Refinement.from_node` takes a tree and a node, with `backend=` and `solver=` as the constructor takes them.
It is how a session resumes from a log that `RefinementTree.load` read.

`Refinement.cherry_pick` takes a node and a pattern.
It rebuilds the `Stage` from the node's action and runs it with `Refinement.run_stage`, in the current mode and fitted range.
The stage starts from the current values, so a strategy can be reused on another branch.
Only a `stage` node can be cherry-picked, and any other kind raises `ValueError` naming the kind it found.

`Refinement.merge` takes another node, `prefer="theirs"` or `"ours"`, and an optional `label`.
It merges parameter values one dot-path at a time against the two nodes' common ancestor:

- a path changed on one side takes that side's value;
- a path changed on both takes the side `prefer` names, `"theirs"` being the other node and `"ours"` the current head;
- a path missing from either side or from the ancestor takes the preferred side's value.

The model's composition comes whole from the preferred side: which phases exist, which background, the free set and the mode.
The merge node records both parents and has no metrics.
`Refinement.merge` raises `RuntimeError` when this refinement has committed nothing, and `ValueError` when the two nodes share no ancestor or `prefer` is neither word.

Only values merge, so a merge across a model edit can drop a phase without raising.
In the walkthrough the CaF₂ impurity arrives in a model edit, and merging the Le Bail node into the last one with `prefer="theirs"` returns a one-phase model.
Read `Refinement.structure` back after any merge that crosses a model edit.

## Replay

`replay` recomputes a node's curves and statistics from its state, and returns them as a `RefinementResult`:

<!-- api-doc: no-exec — it needs a tree and the pattern it was fitted against -->
```python
result = rx.replay(ref.history, "lebail", data)
print(result.statistics.rwp, result.node_id, result.tree_id)
```

It runs no least squares and no Le Bail update, because inspecting a checkpoint must not change it.
It commits no node.
The result's `node_id` and `tree_id` name the node replayed.
A node that ran no fit replays with status `converged`.

The model is compiled afresh at the node's own values, so the statistics can differ from the node's as-optimised `NodeMetrics.statistics`.
On the walkthrough's last node the replayed Rwp is 0.0933034 against the node's 0.0933036, a difference of 2.4e-7.
The `RefinementResult` that fit returned is the replayed figure, 0.0933034.

`replay` refuses a pattern other than the one the tree was recorded against, and names both fingerprints:

```text
pattern does not match this history: fingerprint d305428e but the tree was recorded against 5544a638
```

It rebuilds the ties the node recorded.
A tie whose source a later model edit made structurally fixed is dropped with a `UserWarning` naming it, as a checkout drops it.

## Tree identity

`TreeHeader` says what a tree is a history of.
`RefinementTree.header` is that record on a tree you hold, and it is the first line of a log.

| Field | Holds |
|---|---|
| `TreeHeader.tree_id` | `t` followed by the first 8 hex digits of the fingerprint |
| `TreeHeader.data_fingerprint` | a sha256 over the float64 bytes of the pattern's abscissa as measured (2θ, or flight time) and its intensities, first 32 hex digits |
| `TreeHeader.data_source` | the file the pattern was read from, where the reader recorded one |
| `TreeHeader.n_points` | the number of points in the whole pattern |
| `TreeHeader.plan` | the plan of the first fit, as a `PlanSpec`, or `None` when the first call was `Refinement.run_stage` |
| `TreeHeader.package_version` | the rietx version that created the tree |
| `TreeHeader.schema_version` | the data-contract version the tree was created under |
| `TreeHeader.created_utc` | when the tree was created |

The tree id comes from the pattern alone, so every tree over one pattern has the same id.
Every tree in the walkthrough is `t5544a638`.

`TreeHeader.data_fingerprint` is a digest of the parsed arrays rather than of the file's bytes.
It answers the question a replay needs answered: are these the numbers the nodes were fitted against.
A project keeps a digest of the file's bytes beside it, and [About the project](../concepts/project.md#the-pattern-and-how-it-was-read) says what a disagreement between the two means.

`TreeHeader.plan` is the plan the tree was created with, and later nodes may have run others.
In the walkthrough it holds the five stages of `profile_only`, because the first call was a Le Bail fit and that is the plan Le Bail mode runs by default.
What each node ran is on that node's own `NodeAction`.
`TreeHeader.package_version` is empty on a tree built by `RefinementTree.for_data` without one.

## The history log

A log such as a project's `history.jsonl` holds one JSON object per line, and each line is a `HistoryRecord`.

| Field | Holds |
|---|---|
| `HistoryRecord.record` | `"header"`, `"node"` or `"annotation"`, the tag that says which field below the line sets |
| `HistoryRecord.header` | a `TreeHeader`, on the first line |
| `HistoryRecord.node` | a `HistoryNode`, written when it is committed |
| `HistoryRecord.annotation` | an `Annotation`, written by a tag, an annotation or a move of `head` |

The two fields the tag does not name are `null` on that line.
A reader branches on the tag, so a new kind of line cannot change how the earlier ones read.

The package only appends to a log.
Every commit, tag, annotation and checkout adds one line, and a line once written is never rewritten.
A tag on a node written an hour ago adds an annotation line, and the node's own line stays as it was.
`Project.open` adds a line as well, moving `head` to the node the session resumes at.

`RefinementTree.save` writes a whole tree to a file and replaces what the file held.
Nothing in the package calls it.
It writes what `RefinementTree.records` returns: the header, every node in commit order with its annotations applied, and one annotation line carrying every ref.
Later commits append to the saved file.

```python
import json
import tempfile
from pathlib import Path

import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))],
)])
data = rx.PatternData(two_theta=[10.0, 10.02, 10.04], intensity=[120.0, 480.0, 90.0])

with tempfile.TemporaryDirectory() as tmp:
    log = Path(tmp) / "fit.jsonl"
    tree = rx.RefinementTree.for_data(data, path=log)
    ref = rx.Refinement(lab6, rx.Instrument.debye_scherrer(wavelength=0.4139),
                        history=tree)
    tree.add(parents=[], action=rx.NodeAction(kind="root"), state=ref.snapshot())
    ref.checkout("head")
    ref.set_vary(["phases.*.cell.*"])
    tree.tag("head", "freed")

    def tags():
        return [json.loads(line)["record"] for line in log.read_text().splitlines()]

    # appended: the checkout and the tag are lines of their own
    assert tags() == ["header", "node", "annotation", "node", "annotation"]
    tree.save(log)
    assert tags() == ["header", "node", "node", "annotation"]
    assert rx.RefinementTree.load(log).refs == {"head": "n0001", "freed": "n0001"}
```

`RefinementTree.load` applies the lines in file order, as the tree applied them when each was written.
A node line moves `head` to that node, and an annotation line overlays its refs on whatever `head` was then.
So a reloaded tree resumes at the last commit or the last checkout, whichever came later.
A log written by a plain fit, with no annotation line at all, resumes at its last node.
Blank lines are skipped.
A file with no header line raises `ValueError` saying it is not a history log.
A line that does not parse raises `ValueError` naming the file and the line number.

A log has one writer.
A node line is several kB, longer than the operating system appends in one piece, so two processes appending to one file can interleave their lines.
Each append takes a file lock where the platform offers one, and nothing depends on it.
A parallel search gives each worker its own file and reads them all afterwards.

### Repairs on read

`RefinementTree.load` makes two repairs to a log an earlier release wrote.

The first is a rename.
Release 1.2 renamed the instrument field `background_peaks` to `extra_components`, and every line is rewritten from the old name to the new one before it is parsed.
A stage glob under the old name would otherwise load cleanly and free nothing.
The rename raises no diagnostic.

The second restores declared ranges.
Each field holding a `Parameter` declares a range and a unit, and a `Parameter` you supply inherits the parts you left out ([Patterns and structures](data.md#parameter)).
A release before a class inherited wrote such a parameter with the bounds it then carried, (−inf, inf) and no unit.
A log like that would reopen unbounded, because every key is present and nothing is inherited from a key that is there.
`RefinementTree.load` restores the declared range in every node that stored one, where the node was written before that class inherited.
Each node carries the schema version it was written under (`HistoryNode.schema_version`), and a node written before that field is read at its log header's version.
Each restored parameter is reported once, as a [`DECLARED_RANGE_RESTORED`](diagnostics-refinement.md#declared_range_restored) diagnostic naming its dot-path, the atom where there is one, and both ranges.
Pass `diagnostics=[]` to collect them.
`Project.open` passes a list and keeps it as `Project.history_diagnostics`.

No value moves.
Where any node's value lies outside the declared range, the parameter is left as stored in every node.
It is reported as [`DECLARED_RANGE_NOT_RESTORED`](diagnostics-refinement.md#declared_range_not_restored), naming the node and the value, and it still refines unbounded.
The declared range does not hold for every instrument.
A coarse neutron line's Caglioti `u` sits well outside the X-ray one.
A range that is merely wider than the declared one is a choice, and is left alone.
So is an unbounded one written after the class inherited.
