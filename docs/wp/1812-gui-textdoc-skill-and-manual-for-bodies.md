# WP-1812 — GUI, textdoc, skill and manual for bodies

Milestone: rigid-bodies · Status: 🔄 2026-11-17 — origin paragraph in PR #1661; textdoc, skill, Part 1 chapter, ring line and GUI left
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
- [x] Manual: Part 2 frame section (landed with WP-1805, `1bc0c2e90`: Theory
      tab, parameterisation § Rigid bodies, equation `par-body` with the closed-form M)
- [ ] Manual: Part 1 chapter
- [x] Manual: the origin paragraph (issue #1417, Ruled by Yue 2026-11-07),
      placed in the Theory tab's § Rigid bodies as "Placing the origin" until a
      Part 1 chapter exists
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

- **2026-11-17** — ghostshift runner, manual only (PR #1661). The manual now
  says where a rigid body's origin goes. Moving the origin changes no atom,
  no atom esd and no χ²; it changes only the origin's own esds and their
  correlation with the rotation. The default centroid serves light atoms, and
  a reader who will quote the origin's esd on a body with a heavy atom is shown
  how to pass the Z²- or b²-weighted centroid to the existing `origin=`. No
  code changed, and the rest of the WP (textdoc, skill, Part 1 chapter, ring
  line, GUI) is still open.
  - *Done.* New subsection "Placing the origin" at the end of
    `docs/docs/theory/parameterisation.md` § Rigid bodies: the defaults of
    `body_from_atoms` and `add_body`, the reparameterisation
    t′ = t − [d]× δω (derived here: o′ = o + Exp(δω)·d, linearised), why the
    scattering-power centroid decorrelates, and an executed block on
    acridine IX (`tests/data/cod_2242872.cif`) that builds the body at the
    Z²-weighted centroid, with the b² line for neutrons. `acridine` joined
    `docs/vale/terms.txt` (accept list regenerated). The consumed #1417
    `### Inherited` entry is deleted here, its content now on the page. The
    Part 2 frame section was already in the Theory tab from WP-1805
    (`1bc0c2e90`), so that half of its task line is ticked.
  - *Gotcha: the page is at its size cap.* `tests/test_manual.py::
    test_every_page_has_a_twin_that_keeps_the_contract` caps a page's
    markdown twin at 50 000 characters, and the first draft of this
    subsection put `parameterisation` at 50 568. Cut to about 1 860 source
    characters, the subsection leaves the twin at 49 485, so 515 to spare.
    Mike's open PR #1388 adds 451 characters of source to the same page, so
    the two fit together with about 60 left, whichever merges first. Further rigid-body prose goes in the Part 1 chapter, or the page
    is split. Cut for room, and kept here instead: GSAS-II 5.8.4 places a
    residue body's origin on its first reference atom, or at the unit-weight
    centroid under `Center RB?` (`GSASIIconstrGUI.py:3728` and `:3832-3838`
    in rietx-bench's copy); TOPAS and FullProf not checked.
  - *Kept out, per the ruling.* No number from the reporter's table is
    quoted, since none was reproduced. Still declined until a user quotes a
    body's origin esd or a badly placed origin is measured to slow
    convergence: a reported decorrelating point, an `origin_weights=`
    argument and a label-list `origin=` (issue #1417's three-part proposal).
  - *Settled by Claude (home).* No Part 1 chapter on rigid bodies exists,
    and the Reference pages (`reference/data.md`, `parameter-table.md`) send
    the reader to Theory § Rigid bodies for the technique, so the paragraph
    went there as a `###` subsection with one code block, the Theory tab's
    first. Alternative: a new Guides page, which needs an `examples/guides/`
    script and is the Part 1 chapter task itself. When that chapter is
    written, it links to `theory/parameterisation.md#placing-the-origin` or
    takes the subsection over.
  - *Left.* Textdoc and GUI tasks (visual decisions are Yue's), the skill's
    per-shape reference, the Part 1 chapter, and the #1508 ring line, which
    waits on WP-1814's Z-matrix chunk (PR #1510). Mike's open rigid-body PRs
    (#1388 #1510 #1610 #1655) were not touched.
  - *Measured.* On `[dev]`, macOS arm64, Python 3.12.10: sphinx `-W`
    clean; `tests/test_manual.py`, `test_manual_api.py`, `test_vale.py` and
    `test_docs_consistency.py` 131 passed; CI's Vale steps 0 errors (271
    warnings, none on these lines); ruff clean; `tests.reader_output`
    unchanged. No full suite: the change is prose and one executed block.
  - Next: the Part 1 chapter, once WP-1814's Z-matrix bodies land, so the
    ring line and this subsection can move into it together.

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.
