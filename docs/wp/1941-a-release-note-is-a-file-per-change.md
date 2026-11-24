# WP-1941 — a release note is a file per change

Milestone: unscheduled · Status: 🔄 2026-11-17 — fragments and the join landed (#1645); ROADMAP rule 6 and task 7 are the maintainer's
Track: The repo's own process
Depends on: —
Priority: P3 2026-10-06 — a cost paid in contributor round trips; a rebase covers it every time

## Goal

A PR's release note lands as a file of its own, and the release cut joins the
files into `docs/releases/X.Y.Z.md`. Two PRs that each add a note then never
conflict on it.

## Context

ROADMAP rule 6 stages every break and user-facing addition in the next
release's notes "on the day it lands". Each PR therefore appends a bullet to
one file, `docs/releases/1.7.0.md`, usually at the end of the same section.
Two PRs that append at one place conflict, and only the PR's author can
resolve it. The fix is always to keep both bullets, so each conflict costs a
rebase and a CI round and teaches nothing.

**This reverses a measurement.** WP-1507 fenced fragments out on 2026-09-27
because `releases/1.5.1.md` had changed in 23 PRs and never conflicted. The
traffic has since moved to one outside contributor with many PRs open at once:

- `docs/releases/1.7.0.md` changed in 18 commits between 1.6.0 (2026-10-03)
  and 2026-10-06.
- The 2026-10-06 `/pr-review` run merged seven PRs. Afterwards, 9 of the
  remaining open PRs conflicted with `main`. 6 of the 9 conflicted on the
  release note, and for 4 of them (#743, #749, #754, #788) it was the only
  file.
- During that run's stack replay, three pairs conflicted on the release note
  alone: #743 with #739, #770 with #771, and #771 with #713. #743 needed two
  rebases in one day for this reason only.

**Existing practice.** Two tools do exactly this. towncrier keeps one file
per change in a fragment directory, named `<id>.<type>.md`, where the type
picks the section. `towncrier build` joins them into the release file through
a template and deletes the fragments. scriv does the same with a
`changelog.d/` directory. A stdlib script of a few dozen lines is the
alternative. Compare them on what `1.7.0.md` needs:

- Hand-written prose above the bullets (`## Upgrading`'s opening), which a
  template has to leave alone.
- Nested sections (`### Numbers that move` under `## Upgrading`, then
  `## Foreign files` and `## Indexing`). So the section set is open, and a
  type per section has to be cheap to add.
- Multi-line bullets, with continuation lines indented two spaces.

**Who reads and writes the file today:**

- `docs/RELEASING.md` step 2 writes it at the cut, and the GitHub release
  body is the file verbatim.
- ROADMAP rule 6 stages into it as changes land.
- `ci.yml`'s `PLANNING` pattern lists `docs/releases/`, so a PR touching only
  planning paths runs the docs job. A fragment directory must stay inside
  that pattern.
- CONTRIBUTING.md does not tell a contributor to stage a note. Its one
  mention of release notes is the rule on data that cannot be published.
- The tier of each rule this WP adds: none. It changes how the repository's
  own notes are staged, and nothing in the package decides anything new.

**Decided 2026-11-17 (task 1): a stdlib script, `tests/release_notes.py`.**
Both tools fail the first two needs, the exception the task allows.
towncrier writes its fragments in after one marker (`start_string`), and
scriv at one insert marker. Each renders them through a template from a
configured list of types. Neither places a note under a heading of a file a
person wrote, so `## Upgrading`'s opening line and the paragraphs under
`### Files that change` would move into a template edited every release, or
be lost. The script makes the staged file itself the configuration. Every
heading of level 2 or more is a section, named by its slug
(`### Numbers that move` is `numbers-that-move`), so a new section is one new
heading and nested sections cost nothing. A fragment's multi-line bullets are
copied as written. It is 252 lines with its docstring, and adds no dependency. The tool
facts are from each tool's own configuration pages, read 2026-11-17.

**Decided 2026-11-17 (task 3): keep the staged file as the head.** On
2026-11-17, 24 of the 104 open PRs edit `docs/releases/1.12.0.md`, all from
one fork. Moving its bullets into fragments would make every one of them
conflict once more. Keeping it as the head leaves them conflict-free: an
existing note stays where its PR put it, and the join appends fragments
under the same headings. The two kinds coexist until the 1.12 cut, and the
next release's file starts with headings and no bullets.

## Non-goals

- The milestone record's running narrative (`docs/milestones/vX.Y.md`).
  WP-1507 measured it conflicting once in 33 PRs, and nothing since says
  otherwise.
- Rewriting the notes of shipped releases.

## Tasks

- [x] Pick towncrier, scriv or a stdlib script against the three needs in
      Context. Record the choice and why in this file. A supported tool wins
      unless it cannot hold the hand-written prose or the nested sections.
- [x] The fragment directory and its naming (`<PR>.<section>.md`), inside
      `ci.yml`'s `PLANNING` pattern.
- [x] Move the bullets now in the next release's file (`1.8.0.md` on
      2026-10-10) into fragments, or keep that file as the head the fragments are appended under. Choose the one that leaves
      open PRs a single rebase.
- [x] `docs/RELEASING.md` step 2: join the fragments, then edit the result as
      a reader's document.
- [ ] ROADMAP rule 6 says a change stages its note as a new fragment file,
      and CONTRIBUTING.md gains the same sentence for contributors.
- [x] A test in `test_docs_consistency.py` that every fragment names a known
      section, and that a joined file has no fragment left unplaced.
- [ ] Tell the outside contributor on their open PRs once it lands, since
      every one of them touches the file.

## Acceptance

Two branches that each add a release note merge onto `main` with no conflict,
under the bench's text merge. The joined release file matches the
hand-staged one section for section.

## References

- [1507](1507-the-index-is-read-off-the-wp-files.md): the non-goal this
  reverses, and the measurement it rested on.
- towncrier, https://towncrier.readthedocs.io; scriv,
  https://scriv.readthedocs.io.

## Handover log

- **2026-11-17, review fix-ups** — The PR review's five findings, applied.
  The round trip now always runs on the released `1.11.0.md`, and on the live
  staged file only when it holds two bullets or more. As first opened, 1.12.0.md
  held none, so the old test would have gone red the day after the 1.12 cut.
  The live check now runs the real join. One-bullet notes in a section that
  starts empty join as one tight list, which supersedes "left as designed"
  below. A note with a line of only `-` or `=` (a setext heading or a rule) is
  refused. A note for a section the new staged file lacks is refused with the
  file's name and the remedy, and the README says to rebase after a cut.
  PR #1645.

- **2026-11-17** — A release note can now be a file of its own, and two pull
  requests that each add one no longer conflict. A note goes in
  `docs/releases/unreleased/`, named for the pull request and for a heading of
  the next release's staged notes. The cut joins the files under those
  headings with one command, and a test refuses a note that names no heading.
  Nothing already staged moved: the 24 open pull requests that edit
  `1.12.0.md` keep their edits, and the join appends beside them. Two pieces
  are the maintainer's, because they are ROADMAP's and the PRs' (below).
  PR #1645.

  *Done.* Tasks 1-4 and 6. `tests/release_notes.py` (joins, `--check`,
  `--write`), `docs/releases/unreleased/README.md` (how to name and write a
  note), RELEASING step 2 (join, then edit) and step 11 (the next staged
  file's headings are the sections), and CONTRIBUTING § Release notes, which
  is the contributor half of task 5. The choice and its reasons are under
  Context. No `ci.yml` edit: `docs/releases/` already covers the directory,
  so a PR adding only a note runs the docs job.

  *Measured* (`[dev]`, darwin/arm64, this tree):
  - `tests/test_docs_consistency.py` 30 passed (4 new); `test_skill.py` 174,
    `test_portability.py` 16 and `test_no_stale_name.py` 4 passed.
  - `ruff` clean.
  - With no fragments, the join reproduces `1.12.0.md`, `1.11.0.md`,
    `1.10.0.md` and `1.7.0.md` byte for byte.
  - Acceptance, in a scratch clone: two branches that each add a note merged
    onto a base with exit 0, and the join placed both under `## Changed`. Two
    branches that each append a line to `1.12.0.md` conflicted on it.
  - The round-trip test moves all 16 bullets of the live `1.12.0.md` into
    fragments and joins them back, section for section. It went red when one
    fragment was dropped on purpose.
  - The fast and full suites were not run locally: the branch touches no
    package code, and the ready PR's matrix runs the fast one.

  *Review.* A read-only reviewer found no high-severity bug. Fixed:
  - a fenced `# comment` in a note read as a heading;
  - a note whose code fence never closes was accepted, and it turned every
    later heading into code (now refused);
  - CommonMark's heading indent and closing-`#` rules;
  - an unplaced check that a short note could satisfy by substring;
  - a duplicate heading name raised a traceback instead of a message;
  - RELEASING and CONTRIBUTING wording on patch releases and on the id.

  Left as designed: a section that holds fewer than two bullets gets a blank
  line before each note, so the lists in a release file opened with no
  bullets render loose. The round trip compares each section's blocks as a
  set, not their order. Order is the release editor's in step 2.

  *For the maintainer* (each is a process choice the WP left open):
  1. ROADMAP rule 6, the other half of task 5. Runners do not edit ROADMAP.
     Proposed: after "staged on the day it lands, in the release record and
     the staged notes", add "the notes as a new file in
     `releases/unreleased/` (WP-1941)".
  2. `1.12.0.md`'s staging notice still says to stage under its headings.
     Either way joins correctly. Changing it now edits a file 24 open PRs
     edit, though not at those lines. Changing it at the 1.12 cut costs
     nothing.
  3. The note's id: the README allows any unique name before the PR exists
     (`wp1941`), where the WP says `<PR>`. Keep, or require the number.
  4. Task 7. Every open PR that edits `1.12.0.md` is from one fork, and none
     needs a rebase for this change. Whether new PRs there switch to
     fragments is for that fork to hear on the next PR it opens.
  5. Optional: `/pr-review`'s bookkeeping paragraph could say a note in
     `unreleased/` never conflicts.

  *Next:* item 1, then tick task 5. Item 4 then closes task 7, and the WP
  closes at the 1.12 cut, the first join.

- **2026-10-10** — Recovered and renumbered. The 2026-10-06 commit that filed
  this WP was pushed after PR #796 had merged, so it never reached `main`,
  and 1914 went to another WP on 2026-10-07. Checked against `61422693`: no
  release-note fragments or merge driver exist, and WP-1507 still lists
  fragments as a non-goal. The traffic held. `1.7.0.md` took 40 non-merge
  commits from 2026-10-03 to its cut, and `1.8.0.md` 14 since 2026-10-09.
  Context's counts are the 2026-10-06 ones, and its `1.7.0.md` now reads as
  the next release's file. *Next:* task 1.

- **2026-10-06** — Filed at the maintainer's request after the day's
  `/pr-review all` run, with the run's conflict counts above. No open WP owns
  it: WP-1507 names fragments as a non-goal, on a measurement this one
  reverses, and 1507's remaining task is its merge replay.
