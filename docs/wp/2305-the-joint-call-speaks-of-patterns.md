# WP-2305 — The joint call speaks of patterns and is named a joint refinement

Milestone: series · Status: 🔄 2026-11-25 — claimed by @yue-here (ghostshift runner)
Depends on: —
Priority: P2 2026-11-23 — WP-2300's declaration says `per_pattern` to both calls, and the joint call it reaches still says histogram in its paths, its names and its prose

## Goal

The joint call and everything a user reads about it use one word for one measured dataset:
pattern. Its public names follow the literature's term, joint refinement. A name or a path
prefix a caller wrote before the change raises, naming its replacement.

## Context

**The rulings.** The maintainer ruled on 2026-11-23 that the joint fit's `hist.N.` dot-path
scope becomes `pattern.N.`, with the old prefix refused ("Rename, with refusal", recorded first
in WP-2300). He then handed the rest of the joint call's naming to Claude the same day: "you
make the calls. I don't care about sunk costs here, only about building the best api." The
calls below are settled by Claude under that instruction and DESIGN Rules 4 and 5.

**What changes for a caller.**

| Today | After |
|---|---|
| `rx.refine_multi(...)` | `rx.refine_joint(...)` |
| `rx.MultiHistogramRefinement` | `rx.JointRefinement` |
| `rietx.multi` (the module the manual cites) | `rietx.joint` |
| `hist.0.instrument.zero_shift` | `pattern.0.instrument.zero_shift` |
| "histogram" in docstrings, the manual, `help.py` and diagnostic messages | "pattern" |

The pairs then read as one family: `Refinement` and `refine`, `SequentialRefinement` and
`refine_sequential`, `JointRefinement` and `refine_joint`.

**Grounds.**

- *Name follows the literature's term* (Rule 5, conflicts). "Joint refinement" is the
  literature's phrase for fitting several patterns in one least-squares problem, as in joint
  X-ray and neutron refinement. "Multi-histogram" is GSAS's word and "multi-pattern" FullProf's
  (`NPATT`, `docs/practice.md` § Sequential refinement), each one program's keyword. rietx's
  manual already calls it the joint fit (`guides/joint.md`, `reference/joint.md`), and the
  series milestone calls it the joint call.
- *One idea, one spelling* (Rule 5, convention). The declaration's field is `per_pattern`
  (WP-2300), both calls take `PatternData`, and the series speaks of patterns. Keeping
  "histogram" in the joint call alone would break the convention in one place.
- *The likeliest misuse after a rename is the old name* (Rule 4). A removed name raises
  `AttributeError` naming its replacement, as NumPy 2.0 did for the names NEP 52 cut. A path
  or glob starting with `hist.` raises naming `pattern.`, because a plan glob that matches
  nothing is silent, so an old `"hist.*.instrument.*"` would otherwise free nothing without a
  word.
- *Cost.* No stored file holds a joint path: a joint fit keeps no history or project
  (`multi.py`, "a joint fit keeping no history"). On `bacb7d58b` the prefix had 338 uses
  across source, manual, examples and tests, and "histogram" 1 304 in the source, most in
  docstrings. Callers are few and in direct contact.

**Out of scope.** Internal names that no user types (`params/multi.py`, `MultiParameterTable`,
private helpers) follow only where the manual cites them. WP-2300's `Declaration` replaces
`SharingMap`, so this WP does not rename it.

**Order.** Before WP-2300, so the declaration is written once in the new names.

**Tier.** No heuristic is added; `_audit` gains no row. Diagnostic messages change wording,
so they are reader output and checked blind in the PR.

## Non-goals

- The declaration object (WP-2300).
- Verbs on a joint fit (WP-2103).
- Any change to what a joint fit computes: every number is bit-identical.

## Tasks

- [x] `refine_joint`, `JointRefinement` and the module `rietx.joint`; the old names raise
      `AttributeError` naming the new ones (a module `__getattr__`), with a test.
- [x] `hist.N.` → `pattern.N.` wherever a path is built, parsed or documented; a path or glob
      starting with `hist.` raises naming `pattern.`, with a test through a plan glob,
      `set_vary`, and a result lookup.
- [x] "histogram" → "pattern" in public docstrings, `help.py`, diagnostic messages, the manual,
      examples and the skill. `docs/contracts/schema.md` records the path change.
- [ ] Goldens and the cross-backend matrix unchanged in value; the joint acceptance tests pass.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_manual_api.py tests/test_help.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python -m tests.reader_output
```

## References

- [`../milestones/series.md`](../milestones/series.md) § The rules (1, 2).
- WP-2300 § Context, "The names".
- NumPy NEP 52 (2023), the removed-name error (`docs/practice.md` § How an API meets a
  caller's mistake).

## Handover log

- **2026-11-23** — filed by Claude at the maintainer's instruction to make the joint call's
  naming calls. The `hist.` rename moves here from WP-2300, which recorded it first, since it
  is one change with the class, function, module and prose renames and touches the same
  files. Facts checked on `bacb7d58b`.

  *Next:* the build, before WP-2300's.
