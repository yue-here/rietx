# WP-2009 — The rulebooks: findings out, and the rules that generate overfit rewritten

Milestone: generality · Status: 🔄 2026-11-21 — claimed by @yue-here
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
- [ ] `claude-config/workflow/LESSONS.md`: the lesson "a rulebook's incentives are audited,
      not only its facts", worded for the other projects, through `/workflow-sync`.
- [ ] Skill: none; nothing here reaches an agent driving rietx.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
```

Plus a read by the maintainer of the rewritten rules, since a rule's wording is a
decision (`~/.claude/CLAUDE.md`: a plan sent for approval opens with its context).

## References

- `docs/milestones/generality.md` § The two reviews; `docs/milestones/process.md` § The
  rule; ROADMAP § Session protocol rule 4; WP-1031, 1060, 1116 (the earlier consolidations).

## Moved from the rulebooks, with no other home

The findings pass confirmed each number at its pointer before cutting it. These four
were absent there, or the target had moved on, so they are kept here verbatim.

- Root `CLAUDE.md` (page-directory rule, WP-1461): "`.gitignore`, whose `*.html` has
  swallowed eight committed files." WP-1461 records the seventh only.
- Root `CLAUDE.md` (stacking rule, WP-1438): "at 420 px was nothing and 863 px of
  horizontal document scroll." WP-1438 holds 420 px and "document scrolled to 1283 px".
- Root `CLAUDE.md` (traced code, jax scoped fp64): a constant materialised outside the
  scope "once cost the Pawley aux columns four orders of accuracy." Found in no WP.
- `tests/CLAUDE.md` (measure the spread on the asserted quantity): "sized on `a` at
  2.5e-6, the same bar fired 12 days later on `c`, 7x wider and bit-identical across two
  runs." `tests/test_acceptance_srm676a.py` §3 now describes a different measurement.

## Handover log

- **2026-10-18** — created, from the milestone's opening session. Filed as P4 and last,
  because it changes no number; kept rather than folded because the second review found
  the incentive structure, not the findings, is what regenerates the overfit, and the
  maintainer agreed it is important.
