# WP-2144 — the anti-bump same-body skip, now that a torsion moves the pair

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 1814 soft (its chunk C1 writes the torsion test this reuses, PR #1510)
Priority: P3 2026-11-12 — was P2 (a clash nothing flags, on a path few fits run): waits on the maintainer's choice on #1507

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

**Tier.** Option 1 adds no rule. Option 2's "a rigid pair keeps its distance"
is physics; a 1-4 exclusion is named practice (force fields), cited above.
`exclude_same_body`'s default has no row in `_audit.DEFAULT_SEATS`; if its
meaning changes, the default gets one.

### Inherited

## Non-goals

- Refinable Z-matrix internals (WP-1814). Their pairs join this rule when
  that WP lands, through the reach it builds (`fragments.zmatrix_reach`,
  PR #1509).
- Choosing minimum distances for the caller (#677's rule stands).

## Tasks

- [ ] The maintainer's choice on #1507, recorded here as `Decided YYYY-MM-DD:`.
- [ ] Option 1: the docstrings of `anti_bump_restraints` and
      `stale_anti_bump_pairs` say which pairs the skip covers. Option 2: the
      builder and the stale check keep rows for torsion-moved pairs, with the
      close-pair treatment the decision names, through PR #1510's predicate.
- [ ] Tests: the six-atom chain above (a folded pair gets a row and is named
      stale, or the docstring's claim is pinned); a pair that no torsion
      moves keeps the skip; a positive control that fails with the change
      reverted.
- [ ] Skill: option 2 adds nothing an agent must know beyond the builder's
      docstring; option 1 adds one line to the anti-bump row of
      `references/diagnostics.md` (`RESTRAINT_PAIRS_STALE`) saying a body's
      own pairs are never named.

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

- **2026-11-12** — created, from the 2026-11-12 issue triage (issue #1507).
  Checked against the tree at `a86dcf9d4`: the skip and its reason are where
  the issue says, the stale check shares the skip, and a folded chain reaches
  1.498 Å under a 3.0 Å minimum with no row and no warning. No open WP owns
  it: WP-1809 (the builder) and WP-1808 (torsions) are closed, and WP-1814's
  scope leaves the skip alone by its author's statement on the issue. Next:
  the maintainer's choice, then PR #1510's merge for option 2.
