# The refinement history

A refinement is a walk through parameter space, and the package records the
walk. Every stage, every model edit and every parameter change appends a node
to a directed graph of checkpoints. Any state the refinement passed through can
then be restored, compared against another, or continued down a second branch.

The split is git's. `Refinement` is the working tree: mutable, holding the
values a fit is about to move. `Refinement.history` is the object store:
immutable nodes, plus named refs that point into them. This chapter is that
store as an object. [](files.md) is the file it is written to.

## Switching the history on and off

`history` is a constructor argument rather than a `fit` argument, because one
tree spans many fits. [](refining.md) has the full table of which setting goes
where.

| `history=` | What you get |
|---|---|
| `True` (the default) | nodes in memory |
| a path | the same nodes, appended to that file as JSONL |
| `False` | the light path: no snapshots, no per-stage statistics, no serialisation |
| a `RefinementTree` | commits into an existing tree, which is how two refinements share one history |

A tree is pinned to its pattern by a fingerprint, so it cannot be built before a
pattern has been seen. It is created on the first `Refinement.fit` or
`Refinement.run_stage`. A `Refinement.set_vary` call before that point changes
the working state and records nothing.

## What a node holds

`HistoryNode` is one immutable checkpoint.

| Field | Type | Holds |
|---|---|---|
| `HistoryNode.id` | str | `n0000`, `n0001`, … in commit order |
| `HistoryNode.parents` | list[str] | the ids this node was made from |
| `HistoryNode.action` | `NodeAction` | the operation that produced it |
| `HistoryNode.state` | `RefinementState` | everything needed to reconstruct the refinement |
| `HistoryNode.metrics` | `NodeMetrics` | the agreement the optimiser reached |
| `HistoryNode.diagnostics` | list[`Diagnostic`] | what the stage reported |
| `HistoryNode.label` | str | a short name, set by `RefinementTree.annotate` |
| `HistoryNode.created_utc` | str | when it was committed |
| `HistoryNode.scores` | dict[str, float] | numbers a caller attaches to the node |
| `HistoryNode.notes` | dict[str, str] | strings a caller attaches to the node |

`HistoryNode.parents` is a list because a merge has two. `HistoryNode.parent`
returns the first of them, which is the line a linear history follows, and
`None` at the root.

`HistoryNode.rwp` reads the node's Rwp out of its metrics, or returns `None`
where the node carries no statistics. A model edit and a merge are both such
nodes: neither ran a least squares.

A node stores state and not curves. The calculated pattern and the agreement
indices are a function of the state and the pattern, so they are recomputed on
demand instead of stored. On the 11-BM acceptance case a state-only node is
about 10 kB against about 1.24 MB for one carrying the fitted curves, and that
ratio is what makes wide branching affordable.

### The action that produced it

`NodeAction.kind` names the operation. It is a closed vocabulary.

| `kind` | Committed by |
|---|---|
| `root` | the initial model, before anything ran |
| `stage` | `Refinement.run_stage`, and each stage of a plan |
| `set_vary` | `Refinement.set_vary` |
| `set_value` | `Refinement.set_values` |
| `set_tie` | `Refinement.tie`, `Refinement.tie_equal` and `Refinement.untie` |
| `set_variable` | `Refinement.add_variable` and `Refinement.remove_variable` |
| `set_hold` | `Refinement.hold` and `Refinement.unhold` |
| `edit_model` | `Refinement.edit` |
| `merge` | `Refinement.merge` |

The table is the whole vocabulary, and the second column is why: every member is
committed by a verb you can call. A Le Bail intensity refresh is not among them,
because it is not a node. A Le Bail stage refreshes the intensities inside
itself, and the refreshed values are part of that `stage` node's state.

The other fields are the arguments of the operation, and which of them are set
depends on the kind. `NodeAction.name` is the stage's name, or the label given
to an edit or a merge. `NodeAction.turn_on` and `NodeAction.turn_off` are the
globs a stage freed or a `set_vary` changed. `NodeAction.values` is what
`set_values` was called with. `NodeAction.ties` and `NodeAction.untied` are what
a tie edit declared and removed, and `NodeAction.variables` and
`NodeAction.removed_variables` are the same pair for a variable edit: the
declaration by name, and the names deleted. `NodeAction.held` and
`NodeAction.unheld` are that pair for a hold ({ref}`holding-a-parameter`), as
resolved dot-paths rather than the globs you typed. The glob matched a model,
and replaying it against a later one could hold a different set.

A stage records its solver settings as well: `NodeAction.max_iter`,
`NodeAction.lebail_cycles`, `NodeAction.seed`, `NodeAction.strain_seed`,
`NodeAction.restraint_weight_scale`, `NodeAction.ftol` and
`NodeAction.window_slack_deg`. They are there because
`Refinement.cherry_pick` rebuilds a `Stage` from this action and runs it
somewhere else. A setting missing here would be a stage that replays as a
different stage from the one recorded.

`NodeAction.ftol` records the tolerance the stage was solved at, which is not
always the one it declared. A stage taking the plan's schedule
(`RefinementPlan.intermediate_ftol`, see [](refining.md)) declares nothing and
still stops at `1e-6`, so a node holding `None` would replay the one thing the
original run did not do.

`NodeAction.api_call` renders the node as the public call that would repeat it,
so a log reads as a session script:

```python
import rietx as rx

action = rx.NodeAction(kind="stage", name="cell",
                       turn_on=["phases.*.cell.*"], max_iter=200)
assert action.api_call() == (
    "ref.run_stage(data, rx.Stage('cell', ['phases.*.cell.*'], max_iter=200))")
```

It is computed rather than stored, so it cannot disagree with the fields beside
it. Each extra argument is printed only where it differs from the `Stage`
default, which keeps a plain stage's line short.

### The state it restores

`RefinementState` is what a checkout puts back.

| Field | Holds |
|---|---|
| `RefinementState.structure` | the structure, as of this node |
| `RefinementState.instrument` | the instrument, as of this node |
| `RefinementState.mode` | the intensity mode the node was recorded in |
| `RefinementState.free_paths` | the dot-paths that were free |
| `RefinementState.two_theta_limits` | the fitted range |
| `RefinementState.ties` | the user constraints in force |
| `RefinementState.variables` | the named variables declared, by name |
| `RefinementState.holds` | the paths held against a plan's globs |
| `RefinementState.reflections` | extracted or refined intensities, per phase |

The last five are carried because the models do not hold them. A vary flag
survives in the models, and the free set after globbing does not. A symmetry tie
is rederived from the space group on every table build, while a tie you declared
is not derivable from anything. A node without them would restore a model with
the constraints silently gone, and the parameter count with them.

`RefinementState.variables` is that argument one step further along. A tie is
not a property of the models, and a {ref}`named variable <named-variables>` is
not in them at all, since there is no field for it to be written to. The node is
its only record, and a checkout that dropped it would restore ties naming a
parameter that no longer exists.

`RefinementState.holds` is the same argument again, for a different reason.
A hold is a refusal rather than a value, so nothing in the models could encode
it: the one field that comes close is `vary`, and a plan replaces the vary
flags rather than continuing them. A checkout that dropped the register would
hand back a state whose pin had quietly expired, which is worse than never
having declared it.

`RefinementState.reflections` is a list of `ReflectionState`, one per phase whose
intensities are not computed from the structure.

| Field | Holds |
|---|---|
| `ReflectionState.phase_index` | which phase these belong to |
| `ReflectionState.hkl` | the reflection indices, one triple per row |
| `ReflectionState.intensity` | the intensity for each |
| `ReflectionState.satellite_order` | the m of Q = H + m·k per row, or null for a phase with no propagation vector |
| `ReflectionState.kind` | `lebail_extracted` or `pawley_refined` |
| `ReflectionState.stderr` | esds, which Pawley has and Le Bail does not |
| `ReflectionState.varied` | whether these were free parameters |

Le Bail intensities are seeded flat and refined by a fixed-point loop, so they
are path-dependent. They cannot be recovered from the structure, the instrument
and the pattern. Storing them is what makes a Le Bail checkpoint restorable at
all. In the walkthrough of [](quickstart.md) the Le Bail node carries 129
extracted intensities and the Rietveld nodes carry none, because in Rietveld
mode the structure computes them.

### The metrics it caches

`NodeMetrics` holds the scalars that let `RefinementTree.best` and
`RefinementTree.compare` answer without recomputing anything.

| Field | Holds |
|---|---|
| `NodeMetrics.statistics` | the `Statistics` block, or `None` on a node that ran no fit |
| `NodeMetrics.status` | `converged`, `max_iter` or `diverged`; `None` where no fit ran |
| `NodeMetrics.n_iterations` | least-squares iterations taken |
| `NodeMetrics.cost_initial` | the cost the stage started from |
| `NodeMetrics.cost_final` | the cost it reached |
| `NodeMetrics.stderr` | esds by dot-path, in physical units |

These are as-optimised numbers: the agreement the least squares reached on the
model it was minimising, whose reflection list, windows and quadrature node
counts were frozen at the values the stage started from. Recomputing the same
state with a fresh compile can differ slightly, and `replay` below is how you
see by how much.

A large gap is a reading rather than a defect. It says the stage travelled far
enough that its frozen discreteness went stale, which is an argument for
splitting the stage.

A `RefinementResult` is not measured this way. Its statistics and curves come
from one more compile at the values it returns, with the last stage's own
settings, so a result reproduces from its own parameters while the node it
produced keeps the as-optimised figure. The two differ by the gap described
here, and when that gap exceeds 1 % of χ² the result carries it as
`FROZEN_COMPILE_STALE` ([](results.md)).

`NodeMetrics.status` is the solver's, copied from the stage's own
`StageResult`, so it carries that type's three values and nothing more. A node
that ran no fit (a `set_vary`, a `set_value`, the root) carries `None` instead,
which is the only extra state there is. A stage whose globs matched
nothing is not one of them: it still runs, and it converges.

## Reading a tree

A `RefinementTree` is a dict of nodes, a list giving their order, and a dict of
named refs. `RefinementTree.for_data` builds an empty one, and
`RefinementTree.add` commits a node into it. Both are what `Refinement` and
`Project` call for you; here they build a tree with no fitting in it at all:

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
assert tree["head"].action.api_call() == "ref.set_values({'phases.0.cell.a': 4.157})"
assert tree.diff("n0000", "head") == {
    "phases.0.cell.a": (4.15689, 4.157),
    "phases.0.cell.b": (4.15689, 4.157),   # cubic: b and c follow a
    "phases.0.cell.c": (4.15689, 4.157),
}
```

`RefinementTree.nodes` maps id to node and `RefinementTree.order` lists the ids
as they were committed. `tree[key]` takes either an id or a ref name, `len(tree)`
counts the nodes, and `key in tree` accepts both kinds of key too.
`RefinementTree.resolve` is that lookup on its own, returning the id a name
points at. `RefinementTree.path` is the log file the tree appends to, or `None`
for a tree held only in memory.

Five queries walk the graph.

| Call | Returns |
|---|---|
| `RefinementTree.root` | the node with no parents |
| `RefinementTree.children` | the nodes committed on top of a given one |
| `RefinementTree.leaves` | the nodes nothing was committed on top of, one per open branch |
| `RefinementTree.lineage` | root to a node, following first parents |
| `RefinementTree.ancestors` | every node a given one descends from, following all parents |

`RefinementTree.common_ancestor` is the merge base of two nodes: the latest node
both descend from. `Refinement.merge` uses it, and it answers "where did these
two strategies diverge" on its own.

Three queries compare nodes instead of locating them.
`RefinementTree.best` returns the node with the lowest Rwp. It takes the name of
any other `Statistics` field, and `minimize=False` to take the highest instead.
Nodes carrying no statistics are skipped, and a tree with none at all raises
rather than returning an arbitrary node:

<!-- api-doc: no-exec — it needs a tree with fitted nodes in it -->
```python
print(ref.history.best("rwp").id)
```

`RefinementTree.compare` returns a flat table for the nodes you name, one row
each with id, label, action, status, free-parameter count, Rwp, GoF and χ².
`RefinementTree.diff` returns the parameter values that differ between two
nodes, as `path: (before, after)` pairs. Across the model edit in the
walkthrough, 44 paths differ between the Le Bail node and the final one.

`RefinementTree.summary` prints the tree as indented text with an Rwp per node,
`*` on the head and tags in brackets. `RefinementTree.to_mermaid` prints the
same tree as a mermaid graph. [](files.md) has both, beside the log they are
read from.

## Naming a node

Node ids are assigned in commit order, which makes them stable addresses and
poor labels. Refs are the fix. `RefinementTree.tag` names a node, and every call
that takes a node id takes a tag instead:

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
result = ref.fit(data, mode="lebail")
ref.history.tag(result.node_id, "lebail")
ref.checkout("lebail")
```

`RefinementResult.node_id` is the node a fit committed, and
`RefinementResult.tree_id` identifies the tree it was committed to. Both are
`None` on a result produced with the history switched off.

`RefinementTree.annotate` writes a label, scores and notes onto a node after the
fact, and `RefinementTree.refs` is the whole ref table, `head` included.
`RefinementTree.set_head` moves the head ref without touching the working state,
which is the low-level half of a checkout.

Annotations are an overlay rather than an edit. Each one is recorded as its own
`Annotation`, with `Annotation.node_id`, `Annotation.label`, `Annotation.refs`,
`Annotation.scores` and `Annotation.notes`, and applied on top of the node when
the log is read back. That keeps the log append-only while still letting a node
acquire a name.

:::{admonition} For agents
:class: agent
`HistoryNode.scores` and `HistoryNode.notes` are the bookkeeping channel. They
are yours to write, nothing in the package reads them, and they survive a save
and a reload. A search over strategies can score each leaf as it commits and
sort the leaves afterwards, without holding a table of node ids anywhere else.
:::

## Going back, and forking

`Refinement.checkout` restores a recorded state into the working tree. The node
is untouched, and the next stage commits on top of it, which forks the graph.

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
ref.checkout("lebail")                  # back to the Le Bail state
ref.run_stage(data, rx.Stage("cell", ["phases.*.cell.*"]))   # a second branch
```

`Refinement.branch` is the same move without giving up where you are. It returns
a second `Refinement` over the same tree, so two strategies can be run and
compared:

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
alt = ref.branch("lebail")
alt.fit(data, plan="profile_only")
```

Each `Refinement` carries its own position, so `ref` stays where it was. The
tree's `head` ref is shared, and it follows whichever object committed or
checked out last. Read `RefinementTree.head` as "where a reopened session
resumes" rather than as "where this object is".

`Refinement.from_node` opens a new refinement positioned at a node, as a
container does when it reloads a session:

<!-- api-doc: no-exec — it needs a tree loaded from a log -->
```python
tree = rx.RefinementTree.load("nac.jsonl")
ref = rx.Refinement.from_node(tree, "head")
```

`Refinement.cherry_pick` takes another node's action and runs it here. It
replays the recorded stage rather than the recorded values, so a strategy is
reusable on a different branch or a different specimen:

<!-- api-doc: no-exec — it needs a tree with a stage node in it -->
```python
alt.cherry_pick("n0012", data)
```

Only a `stage` node can be cherry-picked. Any other kind raises and says which
kind it found, because there is no stage to re-run.

`Refinement.merge` combines another branch into the current state. Parameter
values are merged per dot-path against the two branches' common ancestor: a path
changed on one side takes that side's value, and a path changed on both takes
the side named by `prefer`, which is `"theirs"` by default and `"ours"` for the
current head. The merged node records both parents.

<!-- api-doc: no-exec — it needs two branches over one tree -->
```python
ref.checkout("n0012")                 # the state to merge into
ref.merge("n0013", prefer="ours", label="keep this model on conflicts")
```

Only values merge. The model composition comes from the preferred side whole:
which phases exist, which background, which free set, which mode. In the
walkthrough's tree the CaF₂ impurity arrives in a model edit, so merging the Le
Bail branch into the final state with `prefer="theirs"` returns a one-phase
model. Nothing raises. Read `Refinement.structure` back after any merge that
crosses a model edit.

## Recomputing a node

`replay` recomputes a node's curves and statistics from its state:

<!-- api-doc: no-exec — it needs a tree and the pattern it was fitted against -->
```python
result = rx.replay(ref.history, "lebail", data)
print(result.statistics.rwp, result.node_id, result.tree_id)
```

It is strictly evaluate-only. It never runs a Le Bail update, because inspecting
a checkpoint must not change it, and it never commits a node.

The model is compiled fresh at the node's own values, so the statistics it
returns can differ from `NodeMetrics.statistics`, which the optimiser measured
on a model frozen at the values its stage started from. On the walkthrough's
final node the two Rwp values differ by 1.6e-7. A difference of that size is the
freeze being re-taken, and a large one is the staleness signal described
above.

`replay` refuses a pattern that is not the one the tree was recorded against,
comparing fingerprints and naming both. That refusal is the reason the header
below exists.

## The tree's identity

`TreeHeader` is the first record in a log and the answer to "what is this a
history of". `RefinementTree.header` is that record on a tree you hold.

| Field | Holds |
|---|---|
| `TreeHeader.tree_id` | the tree's id, derived from the data fingerprint |
| `TreeHeader.data_fingerprint` | a sha256 over the parsed float64 2θ and intensity arrays, first 32 hex digits |
| `TreeHeader.data_source` | the file the pattern was read from, where the reader recorded one |
| `TreeHeader.n_points` | how many channels that pattern had |
| `TreeHeader.plan` | the plan the tree was created with, as a `PlanSpec` |
| `TreeHeader.package_version` | the version of rietx that created it |
| `TreeHeader.schema_version` | the data-contract version of the nodes |
| `TreeHeader.created_utc` | when the tree was created |

`TreeHeader.data_fingerprint` is the digest of the parsed arrays rather than of
the file's bytes, so it answers the question a replay needs answered: are these
the numbers the nodes were fitted against. [](files.md) covers the second digest
a project keeps beside it, and what disagreement between the two means.

`TreeHeader.plan` records the plan the tree was created with, which is not
necessarily the plan any given node ran. In the walkthrough it reads
`profile_only`, because the first call was a Le Bail fit and that is the plan
Le Bail mode selects. What each node ran is on that node's own `NodeAction`.
