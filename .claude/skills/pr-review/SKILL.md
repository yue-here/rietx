---
name: pr-review
description: Review outside pull requests — triage the backlog, or work it top-down: merge the clear-cut, batch every human call to the end
---

Review pull requests from outside the repository. `$ARGUMENTS`: PR numbers
(reviewed in the order given), `all` (work the whole backlog, § Working the
backlog), or empty (triage, print the ranked backlog, stop — never start on the
top row unasked).

Other people's PRs only. The maintainer's own are gated by `/wp-handover`
steps 6 and 10; a number naming one is still re-gated, but the governance
signal (rank 2) and the public review (step 8) do not apply, and you say so in
one line. Most outside PRs are one recurring contributor's: write the public
review to a colleague who knows the codebase. That is a register and moves no
gate — least of all step 4's execution check, since familiarity is not
provenance.

## Where this command runs

Triage reads the remote and runs from anywhere. Before step 4, and before the
`all` mode's pass B, enter the bench: `EnterWorktree` with
`path: .claude/worktrees/pr-bench` — a persistent worktree with a `[dev,jax]`
venv, created once by `git worktree add --detach .claude/worktrees/pr-bench
origin/main` plus step 4's venv line and, run in the bench,
`git config --worktree merge.wpindex.driver 'git merge-file %A %O %B'`. From then on every command runs from the
bench as plain `git`, and the main checkout is never named (`worktree_only.py`
keeps it read-only anyway). The worktree guard refuses `git -C .`, a shell
variable in a git command, and a git command inside a loop or a compound
pipeline. A multi-step check goes in a scratchpad script, run as one plain
command.

**The bench merges as GitHub does.** GitHub's merge runs no custom driver, so
it merges `docs/wp/README.md` as text. Every local tree runs the `wpindex` row
merge on that file instead (`.gitattributes`). So every `merge` and
`merge-tree` in the bench swaps the row merge for git's text merge on its own
command line:

```sh
git -c merge.wpindex.driver='git merge-file %A %O %B' merge --no-edit refs/pr/N
```

This document calls that flag **the text-merge flag**, and every merge command
below carries it. Since 2026-10-07 the bench also sets the same line in its
own config, so a command that drops the flag still merges as text.
`extensions.worktreeConfig` is on for the repository, and in the bench
`git config --get merge.wpindex.driver` must print the line above. Every other
tree reads the row merge from `.git/config`.

The line takes no `--diff-algorithm`. Apple's git 2.39.5 has no such option on
`merge-file`, and nor has 2.43. A driver git cannot start exits nonzero, and
git reports every merge that reaches it as a conflict. The flag carried
`--diff-algorithm=histogram` from 2026-10-01 to 2026-10-07. Rebuilt with it on
2026-10-07, main's last 60 merges gave 6 conflicts. Those were exactly the 6
merges that changed the index on both sides, and GitHub had merged all of them
clean. Without the option all 60 rebuilt to GitHub's tree. A false conflict
there sends step 4 to sync a branch that needed no sync.

The cost is the diff algorithm. Plain `merge-file` runs myers, while git's own
merge runs histogram, and the two disagreed on 6 of 1500 random merges. Under
the row merge the bench called clean the index conflicts GitHub reported on
#522, #546, #579 and #580. The histogram line reported all four, but it
reports a conflict on every two-sided index merge, so that check shows
nothing. They have not been re-checked under this line.

## Triage — the no-argument mode

One network call, no checkout, no diff:

```sh
gh pr list --state open --limit 30 \
  --json number,title,author,files,changedFiles,mergeStateStatus,latestReviews,headRefOid,updatedAt,statusCheckRollup,commits
```

- **Reviewable size is a jq filter over `files[]`**, excluding
  `^tests/data/|^src/rietx/data/` — never a diff (#125: 48,791 lines, 708
  reviewable).
- **`mergeStateStatus`, not `mergeable`**: `BLOCKED` PRs report `MERGEABLE`;
  `DIRTY` is the conflict, `CLEAN` the only state step 9 merges from.
- **`changedFiles` beside `files[]`**: the array caps at 100 and under-reports
  size and collision degree downward; when they differ, say so.
- **`latestReviews[].commit`** is the sha a *review* (not a comment) was posted
  at — what makes the `all` mode's skip check a field.
- **`commits[].messageHeadline` is the only place a contributor's WP work is
  visible**: a PR prefixing its commits `WP-NNNN:` edits no `docs/wp/` file, so
  `files[]` cannot see it (#98: 45 `WP-1118:` commits, every one of them in
  `src/` and `tests/`). The field carries each commit's *body* too: it took the
  call from 27 kB to 60 kB on a three-PR backlog, so read it through jq, never
  raw.

Print one row per PR — number, title, reviewable lines, merge state, CI,
whether a maintainer has commented — **and the reason for its rank**:

1. **Touches an in-flight WP** — `Status:` 🔄 in a `docs/wp/[0-9]*.md` the PR
   edits, **or** a `WP-NNNN:` commit prefix naming one. Either way a live
   session owns that WP's file.
2. **Outside PR edits `docs/ROADMAP.md` or `docs/wp/**`** — a governance
   question for the user (`CONTRIBUTING.md` § Maintainer-only machinery), cheap
   and blocking nothing. Author-conditional: on the maintainer's own PR it is
   the work. **The edits CONTRIBUTING hands a contributor are not the
   question**: a claim (the WP's `Status:` line set to `🔄 <date> — claimed by
   @…`, with `docs/wp/README.md` regenerated), and, for the work the PR does,
   a handover-log entry, ticked tasks, a moved `Status:` line and the
   decisions that work made (ruled 2026-10-29, on #1103 and #1140). Read the
   hunk; only what goes beyond those ranks here, and a `Status:` set to ✅ is
   beyond them, since closing the WP stays the maintainer's. A claim that
   merges leaves `Status:` reading "claimed" on main, so the step 9 handover
   entry is what rewrites it.
3. **`DIRTY`** — not a review: post a one-line rebase request and move on.
   A conflict on bookkeeping alone is the exception: step 4 syncs it, and the
   PR keeps its place. GitHub computes the field lazily; once main has moved
   since the call, `git -c merge.wpindex.driver='git merge-file %A %O %B' merge-tree --write-tree
   --name-only --no-messages origin/main refs/pr/N`, run in the bench, is the authority. Nonzero
   is a conflict, and the lines after the tree name the conflicted paths. It
   runs in the bench because any other tree's row merge hides an index
   conflict (§ Where this command runs).
4. **Collision degree** (files shared with other open PRs), ascending — every
   merge stales the diffs sharing a file with it.
5. **Reviewable lines**, ascending.

**Name every PR by another author first, above the ranked rows.** That means
an author outside `KNOWN_AUTHORS` in `.claude/skills/issue-review/backlog.py`,
which lists the maintainer and the recurring contributor. Such a PR keeps
its rank, but `all` does not merge it on its own authority: it goes to the
batch, named first (the maintainer asked for this on 2026-10-11).

List the maintainer's own open PRs, marked, last. Two limits, stated once: the
rank does not know which small PR unblocks unstarted work, and degree counts
files, not difficulty. The user overrules with arguments.

## Working the backlog — the `all` mode

Triage, then work the queue. Every disposition step 9 already calls clear-cut
is made as it is reached; everything else is **deferred to one batch at the
end**, never asked mid-run. `all` authorises step 9's merges and step 4's
bookkeeping syncs, and nothing beyond them.

**Pass A — no checkout**, straight off the triage call:

- `DIRTY` → rebase request; out of the queue. On step 4's bookkeeping files
  alone (rank 3's `merge-tree`) → stays in the queue, and step 4 syncs it or,
  finding an edit in a hunk, asks for the rebase then.
- Maintainer's own → one line (gated by `/wp-handover`); out. A ghostshift
  shift lead may also merge one its checks find clear-cut, under the user's
  standing permission of 2026-10-31
  (`~/Code/claude-config/skills/ghostshift/SKILL.md` §4).
- Touches an in-flight WP → **batch, do not review** (a live session's files
  are that person's call). The batch item carries the evidence: what the 🔄
  records (a session's claim, or only work that "landed from outside") and the
  WP file's last touch (`git log -1 -- docs/wp/NNNN-*.md`). A 🔄 kept open by
  the same contributor's earlier PRs is usually free, and the user answers in
  a word.
- Outside edit to `docs/ROADMAP.md` / `docs/wp/**` beyond the edits rank 2
  lists → question to the batch; the PR **stays** (its code
  half is reviewable).
- Touches an execution-shaped path (step 4's list) → batch.
- Already reviewed and nothing since → skip, naming the sha. Test:
  `latestReviews[].commit == headRefOid` **and** `updatedAt` no later than that
  review's `submittedAt` (keyed on the sha alone it skips forever a contributor
  who answered without pushing).

**Pass B — review what is left, in throughput order**: collision degree, then
reviewable lines (print the attention rank once; work this order). Steps 1-10
apply with five changes: conformance always goes to `pr-conformance` agents
(the run's length is the constraint, not one PR's size); step 6b's judge runs
once, after the last PR; a review held on a question (step 8) joins the batch;
step 9's "stop and ask" becomes "defer and continue"; the per-PR report
shrinks to its decision line.

**After every merge**: `git fetch origin main` and re-test every remaining PR
with `git merge-tree --write-tree origin/main refs/pr/N`, carrying the
text-merge flag — the field is stale
from the first merge on. The order is not recomputed, only the conflicts. A
conflict is handled as rank 3 handles `DIRTY`.

**Context checkpoint — between PRs only.** Compaction mid-diff loses the
reading, so stop at a PR boundary once the context nears **500 K tokens**. Read
the context off the transcript itself, whose assistant entries carry the
API's `usage`. The last one's `input_tokens + cache_creation_input_tokens +
cache_read_input_tokens` is the context that call saw:

```sh
python3 -c 'import json,sys
u=None
for l in open(sys.argv[1]):
    try: m=json.loads(l).get("message")
    except ValueError: continue
    if isinstance(m,dict) and isinstance(m.get("usage"),dict): u=m["usage"]
print(sum(u.get(k,0) for k in ("input_tokens","cache_creation_input_tokens","cache_read_input_tokens")))' \
  ~/.claude/projects/<cwd-slug>/<session-id>.jsonl
```

The id is the scratchpad's directory, and the slug is the directory the
session *started* in (the bench's own slug when it started there). Measure
before the first PR and at every boundary. Stop when the next PR's projected
delta would carry the total past 500 K. Without the usage field, `wc -c` is
the fallback: **500 K tokens was 4.3 MB** of transcript on 2026-09-29, when
the old 2 MB mark was only about 300 K. The ratio drifts from 5 to 9 bytes a
token as tool output accumulates, so give the fallback a PR's margin.
Ending means: ask the batch, apply the answers, write the report, kill this
run's waiters (step 5), and name the resume command (`/pr-review all` after
the user's `/compact` or `/clear`). Nothing is carried in a file.

**The batch**: one numbered message. Triage each question before it joins
(the maintainer's instructions, § "Before you bring me a decision"). A
question no trigger covers is settled in the run and listed at the batch's
end under "Settled for you": the choice, its grounds, the alternative. A run
without those instructions batches every question. Per item: the PR and what
it changes in plain words, the question, which trigger sent it, what it
blocks (held review / merge / nothing), and the recommendation with its
confidence (clear call, lean, close call). A clear call is one line: "I will
do X because Y, unless you object." A lean or close call adds why it
matters, ending in an importance word (minor, moderate, serious), the options
a competent person would choose, the practice it rests on, and the crux.
Each item reads without this run's context, so a WP number or a name the run
coined carries a gloss. Open with how many items need a judgement. Approving
the batch approves its posts; the triage decided their content. Group: PRs by other authors (§ Triage), then
governance calls, then tier rulings by class (step 6b), then reader-output
changes with their diffs (step 6c), then held reviews,
then held merges.
`AskUserQuestion` only for ≤ 4 genuine multi-way choices. Then apply in one
pass — post, merge, close — with a step-10 line each. **A gate main has moved
under is void**: before merging a freed PR compare `origin/main` with the sha
its ladder ran on; moved → rebuild the merged tree and re-run step 5 and the
slow suite, or defer to the next run, and say which. A stack's own merges
are the one exception: they move main toward the gated tree, not away from
it (step 9).

**Report** once for the run (step 10's shape), then the batch, then the resume
line if the checkpoint ended it. Close with
`Backlog: N merged, N posted, N rebase requested, N held, N remaining`.

## Reviewing one PR

1. **Read the thread once** — `gh pr view N --comments`; it is the record.
   Earlier rounds → review only `<last-reviewed-sha>..<head>`
   (`latestReviews[].commit`) and say which round. Once the branch has taken
   main in, by a rebase or a step-4 sync, that range carries main's changes
   too. Diff the two merged trees instead: `git diff A B`, where A and B are
   the trees `git merge-tree --write-tree origin/main` prints for the
   last-reviewed sha and for the head, each with the text-merge flag. A
   rebased branch whose last-reviewed sha no longer merges onto main needs
   the PR's own patch compared at the two shas instead, each against its
   merge base.
   On #546's rebased round 4 the range showed 14 files and the trees one,
   the regenerated index.
2. **Classify files before reading**: code / docs / gui / data, then
   `git diff BASE HEAD -- . ':(exclude)tests/data/*' ':(exclude)src/rietx/data/*'`.
   Never a bare `gh pr diff`.
3. **Data files by property, never content**: line and column count, header,
   file mode, a provenance row in `tests/data/README.md`, a
   `tests/validation_matrix.py` row where a standard is claimed, and a licence
   stated where it ships for anything under `src/rietx/data/` (root `CLAUDE.md`
   § Licensing). Nothing enforces any of this.
4. **Bench and merged tree.** One worktree, one venv; never one per PR.
   - **Read before you execute**: the bench runs the branch's code
     (`uv pip install -e .` runs its build config, pytest imports its
     `conftest.py`). Read every hunk to `pyproject.toml`, `setup.py`, any
     `conftest.py`, `.github/**`, `.claude/hooks/**` and `.claude/settings*.json`
     first; a workflow change is a question for the user, not a finding.
     **The rest of `.claude/` is text, not execution** — skills, commands and
     agent definitions are markdown the bench never runs, and treating the whole
     directory as execution-shaped batched three PRs that only sync markdown.
     They are read as part of the diff like anything else; what they can carry is
     an instruction aimed at whoever reads them, which is a conformance question
     rather than a reason to hold the PR out of review.
   - **Run from the bench, `cd` nowhere** — plain `git`, `npm --prefix gui`;
     `no_top_level_cd.py` refuses a bare `cd`.
   - **One `/pr-review` at a time**: the session-start hook names a live
     session already in the bench; a second one stops.
   - **The suite is shared with every WP session**: `ps aux | grep -c '[p]ython -m pytest'`
     before step 5 and again before step 9 (`tests/CLAUDE.md` § Running).
     Another mid-suite is a stop: wait.

   ```sh
   git fetch origin main
   git fetch origin "pull/N/head:refs/pr/N" --force
   git reset --hard origin/main
   git -c merge.wpindex.driver='git merge-file %A %O %B' merge --no-edit refs/pr/N
   git diff origin/main --stat        # the PR's own contribution
   ```

   Fetch into `refs/pr/N`, never `FETCH_HEAD` (it is per worktree; the named
   ref is what the round-2 diff and `merge-tree` want). `reset --hard` is the
   whole reset — never `git clean -fdx`, which takes `gui/node_modules`,
   `docs/docs/_generated`, `tests/output/`, any `*.rex/` and the venv. **The
   merged tree is the tree under test**: branch protection is `strict: false`,
   so nothing else ever tests it; a conflict here *is* the finding — report,
   ask for a rebase, stop. A conflict on bookkeeping alone is the exception,
   synced below. Venv:
   `uv venv --python 3.12 && uv pip install --python .venv/bin/python -e ".[dev,jax]"`
   (on an arm64 Mac `--python cpython-3.12-macos-aarch64-none`; `session_start.python_request`),
   reinstalled only when the PR touches `pyproject.toml`; `[dev,jax]` matches
   `nightly.yml`'s full job so counts compare and cross-backend rows pass
   rather than skip.

   **Sync a bookkeeping conflict yourself.** Three things take one entry per
   merged PR: the WP index, the schema number and the release staging file.
   Two PRs that each add an entry conflict however unrelated they are.
   GitHub refuses that merge too, but each resolves without judgement. A rebase
   request costs the contributor a round trip: on 2026-10-12 #888, #903 and
   #911 were rebased eight times, and every stated conflict was the schema
   number or a release note. Sync when `git diff --name-only
   --diff-filter=U` lists only the files below, every hunk in them is the
   kind described, and `gh pr view N --json maintainerCanModify` is true (9
   of 9 open fork PRs on 2026-10-01). Otherwise ask for a rebase.

   - **`docs/wp/README.md`**: regenerate it with `wp_index.py`.
   - **The schema number**, `src/rietx/schemas/common.py` and the pin in
     `tests/test_magnetic.py`. It moves once per release cycle (the comment
     above `SCHEMA_VERSION`, decided 2026-10-15). The first change after a
     release bumps it, and every later change adds an `Also in M` note under
     that number. So a sync never renumbers onto main. Read R, the number at
     the last release tag (`git show <tag>:src/rietx/schemas/common.py`), and
     M, main's number. Where M is R, main has not bumped this cycle, and the
     PR's own bump merges as written. Where M is past R, the PR's change
     shares M. Keep main's notes, then the PR's, its heading rewritten to
     `Also in M (<its WP or issue>)`. Drop a sentence in it that only
     coordinated the number with other open PRs, and say so in the review.
     In the pin's comment keep main's sentence and append the PR's item "in
     the same number". **Where the PR wrote a number P past M, set
     `SCHEMA_VERSION` and the pin's `assert` back to M by hand.** When the
     PR's base already carried M, its line merges clean at P, outside any
     conflict. **Every other line the PR adds that quotes P moves to M
     too**: a `_declared_since` stamp on a class it adds, a release note, the
     manual, a skill row. Those lines merge clean at P. A stamp at P makes
     `newest_declared_since()` decide which documents to walk from a number
     no document carries. The block's grep is whole-word: without `-w`, 0.50
     matched 0.500000E+01 in #911's GSAS fixtures.
     `INDEXING_THRESHOLDS_VERSION` in `src/rietx/schemas/indexing.py` moves
     the same way, with `Also <M>` notes and no pin. On 2026-10-30 #1107
     and #1123 both added 0.60 notes, and the sync kept both, #1123's first
     (`2da66e61`).
   - **`docs/releases/<next>.md`**, the staging file: keep both sides when
     every hunk only adds, main's lines first. `git checkout --conflict=diff3
     -- <file>` shows each hunk's base. An empty `|||||||` section is an
     append on both sides, as two notes under `## New` gave (2026-10-12).
     Anything in it is an edit, and an edit asks for a rebase. So does a
     file both sides created, whose whole base is empty.

   ```sh
   git merge --abort
   git checkout --detach refs/pr/N
   git -c merge.wpindex.driver='git merge-file %A %O %B' merge --no-edit origin/main     # conflicts on bookkeeping alone
   git diff --name-only --diff-filter=U           # the files to resolve
   python3 .claude/hooks/wp_index.py              # when the index conflicts
   # resolve the schema number and the staging file as above, then:
   git diff origin/main -- src/rietx/schemas/common.py | grep '^[-+]SCHEMA_VERSION'   # prints nothing once M was past R
   git diff -U0 origin/main | grep -n -w -F 'P'   # where P was past M: read every hit, now M
   git diff --check                               # no conflict markers left
   .venv/bin/python -m pytest tests/test_magnetic.py -k capability_flag_is_derived
   git add <each file resolved>
   git status --short                             # nothing modified beyond those
   git commit -m "Merge main; <what was synced, e.g. keep both M notes>" \
     -m "Synced with Claude Code on behalf of @yue-here."
   gh pr view N --json headRepositoryOwner,headRepository,headRefName
   git push https://github.com/OWNER/REPO.git HEAD:refs/heads/BRANCH
   git fetch origin "pull/N/head:refs/pr/N" --force
   ```

   Then rerun the block above from `reset --hard`. The push is a
   fast-forward, so it never needs `--force`. A rejected push means the
   contributor pushed in the meantime: fetch and start again. The push
   reruns CI, and step 9 waits for it to go green. Name the sync commit in the
   review, and say what it synced. Measured on #585 (2026-10-01): the
   synced head had no conflict markers, passed `wp_index.py --check` and
   merged clean onto main. Against main it changed only the PR's own 18
   files.
5. **Run the ladder the touched paths select**, every pytest with
   `-n auto --dist loadgroup`, from the bench:
   - **docs/docs only** → `test_docs_consistency.py`, `test_manual.py`,
     `test_manual_api.py`, the `-W` sphinx build.
   - **`gui/` only** → `npm --prefix gui ci && npm --prefix gui run build`,
     `git diff --exit-code src/rietx/gui/static`, `npm --prefix gui test`,
     `npm --prefix gui run check` (`gui.yml` is not a required check).
   - **`src/` or `tests/`** → the fast suite, then the slow tests covering the
     PR's area.
   - **always** → `.venv/bin/python -m ruff check src tests examples`.

   The slow selection is the point: `ci.yml` runs `-m "not slow"` and
   `nightly.yml` has no `pull_request` trigger, so acceptance never runs on a
   PR and CI green tells you little (#108's red got through that way). The
   **whole** `-m slow` suite fires once, at step 9. Quote counts with venv and
   platform, wall clock as a range, and whether anything else was running.
   **A backgrounded run is yours until you kill it**: before the run ends,
   `pgrep -f "$SCRATCH"` and kill every waiter this session started (seven
   orphans from a dead run were once found still polling the bench).
6. **Conformance against `CLAUDE.md`, sized to what the main session carries.**
   Everything the main session reads, every later request it makes re-reads at
   the cache-read price. A subagent's reading ends with the agent. Cache reads
   are nearly all of a review's bill, so delegate unless the diff is small *and*
   the session is young.
   - **Breakeven** (measured 2026-09-30 on three runs' transcripts, at Opus 5.5
     prices): a `pr-conformance` agent (Sonnet, ~38K base context) pays above
     ~100 reviewable lines. A general-purpose reader (~70K base) pays above
     ~200, falling toward ~100 once the main context passes 300K. Below those
     it is a wash, so read the diff yourself.
   - **Size of the saving:** a read-only Opus reader cost $2-3 a PR, roughly half
     what the same reading costs mid-run in the main session. Six PRs read
     in-session would have taken a 306K context past the context checkpoint.
   - **Sonnet saves less than its list price suggests:** its cache reads cost
     the same as Opus 5.5's, so it saves only on writes and output.

   To delegate, write the reviewable diff to `$SCRATCH` once and dispatch one
   `pr-conformance` agent per touched subtree, pointed at that file and the
   subtree's `CLAUDE.md`. Give each agent
   the PR's tree as files, `git archive refs/pr/N | tar -x -C
   "$SCRATCH/tree-N"`, never the bench: the bench holds whichever tree step 5
   is testing, and a PR based on current main is its own merged tree.
   **Verify every finding yourself before posting.** The breakeven already
   counts that check: about one main-session request per twelve the agent
   made. Do not restate invariants
   here; the
   classes outsiders miss most: a `Literal` member or defaulted field with no
   writer, physics without a citation, a correction offering an Rwp comparison
   as evidence, a reader repairing a file without a diagnostic, GPL-derived
   code, a diagnostic code or a measured operating rule with no agent-skill
   row (root CLAUDE.md § skill: the body, or the task shape's reference),
   physics with prose but no Theory-tab equation, a skill row telling
   agents to call a `caller` verb (it makes the verb a default path), a
   finding from one dataset written into a CLAUDE.md as a rule.
6b. **The generality audit table** (WP-2014). Every decision the package
   makes on its own has a row in `src/rietx/_audit.py` with a tier, and an
   author choosing their own tier is the self-certification the table exists
   against. Two triggers. `RIETX_CAPS_BASE=<the main it merged>
   .venv/bin/python -m tests.audit_delta`, run in the bench on the merged
   tree, lists row deltas; CI's lint step prints the same list in its
   summary. Or the diff adds a module-level number under an entry
   `_audit.NOT_WALKED` declares out (an added line matching
   `^\+[A-Z_][A-Z0-9_]* *(:[^=]*)?= *[-+0-9.(]`), which the walk cannot see.
   - **Propose a tier** for each row the author left at `unaudited`, and read
     again each row they put at 1 or `invariant`, the two tiers that need no
     ruling. Work from the constant's docstring, its call sites and
     `docs/milestones/generality.md` § The rule, and write each as the row
     it would be, with its evidence.
   - **Judge once per run.** Collect every PR's items in
     `$SCRATCH/generality-items.md`: per PR its diff file, its description,
     the printout and your proposed rows. Dispatch one `generality-review`
     agent over the whole file, after Pass B in the `all` mode and here for
     one PR. Verify each `fails` yourself before it goes public.
   - **Post the proposed rows** in the PR's step-8 review, each with the
     judge's one-line verdict. In the `all` mode that review waits for the
     judge and goes out in the apply pass.
   - **Tier-3 rows and tier-2 actions go to the batch, grouped by class**:
     one question for every row resting on the same evidence (WP-2002 ruled
     256 rows as 16 classes). After a ruling, write `grounds` and `approved`
     (the ruling's date) into the PR's rows. Push them to its branch where
     `gh pr view N --json maintainerCanModify` says true; otherwise ask the
     contributor in the review.
6c. **What a reader receives** (ruled 2026-11-01). The package should pass no
   junk back to a reader, a person or an agent, so every change to what a
   reader receives goes to the user before merge. A PR changes it when either
   holds:
   - `.venv/bin/python -m tests.reader_output`, run in the bench on the merged
     tree, exits 1. It prints the diff of one standard fit's printed result,
     report and diagnostics against the base (about 25 s).
   - The diff changes a result or report type's fields, which shows in the
     generated `docs/skill/rietx/references/api*.md`. A diagnostic code new
     to the audit table (step 6b's printout) counts too.

   Either way it is a question for the batch: the before and after text, and
   your reading of whether each added line tells this fit's reader something.
   A line that reads the same for every fit, repeats another field, or gives
   no action is the junk the ruling names. #1266 added 930 characters to every
   report that way, and it reached the user only because its author flagged it.
7. **`/code-review medium N`** for `src/` changes above step 6's ~200 lines;
   name the level (unnamed, it reuses whatever was typed last). **Never while a
   suite holds the bench**: the review forks into the session's working
   directory and checks the PR head out there. On 2026-09-29 that swapped the
   tree under a running full suite and voided it (the `ps` check of `tests/CLAUDE.md` § Running first,
   and `git log -1` after, back to the tree step 5 wants). Run it
   before step 5 starts, or between suites. Verify its findings as you do the
   agents', by reading the code and, where it is cheap, by running it.
8. **Two audiences.** *Public*, posted **as a review, from a file** (so the sha
   lands in `latestReviews[].commit`): what you checked independently and what
   it produced; a numbered "before merge" list; follow-ups kept separate; then
   `*Reviewed with Claude Code on behalf of @yue-here.*`
   ```sh
   gh pr review N --comment --body-file "$SCRATCH/review-N.md"
   gh pr merge N --merge --body "Reviewed with Claude Code on behalf of @yue-here."
   ```
   *Private*, in the terminal: what the PR is for and changes for a user, in
   plain language with no symbols in the opening paragraph; what ran; open
   questions. **Findings go public, questions come to the user** (design
   wanted at all? maintainer machinery edited?), and no review is posted while
   one is outstanding — in the `all` mode it is held for the batch.
9. **Merge only the clear-cut**, `gh pr merge --merge --body …`, when **all**
   hold: required checks green and `mergeStateStatus` `CLEAN`; the step-5
   ladder green on the merged tree, counts quoted; the **full `-m slow` suite
   green on the merged tree**, nothing else mid-suite, against the main that is
   there *now*; no execution-shaped file without the step-4 read; no
   conformance finding; every audit-table row tiered and every tier-3 row
   ruled (step 6b); no change to what a reader receives that the user has
   not seen (step 6c); no new public surface undocumented; every data file
   with provenance (and a licence if in the wheel); no maintainer-machinery
   edit; no open question. Name which each merge satisfied. **Say which PRs
   you merged**: `origin/main` moves under every live WP session. Close only
   when the contributor asked or the work was folded into another PR.
   Anything else stops and asks (`all`: defers).

   **Stack the clear-cut PRs that replay clean, and gate the stack once.** A
   full `-m slow` run costs 50-75 min on a 4-core box, so when several PRs
   have passed steps 1-8, replay their merges onto the bench in the order
   GitHub will merge them. Start from `origin/main` and run
   `git merge --no-edit refs/pr/N` with the text-merge flag, once per PR. GitHub tests each
   PR against the main the previous merge left, and the replay asks the same
   question with the bench's text merge. This is a merge queue built by hand,
   and like one it decides membership by the merged result, not by which
   files the PRs share.
   - **A conflict step 4 would sync stays in the stack.** Resolve it as step
     4 does, with the stack's lines standing for main's, then `git add` and
     commit. On GitHub, sync that PR once the PR before it has merged. Two
     schema changes in one stack take consecutive numbers in merge order.
     Replayed on #578, #579 and #580, the index path built the same tree as
     syncing each head and merging them in turn (2026-10-01). The final
     `git diff <stack-sha> origin/main` below is what shows a hand-resolved
     schema sync reproduced the replay's.
   - **Any other conflict drops the PR** (`git merge --abort`)
     with a rebase request.
   - **Before the gate, read every hand-written file that two stacked PRs
     both change**, as the stack combined it:
     `git diff origin/main HEAD -- <file>`. Each review saw only
     its own half of that file. A problem there drops the later PR and goes
     in its review. Intersect each PR's
     `git diff --name-only origin/main...refs/pr/N` to find the files. The
     index needs no read, because `test_the_wp_index_is_the_generators_output`
     checks it.

   Run step 5's suites and the slow gate once on that tree, and note its sha
   before any sync moves the bench. Then merge on GitHub in the replay's
   order. The last merge leaves `origin/main` content-identical to the tree
   the gate ran on: check it with `git diff <stack-sha> origin/main`, which
   must be empty, and say so in each review's "what ran". A PR whose review
   is still open stays out. A red stack is bisected before anything in it
   merges, by replaying it again without the suspect. On 2026-09-29 three PRs
   went in on one 76-minute full run instead of three.

   **And say which issues the merge closed.** Read
   `gh pr view N --json closingIssuesReferences` before merging. A PR that
   fixes an issue without linking it (a keyword in backticks, `/wp-handover`
   step 11) leaves the issue open with its fix on main; close it after the
   merge with a one-line comment naming the PR, in step 8's public register.
   One left open is what `/issue-review`'s landed column exists to find, so
   the miss costs a later round rather than the fix.

   **A merge that lands part of an in-flight WP owes that WP a handover entry,
   and nothing will ask for it.** Two ways in, and only the first is mechanical:
   the PR carries `WP-NNNN:` commits, **or** its content is a task an open WP
   declares and has not checked off. An outside contributor has no reason to
   prefix a commit or to edit a WP file, so the second way is invisible to every
   check there is — #248 is the GSAS `.PRM` half of WP-1118's unticked
   `.EXP`/`.PRM` task and names neither. Read the open WPs' task lists at step 1,
   not at merge. `session_start.py`'s order rule is satisfied by
   *any* later touch of the WP file and its date rule is day-dated, so a
   same-day session editing that file for its own reasons clears both: PR #98's
   45 `WP-1118:` commits merged (`0576726f`, 2026-09-01) with the WP file
   untouched and the scan stayed quiet, and the entry was rebuilt a session
   later out of `git log --stat`, which cannot recover a reason the diff does
   not state. Pay it here, where the reading still exists.
   `git fetch origin main`, branch off it, add a
   `### YYYY-MM-DD` entry to `docs/wp/NNNN-*.md` (the template's
   multi-session suffix when the day already carries one) naming the PR, its
   merge sha and what your review established — what the merge makes possible,
   what it deliberately does not, the gotchas you found — update the `Status:`
   line, and open it as a PR. Docs only, so no ladder; not yours to merge,
   being the maintainer's own. Then put the bench back where step 4 expects it
   (`git checkout --detach origin/main`), or the next PR's
   `reset --hard` rewrites the branch you just pushed. A WP a *live session* owns
   never reaches this step — rank 1 batches it on the two signals that mean
   someone is mid-edit — so the entry can never collide with a live session's
   log. A WP that is merely open reaches it often, and that is the case above:
   `Status:` 🔄 means the WP has unfinished tasks, not that anyone is holding it.
   Check before assuming either — for #248 the last touch of the WP file was six
   days back and its only worktree branch was already merged and gone.
10. **Report to the person**: the plain-language paragraph, then what ran, the
    open questions, the URL, and `PR N (<what it is, in plain words>):
    <decision>`, the decision exactly one of `merged`
    (`merged, handover PR M` where step 9's entry was owed),
    `closed`, `review posted`, `rebase requested`, `held, waiting on you`,
    plus `skipped (reviewed at <sha>)` and `deferred (<criterion>)` in the
    `all` mode. Kill this run's waiters first (step 5).
