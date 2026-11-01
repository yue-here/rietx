# WP-2050 — a correlation with a flat direction is not reported as one

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-25 — a warning whose count is rounding: brucite carries 35 to 42 by a 1e-14 start nudge, and the alarm pin cannot hold it on any platform

## Goal

`HIGH_CORRELATION` names only pairs whose ρ the data determines. A pair whose
partner is a member of a flat direction (an esd of order 10³ on a value of
order 10⁻²) is either not reported or reported as that, and the warning count
on a fit no longer moves under a 1e-14 nudge to its start.

## Context

`tests/test_suite_alarms.py::test_the_standards_fire_what_the_pin_says` was red
on the Linux nightly on `deff4c301` (run 40184228951): warnings per result rose
by exactly 0.75 under every purpose against `tests/data/suite_alarms.json`, re-pinned
on an arm64 Mac by WP-2045 the same day. The per-standard codes did not move,
only their counts.

**Measured 2026-10-25** (`deff4c301`, macOS arm64, `[dev]`) by a lane of
WP-2036's session. At the unnudged starts the eight standards carry brucite 36,
zincite 14, fluorite 12, corundum 11, SRM 660c 2, FAP 1, NAC 0 and the LaB6
capillary 0 warnings: 76/8 = 9.5, the pin. Under 1e-14 nudges to one start
value only brucite moves, to 35, 36, 39 or 42, at an Rwp of 0.4690163639 every
time. With brucite's start scale nudged by +4e-14 and the rest unnudged the
module prints exactly Linux's seven lines. Brucite's six extra warnings are all
`HIGH_CORRELATION`: `lor_size` and `lor_strain`, each against `gauss_size`,
`gauss_strain` and `instrument.profile.w`, at ρ 0.991 and 0.988 against the 0.98
limit. Those three partners are an exactly flat triple: values 0, 0 and 0.0132,
each with an esd of about 1124. A ρ against one member of a flat direction is
numerically undetermined, so the count is rounding. The probes are in
`docs/wp/2050-batch/`.

The guard is the pairwise loop in `strategy/staged.py:2083-2089` over
`outcome.correlation`. The esd authority is `statistics.normal_covariance`
(root CLAUDE.md § Invariants: a direction the data does not move has no esd
rather than a small one, and a row on its bound stays in the matrix, WP-1929).
Here no column is gradient-free, so `_cov_free` keeps all three and they come
back with huge finite esds.

The tier of each rule this WP adds: new judgement, unless practice has one.
Which esd marks a direction as flat is a threshold. Read `docs/practice.md`
first, and survey how GSAS-II and TOPAS report a correlation with an
undetermined parameter. The datasets it must hold on are the eight alarm
standards, brucite above all.

## Non-goals

- Brucite's flat triple itself: the Gaussian size, Gaussian strain and W
  degeneracy is a protocol question for its standard.
- The pin's design. Once brucite's count is stable, re-pin it once.

## Tasks

- [ ] Survey practice (above) and pick the test for "this partner's ρ is not
      determined", measured on brucite's triple and on the other seven
      standards, with no pair dropped that a refiner would want reported.
- [ ] Apply it in the guard loop. Say in the message what was left out and why,
      rather than dropping it silently.
- [ ] Tests: brucite's count is the same at the nudges in
      `docs/wp/2050-batch/`; re-pin `tests/data/suite_alarms.json`.
- [ ] Skill: `HIGH_CORRELATION`'s row in `references/diagnostics.md`, if the
      message changes.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_suite_alarms.py tests/test_high_correlation_dedup.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-2037 (the alarm pin), WP-1929 (a bound row stays in the matrix),
  WP-1110 item 14 (`normal_covariance`), WP-2036 (found it on the nightly).

## Handover log

- **2026-10-25** — filed by WP-2036's session after a measurement lane
  reproduced the nightly's alarm red on an arm64 Mac. No open WP owns the
  guard: WP-2037, which made the pin, is closed. Next: the first task.
