# WP-2064 — An approval belongs to the value it approved

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P4 2026-10-30 — process: no number moves, and the judge already sees a retuned value at review; it closes a path where one passes without a fresh ruling

## Goal

A pull request that changes the value of an approved audit row fails CI until the row
carries an `approved` date later than the one at its base. A tier-3 number is then never
merged under an approval the maintainer gave to a different number.

## Context

**The gap.** `rietx._audit.Row.approved` is an ISO date, required on every tier-3 row and
every tier-2 action row (`tests/test_audit_table.py`, the `needs grounds and approved`
assertion). It is not tied to `Row.value`. `test_a_valued_row_holds_the_live_value` forces
the table's value to follow the tree, so a retune edits the row's value and leaves its date.
`tests/audit_delta.py` prints the change for the `generality-review` judge, and its docstring
says it "fails on one thing": a name new to `ROWS` at `unaudited`. Measured on 44de0f62a: all
142 tier-3 rows carry a date, and none is checked against its value's history.

**Practice.** An assessment belongs to the version it assessed. NASA-STD-7009A scores a
model's credibility per version. An architecture decision record that changes is
superseded by a new record. `docs/practice.md` § Grading the evidence behind a heuristic
has the survey (2026-10-30) and how each source was read.

**Where it goes.** `tests/audit_delta.py` already pairs base and head rows, renames
included, and reads the base by `git show` because the table test reads no git
(`rietx._audit`'s docstring says why). So the check is a second failure there: a row whose
`value` differs from its paired base row, with `approved` set at the base, fails unless the
head's date is later. It runs in CI's lint job, the same place as the first. A rename with
an unchanged value is not a retune.

**Two cases to decide while writing.** A row whose value moved and whose tier changed
from 3 to 1 or `invariant` needs no approval at all, so it passes. A tier-2 action row that
is retuned meets the same rule as a tier-3 one. The maintainer writes the date into a
contributor's branch (`CONTRIBUTING.md` § A heuristic needs its tier), so a failure message
names the row and says the maintainer's ruling is owed. It does not tell the author to
write the date.

**Tier of the rule added.** None: this changes a CI check, not a decision rietx makes.

**Where this came from.** The 2026-10-30 issue triage, asked whether the tier mechanism is
consistent with practice while answering #1224 (machinery before heuristics, adopted in
`CONTRIBUTING.md` the same day). Decided 2026-10-30: the tiers stay as they are; this WP
closes the one gap the survey found that is cheap to close.

## Non-goals

- A sensitivity or consequence column per row. It was considered and not taken
  (`docs/milestones/generality.md` § Decisions, 2026-10-20), and the survey did not reopen it.
- Expiring an approval with time. Nothing in the evidence says a date ages; a value does.

## Tasks

- [ ] `tests/audit_delta.py`: the retune failure, with its message naming the row, both values and the base date
- [ ] Tests: a changed value under an old date fails, a later date passes, a rename with the same value passes, a demotion to tier 1 passes; make the check fail once on purpose and read the message (`tests/CLAUDE.md` § Guards that go quiet)
- [ ] `CONTRIBUTING.md` § A heuristic needs its tier: one sentence saying a retuned value waits for a new ruling
- [ ] Skill: none. The check governs changing the package, and an agent driving rietx never edits the table

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_delta.py
.venv/bin/python -m tests.audit_delta
.venv/bin/python -m ruff check src tests examples
```

## References

NASA-STD-7009A (2016), Standard for Models and Simulations, via `docs/practice.md`.

## Handover log

- **2026-10-30** — created, from the 2026-10-30 issue triage (issue #1224). Checked against the tree at 44de0f62a: `Row.approved` is a date with no tie to `Row.value`, and `tests/audit_delta.py` fails only on a new `unaudited` name. No open WP owns it: 2017 measures the tier-3 thresholds and does not touch the guard, and 2014, which built the guard's outside-PR path, is closed.
