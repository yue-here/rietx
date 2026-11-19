# WP-2119 — the design record says how a design is chosen

Milestone: unscheduled · Status: ✅ 2026-11-07 — DESIGN.md Rule 5, choosing a design, approved as drafted by the maintainer
Track: The repo's own process
Depends on: —

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

- [x] The maintainer polishes the draft: the wording, and whether it is a new Rule 5 or
      folds into Rule 4 and § Why this package exists.
- [x] Check the polished text against past decisions before it lands: WP-1964's decisions
      (a) and (c), WP-1303's deletion of the second integration surface, and the 2026-11-04
      ruling that rietx takes no TOPAS aliases. Each should come out as it was decided,
      or the draft changes.
- [x] Apply it to `docs/DESIGN.md`, with a § History line if it supersedes a sentence.
- [x] Skill: none. The rule governs changing the package, not driving it.

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

- **2026-11-07** — The design record now says how rietx chooses between designs. It is
  Rule 5 of `docs/DESIGN.md`: three tests (convention, direction, practice) and an order for
  when they disagree. A session can now reach the maintainer's 2026-11-05 calls without the
  maintainer's chain of questions. Checking the draft against four past decisions found two
  places where it would have let a session decide the other way, and both are fixed. The
  maintainer approved the revised text as drafted (2026-11-07, in session).
  - *Done.* Rule 5 placed after Rule 4, and "Four" rules became "Five". No § History line,
    because no sentence is superseded. Rule 4's "A new API takes the shape the surface
    already has" stays, as Convention applied to an API.
  - *The check (task 2).* WP-1964 (a), the formula on a parameter: comes out as decided
    under the draft and the revision. The API's shape follows convention, so it is a `tie`
    command, and Claude's lean at the time ("wire `Parameter.expr`") would have been
    flipped. WP-1964 (c), the per-pattern variable: the draft asked a departure only to
    "name its reason", and the proposed extra refusal on `vars.*` globs had one. The
    revision asks for the likely mistake or the wrong number the convention would cause,
    and the refusal guarded an unlikely mistake, so it comes out as decided. WP-1303, the
    JSON surface: Direction and Practice both delete it, under either text. The 2026-11-04
    ruling on TOPAS aliases: "a name follows the field's standard term" could be read as a
    TOPAS keyword. The revision names the literature and the IUCr dictionaries and says one
    program's keyword is not that term.
  - *Other edits to the WP's draft.* "Four tests" became "three tests and an order". The
    maintainer's reason for Convention came back as one sentence (one shape sets fewer
    traps for a person or an agent). Direction covers work outside a milestone.
  - *Settled by Claude.* No separate "easiest for agents" test, because Rule 4's "A new
    API" already asks that a first call be right from the signature and docstring.
    `docs/milestones/generality.md:24` still says "the four rules", left as that
    milestone's dated record.
  - *Gotchas.* The session-start hook in the main checkout flagged WP-1334 and WP-1956 for
    repair. Both flags were stale: the checkout was 600 commits behind `origin/main`, where
    both WP files postdate their last commits.
  - *Next.* None. A convention found wrong later goes to its own WP under Rule 5 (Non-goals).

- **2026-11-05** — Filed at the maintainer's request, as a draft to polish. No open WP
  owns DESIGN.md's rules on choosing a design. Next: the maintainer's polish (task 1).
