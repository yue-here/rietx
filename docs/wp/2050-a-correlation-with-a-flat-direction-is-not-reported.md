# WP-2050 — a correlation with a flat direction is not reported as one

Milestone: unscheduled · Status: 🔄 2026-11-01 — claimed by @yue-here
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

**Superseded in part, 2026-11-01** (re-measured on `62034506e`, after
WP-2048 merged; macOS arm64, `[dev]`). The counts reproduce: brucite 36 at
k = 0 and 42 at a +4e-14 scale nudge, 35 at −4, ±1 and +7. Two findings
change the frame.

- **The partner rule alone cannot hold the count.** `lor_size ~ lor_strain`
  is a pair of non-members, and it flips too: −0.995 at k = 0, −0.9975 at +4,
  under the guard at −4. Both columns load weakly on the flat direction, and
  that loading is divided by an eigenvalue rounding sets. With the direction
  projected out the pair reads −0.896 and −0.893.
- **What marks the direction is its eigenvalue, not an esd.** In the
  unit-diagonal normal matrix of the closing stage, the triple's eigenvalue is
  2.7e-15 to 4.9e-14 of the largest across the nudges. That is an 18-fold
  spread, so rounding sets it. The next direction (zero shift with sample
  displacement) holds at 1.3e-10 to 1.4e-10. The forward-difference columns
  are accurate to about `FD_STEP` = 1e-6 relative, so an eigenvalue under
  FD_STEP² = 1e-12 of the largest lies inside the Jacobian's own error.

The test is `statistics.resolved_correlation` (task 1). The guard reads the
correlation with every direction under that cut projected out. A pair with
one member of such a direction is `nan` there and is never thresholded. A pair
of members keeps its full-matrix ρ, which is ±1 to rounding and stays a
`FLAT_DIRECTION`. Simulated in-process on the eight alarm standards
(`docs/wp/2050-batch/simulate.py`), brucite gives 35 warnings at all eight
nudges (k = 0, ±1, ±4, +7, ±20) and the other seven are unchanged at k = 0
and +4. Corundum, zincite and fluorite carry the same unresolved triple, and
none of their reported pairs involves it.

## Non-goals

- Brucite's flat triple itself: the Gaussian size, Gaussian strain and W
  degeneracy is a protocol question for its standard.
- The pin's design. Once brucite's count is stable, re-pin it once.

## Tasks

- [x] Survey practice (above) and pick the test for "this partner's ρ is not
      determined", measured on brucite's triple and on the other seven
      standards, with no pair dropped that a refiner would want reported.
      Survey: `docs/practice.md` § Correlations against a parameter the data
      does not determine. Test: `statistics.resolved_correlation`, cut
      FD_STEP² × |λ|max, members by `discarded_directions`' touched rule;
      `top_correlations` skips a `nan` pair. Settled by Claude under
      established practice (GSAS-II's truncated pseudo-inverse) and the
      measurement above, which chose the cut. GSAS-II's own 1e-6 lost: it
      would also project out the zero-shift/displacement direction at
      1.4e-10, whose pairs hold to 2e-5 under the nudges and which a refiner
      wants reported. Tier: derived (the cut is the Jacobian's accuracy).
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

- **2026-11-01** — ghostshift runner, PR #1306 (draft), branch
  `wp2050-flat-direction-correlation`. **Paused at task 2 on a file
  boundary, not a design question.** Task 1 landed: the premise
  re-measured (Context, "superseded in part"), the practice survey, and
  `statistics.resolved_correlation` with 8 tests
  (`tests/test_resolved_correlation.py`, 8 passed, `[dev]`, macOS arm64).
  The shift lead had told this runner to stay out of `src/strategy/` and
  `refine.py` while WP-2049's runner works there. Task 2 needs
  `strategy/staged.py`, in two functions WP-2049's tasks do not reach.
  In `check_guards`, before `_correlation_findings`, pass
  `resolved_correlation(corr, covariance_jacobian(outcome, free))`'s
  matrix when `outcome.jac is not None and not outcome.n_aux`, so the
  findings and `measured_top_correlations` read one matrix (WP-1056's
  rule). And in `_correlation_findings`, say what was left out:
  `GuardFinding.flat_direction` gains a clause for a pair of unresolved
  members, along the lines of "ρ against either is not determined and is
  not reported". The joint twin in `multi.py` passes a `BlockJacobian`,
  which the helper returns unchanged; leave it. After that: re-pin
  `tests/data/suite_alarms.json` (brucite 36 → 35; 76/8 = 9.5 → 75/8 =
  9.375 warnings per result), the `HIGH_CORRELATION` and `FLAT_DIRECTION`
  rows of `references/diagnostics.md`, an `_audit` row for the cut, and
  `python -m tests.reader_output` (the message changes, so it goes to Yue
  before merge). Measured with `docs/wp/2050-batch/simulate.py`: brucite
  35 at k = 0, ±1, ±4, +7, ±20; the other seven unchanged at k = 0, +4.
  Not generalised: the esds. `lor_size`'s own esd moves 55 % across the
  nudges (0.185 against 0.287) for the same reason, and the three members'
  esds (≈ 6000) are rounding too. The correlation feeds
  `stderr_physical`, so fixing that belongs to the esd authority
  (`normal_covariance`) and to its own WP.
- **2026-10-25** — filed by WP-2036's session after a measurement lane
  reproduced the nightly's alarm red on an arm64 Mac. No open WP owns the
  guard: WP-2037, which made the pin, is closed. Next: the first task.
