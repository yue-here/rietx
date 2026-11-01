# WP-1810 — hydrogens riding on a body, CIF flags

Milestone: rigid-bodies · Status: ✅ 2026-10-23 — a body's riding H at SHELXL's X-ray or ITC's neutron lengths, and the CIF flags on write (PR #955)
Depends on: 1805; 1806 soft (a real case to show it on)

## Goal

A body's H atoms ride with it, at an X–H length set by bond class and radiation, and a
CIF write records which atoms were constrained. This is chunk R9 of issue #561, sized S.

## Context

- `crystallography/riding.py` holds the X–H lengths by bond class and radiation. The
  neutron template's C–H differs from the X-ray one by the tabulated offset, and a joint
  fit takes the neutron lengths.
- `_atom_site_refinement_flags_posn` writes `G` for body atoms, `R` for riding H, and
  `calc` where computed. *Decided 2026-10-15:* a riding H inside a body is `R`, not
  `GR`. `R` is SHELXL's convention for a riding H, and its parent's own `G` already
  says the parent came from the group.
- It touches no v1.6 file. #596 made WP-1806 a hard dependency. Nothing here reads
  WP-1806's data, so it is soft.
- An outside branch builds it (`0d28c964`, on #561, 2026-10-06). That file reads back,
  but the reader does not rebuild a body from the flags.

## Non-goals

- Riding H on free atoms (issue #759).
- Rebuilding a body from CIF flags on read.

## Tasks

- [x] Riding H lengths by class and radiation; `RigidBody.riding`
- [x] The CIF flags on write
- [x] Tests (the acceptance below)
- [x] Skill: none expected; say why at handover

## Acceptance

- The flags are written, and the file reads back. *Decided 2026-10-15:* reworded
  from "a CIF round trip keeps the flags". A read does not rebuild a body (a non-goal),
  so a read → write does not keep them, and no `Atom` field carries them through.
- The neutron and X-ray templates differ by exactly the tabulated offset.
- A class with no tabulated length is refused.
- A phase with no body writes neither column.

## References

- Issue #561; PR #596.

## Handover log

- **2026-10-23** — closed by the maintainer's word. A rigid body now carries its
  riding hydrogens at a length set by bond class and radiation, and a CIF written
  from a phase with a body says which atoms the group or a riding rule placed.
  Nothing was left open. All four tasks and every acceptance line were met at
  `719a0a74`, and there was no `### Inherited`. *Next:* nothing owed here. The
  user-facing call (`set_riding_lengths` reached from `src/`) is WP-1812's,
  which already parks the body fields in `api_surface_deferred.txt`.
- **2026-10-15** — PR #955 (outside contributor) merged as `719a0a74`.
  All four tasks landed. `RigidBody.riding` carries the riding H at SHELXL's
  X-ray lengths or ITC Vol. C Table 9.5.1.1's neutron means, and a joint fit
  takes the neutron ones. A phase with a body writes
  `_atom_site_refinement_flags_posn` and `_atom_site_calc_flag`. Schema is
  0.58. Round 2 answered round 1's three items. The table does carry N–H rows,
  so `NH` now has the neutron length 1.009 Å (H—N(3)). The refusal path keeps
  its test by patching the entry to `None`, because no class lacks a length
  today. The skill takes no row, since no diagnostic code landed. Nothing
  under `src/` calls `set_riding_lengths` yet: the user-facing call is
  WP-1812's, where `api_surface_deferred.txt` already parks the body fields.
  The merge was gated in the stack on tree `2268e525` (counts in WP-1343's
  entry of today). *Next:* close this WP at the maintainer's next handover.
- **2026-10-15** — from the PR review (PR #955): @yue-here answered the PR's two
  questions. The round-trip acceptance is reworded to what a read can keep, and a riding
  H inside a body is flagged `R`. Both are recorded above, where a session working this
  WP reads them. Round 1 at `85fff805` carries the answers and asks for three things
  before merge: a rebase (`main`'s `SCHEMA_VERSION` 0.57 is now WP-1960's, so this bump
  becomes 0.58), a `docs/releases/1.10.0.md` note for `RigidBody.riding` and the two
  CIF columns, and one account of whether ITC Table 9.5.1.1 has an N–H row. Its tests
  ran green on the earlier head; the merged tree runs on the rebased one. *Next:*
  #955's round 2.
- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal, with WP-1806
  made a soft dependency.
