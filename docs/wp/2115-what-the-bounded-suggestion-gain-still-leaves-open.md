# WP-2115 — what the bounded suggestion gain still leaves open

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 1998 (PR #1383 lands the bounded gain these questions are about)
Priority: P3 2026-11-05 — no wrong suggestion in any case tested; each item is a way the score can differ from what a stage would do

## Goal

`Refinement.suggest`'s bounded score agrees with what a stage would do in the four places it can still
differ, or each difference is ruled and written down.

## Context

**Source.** Issue #1392, from WP-1998's review and generality check. PR #1383 makes `suggest` score each
held parameter by the gain it can reach inside its bounds, and makes `SuggestionResult.best_or_none`
return `None` when ΔBIC refuses the top group. `_bounded_group` and `bound_limited` are on that PR's head
and not on main at `541f0daf7`, so read this file against the merge. None of the four is measured.

1. **A floored partner is dropped before grouping.** A candidate enters a group only if its own
   one-parameter bounded gain clears the noise floor. A parameter on its floor that cannot help alone, but
   could move inward to compensate for a collinear partner, is dropped before the tie test runs. So the
   group's joint bounded solve (BVLS) never sees it. No test covers this. (`build_suggestion`, the
   `survivors` filter.)
2. **A bounded group is still charged for every member.** `CandidateGroup.delta_bic` charges `len(members)`
   parameters. When the bounded solve leaves a member on its bound with zero step, the group reaches what
   fewer parameters reach, and it pays ln N_eff more per pinned member (about 6.9 at N_eff = 1001). Whether
   a freed parameter that stays on its bound counts toward k is a model-selection question. Practice has
   not been read for it, so read it before ruling (`_predicted_delta_bic`, `_bounded_group`).
3. **The group shortcut and the unbounded gain solve slightly different problems.** `_bounded_group` checks
   whether the minimum-norm step lies inside the box, using every member's projected column.
   `one_parameter_gains` computes the unbounded joint gain after dropping columns it finds absorbed. On a
   near-identity tie the two can disagree about which columns take part. `min(gain, reach)` keeps the
   reported gain from going above the unbounded one, but the bounded solve can run when it is not needed,
   or be skipped when it is.
4. **`gradient` and `bound_limited` can disagree on direction.** `bound_limited` comes from the sign of the
   step with the free block re-solved. `ParameterCandidate.gradient` is the unprojected 2·Jᵀr. Where the free
   block has not converged, the two can have opposite signs. One option is a projected-gradient field beside
   `gradient`. That field is reader output, so it goes to the maintainer before merge.

**Also noted, with no behaviour change.** `SuggestionResult.summary` does not name a lower group that ΔBIC
admits, and `Refinement.summary()`'s `next:` line does. `one_parameter_gains` and `block_projection_r2` each
rebuild the free block's QR. `_scaled` duplicates `statistics._column_in_range` so that it can return the
scale factor.

**Tier.** Item 2's rule, if it changes, is a model-selection choice, so it names its source or its measured
families. Items 1, 3 and 4 are arithmetic.

## Non-goals

- A new suggestion family, or what `suggest` proposes beyond its current candidates.

## Tasks

- [ ] A test for item 1: a floored partner collinear with a helpful parameter, showing whether the group's gain is short of a real stage's.
- [ ] Item 2: read what practice charges a parameter at a bound, and rule whether a pinned member counts toward k.
- [ ] Item 3: one set of columns for the shortcut and the gain.
- [ ] Item 4: construct the sign disagreement, then decide on a projected-gradient field.
- [ ] The two efficiency points, each with a timing, and the `summary` sentence.
- [ ] Skill: the `references/` row for `suggest` if `gradient`'s neighbour lands, or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_suggest.py
.venv/bin/python -m tests.reader_output    # exit 0, or the change goes to the maintainer
```

## References

- Issue #1392; WP-1998; Stark, P. B. & Parker, R. L. (1995). *Comput. Stat.* 10, 129-141 (BVLS).

## Handover log

- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1392). Checked against PR #1383's WP file and `strategy/suggest.py` at `541f0daf7`: the issue's four questions are about code that lands with that PR, so they were read, not run; no open WP owns it: WP-1998 closes in #1383, and WP-2004 owns the report's thresholds and not `suggest`. Next: item 1's test, since it is the only one that could show a short gain.
