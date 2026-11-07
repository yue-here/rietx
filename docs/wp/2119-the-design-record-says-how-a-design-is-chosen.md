# WP-2119 — the design record says how a design is chosen

Milestone: unscheduled · Status: 🔄 2026-11-07 — claimed by @yue-here
Track: The repo's own process
Depends on: —
Priority: P3 2026-11-05 — the maintainer stated how designs are chosen and DESIGN.md does not yet say it; sessions apply it today only through the maintainer's questions

## Goal

`docs/DESIGN.md` states how rietx chooses between designs: its own conventions first, the
stated direction over the single case, existing practice where it fits, and an order for
when these disagree. The maintainer has polished the wording and approved it.

## Context

**Where this came from.** On 2026-11-05 the maintainer answered two WP-1964 decisions
through a chain of questions. Does it follow rietx convention? What is the mechanism for?
Which is better for an agent calling rietx? How does the formula language work? Why not
Python? What do codes outside diffraction do? What is best practice for a code like ours?
The maintainer then stated the heuristics behind those questions. Claude critiqued them,
and the maintainer confirmed the result:

1. **rietx convention first.** Consistency reduces traps in the API, for human and AI
   users alike. Break from a convention only for a very good reason. The conventions are
   young, and some were set offhand. A convention found wrong is changed everywhere,
   which is still cheap at this stage.
2. **Understand the purpose.** A decision cannot be made without knowing what the thing is
   for and how it works. This governs how a decision is brought to the maintainer, so it
   belongs in the maintainer's own instructions and not in this file (Non-goals).
3. **Build towards the vision.** A design builds towards a cohesive direction but never
   pre-builds infrastructure that may never be used. Cases test a design. They never
   shape it.
4. **Reuse a good wheel.** Resources are limited, so rietx adopts existing best practice
   from any field and spends effort only on the decisions it must take. This is a
   guideline. It yields to accuracy and to the constraints a reused design must meet.
   WP-1964 built its own grammar because asteval and sympy fail two of them: safe
   loading and exact derivatives on every backend.

The order when they disagree, accepted the same day: the shape of the API follows rietx
convention; names and meanings follow the field's standard term; numbers follow accuracy.
WP-1964's decision (a) is the worked case. lmfit and TOPAS declare a formula on the
parameter, and rietx declares links with `tie`, so the formula became a command.

**What DESIGN.md says already.**

- § Why this package exists: "The API follows current Python practice". This covers part
  of point 4.
- Rule 3: "A rule whose only evidence is a run on rietx's own test data is the code's
  overfit in prose form and is cut." It covers the agent skill only.
- Rule 4, *A new API*: "It takes the shape the surface already has". This covers part of
  point 1 for a new call. It says nothing of a departure or of changing a convention.
- Rule 2 and the ruling that accuracy leads (maintainer memory) back "numbers follow
  accuracy".

**The draft** (for the maintainer to polish; placement is open, task 1):

> 5. **Choosing a design.** Four tests, in the order they yield to each other.
>
>    *Convention.* A change takes the shape rietx already uses for the same job. A
>    departure names its reason in the WP. A convention found wrong is changed
>    everywhere, in one change, and never broken in one place.
>
>    *Direction.* A design builds towards the milestone's stated direction. Cases test it
>    as acceptance rows. A design is not fitted to one case, and nothing is built before
>    a case needs it.
>
>    *Practice.* Where a good answer exists, in diffraction or elsewhere, rietx adopts it
>    and spends its effort on the questions practice leaves open. A practice yields to
>    accuracy and to the constraints a reused design must meet. The survey behind it is
>    in `docs/practice.md`.
>
>    *Conflicts.* The shape of the API follows rietx convention. A name or a meaning
>    follows the field's standard term. A number follows accuracy.

How a DESIGN.md sentence is written (maintainer memory, 2026-10-18): each rule is a test a
session can apply to a change, with what passes. Cut any sentence nobody would use to make
a choice, and check the draft against past milestones before presenting it.

## Non-goals

- How a decision is brought to the maintainer (point 2). That is the maintainer's global
  instructions, which live outside this repository. The line proposed on 2026-11-05 was:
  "State what the thing being decided is for and how it works, in plain words, before
  what could go wrong."
- Auditing existing conventions for ones that are wrong. A case found later goes to its
  own WP under the new rule.

## Tasks

- [ ] The maintainer polishes the draft: the wording, and whether it is a new Rule 5 or
      folds into Rule 4 and § Why this package exists.
- [ ] Check the polished text against past decisions before it lands: WP-1964's decisions
      (a) and (c), WP-1303's deletion of the second integration surface, and the 2026-11-04
      ruling that rietx takes no TOPAS aliases. Each should come out as it was decided,
      or the draft changes.
- [ ] Apply it to `docs/DESIGN.md`, with a § History line if it supersedes a sentence.
- [ ] Skill: none. The rule governs changing the package, not driving it.

## Acceptance

The maintainer approves the text in the PR. The docs checks pass:

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py
```

## References

- `docs/DESIGN.md` § Why this package exists, Rules 2-4.
- `docs/practice.md`.
- WP-1964's handover entry of 2026-11-05 (decisions (a) and (c)).

## Handover log

- **2026-11-05** — Filed at the maintainer's request, as a draft to polish. No open WP
  owns DESIGN.md's rules on choosing a design. Next: the maintainer's polish (task 1).
