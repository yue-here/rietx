# WP-2005 — `refine.py`'s codes and its inline literals

Milestone: generality · Status: ⬜
Track: The audits
Depends on: 2002
Priority: P3 2026-10-23 — 2002 closed, its last item touching no code here; codes, not actions; a verdict here is a flag the caller reads, and the workaround is to read past it

## Goal

Each of the 61 diagnostic codes raised in `src/rietx/refine.py` is in the audit table with
a tier, and each inline literal that gates one (about 30) is either a named constant in the
table or recorded as tier 1. A tier-3 verdict that fails either ground is demoted: its
`level` drops to `info`, or, where the threshold was its trigger, the code becomes an
`info` record with no threshold (the record § Demotion).

## Context

The rule is `../milestones/generality.md` § The rule. 2002 owns the *actions* in this file
and lands first; this WP owns the codes, which are what an agent reads.

`refine.py` is 9 587 lines and raises 61 codes (`grep -o 'code="[A-Z0-9_]*"'`, 2026-10-18).
Each has an explanation in `rietx.help.DIAGNOSTIC_HELP` (WP-1985) and a `level`. The
open's count found about 30 inline numeric literals in comparisons, two named by the
second review: `< 0.7` in the flat-plate thickness test (`ABSORPTION_PLATE_THICKNESS`,
~line 6819) and `>= 2.0` further down (~line 8467). An inline literal is invisible to
2001's tripwire, which walks module-level constants, so this WP lifts each that gates a
verdict into a named constant with its value in the table, or records why it is tier 1 (a
count, a dimension, a physical limit).

**Five codes no seam names come here too**, since each is raised beside a fit rather than
in a reader or a report: `BACKGROUND_ORDER_AT_CAP` (`background/select.py`),
`BRINDLEY_OUTSIDE_REGIME` and `MICROABSORPTION_SKIPPED` (`optimize/qpa.py`),
`DECLARED_RANGE_RESTORED` and `DECLARED_RANGE_NOT_RESTORED` (`schemas/migrate.py`). The
four in `strategy/` are 2002's.

**Families.** The size-flag thresholds are calibrated on one 1 213-record archive (~line
9069): many files, one population, one family. Count by lab, instrument and material.

**What the caller reads.** Every code carries an explanation (WP-1985), and under
DESIGN.md § Rules, 3 that explanation is what teaches the reader, agent or person. 70 of
the tree's codes are not mentioned in the agent skill, and under the skill's role (the
record § Decisions) that is no defect. Whether the skill routes a code is no evidence for
its tier.

### Inherited

- **From WP-2037 (2026-10-24, second session, PR #1145): this WP's codes are the view's loudest, so their responses decide how quiet it gets.** Over the eight `rietx compare` standards' fits (darwin/arm64), `HIGH_CORRELATION` is 44 % of all warning rows, `FLAT_DIRECTION` takes the running total to 69 % and `FLOOR_HIT` to 87 %. On cpd-1a under `qpa`, 49 of 57 warnings still print in full, 24 of them `HIGH_CORRELATION` and 22 `FLAT_DIRECTION`, because a code still on `_audit.RESPONSE_BASELINE` stays a warning under every purpose. Giving each a response (and its `where`-derived purposes) is what quiets the view; each one given `response="warning"` adds its pair to `tests/silence.py` (`FLOOR_HIT` has one). `rx.diagnostics_summary` and `python -m tests.suite_alarms` re-measure the numbers.
- **From WP-2002 (2026-10-21, 4th session): tier 2 names seven programs.** `docs/milestones/generality.md` § The rule's tier 2 now reads "by default in an established Rietveld program": GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD and EasyDiffraction, the list rietx-bench runs (the maintainer's instruction). A row resting on a program default names the programs it checked and what each does; a program doing otherwise by default is a dissenter, one without the feature is neither. What each does on peak windows, staging, roughness starts, width limits, dispersion, solver, mode and background seed is in `docs/practice.md`; where each program's manual or source sits is in the maintainer's memory (`foreign-code-sources-on-disk`), and rietx-bench's `tools/` holds BGMN, MAUD, RIETAN-FP and EasyDiffraction's environment beside GSAS-II and FullProf.
- **From WP-2002 (2026-10-20, PR #1050): `OCCUPANCY_ABOVE_ONE` is new** (`refine._occupancy_flag_diagnostics`, a warning when a refined occupancy exceeds 1, from the B9 ruling). With no significance gate it fires on counting noise about half the time on a freely refined full site (synthetic LaB6, 1.032 ± 0.025). Whether to gate it is with the maintainer; the message quotes the distance above 1 in esds.
- **From WP-2002 (2026-10-20, PR #1050): `HUMP_MIN_WIDTH_MULT` is a diagnostic threshold** (it gates `HUMP_TOO_NARROW`; it also floors a hump's width in the extinction screen, `indexing/extinction.py:737`), so it belongs with the other diagnostic-only constants handed here (B13). The suggestions of `SIZE_UNUSUALLY_SMALL` and `STRAIN_UNUSUALLY_LARGE` said a finite `Parameter.max` silences them; neither reads `max`, and both now say the flag changes nothing in the fit.
- **From WP-2002 (2026-10-19, PR #1050).** 2002's batch class B13 proposes handing 34 constants to this WP, pending the maintainer's ruling. Each is the threshold of a code raised in `refine.py` and gates no action. The list with each code is `2002-batch/batch.md` § The B13 hand-off table, and each row's provenance is in `2002-batch/inventory.json`. If WPs 2005-2007 are cancelled at the gate after 2004, these rows need another home.

## Non-goals

- The holds, releases, seeds and bound tests: 2002.
- Codes raised elsewhere: `report/` 2004; `io/`, `crystallography/`, `gui/` 2006;
  `indexing/` 2007; `sequential.py` and `multi.py` 2003; `strategy/` 2002. The five
  named above are the whole remainder.
- Rewriting an explanation's text (1985's voice stays); only `level`, the threshold and
  whether the code exists.

## Tasks

- [ ] Inventory: the 61 codes with raise site, `level`, the threshold or condition, the
      explanation's claim, the kind of ambiguity its verdict has (DESIGN.md § Rules, 1),
      and how many tests touch it.
- [ ] The inline literals: each lifted to a named constant (table row with value) or
      recorded tier 1 with the reason.
- [ ] Tier each code per part, with evidence and families.
- [ ] The batch to the maintainer; rulings dated into the table.
- [ ] Approved demotions: `level` to `info`, or, where the threshold was the trigger, the
      code replaced by an `info` record with no threshold that states the number (the
      record § Demotion); the explanation's observation sentence updated where the verdict
      went; the release notes staged for every removed or renamed code.
- [ ] Goldens re-pinned only if no further from reference (a code change moves no number;
      a lifted literal must not either, pinned by a bit-identity check before and after).
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: none here. A code that keeps a verdict is explained by its
      `DIAGNOSTIC_HELP` entry (DESIGN.md § Rules, 3). List each skill row that names a
      demoted code, for 2008 (the record § Decisions, the skill's role).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- `docs/milestones/generality.md`; WP-1985; WP-1076 (a declared name is a claim).

## Handover log

- **2026-10-18** — created, from the milestone's opening session, split out of 2002 on the
  second review's finding that one WP over 9 587 lines of actions *and* codes is too big
  for one session.
