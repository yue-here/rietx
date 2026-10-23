# WP-2030 — A formula's volume window fits inorganic cells, and a hydrate parses

Milestone: unscheduled · Status: 🔄 2026-10-23 — claimed by @mustachefeeling (#1121); part 1 (the measurement and the fixes that need no ruling) is up, the window rule waits on the maintainer
Track: Data and metadata in, a structure out
Depends on: — (1510 soft, closed 2026-10-23: the window, the Z check and the review findings this carries)
Priority: P2 2026-10-23 — a defect that fires wrongly: the skill sends an agent through `SearchSpec.from_formula` before its first search, and the window excludes the true cell of 7 of 8 inorganic solids measured (fluorapatite abstained where the unwindowed search ranked the truth first); indexing is a path few fits run

## Goal

`SearchSpec.from_formula` gives a window that holds the true cell of an
inorganic solid as well as an organic one, or says that it cannot, and
`INDEX_Z_NOT_INTEGER` stays silent on a true inorganic cell. A hydrate
written `CuSO4.5H2O` is read as a hydrate or refused, never read silently as
4.5 O. Each review finding WP-1510 left open is fixed or declined with its
reason.

## Context

**What exists** (WP-1510, PR #690, shipped in 1.7).
`crystallography/atomic_volume.py` holds Hofmann's (2002) Table 2, and
`formula_unit_volume(formula, temperature)` sums it.
`SearchSpec.from_formula(formula, z=…, temperature=…)`
(`indexing/engines.py:419`) sets
`min_volume`/`max_volume` to z formula units × `VOLUME_RATIO_BOUNDS` =
(0.8, 1.25), Hofmann's 25 % boundary (1746 of 182 239 structures lie outside
it, § 3). With `z=None` it sets only the floor.
`index_pattern(formula=, temperature=)` reports `INDEX_Z_NOT_INTEGER` (warning, `value` = the implied
Z) per candidate and never narrows. Its tolerance `Z_INTEGER_TOLERANCE` is
2 × `VOLUME_SCATTER` = 0.08 (`indexing/diagnostics.py:503`), so above
Z = 6.25 it is silent by arithmetic.

**The window misses most inorganic cells.** Measured by WP-1986's session on
2026-10-18 with `SearchSpec.from_formula(formula, z=…)` against each known
cell. The figure is the window's midpoint over the true volume, at each
cell's true z (the four the entry left blank were re-measured 2026-10-23):

| formula | z | midpoint / true V | true cell |
|---|---|---|---|
| NaCl | 4 | 1.18 | inside |
| C8H9NO2 (paracetamol) | 4 | 1.05 | inside |
| CaF₂ | 4 | 1.69 | outside |
| Al₂O₃ | 6 | 2.74 | outside |
| ZnO | 2 | 2.17 | outside |
| Ca5P3O12F (fluorapatite) | 2 | 1.81 | outside |
| LaB₆ | 1 | 1.96 | outside |
| Si | 8 | 1.91 | outside |
| Na2Ca3Al2F14 (NAC) | 8 | 3.22 | outside |

The midpoint is 1.025 × z × V_est, so the truth lies inside only while the
ratio is between 0.82 and 1.28 (arithmetic on the shipped bounds). Every miss
is an overestimate, so the floor is what excludes the truth. LaB₆ holds one
formula unit, so even `z=None`'s floor sits about 1.5× above its true cell
(0.8 × 1.96 / 1.025). On the shipped fluorapatite pattern
(`src/rietx/data/examples/FAP.XRA`) the windowed search took 127 s, ranked
only cells of 1000-1050 Å³ and abstained. The same search unwindowed put the
true 523.6 Å³ cell first. `INDEX_Z_NOT_INTEGER` rests on the same volume, so
on fluorapatite's true cell it implies Z = 1.14 and fires.

**The source says so.** Hofmann's table is fitted to organic and
metal-organic crystals. He found 496 structures overestimated by 25-75 %,
often highly ionic with small cells, and says the volumes may not apply to
inorganic substances (§ 3 (iii)). `atomic_volume.py`'s docstring records
this, yet `from_formula` applies the table to any formula. The skill
recommends it twice: § 7d of `docs/skill/rietx/references/diagnostics-indexing.md`
("Before the first search, ask for the cell or infer it"), and
`references/abstention.md`, which sets `max_volume` from it for a large
monoclinic or hexagonal search. An agent that follows either gets a wrong lead,
and nothing tells it so.

**The Z tolerance's trade-off** (WP-1510, 2026-10-03). One crystal scatters
4 % about Hofmann's estimate, so the source run's Z ≈ 2.8 reads as "3, within
the method" and does not fire. Flagging it would need a tolerance under
6.7 %, and Hofmann's Table 1 puts about a third of correct cells more than
5 % off. Nobody has asked for that change.

**The hydrate parse.** `_parse_formula` (`atomic_volume.py:154`) splits an
adduct on `·`, `•` or `*`, and a count may be decimal. So `CuSO4.5H2O` reads
as 4.5 O and comes out 39 % low, silently, and the grammar cannot tell it
from `Mg0.5SiO3` (WP-1510's review, 2026-10-03). The review's candidate fix:
refuse a `.` hydrate and point to `·`.

**The rest of WP-1510's review, still open** (sites checked 2026-10-23):
- `IndexingResult` (`schemas/indexing.py:1861`) records no formula, so a
  reopened result cannot say which formula its Z check read. `formula` does
  not reach the CLI (`cli.py:343`, the `index_pattern` call) or the GUI
  (`gui/session.py:1618`).
- `INDEX_DATA_INSUFFICIENT` leads with an undeclared instrument
  (`diagnostics.undeclared_instrument`, `indexing/diagnostics.py:338`) when
  the axial apertures are zero or the profile is the default `ProfileTCHZ`. A
  correctly set-up synchrotron instrument has both, so the lead misfires
  there. And the documented two-step flow, `index_pattern(peaks)` with no
  instrument, never sees the lead: `PeakList` (`schemas/indexing.py:881`) does
  not record the instrument it was picked with.
- The supercell test (`ambiguity.supercell_chance`, `:708`) judges which
  observed lines the parent explains (`explained`, `:814`) with the child's
  shift correction applied to the parent's lines. That count drives
  `consensus.above_supported_parents` (`:324`), which ranks a supported child
  directly above its parent. Whether the promotion earns a rule in
  `src/rietx/indexing/CLAUDE.md` was left open; the rulebook records only the
  refuted direction (WP-1449). 1510's lane replay over 13 captured searches
  moved only corundum's order, 8th → 1st.
- The GUI peak editor's `duplicate_line` marks go stale when the owning
  component moves. `gui/peaks.py`'s `_spliced` (`:525`) re-flags only the
  edited group (`flag_duplicate_lines(merged, only=…)`). 1510 declined it
  twice: clearing other groups' flags would undo a user's flag edits
  (WP-1043), and `gui/peaks.py` forbids editing other groups. Its last entry
  still listed it open.

**Tiers** ([generality § The rule](../milestones/generality.md#the-rule)).
Hofmann's volumes and the 0.8-1.25 boundary are tier 2 for organic and
metal-organic crystals, cited (Hofmann 2002, § 3). The citation does not
reach past that population. Any rule deciding which formulas the table
serves, and any window or volume source for the rest, is tier 3 unless a
cited inorganic source carries it. Tier 3 means at least three unrelated
families, each checked against its certified or published cell
(`tests/data/README.md`). The window removes cells from the search, so it is
an action. Name its kind before choosing (DESIGN § Rules, 1): a narrowing
that can exclude the truth on a formula its source does not cover is not one
every competent refiner would make. `Z_INTEGER_TOLERANCE`'s factor 2 is
tier 3 over a tier-2 scatter. `INDEX_Z_NOT_INTEGER` is a flag, so the
mechanical ground asks that it fire on a cell of non-integer Z and stay
silent on true cells. A refusal of an ambiguous formula string is tier 1.
Gating the instrument lead on a lab source is tier 1 if it reads the declared
source. `VOLUME_RATIO_BOUNDS` (WP-2006's walk) and `Z_INTEGER_TOLERANCE` and
`INDEX_Z_NOT_INTEGER` (WP-2007's) sit at `unaudited` in
`src/rietx/_audit.py`. A value changed here updates its row, and a name new
to the table arrives tiered (CI's `tests/audit_delta.py`).

## Non-goals

- Replacing Hofmann's table for organic and metal-organic formulas, where the
  window held (paracetamol 1.05; benzoic acid 16.7 Å³ per non-hydrogen atom,
  WP-1510).
- Letting the Z check narrow or remove candidates. It reports (1510's
  agent-first rule).
- Widening the default box, any engine change, or ranking beyond the
  supercell count (1449, 1511).
- Replaying `solution case 1`: its pattern is a collaborator's unpublished
  data and is not in this tree.

## Tasks

- [x] Re-measure the table above on this tree, at the true z and at
      `z=None`, adding any inorganic standard in `tests/data/` it lacks.
      Pin it in `tests/test_indexing_formula.py`.
- [ ] Decide the inorganic rule from that measurement. Candidates: a
      ceiling-only window outside Hofmann's population, since every measured
      miss is an overestimate; a cited inorganic volume source; or the window
      kept with a warning. Record the choice, the rejected options and why in
      the handover. Test that every measured true cell lies inside its window.
- [ ] `INDEX_Z_NOT_INTEGER`: silent on every measured true cell, still firing
      on an injected cell of non-integer Z.
- [ ] Fluorapatite: `from_formula("Ca5P3O12F", z=2)` holds the 523.6 Å³ cell,
      and the windowed search on `FAP.XRA` ranks it where the unwindowed one
      does.
- [x] Hydrate: `CuSO4.5H2O` is refused, naming `·`, or read as a hydrate.
      `Mg0.5SiO3` still reads 0.5 Mg and `CuSO4·5H2O` is unchanged. Test all
      three.
- [ ] `formula` and `temperature` recorded on `IndexingResult`, with the
      writer named (root CLAUDE.md: a declared name is a claim). `formula`
      reaches the CLI and the GUI's indexing call.
- [x] The instrument-first lead fires only on a lab source. Decide whether
      `PeakList` records its instrument so `index_pattern(peaks)` sees the
      lead. Test both.
- [x] Supercell: judge the parent's lines with the parent's own shift. Replay
      the captured searches and run the indexing acceptance. Then write or
      decline the supported-promotion rule in `src/rietx/indexing/CLAUDE.md`.
- [ ] GUI: fix the stale `duplicate_line` marks or decline them, with the
      reason in the handover.
- [ ] Audit rows for every value changed or name added (tiers above).
- [ ] Manual: `docs/docs/theory/indexing.md` and `reference/indexing.md`
      state the window's scope; a staged release note.
- [ ] Skill: § 7d and `abstention.md` say when the window applies. Stay
      inside `tests/skill_caps.py`'s budget and re-sync the copies
      (`rietx skill --install . --copy`).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_indexing*.py -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_skill.py -q
.venv/bin/python -m ruff check src tests examples
```

And: every true cell in the measured table lies inside its window (a test),
the windowed fluorapatite search ranks the 523.6 Å³ cell where the
unwindowed one does, and `CuSO4.5H2O` never reads as 4.5 O.

## References

- Hofmann, D. W. M. (2002). *Acta Cryst.* B58, 489–493. Per-element volumes;
  § 3 (iii) on inorganic substances. In the corpus at
  `zotero-linker/derived/XULHS76B/`.
- Kempster, C. J. E. & Lipson, H. (1972). *Acta Cryst.* B28, 3674. The 18 Å³
  rule, organic.
- A candidate inorganic source, read before citing: Jenkins, H. D. B.,
  Roobottom, H. K., Passmore, J. & Glasser, L. (1999). *Inorg. Chem.* 38,
  3609–3620. Formula-unit volumes from ion volumes.
- WP-1510 (closed 2026-10-23): the window, the Z check, the review findings.
  WP-1986's 2026-10-18 entry: the measurement above.
- #1121: the claim, and the plan of two PRs (the measurement and the fixes
  that need no ruling, then the window rule once it is chosen).

## Handover log

- **2026-10-23** — Part 1 of 2 (#1121): the measurement, and the fixes that
  need no ruling. The window holds the true cell of 1 of 16 inorganic solids
  and 4 of 5 organic or metal-organic ones; the window rule is the
  maintainer's choice, set out on #1121 with these numbers. A hydrate written
  with a full stop is refused, the result records its formula, the
  instrument lead reads the declared source, and the supercell check reads
  the parent's lines on the parent's own shift.

  *Done.* (1) `tests/test_indexing_formula.py` pins 21 known cells, each
  with its source: 16 inorganic (the NIST certificates for LaB6, Si and
  corundum; NAC, fluorapatite, the five round-robin minerals, cBN, three
  GSAS-II tutorial cells and COD's YBCO; halite's 5.6402 Å) and 5 organic
  or metal-organic (paracetamol, benzoic acid from COD 7252065, bethanechol
  chloride, HKUST-1, a hybrid iodide). V_obs/V_est: 0.375-0.649 on 15
  inorganic cells, halite 0.866; 1.000-1.044 on four organic ones, HKUST-1
  2.283 (its formula leaves the pores' contents out, Hofmann § 3 (ii)). The
  window at the true Z holds halite and the four; at `z=None` the floor of
  one formula unit still excludes the three Z = 1 cells (LaB6, brucite,
  YBCO). **The Context table's NAC row uses z = 8; COD 1000236 gives Z = 4**,
  so its midpoint ratio is 1.61, not 3.22, and the cell is still outside.
  (2) `INDEX_Z_NOT_INTEGER` fires on 12 of the 16 inorganic true cells and
  is silent on every organic one; the four it spares imply the wrong whole
  number (Si 4.30 for 8). (3) `formula_unit_volume` refuses a full stop
  that reads both as a decimal count and as a hydrate's dot, naming `·`
  (tier 1, an ambiguous string); `Mg0.5SiO3`, `CuSO4·5H2O` and a spaced
  CIF formula are unchanged, while `Fe2.95O4` is now refused too and reads
  as `Fe2.95 O4`. (4) `IndexingResult.formula` and `.temperature`, written
  by `index_pattern` on both its paths (`None` with no formula), and
  `rietx index --formula --temperature`. (5) `diagnostics.lab_source` reads
  the declared source: a Kα doublet, or one anode's Kα1 as `radiation=`
  writes it. The instrument lead fires only there. `PeakList` records the
  undeclared blocks (`instrument_undeclared`, written by `pick_peaks` and
  `fit_peaks`) rather than the whole instrument, and the record outranks
  an instrument handed in later. (6) `supercell_chance(parent_q_obs=)`;
  `supercell_checks` hands each candidate its own `scored_positions`. A
  synthetic pair whose corrections differ by a 0.2 % metric scale read
  supported before and undecided now. The supported-promotion rule is
  declined for `src/rietx/indexing/CLAUDE.md`: the file sits at its
  340-line cap, the rule is stated where the code is (`supercell_chance`'s
  "Support asks a narrower count", `above_supported_parents`), and the replay
  below found no new case for it. No audit row was owed: no
  number, code, default or record field the table walks was added or moved.

  *Measured* (own `[dev]` venv, macOS arm64, pearl offline). Replay of the
  22 consensus calls the indexing acceptance makes (100 parent-child pairs,
  20 candidates carrying a shift): no count, verdict or order moved.
  `tests/test_acceptance_indexing.py`: 44 passed in 14:44. Fluorapatite on
  `FAP.XRA` (hexagonal and trigonal, preset full, the acceptance row's
  budgets): unwindowed 157 s, truth ranked 1; the shipped window
  (738-1153 Å³) 28 s, truth absent, the 1050 Å³ cells lead; a ceiling alone
  (15-1153 Å³) 36 s, truth ranked 1. Bethanechol sets Aa and E (monoclinic,
  20 Å axes, default budgets, every search budget-truncated): the window
  took 70 and 76 s, the ceiling alone 89 and 95 s, no volume 97 and 111 s;
  set E ranked the truth 8th windowed and 1st in both others, Aa nowhere.

  *Not done, for part 2.* The window rule (task 2) and what rests on it:
  the Z check (task 3; no tolerance silences it on every measured true cell
  and still fires on an injected Z = 2.5, since LaB6 and YBCO sit 48 % from
  1, so it needs the same population test the window does), the
  fluorapatite task (4), the audit rows the rule adds (10), the manual's
  scope sentences (11) and the skill (12). `formula` in the GUI's indexing
  call (half of task 6): it needs an `IndexingControls` field, so the form,
  its vitest corpus and a rebuilt dist, which belongs with task 9's GUI
  work. The stale `duplicate_line` marks (9): not attempted. Hofmann (2002)
  is not on this machine (the corpus path above is the maintainer's) and
  Jenkins et al. (1999) is closed; neither was read here.

  *Next.* The maintainer's choice of window rule on #1121, then part 2.
- **2026-10-23** — created by WP-1510's close, from its `### Inherited`
  (WP-1986's window measurement, 2026-10-18) and the review findings its
  2026-10-03 entries left open. No open WP owned `from_formula`, Hofmann, a
  hydrate or `formula=`, nor the instrument lead, the supercell count or the
  GUI marks (grep of `docs/wp`, 2026-10-23). Nothing built.
