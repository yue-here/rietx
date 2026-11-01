# WP-1991 — a site and its own image are one atom on every route

Milestone: unscheduled · Status: 🔄 2026-11-01 — #1264 fixed in PR #1274 (merged 2026-11-01, `95bd38953`; a path follows its atom by label); open: the `adp.k` probe, series trajectories by phase name + atom label (ruled 2026-11-01), phases by name
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-16 — a doubled composition with nothing firing, but only on a stored, hand-edited or code-built coordinate; a refined coordinate cannot drift there, and the CIF route already merges it

## Goal

A free atom within a fraction of an ångström of a special position counts
once in the cell on every route into a `Structure`, and says so, as a CIF
read already does.

## Context

Issue #1007 (mustachefeeling, 2026-10-16), found building #1005 (R6 of #561).

Reproduced at `138d55dc` with the issue's script (PbSO₄,
`tests/data/gsas2_pbso4.gpx`, Pnma; S2 on the mirror at y = ¼,
multiplicity 4; only S2's y moved; counted by
`rietx.optimize.qpa.phase_zmv`):

```
dy=0       S per cell = 4
dy=5e-05   S per cell = 4
dy=6e-05   S per cell = 8
dy=0.0001  S per cell = 8
```

Mechanism, from the issue and the code: `site_orbit`
(`crystallography/symmetry.py:867`) tests |R·x + t − x| against
`SITE_TOL = 1e-4` (line 766). A mirror's displacement is 2δy, so the
effective tolerance there is `SITE_TOL`/2. Past it the atom is general and
its image sits 2δy·b away (0.0006 Å at δy = 1e-4). The two images overlap
within the profile's resolution, the scale and Biso absorb the doubled
atom, and building a `Refinement` emits nothing.

What exists to reuse: #764/#765's twin merge in `structure_from_cif`
(`crystallography/cif.py:353`, `TWIN_DISTANCE = 0.02` Å at line 320). A
site whose own images lie closer than that is put on the special position
its orbit collapses to, with `CIF_SITE_TWINS_MERGED`. The gap is every other
route: a project file, a hand edit, a structure built in code. #1005 refuses
the rigid-body analogue (`RIGID_BODY_IMAGE_OVERLAP`, WP-1807, #876).

The reporter's comment proposes the fourth of their options: apply the twin
merge wherever an orbit is expanded, at the same distance, under a code
renamed off the `CIF_` prefix. A reader and a hand-built structure then
agree. They have said a PR follows.

Two constraints. `SITE_TOL` stays tight (#215: five-decimal files), so the
answer is the merge at a distance, never a looser snap. And the merge must
happen where a diagnostics channel exists: `ParameterTable` has none (root
CLAUDE.md, "a silent correction is a reader's to make").

Superseded in part, 2026-10-31: the Priority line's premise "a refined
coordinate cannot drift there" holds only for a site already special. #1088
showed a general atom at occupancy ½ refined onto a mirror is snapped by the
next stage compile, and the default plan's closing stage then returns 10 O per
cell for 12 (10 of 16 noise draws). That mid-fit case is WP-2052's, outside this
WP (checked at c0e32ab29, 2026-10-26).

### An atom's number is not its identity (#1264)

Issue #1264 (mustachefeeling, 2026-10-31), the case the 2026-10-31 handover
left uncovered. A dot-path names an atom by its index, so a path read by index
across two structures whose atom lists differ names the wrong atom.
`numbering_moves` listed only sites whose own DOFs renumbered, and every other
path crossed by index. In a series, a `prepare` hook that removes an atom ahead
of a site tied by the `constrain` hook made `_displaced_as_built` miss the tie,
and the warmed variable added the fitted displacement again. Reproduced at
`1314c69ea` with the issue's script: pattern 2 started O3's z at 0.8437 for
0.8268. The merge alone cannot cause it, since `merge_site_twins` never removes
or reorders an atom.

The same index crossing sat in three more places, all measured at `1314c69ea`.
`_carry_into` read the previous pattern's values (built numbering) into the
declared structure by index; with O1 removed from every pattern, O2 started
pattern 2 at O3's general position, off its mirror. `_reanchor_carried` read the
source's values against the built table's paths. And `Refinement.edit`, the
GUI's remove-atom route, kept holds, ties and free paths by index: removing O1
moved a hold on O2's Biso onto O3's and dropped a tie on O3 as "no such
parameter".

The tier of the rule this adds: an automatic action of Rule 1's first kind
(`docs/DESIGN.md` § Rules). Where a label is unique in both structures, the atom
is the same atom, and every refiner would carry its constraint to it. An atom
the match cannot place has its constraints dropped where another atom took its
number, with a warning on `edit`; where its number names no atom, its paths are
left as they were (WP-1435 keeps such a hold).
No diagnostic code, number or default is added, so `rietx._audit` is unchanged.

### Ruling: series trajectories are keyed by phase name and atom label (2026-11-01)

The question left open by PR #1274 (merged 2026-11-01 as `95bd38953`): does a
series report a parameter per atom label or per path? Yue ruled on 2026-11-01,
about 10:00 ("confirm a"), on the lead's recommendation, option A extended to
phases. Users and agents may add or remove phases and atoms in the middle of a
series, so a path such as `phases.1.atoms.2.biso` names a different atom in
different patterns. The ruling:

- A trajectory is keyed by phase name, atom label and parameter.
- A pattern where the phase or the atom is absent leaves a gap, never a zero or
  a neighbour's value.
- Each point carries its per-pattern dot-path beside it, so a reader can still
  find the parameter in that pattern's model.
- A duplicate phase name, or a duplicate atom label within a phase, is
  **refused**, not guessed at.
- An old `SeriesResult` file is converted at read, by the migration pattern of
  `schemas/migrate.py`.

This is a stored-format change and changes what a series returns. Its PR goes to
Yue before merge, under the reader-output rule (`python -m tests.reader_output`),
and no runner merges it. The phase-name matching task below is the same rule one
level up, and the two should share one matcher.

## Non-goals

- Changing `SITE_TOL`.
- The rigid-body case (WP-1807).

## Tasks

- [x] Find every route that expands an orbit without the CIF reader's merge,
  and the one place a merge with a diagnostic can sit for all of them.
  (PR #1014, `b0019706`: `twins.merge_site_twins`.)
- [x] Apply the twin merge there, renaming the code off `CIF_` (keep the old
  code readable for stored results, or record the break). (PR #1014:
  `SITE_TWINS_MERGED`; the reader keeps `CIF_SITE_TWINS_MERGED`.)
- [x] Tests: the issue's δy sweep reads 4 S at every step, and the warning
  fires from δy = 6e-5 to the 0.02 Å boundary (PR #1014,
  `tests/test_site_twins_merged.py`)
- [x] Skill: the reference row for the renamed code (PR #1014,
  `references/diagnostics-reading.md`)
- [x] #1264: every path read across a changed atom list follows its atom by
  label (`twins.atom_moves`, `renumber_path`): the series carry, the
  displaced paths, the re-anchor, and `Refinement.edit`'s registers.
- [ ] Anisotropic ADP DOFs (`phases.i.atoms.j.adp.k`) are not renumbered by
  `numbering_moves`, so a hold or tie on `adp.k` of a site that merges is not
  carried. Read off the code in PR #1223's review, never probed: probe it,
  then fix or fence.
- [ ] A series trajectory follows its atom, as ruled 2026-11-01 (see
  § Ruling above). `SeriesResult.trajectory(path)` and the fences built on it
  join patterns by path, so a `prepare` that changes the atom list per pattern
  joins two atoms into one trajectory (PR #1274's handover). Key trajectories by
  phase name + atom label + parameter, with gaps where absent and the
  per-pattern path beside each point; refuse duplicate phase names and duplicate
  atom labels within a phase; convert old `SeriesResult` files at read. **Gate:**
  a stored-format and reader-output change, so its PR goes to Yue before merge
  (`python -m tests.reader_output`, WP-2010's rule), and the manual's series
  chapter and the skill's series reference change in the same PR.
- [ ] Phases are matched by name where unique, as atoms are by label.
  `atom_moves` and `numbering_moves` match phases by position, so removing a
  phase ahead of another renumbers every `phases.N` path the way #1264 did
  for atoms (PR #1274's `/code-review`).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cif_sites_coincide.py -q   # plus the file this WP adds
.venv/bin/python -m ruff check src tests examples
```

## References

- International Tables for Crystallography Vol. A (site multiplicity).
- Issues #1007, #765, #876, #215.

## Handover log

### 2026-11-01 (2nd session) — PR #1297: the ruling on series trajectories recorded (docs only)

When a user or an agent adds or removes an atom or a phase partway through a series, a trajectory joined by dot-path can follow two different atoms as if they were one. Yue ruled this morning how a series should report instead: by phase name and atom label, with gaps where something is absent. That ruling is now written into this WP as a task, so the next session finds it in the file and not in a chat. Nothing in the package changed. Implementing it changes what a series returns and how its files are stored, so that PR waits for Yue.

  *Done.* § Ruling (2026-11-01) under Context states the ruling. The open task "A series trajectory follows its atom" now names it: key by phase name + atom label + parameter; leave gaps where a phase or atom is absent from a pattern; carry the per-pattern dot-path beside each point; refuse duplicate phase names and duplicate atom labels within a phase; convert old `SeriesResult` files at read. Its **Gate** line says the PR is a stored-format and reader-output change and goes to Yue before merge (`python -m tests.reader_output`). The Status line records that PR #1274 merged as `95bd38953` on 2026-11-01. Source of the ruling: Yue, 2026-11-01 about 10:00, "confirm a", on the lead's option A extended to phases (ghostshift 2026-10-31 note).

  *Measured.* Nothing, since no code changed. Checked: PR #1274's state is MERGED at 95bd38953 (`gh pr view`). `closed_wp_writes.py` reports nothing. `/code-review` skipped: the branch touches one markdown file under `docs/wp/`.

  *Gotchas.* PR #1282 (mustachefeeling, opened 2026-11-01, `fix/1264-series-carry-label-match`) is still open, CONFLICTING, and names WP-1991. It touches `twins.py`, `sequential.py` and a new test file for the same #1264 carry that #1274 fixed. It is probably superseded by #1274 and was not read for this entry. Whoever reviews it should check it against `95bd38953` before any ask for changes.

  Next: the `adp.k` probe still goes first (possibly a one-line fix). The trajectory keying follows, and its PR goes to Yue before merge. The keying and phases-by-name tasks both need a phase matcher, so build one matcher and use it for both. Refusing duplicate names at read must not break old files: convert at read, and decide with Yue's rule "old files always open" what an old file with duplicate names becomes.

- **2026-11-01** — PR #1274, closing #1264. A path that names an atom by its number now follows the atom when two models number their atoms differently. The issue's series case is fixed: a `prepare` hook that removes an atom ahead of a tied site no longer adds the fitted displacement twice. Three siblings with the same cause are fixed as well. The series carry wrote each value onto whichever atom held the number, so an O on a mirror could start the next pattern at a general position. The re-anchor read the previous pattern's values against the wrong numbers. And `Refinement.edit`, which the GUI's remove-atom button calls, moved a hold onto the next atom with nothing said. Nothing about which atoms or phases a series reports per pattern has changed, and that is the next thing to look at.

  *Done.* `twins.atom_moves` maps each old atom path to its new one, or to `None`, wherever the number changes; `renumber_path` reads a dot-path through it; `NumberingMoves` carries it as `.atoms`, with `.renumber` and `.in_new_numbering`. `_matched_atoms` decides identity in this order: identical lists by position; one inserted or removed block the labels place at exactly one position, by position either side (from `/code-review`); each label both phases hold equally often, occurrences in order; an atom renamed in place, by position, only when no atom was added or removed. An unmatched atom maps to `None` only where another atom took its number; where its number names no atom its paths are left alone, so WP-1435's rule that an edit keeps a hold on a removed path still holds (`test_a_hold_on_a_path_an_edit_removed_is_kept_and_said_out_loud` caught the first version). Readers: `sequential._values_onto` (the carry and the re-anchor), `_displaced_as_built` (every site, not only renumbered ones), and `Refinement._carry_twin_moves` through `_renumber_atoms`, which renumbers holds, ties (target and sources), free paths and `_held` before the DOF moves, rekeyed to the new numbering. A dropped hold or tie warns once; a dropped free path does not, since a plan re-declares the free set. The `constrain` docstring now says the hook sees the built model's atom numbers.

  *Measured.* At `1314c69ea` with the issue's script: pattern 2 started O3's z at 0.8437 against 0.8268 fitted; with O1 removed from every pattern, O2 started at O3's (0.081, 0.025, 0.8134), off its y = ¼ mirror; after the fix, 0.8268 and (0.19, 0.25, 0.543). Of the new tests, the three behaviour tests fail on main's `src` (snapshot run: 0.8286 against 0.8186; O4 at O5's position; no warning from `edit`), and the `atom_moves` cases fail on import. Fast suite on this branch with origin/main merged in (`6a1f29e8a`), final tree `b9d374ff1`, macOS arm64, `[dev]`, Python 3.12: 13 176 passed, 310 skipped, 32 xfailed, 1 failed. The failure is `test_site_classes.py::test_an_unplaceable_species_does_not_enumerate_the_others`, a 15 s wall-clock budget that took 18.0 s under load and 12.2 s alone, where it passes; it touches nothing this branch changed, and it is filed into WP-1997's `### Inherited`. The run before the last fix had the same totals with `test_params_surface.py::test_a_hold_on_a_path_an_edit_removed_is_kept_and_said_out_loud` as its one failure, which the fix answers. No main baseline was measured, so the delta against main is CI's to show. The 15 added tests are 3 behaviour tests and 12 `atom_moves` cases, in `tests/test_site_twins_merged.py`. Added-test cost, one local run: 2.58 s and 1.01 s for the two series tests, 0.09 s for the `edit` test, 0.07 s for the 12 `atom_moves` cases; 3.76 s in all, none near the fast tier's tail.

  *Generality* (the `generality-review` agent, run before the matching was tightened; both verdicts were "weak"; its tables are condensed, its findings unedited):
  **`twins._matched_atoms`: the rule that decides which atom is which across two atom lists.** Verdict: weak. The case for acting is strong where a label is unique in both lists. The two new fallback steps have no evidence behind them. One is the positional match for an atom renamed where it stands. The other is "no partner, so drop". Reading the code, I found one case where each gives a wrong answer.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | WP file § "An atom's number is not its identity (#1264)": "Where a label is unique in both structures, the atom is the same atom." `_matched_atoms` docstring: an atom renamed in place "is matched by position"; "Any other atom has no partner and is a different atom". | It decides which old atom is which new atom, so every path is renumbered by that decision. Step 1, unique-label matching, already existed for coordinate-freedom moves (#1014 round 6). The rename-in-place step is new. Applying the match to every path is new. | stated |
  | 2. Kind of ambiguity | "an automatic action of Rule 1's first kind" (WP file). There is no audit row, so no `ambiguity` field. | The unique-label step is kind 1. The rename and no-partner steps choose between hypotheses that can be listed: was B removed and C renamed, or was B renamed and C removed? Species and coordinates could score them, so these steps are kind 2. They pick without that evidence, which is outside Rule 1's two cases. | partly disagrees |
  | 3. Case against acting | none given | Both read off the code and not run. (a) A removal and a rename together: `[A,B,C]` becomes `[A,C2]`. The rename step pairs old index 1 with new index 1, so B's hold or tie moves onto C2 with no message. (b) Repeated labels: rietx does not require unique labels. Take `[O,O,S]` with S removed. No label is unique and no rename applies, so both O atoms map to nothing. The index carry this replaces was right for them. | weak (the change has no answer to either case) |
  | 4. Case for acting | WP file: #1264 reproduced at `1314c69ea`, 0.8437 for 0.8268. On `edit`, removing O1 moved a hold from O2's Biso onto O3's and dropped a tie on O3. | Measured, and this is a number moved off where the fit left it. GSAS-II 5.8.4's `G2VarObj` docstring (`GSASIIobj.py` lines 937-963) stores an atom in a constraint by a random ID, not by its number, which it says "can change". | strong for unique labels |
  | 5. Tier and source | none given | Closest fit is tier 2 for "follow the atom, not the index", resting on GSAS-II, checked in its source. GSAS-II keys on a stable ID, not a label, so its identity survives a rename. rietx needs the positional guess for that. FullProf and TOPAS not checked. | none given |
  | 6. Dataset families | none given | No threshold. One synthetic PbSO₄ model and one test of bare label lists. | n/a |
  | 7. What records that it fired | none given | Nothing records the match itself. No field or diagnostic says an atom went unmatched. | missing |

  Author: (a) and (b) are fixed in `47110e9ee` and `19ba3a212`. A rename pairs by position only when no atom was added or removed. A label both phases hold equally often pairs its occurrences in order, and one inserted or removed block the labels place at one position pairs by position either side. Both cases are rows of `test_atom_moves_names_every_atom_whose_number_changes`. Item 7 stands. On `edit` a dropped hold or tie warns, and a moved one is not named.

  **The always-on carry: paths follow their atom, and paths on an unmatched atom are dropped (series and `Refinement.edit`).** Verdict: weak. The case for following the atom is strong and measured. The drop half fails Rule 4's "records that it fired" in the series, and on `edit` it is reported only by a Python warning.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides | WP file: "An atom the match cannot place has its constraints dropped, with a warning on `edit`." | Every series carry (`_carry_into`, `_displaced_as_built`, `_reanchor_carried`) and, on `edit`, holds, ties and free paths. A value on an unmatched atom is not carried, so that atom starts the pattern from its declared value. | stated |
  | 2. Kind of ambiguity | first kind (WP file) | Kind 1 for "a path follows its atom". Dropping a constraint on an atom that is gone is kind 1 too. The drop for an atom present but unmatched inherits item 1's kind 2. | partly agrees |
  | 3. Case against acting | none given | Item 1's case (b) reaches the series with no message. Free paths dropped on `edit` give no message, which is reasonable since a plan replaces the flags (WP-1208). Dropping a hold contradicts the `edit` rule that a hold "is kept"; the new comment states the exception and its reason. | weak (series silence) |
  | 4. Case for acting | the measurements above, plus `_carry_into` with O1 removed from every pattern: O2 started pattern 2 off its mirror | Measured, with three tests. No competent refiner wants a hold to land on a neighbouring atom. | strong |
  | 5. Tier and source | none given | As item 1. GSAS-II's sequential refinement shares one phase across histograms, so the atom list cannot change across patterns there, and the series half has no program to compare against. | none given |
  | 6. Dataset families | none given | No threshold. One synthetic PbSO₄ model. | n/a |
  | 7. What records that it fired | WP file: "with a warning on `edit`" | On `edit`, a `UserWarning` naming each dropped hold or tie; not a diagnostic, not stored. Series: nothing for a dropped carry or tied path. | missing in the series |

  Author: case (b) no longer reaches the series. The fast suite then held the hold drop to WP-1435's rule, so an unmatched atom whose number names no atom now keeps its paths, as before. The drop applies only where another atom took the number, which is where keeping it held that atom. The series silence stands, because only the caller's own `prepare` removes an atom there and nothing is inferred. A diagnostic code for it would be a new audit row and skill row for a case no user has reported.

  *Review.* `/code-review high --fix` found 7. Applied: the single-block rule above (a repeated label appended lost every earlier atom of it), dict-based label lookup, and one `_values_onto` helper for the two copies. Declined, with reasons: phases are still matched by position (below); a `constrain` hook that itself removes atoms leaves `displaced` and the hook's ties in two numberings (the hook is documented to run on the built model, and changing what a hook may do is a design call); a dropped free path is silent and `_free_set_declared` stays set (a plan replaces the free set anyway, WP-1208); `numbering_moves` matches atoms twice per changed phase (cheap at today's sizes).

  *Deliberately not generalised.* (1) `SeriesResult.trajectory(path)` and the fences built on it join patterns by path, so a `prepare` that changes the atom list per pattern still joins two atoms into one trajectory. Keying a trajectory by atom changes the series' reporting surface; it is a task below. (2) Phases are matched by position in `atom_moves` and `numbering_moves`, so removing a phase ahead of another renumbers every `phases.N` path the same way atoms did; a task below. (3) Rigid bodies (`phases.i.rigid_bodies.b`), and plan or stage globs that name a literal atom index, are not renumbered. (4) The GUI does not surface the new warning, nor the existing tie-drop one; both reach the server's stderr. (5) The series records nothing when a carried value or displaced path is dropped for an atom the caller's `prepare` removed: the caller removed it, so nothing was inferred.

  *Gotchas.* On the PbSO₄ fixture with the scale free, the ladder escalated pattern 2 to a cold rung even with a correct warm start, so the tests read the first rung's start (`started.setdefault`). Not investigated.

  Next: the three open tasks, in this order. The `adp.k` probe first, since it is the last open item from #1014's review and may be a one-line fix. Then the trajectory keying, which needs a decision on whether a series reports per atom label. Then phases by name, which follows the same matching rule one level up.

- **2026-10-31** (`/pr-review`) — #1014's follow-ups merged from outside as PR #1223 (`e93378da`), two `WP-1991:` commits, after two rounds. They are the four items round 6 of #1014 listed. (1) A hold on x was dropped where the position couples x and y, as (x, 2x, z) does in P 6₃/mmc. The site merged 24 → 12, `_user_holds` emptied, and x refined. `twins._linked` now pairs each old DOF with every new DOF it shares a direction with. A hold follows every paired new DOF. A free path follows only where every coordinate the new direction moves was free. A tie needs a single direction and is still dropped, with a message naming the coupling. Tests cover P 6₃/mmc 12k, P m-3m 24m (x, x, z) and R-3m:H 18h (x, −x, z), each with holds on x, y, z and x+z. (2) `RefinementTree.load` carries every path-bearing action field (`turn_on`, `turn_off`, `values`, `held`, `unheld`, `ties`, `untied`) through `twins.carry_action_constraints`, in the parent state's numbering, and what moved joins the site's one `Constraints:` note. (3) A series `constrain=` hook runs against the declared structure's numbering (`sequential._constrain_in_declared_numbering`). On main a hold on `dof.2` raised `unknown parameter path` and ended the series. (4) `carry_constraints` uses the full form θₜ' = (sₜ·c/sᵢ)·θᵢ' + sₜ·k. Every s is 1 today, pinned by a sweep of 17 site templates in each of the 230 groups with the scale set exactly {1.0}. Round 1 found that the re-anchor read the carried displacement in the declared numbering while the hook's ties land in the built one. On O5 declared on the y = ¼ mirror and warmed off it, the hook's tie to `vars.dz` was missed, and pattern 2 started z at 0.8620 against pattern 1's fitted 0.8403. `_displaced_as_built` now maps it through `numbering_moves`, and a new test fails on the old code. `DofMove`'s docstring names `_dof_moves` as the one writer and says the empty defaults mean "not computed". The PR adds 20 tests, of which 17 fail on main's `src` and 3 are hold-on-z controls that pass there. `tests.audit_delta` reports 1 changed (`SITE_DOFS_RENUMBERED`'s evidence, still tier 1), 0 new at `unaudited`. The skill row's three copies, `help.py`, `reference/structure-files.md` and the 1.11.0 note carry the new wording. Left open. Anisotropic ADP DOFs (`phases.i.atoms.j.adp.k`, numbered by `wyckoff.adp_basis`) are not renumbered by `numbering_moves`, so a hold or tie on `adp.k` of a site that merges is not carried. The contributor read this off the code, did not probe it, and asked whether it belongs here or in its own WP. The review left that unanswered. An atom shifting index because the merge removed one ahead of it, for a site whose own DOFs did not renumber, is uncovered. The review said it is worth an issue of its own. No task is ticked, and the Status line still reads to be checked against #1014. Gate (the six PRs of this round merged together onto main `766c3505d`; macOS arm64, `[dev,jax]`, Python 3.12): fast 12 884 passed, 223 skipped, 32 xfailed; slow 435 passed, 18 skipped, 16 xfailed, with one GUI-boot socket timeout under load that passed alone in 5 s; ruff and the `-W` manual build clean.

- **2026-10-29** (`/pr-review`) — merged from outside as PR #1014 (`b0019706`) after nine rounds, closing #1007. A site whose images coincide is merged onto its special position on every route, not only CIF reads, under one F-independent gate (`TWIN_COORD_TOL`), with `SITE_TWINS_MERGED`/`SITE_TWINS_KEPT` and `SITE_DOFS_RENUMBERED`. Where several subgroups of one order have a fixed point in reach, the nearest wins (round 8). `TWIN_DISTANCE` moved to `symmetry.py` and stays on `UNAUDITED_BASELINE`. One note for later: the tie-break measures in fractional max-norm, as the reach does, so on a cell with unequal axes the Cartesian nearest can differ.

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #1007).
  Checked against the tree at `138d55dc`: reproduced, S doubles from
  δy = 6e-5. No open WP owns it: WP-1807 owns a body on a special position,
  and WP-1324 and WP-1319, which touched site handling, are closed. The
  reporter has said a PR follows on option four. Next: review that PR
  against this file.
