# WP-2132 — the Estimation page splits before it grows

Milestone: unscheduled · Status: 🔄 2026-11-28 — the four split questions settled by Claude on 2026-11-16 (handover log); the split, tasks 3-6, is next
Track: The repo's own process
Depends on: —
Priority: P3 2026-11-09 — no reader sees a defect yet, but the next sentence added to the Theory tab's Estimation chapter fails the page contract, and two open PRs already edit that page; the workaround is trimming text that is right

## Goal

`docs/docs/theory/estimation.md` is two Theory chapters, each with room to grow under the page
contract's size cap, and every link into the old page lands on the section it meant.

## Context

**Source.** Issue #1495 (mustachefeeling, 2026-11-09), a follow-up to the maintainer's review of
PR #1383, where that PR dropped a display equation to stay under the cap.

**The cap.** `tests/test_manual.py` holds every manual page to the page contract (WP-1978).
`PAGE_CHAR_CAP = 50_000` applies to the page's built Markdown twin (`<page>.html.md`, written by
`docs/markdown_twin.py` beside each HTML page), never to the source. The twin carries the rendered
equations and anything the source includes, so the source's length is no guide to the headroom.
`test_every_page_has_a_twin_that_keeps_the_contract` reads `len()` of each twin and fails a page
over the cap with "split it". The contract also wants each page to have one H1, an answer sentence
under it, and no section opening on a back-reference ("as above").

**Measured at `9979cee7c`**, building the manual as that test does
(`python -m sphinx -W -q -E -b html docs/docs <out>`) and reading `len()` of each of the 129 twins:
`theory/estimation.html.md` is 49 998 characters, 2 under the cap. The issue's number reproduces
exactly. The source is 45 843 characters.
*Superseded in part, 2026-11-16 (`bc77a934e`):* 132 twins; this one is 49 940 (60 to spare), the
source 45 647. WP-1419's `da3a2d301` trimmed four wordings after #1108's `{cite}` on another page
renumbered Sphinx's global citation ids and took this twin 48 over the cap with its source unedited.

**Two open PRs edit the page**, both mustachefeeling's: PR #1383 (WP-1998) adds a net 193 source
characters to it, and PR #1473 (WP-2080) changes 150 characters for 150. Whichever lands first takes
the room. A split made while they are open conflicts with both. So the first task reads their state.
*Superseded in part, 2026-11-16:* #1383's head (`fa35f671d`) now adds 1 twin character and #1473's
(`eca5fafbc`) none, and PR #1332 is a third that edits the page (−7). Task 1's line has the state.

**Where a split could fall**, source characters per H2 at `9979cee7c`:

| Section | Characters |
|---|---|
| Objective and weights; Agreement statistics; Structure agreement indices; The effective observation count | 5 898 |
| Esds and the Bérar-Lelann inflation | 7 712 |
| Esds of derived quantities; A derived esd describes one basin; An interval for a parameter on its bound; A moment angle at a direction the symmetry fixes; A scale and a B the range cannot separate | 16 812 |
| Staged strategy and series; Solvers; Convergence; The fp64 floor; From fit to report; Which parameter to free next | 15 125 |

The last group reads as one chapter on how the fit is solved and steered, and the middle group as one
on esds where the curvature misleads (the second and third rows). *Corrected 2026-11-16:* only the
second choice leaves both halves near 23 000: moving the esd rows keeps 21 123 source characters and
moves 24 524, and moving the last group keeps 30 522 and moves 15 125 (first row 5 840 now). Which
boundary, and the new page's title, is this WP's first decision. The Theory tab's titles are short
nouns (`Estimation`, `Profiles`, `Background`), so the title should be one too.
*Settled by Claude, 2026-11-16:* the esd rows move, under the title "Esds and intervals" (handover
log, 2026-11-28).

**What a move breaks.** 27 links from other manual pages name a section of this page by fragment,
over 13 of its 16 sections, and 9 places under `src/` cite `theory/estimation`. Sphinx's `-W` build
fails a broken in-manual link. Nothing checks a docstring's link, so those 9 are checked by grep.
*2026-11-16:* 28 fragment links from 19 files, over the same 13 sections; still 9 under `src/`.
`docs/docs_versions.py`'s `RETIRED` maps the old tree's `estimation` to `theory/estimation` with no
fragment, so it keeps working whichever half keeps the old file name. `theory/index.md` lists the
chapters twice (a sentence each, and the toctree), and both take the new page. The Theory tab's
own guards (`tests/test_manual.py`: every displayed equation carries a `*Source:*` line, every bib
entry is cited) move with the equations.

**The siblings.** The same build measured three Reference twins within 20 characters of the cap, as
the issue said: `reference/indexing` (49 994), `reference/parameters` (49 986) and
`reference/refinement` (49 985). A fourth the issue did not name is `reference/series` (49 919, 81
to spare). `parameters` is generated from `src/rietx/help.py` by
`docs/reference_pages.py`, so whoever adds a help entry meets it. `indexing.md` (49 073 source
characters) and `refinement.md` (49 757) are hand-written, so the issue's "the Reference ones are
generated" holds for one of three. Open WPs already plan around the cap on their own pages: WP-2024,
WP-2025 and WP-2027 for the API pages, WP-1335 and WP-1931 for `reference/refinement`. This WP
splits only the Theory page.
*Superseded in part, 2026-11-16 (`bc77a934e`):* `reference/parameters` is no longer near the cap
(WP-2087 split the parameter map; 27 316). The four within 100 are `reference/indexing` 49 994,
`reference/refinement` 49 987, this page 49 940 and `reference/series` 49 924, which PR #1473 splits
(45 502 merged).

**The class.** Five pages sit within 100 characters of the cap (*superseded, 2026-11-16:* four, per
the note above), and each is found by the session whose addition fails. The
skill's sizes (`tests/skill_caps.py`) answer the same problem with a ceiling per file plus a budget
below it that fails only growth, so concurrent PRs land in the gap. Whether the manual wants that is
a question for this WP to measure and report, never to build unasked.

**Tier.** None: a page split adds no heuristic.

## Non-goals

- Splitting the three Reference pages. Their owners are named above.
- Raising `PAGE_CHAR_CAP`. WP-1975 § F8 set it as the length past which a page is two pages.
- Rewriting the chapter's content. Text moves whole, apart from the answer sentence each half needs
  and any section opening that reads as a back-reference once it leads a page.

## Tasks

- [x] Read the state of PR #1383 and PR #1473. Split after both land or close, or agree the order with their author on the PR.
  2026-11-16: both open, neither approved. #1383 (head `fa35f671d`, last push 2026-11-09, one maintainer review "commented") conflicts with main in `src/rietx/schemas/common.py` and `tests/test_magnetic.py`; its estimation hunk merges clean. #1473 (`eca5fafbc`) is mergeable and green. Merged into main alone or together they move this twin by +1 and 0. The order is the maintainer's call (handover entry).
- [x] Re-measure every twin on a fresh build (`python -m sphinx -W -q -E -b html docs/docs <out>`, then `len()` of each `.html.md`), since the numbers above move with every merge.
  2026-11-16 at `bc77a934e`: 132 twins, none over; the Context's dated notes carry the numbers, the handover entry the table.
- [ ] Split the page along one H2 boundary: the new chapter's file, its H1 and answer sentence, both lines in `theory/index.md`, and the old page's answer sentence narrowed to what it keeps.
- [ ] Move every inbound link: the 27 fragment links in the manual (the `-W` build finds a miss) and the 9 `theory/estimation` citations under `src/` (grep finds them).
- [ ] Report the headroom of every twin after the split, and whether a growth budget below the cap, on `tests/skill_caps.py`'s pattern, is worth proposing. Propose; build nothing.
  2026-11-16: no budget and no headroom report, settled by Claude (handover log, 2026-11-28); what remains is the after-split headroom.
- [ ] Tests: `tests/test_manual.py` and `tests/test_manual_api.py` green on the split tree.
- [ ] Skill: none. The skill does not cite this page (grep at `9979cee7c`).

## Acceptance

```sh
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_docs_consistency.py
```

## References

- Issue #1495; PR #1383 and its review; PR #1473; WP-1978 (the page contract); WP-1975 § F8 (the cap).

## Handover log

- **2026-11-28** — post-merge bookkeeping for PR #1578 (maintainer side, ghostshift runner; PR
  #PRNUM). PR #1578 merged today as `9eb1e3352`. It carried the 2026-11-16 measurement and the three
  questions in the entry below. All of them, plus the budget, were settled in the maintainer's
  decisions walk on 2026-11-16 and posted on #1578 on 2026-11-17. Claude settled each call. None is
  a ruling of Yue's, and Yue may reverse any of them. The split can now be built. Mike said on #1578
  (2026-11-18) that he will build it as its own PR.

  *Settled* (the four calls, as posted on #1578):
  - **Boundary.** The esd rows move, from "Esds and the Bérar-Lelann inflation" through "A scale and
    a B the range cannot separate". Settled by Claude under the 2026-11-16 measurement: halves of
    21 123 and 24 524 source characters, against 30 522 and 15 125 for the solve-and-steer cut.
    Alternative: the solve-and-steer rows.
  - **Title.** "Esds and intervals". Settled by Claude under rietx convention: the manual says "esd"
    throughout. Alternative: "Standard uncertainties", the IUCr term.
  - **Timing.** Split now, without waiting for #1383 and #1473. Settled by Claude under the
    2026-11-16 measurement: #1383 moves this twin by +1 character and #1473 by 0, so their rebase
    is a hunk move. Alternative: wait for both, as task 1 said.
  - **Budget.** No growth budget. Settled by Claude under the smallest-thing rule. The only recent
    overflow came from citation renumbering, which a source-delta budget cannot see, and the cap
    test already catches an overflow. Alternative: option A, a headroom report with no gate.

  *Checked against `origin/main` at `0f4894d58`:* the page is not split yet (16 H2s, 45 805 source
  bytes). #1383 and #1473 are both still open. No checklist item landed with #1578, so none is
  ticked.

  Next: task 3 on the esd-row boundary under the title "Esds and intervals". Then task 4, recounting
  the links first (28 fragment links and 9 `src/` citations on 2026-11-16). Then task 5's
  after-split headroom table, and task 6's tests. Mike's claim holds the WP.

- **2026-11-16** — measured and reported, nothing split (ghostshift runner; PR #1578). The page is
  not about to break from the two PRs the WP was waiting on: on current main it has 60 characters to
  spare, and #1383 and #1473 merged in, alone or together, move it by one character. What does
  threaten it is growth nobody makes on this page: a citation added to another Theory page renumbered
  Sphinx's citation ids and took this twin 48 over the cap on 2026-11-10 with its source unedited,
  so it was trimmed a second time (WP-1419's `da3a2d301`). The split still waits on the maintainer:
  which of the two boundaries, the new title, and whether to go before #1383 lands. A growth budget
  on the skill's pattern is not worth building as it stands; the evidence and three options are
  below, for the maintainer to choose.

  *Measured* (`[dev]` venv, Python 3.12, Linux under WSL2, sphinx 9.1.0; the build the test runs,
  `python -m sphinx -W -q -E -b html docs/docs <out>`, then `len()` of each twin; 27-34 s a build, 430 MB):
  - Main `bc77a934e`: 132 twins, none over. Headroom: `reference/indexing` 49 994 (6),
    `reference/refinement` 49 987 (13), `theory/estimation` 49 940 (60), `reference/series` 49 924 (76),
    `reference/parametric` 49 031 (969), `reference/instrument` 48 801, `reference/gui-guide` 48 407,
    `theory/parameterisation` 47 550, `start/tutorials/03_peaks_indexing_lebail` 47 053; median 13 884.
    Twins over 49 000: 5; over 48 000: 7; over 45 000: 9; over 38 000: 17.
  - Each open PR touching the four near-cap pages or `src/rietx/help.py` (25: #1043 #1262 #1285 #1286
    #1332 #1372 #1383 #1388 #1405 #1410 #1422 #1472 #1473 #1475 #1477 #1480 #1482 #1493 #1510 #1532
    #1548 #1549 #1562 #1566 #1567), merged into main one at a time with `git merge-tree` and built.
    18 merge clean and build green; none of the 18 takes any twin over the cap or adds to a near-cap
    twin (#1472 `indexing` −24, #1332 `estimation` −7, #1473 splits `series` to 45 502 with a new
    `series-ladder` page). The largest growth any of them puts on an existing page is 3 935
    (`reference/extinction`, #1286). Seven conflict with main and were not built: #1262 and #1383 in
    `schemas/common.py` and `tests/test_magnetic.py`, #1480 and #1548 in the skill's `api.md`
    copies, #1562, #1566 and #1567 in `docs/milestones/v1.12.md`. Three of the seven edit a
    near-cap page: #1383 adds 1 to the `theory/estimation` twin (its estimation hunk alone, the
    Context's dated note), #1262 nets +1 source character on `reference/refinement` (+748/−747) and
    #1567 −21 on `reference/indexing`, read from `gh pr diff`, their twins not built.
  - Worst 24 hours of source growth on main's first-parent merges, 2026-10-16 to 2026-11-16, bytes:
    `theory/estimation` 5 930 (2026-10-20), `reference/refinement` 6 138 (10-22), `reference/indexing`
    2 906 (10-25), `reference/series` 910 (10-26).
  - Source characters per H2 now: preamble 158; first row 5 840; Bérar-Lelann 7 712; derived-esd rows
    16 812; solve-and-steer rows 15 125. Twin/source ratio 1.094, so the esd split gives twins near
    23 100 and 26 800, the solve split near 33 400 and 16 500.

  *Growth budget, the evidence.* `tests/skill_caps.py` sets its gap at twice the worst day close to
  a cap, and fails a change that grows a file past the budget against the change's base. Three
  things differ here. (1) The size is a build product: the base's twin needs a second build, or the
  budget reads source deltas, which cannot see the citation renumbering above, one of the two cap
  failures on record (the other, #1383 dropping an equation, a source budget would see). (2) Twice
  this month's worst day is about 12 000 characters, a budget near 38 000 that would close 17 pages
  today. The worst days are source bytes and the cap counts twin characters (ratio 1.094, less
  where `é`, `−` and `σ` take two bytes or more), a difference of about 10 % that leaves the
  argument standing. (3) The concurrent load it guards against is about one character: of the 18
  open PRs that build, none grows a near-cap twin; of the seven that conflict, #1383 adds 1 to this
  twin, #1262 nets +1 source character on `reference/refinement` and #1567 −21 on
  `reference/indexing` (not built).
  Options, none built: **A** no budget, plus a headroom report (`python -m tests.<name>`, the skill's
  report without its gate) and the five nearest pages named in the cap test's failure message;
  **B** a source-delta budget on the skill's pattern, stdlib and cheap, blind to non-local growth;
  **C** a twin budget against a committed size snapshot, a stored file someone must regenerate.
  The runner would choose A, since it is the only one whose cost fits what was measured.

  *Questions for the maintainer.* (1) Which boundary: the esd rows (Bérar-Lelann through "A scale
  and a B …", contiguous, halves near 23 000) or the solve-and-steer rows; and the new page's title.
  (2) Split now and let #1383 and #1473 rebase (their hunks are 4/5 and 2/2 lines and follow their
  section to whichever page), or wait for both as the first task says. #1383 is mustachefeeling's,
  conflicted on unrelated files, and unpushed since 2026-11-09. (3) A, B, C or nothing for
  the budget.

  *Gotchas.* `git merge --no-commit` still wants a committer identity; `git merge-tree --write-tree`
  then `git read-tree --reset -u` builds a merged tree without one.

  Next: answer the three questions; then task 3 on the chosen boundary, task 4's 28 links and 9
  citations, task 5's after-split headroom, task 6's tests.

- **2026-11-09** — created, from the 2026-11-09 issue triage (issue #1495; PR #1501). Checked against the tree at `9979cee7c`: built the manual and read every twin's length, and the issue's 49 998 for this page reproduced exactly, with a fifth page near the cap (`reference/series`, 49 919) that the issue did not name; no open WP owns it: every WP citing `theory/estimation` is closed (WP-2060 last trimmed the page, ✅ 2026-11-07), WP-1986 (🔄) is open only for guide 18, and the open WPs that plan around the cap own Reference pages. Next: read the two open PRs' state, then split.
