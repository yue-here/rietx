# WP-2038 — The softening: unanimity for a recorded, cheap-to-undo default, a brief and not a change

Milestone: generality · Status: ⬜
Track: The registry and the guard
Depends on: 2037 soft (its clause 1 is why the two questions separate)
Priority: P4 2026-10-23 — nothing in it can start until the maintainer answers the two questions in Context, and it changes no number until a brief exists; P2 if the answer to the first is yes

## Goal

A brief the maintainer can rule on, with three worked cases from the tree, or a dated
note that fewer than three exist and the idea closes. No change to DESIGN.md § Rules 1
or to the generality record is made by this WP; the brief proposes one and the ruling
decides.

## Context

Deferred from WP-2037's proposal on 2026-10-23 by the maintainer's ruling: it reopens
the fourth review for a reason unrelated to attention and gets its own brief. This file
records what the idea is, what it reopens and what a brief must contain. Nothing here is
proposed yet.

**The idea.** [DESIGN § Rules](../DESIGN.md#rules), 1 lets the package act alone only
where every competent refiner would take the same action. The gate is unanimity: one
named dissenter moves the action to a ranking or a report. The softening would split
the gate by the cost of being wrong. A default that is **recorded in a field and undone
by one call** would need only "most careful refiners, most of the time"; unanimity would
stay the bar for an action the caller cannot see in the result or cannot undo without a
rerun (a write into history, a repair of a file, a quarantine that seeded no successor).
The reason offered: a wrong default costs more the harder it is to catch and reverse,
and the token rule already says a package that decides nothing can cost the caller more
than one wrong-but-reversible decision.

**What it reopens.** The fourth review ([generality § The fourth
review](../milestones/generality.md#the-fourth-review-2026-10-18), § Decisions) replaced
visibility with judgement as the second ground, on the argument that what rietx returns
is rietx's choice, any action can be reported as its statistic instead, and so "could
the caller see it" sorted items by whether a record field happened to exist. The
softening puts reversibility back as a ground. A brief has to answer that argument head
on. The honest form of the answer is that reversibility is not visibility: a field makes
an action visible, but whether undoing it costs one call or a rerun is a property of the
action, and the fourth review did not weigh that property. The line is also one
DESIGN.md says does not move as agents improve, so the brief must show the softening
moves it for a reason about the action's cost, never about the caller's competence.

**Two questions for the maintainer, before anyone writes it.**

1. Is reversibility a property the gate should weigh at all, given the fourth review's
   reasoning? If not, this WP closes 🛑 and nothing is lost.
2. If yes, who names "most careful refiners": the implementing agent, the judge, or the
   seven programs' defaults? Tier 2 already counts program defaults as evidence of
   unanimity and lets one dissenter outweigh them. The softening would have to say how
   many dissenters it tolerates and on what evidence.

**Why it is separable from WP-2037.** Under 2037's clause 1 a softened default lands in
a record field and costs no attention, so the softening is a question about the
decision line alone; 2037 neither needs it nor is changed by it.

### Inherited

- 2026-10-31, WP-2010's consistency read of the rule set (#1190): Rule 1's text already
  disagrees with rulings and rows for the defaults a fit cannot run without. Rule 1 lets
  a kind-2 ambiguity pick only on a caller's request or a unanimous margin, and a kind-3
  one report and stop. Yet `ProfileTCHZ:shape` (kind 2, tier 2, `tchz_pv`) and
  `auto_background:kind` (kind 2, tier 3, `pspline`) are picked on every default fit, and
  `Source:polarization` (kind 3, tier 3) runs at 0.5, recorded as assumed. The
  2026-10-21 ruling (`generality.md` § The rule, tier 2: a dissenter keeps a default at
  tier 2, and rietx chooses from inside the range of practice) is a fourth outcome Rule 1
  does not list, and the judge's question 5 applies it. Measured at 091600955: 126
  default rows, 81 audited, 4 at kind 2 or 3. That is a contradiction to resolve
  whatever the answer to question 1, so it is the brief's first worked case.

## Non-goals

- Any change to Rule 1, the record or the audit table from this WP.
- Diagnostic levels, rendering, the deliverable vocabulary: WP-2037.
- A ruling on any single tier-3 item: its audit's batch.

## Tasks

- [ ] The maintainer's answers to the two questions, dated into this file; on a no to
      the first, close 🛑 with the reason.
- [ ] A measurable definition of cheap to undo (candidates: the off state is one
      argument and reproduces every number bit-identically; no history node is written;
      no file is changed). A definition that needs judgement to apply is not one.
- [ ] Three worked cases on the tree: an action that fails unanimity today on a named
      dissenter, is recorded in a field, and is cheap to undo by that definition. Each
      opens with the record's stakes line (the reported quantity, the case on disk, the
      distance from reference, the dissenter). Where to look: `rietx._audit` rows whose
      grounds name a dissenter, and 2003's chain actions. Fewer than three: say so, and
      close.
- [ ] The cost side, measured: the rate at which "most careful refiners" are wrong on the
      three cases, from the families, beside the rerun each wrong default costs and the
      rerun a withheld one costs every time.
- [ ] The brief, with the gate's two readings applied to each case and the ruling each
      gets under each; the maintainer's ruling dated here and, if adopted, carried into
      DESIGN.md § Rules 1 and the record by a follow-up WP named here.
- [ ] Tests: none unless the ruling changes the rule; then the follow-up's.
- [ ] Skill: none; a decision-line change reaches the skill through 2008.

## Acceptance

The brief exists with three cases and the maintainer's dated ruling, or the WP is
closed 🛑 with the dated reason. No code moves.

```sh
python3 .claude/hooks/wp_index.py --check
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
```

## References

- `docs/DESIGN.md` § Rules 1; `docs/milestones/generality.md` § The rule, § The fourth
  review, § Decisions (2026-10-18, "the second ground is judgement, superseding
  visibility").
- WP-2037 (the proposal it was cut from), WP-2001 (the rule written down), WP-2003.

## Handover log

- **2026-10-23** — created as a stub from WP-2037's § Not proposed. No open WP owns a
  change to Rule 1's gate: 2001 wrote it and closed, 2009 rewrites the rulebooks that
  cite it and does not move it. Filed at P4 because it waits on two answers only the
  maintainer can give.
