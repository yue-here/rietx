# WP-2132 — the Estimation page splits before it grows

Milestone: unscheduled · Status: ⬜
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

**Two open PRs edit the page**, both mustachefeeling's: PR #1383 (WP-1998) adds a net 193 source
characters to it, and PR #1473 (WP-2080) changes 150 characters for 150. Whichever lands first takes
the room. A split made while they are open conflicts with both. So the first task reads their state.

**Where a split could fall**, source characters per H2 at `9979cee7c`:

| Section | Characters |
|---|---|
| Objective and weights; Agreement statistics; Structure agreement indices; The effective observation count | 5 898 |
| Esds and the Bérar-Lelann inflation | 7 712 |
| Esds of derived quantities; A derived esd describes one basin; An interval for a parameter on its bound; A moment angle at a direction the symmetry fixes; A scale and a B the range cannot separate | 16 812 |
| Staged strategy and series; Solvers; Convergence; The fp64 floor; From fit to report; Which parameter to free next | 15 125 |

The last group reads as one chapter on how the fit is solved and steered, and the middle group as one
on esds where the curvature misleads. Either leaves both halves near 23 000 source characters. Which
boundary, and the new page's title, is this WP's first decision. The Theory tab's titles are short
nouns (`Estimation`, `Profiles`, `Background`), so the title should be one too.

**What a move breaks.** 27 links from other manual pages name a section of this page by fragment,
over 13 of its 16 sections, and 9 places under `src/` cite `theory/estimation`. Sphinx's `-W` build
fails a broken in-manual link. Nothing checks a docstring's link, so those 9 are checked by grep.
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

**The class.** Five pages sit within 100 characters of the cap, and each is found by the session whose addition fails. The
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

- [ ] Read the state of PR #1383 and PR #1473. Split after both land or close, or agree the order with their author on the PR.
- [ ] Re-measure every twin on a fresh build (`python -m sphinx -W -q -E -b html docs/docs <out>`, then `len()` of each `.html.md`), since the numbers above move with every merge.
- [ ] Split the page along one H2 boundary: the new chapter's file, its H1 and answer sentence, both lines in `theory/index.md`, and the old page's answer sentence narrowed to what it keeps.
- [ ] Move every inbound link: the 27 fragment links in the manual (the `-W` build finds a miss) and the 9 `theory/estimation` citations under `src/` (grep finds them).
- [ ] Report the headroom of every twin after the split, and whether a growth budget below the cap, on `tests/skill_caps.py`'s pattern, is worth proposing. Propose; build nothing.
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

- **2026-11-09** — created, from the 2026-11-09 issue triage (issue #1495; PR #1501). Checked against the tree at `9979cee7c`: built the manual and read every twin's length, and the issue's 49 998 for this page reproduced exactly, with a fifth page near the cap (`reference/series`, 49 919) that the issue did not name; no open WP owns it: every WP citing `theory/estimation` is closed (WP-2060 last trimmed the page, ✅ 2026-11-07), WP-1986 (🔄) is open only for guide 18, and the open WPs that plan around the cap own Reference pages. Next: read the two open PRs' state, then split.
