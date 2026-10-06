# WP-1914 — a release note is a file per change

Milestone: unscheduled · Status: ⬜
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

## Non-goals

- The milestone record's running narrative (`docs/milestones/vX.Y.md`).
  WP-1507 measured it conflicting once in 33 PRs, and nothing since says
  otherwise.
- Rewriting the notes of shipped releases.

## Tasks

- [ ] Pick towncrier, scriv or a stdlib script against the three needs in
      Context. Record the choice and why in this file. A supported tool wins
      unless it cannot hold the hand-written prose or the nested sections.
- [ ] The fragment directory and its naming (`<PR>.<section>.md`), inside
      `ci.yml`'s `PLANNING` pattern.
- [ ] Move the bullets now in `1.7.0.md` into fragments, or keep `1.7.0.md`
      as the head the fragments are appended under. Choose the one that leaves
      open PRs a single rebase.
- [ ] `docs/RELEASING.md` step 2: join the fragments, then edit the result as
      a reader's document.
- [ ] ROADMAP rule 6 says a change stages its note as a new fragment file,
      and CONTRIBUTING.md gains the same sentence for contributors.
- [ ] A test in `test_docs_consistency.py` that every fragment names a known
      section, and that a joined file has no fragment left unplaced.
- [ ] Tell the outside contributor on their open PRs once it lands, since
      every one of them touches the file.

## Acceptance

Two branches that each add a release note merge onto `main` with no conflict,
under the bench's text merge. The joined `1.7.0.md` matches the hand-staged
one section for section.

## References

- [1507](1507-the-index-is-read-off-the-wp-files.md): the non-goal this
  reverses, and the measurement it rested on.
- towncrier, https://towncrier.readthedocs.io; scriv,
  https://scriv.readthedocs.io.

## Handover log

- **2026-10-06** — Filed at the maintainer's request after the day's
  `/pr-review all` run, with the run's conflict counts above. No open WP owns
  it: WP-1507 names fragments as a non-goal, on a measurement this one
  reverses, and 1507's remaining task is its merge replay.
