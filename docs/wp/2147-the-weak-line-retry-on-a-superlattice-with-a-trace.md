# WP-2147 — The weak-line retry on a superlattice that also carries a trace phase

Milestone: unscheduled · Status: 🔄 2026-11-18 — claimed by @yue-here (ghostshift runner)
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

### Measured 2026-11-18

Development data on one synthetic family, measured on `05ea63571`
(`[dev]` venv, macOS arm64), from a `git archive` snapshot, one run at a
time. The fixture is `weak_superlattice_with_trace` in
`tests/_synthetic_weak_lines.py`: (b) at antisite 0.1, seed 5, plus α-MoO₃
summed the way (a) sums it, `trace` being the ratio of the two phases'
strongest peak heights. MoO₃ is a reactant of the usual solid-state route to
Sr₂FeMoO₆, so an unreacted trace is the plausible impurity. Every run is
`index_pattern(peaks, spec=SearchSpec(systems=("cubic",)), preset="full")`
on the list as picked. "Truth" is the supercell F 7.886 Å; "subcell" is the
primitive perovskite cell P 3.943 Å. A rank is read by `rank_of_lattice`;
"—" means absent.

**The picked list.** The picker keeps all twelve ordering lines at every
trace. The oxide adds 25 lines at 0.5 %, 39 at 1 %, 58 at 2 % and 77 at 4 %.
The retry's 5 % floor keeps 11 or 12 lines at every trace up to 4 %, all of
them subcell lines: no ordering line and no oxide line survives it.

**When the retry first fires.** At 0.5 % the inlier retry finds the
supercell with all three engines, the weak-line retry does not run, and the
truth ranks first. At 0.6 % the full list ends with no agreement and the
retry fires. The threshold is not monotone: at 0.7 % dichotomy and
trial_error agree on a wrong P 13.659 Å cell after the inlier retry, so the
retry does not run and the truth is absent. From 0.8 % to 4 % it fires on
every trace tried. The fixture's default is 2 %, inside that band.

**All three engines** (truth / subcell rank in the answer a user reads; the
"retry off" column is the full list's own answer, inlier retry included,
measured by making the floor set nothing aside):

| trace | retry fires | adopted | truth | subcell | rank 1 | retry off: truth, candidates |
|---|---|---|---|---|---|---|
| 0 | no | — | 1 | — | F 7.886 (truth) | (same run) |
| 0.5 % | no | — | 1 | — | F 7.886 (truth) | 1, 12 |
| 0.6 % | yes | yes | 4 | 2 | I 3.943 | —, 4 (dichotomy only) |
| 0.7 % | no | — | — | — | P 13.659 | (same run) |
| 0.8 % | yes | yes | 4 | 2 | I 3.943 | —, 2 (dichotomy only) |
| 0.9 % | yes | yes | 4 | 2 | I 3.943 | not run |
| 1 % | yes | yes | 4 | 2 | I 3.943 | —, 1 (dichotomy only) |
| 2 % | yes | yes | 4 | 2 | I 3.943 | —, 0 |
| 4 % | yes | yes | 3 | 2 | I 3.943 | —, 0 |

Every candidate in every row grades `low`. Seeds 1-4 at 2 % make the same
decision (fires, adopted; truth 3rd or 4th, subcell 2nd). Searches took
5-36 s each.

**Each engine alone** (a single engine "agrees" only by returning nothing,
`workflow._no_agreement`, so the retry fires only on an empty first answer):

| engine | trace | retry fires | adopted | truth | subcell |
|---|---|---|---|---|---|
| dichotomy | 0 | no | — | 1 | — |
| dichotomy | 1 % | no | — | — | — |
| dichotomy | 2 % | yes | yes | 4 | 2 |
| svd | 0 | no | — | 1 | — |
| svd | 1 % | yes | yes | 4 | 2 |
| svd | 2 % | yes | yes | 4 | 2 |
| trial_error | 0 | no | — | 1 | — |
| trial_error | 1 % | yes | yes | 4 | 2 |
| trial_error | 2 % | yes | yes | 4 | 2 |

At 1 % dichotomy alone returns one wrong cell (P 19.317 Å), so the retry
does not run and the truth is absent.

**What this says about the two open questions.** The retry does not lose
the supercell, because the full list never held it: wherever the retry
fires, the full list's answer lacks the truth (0 to 4 single-engine cells at
13-22 Å). The retry moves the truth from absent to 3rd or 4th. What it puts
above the truth is the perovskite subcell (2nd) and, first, I 3.943 Å, a
lattice of half the subcell's volume. The floor also removes the subcell's
own weak lines: at 2 % it keeps the subcell's even lines (h² + k² + l² = 2,
4, ..., 22, bar 16) and one odd one, (111) at 5.7 % of the strongest. The
I cell indexes ten of those eleven lines and predicts about half as many
lines as the subcell, and the panel ranks it first. Appending the full
list's candidates after the retry's would add 0 to 4 wrong cells below the
truth and move no rank above it.

**Undeclared systems** (all three engines, `preset="full"`, 2 %, one run,
595 s, `INDEX_SEARCH_INCOMPLETE`): the inlier retry finds two engines
agreeing on an orthorhombic P 6.991 Å cell, so the weak-line retry does not
run. The truth is absent, and so is the subcell. The quick preset's 120 s
ceiling would cut this search, so the default call does not reach the
retry here either.

### Inherited

## Non-goals

- Changing the retry, its floor or its trigger. A change follows the
  maintainer's answer, in WP-2078's successor or here if the maintainer
  says so.
- Real-data superlattices (the reporter's pyrochlore and trirutile hosts are
  private).

## Tasks

- [x] The fixture: (b) plus a planted trace phase, with the smallest trace
      fraction at which the full list finds no agreement after the inlier
      retry. Seeded, no data file.
- [x] Measure under `preset="full"` with each engine and all three together:
      whether the retry fires, whether it finds agreement, and where the
      supercell and the subcell rank in the answer a user reads.
- [ ] Write the result here and in WP-2078's successor's `### Inherited`.
      If the supercell is lost, brief the maintainer on replace-versus-append
      with these rows.
- [x] Tests: the fixture as a row pinning the decision the code makes (fires
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
