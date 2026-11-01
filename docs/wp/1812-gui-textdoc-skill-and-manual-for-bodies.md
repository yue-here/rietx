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
- [ ] GUI: a body shown in the parameter and structure panels

## Acceptance

- The textdoc round trip reproduces a body.
- `tests/api_surface.py`'s partition is green.
- The skill caps (`tests/skill_caps.py`) pass without raising `api.md`'s.

## References

- Issue #561; PR #596.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal.
