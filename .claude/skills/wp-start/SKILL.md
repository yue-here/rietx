---
name: wp-start
description: Session-start ritual — act on the hook report, pick the WP, branch, venv, restate scope
---

Run the session-start ritual. The SessionStart hook's report
(`.claude/hooks/session_start.py`) is already in context — start from it.

1. **Act on the hook's report first.** A `repair first` flag means a previous
   session missed its handover: run `/wp-handover` in repair mode for that WP
   *before* any new work. A soft `post-close commits not in the log` note is
   surfaced to the user, not necessarily repaired.

   **Read which rule fired**, because they mean different things.
   `WP file not touched since` is the *order* rule — substantive work landed
   after the WP file was last edited, and it sees a miss within the same day.
   `last handover entry <date>` is the *date* rule — the log is behind the
   commits by a day or more; it is the only rule that sees a session whose
   every commit was ritual (docs, a CLAUDE.md, `.claude/`).

   Neither rule proves health: work committed and handed over in the same
   session leaves both satisfied whatever the entry says, so a quiet report is
   a prompt, not proof.
2. **Identify the WP**: the one the user names, else ROADMAP "Current
   focus" — read the two sections, not the file
   (`sed -n '/^## Session protocol/,/^## Milestones/p' docs/ROADMAP.md`, one
   contiguous block): about a sixth of the file, and a WP file is
   self-contained. **§ Session protocol is read for its step 3**, which is
   the only statement of the handover trigger that stays in context after
   this command scrolls away; narrowing this read to Current focus alone
   (2026-09-01) cost the next two sessions their handover. Current focus holds
   milestone prose; what is in flight and what is next by priority are the
   index's first two lists, generated from the WP files (WP-1507):
   `sed -n '/^## In flight/,/^## <a id/p' docs/wp/README.md`. Read that one
   WP file only (plus the DESIGN.md sections it links); do not read other WP
   files.

   **Over ~50 KB (`wc -c`), read the WP file only through its newest handover
   entry**, which is the log's first under the template's newest-first order.
   This prints the line that entry ends on, and prints nothing when there is at
   most one entry:
   `awk '/^## Handover log/{h=1} h && /^(- \*\*20[0-9][0-9]-|### 20[0-9][0-9]-)/ && ++n == 2 {print NR - 1; exit}' docs/wp/NNNN-*.md`.
   `Read` the file with that number as `limit`, and never `cat` it: `Edit`
   needs a `Read` of the file you will tick and write in, and Bash hides
   output past 30,000 characters. If what you read is still over the bar,
   read it by section (`grep -n '^## '`). Then `grep -n` the older entries for
   the names your task touches, and for their dates if the log looks appended
   out of order. Step 6b gives the reason.

   **Then check nobody else has it**, before committing to the choice:
   `python3 .claude/hooks/wp_claim.py status NNNN` for the WP in hand, or bare
   `status` for the whole picture. It answers in two parts, because a clash
   comes from two directions.

   **This machine's worktrees.** One row each: `held` means a live `claude`
   session is sitting in that tree now, `dormant` means the tree and branch
   exist with nobody in them, `→` marks this session's own. Closed WPs whose
   trees were merely kept are filtered out, so a quiet table means what it
   says, and this half needs no network and no venv.

   **A held WP is taken**: two sessions on one WP duplicate hours of work and
   discover it at handover, so pick another or ask the user. A **dormant** one
   is the opposite and is often what you want — unfinished work with a branch
   to continue, resumed by giving `EnterWorktree` that tree's name.

   **Open pull requests, contributors' forks included.** The second part, and
   the only one that can see a person on another machine. Contributors here
   work from *issues* rather than WPs — measured 2026-09-15, all three open
   contributor PRs were on forks, named no WP in branch, title or body, and
   cited issues — so the chain is PR → issue → WP, through the issue numbers
   the WP files already cite. Issue *assignees* are not a signal: 0 of 78 open
   issues carried one.

   **An issue link is evidence of overlap, not proof of a clash.** One issue
   can be cited by several WPs, so read the PR before dropping a WP over it.
   A PR that names a WP outright is the strong form. If `gh` cannot answer the
   command says so rather than printing an empty list, and a session that
   cannot look should ask the user before starting.

   The WP a tree is on comes from its branch, so a tree you resume for a
   *different* WP is telling the next session the wrong thing. Say so once:
   `python3 .claude/hooks/wp_claim.py claim NNNN`. Nothing else needs it, and
   skipping it degrades to the branch name rather than to nothing.
3. **Worktree, then branch.** If the hook's first line names the main
   checkout, call `EnterWorktree` with the WP's name (`wp1208-<slug>`) before
   anything else. The `WorktreeCreate` hook cuts that branch from `origin/main`
   (or checks out an existing branch of that name), builds the `[dev]` venv,
   and keeps memory shared. The main checkout is read-only for a session —
   `.claude/hooks/worktree_only.py` refuses an edit or a HEAD-moving git verb
   there — so there is nothing to decide. Already in a worktree: continue its
   branch; it is yours. At session end Claude Code asks whether to keep or
   remove the tree; remove once the PR is open, the branch stays either way.

   The create hook **refuses** a tree whose name is a WP a live session in
   another tree is already working, and names that session and the release
   verb. It is the one refusal in this workflow rather than a report, because
   it is the last moment before a duplicated session is paid for. A refusal
   on a WP whose holder is plainly finished is cleared with the verb the
   message prints; check it really is finished first, because the trigger is a
   live process, not a leftover branch.

   **Never `git stash` here.** The stash is per *repository*, shared by every
   worktree, and another session's `stash pop` takes yours (measured
   2026-08-26). Commit to your branch instead.
4. **Venv.** If the hook flagged a mismatch or a missing venv (the create hook
   reports when its build failed), build this worktree's own
   (the fix the flag prints, `session_start.VENV_FIX`, which names the
   architecture on an arm64 Mac) and say which extras
   were installed — every test count quoted later depends on that statement
   (`tests/CLAUDE.md`).
4b. **Claim the WP where other people can see it** — a draft pull request, as
   the first act in the new tree. The local claim of step 2 is on *this*
   machine's disk and reaches nobody else; anyone working from another clone,
   the maintainer included, learns what you are on only through GitHub.

   Three commands, and they are the whole claim:

   - Set the WP file's `Status:` line to `🔄 <today> — claimed by @<you>`, and
     run `python3 .claude/hooks/wp_index.py`, which rewrites its row in
     `docs/wp/README.md` (a test fails on a stale index).
   - Commit the two alone, `WP-NNNN: claimed`. A commit touching only its own
     WP file and the index is *ritual*, so it owes no handover entry and trips
     no hook.
   - `git push origin HEAD` and `gh pr create --draft --title "WP-NNNN: <the
     WP's title>"`, body one line saying what you are starting.

   **It is a draft of the real PR, never a second one.** `/wp-handover` step 11
   edits this same PR and marks it ready, so claiming early costs nothing at the
   end and the work is reviewable from the first commit. Nor does it cost
   anything in CI: a draft PR runs ruff alone (~40 s), and the matrix waits for
   `gh pr ready` at the handover. Nor is it watched: the session subscribes to
   its PR at that same `gh pr ready` (`.claude/skills/steward/SKILL.md`), since
   every event on a draft is its own push. Skip it only for a session that
   will not commit — say so in a line if you do.

   **Its base is `main`, even when the branch is cut from an unmerged one.**
   GitHub retargets a stacked PR only when its base branch is deleted, and
   this repository keeps merged branches. On 2026-09-25 #476 merged into its
   base branch 16 s after that branch had merged into `main`, and its seven
   commits reached nothing (WP-1461, re-landed as #479). Based on `main`, the
   diff shows the other PR's commits until that one merges, and nothing strands.

   **Everyone does this, not only contributors.** A maintainer working locally
   is exactly as invisible to a contributor as the reverse, and a one-sided
   claim leaves half the clash open.

5. **Prune the WP's `### Inherited`** on arrival: fold still-true entries
   into Context or Tasks, delete stale ones, and say why in the handover
   entry.

   **Then check the WP's *Findings* the same way, before building on one.** A
   findings block is a dated claim about the tree, not a standing fact, and a
   queued WP can lose whole tasks to work that landed after it was written:
   WP-1131, opened 2026-08-23 and started 2026-09-02, declared a conversion
   module missing that had landed the next day, and the width check it had
   inherited had shipped entire in v1.2 — three of eleven tasks already done,
   one task changed shape, and a dependent WP's blocker discharged rather than
   delivered. Grep for the names a finding says are missing and
   `git log --oneline -- <the file it says lacks them>` since the WP's date.
   A WP `/issue-review` filed names the sha it checked the issue against in
   its first handover bullet, so the range to read is `<that sha>..origin/main`
   on the files the WP names, and the issue's thread may have moved since:
   `gh issue view N --json comments` for anything newer than that bullet.
   **Delegate this check once it means reading past step 6b's bar**, such as
   a long range diff or several files. Give one agent the findings and the
   range, ask which still hold with `file:line`, and check each answer at its
   line before you rewrite anything.
   Rewrite what has gone stale **in place** with a dated "superseded in part"
   note and commit that prune first, because the successor reads the WP file
   and not your session. Then check whether any WP depending on this one is
   now unblocked — that goes in *its* `### Inherited` at handover (step 5 of
   `/wp-handover`).
6. **Tick the checklist item in the same commit that lands it** (protocol
   step 2). This is the cheap insurance behind the whole ritual: it keeps a
   partial record on disk at every point, so an interrupted session leaves the
   successor something, and it is what keeps the hook's order rule quiet
   without a handover being owed.
6b. **Read by what the rest of the session pays.** Every token read into
   this session is written to its cache once, at the 1-hour rate. It is then
   re-read by each request after it. An agent's reading is written at the
   cheaper 5-minute rate and ends with the agent. Delegating also keeps the
   session further from compaction, which is one of step 7's handover
   triggers. The measurement and the model are in `docs/milestones/process.md`
   § What a session's reading costs, from #548.
   - **Read what you will edit by range.** `grep -n` for the symbol, then
     `Read` with `offset`/`limit`. Delegating that saves nothing, because the
     edit needs the text here anyway. Never read a large module whole: the
     largest run to hundreds of KB.
   - **Delegate what you need only a conclusion from once it passes ~50 KB**
     (`wc -c`; 1 KB ≈ 400 tokens). Examples: a survey across modules, a long
     WP's history, a range diff. The bar falls as the number of requests
     still to come rises, and the record's table shows by how much. Use
     `Explore` to locate something and a general-purpose agent to read and
     judge it. Ask for the conclusion with `file:line` pointers, never
     excerpts, because the agent's report is carried like any other read.
     Check what you build on.
   - **Under the bar, read it yourself.** An agent starts from its own base
     context, so a small read saves little or nothing delegated, and checking
     the agent's answer adds requests of its own.
6c. **Send a long item to a lane once the context is large.** A *lane* is a
   subagent that does one checklist item while this session waits. This
   session then checks its diff and commits it. It pays for the reason step 6b
   gives: every request here re-reads the whole context, and a lane starts at
   about 70K. In WP-1903's trial, ten sessions sent 26 items to lanes and
   every session came out ahead, by a median 20% of what it would have cost
   without lanes (`docs/milestones/process.md` § Lanes within a WP).
   - **Decide each item when you start it.** Read the main context with
     `python3 .claude/hooks/session_usage.py context <session-id>`. The id is
     the name of the directory that holds your scratchpad. Then estimate the
     item's requests, a request being one round of tool calls. Implementing
     and testing a feature usually passes 20. A doc edit, an index
     regeneration or a one-line fix usually does not.
   - **Lane the item if the context is over 150K and the estimate is 20 or
     more.** Keep anything else. Estimates ran short by a median 1.6× in the
     trial, so an estimate of 20 is an item of about 30, and the replay's most
     robust rows lane from there.
   - **Keep an item that needs the user or a decision partway**, whatever its
     size. The trial's one lane that needed a redesign sent mid-way re-read
     74K of this session's files, against a median of 3K. The handover is
     never laned.
   - **Write the decision as a line of its own** for every item, kept ones
     too: `lanes: keep <item> ~<N>` or `lanes: lane <item> ~<N>`, with the
     checklist item's short name and the estimate. The measurement compares
     each estimate with what happened. Three trial sessions measured items
     that had no line, so those items have no estimate.
   - **Dispatch with one `Agent` call**: `subagent_type: general-purpose` on
     the default model, description exactly `lane: <item> ~<N>`. The
     measurement finds lanes by that prefix. Run one lane at a time, in this
     worktree, with no `isolation`. Wait for its notification and leave its
     files alone meanwhile.
   - **The prompt carries what a lane cannot see.** A lane loads the
     CLAUDE.md files but no MEMORY.md, and it knows nothing this session
     learned. Give it the WP file's path and the item verbatim. Give it what
     this session found as `file:line` pointers, without the text. Name
     **every code path the change reaches**. In WP-1534 a lane's bug sat on a
     second entry path the prompt left out. Restate each memory
     rule that bears on the item in a line, and always this one: a foreground
     command running past about 8 minutes kills the lane, so background it.
     A lane that runs suites or probes keeps its own context small: each log
     goes to a file, only the numbers come back, a `CHECKPOINT.md` records
     what is measured, and it reports once past 300K. WP-2043's VALIDATION
     lane read its logs whole and reached 813K before anyone saw it.
     Give the acceptance as the fast selection for the touched area, never the
     full suite. Tell it to leave git and the WP file alone, and to end with a
     short report: files changed, tests run with their counts, and
     anything unresolved with `file:line`.
   - **Check it, then commit it.** Read the diff by file, re-run the lane's
     tests and fix small things here. If the lane got the item wrong, dispatch
     again with the same description. Commit with the `WP-NNNN:` prefix and
     tick the item in the same commit (step 6). `/wp-handover` step 3b
     measures the lanes, and its diff review covers their code like any
     other.
7. **Restate before starting**: the checklist item being started, the WP's
   acceptance command, and the session scope — this WP only; finish →
   `/wp-handover` → stop.

   **Name the tier of what the item adds** (WP-2014). For each flag,
   threshold or automatic action the item adds, say its tier and its kind of
   ambiguity (`docs/milestones/generality.md` § The rule; `docs/DESIGN.md`
   § Rules, 1). A WP filed before 2026-10-19 that plans one has no tier line
   in its Context; write the template's line there first (`docs/wp/TEMPLATE.md`,
   "The tier of each rule this WP adds"). Do not pause for the maintainer.
   The judge still decides at handover (`/wp-handover` step 7).

   Say the trigger out loud too, because `/wp-handover` is missed by drifting
   past it rather than by deciding against it. Run it when **any** of these
   happens, not only the first: the WP's scope for this session is done; the
   user says stop, `/clear`, or "that's enough"; context is about to compact;
   or the work is blocked on something outside the session. The protocol's own
   words are "at the end — **or whenever interruption threatens**".

   **Invoke the command; do not reproduce it.** The second failure mode is
   writing the entry, syncing the glyph and opening the PR by hand and
   reporting "handed over" — which is what WP-1131 did on 2026-09-02, having
   skipped the diff review and the verify pass, the two steps that cost work.
   A summary of the checklist is not the checklist.
   `.claude/hooks/handover_owed.py` holds one stop open when a WP branch is
   clean and pushed and this session never ran the command; a session that is
   genuinely not finished says so in a line and carries on.
