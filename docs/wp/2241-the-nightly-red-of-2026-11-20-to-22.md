# WP-2241 — the nightly red of 2026-11-20 to 11-22: Windows path checks, the width triple's esd, and a lost runner

Milestone: unscheduled · Status: 🔄 2026-11-22 — claimed by a ghostshift runner
Track: The repo's own process
Depends on: —
Priority: P1 2026-11-22 — a required check red on main: the Windows fast job is the release pre-upload gate (`docs/RELEASING.md` step 4)

## Goal

The three red nightlies of 2026-11-20, 11-21 and 11-22 each have a named cause, and every
cause still present on `main` is fixed. The next scheduled nightly measures the fix.

## Context

No open WP but WP-2036 owns nightly health, and WP-2036 is held by a stale claim, so this
WP carries the three nights and WP-2036 gets a note pointing here.

`nightly.yml` failed on three days running. Runs, jobs and what each one said:

- **45028953563 (11-22, `133aa002f`).**
  - `fast suite (Windows)`: 11 failed. Ten are tooling tests that ask whether a cited
    directory exists: `tests/test_code_references.py::test_every_comment_citation_resolves`
    (11 directory citations) and 9× `tests/test_docs_consistency.py::test_rulebook_paths_and_names_resolve`.
    Every miss is a directory (`docs/wp/`, `src/rietx/io/`, `static/`). The eleventh is
    `tests/test_discarded_direction.py::test_the_lab6_width_triple_has_no_esd_from_either_start[0.00015]`,
    which got esds of 4.127 on all three triple members where it expects none.
  - `full suite (Linux, incl. slow acceptance)`: the Full suite step started at 14:27:07Z
    and never finished. The job ended at 16:24:50Z (1 h 58 min) with the annotation "The
    hosted runner lost communication with the server". The log endpoint answers 404.
- **44910841692 (11-21, `e1f6d1ac4`).** Full suite, 1 failed and 16 181 passed (4:00:43):
  `tests/test_suite_alarms.py::test_the_standards_fire_what_the_pin_says`. Fluorite's
  `COVARIANCE_DIRECTION_DISCARDED` went warning → absent, with one warning less per result
  under five purposes.
- **44754238414 (11-20, `20255ddfa`).** Full suite, the same row, 1 failed and 16 082 passed (4:00:17).
  Brucite and zincite gained `CONSTRAINT_ACTIVE` (info), zincite gained
  `RESOLUTION_NOT_POSITIVE` (warning).

**The directory check.** `tests/code_references._committable` reads git's file list and
builds the directory set with `str(p) for p in Path(f).parents`. On Windows `str()` of a
`Path` uses backslashes, so the set holds `docs\wp` while `in_tree` looks up the POSIX form
`docs/wp`. Every directory misses there, and no file does. Both tests landed with WP-2233
on 11-21, so 11-22 was their first Windows night.

**The width triple.** W, `gauss_size` and `gauss_strain` are exactly degenerate
(1/cos²θ = 1 + tan²θ), so the normal matrix has one eigenvalue at rounding level. The
pseudo-inverse cut is `PINV_RCOND = 1e-15` of the largest eigenvalue, which is also
rounding level. So rounding decides on which side of the cut the eigenvalue falls. Below
it the direction is discarded and the three report no esd. Above it they report an esd
about 16 000 times W's value. The joint-fit test beside it already says so and asserts
"no esd, or one more than 1000 times the value". The single-fit test asserted no esd only.

**The full suite's death.** Only one of the last 40 nightly `full` jobs ended this way;
the others ended by exit code or by the timeout. githubstatus.com lists no incident on
2026-11-22. With no log, an out-of-memory runner and a lost host cannot be told apart.

The tier of each rule this WP adds: none. It changes tests and a test helper, no package
behaviour.

## Non-goals

- Making the width triple's esd the same on every platform. WP-2219 and WP-2225 chose to
  report the triple's split as it falls, and the cut is the covariance's general rule.
- WP-2036's open items. That WP keeps them.

## Tasks

- [ ] The directory set is built in POSIX form, so a cited directory resolves on Windows.
- [ ] The single-fit width-triple test takes the joint-fit test's bar, measured under 1e-14
      start nudges.
- [ ] The two alarm-pin failures (11-20, 11-21) checked against `main`, and the full
      suite's death on 11-22 measured from what GitHub exposes and recorded.
- [ ] Tests: the touched files and the fast selection.
- [ ] Skill: none. Nothing an agent driving rietx does changes.

## Acceptance

The next scheduled nightly (`nightly.yml`, ~13:40Z) has `fast suite (Windows)` green.

```sh
gh run list --workflow nightly.yml --branch main --limit 1
.venv/bin/python -m pytest tests/test_code_references.py tests/test_docs_consistency.py tests/test_discarded_direction.py --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Nightly runs 45028953563, 44910841692, 44754238414; jobs 137228050543 (Windows),
  137228050728 (the lost full job), 136866113370, 136349660143.
- WP-2036 (nightly health), WP-2233 (the citation and rulebook checks), WP-2219 (no esd on
  a discarded direction), WP-2225 (the triple's split is reported).

## Handover log

- **2026-11-22** — created. No open WP but WP-2036 owns nightly health, and WP-2036's claim
  is stale, so the three nights are filed here and WP-2036 gets a pointer.
