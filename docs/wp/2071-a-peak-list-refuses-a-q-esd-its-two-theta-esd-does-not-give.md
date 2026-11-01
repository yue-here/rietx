# WP-2071 — A peak list refuses a q_esd that its two_theta_esd does not give

Milestone: unscheduled · Status: ✅ 2026-11-01 — the list refuses a `q_esd` its `two_theta_esd` does not give (PR #1281)
Track: What fires, and what stays silent
Depends on: —

## Goal

`PeakList` validates `q_esd` against `two_theta_esd` the way it already validates `q`
against `two_theta`, so an edit to one uncertainty that leaves the other stale is refused
by name rather than silently ignored by the indexer.

## Context

**Source.** Issue #1236 (2026-10-30, @mustachefeeling). `ObservedPeak` stores the
position twice (`two_theta`, `q`) and its esd twice (`two_theta_esd`, `q_esd`).
`PeakList._q_matches_two_theta` (`schemas/indexing.py:991`) ties `q` to `two_theta` at
rtol 1e-9 and names the remedy; nothing ties `q_esd`. The SVD indexer weights lines by
`PeakList.q_esd()` (`indexing/svd.py`, through `sigma_effective`), so an edit to
`two_theta_esd` never reaches the search. The reporter's weighting experiment ran an arm
that was a no-op and read "no effect".

**Reproduced at `d87c8cc91`** (the issue's snippet): `from_positions` with
`two_theta_esd=0.002`, peak 1's `two_theta_esd` tripled by `model_copy`, round-tripped
through `model_validate_json` with no error; `two_theta_esd` ratio 3.0, `q_esd` ratio 1.0.

**The check is safe to add** (checked at `d87c8cc91`): both constructors,
`indexing/pick.py` `peaks_of_group` (line 338) and `PeakList.from_positions` (line 1091),
derive `q_esd` through `schemas.indexing.q_esd_of_two_theta`; nothing in `src/` edits
`two_theta_esd` after construction. The reporter checked 1318 picked lists (59 975 lines)
from two commits: all satisfy it exactly.

**Siblings.** `d` is a property, so it cannot drift. `two_theta_esd_fit` is deliberately a
separate number (the fit's σ before a merge widened it, #934) and needs no tie. The
`wavelength` already reaches `q` through the existing check. No other derived field
is stored on `ObservedPeak`.

**Design.** Extend the existing validator in the same vectorised pass: compare stored
`q_esd` with `q_esd_of_two_theta(two_theta, two_theta_esd, wavelength)` at a relative
tolerance; a pair where both are non-finite agrees. The message names the same remedy as
the `q` check. Making `q`/`q_esd` computed fields instead would remove the duplication
but changes the serialised schema; this WP does not.

**Tier.** Arithmetic on the list's own fields (physics): no `_audit` row unless the
refusal gets a diagnostic code.

**Old files.** A stored peak list written by any shipped constructor satisfies the check
exactly, per the reporter's 1318-list control. A hand-edited stored list would now fail
to load; the message must say how to rebuild it.

## Non-goals

- Making `q`/`q_esd` computed fields (a schema change).
- Any change to how the indexer weights lines.

## Tasks

- [x] The `q_esd` check in `_q_matches_two_theta` (or a sibling validator), relative
      tolerance, non-finite pairs agree, message naming the remedy.
- [x] Tests: the issue's reproduction now raises; both constructors' lists pass; a JSON
      round trip of a picked list passes; a non-finite pair passes. Make it fail once on
      purpose and read the message.
- [x] Skill: none. The refusal names its own remedy, the package's own output.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_peak_picking.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

No test of the existing `q` refusal was found at `d87c8cc91` (grep for its message), so
the new test file or `tests/test_peak_picking.py` covers both checks.

## References

- Issue #1236 (reproduction and the 1318-list control).

## Handover log

- **2026-11-01** — closed, PR #1281. A peak list now refuses a line whose stored σ(Q)
  does not follow from its σ(2θ), as it already refused a stale Q. Before, a script that
  edited one line's σ(2θ) got a list that loaded clean while the indexer, which weights
  lines by σ(Q), never saw the edit; that is why #1236's weighting arm read "no effect".
  Now the reload raises, names the peak and both numbers, and says to set both fields
  together. Nothing a package constructor writes is affected, and no default or stored
  format moved.
  - *Done.* `PeakList._q_matches_two_theta` (`schemas/indexing.py`) checks `q_esd`
    against `q_esd_of_two_theta(two_theta, two_theta_esd, wavelength)` in the same pass:
    `np.isclose` at rtol 1e-9, atol 0, since σ(Q) is ~1e-5 Å⁻² and the position check's
    floor of 1.0 would make it an absolute 1e-9 Å⁻². A pair with both values non-finite
    agrees. The message leads with deriving `q_esd` through `q_esd_of_two_theta` (keeps a
    fitted list's provenance) and names `pick_peaks`/`from_positions` second, noting that
    `from_positions` marks every σ assumed. Three tests in `tests/test_peak_picking.py`:
    the issue's reproduction raises (and a directly edited `q_esd`), a non-finite pair
    loads while a half-finite one is refused, a picked list round-trips through JSON with
    every `q_esd` at the derived value. Two hand-built test peaks carried a `q_esd` their
    `two_theta_esd` did not give and now derive it (`test_peak_bounds._peak`, the existing
    q-drift test's good peak). `reference/peaks.md` states the check and how to change an
    esd.
  - *Old files.* The formula line of `q_esd_of_two_theta` has not changed since WP-1018
    introduced it, and `peaks_of_group`'s `q_esd` line has derived from the very esd it
    stores since WP-1027 (`git log -S`/`-L`), so no saved `peaks.json` from a shipped
    release should fail to load.
  - *Measured* (`[dev]` venv, darwin arm64). With the new branch disabled, both refusal
    tests fail with DID NOT RAISE; restored by the inverse edit. Fast selection on
    `ca001086b`: 12879 passed, 305 skipped, 32 xfailed, 1 failed, 19:12 under load
    (load average ~52 from another session). The failure is environmental:
    `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`
    launches the user's Jupyter kernel spec, which points at a deleted venv. The later
    commits change a docstring, the message text, a manual sentence and a test-helper
    name; the peak files plus `test_manual_api.py` on the head: 103 passed. +3 tests;
    no baseline run on main (CI's job). Full suite not run: the change moves no measured
    number.
  - *Review.* `/code-review high --fix`: four findings, three accepted (message order,
    manual wording "the same way" → "also", helper renamed `_reloaded_with`). Declined:
    `gui/session.py:2150` `_load_peaks` turns every `ValueError` into
    `PEAKS_WRONG_PATTERN`, so a drifted `peaks.json` reads as "wrong pattern". It already
    did for a drifted Q; fixing it adds a GUI error code, outside this WP. Not filed: only a
    hand-edited `peaks.json` reaches it.
  - *Generality.* The `generality-review` judge, summarised: verdict holds; the case for
    acting is stronger (kind 1, the data settle it: σ(Q) is fixed by σ(2θ), 2θ and λ). No
    row needed: no code, no action field, an inline literal the table cannot see. If the
    1e-9 were ever lifted to a constant it would be tier 1, and the sibling `q` check's 1e-9
    should move with it. Its one caveat, an older release writing σ(Q) differently, is
    answered under *Old files*. It also caught an overstated docstring reason, fixed in
    `11d5c49ad`.
  - *Not generalised.* `two_theta_esd_fit` stays untied (a deliberately separate number,
    #934), and `d` is a property. Test builders in `test_peak_fdr.py` and
    `test_peak_resolvability.py` never enter a `PeakList`, so they keep placeholder values.
  - *Next:* none in this WP.
- **2026-10-31** — created by the issue triage from #1236. No open WP owns the peak-list
  schema: WP-1520 (a search refines each assignment once) reads `q_esd` but owns the
  refinement memo, and WP-1915 (an unmeasured direction poisons a candidate's esds) owns
  candidate covariance.
