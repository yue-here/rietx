# WP-2079 — A stated prior is not an engine in the grade

Milestone: unscheduled · Status: ✅ 2026-11-02 — the grade's two-engine floor counts engines, a stated prior excluded (PR #1327)
Track: What fires, and what stays silent
Depends on: —

## Goal

The confidence gate counts only engines toward its two-finder floor
(`MIN_AGREEMENT`). A stated prior cell (finder `"prior"`) corroborates a
lattice the engines found and never lifts its grade. Stating a prior changes
no candidate's grade unless an engine's own finding changes.

## Context

**Source.** Issue #1308 (2026-11-02), by the recurring contributor, with a
repro on planted values.

**The rule it breaks.** WP-1003 § E, recording WP-1046 §4: *a prior
corroborates but does not confirm*. Agreement means independent searches,
and a stated cell is not one. The ruled fix was to count engines in `grade`
the way `engines.agreement` does (the ranking's first key, which already
excludes `PRIOR_FINDER`). It was deferred into the post-1003 indexing work
"where the acceptance suite runs", and `consensus.grade`'s docstring said so.

**The mechanism.** `consensus.grade` floors a candidate at `low` when
`len(set(found_by)) < MIN_AGREEMENT`. `found_by` gains `"prior"` when a
checked prior merges into an engine's candidate (`consensus.consensus`, the
`carrier` holder). So a lattice one engine found and the caller stated has
two "finders" and can reach `medium`. A lattice the same engine found and
nobody stated stays `low`.

**Reproduced on `main` `0d735f5e5`** (darwin/arm64, `[dev]` venv). F-centred
cubic a = 4.5 Å planted with `tests.test_indexing_engines.synthetic_peaks`,
`engines=("svd",)`, `preset="full"`. The prior is the primitive cubic cell at
the same metric, which predicts mixed-parity lines the data lack.

| run | lattice | `found_by` | grade |
|---|---|---|---|
| no prior | F cubic 4.5 (planted) | svd | low |
| | P cubic 4.5 | svd | low |
| prior P 4.5 | F cubic 4.5 (planted) | svd | low |
| | P cubic 4.5 | prior, svd | **medium** |
| prior P 9.0 | P cubic 9.0 | prior | low, appended last |

**Every other reader of `found_by`, checked.** Only the floor counted the
prior. The others ask a superset question against `engines_run`, and
`"prior"` never enters `engines_run`:

- `grade`'s `high` clause, `set(found_by) >= set(engines_run)`.
- `caveats_for`'s `engines_disagree`.
- `checked_indices`, which picks the candidates the ambiguity walk and the
  validation cover.
- `engines.agreement`/`corroborated` (ranking key), which excludes the prior.
- `workflow._no_agreement` (the inlier retry's trigger), which merges the
  engines' results without the priors.

**The seed sibling, measured and left alone.** A prior's metric also seeds
svd's starting basin, outside its volume gate (`svd.py`, WP-1045 rule 1). A
lattice svd reaches only from that seed would count as an engine's finding.
WP-1045 states that rule on purpose: "a prior cell that is real is then
*found* by the engines from the seeded start, so `found_by` and `grade` keep
their meaning". Measured on the issue fixture, svd alone, seeds 0-3, with and
without the P 4.5 prior: the seed bought svd no lattice it did not find
unseeded (0 of 4 seeds). The 9.0 prior bought none either. So no measured
case bites, and changing the rule would rewrite WP-1045's contract. Left as
a recorded open question (Handover log).

**Tier.** Named practice inside the package: the WP-1003 § E ruling. No new
judgement, no new constant.

**Reader output.** The grade of a prior-confirmed candidate falls from
`medium` to `low` wherever only one engine found it. That changes what a run
returns, so it goes to the maintainer before merge.

## Non-goals

- The svd seed's independence (above). A change there is WP-1045's contract.
- Several descriptions of one lattice graded `medium` under all three
  engines (#1291's controls). That is WP-2078's and WP-1956's ground.

## Tasks

- [x] `grade` counts engines through the same authority as
  `engines.agreement`, prior excluded; docstrings, the indexing CLAUDE.md and
  the manual's confidence-gate rule say so
- [x] Tests: the issue's repro as a regression (the planted lattice is never
  graded below the prior's lattice, and the P lattice's grade is the same with
  and without the prior); a unit test of `grade` on `["prior", "svd"]`
- [x] Skill: none. The skill already says a real prior is found by the
  engines and that `found_by == ["prior"]` alone is the caller's hypothesis;
  the fix makes the grade agree with that text.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing_priors.py tests/test_indexing_consensus.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #1308.
- WP-1003 § E (the deferred ruling), WP-1045 (priors), WP-1046 (agreement as
  the ranking's first key).

## Handover log

### 2026-11-02 — closed: a prior corroborates and no longer counts as an engine

A stated prior cell can no longer lift its own lattice's grade. Before,
a lattice that one engine found and the caller also stated counted as two
finders and could reach `medium`, while the true lattice found by the same
engine stayed `low`. Now the grade's two-engine floor counts engines only,
through the same count the ranking already used. Stating a prior changes
no grade in any measured case. A grade moves only where one engine and a
prior stood behind a lattice: it was `medium` and is now `low`. That is a
reader-output change, and it waits for the maintainer before merge.

- *Done.* `consensus.grade` reads `engines._engines_behind(found_by)`, the
  count `engines.agreement` now reads too. Docstrings (grade, rank_candidates,
  `CellCandidate.found_by`), the indexing rulebook and the manual's priors
  paragraph say a prior is not an engine. Two tests that counted
  `len(found_by)` call `engines.corroborated` (no fixture there states a
  prior, so no assertion moves).
- *Siblings checked.* Every reader of `found_by`: the `high` clause,
  `engines_disagree`, `checked_indices` and the inlier retry's trigger ask a
  superset question against `engines_run`, which never holds `"prior"`, or
  merge without priors. Only the floor miscounted.
- *Not generalised: svd's seeded start.* A prior's metric seeds svd outside
  its volume gate (WP-1045 rule 1), so a lattice svd reaches only from the
  seed counts as svd's finding. WP-1045 states that on purpose. Measured on
  #1308's fixture, svd alone, seeds 0-3, with and without the P 4.5 prior:
  the seed bought svd no lattice it missed unseeded (0 of 4); the 9.0 prior
  bought none either. Changing it would rewrite WP-1045's contract, and no
  measured case bites, so it is reported to the maintainer and not filed.
- *Measured* (darwin/arm64, worktree `[dev]` venv). The repro after the fix:
  svd alone, the P lattice is `low` with `found_by` `['prior', 'svd']`, the
  same grade as unstated; all three engines, every grade identical with and
  without the prior. `tests/test_acceptance_indexing.py`: 45 passed (21:09,
  alone on the machine), before the review commit, which changed one of its
  assertions to an equivalent form. Fast suite on main `0d735f5e5`+ merged:
  13298 passed, 310 skipped, 32 xfailed, 3 failed. Two failures were this
  branch's (the indexing rulebook one line over its cap, the manual's
  indexing page 163 characters over its twin cap) and are fixed, those files
  re-run green. The third, `test_display`'s kernel test, fails on a stale
  Jupyter kernel spec on this machine. A second pytest was running beside it.
  Added tests: 6 cases, 6.96 s total under that load (the end-to-end repro;
  the grade table is 0.00 s).
- *Review.* `/code-review high --fix`: no correctness bug. It fixed the
  test's key (whole cell, no collisions), "finders" → "engines" wording in
  two places and the `found_by` schema docstring. I took its two skipped
  findings too (the two `len(found_by)` tests, the rulebook clause trimmed to
  a rule). Declined: the #1308 story written in two docstrings, cosmetic.
- *Generality.* No row added, changed or removed in `_audit.py`; no new
  constant, ordering or fallback. Not dispatched.
- *Next.* The maintainer approves the grade change (PR #1327, Reader-output
  changes), then merges. Optional: rule on the svd seed's independence.

- **2026-11-02** — created. No open WP owns the prior's place in the grade:
  WP-1956 owns the absence screen and WP-2078 the ranking under foreign
  lines, and the WP-1003 deferral named no successor WP.
