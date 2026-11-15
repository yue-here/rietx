# WP-2147 — The weak-line retry on a superlattice that also carries a trace phase

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 2078 (PR #1567 builds the retry this WP measures, and was not merged on 2026-11-15)
Priority: P3 2026-11-15 — a measurement that decides two open maintainer questions on WP-2078's retry (replace or append, and the code's tier); down a rung from P2 because nothing can start until PR #1567 merges

## Goal

We know whether WP-2078's weak-line retry loses a superlattice's true cell
when a trace second phase stops the full line list from reaching agreement.
The answer is measured on a public synthetic fixture under every engine. If
the retry loses the supercell, the result goes to the maintainer as the
evidence for the two open questions below.

## Context

**What WP-2078 built** (PR #1567, branch `wp2078-weak-line-floor`; not
merged on 2026-11-15). When an indexing search ends with no lattice that two
engines agree on, the inlier retry included, `index_pattern` searches once
more on the usable lines at or above 5 % of the strongest
(`engines.WEAK_LINE_RETRY_FLOOR`). That kept list is the I ≥ 5 % Imax list
of the 2004 indexing round robin (Bergmann, Le Bail, Shirley & Zlokazov,
*Z. Kristallogr.* 219, 783). The retry's candidates replace the full list's
only when the retry finds agreement. `INDEX_WEAK_LINE_RETRY` (info) says the
retry ran and what it set aside.

**Why this case.** WP-2078's generality review (the `generality-review`
agent's judgement, in WP-2078's 2026-11-13 handover entry) rated the code
"weak". Its open point: a superlattice host that also carries an impurity.
The retry's floor removes the superlattice's own ordering lines, which are
the lines that tell the supercell from the subcell. If the retry then finds
agreement on the subcell, it replaces the full list's answer with a wrong
cell. The author's answer was that on such a list the full search had no
agreed cell to lose. That is true of the agreed cells and not measured on
the ranking a user reads. The review named this fixture as what would
change its rating.

**The fixtures** (all in `tests/_synthetic_weak_lines.py`, drawn by the
package's forward model with fixed-seed Poisson noise, no data file):
- (b) `weak_superlattice`: a partly ordered double perovskite. The truth is
  the supercell F 2·a_p. Its ordering lines (h, k, l all odd) sit at 0.1-2.3 %
  of the strongest at the default antisite 0.1. All of them fall under the
  5 % floor. On its own, the full list ranks the truth first, so the retry
  never fires (PR #1567's trigger table).
- (a) `weak_second_phase`: a host with a trace phase (MoO₃ beside Mo) whose
  lines sit under 1 % of the strongest. Its full list finds no agreement,
  which is what fires the retry.
- This WP's fixture is (b) with a planted trace phase, built the way (a)
  builds its trace. The trace has to be strong enough that the full list
  finds no agreement after the inlier retry, or the retry does not fire and
  the run measures nothing. Record the trace fraction at which that first
  happens.

**Gotchas from WP-2078.** A probe run against a worktree while it is being
edited imports the edits: measure from a `git archive` snapshot. The `quick`
preset's whole-run ceiling cut most as-picked lists under load, so the
retry, which needs an uncut search, did not run. Measure under
`preset="full"`, one run at a time, since engine budgets are wall-clock
(root CLAUDE.md § Commands).

**Still the maintainer's** (rulings file of 2026-11-15, WP-2078):
replace-versus-append (whether the full list's candidates are listed after
the retry's rather than dropped), and the tier of `INDEX_WEAK_LINE_RETRY`
(an action at tier 3 needs the maintainer's dated approval). This WP
supplies evidence for both and decides neither.

**Tier.** No rule is added. The measurement is development data on one
synthetic family; say so where it is quoted.

### Inherited

## Non-goals

- Changing the retry, its floor or its trigger. A change follows the
  maintainer's answer, in WP-2078's successor or here if the maintainer
  says so.
- Real-data superlattices (the reporter's pyrochlore and trirutile hosts are
  private).

## Tasks

- [ ] The fixture: (b) plus a planted trace phase, with the smallest trace
      fraction at which the full list finds no agreement after the inlier
      retry. Seeded, no data file.
- [ ] Measure under `preset="full"` with each engine and all three together:
      whether the retry fires, whether it finds agreement, and where the
      supercell and the subcell rank in the answer a user reads.
- [ ] Write the result here and in WP-2078's successor's `### Inherited`.
      If the supercell is lost, brief the maintainer on replace-versus-append
      with these rows.
- [ ] Tests: the fixture as a row pinning the decision the code makes (fires
      or not, adopts or not), never the landing rank (root CLAUDE.md: what a
      decline leaves free finds the peaks at a rate).
- [ ] Skill: none expected. If the retry's guidance changes, the row in
      `references/abstention.md` changes with it.

## Acceptance

The table of fires, adopts and ranks for the new fixture under each engine,
in this file, and a test row that reproduces the decision.

```sh
.venv/bin/python -m pytest tests/test_indexing_weak_lines.py
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Bergmann, Le Bail, Shirley & Zlokazov (2004), *Z. Kristallogr.* 219, 783.
- WP-2078 and PR #1567; issue #1291.

## Handover log

- **2026-11-15** — created, from the 2026-11-15 issue triage, as the
  follow-up the 2026-11-15 rulings file asks for (WP-2078, PR #1567). No issue
  reports it. Checked against PR #1567's head on 2026-11-15: the retry fires
  only when no two engines agree after the inlier retry, and fixture (b)
  alone ranks its truth first, so no existing row exercises this case. No
  open WP owns it: WP-2078 closes with PR #1567 and lists this run for the
  maintainer to place. Next: wait for PR #1567, then build the fixture.
