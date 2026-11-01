---
name: wp-handover
description: End-of-session WP handover — record everything, review, verify, open the PR and watch it, report ready for /clear
---

Run the end-of-WP-session checklist (docs/ROADMAP.md § Session protocol,
steps 3–5). Work through every item; do not skip one silently — if an item
does not apply, say why in one line.

**Repair mode** — when invoked for work a *previous* session left
un-handed-over (the session-start hook's `repair first` flag): reconstruct
the missing entry from `git log --stat` over that WP's commits and the
current state of its checklist, date it with the commits' own date (never
today's), and mark it "(reconstructed post hoc)". A reconstruction records
what the commits show, not what the session might have known — where the
diff does not say why, say so rather than inventing a rationale. All other
steps below run unchanged.

**The handover runs at the session's largest context, so every request and
every read costs the most here** (`docs/milestones/process.md` § What a
session's reading costs). So send independent calls in one response: step
10's three checks are one. Read a long file by range rather than whole
(steps 5 and 8). Answer step 7 from what the session knows, never by
re-reading its own diff.

1. **Identify the active WP** from this session's `git log` (`WP-NNNN:`
   prefixes). If more than one WP was touched, confirm with the user before
   proceeding. If the session made **no** commit and left no uncommitted work,
   say so in one line and stop — there is nothing to hand over, and running the
   rest anyway is what makes this command feel expensive enough to skip.
2. **Tick landed tasks** in the WP file's checklist — every commit that
   landed should correspond to a checked item.
3. **Prepend the dated handover entry** to the WP's `## Handover log`
   (newest first), in one of the two forms `docs/wp/TEMPLATE.md` sanctions —
   a `- **YYYY-MM-DD** — …` bullet, or a `### YYYY-MM-DD [(Nth session)] — …`
   heading once the WP takes more than one session in a day. **Only those two
   are read by `.claude/hooks/session_start.py`**, and an entry it cannot see
   is a handover that did not happen: it flags the WP at the next session and
   spends the successor's first act on a repair that was not needed.

   The entry has two audiences and therefore two registers.

   - **Open with a short plain-language paragraph saying what the work
     *means*** — what a person who has not read the diff now knows, or can do,
     that they could not before, and what it cost or ruled out. No dot-paths,
     no symbol names, no commit list. Two to five sentences. If the honest
     answer is "nothing yet, but X is now refuted", write that; a negative
     result stated plainly is worth more than a summary of activity.
   - **Close by naming the next actions** — the concrete next thing, in order,
     with whatever decides between them. "Next: answer the last task first,
     because it decides whether the rest is JSON-surface work or python-surface
     work" is an entry a successor can act on; "next: continue" is not.
   - **Between them go the working details** for the successor: *Done* /
     *Measured* / *In flight* / *Gotchas*, written for someone who has read
     only this WP file and CLAUDE.md.
3b. **Measure this session's lanes**, if it dispatched any under `/wp-start`
   step 6c (an `Agent` call whose description starts `lane:`). Run
   `python3 .claude/hooks/session_usage.py lanes <session-id>`, where the id
   is the name of the directory that holds your scratchpad. Put its tables
   under the entry's *Measured*. Append its `trial row` to the table in
   `docs/milestones/process.md` § Lanes within a WP: `grep -n '^| date |
   session'` for the line, then `Read` from there. Run the `baseline` command
   it prints, and quote the selective policy's row in the entry.
4. **Sync the Status line** (`glyph date — free text`, vocabulary in
   `docs/wp/TEMPLATE.md`). The index row follows at the end of step 8.
5. **Push forward references**: anything learned that changes work in a WP
   that is not closed and not this one goes into *that* WP's `### Inherited`
   section, naming this WP as the source. **A follow-up with no obvious owner
   is checked for one before it becomes a new WP** — fold first, the rule in
   `docs/wp/TEMPLATE.md`'s header; WP-1469 filed four and withdrew two as
   folds the same day. Look for an owner with `grep -rln` over `docs/wp/`.
   Edit another WP's `### Inherited` or `Priority:` by range once the file
   is over ~15 KB: `grep -n` for the heading, then `Read` with `offset`.
   Below that size the extra round trip costs more than reading the whole
   file. **Re-rate what this close moved**:
   a WP whose last blocker was this one, or whose trigger this work mooted,
   gets its `Priority:` line rewritten (tier, today's date, one clause naming
   this WP; rubric in `docs/wp/TEMPLATE.md`). An unrated WP (`—`) stays
   unrated unless the move is the reason to rate it.
   **Then run `python3 .claude/hooks/closed_wp_writes.py`**. It lists every
   WP this branch adds lines to that is ✅/🛑 at the merge-base or on
   `origin/main` (closed by its owner since this branch forked). No
   session reads a closed WP again, so a note there that asks for work is
   lost: move it to the open owner, or file one. A correction to the closed
   WP's own record may stay, and the handover entry says which it was. Two
   notes were lost this way, one of them for 81 days (WP-1994).
6. **Review the diff before it becomes a PR.** Run `/code-review high
   --fix` — it reads this session's work (a clean tree means the branch's own
   diff against `origin/main`) and applies what it accepts to the working
   tree. It belongs *here*, ahead of step 7's test runs and step 10's verify,
   because a fix is a code change: one landed after the suite ran, or after
   the PR was opened, leaves neither the quoted counts nor the review
   describing the tree that merges. It is also ahead of `gh pr ready` (step
   11), so its fixes ride pushes to the draft, which run lint alone. The full
   matrix then runs once, on the tree this handover hands over.

   **A prose-only branch skips it**, saying so in one line. `/code-review`
   hunts correctness bugs in code, and a branch that touched only `docs/`,
   the `CLAUDE.md`s and the markdown under `.claude/` gives it nothing to
   read. A `.py` anywhere, hooks and skill scripts included, is code. The
   review a prose branch gets is step 7's checklist against what it
   declared, and step 10's `test_docs_consistency.py`.
   - Each accepted fix lands as its own commit prefixed `WP-NNNN:` like any
     other work; one left uncommitted fails step 10's clean-tree check.
   - **A finding is advice, not a gate** — declining one is a line in the
     handover entry, never silence. Say there what the pass changed, or that
     it found nothing: a review that left no trace cannot be told apart from
     one that never ran.
   - A finding outside this WP goes into that WP's `### Inherited` (step 5),
     not into this branch.
7. **Audit this session's CLAUDE.md edits** (root, `gui/`, `tests/`,
   `src/rietx/indexing/`): every added line must be a standing rule
   (protocol rule 4 — evidence compressed to a clause plus a pointer), never
   a dated finding. Counts and timings this session measured go **in the
   handover entry** (root CLAUDE.md § Numbers is a recipe, not a ledger),
   and run the count check there: passed+skipped moved by exactly the tests
   this session added, in both the fast and full selections, and any new
   skip is named as a skip, not a pass.

   **Give the fast run a junit file and quote what the added tests cost.**
   Add `--junitxml=<scratchpad>/junit.xml -o junit_duration_report=total` to
   the fast command, then run `.venv/bin/python -m tests.added_test_times
   <junit>`. **Prefer CI's file when the branch has one**, because local
   seconds understate a CI leg by 3-4× (WP-1547). A PR readied once has one:
   `gh run list --workflow ci.yml --branch "$(git branch --show-current)"
   --status completed --limit 5 --json databaseId,headSha,conclusion`, then
   `gh run download <id> -p 'junit-py3.14-*' -D <scratchpad>/ci` on the
   newest run that has the artifacts, and name the sha it ran on. A draft's
   run and a cancelled one have none. Pass the directory, since the leg runs
   as two shards with a file each. Read the py3.14 leg because it alone
   executes the tutorials. Otherwise pass the local file. The entry quotes the rows and
   the per-file totals as one run's figures on the named machine. They rank a
   test or a file against the tail and do not time it. A test or a file that
   joins the fast tier's slow tail says why it is not marked `slow`
   (`tests/CLAUDE.md` § Budgets in tests).

   **Check nothing else is mid-suite before the full selection** — the `ps` check,
   `tests/CLAUDE.md` § Running. A `/pr-review` or another WP session may be
   running one, and a count measured beside it is not a count this handover can
   quote. Found one, the honest entry says the full selection did not run —
   never a figure taken anyway.

   Then **audit the names this session declared**, for the classes that have
   already gone wrong here and that no test catches. Only the ones the
   session actually triggered; the mechanised classes need no second opinion
   (`test_manual_api.py` already fails on an undocumented public surface,
   `test_docs_consistency.py` on glyphs and links, the `capabilities`
   meta-tests on a registry member missing from its arm). Did this session
   add physics with prose but no Theory-tab manual equation — **four of
   the six McCusker WPs** did exactly that (WP-1067's log)? Something this
   session **measured that an agent driving rietx needs** — a rule, a stop
   condition, a surprise — sitting in the handover entry and not in the
   skill? Root CLAUDE.md § skill routes it: the body if it holds for every
   fit, the task shape's `references/` file otherwise, a `(Measured: …)`
   tag on the row; the mechanised half is three suites' — a code without a
   row `tests/test_docs_consistency.py`, a verb the index omits
   `tests/test_skill.py`, a copy out of sync `tests/test_skill_cli.py`. A declared
   name with no writer — a defaulted `False`/`0` that reads as an *answer* about
   something nothing checked, a `Literal` member no code produces (**nine in
   WP-1076 alone**, and they were found by writing a manual chapter over the
   type, never by reading the code)? A correction whose evidence is an Rwp
   comparison? A physics function without its citation?

   Reading your own diff for these is weaker than reading someone else's, so
   name the trigger rather than scanning: this is a checklist against what
   the session *added*, not a re-review of it. Nor is it a re-read. At this
   context, each line read here is paid again by every request left, and
   step 6's review has already read the diff.

   **Dispatch the generality judge when a heuristic's tier was written by its
   author** (WP-2001). Two triggers. The branch touches the audit table:
   `git diff --name-only origin/main...HEAD -- src/rietx/_audit.py` prints the
   file, because the tripwire (`tests/test_audit_table.py`) fired and was
   answered or because a row was retiered. Or the session added a heuristic
   the table cannot see, which its module docstring lists: an inline literal,
   an ordering or fallback chain, an always-on correction, a rule in the skill.
   The second trigger is why this sits on step 7, which a prose-only branch
   runs, and not on step 6. Write the branch diff to a WP-named file in the
   scratchpad (`wp-NNNN-generality.diff`; parallel lanes share it) and
   dispatch one `Agent`, `subagent_type: generality-review`, naming the diff
   file, this worktree, the WP file and the items: each row added, changed or
   deleted in `_audit.py` (`.venv/bin/python -m tests.audit_delta` lists them
   against the merge-base, as CI does), each name added to
   `UNAUDITED_BASELINE` or `OTHER_RECORD_FIELDS`, each entry added to
   `NOT_WALKED` or removed from `WALKED` or `DEFAULT_SEATS` (its declarations
   list), and each heuristic of the second trigger. A session
   registers agents from the checkout it started in, so where that type is
   not found, dispatch `general-purpose` on Opus and have it read
   `.claude/agents/generality-review.md` first and follow it. Paste its
   sections into the handover entry under *Generality*, unedited, with the
   author's one-line answer under any `fails`.
   The maintainer reads both.
8. **If the WP is closing** (✅/🛑): delete its consumed `### Inherited`
   section and its `Priority:` line (a closed WP's priority is moot), and
   MOVE its narrative to the record of the release in flight
   (`docs/milestones/vX.Y.md` for `pyproject.version`'s X.Y, § "How vX.Y is
   getting here"), whichever named milestone the WP sits under (WP-1540).
   Append to the record by range:
   `grep -n '^##'` for the section, then `Read` only its last lines. Records
   grow long; v1.0's reached 340 KB. Leave ROADMAP's Current focus alone:
   it holds milestone prose, and the index lists what is in flight and next
   (WP-1507).
   **A closing WP that was P1 for a silent wrong answer or data loss owes a
   release at once** (`docs/RELEASING.md` § When): read the tier off the
   `Priority:` line before deleting it, and say so in step 12's report.
   **Then, closing or not, run `python3 .claude/hooks/wp_index.py`**, once,
   after every header edit of steps 4, 5 and 8. It rewrites
   `docs/wp/README.md`, and a test fails while the index is stale.
9. **Sweep session memory notes**: anything in the assistant memory
   directory that corrects or extends the repo record gets ported into the
   repo now — a memory note is not a channel to the next session's repo
   state.
10. **Verify**: run `python3 .claude/hooks/session_start.py` — the scan the
    *next* session starts from. It must come back with no flag for this WP; a
    flag here means the entry was written in a form it cannot read, or that
    work landed after the WP file was last touched, and either way the
    successor pays for it. Then run
    `.venv/bin/python -m pytest tests/test_docs_consistency.py` and
    `.venv/bin/python -m ruff check src tests examples`; confirm the working
    tree is clean and pushed (or say what deliberately is not). **Clean and
    pushed is not the same as landed**: if the branch is already merged, check
    `git log origin/main..HEAD` is empty too. A commit made after its own PR
    merged is stranded on a dead branch — the merge cannot carry it and the
    session-start hook only compares dates, so nothing detects it (measured
    2026-08-18: `11ec1cd5` sat there until the next session's repair).

    **And green on this branch is not green on what lands.** Where the session
    ran the full suite at all — step 7's rule, when the change could move a
    measured number — run it on **current main merged into this branch**, not
    on the bare branch: `git fetch origin main` and merge it in first. Nothing
    else ever tests that tree. Branch protection is `strict: false`, so a PR
    merges green without ever having been built against the main it lands on,
    and `nightly.yml` has no `pull_request` trigger, so the acceptance suites
    do not run on a PR at all. `tests/CLAUDE.md` states the half of this that
    was already known: when main has moved under a branch, that branch's
    counts are not the merged tree's and the two parents' additions cannot
    simply be summed. The counts quoted in the handover entry are then the
    merged tree's, and say so.

    This is the same class as the stranded commit above, one rank out: what
    you verified and what the repository will hold are not the same object.

    **Fetch main immediately before the merge**, not at step 1. A concurrent
    `/pr-review` merges other people's PRs, so `origin/main` moves for reasons
    this session never sees, and a main fetched an hour ago can be several merges
    stale — which puts this step's tree back to being one nothing tested.
11. **Open or update the pull request.** A session's work is not handed over
    until it is reviewable, so the PR is part of the ritual rather than a
    follow-up request. Skip it — saying so in one line — when the branch is
    `main`, when `git log origin/main..HEAD` is empty, or when the branch is
    already merged (repair mode usually lands here).
    - Check first with `gh pr view --json url,state,isDraft`: an existing open
      PR for this branch is **edited** (`gh pr edit --title --body`), never
      duplicated. `/wp-start` step 4b opens one as a **draft** to claim the WP,
      so the usual case here is editing that draft and marking it ready
      (`gh pr ready`) — a claim PR left in draft reads as work still in flight
      and goes on holding the WP. **`gh pr ready` is also what starts the
      gating run**: a draft PR runs ruff alone, so the fast matrix reports only
      once the PR is ready, and step 12 has nothing to watch until it is.
    - Title mirrors the lead commit: `WP-NNNN: <what landed>`.
    - Body is the handover entry **rewritten for a reviewer**, not pasted:
      what landed and why, what it measured (with the venv **and** platform,
      per `tests/CLAUDE.md` § Quoting numbers), what it deliberately did not
      do, and any finding filed into another WP, named with its number. End
      with the repo's two-line Claude Code footer.
    - **Say what a reader now receives** (ruled 2026-11-01: no junk passed
      back to a reader, a person or an agent). Run `.venv/bin/python -m
      tests.reader_output`. On exit 1, the body gains a section headed
      `What a reader receives` with its diff, and step 12 shows the diff to
      the person and asks whether each added line belongs. A field added to
      a result or report type gets the same section, read off the generated
      `docs/skill/rietx/references/api*.md`. On exit 0 with no such field,
      the body says so in one line.
    - **A closing keyword is plain text, never a code span.** GitHub does not
      parse `` `Closes #148` `` inside backticks, so the issue stays open with
      its work merged and nothing says so. Measured 2026-09-16 over the last
      120 merged PRs: 10 closing phrases written plain, every one of their
      issues closed; 7 written in backticks, every one of their issues open.
      Four of those seven quote the keyword on purpose (#206 and #213, which
      say they are leaving their issue open); the other three are WP-1118
      losing #101, #148 and #234. **The trap has a second half**: prose about
      a keyword is a keyword. Writing that another PR declined to close an
      issue linked that issue here, and rewording around the number left the
      link standing. Check with
      `gh pr view N --json closingIssuesReferences`, and clear a stray link by
      taking the **number** out, since editing the words around it does not.
    - **Never merge, and never wait on CI to decide.** Whether green is
      enough, and when to merge, is the maintainer's call.
    - **Then subscribe to it**, where `subscribe_pr_activity` exists (a cloud
      session; `ToolSearch` loads it). `.claude/hooks/pr_subscribe.py` puts
      the call, number filled in, in front of you after `gh pr ready`. From
      here the session is the PR's steward until it merges or closes, and
      handles each CI result, review and merge conflict by
      `.claude/skills/steward/SKILL.md` (WP-1988): main moves under every
      open PR all day, and an unwatched one sits red or conflicted until the
      maintainer finds it.
12. **Report**, to the person and not to the log: **first the same
    plain-language paragraph the entry opens with** — what this session's work
    means, in a few sentences someone can read without opening the diff — then
    step 11's reader diff with its question, where there is one — then
    the next actions, then the PR URL, and that CI is the gate — the required checks run
    ruff plus the fast suite across the supported Pythons and a `[dev,jax]`
    job. Subscribed (step 11), say so; without the tool, offer to watch the
    run rather than assuming. When you watch by polling, read
    state from `gh run list` (REST) rather than `gh pr checks` (GraphQL, which
    has 503'd through a GitHub incident while runs kept reporting), and read a
    sub-minute failure as one that never reached repo code. Only when step 10
    is green, end with exactly: **ready for /clear** — or, subscribed, with
    **watching <PR url>**: its events arrive in this session, so the next WP
    starts in a new one.
