# WP-2217 — Records of what was read in another program's source

Milestone: unscheduled · Status: 🔄 2026-11-13 — claimed by @yue-here
Track: The repo's own process
Depends on: —
Priority: P4 2026-11-13 — bookkeeping: changes no number and no decision, only which evidence a reader can check

## Goal

Every record that cites another refinement program says whether the claim rests on that
program's source, its manual or a run. A contributor who reads no foreign source can then use
the manual-level evidence and skip the rest.

## Context

Michael Gaultois (mustachefeeling) sent a note on 2026-11-13. His agents never open another
refinement program's source, permissive ones included. They use papers, manuals, official docs
and black-box runs. That rule binds only their work. rietx's rule is set by licence (root
CLAUDE.md § Licensing, `ATTRIBUTION.md`). Source is read as specification where the licence
permits it: GSAS-II (Argonne royalty-free, grant-back clause), MAUD (BSD-3), EasyDiffraction and
cryspy (BSD-3 / MIT). It is never read for GPL/LGPL programs, closed programs or ChimeraX.
Code is ported only from permissive sources, with attribution, and only SLEEF has been. The
maintainer confirmed that stance in this session (2026-11-13) and asked for the records to be
tightened.

The note found five places where the records fall short. Line numbers are at `2086ed273`.

1. `ATTRIBUTION.md:242-249`. CrysPy reads as a "reference for pure-Python Rietveld mathematics",
   MAUD as a "reference for texture / residual-stress methods" and EasyDiffraction as an
   "architecture reference". `docs/practice.md:9-13` and WP-2003 cite their source files as
   evidence of behaviour. The GSAS-II row (`:241`) already has the right wording.
2. `docs/practice.md:4` marks a claim "checked (read in the source or manual)". A reader cannot
   tell which. 213 lowercase and 6 capitalised "checked" in a 126 KB file. `:13-14` points
   public readers at "the maintainer's memory", which they cannot open.
3. `docs/practice.md:625` (§ A volume window from the formula) reads "Checked by the maintainer
   in the sources on 2026-10-24 (#1121)". It entered under mustachefeeling's identity in
   `55b6c3c63`, reworded from the maintainer's comment. His agent read no source.
4. WP-2208's stage order (`src/rietx/strategy/staged.py:193-202`, practice.md § A stage that
   fixes a parameter, rietx row) rests on "as GSAS-II", whose evidence is
   `GSASIIscriptable.py:2085-2106, :2166-2230`. GSAS-II's own scripting docs
   (`docs/source/GSASIIscriptable.rst` § Refinement recipe, read at 5.8.4 for this WP) do not
   state the order of `set` and `clear`. They imply that flags carry, since the recipe example
   clears `LeBail` in a later step than the one that set it. WP-2208 has its own reason for the
   order: a stage frees a broad glob and fixes a narrow one, and only free-then-fix lets the
   narrow fix act.
5. `src/rietx/_audit.py` has 22 evidence strings with GSAS-II `file:line` citations. Under the
   licence rule these are legitimate. The carry default's grounds (`:4925-4927`) rest on
   `Copy2Next`, which GSAS-II's SeqRefine tutorial documents.

`src/rietx/crystallography/spherical_harmonics.py:20` names coefficients after GSAS-II's
C(l, n). A naming convention is a concept, so no change.

The tier of each rule this WP adds: none. It changes evidence text and adds no flag, threshold
or automatic action.

## Non-goals

- Replacing source citations that are legitimate under the licence rule. A doc citation is added
  only where a row's claim is the kind a reader would want to check without the source.
- Mike's own records. His agents' rule is theirs.
- Any change to behaviour or a stored format.

## Tasks

- [x] `ATTRIBUTION.md`: a paragraph opening § Open-source software stating the reading rule by
  licence; the CrysPy, MAUD and EasyDiffraction rows say "behavioural reference, source read as
  specification, no code ported".
- [x] `docs/practice.md`: the legend splits "checked" into "checked (source)" and "checked
  (manual)" (docs, help pages and tutorials count as manual); every occurrence relabelled; the
  memory pointer replaced by the public versions and tags already given.
- [x] `docs/practice.md` § A volume window from the formula: attribute the source check to the
  maintainer's #1121 comment, and say the entry was written from that comment.
- [x] Stage order: `staged.py`'s `turn_off` comment and practice.md's rietx row ground the order
  on free-then-fix, with GSAS-II's source as agreement and its docs' silence noted.
- [x] `_audit.py` carry row: cite the GSAS-II SeqRefine tutorial for `Copy2Next` once its wording
  is checked.
- [ ] Tests: `tests/test_docs_consistency.py`, `tests/test_audit_table.py`, ruff.
- [ ] Skill: none. Nothing here changes how an agent drives rietx.

## Acceptance

`grep -c -w 'checked' docs/practice.md` counts only labelled occurrences (each followed by
` (source)` or ` (manual)`, or inside the legend), and

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_docs_consistency.py tests/test_audit_table.py
.venv/bin/python -m ruff check src tests examples
```

pass.

## Handover log
