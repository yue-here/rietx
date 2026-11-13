# WP-2217 — Records of what was read in another program's source

Milestone: unscheduled · Status: ✅ 2026-11-13 — PR #1561
Track: The repo's own process
Depends on: —

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
- [x] Tests: `tests/test_docs_consistency.py`, `tests/test_audit_table.py`, ruff.
- [x] Skill: none. Nothing here changes how an agent drives rietx.

## Acceptance

`grep -c -w 'checked' docs/practice.md` counts only labelled occurrences (each followed by
` (source)` or ` (manual)`, or inside the legend), and

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_docs_consistency.py tests/test_audit_table.py
.venv/bin/python -m ruff check src tests examples
```

pass.

## Handover log

- **2026-11-13** — The records now say which claims about another program rest on reading its
  source. `ATTRIBUTION.md` states the reading rule by licence, and the three rows that understated
  their use (CrysPy, MAUD, EasyDiffraction) now say their source was read as specification.
  `docs/practice.md` marks each check as made in the source, the manual, or both, so a contributor
  who reads no foreign source (Michael Gaultois's agents) can use the manual-level rows and skip
  the rest. Nothing a fit computes moved.

  *Done.* No open WP owned this (a `docs/wp/README.md` search for attribution, practice and
  licence found none). ATTRIBUTION paragraph and three rows. practice.md: legend with three
  tokens, "checked (source)", "checked (manual)" and "checked (source and manual)"; 192 marks
  relabelled (87 source, 101 manual, 4 both, 0 undecidable); the pointer to the maintainer's
  memory replaced by a sentence naming which programs' source was read; the volume-window
  section says the GSAS-II row is the maintainer's #1121 check, written up by a contributor who
  read no source; § Limits a control file declares opens "Surveyed" instead of "Checked"; the BGMN
  extinction mark is "inferred from the binary's keyword table". The carry row in `_audit.py`
  cites GSAS-II's SeqRefine tutorial (`SequentialTutorial.htm` at GSAS-II-tutorials `924e9eb8`,
  wording read this session: "Copy results to next histogram?", unchecked after a successful run,
  otherwise each histogram starts from its own parameters). `staged.py`'s `turn_off` comment and
  practice.md's rietx row ground the order on free-then-fix. GSAS-II's `GSASIIscriptable.rst`
  § Refinement recipe was read at 5.8.4 and does not state the order.

  *Generality* (judge's verdicts, condensed by row): carry row **holds** for this edit, but is
  "weak on the default half of the citation". The tutorial tells the reader to tick the box and
  says what happens unticked, but never states the default. Author's answer: the row now names
  `GSASIIobj.py:22` (checked in source) beside the tutorial for the default. The judge also noted,
  as outside this edit: a standing tension between `ambiguity=1` and a named dissenter (ruled by
  the maintainer 2026-11-03, C9 q1); MAUD's and Profex's batches dissent too, but the row names
  GSAS-II alone; no field records which entries were carried.

  *Not done, on purpose.* The other 21 GSAS-II `file:line` citations in `_audit.py` stay: they are
  legitimate under the licence rule, and practice.md's marks now say which kind they are.
  `spherical_harmonics.py`'s C(l, n) names are a convention, so a concept: no change.

  *Gotchas.* MAUD rows with no citation (practice.md, around old lines 27, 80, 315, 328, 341, 368)
  were marked source because MAUD was read at its tag. Some may have come from its help text.
  GSAS-II rows with no citation were marked source by the same rule. `/code-review` was skipped:
  the two `.py` changes are a comment and a string literal.

  *Measured.* Lanes, from `session_usage.py lanes`:

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | redo | lane $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|
  | practice-checked | 30 | 28 | 176K | 98K | 0K of 48K | 5 | 6K | 0 | 2.21 | +0.28 |

  Kept items: attribution-rows (est 4, ran 5), volume-window (2, 5), stage-order (5, 5),
  audit-carry (6, 5), all at 176K. Baseline, selective policy, 0K-300K peak: 72 sessions, -4 %.
  Tests: `tests/test_audit_table.py` 23 passed; `tests/test_docs_consistency.py` 26 passed after
  this entry ([dev] venv, macOS arm64). No test added.

  Next: none in this WP. Mike may want the practice.md legend quoted to his agents. WP-2208's
  Inherited carries its one wording follow-up.
