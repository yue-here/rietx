# WP-1967 — what the chemist declares reaches the extinction screen

Milestone: unscheduled · Status: ✅ 2026-10-23 — a declared chirality, centre of symmetry or polarity filters each extinction class and names what it removed (PR #940); Z and density are WP-2033's
Track: Data and metadata in, a structure out
Depends on: 1910 soft (the screen's default, PR #939, shares this work's functions)

## Goal

A caller can declare what the chemistry rules out (an enantiopure, a
centrosymmetric or a polar compound), and the extinction screen drops the
space groups that contradict the declaration from each class and names them.
With nothing declared the screen still gives a good answer, and no caller is
made to declare anything.

## Context

**Source.** Issue #935 (2026-10-13). `determine_extinction_symbol` returns
classes whose members a powder cannot separate
(`EXTINCTION_GROUPS_NOT_SEPARABLE`) and leaves the choice to chemistry. There
is no way to state the chemistry, so the user drops groups by hand. The
issue's case is a P2₁ organic salt (Z = 2, structure from a published SI). The
screen answers `P 1 2₁ 1` = {P2₁, P2₁/m} at ΔBIC −61.7 on two testable 0k0
absences, and a declared chirality leaves P2₁. The issue also asks for a
Laue-class fork inside a class. `P - - -` on a hexagonal lattice holds P6/m
and P-31m, which differ only in how overlapped multiplets partition, so a
structure solution that follows runs once per Laue class rather than once
per member.

**Checked against the tree at `ee589bab`.** `determine_extinction_symbol` is
`indexing/extinction.py:705` and `EXTINCTION_GROUPS_NOT_SEPARABLE` is
`indexing/diagnostics.py:890`. The screen takes no declaration and groups no
members by Laue class. The issue's ΔBIC comes from its own data and was not
reproduced here.

**Decided 2026-10-14** (the maintainer, answering the PR-review batch): yes,
as PR #940 builds it. Two conditions bind the work. The screen's default must
be good when nothing is declared, and no caller is ever made to declare. The
PR's questions, and one from the review, answered:

1. Z and density as a member filter: a follow-up, outside #940. It needs
   Wyckoff multiplicities, which gemmi does not ship.
2. A class the declaration empties is still fitted (about 0.1 s a class).
   That fit is how a wrong declaration shows up.
3. `restrict` is not carried on to `IndexingResult` or
   `structure_from_candidate` now. The screen is where the choice is made.
4. A declaration may steer `best_or_none`. It picks among the classes the
   declaration leaves a member in, and abstains when the data prefer an
   emptied class by the decisive margin. Every removed group is reported.

**Rules that bind the work.** `INDEXING_THRESHOLDS_VERSION` bumps when an
answer can move. Each fact is read off the group's operators, never a table:
gemmi's `is_sohncke` and `is_centrosymmetric`, and polarity as an invariant
vector shared by every rotation. A new diagnostic code needs its skill row.

## Non-goals

- The screen at a small cell error, and its default prefit (WP-1910, PR #939).
- The blind search's use of what the chemist knows (WP-1510, shipped in 1.7; its open window
  and Z-check work is WP-2030).
- Z and density inside #940 (decided as a follow-up; WP-2033 since the close).

## Tasks

- [x] **Decision (maintainer):** the issue's proposal, whole or in part,
      recorded as `Decided YYYY-MM-DD:` here and answered on #935.
      *Decided 2026-10-14: yes, as PR #940 builds it (Context).*
- [x] Review and merge PR #940 against the two conditions: answers with
      nothing declared stay as on `main`, and `restrict` stays optional on
      every surface.
- [x] ~~Follow-up: Z and density as a member filter, from Wyckoff
      multiplicities derived off the operators.~~ Moved at the close to
      [WP-2033](2033-a-declared-z-filters-the-extinction-class.md), by the
      maintainer's decision of 2026-10-23.
- [x] Tests (#940 carries `tests/test_extinction_prior.py`), and
      `tests/test_acceptance_indexing.py` green.
- [x] Skill: the two new codes' rows (#940 puts them in
      `references/abstention.md`, since `diagnostics-indexing.md` is over its
      budget).

## Acceptance

A declared chirality removes every non-Sohncke member and names it. A
declaration the data contradict ends in an abstention, never in the declared
answer. With nothing declared, every extinction screen in the tree answers as
on `main`.

```sh
.venv/bin/python -m pytest tests/test_extinction_prior.py tests/test_extinction_symbol.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #935; PR #940.
- Flack, H. D. (2003). *Helv. Chim. Acta* 86, 905: the Sohncke groups, the
  ones a chiral compound can occupy.
- Markvardsen, A. J., David, W. I. F., Johnson, J. C. & Shankland, K. (2001).
  *Acta Cryst.* A57, 47: a powder measures the extinction symbol.

## Handover log

- **2026-10-23** — closed by the maintainer's decision. A caller can now
  declare that a compound is enantiopure, centrosymmetric or polar. The
  extinction screen drops the members that contradict the declaration and
  names each one, and with nothing declared it answers as before. PR #940 met
  the Goal and every acceptance line on 2026-10-17 (entry below). The one box
  left open was the follow-up the maintainer split off on 2026-10-14: a
  declared Z or density, which needs each group's Wyckoff orbit sizes. That box
  is now [WP-2033](2033-a-declared-z-filters-the-extinction-class.md). It was
  filed at this close because no open WP owns a declared Z for the screen.
  2030 holds Z in the search, and 1910 holds the screen at a small cell error.
  Issue #935 stays open for that half. The one `### Inherited` bullet was
  #940 itself, and its merge discharged it. *Next:* nothing owed here.
- **2026-10-14** — created, from the 2026-10-14 issue triage (issue #935).
  Checked against the tree at `ee589bab`: both symbols the issue names exist
  where cited, and nothing lets a caller declare chemistry to the screen. No
  open WP owns it. WP-1910 holds the screen's behaviour at a small cell
  error, which the issue fences out ("about declaring the chemistry, not the
  cell"). WP-1510's chemistry reaches the search, not the screen, and every
  task there has landed. The maintainer decided it the same day (Context).
  *Next:* PR #940's review.
- **2026-10-17** — PR #940 merged from outside (`c93c4213`, head `53094b28`),
  after four review rounds. Gated with PR #951 and the one-word test fix #1031
  on one merged tree (`8b8287fb`), macOS arm64, `[dev,jax]` venv, alone on the
  machine: ruff clean; the fast suite 10 854 passed, 120 skipped, 2 xfailed
  and 1 failed; the full `-m slow` suite 321 passed and 12 skipped, which
  includes `tests/test_acceptance_indexing.py`. The fast failure was a
  wall-clock margin in `test_events_aggregator.py` missed by 5 ms under load.
  It passes alone, and neither PR touches the events code. After #951 merged,
  `main` was the gated tree byte for byte. Both conditions hold: with nothing
  declared no ranking and no `best_or_none` moves, and `restrict` is optional
  on every surface. The merge lets a caller declare chirality, centrosymmetry
  or polarity to `determine_extinction_symbol` and get the contradicting
  members named in `excluded_groups`. It deliberately does not carry
  `restrict` on to `IndexingResult` or `structure_from_candidate` (decision
  3), and does not filter on Z or density. A gotcha for the next PR here: #940
  and #951 each added a history line under `INDEXING_THRESHOLDS_VERSION` 1.11,
  and the two lines conflicted as adjacent text. A sync commit on #951 kept
  both, #940's first. PR #939 (WP-1910) now conflicts with `main` and has a
  rebase request. Issue #935 stays open for the Z and density half.
  *Next:* the Z and density filter, from Wyckoff multiplicities derived off
  the operators.
