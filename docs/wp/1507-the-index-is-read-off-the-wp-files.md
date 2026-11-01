# WP-1507 — the WP index is read off the WP files

Milestone: unscheduled · Status: ✅ 2026-10-23 — the WP index is generated from the WP files; ROADMAP conflicts went from 17 in 378 merges to 0 in 332
Track: The repo's own process
Depends on: — (1506 soft: the docs job it adds runs this WP's tests)

## Goal

The WP tables and the in-flight list are generated from each WP file's
Milestone, Status, Priority and Depends lines. Filing, starting, closing or
re-rating a WP then edits only that WP's file. ROADMAP.md keeps the prose,
which changes when a milestone opens or ships.

## Context

**Measured 2026-09-27.**

- From 2026-08-27 to 2026-09-27, 232 PRs merged. `docs/ROADMAP.md` changed
  in 144 of them (62%). `tests/test_docs_consistency.py` changed in 82, and
  46 of those changed nothing but a `SIZE_CAPS` number and its diary comment.
- Every two-parent merge since 2026-08-15 was replayed with `git merge-tree`
  (method in References). 25 conflicted: 17 on ROADMAP.md, 7 on
  `test_docs_consistency.py` (the cap line), 3 on the GUI dist, 2 on
  `SCHEMA_VERSION`, 5 on WP files and 1 on the skill (in all three copies).
- Of the 17 ROADMAP conflicts, 7 were in the WP tables. Two branches had
  inserted or edited adjacent rows, which git reports as a conflict even
  when the rows differ. The other 10 were in Current focus, which Session
  protocol step 5 rewrites at every close.
- Local reflogs show 6 merges and no rebases, so the replay sees most syncs.
  It is still a floor: a rebase in a worktree since deleted leaves nothing.
- Today's instance: two sessions each added a row within the one line of
  headroom and overran it together. f90d257d raised the cap from 854 to 856
  after both had merged.

**The rows copy a fact that already has an authority.** Each WP file carries
`Milestone:`, `Status:`, `Priority:` and `Depends on:` lines. Five tests in
`test_docs_consistency.py` hold the ROADMAP rows equal to them:
`test_wp_files_and_roadmap_rows_are_a_bijection`,
`test_roadmap_glyph_mirrors_the_wp_status_line`,
`test_index_section_mirrors_the_wp_milestone_line`,
`test_roadmap_status_cell_is_a_glyph_and_a_date` and
`test_roadmap_priority_cell_mirrors_the_wp_priority_line`. The copy is written
by hand at every start, close and re-rating, and a test catches the drift.
Root CLAUDE.md's rule for such a mirror is a projection computed from the
authority.

**Prior art.**

- `docs/VALIDATION.md` is generated, committed and asserted fresh by the
  suite. That is the house precedent for a committed generated file.
- `.claude/hooks/session_start.py` already derives the in-flight list from
  the WP files (`in_flight_wps`), not from ROADMAP.
- Python's PEP index (PEP 0) is generated from the PEP headers, and nobody
  edits it.
- GitHub renders a directory's `README.md` in its listing. A generated
  `docs/wp/README.md` would show the index to anyone browsing `docs/wp/`.

**Where the index lives: decided 2026-09-27 by the maintainer, option (a).**
The two options as they were put:

- (a) Committed, as `docs/wp/README.md`, asserted fresh like VALIDATION.md.
  Adjacent-row conflicts still happen, and they resolve by rerunning the
  generator. A merge driver (`docs/wp/README.md merge=wpindex` in
  `.gitattributes`, the command set in `.git/config` by the SessionStart
  hook) makes that automatic in a local merge. GitHub's web merge runs no
  custom driver, so a PR behind main is synced locally, as today.
- (b) Not committed. A script prints the index, and `/wp-start` and the
  SessionStart hook show it. There are no conflicts at all, and nothing in
  the repository shows the index on GitHub.

Recommended: (a). Contributors work on forks and see only GitHub, and the
index is how they see what is queued. It also follows VALIDATION.md.

**Current focus.** Its 60-line and 300-word caps stay. What changes is who
writes it. The in-flight list (🔄) and the next WPs by priority are generated
into the index. Current focus keeps the milestone-level prose, written when a
milestone opens or ships, and by `/issue-review` when a triage moves the
order. A close writes its narrative into the milestone record, which step 5
already does, and stops rewriting Current focus. `milestones/v1.4.md` changed
in 33 PRs and conflicted once. `releases/1.5.1.md` changed in 23 and never
conflicted. Neither needs a change.

**The cap.** `SIZE_CAPS["docs/ROADMAP.md"]` guards a file every session
reads. With the tables out, it measures prose only, and filing a WP no longer
moves it. The diary comment above `SIZE_CAPS` gains an entry at every bump,
always at the same place, which makes it a second conflict site. With the
per-row bump gone, it is written only when prose grows.

**Touchpoints.** `grep -rl ROADMAP .claude/` finds
`commands/wp-start.md`, `commands/wp-handover.md`, `commands/pr-review.md`,
`hooks/handover_owed.py`, `skills/issue-review/SKILL.md`,
`skills/issue-review/backlog.py` and `agents/pr-conformance.md`. Beyond
`.claude/`: ROADMAP § Session protocol steps 3 and 5, and the comment in
`wp/TEMPLATE.md` that says to keep the Status line and the ROADMAP row in
sync. A touchpoint that writes a row stops writing it. One that reads a row
reads the index.

**CI (from [1506](1506-a-planning-doc-pr-runs-what-reads-it.md), folded
2026-09-27).** A PR whose files all match `ci.yml`'s `PLANNING` pattern
(`docs/wp/`, `docs/milestones/`, `docs/releases/`, `ROADMAP.md`,
`DESIGN.md`, `tests/test_docs_consistency.py`) runs only the `docs` job,
which runs the four test files that read those paths. So a regenerated
`docs/wp/README.md` on its own stays a docs-only PR. The generator sits in
`.claude/hooks/`, outside the pattern, so a PR that changes it runs the full
matrix. The freshness and merge tests live in `test_docs_consistency.py` and
`test_workflow_hooks.py`, both on the docs job's list.

## Non-goals

- The skill's byte caps race the same way (WP-1338, issue #247). A skill file
  cannot be generated away, so its policy stays there.
- `SCHEMA_VERSION` (6 bumps in the 30 days, 2 conflicts) and WP numbers (two
  collisions, 1436 and 1469) are shared counters of the same class. Both are
  left alone. The first is a compatibility policy. The second has had a
  duplicate-number test since 2026-09-27.
- Committing one skill copy with symlinks for the two harness directories.
  The skill conflicted in one merge in six weeks, and a Windows clone without
  `core.symlinks` would lose the skill.
- Release-note and milestone-narrative fragments (the towncrier pattern).
  Measured above, those files do not conflict.
- The GUI dist: WP-1313. CI: WP-1506.

## Tasks

- [x] The decision above, taken with the maintainer and recorded here:
      (a), committed as `docs/wp/README.md`, 2026-09-27.
- [x] A generator, stdlib only, sharing one header parser with
      `test_docs_consistency.py`. It writes the per-milestone tables and the
      in-flight and next-by-priority lists from the WP files.
- [x] ROADMAP.md: each table replaced by a link to its place in the index.
      Section prose stays under its milestone heading. Current focus keeps
      milestone prose only.
- [x] `test_docs_consistency.py`: the five mirror tests become one freshness
      test on the index. The ROADMAP cap counts what is left and is set once,
      with its diary entry. The Current focus caps are unchanged.
- [x] If (a): the merge driver and its SessionStart setup, tested in
      `test_workflow_hooks.py`. Two branches adding adjacent rows merge
      locally with no conflict markers.
- [x] The touchpoints above: commands, hook, issue-review skill,
      pr-conformance agent, Session protocol, TEMPLATE comment.
- [x] Two weeks after landing, rerun the merge replay and report ROADMAP
      conflicts against this WP's baseline of 17 in six weeks.
      `python -m tests.merge_replay <landing date>` prints both this and the
      acceptance check below. The same script over `2026-08-15 2026-09-27`
      reproduces the baseline exactly: 398 merges, 25 conflicted (6.3 %),
      17 on ROADMAP. Compare rates, since the windows differ in length.
      Scheduled: a one-time cloud routine, `trig_01GNHLhDTBxq3Z9oG2sNVRnB`,
      runs both on 2026-10-11 at 01:00 UTC and opens a PR with the entry. It
      stops without editing if #509 has not merged, and it never closes the WP.
- [x] Skill: none. This is the repo's planning process.

## Acceptance

- Filing, starting and closing a WP change no line of ROADMAP.md and no line
  of `test_docs_consistency.py`. Check this on the first three WPs after
  landing.
- The index equals the generator's output on the tree.

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_workflow_hooks.py
```

## References

- Merge replay: for each `git log --merges --since=<date> --format='%H %P' --all`
  line with two parents, `git merge-tree --write-tree --name-only --no-messages
  <p1> <p2>` exits 1 on a conflict and lists the conflicted paths after the
  tree id. The per-PR counts come from `git diff --name-only <m>^1 <m>` over
  `git log --merges --first-parent origin/main`.
- PEP 0: generated by `pep_sphinx_extensions` in the python/peps repository.

## Handover log

### 2026-10-23 — closed: the index is the WP files' projection

The maintainer closed this WP on the 2026-10-11 replay. Both of its claims held.
Filing, starting or closing a WP now edits only that WP's file and the
regenerated index. ROADMAP's own conflict rate went from 17 in 378 merges to 0
in 332, and no later commit went back to hand-editing a row.

*Closed on.* The acceptance's literal reading, "the first three header-change
commits touch neither file", does not pass, because two of those three touch one
file each for reasons that have nothing to do with WP rows (entry below). The
maintainer accepted the substantive reading. Every task was already ticked, and
there was no `### Inherited` to dispose of.

*Next.* Nothing owed here. Under GitHub's web merge the conflicts moved onto
`docs/wp/README.md` itself: 31 in 332 merges. The local `wpindex` driver brings
that down to 1 (entry below). Option (a) accepted that cost when it was chosen,
and a regenerate resolves each conflict.

### 2026-10-11 — the merge replay, two weeks after landing

ROADMAP conflicts fell to zero. The cap-test conflicts fell to zero too. The
literal acceptance check does not pass clean on the first three
header-change commits, because the first of the three is the landing commit
itself and the third touches the cap test file for an unrelated reason.
Reading every flagged commit's diff, none reverts to hand-editing a WP row
or a status glyph, so the claim the acceptance was testing for holds.

**Baseline, 2026-08-15 to 2026-09-27.** This clone replays 378 two-parent
merges, 25 conflicted (6.6%), 17 on `docs/ROADMAP.md` (4.5%) and 7 on
`tests/test_docs_consistency.py` (1.9%), identical under both merge modes
(the driver did not exist yet in this window). The conflicted, ROADMAP and
cap-test counts match the WP's claimed 25, 17 and 7 exactly. The merge
count does not: this clone counts 378 where the WP file claims 398 and the
2026-10-01 session's rerun counted 391. All three runs agree on every
numerator and disagree only on the denominator, which moves with which
refs still exist in the clone doing the counting (`--all` reads live refs).

**After, 2026-09-27 to 2026-10-11 (14 days, 332 merges — both above the
7-day/30-merge floor).** `docs/ROADMAP.md` and `tests/test_docs_consistency.py`
each conflict 0 times (0%) in both modes. Merged as GitHub's web merge
would (no driver), the window still shows 41 conflicted (12.3%), almost
all of it moved onto the new `docs/wp/README.md`, which alone conflicts 31
times (9.3%). Merged locally through the wpindex driver, that falls to 20
conflicted (6.0%), with `docs/wp/README.md` down to 1 (0.3%). So the driver
is carrying the result, not the index move by itself: without it, the
generated file conflicts more often than ROADMAP's tables ever did; with
it, the overall rate (6.0%) sits close to the baseline's (6.6%) while the
specific pain point, ROADMAP, is gone.

**Header changes.** 108 commits changed a WP header in the window, 20 of
them also touching `docs/ROADMAP.md` or the cap test. The first three:
`3b3a9dc5` (PR #509, the landing merge itself — it necessarily touches both
files, since it is the implementation, including WP-1507's own header);
`154c33da` (PR #511, clean); `537f343d` (PR #512, touches only the cap
test, raising `SIZE_CAPS["src/rietx/io/CLAUDE.md"]` from 498 to 501 for
WP-1527, with no touch to any WP row or to ROADMAP). Reading all 20
flagged commits' diffs rather than just the first three: none edits an
individual WP row or a status glyph, and none raises the ROADMAP cap
because a WP was filed. The touches are the landing PR itself; four
unrelated `SIZE_CAPS` raises for `src/rietx/indexing/CLAUDE.md` (WP-1508,
1509, 1518, 1519) and one for `src/rietx/io/CLAUDE.md` (WP-1527) and
another (WP-1546-adjacent, PR #696) for the same file; one `docs/ROADMAP.md`
cap raise (PR #515) sized to and documented against a legitimate new
`####` track heading's prose, the kind this WP's own task list calls
legitimate; several more legitimate `####` headings and fence-prose edits
in `§ Fenced for now`/`§ Unscheduled`; and the separate Milestones table's
rows and status glyphs and the Current focus prose, both turned by
WP-1540, 1541 and 1546's named-milestone and weekly-release-cut work (a
different table from the one this WP removed, and not touched by any
ordinary WP filed, started or closed); plus two unrelated test refactors
(Windows path handling in PR #693, an engine-code walk in PR #802). So the
acceptance holds in substance: nobody went back to hand-editing a WP row
after landing. It does not hold on a literal reading of "the first three
commits touch neither file," because two of those three touch one file
each for reasons unrelated to WP rows.

Both of this WP's claims held: ROADMAP's own conflict rate went from 17 in
378 merges to 0 in 332, and no post-landing commit reverted to the habit
the index move was meant to end. The maintainer can close the WP on this.

### 2026-10-01 — /pr-review's bench merges as GitHub does

Not a session on this WP. A /pr-review fix touched two of its pieces.

- The 2nd session left `/pr-review` unchanged on purpose, and that was wrong.
  The bench ran the row merge, so its stacks and `merge-tree` checks called
  clean the index conflicts GitHub reported on #522, #546, #579 and #580. The
  bench now overrides the driver with git's text merge in its own worktree
  config (`commands/pr-review.md` § Where this command runs). Other trees keep
  the row merge. `session_start.ensure_merge_driver` now reads `--local`, so
  the override never makes it rewrite `.git/config`.
- `tests/merge_replay.py`'s `TEXT_MERGE` now passes
  `--diff-algorithm=histogram`, the algorithm git's own merge uses. Over the
  baseline window both algorithms give the same paths for every merge: 25
  conflicted, 17 on ROADMAP. The window now holds 391 merges, where the task
  below says 398, because `--all` reads only the refs that still exist.
  Compare rates, as the task says.

### 2026-09-27 (2nd session) — the index is generated; the replay waits two weeks

The WP tables no longer live in ROADMAP. A script reads each WP file's
header and writes `docs/wp/README.md`: what is in flight, what is next by
priority, and one table per ROADMAP section and track. Starting, closing or
re-rating a WP now edits that WP's file and the regenerated index, and
ROADMAP not at all. When two branches both add rows, a local merge resolves
the index by itself. A real merge in the tests conflicts without the driver
and merges clean with it. The cost: every WP under a ROADMAP track gained a
`Track:` line (200 files), and the index takes titles and dependencies from
the files, so 58 titles and 51 dependency cells read differently from the
hand-written rows. Whether conflicts actually fall is not measured yet. That
is the replay two weeks after landing.

**Done.**

- `.claude/hooks/wp_index.py`, stdlib only. `read_header` is the one header
  parser, and `test_docs_consistency.py` reads headers through it.
  `generate` writes the index; `render` and `parse` are exact inverses
  (tested on all 278 rows); `merge` is three-way per WP number. CLI: bare
  writes, `--check` exits 1 when stale, `--merge %O %A %B` is the driver.
- ROADMAP: its 34 tables became one sentence each, linking the table's
  anchor in the index. Current focus kept milestone prose. Its WP-level
  paragraphs (1442's four WPs, the triage queue list, 1432 and 1433) moved
  verbatim to the v1.6 record § How v1.6 is getting here. Session protocol
  steps 1, 3 and 5 read or regenerate the index, and a close no longer edits
  Current focus. v1.2's prose now states the order its table had carried.
- Tests: the five row-mirror tests became four. The index equals the
  generator's output; it parses back to the rows that wrote it; every WP
  names a heading ROADMAP has; every heading with rows links them. The
  duplicate-number check is its own test. The three new guards were each made
  to fail once, with the intended message (a status edited without
  regenerating, a removed link, a bogus track).
- Merge driver: `.gitattributes` marks `docs/wp/README.md merge=wpindex`, and
  `session_start.ensure_merge_driver` writes one config line, `python3
  .claude/hooks/wp_index.py --merge %O %A %B || git merge-file %A %O %B`. It
  is the hook's only write, and its docstring says so. Real-git tests: two
  branches adding adjacent rows (the control conflicts, the driven merge is
  clean and equals the generator's output), and one row both branches
  changed (the driver declines, and git writes its own markers).
- Touchpoints: `/wp-start` step 2 reads the index head (`sed -n '/^## In
  flight/,/^## <a id/p' docs/wp/README.md`) and step 4b regenerates;
  `/wp-handover` steps 4, 5 and 7; the issue-review skill (a `Track:` line,
  then regenerate); TEMPLATE (the Track line, how Depends on is read);
  CONTRIBUTING; the design-proposal template; root CLAUDE.md, rewritten
  within its cap; `test_no_stale_name.py`'s allowlist, where 1062's row moved
  to the index. Unchanged on purpose: `/pr-review` and the pr-conformance
  agent already cover `docs/wp/**`; `handover_owed.py`'s mention is history;
  `backlog.py`'s issue numbers from the old Depends cells come from WP files
  it already reads.
- `/code-review high --fix` found ten issues and fixed eight, in one
  commit. The one that mattered: a merge where one side renumbered a WP
  another side's Depends cell links now declines, where it had reported a
  clean merge the freshness test then failed. Also a non-⬜ glyph without a
  date is refused at parse, where render had crashed on it. Declined: both
  branches opening a first row under two different empty tracks still
  conflicts (it fails safe to git's line merge, and an ordered merge of the
  heading lists could hide a rename), and `session_start.py` keeps its own
  lenient Status parse (the hook must survive a malformed file).
- ROADMAP's cap 880 -> 571, with the diary in the test ledger, the per-cap
  comment and `milestones/process.md`.
- Three closed headings now carry the fate only their rows had: 0408 (was
  0603), 0602 (deleted by 1303), 1062 (superseded by 1066). Three Depends
  lines reworded: 1036 ("blocks 1035" read as a dependency), 1337 (the 1311
  and 1321 soft order only its row had), 1460 (soft markers).

**Measured.**

- Fast selection on the final tree, `[dev]`, darwin/arm64, no other suite
  running: 6556 passed, 151 skipped (6707). The run before the review's fix
  was 6555 + 151, so the review's one test moved it by exactly one. Wall
  clock 2:16-3:05 over the two runs. Net +4 tests: five removed, nine added.
  The full selection was not run, since no package code changed and no
  measured number can move (tests/CLAUDE.md, rung 3).
- Added tests, one run's figures on this machine: 1.57 s (adjacent-rows
  merge), 0.83 s (a row both changed), 0.33 s (driver setup), and six more
  at 0.06 s or less; 2.86 s in all. None joins the slow tail.
- The index is 500 lines and 56 kB, and its head is 35 lines (4.7 kB).
  ROADMAP went from 879 to 570 lines. The SessionStart hook's added config
  read is 13 ms.
- Titles: 58 of 278 differ from the old rows, all but two on closed WPs. The
  index sentence-cases a first word made of letters and hyphens.
- Depends: 51 of 278 differ. The open ones: 1132 (#108 merged) and 1321
  (#206 merged); 1133 and 1312, whose files say `—`; 1443 and 1449, whose
  old cells held notes; 1464 (#385 soft); and 1418, whose file names #290,
  1326 and 1327 as hard. 1418 is held by another session and was left alone.
- Git runs a merge driver from the top of the tree while the tree still
  holds the pre-merge files (probed in a scratch repo). So the driver merges
  the index text and never regenerates from the tree.

**Gotchas.**

- Transition: a branch open when this lands conflicts once if it edited a
  ROADMAP row, or the header of a WP that now carries a Track line (in
  flight: 1449, 1450, 1506). Take main's ROADMAP and rerun `python3
  .claude/hooks/wp_index.py`. In a WP header keep both the Track line and
  the branch's edit.
- GitHub's web merge runs no custom driver. A PR whose index conflicts with
  main is synced locally, where the driver resolves it.
- The driver cannot see the merged WP files. So a clean index merge can
  still be stale when a new WP number falls inside a range some Depends line
  names. The freshness test catches it, and rerunning the script fixes it.
- A new `####` track needs its ROADMAP heading, its prose, and the one-line
  sentence every other heading carries, linking its anchor in
  `wp/README.md`. The test's failure message names the anchor.

Next: the maintainer reviews and merges PR #509. After it lands, check the
acceptance on the first three WPs filed, started or closed: none should
touch ROADMAP or `test_docs_consistency.py`. Then, from 2026-10-11, rerun
the merge replay against the baseline of 17 ROADMAP conflicts in six weeks.
That is the last task, and the WP closes on it.

### 2026-09-27 — created

Created by a session the maintainer asked to find where the repo's merge
drag comes from. Most ROADMAP conflicts come from a hand-kept copy of the WP
headers and from rewriting Current focus at every close, and both can stop.
The numbers above are that session's merge replay. Next: the maintainer's
answer on where the index lives, then the generator.
