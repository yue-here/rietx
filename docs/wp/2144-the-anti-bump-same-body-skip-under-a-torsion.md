# WP-2144 — the anti-bump same-body skip, now that a torsion moves the pair

Milestone: unscheduled · Status: ✅ 2026-11-13 — the docs and RESTRAINT_BODY_CONTACTS_UNCHECKED landed; the bonds direction is WP-1816
Track: What fires, and what stays silent
Depends on: —

## Goal

Two atoms of one rigid body that a declared torsion can bring together are
either restrained and reported like any other contact, or documented as
deliberately unrestrained. Which of the two is the maintainer's choice on
issue #1507.

## Context

Issue #1507 (mustachefeeling, 2026-11-09). The anti-bump builder
`anti_bump_restraints(..., exclude_same_body=True)` in
`src/rietx/model/restraints.py` (WP-1809) gives no row to two atoms in the
same copy of one rigid body. Its docstring says their distance is the
template's, "and a row would only fight the body". The skip is at lines 989
and 1015-1021. `stale_anti_bump_pairs` skips the same pairs ("as the builder
skips them"), so the plan-end `RESTRAINT_PAIRS_STALE` warning is silent on
them too.

The reason stopped holding with WP-1808: a declared torsion turns the atoms in
its `moves` about its axis. Two atoms on opposite sides of the axis then no
longer sit at their template distance. WP-1814's refinable Z-matrix internals
will move most pairs of a Z-matrix body the same way.

**Measured 2026-11-12 at `a86dcf9d4`** (scripts in the triage's scratch, not
committed). A planar zigzag chain N1–C2–C3–C4–C5–O6 (bonds 1.5 Å) as one
body, with torsions about C2–C3 (moving C4, C5, O6) and C4–C5 (moving O6),
in a 20 Å P1 cell, rule `{("N", "O"): 3.0}`:

- at the template N1···O6 is 4.499 Å;
- at twists of −120° and −120° it is 1.498 Å, half the stated minimum;
- the builder returns no N1–O6 row by default, and one with
  `exclude_same_body=False`;
- `stale_anti_bump_pairs` names nothing.

No fit was run. The reporter read the defect from the code; this
reproduces the mechanism, not a fit that walks into it.

**The two options #1507 puts to the maintainer.**

1. Keep the skip and correct the docstring: it holds only for a pair that no
   declared torsion or internal can move.
2. Build rows for every pair a declared torsion or internal can move, and
   skip only the pairs that stay rigid.

**A finding the issue does not raise, which bears on option 2.** Pairs a
single torsion moves include the two ends of the dihedral itself (A and D in
A–B–C–D, a "1-4 pair"). Those sit at about 2.5 Å (cis) to 3.9 Å (anti) in
real molecules, about 3.0-3.1 Å gauche for C–C–C–C. The minimum a caller
states for anti-bump is an *intermolecular* contact distance (#677's rule:
the caller states it; WP-1809's radii question was ruled that way). Applied
to 1-4 pairs, the same minimum would push every gauche or cis torsion
towards anti. Force-field practice excludes 1-2 and 1-3 pairs from the
nonbonded terms and scales 1-4 pairs down (AMBER: Cornell et al., 1995,
*J. Am. Chem. Soc.* 117, 5179; recall, not re-read). So option 2 needs a
topological exclusion or its own minimum for close pairs, and a body may
declare no bonds (`Fragment.bonds` is optional).

**The torsion test.** PR #1510 (WP-1814 chunk C1, open) writes
`model.restraints._refuse_fixed_body_geometry`: a torsion changes a set of
atoms when it turns some of them, other than its own two axis atoms, and not
the others. For a pair that is the predicate option 2 needs, chained torsions
included. Import it once it merges; do not write a second one.

**Tier.** The warning is tier 1: it states a fact about the checks (the
end-of-run search never looks inside one copy of a body, and the builder
skips those pairs by default) where a torsion moved, and gates nothing.
Option 2's "a rigid pair keeps its distance" is physics; the bond-count
exclusion is named practice, surveyed in `docs/practice.md` § Which pairs
inside a molecule a contact term checks. `exclude_same_body`'s default has
no row in `_audit.DEFAULT_SEATS`; if its meaning changes (WP-1816), the
default gets one.

## Non-goals

- Refinable Z-matrix internals (WP-1814). Their pairs join this rule when
  that WP lands, through the reach it builds (`fragments.zmatrix_reach`,
  PR #1509).
- Choosing minimum distances for the caller (#677's rule stands).

## Tasks

- [x] The maintainer's choice on #1507. **Decided 2026-11-13** (ruled by
      Yue 2026-11-13: "both"). (1) Now, here: correct the docs, and warn when
      anti-bump meets a body with torsions, saying contacts inside the
      molecule are not checked. (2) The direction, filed as WP-1816: the
      stored `RigidBody` keeps its declared bonds (optional field, `None` =
      undeclared, old files open; WP-1319's never-perceived rule kept). With
      bonds, anti-bump restrains intra-body pairs four or more bonds apart
      that a torsion moves; pairs one to three bonds apart are excluded, not
      scaled, because a floor on a torsion's ends biases the conformation and
      a preference belongs in a torsion prior. Without bonds, the warning.
- [x] The docstrings of `anti_bump_restraints` and `stale_anti_bump_pairs`
      say which pairs the skip covers, and that a torsion-moved pair is among
      them; the theory chapter's anti-bump paragraph says the same.
- [x] The warning `RESTRAINT_BODY_CONTACTS_UNCHECKED` at plan end (`fit`
      and `run_stage`): a phase with an anti-bump row at the start, and a
      body torsion whose wrapped `angle` moved during the run. The message
      counts the rows the list holds inside the body
      (`model.restraints.body_own_rows`), which do not silence it. Audit rows
      (code and suggestion, tier 1), help entry, silence pair.
- [x] Tests: the six-atom chain above (fires, and the folded pair still has
      no row and no stale report); fires and counts the rows of a list built
      with `exclude_same_body=False`; silent for an unturned torsion, for one
      declared at −180 and written back as 180, for a body without torsions;
      the biphenyl fit on both entry paths. Positive control: with the
      emitter's gate disabled, both firing tests fail.
- [x] Skill: a `RESTRAINT_BODY_CONTACTS_UNCHECKED` row in
      `references/diagnostics.md`.
- [x] File WP-1816 for the bonds direction, coordinated with WP-1814, and
      record the practice survey in `docs/practice.md`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_one_sided_restraints.py tests/test_body_torsions.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #1507; issue #759 (the Z-matrix proposal); issue #677 (the
  caller-stated minimum).
- Cornell, W. D. et al. (1995), *J. Am. Chem. Soc.* 117, 5179 (AMBER's 1-4
  scaling).

## Handover log

### 2026-11-13 — the warning and the docs land; the bonds direction filed as WP-1816 (PR #1562)

A fit that turns a torsion inside a rigid body now says that the anti-bump checks do not look inside that molecule. Before, a chain could fold to half its stated minimum with no row, no stale report and no message. The docstrings and the theory chapter now say which pairs the skip covers, and that a torsion-moved pair is among them. Yue's direction for the real fix, a body that keeps its declared bonds and anti-bump rows for pairs four or more bonds apart, is filed as WP-1816 and proposed to Mike before anything is built. The intramolecular-exclusion practice behind that ruling is now in `docs/practice.md`.

*Done.*
- Ruled by Yue 2026-11-13 on #1507 ("both"); the ruling is recorded under Tasks.
- `RESTRAINT_BODY_CONTACTS_UNCHECKED` (warning, plan end, `fit` and `run_stage`): a phase with an anti-bump row at the start, a body torsion whose wrapped `angle` moved. The message names the body, each torsion as start° → end°, and counts the rows the list holds inside the body (`model.restraints.body_own_rows`). Rows do not silence it, because `stale_anti_bump_pairs` skips the body's own pairs whatever the list holds. Audit rows (code and suggestion, tier 1, ambiguity 1, scope as `RESTRAINT_PAIRS_STALE`), help entry, silence pair, skill row in all three copies.
- `model.restraints._is_own_copy`: the one own-copy test, read by the builder's skip and by `body_own_rows`.
- WP-1816 filed (rigid-bodies, P3), coordinated with WP-1814 (cited, not edited). Practice section "Which pairs inside a molecule a contact term checks" with its sources.
- The rewritten #1507 comment, which proposes the direction to Mike and asks three questions, is in the runner's scratch (`~/.cache/ghostshift/rietx/wp-2144/comment_1507.md`). Nothing posted.

*Review.* `/code-review high --fix` raised 8. Fixed: the suggestion pointed at `result.geometry.contacts`, where a pair folded to 1.5 Å is listed as a bond (now `distances`); one hand row silenced the warning for the whole body (now counted, not silencing); the `exclude_same_body=False` docstring overclaimed; the own-copy test was copied twice (now one helper); the new code's scope had no test (the scope test now runs for both codes); the message claimed neighbouring contacts are checked (sentence removed). Declined: searching the body's own pairs at plan end, which is WP-1816's rule; a tolerance on "turned", which would be a new number.

*Generality* (judge's sections, condensed by the author; verdicts unedited).
- `RESTRAINT_BODY_CONTACTS_UNCHECKED` (code): **holds**. Tier 1 and ambiguity 1 agree. Case against: moderate, on level only. It fires on most fits that free a torsion under an anti-bump list, including methyl or hydroxyl rotors whose moved pairs WP-1816 will exclude anyway. The ruling chose the warning channel. Evidence that would change it: a measured run of real molecular refinements where it fires on nearly every freed-torsion fit with no fold found. The narrowing to "a torsion moved" is the author's, not the ruling's; a body that arrives folded with its torsions held gets no warning. Author: kept, since a held torsion cannot have folded anything the run did not start from.
- `.suggestion`: **holds**; the case against (no caution about a floor on a torsion's ends) was taken: the suggestion and help entry now warn off it and name holding the torsion.
- The exact-inequality "moved" test: **weak**, a misfire for a torsion declared at −180 (written back as 180 with nothing turned). Fixed: both sides are wrapped, and a test pins it.

*Measured* (`[dev]`, darwin/arm64, this worktree's venv).
- The chain: N1···O6 4.499 Å at the template, 1.498 Å at twists −120°/−120°, no row, no stale report, the warning fires. Positive control: with the emitter's gate disabled, both firing tests fail.
- Touched files (8 test files): 165 passed.
- Fast selection (`-m "not slow"`, on main merged in at `ca949ac65`): 14596 passed, 433 skipped, 32 xfailed, 1 failed. The failure was `test_multi_diagnostics.py`'s helper-scope partition, which wanted a `multi.DIAGNOSTIC_SCOPES` row for the new helper; the row (absent: a joint fit refuses soft restraints) landed after, and that file then ran 129 passed. Added tests: 4 cases plus the parametrised rows (silence pair, scope test, multi scope row); their cost 2.06 s, 1.96 s of it the biphenyl fit, which stays fast-tier as the only end-to-end check of both entry paths. Run queued behind two other suites through serial.py, so alone on the machine.
- `python -m tests.reader_output`: exit 0, unchanged against the merge-base. Its fixtures carry no body with a torsion, so the new warning is a reader-visible line it does not cover (the text is in the PR body).
- Full suite not run: the change adds a diagnostic and moves no fitted number.

*Next.* Yue reads the new warning's text (a reader-output change). Then the comment goes to Mike on #1507, and his answer folds into WP-1816 before its first commit. WP-1816 also waits on #1510's merge for the moved-pair predicate.

- **2026-11-12** — created, from the 2026-11-12 issue triage (issue #1507).
  Checked against the tree at `a86dcf9d4`: the skip and its reason are where
  the issue says, the stale check shares the skip, and a folded chain reaches
  1.498 Å under a 3.0 Å minimum with no row and no warning. No open WP owns
  it: WP-1809 (the builder) and WP-1808 (torsions) are closed, and WP-1814's
  scope leaves the skip alone by its author's statement on the issue. Next:
  the maintainer's choice, then PR #1510's merge for option 2.
