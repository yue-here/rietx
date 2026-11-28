# WP-2303 — A glob a caller passes that matches nothing says so

Milestone: unscheduled · Status: 🔄 2026-11-28 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: — (2300 soft: it owns how a series declares a parameter fixed)
Priority: P2 2026-11-23 — a misspelt glob in `hold` holds nothing and the parameter refines, with no word; the workaround is reading the return value

## Goal

`set_vary`, `hold`, `unhold`, `untie` and `tie_equal` warn when a pattern the caller passed
matches no parameter. A plan's globs stay silent. A call that matched rows but changed none,
such as a repeated `hold`, stays silent too.

## Context

**The rule.** [DESIGN § Rules](../DESIGN.md#rules), 4, amended 2026-11-23: "A pattern the
caller passed that matches nothing warns. A pattern skips the rows it cannot change without a
word when it changed others." Rule 5: a convention that lets a caller's likeliest mistake pass
in silence is a convention found wrong, and is changed everywhere in one change. The review is
[`2302-batch/plans.md`](2302-batch/plans.md), Plan 2 C.

**Today** (measured 2026-11-22 on `f9adf0e57`). `Refinement.set_vary("phases.0.cel.*")` and
`Refinement.hold("phases.0.cel.*")` both return `[]` with no warning. A literal path the model
lacks already raises with the nearest path (WP-1951). `set_vary` already warns when a request
changes nothing it named for a retired spelling or a declined row (issue #896); extend that
channel rather than adding one. `set_vary`'s docstring gives WP-1414's reason for the silence:
a plan's glob may reach a component the model does not declare. That reason holds for plans
only.

**Why the public verbs can warn without touching plans.** A stage reaches the table directly,
`table.set_vary(stage.turn_on, True)` in `_run_stage` (`refine.py:5206` at `f9adf0e57`), not
the public verb.

**Internal callers of the five public verbs**, each to be read before the warning lands
(found by the blind review, `f9adf0e57`): `gui/session.py:1867, 1870, 4210`,
`gui/textdoc.py:1318`, `report/layer2.py:1434`, `strategy/parameter_interval.py:277`,
`strategy/fraction_profile.py:216`, `strategy/magnetic.py:1369`, `sequential.py:1286`. A
caller whose glob may legitimately match nothing goes through the table, or passes the globs
it knows exist. The GUI's callers need the GUI's own message channel, since a GUI user never
sees a python warning.

**Matches nothing and changes nothing are different.** `hold`'s docstring returns `[]` on a
repeat call. Warn only when no entry matched any pattern the caller passed.

**In the probe** (2302-batch/plans.md), all three agents that implemented a `hold` kept the
empty glob silent, copying the toy's `set_vary` docstring, and no reviewer flagged it. New code
copies this convention, so it is fixed everywhere at once.

Tier: none. The warning reports a fact about the call.

## Non-goals

- What `set_vary(path, False)` means through a plan: WP-2300.
- Literal paths, which already raise.
- A plan's globs, which keep WP-1414's silence.

## Tasks

- [ ] Read each internal caller above; route those that may match nothing through the table.
- [ ] Warn on a caller's pattern that matches nothing, in the five verbs, through the
  existing `_set_vary_findings` channel; keep "matched, changed nothing" silent.
- [ ] The GUI callers report the same fact in the GUI's message channel.
- [ ] Count warnings the change adds to the fast suite before and after; each new one is either
  a real typo in a test (fix the test) or a caller to route.
- [ ] Tests: each verb warns on an empty match, stays silent on a repeat and on a plan.
- [ ] Skill: a trap row only if the skill describes these verbs as silent; else none.

## Acceptance

`hold("phases.0.cel.*")` warns naming the pattern. `hold` twice on one path returns `[]` and
does not warn. A default-plan fit emits no new warning.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow" -W error::UserWarning -k "hold or vary or tie"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Russell, R. (2008), "How Do I Make This Hard to Misuse?", ozlabs.org/~rusty, 30 March.

## Handover log

- **2026-11-23** — created from the API review (2302-batch/plans.md). No open WP owns the
  glob verbs' silence: WP-2300 owns how a series declares a parameter, and WP-1435's hold is
  closed. Next: read the internal callers.
