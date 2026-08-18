---
description: End-of-session WP handover — record everything, verify, open the PR, report ready for /clear
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

1. **Identify the active WP** from this session's `git log` (`WP-NNNN:`
   prefixes). If more than one WP was touched, confirm with the user before
   proceeding.
2. **Tick landed tasks** in the WP file's checklist — every commit that
   landed should correspond to a checked item.
3. **Prepend the dated handover entry** to the WP's `## Handover log`
   (newest first): done / in flight / next / gotchas. Write it for a
   successor who has read only this WP file and CLAUDE.md.
4. **Sync the Status line** (`glyph date — free text`, vocabulary in
   `docs/wp/TEMPLATE.md`) and mirror the glyph in the WP's ROADMAP index
   row.
5. **Push forward references**: anything learned that changes work in a WP
   that is not closed and not this one goes into *that* WP's `### Inherited`
   section, naming this WP as the source.
6. **Audit this session's CLAUDE.md edits** (root, `gui/`, `tests/`,
   `src/rietx/indexing/`): every added line must be a standing rule
   (protocol rule 4 — evidence compressed to a clause plus a pointer), never
   a dated finding. Counts and timings this session measured go **in the
   handover entry** (root CLAUDE.md § Numbers is a recipe, not a ledger),
   and run the count check there: passed+skipped moved by exactly the tests
   this session added, in both the fast and full selections, and any new
   skip is named as a skip, not a pass.
7. **If the WP is closing** (✅/🛑): delete its consumed `### Inherited`
   section, rewrite ROADMAP's "Current focus" for the successor (within
   `CURRENT_FOCUS_CAP`, tests/test_docs_consistency.py), and MOVE the
   outgoing focus narrative to the in-flight milestone record
   (`docs/milestones/v1.0.md` § "How v1.0 is getting here").
8. **Sweep session memory notes**: anything in the assistant memory
   directory that corrects or extends the repo record gets ported into the
   repo now — a memory note is not a channel to the next session's repo
   state.
9. **Verify**: run
   `.venv/bin/python -m pytest tests/test_docs_consistency.py -q` and
   `.venv/bin/python -m ruff check src tests examples`; confirm the working
   tree is clean and pushed (or say what deliberately is not).
10. **Open or update the pull request.** A session's work is not handed over
    until it is reviewable, so the PR is part of the ritual rather than a
    follow-up request. Skip it — saying so in one line — when the branch is
    `main`, when `git log origin/main..HEAD` is empty, or when the branch is
    already merged (repair mode usually lands here).
    - Check first with `gh pr view --json url,state`: an existing open PR for
      this branch is **edited** (`gh pr edit --title --body`), never
      duplicated.
    - Title mirrors the lead commit: `WP-NNNN: <what landed>`.
    - Body is the handover entry **rewritten for a reviewer**, not pasted:
      what landed and why, what it measured (with the venv **and** platform,
      per `tests/CLAUDE.md` § Quoting numbers), what it deliberately did not
      do, and any finding filed into another WP, named with its number. End
      with the repo's two-line Claude Code footer.
    - **Never merge, and never wait on CI to decide.** Whether green is
      enough, and when to merge, is the maintainer's call.
11. **Report**: the PR URL, and that CI is the gate — the required checks run
    ruff plus the fast suite across the supported Pythons and a `[dev,jax]`
    job. Offer to watch the run rather than assuming; when you do watch, read
    state from `gh run list` (REST) rather than `gh pr checks` (GraphQL, which
    has 503'd through a GitHub incident while runs kept reporting), and read a
    sub-minute failure as one that never reached repo code. Only when step 9
    is green, end with exactly: **ready for /clear**.
