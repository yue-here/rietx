(guide-branch)=
# How to branch a refinement, compare the branches and roll back

Tag the node to start from, run the second strategy on `Refinement.branch`, compare the two ends with `RefinementTree.compare`, and return to the better one with `Refinement.checkout`.

Every stage and every edit commits a node to the refinement's history, `Refinement.history`.
A node keeps the parameter values, the free set, the ties and the holds, so any of them can be restored and refined again.

## Fork at a node

This runs two stages on the fluorapatite pattern that ships with rietx, tags the second, and then frees the peak widths in two ways from that one node:

```{literalinclude} ../../../examples/guides/branch.py
:language: python
:start-after: "# guide: start"
:end-before: "# guide: end"
```

`ref.history.tag` names a node, and every call that takes a node id takes the name instead.
`ref.branch("cell")` returns a second `Refinement` over the same history, positioned at the tagged node.
Each object keeps its own position, so `ref` stays at the end of strategy A while `alt` runs strategy B.

## Compare the branches

`RefinementTree.compare` returns one row per node, and `RefinementTree.best` returns the node with the lowest Rwp in the whole tree:

```{literalinclude} ../../../examples/guides/branch.py
:language: python
:start-after: "# guide: compare start"
:end-before: "# guide: compare end"
```

<!-- output of examples/guides/branch.py -->
```text
n0003  stage:profile  free 15  Rwp 0.0947
n0005  stage:profile  free 15  Rwp 0.0947
best: n0005
```

Both ends refine the same 15 parameters and reach Rwp 0.0947, so on this pattern the two orders find one fit.
`best` returns `n0005`, lower by 0.00002.
`best` takes the name of any other `Statistics` field, such as `"gof"` or `"chi2"`, and skips the nodes that ran no fit.

`RefinementTree.diff` lists the parameters whose values differ between two nodes, as `(first, second)` pairs.
Here it is narrowed to the five width terms, in deg²:

```{literalinclude} ../../../examples/guides/branch.py
:language: python
:start-after: "# guide: diff start"
:end-before: "# guide: diff end"
```

<!-- output of examples/guides/branch.py -->
```text
instrument.profile.u   0.00187  0.00187
instrument.profile.v   -0.00320  -0.00320
instrument.profile.w   0.00324  0.00324
instrument.profile.x   0.03102  0.03101
instrument.profile.y   0.03371  0.03372
```

The full list also holds the background, zero shift, lattice parameters and scale.
Every value in it is within 0.05 % of the other branch's.

## Roll back and carry on

`Refinement.checkout` puts the working models back to a node's values.
The node itself is unchanged, and the next stage commits on top of it:

```{literalinclude} ../../../examples/guides/branch.py
:language: python
:start-after: "# guide: rollback start"
:end-before: "# guide: rollback end"
```

<!-- output of examples/guides/branch.py -->
```text
tcb8d2285  7 nodes  data=FAP.XRA
 n0000  root                   —
 n0001  stage:scale_bkg        Rwp 0.6050
 n0002  stage:cell             Rwp 0.4919  [cell]
├─  n0003  stage:profile          Rwp 0.0947  [together]
└─  n0004  stage:profile_w        Rwp 0.1930
    n0005  stage:profile          Rwp 0.0947  [w_first]
   *n0006  stage:biso             Rwp 0.0943
```

`RefinementTree.summary` draws the tree with each node's Rwp and its tags in brackets.
A fork is indented, and `*` marks the head, the node the last commit or checkout moved to.
Strategy A's end, `n0003`, stays in the tree and can be checked out again later.

The same call undoes a stage without a branch: check out the node before it and run something else.
The stage you undid stays in the tree as a branch nobody continued.

## Recompute a node

A node records the Rwp the solver reached, on a model whose reflection list and peak windows were fixed when its stage started.
`rx.replay` recomputes a node's curves and statistics from its values, without refining and without adding a node:

```{literalinclude} ../../../examples/guides/branch.py
:language: python
:start-after: "# guide: replay start"
:end-before: "# guide: replay end"
```

<!-- output of examples/guides/branch.py -->
```text
together  recorded 0.0947  replayed 0.0970
w_first   recorded 0.0947  replayed 0.0970
```

The difference comes from rebuilding the reflection list and windows at the stage's final values.
The `RefinementResult` a stage returns is computed as a replay is, so `together.statistics.rwp` is 0.0970.
A result carries `FROZEN_COMPILE_STALE` when its χ² and its node's differ by more than 1 %.
Both results carry it here, at 5.0 %, and the two strategies stay within 0.0001 of each other on either measure.

`replay` refuses a pattern other than the one the history was recorded against, and names both.

## Combine two branches

`Refinement.cherry_pick` takes a stage node from anywhere in the tree and runs the same stage from the current position.
It repeats the recorded stage, with the parameters it freed and its solver settings, and not the values that stage reached.
Only a `stage` node can be cherry-picked.

`Refinement.merge` combines another node's parameter values into the current one, path by path, against the latest node both descend from.
A value changed on one side only takes that side's value, and one changed on both takes the side `prefer` names (`"theirs"` by default).
The phases, background, free set and mode come whole from the preferred side, so read `Refinement.structure` back after a merge across a model edit.

## Keep the history between sessions

A project keeps the history in `history.jsonl`, and reopening it resumes at the last node ([About a project](../concepts/project.md)).
Outside a project, `rx.Refinement(..., history="fit.jsonl")` appends each node to that file as it is committed.
`rx.RefinementTree.load` reads one back, and `rx.Refinement.from_node(tree, "head")` opens a refinement at a node.

## See also

- [How to run a plan one stage at a time](stage.md) shows where in a plan you would stop to branch.
- [How to choose the next parameter to free](next.md) compares two branches of one node to measure a candidate parameter.
- [About a fit](../concepts/fit.md) describes what a node records.
