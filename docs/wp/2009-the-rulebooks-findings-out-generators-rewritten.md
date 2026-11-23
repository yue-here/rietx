# WP-2009 — The rulebooks: findings out, and the rules that generate overfit rewritten

Milestone: generality · Status: 🔄 2026-11-22 — every task landed; the blind check of the reworded rules ran and its findings are fixed (PR #1768)
Track: The prose
Depends on: 2001 (2008 soft)
Priority: P3 2026-10-30 — was P4: the 2026-10-30 Inherited entry measures a cost every session pays (root alone about 21k tokens a request); a cost-only item with no user at the wall

## Goal

The five CLAUDE.md files (root, `gui/`, `tests/`, `src/rietx/io/`, `src/rietx/indexing/`)
and `docs/wp/TEMPLATE.md`'s priority rubric state rules a stranger needs, with the
one-dataset findings moved to the WP or milestone record they came from, and the rules
that reward adding a firing code rewritten to DESIGN.md § Rules, 1's three outcomes.

## Context

The rule is `../milestones/generality.md` § The rule. The second review's biggest finding:
the rulebook's *rules*, not its findings, generate the overfit. Two it named in root
CLAUDE.md: "A new correction ships with a record field or a diagnostic stating what it
changed" (2001 rewrites this one, before the audits) and `TEMPLATE.md`'s P1 rubric, "a
wrong number that nothing flags outranks one that raises", which ranks a silent number as
the worst outcome and so makes every new flag a P1 fix. Both reward a code that fires.
The rubric is right about severity and wrong as an incentive; the rewrite keeps the
severity class and names the *remedy* by Rule 1's kind: act and record where every
competent refiner would act, rank where the data can rank the alternatives, otherwise
report the number with its meaning. (A flat order, record field before diagnostic before
action, was the second review's wording; the maintainer replaced it on 2026-10-18,
because it points a session away from acting where Rule 1's first kind says act.)

**Findings as rules.** Protocol rule 4 already says a CLAUDE.md takes rules, not findings,
and `/wp-handover` step 7 audits each session's additions. What has accumulated anyway is
the compressed-evidence clause that reads as law: "holding it anyway cost 10 441 ppm on
that phase's cell", "7.2 % of one arm's is weighting", "un-gated, a background column
measured wrong by 49 % of its own scale". Each is one dataset's number, and each steers a
future session toward reproducing the mechanism that found it. The pass: for every clause
carrying a number, is the number the *rule* (a cap, a floor, a cited band) or the
*evidence*? Evidence compresses to a pointer at the WP or record that holds it.

**The evidence is paid for on every request** (maintainer, 2026-10-30, via the
claude-config workflow harvest). On `origin/main` at d35ffeda7 root CLAUDE.md was
86 001 B (12 700 words, about 21k tokens), loaded on every request of every session;
`gui/` 77 677 B, `src/rietx/io/` 51 398 B, `src/rietx/indexing/` 26 202 B and `tests/`
19 428 B load with their subtree, so an `io/` session carried about 34k, re-read by the
cache on each request. The ruling: a rulebook carries the rule and a one-clause reason;
incidents, shas and measurements go where a session reads them on demand. So the findings
pass covers every clause that is evidence, numbered or not, and the handover reports each
rulebook's bytes before and after beside the word counts. claude-config's
`workflow/LESSONS.md` took the same split that day, with an `EVIDENCE.md` beside it.

**The limits** (WP-2233, landed 2026-11-21). `tests/rulebook_limits.py` `LIMITS` holds a
(budget, ceiling) in bytes for all eight always-loaded documents, every budget pinned at
that day's bytes, so each rulebook is closed to growth; the line caps it replaced had
taken 35 raises and 2 cuts on root in eleven weeks. The re-landing lowers each budget to
the landed bytes and each ceiling by the same amount, in the same change as the cut: a
lowering is not a raise and needs no change of its own. A re-pin adds a paragraph to
`docs/milestones/process.md` § The caps diary. Never delete a fact to fit a limit: it
moves to the WP or record. `test_rulebook_paths_and_names_resolve` checks every path,
test and rietx `module.attr` name in the rulebooks, so a rewrite names live ones only.

**Outside PRs write findings into the rulebooks** (from WP-2014's filing, 2026-10-20):
four of twelve open outside PRs touching `_audit.py` edited a CLAUDE.md, some with
one-dataset findings stated as rules (#941, #1048). An outside PR never reaches
`/wp-handover` step 7, so the rule's wording goes into `/pr-review`'s list of what
outsiders miss as well as into the handover's audit.

**The register.** These files are agent-facing and may compress (the `yue-prose` skill
says so); the rewritten rules keep that register. A rule's *reason* stays as one clause
plus a pointer.

## Non-goals

- The skill: 2008.
- Adding a rule. This WP removes and rewrites.
- `docs/DESIGN.md`, the milestone records and the WP files: those are where findings go,
  not where they leave.
- `docs/manual/`: a user document, not a rulebook; 1986's.

## Tasks

- [x] The generator pass: every rule in the five files and the rubric that rewards a code
      that fires, listed with its rewrite to Rule 1's three outcomes; `TEMPLATE.md`'s
      rubric rewritten with the remedy named by kind.
- [x] The findings pass: every numbered clause classified rule or evidence; evidence
      compressed to a pointer, the number confirmed present at the pointer's target
      before it leaves.
- [x] The caps re-landed with diary lines.
- [x] `tests/test_docs_consistency.py` green; the rulebook word counts before and after in
      the handover.
- [x] `claude-config/workflow/LESSONS.md`: the lesson "a rulebook's incentives are audited,
      not only its facts", worded for the other projects, through `/workflow-sync`.
      Handed to the maintainer as paste text for a claude-config session (2026-11-22).
- [x] Skill: none; nothing here reaches an agent driving rietx.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
```

Plus a blind check of the rewritten rules: a fresh agent given the diff, not the author's
reading, names each rewording that changes what a rule tells an agent to do. A rewording
that amends one of the maintainer's rules or rulings goes to him; the rest are settled
(his routing rules of 2026-11-22, WP-2237, replacing a read by him of every rewording).

## References

- `docs/milestones/generality.md` § The two reviews; `docs/milestones/process.md` § The
  rule; ROADMAP § Session protocol rule 4; WP-1031, 1060, 1116 (the earlier consolidations).

## Moved from the rulebooks, with no other home

The findings pass confirmed each number at its pointer before cutting it. These seven
were absent there, or the target had moved on, so they are kept here verbatim (the last
three found by the blind check).

- Root `CLAUDE.md` (page-directory rule, WP-1461): "`.gitignore`, whose `*.html` has
  swallowed eight committed files." WP-1461 records the seventh only.
- Root `CLAUDE.md` (stacking rule, WP-1438): "at 420 px was nothing and 863 px of
  horizontal document scroll." WP-1438 holds 420 px and "document scrolled to 1283 px".
- Root `CLAUDE.md` (traced code, jax scoped fp64): a constant materialised outside the
  scope "once cost the Pawley aux columns four orders of accuracy." Found in no WP.
- `tests/CLAUDE.md` (measure the spread on the asserted quantity): "sized on `a` at
  2.5e-6, the same bar fired 12 days later on `c`, 7x wider and bit-identical across two
  runs." `tests/test_acceptance_srm676a.py` §3 now describes a different measurement.
- `tests/CLAUDE.md` (the WP-1059 rival-fit round): "Fitting each rival alone costs
  seconds; that round cost 1.7 M tokens." Not in `PROTOCOL.md` or WP-1059; WP-1063 has it.
- Root `CLAUDE.md` (bound test, WP-1434): a distance to the bound was "silent on nine of
  32 binding cases". WP-1434 records nine in 24.
- `src/rietx/indexing/CLAUDE.md` (line order, WP-1039): "NAC: 6 of the truth's lines in
  2θ order, 18 by intensity over a `SEARCH_POOL_MULTIPLE` low-Q pool." WP-1039 has the six
  only.

## Handover log

- **2026-11-22** — the blind check (WP-2237's session, under the maintainer's new routing
  rules). A fresh Opus agent read the diff without the author's reading, about 140
  rewordings. It found one rule deleted outright and six clauses whose instruction
  changed, all restored: "No pydantic in the hot loop"; the FPA fence's 2.8-4.2 FCJ images
  (a threshold, not evidence); the per-stage charge's 17.7 ms budget; "a writer that
  touches one entry per histogram inherits nothing" and "silently"; "declaring a thickness
  *correctly*"; "both halves stay written down". It also found the io gsas row now
  attributing the wrong GSAS-II bug (fixed to the ÷100), the gui pointer to WP-2134's
  style guide dropped (restored), and three numbers not at their pointers (now in § Moved).
  It judged "never `k`", "never a default" and io's "every format that states an axis"
  faithful to the old evidence. Root's refuse sentence was narrowed to a value stated in
  two units, with the bare-R case read and reported (WP-1911): six of six routing agents
  had read the old wording as refusing it. Byte pins re-set at the landed bytes: root
  77 573, gui 44 972, io 49 324, each ceiling moved by the same amount. With these fixes the
  last acceptance step is met; the WP can close.
- **2026-11-22** — the findings pass and the generator pass, all five rulebooks.
  The always-loaded rulebooks now carry rules and a short reason, and the one-dataset
  numbers behind them live in the WP or record each rule points at. Together they lost
  21 kB (235 kB to 214 kB), so a session working in `io/` reads about 8 kB less on every
  request, and root alone about 9.6 kB less. The generator pass found one rule that
  rewarded adding a code that fires, the priority rubric, and rewrote it to name the fix
  by Rule 1's kind; the five rulebooks themselves had none left after WP-2001. The cut is
  a third of what the policy guessed (10-12 %, not 33 %): each lane stopped where the next
  cut would have been a rule. Nothing changes what rietx computes.

  *Done.* Inherited folded into Context (all four entries still true). TEMPLATE.md's
  rubric: the severity class stays, and four sentences say it ranks the defect, never its
  fix, which takes DESIGN.md § Rules, 1's kind; a new flag is a fix only as the record of
  an action or as the third kind's report (review fix: the first draft read "third kind
  only", which would have refused a Diagnostic that records an action).
  `/wp-handover` step 7 now audits every committed CLAUDE.md and AGENTS.md and words the
  check as the 2026-10-30 ruling; `/pr-review` step 6's outsider class says the same. The
  findings pass ran as four lanes, each confirming a number at its pointer before cutting
  it; four sentences with no home there are kept verbatim in § Moved from the rulebooks.
  Byte limits re-pinned at the landed bytes, each ceiling lowered by the same amount;
  diary paragraph in `docs/milestones/process.md` § The caps diary.

  *Measured* (`wc`, this worktree, macOS arm64). Bytes before → after: root 86 787 →
  77 188; `src/rietx/io/` 55 732 → 49 292; `gui/` 45 159 → 44 892 (WP-2134 had already
  done this file); `src/rietx/indexing/` 27 747 → 24 935; `tests/` 19 733 → 17 707.
  Words: 12 826 → 11 141; 9 097 → 7 930; 6 601 → 6 555; 4 138 → 3 667; 3 141 → 2 769.
  `tests/test_docs_consistency.py`: 57 passed, `[dev]` venv, macOS arm64; no test was
  added or removed, so no count moved. Lanes (`session_usage.py lanes`): four, all kept
  without redo, re-read median 0K, 4 main requests a lane, actual/estimated requests
  0.75, saved +$2.33 (+14 % of the session); the selective policy's baseline row reads
  −20 % over the trial corpus.

  *Wording the maintainer reads.* Every rule whose wording moved beyond a deleted clause
  is listed in the PR body by file. Three a reviewer should look at first: root's opening
  line now says each rule carries "a one-clause reason and a pointer"; the `s`/`stol`
  convention's bold lead says "never `k`"; `tests/CLAUDE.md`'s spread rule lost its
  12-day `a`/`c` story (kept below the fold in § Moved).

  *Generality.* No row of `_audit.py` touched and no heuristic added, so the judge was not
  dispatched. `tests.reader_output` exit 0: nothing a reader receives changed.

  *Not done.* The LESSONS.md lesson is paste text for a claude-config session
  (`lesson-19-paste.md` in this session's scratchpad; the PR body quotes it). The rietx
  harvest marker there is `c220c00a` (29 Oct), so a later harvest would also find it.

  *Gotcha.* The lane policy's acceptance command carried `-q`, which with `addopts`'s own
  prints no summary; run it bare.

  Next (superseded by the blind check above): the maintainer reads the reworded rules in PR #1768. On approval the WP closes:
  delete `Priority:`, move this narrative to the v1.13 record, and mark ✅. If a rule's
  wording is reversed, fix it on the branch and record the reversal in memory.

- **2026-10-18** — created, from the milestone's opening session. Filed as P4 and last,
  because it changes no number; kept rather than folded because the second review found
  the incentive structure, not the findings, is what regenerates the overfit, and the
  maintainer agreed it is important.
