# WP-2064 — An approval belongs to the value it approved

Milestone: unscheduled · Status: ✅ 2026-11-16 — CI's audit delta fails a retune under its old approval (PR #1601)
Track: The repo's own process
Depends on: —

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

- [x] `tests/audit_delta.py`: the retune failure, with its message naming the row, both values and the base date
- [x] Tests: a changed value under an old date fails, a later date passes, a rename with the same value passes, a demotion to tier 1 passes; make the check fail once on purpose and read the message (`tests/CLAUDE.md` § Guards that go quiet)
- [x] `CONTRIBUTING.md` § A heuristic needs its tier: one sentence saying a retuned value waits for a new ruling
- [x] Skill: none. The check governs changing the package, and an agent driving rietx never edits the table

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_delta.py
.venv/bin/python -m tests.audit_delta
.venv/bin/python -m ruff check src tests examples
```

## References

NASA-STD-7009A (2016), Standard for Models and Simulations, via `docs/practice.md`.

## Handover log

- **2026-11-16** — review fix-ups on PR #1601 (a ghostshift runner, from a read-only review).
  The head tiers that pass a retune without a later date are now the WP's own two, tier 1 and
  `invariant` (`NEEDS_NO_APPROVAL`, replacing `needs_approval`); a retune that demotes the row
  to tier 2 or `unaudited` fails until a later date, with a test. The new-name pairing places
  every exact rename before the retune pairing, so a split of one approved row reads the same
  whichever name sorts first, with a test. The docstring now says a same-day date fails, and
  that the pairing is by leaf. The tier list is the same in the docstring, the v1.12 record and
  WP-2017's forward note. `tests/test_audit_delta.py` is 25 passed (two tests added).

- **2026-11-16** — closed, all four tasks landed (PR #1601; a ghostshift runner, one session).

  A pull request can no longer carry a tier-3 number into `main` under an approval the
  maintainer gave to a different number: CI's audit delta now fails it until the row carries a
  later date, and the failure says the maintainer's ruling is owed. The WP's two cases are
  settled as written: a value moved together with a tier that needs no approval passes, and a
  tier-2 action meets the tier-3 rule. A change with no such retune prints and exits exactly as
  before, so nothing open moves; it costs one more paired-row comparison per run.

  *Done.* `tests/audit_delta.py`: `RETUNED`, its `(FAILS)` group, `needs_approval` (tier 3 or a
  tier-2 action, the predicate of `test_audit_table.py`'s `needs grounds and approved`),
  `retuned_under_old_approval`, a message naming the row, both values and the base date, and a
  `::error` annotation. The summary line gains `, N retuned under an earlier approval` only when
  N > 0; retunes still count under `changed`. Exit codes unchanged (1 on any failure). Seven new
  tests in `tests/test_audit_delta.py`; one sentence in `CONTRIBUTING.md`.

  *Decided while writing (the WP's two cases, and two it did not name).* "Needs no approval"
  is the WP's own list, tier 1 or `invariant` (`NEEDS_NO_APPROVAL`); a retune that demotes the
  row to tier 2 or `unaudited` still fails until a later date, since the demotion is itself a
  ruling (narrowed at review: the review fix-up entry). The tier-2 action arm is vacuous today, since
  `test_audit_table.py` holds every action's value at None; the test gives an action a value to
  show the rule reaches it. "Later" is strict, as the Goal says: a retune ruled on the day of
  the old approval needs the next day's date. From the diff review: renames pair only at an
  equal value, so a row renamed and retuned in one change read as an addition plus a deletion
  and passed; a new name now pairs with a deleted one of the same kind and leaf for this check
  alone, and only when the pair fails (otherwise the report is unchanged).

  *Measured.* Five of the seven new tests fail against main's `audit_delta.py` (the two
  decided cases among them, the demotion test through its positive arm); the plain-rename and
  evidence-only tests pass there too, as they should. Locally (`[dev]`, darwin/arm64) the file
  is 23 passed, 16 on main plus 7. On purpose: `AIR_SCATTER_TRIGGER` 0.3 → 0.25 in the
  working tree, `python -m tests.audit_delta` exited 1 printing the message, then restored. On
  #1577's head 539ef7fc7 against its merge-base: 24 changed (evidence only), 0 failures, output
  identical to main's. Workstation canary (38132e546): 109 passed, 35 s, 4 pinned cores,
  149 % CPU, 432 MB. Fast suite: 14857 passed, 280 skipped, 32 xfailed, 0 failed, 514 s (co-tenant, after ~4.5 min queued for memory), 5.9 GB, 745 % on 8 cores; the 7 added tests cost 0.00 s in its junit (`tests.added_test_times`) (Linux workstation, py3.12 `[dev]`). `tests.reader_output` exit 0.

  *Review.* A read-only subagent reviewed the diff (`/code-review` not run: a ghostshift runner
  may not). Five findings: the rename-plus-retune gap (fixed, above); the vacuous action arm
  (documented); same-day strictness (kept, documented in the docstring); a test name that
  promised an equal-date case (added); the docstring overstating who writes the date (now says
  the check sees only that the date moved).

  *Generality.* Not dispatched: the branch does not touch `_audit.py` and adds no heuristic
  rietx makes (the WP's tier line: none, a CI check).

  *Forward.* WP-2017's `### Inherited` names the new failure, since its groups measure tier-3
  values and #1577 runs this gate.

  Next: none here. If the maintainer wants a same-day ruling to count, `now <= was` in
  `retuned_under_old_approval` becomes `now < was` and the equal-date test flips.

- **2026-10-30** — created, from the 2026-10-30 issue triage (issue #1224). Checked against the tree at 44de0f62a: `Row.approved` is a date with no tie to `Row.value`, and `tests/audit_delta.py` fails only on a new `unaudited` name. No open WP owns it: 2017 measures the tier-3 thresholds and does not touch the guard, and 2014, which built the guard's outside-PR path, is closed.
