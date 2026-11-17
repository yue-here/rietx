# WP-1812 — GUI, textdoc, skill and manual for bodies

Milestone: rigid-bodies · Status: ⬜
Depends on: 1805
Priority: P4 2026-10-06 — the surfaces over a feature that already works from python

## Goal

A body round-trips through the `.rxt` textdoc, appears in the GUI, and has its own
generated skill reference and manual section. This is chunk R10 of issue #561, sized S/M.

## Context

- The skill's body verbs go in a separate generated `api-<shape>.md`, never `api.md`
  (root CLAUDE.md § skill; `make_api_index.py`'s docstring). `api.md` had 402 B of
  headroom on 2026-10-01.
- `tests/api_surface.py`'s partition has to go green, moving WP-1805's deferred names
  to documented.
- Manual Part 2 gets a section with the frame contract (WP-1804's closed-form M).
- Some of this lands inside WP-1805 and WP-1808 already: the help rows, `PLACES`, and
  both Part 2 equations. Check what is left before starting.
- It touches no v1.6 file.

### Inherited

- **2026-11-12, from the issue triage (issue #1508): the manual owes a line
  on rings in a Z-matrix body.** A Z-matrix is a spanning tree, so a bond
  that closes a ring is no line of it and no internal controls it.
  Refining a tree bond of the ring moves the closing bond and the ring
  angles, and the refined value depends on which tree the user declared.
  *Checked against the tree at `a86dcf9d4`* with `from_zmatrix` on a regular
  six-ring declared as the chain 0-1-2-3-4-5 (bonds 1.39 Å, angles 120°,
  dihedrals 0°): raising bond 0-1 to 1.43 Å moves the closing bond 5-0 to
  1.37044 Å (−0.0196) and the angle 1-0-5 to 118.552° (−1.45°), and leaves
  the other four tree bonds at 1.39. The issue's numbers reproduce. The
  reporter's proposed line, for the Z-matrix part of the Part 1 chapter:
  "A ring in a Z-matrix body is described by a spanning tree. The bonds
  that close the ring are not internals. Refining a tree bond of the ring
  also moves the closing bond and the ring angles. If the closing bond must
  stay near a value, restrain that atom pair." **It is untrue until
  WP-1814's Z-matrix bodies land**: on `a86dcf9d4` no internal refines, and
  PR #1510 (WP-1814 chunk C1, open) gives a Z-matrix body no structural
  restraint refusal, which is what makes the restraint advice hold. So the
  line lands with or after WP-1814's Z-matrix chunk, and WP-1814's
  acceptance test records the tree it used (the reporter's plan on the
  issue).

- **2026-11-06, from the issue triage (issue #1417): the manual owes a
  paragraph on where a body's origin goes. Ruled by Yue, 2026-11-07: docs
  only.** A body's origin is the point it turns about.
  `body_from_atoms(phase, labels, name, *, origin=None)` puts it at the atoms'
  unit-weight centroid, and `origin` may also be an atom label or a fractional
  point (`crystallography/bodies.py`); `add_body(..., centre=True)` centres the
  template the same way. Moving the origin by d is an exact
  reparameterisation of the pose (t′ = t − [d]×ω, ω′ = ω). So χ², every atom
  and every atom esd are unchanged. Only the origin's own esds and its
  correlations with the rotation move. *Checked against the tree at
  `a84379aac`:* both functions and both defaults are as the issue says.
  The reporter fitted one body with its origin at seven points on three
  patterns (rietx `ba3719f06`; not reproduced here). Distance of each origin
  from the decorrelating point P_opt, and the largest origin–rotation
  correlation:

  | origin | acridine IX, measured (COD 2242872) | acridine, synthetic neutron | Br-acridine, synthetic X-ray |
  |---|---|---|---|
  | unit centroid (default) | 0.50 Å, 0.25 | 0.23 Å, 0.20 | 3.8 Å, 0.59 |
  | Z² (X-ray) or b² (neutron) weighted centroid | 0.49 Å, 0.24 | 0.16 Å, 0.08 | 0.2 Å, 0.24 |

  Across the arms χ² agreed to 0.002, atoms to 2.4e-6 Å and atom esds to 5e-5
  relative; no convergence effect was seen. **The ruling.** The paragraph says
  the default is fine for light atoms, and that when a heavy atom dominates
  and the origin's esd will be quoted, the caller passes its Z²- (X-ray) or
  b²- (neutron) weighted centroid to the existing `origin=`, with the few
  lines that compute it. Declined until a user quotes a rigid body's origin
  esd, or a badly placed origin is measured to slow convergence: a reported
  P_opt, an `origin_weights=` argument, and a label-list `origin=`. Grounds:
  the origin is a parameterisation choice that moves no atom, esd or χ²;
  `origin=` already takes the weighted or subset centroid as a point; GSAS-II
  5.8.4 places a residue body's origin on a reference atom or the unit
  centroid and reports nothing about it (`GSASIIconstrGUI.py:3728-3753`,
  checked), TOPAS and FullProf not checked. Quote no number in the manual
  before reproducing one row of the table (acridine IX is WP-1806's fixture).
  The ruling folded here a separate WP the triage branch had filed for the
  three-part proposal, before any of it merged.

- **2026-10-23, from [1810](1810-hydrogens-riding-on-a-body.md) (closed): the
  riding hydrogens have no user-facing call yet.** `RigidBody.riding` and
  `crystallography/riding.py` landed in PR #955, and a CIF write carries
  `_atom_site_refinement_flags_posn` and `_atom_site_calc_flag`. But nothing
  under `src/` calls `set_riding_lengths`, so a user reaches riding H only by
  building the body by hand. The verb, its `.rxt`/GUI surface and its skill row
  belong with this WP's body fields, which `api_surface_deferred.txt` already
  parks.
- **2026-10-11, from WP-1920 (closed, PR #906): `api-bodies.md` need not wait
  for this WP.** The maintainer ruled that the first pull request documenting
  the rigid-body classes creates their index, one `TECHNIQUES` entry in
  `docs/skill/make_api_index.py`. PR #888 (WP-1809) may be that PR. The
  `TECHNIQUE_FIELDS` comment now says so. Every `api*.md` has one ceiling,
  39 000 B, so a new index edits no list in `tests/skill_caps.py`.

- **2026-10-11, from WP-1808 (closed, #823): two torsion surfaces are this
  WP's.** `BodyTorsion` and its fields sit in `tests/api_surface_deferred.txt`
  with WP-1812 as the reason, so the partition task moves them too. A fit
  reports the twist increment, which is 0 after the last commit, with the
  angle's esd, and the composed angle lives only in the record. Whether
  `RefinementResult` carries the composed angle with that esd was left to this
  WP in #823's question 3. A torsion already round-trips through the textdoc
  (`test_a_body_with_a_torsion_round_trips_through_json_and_textdoc`).

## Non-goals

- Fragment file formats (WP-1813).

## Tasks

- [ ] Textdoc: a body block and its round trip
- [ ] Skill: the generated per-shape reference and its routing row
- [ ] Manual: Part 1 chapter, Part 2 frame section
- [ ] Manual: the origin paragraph in the Part 1 chapter (issue #1417, Ruled by
      Yue 2026-11-07; Inherited)
- [ ] Manual: the ring line for Z-matrix bodies (issue #1508; Inherited),
      once WP-1814's Z-matrix bodies land
- [ ] GUI: a body shown in the parameter and structure panels

## Acceptance

- The textdoc round trip reproduces a body.
- `tests/api_surface.py`'s partition is green.
- The skill caps (`tests/skill_caps.py`) pass without raising `api.md`'s.

## References

- Issue #561; PR #596.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.
