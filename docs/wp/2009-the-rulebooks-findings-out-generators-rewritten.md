# WP-2009 — The rulebooks: findings out, and the rules that generate overfit rewritten

Milestone: generality · Status: ⬜
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

**The caps.** Every always-loaded rulebook is capped (`tests/test_docs_consistency.py`,
diary in `docs/milestones/process.md`). Moving findings out lowers the landed count; the
cap then lands at the new count plus the headroom the diary records, in a commit that says
so. Never delete a fact to fit a cap: it moves to the WP or record.

**The register.** These files are agent-facing and may compress (the `yue-prose` skill
says so); the rewritten rules keep that register. A rule's *reason* stays as one clause
plus a pointer.

### Inherited

- **2026-10-30, from the maintainer, via the claude-config workflow harvest: the evidence is paid for on every request.** Sizes on `origin/main` at d35ffeda7: root CLAUDE.md 86 001 B (12 700 words, about 21k tokens at 4 B a token), loaded on every request of every session. `gui/` 77 677 B, `src/rietx/io/` 51 398 B, `src/rietx/indexing/` 26 202 B and `tests/` 19 428 B load with their subtree, so an `io/` session carries about 34k. The cache re-reads all of it on each request: root alone is about 2.1M tokens per 100 requests. The maintainer's ruling: a rulebook carries the rule and a one-clause reason; incidents, shas and measurements go where a session reads them on demand. The findings pass therefore covers every clause that is evidence, numbered or not, and the handover reports each rulebook's bytes before and after beside the word counts. claude-config's `workflow/LESSONS.md` took the same split on 2026-10-30, with an `EVIDENCE.md` beside it.
- **2026-10-20, from [2014](2014-a-heuristic-meets-the-judge-on-every-path.md)'s filing: outside PRs write findings into the rulebooks.** Four of the twelve open outside PRs that touch `_audit.py` edit a CLAUDE.md (three `src/rietx/indexing/`, one `src/rietx/io/`), some with one-dataset findings stated as rules: #941 adds "magnetite's wrong P description bought a negative background and read 0 of 163 absent", #1048 a NAC line count. After this WP's findings pass, only `/wp-handover` step 7 audits a rulebook edit, and an outside PR never reaches it. 2014 adds the class to `/pr-review`'s list of what outsiders miss; this WP owns the rule's wording, so word it for `/pr-review` as well as for the handover.

## Non-goals

- The skill: 2008.
- Adding a rule. This WP removes and rewrites.
- `docs/DESIGN.md`, the milestone records and the WP files: those are where findings go,
  not where they leave.
- `docs/manual/`: a user document, not a rulebook; 1986's.

## Tasks

- [ ] The generator pass: every rule in the five files and the rubric that rewards a code
      that fires, listed with its rewrite to Rule 1's three outcomes; `TEMPLATE.md`'s
      rubric rewritten with the remedy named by kind.
- [ ] The findings pass: every numbered clause classified rule or evidence; evidence
      compressed to a pointer, the number confirmed present at the pointer's target
      before it leaves.
- [ ] The caps re-landed with diary lines.
- [ ] `tests/test_docs_consistency.py` green; the rulebook word counts before and after in
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

## Handover log

- **2026-10-18** — created, from the milestone's opening session. Filed as P4 and last,
  because it changes no number; kept rather than folded because the second review found
  the incentive structure, not the findings, is what regenerates the overfit, and the
  maintainer agreed it is important.
