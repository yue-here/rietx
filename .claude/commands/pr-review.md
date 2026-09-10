---
description: Review outside pull requests — triage the backlog, or work it top-down: merge the clear-cut, batch every human call to the end
---

Review pull requests from outside the repository. `$ARGUMENTS`: PR numbers
(reviewed in the order given), `all` (work the whole backlog, § Working the
backlog), or empty (triage, print the ranked backlog, stop — never start on the
top row unasked).

Other people's PRs only. The maintainer's own are gated by `/wp-handover`
steps 6 and 9; a number naming one is still re-gated, but the governance
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
origin/main` plus step 4's venv line. From then on `BENCH=.` and the main
checkout is never named (`worktree_only.py` keeps it read-only anyway).

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
   the work.
3. **`DIRTY`** — not a review: post a one-line rebase request and move on.
   GitHub computes the field lazily; once main has moved since the call,
   `git merge-tree --write-tree origin/main refs/pr/N` (nonzero = conflict) is
   the authority.
4. **Collision degree** (files shared with other open PRs), ascending — every
   merge stales the diffs sharing a file with it.
5. **Reviewable lines**, ascending.

List the maintainer's own open PRs, marked, last. Two limits, stated once: the
rank does not know which small PR unblocks unstarted work, and degree counts
files, not difficulty. The user overrules with arguments.

## Working the backlog — the `all` mode

Triage, then work the queue. Every disposition step 9 already calls clear-cut
is made as it is reached; everything else is **deferred to one batch at the
end**, never asked mid-run. `all` authorises step 9's merges and nothing
beyond them.

**Pass A — no checkout**, straight off the triage call:

- `DIRTY` → rebase request; out of the queue.
- Maintainer's own → one line (gated by `/wp-handover`); out.
- Touches an in-flight WP → **batch, do not review** (a live session's files
  are that person's call).
- Outside edit to `docs/ROADMAP.md` / `docs/wp/**` → question to the batch; the
  PR **stays** (its code half is reviewable).
- Touches an execution-shaped path (step 4's list) → batch.
- Already reviewed and nothing since → skip, naming the sha. Test:
  `latestReviews[].commit == headRefOid` **and** `updatedAt` no later than that
  review's `submittedAt` (keyed on the sha alone it skips forever a contributor
  who answered without pushing).

**Pass B — review what is left, in throughput order**: collision degree, then
reviewable lines (print the attention rank once; work this order). Steps 1-10
apply with four changes: conformance always goes to `pr-conformance` agents
(the run's length is the constraint, not one PR's size); a review held on a
question (step 8) joins the batch; step 9's "stop and ask" becomes "defer and
continue"; the per-PR report shrinks to its decision line.

**After every merge**: `git fetch origin main` and re-test every remaining PR
with `git merge-tree --write-tree origin/main refs/pr/N` — the field is stale
from the first merge on. The order is not recomputed, only the conflicts.

**Context checkpoint — between PRs only.** You cannot see your context, and
compaction mid-diff loses the reading. Measure this session's transcript
(`wc -c ~/.claude/projects/-Users-yue-Code-rietx/<session-id>.jsonl`, the id
being the scratchpad's directory) before the first PR and at every boundary;
stop when the next PR's projected delta would carry the total past **2 MB**
(≈500 K tokens; uncalibrated — replace with what the first run measures).
Ending means: ask the batch, apply the answers, write the report, kill this
run's waiters (step 5), and name the resume command (`/pr-review all` after
the user's `/compact` or `/clear`). Nothing is carried in a file.

**The batch**: one numbered message; per item the PR, the question in one
sentence, what it blocks (held review / merge / nothing), and your
recommendation. Group: governance calls, then held reviews, then held merges.
`AskUserQuestion` only for ≤ 4 genuine multi-way choices. Then apply in one
pass — post, merge, close — with a step-10 line each. **A gate main has moved
under is void**: before merging a freed PR compare `origin/main` with the sha
its ladder ran on; moved → rebuild the merged tree and re-run step 5 and the
slow suite, or defer to the next run, and say which.

**Report** once for the run (step 10's shape), then the batch, then the resume
line if the checkpoint ended it. Close with
`Backlog: N merged, N posted, N rebase requested, N held, N remaining`.

## Reviewing one PR

1. **Read the thread once** — `gh pr view N --comments`; it is the record.
   Earlier rounds → review only `<last-reviewed-sha>..<head>`
   (`latestReviews[].commit`) and say which round.
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
   - **Target in the command, `cd` in a subshell** — `git -C`, `npm --prefix`,
     `(cd "$BENCH" && …)`; `no_top_level_cd.py` refuses a bare `cd`.
   - **One `/pr-review` at a time**: the session-start hook names a live
     session already in the bench; a second one stops.
   - **The suite is shared with every WP session**: `pgrep -f "[p]ytest"`
     before step 5 and again before step 9 (`tests/CLAUDE.md` § Running).
     Another mid-suite is a stop: wait.

   ```sh
   BENCH=.
   git -C "$BENCH" fetch origin main
   git -C "$BENCH" fetch origin "pull/N/head:refs/pr/N" --force
   git -C "$BENCH" reset --hard origin/main
   git -C "$BENCH" merge --no-edit refs/pr/N
   git -C "$BENCH" diff origin/main --stat        # the PR's own contribution
   ```

   Fetch into `refs/pr/N`, never `FETCH_HEAD` (it is per worktree; the named
   ref is what the round-2 diff and `merge-tree` want). `reset --hard` is the
   whole reset — never `git clean -fdx`, which takes `gui/node_modules`,
   `docs/manual/_generated`, `tests/output/`, any `*.rex/` and the venv. **The
   merged tree is the tree under test**: branch protection is `strict: false`,
   so nothing else ever tests it; a conflict here *is* the finding — report,
   ask for a rebase, stop. Venv:
   `(cd "$BENCH" && uv venv --python 3.12 && uv pip install --python .venv/bin/python -e ".[dev,jax]")`,
   reinstalled only when the PR touches `pyproject.toml`; `[dev,jax]` matches
   `nightly.yml`'s full job so counts compare and cross-backend rows pass
   rather than skip.
5. **Run the ladder the touched paths select**, every pytest with
   `-n auto --dist loadgroup`, from the bench:
   - **docs/manual only** → `test_docs_consistency.py`, `test_manual.py`,
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
6. **Conformance against `CLAUDE.md`, sized to the PR.** Under ~400 reviewable
   lines read the diff yourself; above it (the usual case) write the reviewable
   diff to `$SCRATCH` once and dispatch one `pr-conformance` agent per touched
   subtree, pointed at that file and the subtree's `CLAUDE.md`. **Verify every
   finding yourself before posting.** Do not restate invariants here; the
   classes outsiders miss most: a `Literal` member or defaulted field with no
   writer, physics without a citation, a correction offering an Rwp comparison
   as evidence, a reader repairing a file without a diagnostic, GPL-derived
   code, a diagnostic code or a measured operating rule with no agent-skill
   row (root CLAUDE.md § skill: the body, or the task shape's reference),
   physics with Part 1 prose but no Part 2 equation.
7. **`/code-review medium N`** for `src/` changes above the step-6 threshold;
   name the level (unnamed, it reuses whatever was typed last).
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
   conformance finding; no new public surface undocumented; every data file
   with provenance (and a licence if in the wheel); no maintainer-machinery
   edit; no open question. Name which each merge satisfied. **Say which PRs
   you merged**: `origin/main` moves under every live WP session. Close only
   when the contributor asked or the work was folded into another PR.
   Anything else stops and asks (`all`: defers).

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
   `git -C "$BENCH" fetch origin main`, branch off it, add a
   `### YYYY-MM-DD` entry to `docs/wp/NNNN-*.md` (the template's
   multi-session suffix when the day already carries one) naming the PR, its
   merge sha and what your review established — what the merge makes possible,
   what it deliberately does not, the gotchas you found — update the `Status:`
   line, and open it as a PR. Docs only, so no ladder; not yours to merge,
   being the maintainer's own. Then put the bench back where step 4 expects it
   (`git -C "$BENCH" checkout --detach origin/main`), or the next PR's
   `reset --hard` rewrites the branch you just pushed. A WP a *live session* owns
   never reaches this step — rank 1 batches it on the two signals that mean
   someone is mid-edit — so the entry can never collide with a live session's
   log. A WP that is merely open reaches it often, and that is the case above:
   `Status:` 🔄 means the WP has unfinished tasks, not that anyone is holding it.
   Check before assuming either — for #248 the last touch of the WP file was six
   days back and its only worktree branch was already merged and gone.
10. **Report to the person**: the plain-language paragraph, then what ran, the
    open questions, the URL, and exactly `PR N: <decision>` — `merged`
    (`merged, handover PR M` where step 9's entry was owed),
    `closed`, `review posted`, `rebase requested`, `held, waiting on you`,
    plus `skipped (reviewed at <sha>)` and `deferred (<criterion>)` in the
    `all` mode. Kill this run's waiters first (step 5).
