---
name: issue-review
description: Triage the issue backlog — test each report against the tree, place it (close, comment, fold into a WP, file a WP, fence, schedule), batch every public act to the end
---

Triage the open issues. `$ARGUMENTS`: issue numbers (worked in the order
given), `new` (every open issue that no WP file or ROADMAP line cites,
§ Working the backlog), `all` (the whole open backlog, cited issues re-read
for what moved since), or empty (print the table, stop; never start on a row
unasked).

Issues only. A pull request that fixes one is `/pr-review`'s. An issue an
open PR cites is placed here as "in a PR" once the PR's claim has been read
against the issue, and is not reviewed. Most issues are one recurring
contributor's design proposals and measured reports; the rest are a
newcomer's questions. Both get the answer a colleague would get. Three rounds
preceded this command (2026-09-01, 2026-09-03, 2026-09-15; PRs #205 and
#213, #253, #326). Each ended in WP files and one docs PR. This command keeps
that shape and adds the public half.

## Where this runs

A worktree of its own, with a venv, because testing means running the tree.
`EnterWorktree` with the name `issue-triage-YYYY-MM-DD`, the rounds' branch
name. The create hook cuts it from `origin/main` and builds the `[dev]` venv.
The name declares no WP, so nothing claims it and `handover_owed.py` never
fires on it. Never the `pr-bench`, which `/pr-review` resets hard, and never
the main checkout.

## The table — the no-argument mode

One command, with the scratchpad path spelled out, since the worktree guard
refuses a variable in a path:

```sh
python3 .claude/skills/issue-review/backlog.py <scratchpad>/issues
```

Three network calls (open issues with bodies and comments, open PRs, merged
PRs) and one `git log`. It writes one file per issue to
`<scratchpad>/issues/N.md` and prints one table. Read the files, never the
threads: `gh issue view --comments` prints the comments and drops the body,
which lost 16 of 21 bodies on 2026-09-15. Columns:

- **WPs**: every WP file citing `#N`, each with its glyph; `+ROADMAP` where
  a ROADMAP line cites it; `untriaged` where nothing does. The citation is
  the triage record. Every earlier round audited itself by that grep and
  `wp_claim.py` reads the same text, so nothing else has to be written for
  an issue to count as placed.
- **open PR**: an open PR citing it, forks included. The fix may be in
  flight on another machine.
- **landed**: merged PRs and commits on `origin/main` that cite it and
  touched something outside the planning record. A fix lands without its
  issue closing more often than not: a closing keyword in backticks closes
  nothing (`/wp-handover` step 11), and WP-1310 filed two defects that were
  already fixed. Issue state is no evidence, so this column is. With the
  planning record counted, 65 of 86 issues carried a reference on 2026-09-21;
  without it, 19.

The summary names the untriaged and the landed lists. Its last line names
every open issue and PR whose author is neither the maintainer nor the
recurring contributor (`KNOWN_AUTHORS` in `backlog.py`). Tell the user about
those before the queue starts, and list them again as the first item of the
batch, whether or not the batch acts on them (the maintainer asked for this
on 2026-10-11). The rank to work in:

1. **A landed reference** on an untriaged or open-WP issue. Cheapest, and
   most often a close.
2. **A reporter waiting on a first answer**: an issue with no comment from
   the maintainer, oldest first. A newcomer filed thirteen in two days on
   2026-09-19 and every one was a first contact.
3. **A wrong answer given silently**, a bug whose symptom is a converged
   fit, before a raise, before a feature, before a proposal.
4. **In a PR**, last, once the PR's claim is checked.

Two limits: the rank cannot see that one small issue unblocks a WP in
flight, and "landed" is evidence to read and never a verdict. The user
overrules with arguments.

## Testing one issue

Read `N.md`. A body that is only a screenshot is fetched to the scratchpad
with `curl -sL <the user-attachments URL> -o <scratchpad>/N.png` (no auth
needed, measured) and read with the Read tool.

1. **Classify**: bug, question, docs, proposal, offer (a contributor
   offering a PR), or process (the repo's own machinery).
2. **Check the premise against this tree, and name the sha.** An issue's
   evidence goes stale four ways, and each is cheap to catch: a symbol it
   names that does not exist (`grep -rn` under `src/`; #277 cited three
   surfaces that never existed), a file that moved since
   (`git log --oneline -- <file>` from the issue's date), a fix that landed
   (the landed column, then the PR), and a number that no longer reproduces.
   Nothing the issue measured becomes a tolerance or a target until this
   tree has produced it.
3. **Reproduce.** A bug: the issue's own snippet, or the smallest script
   that asks the same question, run from this tree's venv with the script
   kept in the scratchpad. Record reproduced, not reproduced, or the surface
   is gone, with the sha. A question: answer it from the manual and the
   skill, and note where the manual could not, since that is the docs
   defect. A proposal: prior art and the licensing fence (concepts only from
   GPL codes; TOPAS and FullProf by paper), the `v2+` fence, and whether an
   existing WP already carries it. An offer: what it would land, and which
   WP would own it.
4. **Never fix here.** A round is docs-only, so it reviews as one PR and no
   `WP-NNNN:` commit owes a handover. A fix, however small, is a WP's or a
   fold into one, a one-line manual correction included.

## Placing one issue

Every placement is a dated line naming the issue as `#N`, plain, because
that is what the audit and `wp_claim.py` read. Private acts, in the planning
record, are done as reached. Public acts, anything on GitHub, are drafted to
a file and held for the batch.

- **Landed** → close, with a one-line comment naming the PR or commit.
  Batch.
- **Fold**, checked before filing: into the open WP (⬜ or 🔄) that owns
  the work (`docs/wp/TEMPLATE.md`'s fold-first rule), as a dated entry in its
  `### Inherited`, the section other sessions write for the one that will
  work it, with the check-against-the-tree line. A fold that moves the
  WP's rubric row (a second reporter, a number now shown wrong) re-rates its
  `Priority:` line in the same edit, and the index is regenerated. Never into a closed WP: a
  defect a ✅ WP's fix did not cover is a new WP or a landed close.
- **New WP** only where no open WP owns the work: `docs/wp/TEMPLATE.md`
  whole, `Milestone: unscheduled`, a `Priority:` line rated by the
  template's rubric (the test refuses a ⬜ WP without one), a `Track:` line
  naming the `####` of ROADMAP § Unscheduled it belongs under, the Skill task
  line, and a first handover bullet. Then `python3 .claude/hooks/wp_index.py`
  writes its row into `docs/wp/README.md`; ROADMAP changes only when the WP
  needs a new track or a sentence of prose (WP-1507). The bullet:
  `created, from the YYYY-MM-DD issue triage (issue #N). Checked against the
  tree at <sha>: …; no open WP owns it: …`. **Pick the number in the same
  breath as the file**: `git fetch origin main && git ls-tree --name-only origin/main docs/wp/ | tail -3`.
  A number is claimed by nothing, two sessions took 1436 on 2026-09-17, and
  a round filing several takes consecutive numbers, so re-check before each.
- **Fence**: a `v2+` proposal is named by issue in ROADMAP § v2+, so the
  audit sees it, and the reporter is told. Batch.
- **Comment**, for a question answered, a proposal answered (CONTRIBUTING
  promises "read and answered, not queued silently"), a report that does not
  reproduce and needs the file or the version, or a decision the reporter
  asked for. Written to a colleague who knows the codebase, in plain
  language, saying what was checked and on which sha, ending
  `*Reviewed with Claude Code on behalf of @yue-here.*`, the form the
  maintainer's threads already carry. Batch. A decision also goes in the WP
  file that owns the issue, as `Decided YYYY-MM-DD: …`, because a later
  session reads the WP file and not the thread.
- **Label**: the repo's default set (`bug`, `enhancement`, `question`,
  `documentation`, `duplicate`, `wontfix`). One batch item for the whole
  table, applied on a yes. The design-proposal template names a `proposal`
  label that does not exist, so proposals arrive unlabelled: a finding for
  the report, not this command's to fix.
- **Schedule**, or **open a milestone**, when a round's issues make a
  milestone's worth or a shipped answer is wrong enough for a patch release.
  A governance question for the batch; the mechanics are protocol step 6 and
  `docs/RELEASING.md`. GitHub milestones stay unused: the ROADMAP is the one
  authority for what is scheduled, and a second would drift.
- **Duplicate, invalid, wontfix**: the label, a comment naming the original
  or the reason, and the close. Batch.
- **In a PR**: a line in the owning WP's Inherited naming the PR. No comment
  unless the PR's claim and the issue disagree.

**Commit per placement**, `docs:`-prefixed (`docs: WP-1443 for #394`; the
branch is no WP's), so an interrupted round leaves its files and the next
`/issue-review new` starts from what is left.

## Working the backlog — `new` and `all`

The table, then the queue in rank order. Clear-cut private placements are
made as reached. Every public act and every governance call goes to one
batch at the end, never asked mid-run. In `all`, a cited issue is re-read
only for what moved since its placement: a comment newer than the WP's
citation, a landed reference. The WP's own premise is `/wp-start` step 5's.

**Context checkpoint, between issues only.** Measure the context the way
`/pr-review`'s context checkpoint does, before the first issue and at every
boundary. Stop when the next would carry it past **500 K tokens**. Ending means the batch, the audit, the PR and the
resume line: `/issue-review new` after the user's `/clear`. The committed
files carry the work across.

**The batch**: one numbered message. Every act is public, so every act joins
it; the triage in the maintainer's instructions (§ "Before you bring me a
decision") decides each one's content. Per item: the issue and what it
reports in plain words, the act in one sentence, the file holding a
comment's text, and the recommendation with its confidence (clear call,
lean, close call). A clear call is one line: "I will do X because Y, unless
you object." A lean or close call adds why it matters, ending in an
importance word (minor, moderate, serious), the options a competent person
would choose, the practice it rests on, and the crux. Each item reads
without this run's context, so a WP number or a name the run coined carries
a gloss. Open with how many items need a judgement. Group:
the summary's issues and PRs by other authors first, then closes, then
comments, then labels as one item, then scheduling.
`AskUserQuestion` only for ≤ 4 genuine multi-way choices. Then apply in one
pass, `gh issue comment N --body-file`, `gh issue close N --comment`,
`gh issue edit N --add-label`, record each decision in its WP file, and
commit.

**The audit, then the PR.** Re-run the table. The untriaged list must be
empty, or each remaining number is named in the report with its reason. The
counts in the commit and the PR come from the summary line and never from
memory: the 2026-09-15 round's first commit said twenty over a range holding
twenty-one. The ladder for a docs-only tree is `tests/test_docs_consistency.py`,
plus `tests/test_skill.py` if `docs/skill/` moved, plus ruff. No
`/code-review` (docs only) and no `/wp-handover` (no WP branch).
`git push origin HEAD`, then a PR titled
`docs: the YYYY-MM-DD issue triage — N WPs for M issues`. Its body carries
the WPs filed (WP, issues, one line each), the folds, the closes and comments
posted with their URLs, the decisions taken, the checks, and the footer. No
closing keyword before a `#N` anywhere in it (`/wp-handover` step 11's trap:
prose about a keyword is a keyword), since the round closes issues with
`gh issue close` and the PR must close none on merge. Check with
`gh pr view --json closingIssuesReferences`. Merging is the maintainer's.

**Report**: the plain-language paragraph first, what the backlog now holds
and what moved; then `#N (<what it reports, in plain words>): <decision>`
per issue, the decision one of
`closed (landed as PR M)`, `WP-NNNN filed`, `folded into WP-NNNN`,
`commented`, `fenced (v2+)`, `in PR #M (theirs)`, `held, waiting on you`;
then the PR URL, and
`Backlog: N open, N closed, N filed, N folded, N commented, N untriaged remaining`.
