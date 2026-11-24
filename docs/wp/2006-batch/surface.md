# WP-2006 part 2: the unreached public surface

The walk was re-run at the head of the 2026-11-17 session (`tests/reachability_walk.py`,
written to a scratch directory; the committed `reachability.csv` is part 1's, at 2 267
entries). `derive_surface()` now returns **2 504** entries. By use (`state_use`): 1 154
reached, 85 reached through another entry, 1 236 documented only, 25 tests only, 3
unreached, 1 named only in a docstring example.

**Nothing here is removed.** Removing a public name breaks callers, so each row is a
recommendation for the maintainer.

## The 29 entries no use reaches

All 29 sit in the rigid-body and distance-restraint types of `rietx.schemas.structure`:
`RigidBody`, `BodyOrigin`, `BodyTorsion`, `AntiBumpRestraint` and `TetherRestraint`. A user
builds these by keyword (`RigidBody(name=..., atoms=..., origin=...)`), so each field is used
by construction. The walk reads text and cannot see that. The three `BodyOrigin` entries the
walk calls unreached (`values`, `y`, `z`) are the same case: `x` is named once in a docstring
example and its siblings are not.

| Entries | State | Recommendation |
|---|---|---|
| `AntiBumpRestraint.atom_i`, `.atom_j`, `.min_distance`, `.op_index`, `.sigma`, `.translation`, `.weight` | tests only | Keep. Constructor fields of a restraint a user writes. Cover them in the rigid-body guide when WP-1814 lands. |
| `TetherRestraint.atom_i`, `.atom_j`, `.max_distance`, `.op_index`, `.sigma`, `.translation`, `.weight` | tests only | Keep, as above. |
| `BodyTorsion` and `.angle`, `.axis`, `.name`, `.vary` | tests only | Keep, as above. |
| `RigidBody.atoms`, `.name`, `.origin`, `.riding`, `.rotation_vary`, `.torsions` | tests only | Keep, as above. |
| `BodyOrigin.x` | docstring example only | Keep, as above. |
| `BodyOrigin.y`, `.z`, `.values` | unreached | Keep, as above. `values` is the model's method, reached wherever an origin is read. |

The rigid-body restraint is open with the maintainer (WP-1814, PR #1510). An example under
`examples/` that builds one body would move all 29 to *reached*; that belongs to WP-1814.

## The three exports the WP named

`IndexingEvidence`, `CaveatEvidence` and `CandidateEvidence` are named in no example, no GUI
file and no `src` module outside `schemas/indexing.py`. `IndexingEvidence` is the return type
of `IndexingResult.evidence()`, which examples, the GUI and the skill call. The other two are
the types of its fields. **Keep all three**: a caller reads them through the method, and a
return type is part of the surface whether or not anyone spells its name.

## Declared names with no writer (inherited from WP-1986)

Re-checked by grep at the session's head. Each is a field whose empty state reads as an
answer, the WP-1076 shape. Each needs a choice between writing it, retiring it and
documenting it, and two of those are public-surface changes, so they go to the maintainer.

| Name | What the code does today | Options |
|---|---|---|
| `PhaseMicrostructure.separable`, `.size_strain_collinearity` | `None` on every `RefinementResult.microstructure`. Only the report's deep copy writes them (`report/__init__.py:231-232`). | Write them on the result, or retire them from the result type and keep them on the report's block. |
| `ProjectFormat.refuses` | No member of `PROJECT_FORMATS` sets it (`io/projects/registry.py:134`); the capabilities listing filters on it (`:451`). | Retire it, or keep it as the declared seat for the first refusing format. |
| `SuggestedAction.vetoed_by` | Set from the staged plan and from already-free paths only (`report/layer2.py:1128-1131`). Its docstring and `layer2.py`'s module docstring said "or a guard forbids it". | Fixed in this branch: both docstrings now state what the code does. |
