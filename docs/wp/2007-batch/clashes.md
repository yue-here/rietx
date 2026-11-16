# WP-2007 clash table: grading × gating × the `best_or_none` gate

Task 4 of WP-2007. A clash is two or three rules where one rule's outcome decides what another
reads, so the result says something neither rule alone would justify. The rules are the grading
rules (`IndexCaveat`, `INDEX_REFUTING_CAVEATS`, `consensus.caveats_for` and `grade`,
`MIN_AGREEMENT`), the gating rules (`INDEX_DATA_INSUFFICIENT`, `PEAK_UNUSABLE_FLAGS` and the ghost
flags, `max_candidates` and `ENGINE_POOL_MULTIPLE`, the `quick` ceiling and the per-unit budget,
`VALIDATION_RESERVE_FRACTION`, `CONSENSUS_CHECK_TOP`) and the two `best_or_none` gates.

Tree: `94a35558b` (this worktree's HEAD, read 2026-11-16T12:03Z). Every file:line below is at that
sha. Proposed tiers are the ones in `inventory.json` (`proposed` for constants and defaults; the
statistic/threshold/action triple for codes). **Nothing here is a ruling.** Each section ends with
a question for the maintainer.

**Measurements.** Two, both run on 2026-11-16 on the Mac (darwin/arm64, worktree `.venv`), one at
a time through the ghostshift serial runner. Logs: `~/.cache/ghostshift/rietx-src/wp-2007/clash_1.log`
and `clash_8.log`; the scripts are in this session's scratchpad and are quoted in each section.
(M1) `synthetic_peaks("cubic", two_theta_max=150.0)` (the fixture of `tests/test_indexing_ceiling.py:42`),
systems cubic, tetragonal, hexagonal, `preset="full"`, peaks only: 10.3 s, 12 candidates.
(M2) `index_pattern(data=data, instrument=ins)` on qarr SRM 676a corundum
(`tests.test_acceptance_indexing._qarr("corundum.prn")`), every default, so `quick`: 107.3 s,
12 candidates. Wall clock depends on machine load, so M2's reach is one sample.

## Summary

| # | Rules (proposed tier) | Effect | Verdict | Question |
|---|---|---|---|---|
| K1 | unchecked → `geometric_ambiguity` (refuting) × `CONSENSUS_CHECK_TOP` (1) × the `quick` ceiling (3) | Every listed candidate outside the checked set is `low`, and the clock can shrink the checked set. A 2-of-3-engine cell at rank 4+ goes from `medium` to `low` with no data read. | Partly. Mechanism verified. In M2 the clock cut the search, not the sweep, and 0 of 8 unchecked grades moved because K9 already made every candidate `low`. | Should an unasked ambiguity question cap (`medium`) rather than refute? If it refutes, can `CONSENSUS_CHECK_TOP` stay tier 1? |
| K2 | `validation_failed` (refuting, action 3) × WP-2076 "a raised fit is no evidence" × help text | A fit that raises refutes the candidate. The help text says the candidate is "neither supported nor refuted". The extinction screen leaves a raised class unscored. | Verified. Not measured. | Should a raised fit cap like `not_validated`, with `diverged` kept refuting? |
| K3 | `shift_allowance_assumed` (capping; INDEX_SHIFT_ALLOWANCE action 3) × `best_or_none` default paths | Where the pair screen declines, `high` is out of reach, so the CLI exits 1 and prints "NO CELL". | Partly refuted. Every fitted corpus list measures its shift from pairs, so the caveat does not fire there. It fires on position lists and where the screen declines. | Should the dossier sentence be narrowed to "where the pair screen declines"? |
| K4 | `INDEX_DATA_INSUFFICIENT` (action 3) × `usable()` flags and ghost flags (B13 pending) | Flags remove lines before the line count is taken. The refusal needs fewer than 5 usable lines. The live effect is the 20-line bar: below it the search is narrowed to the systems the count supports. | Partly. Mechanism verified. Refusal by flags only on lists of a few lines. Not measured. | Should the narrowing and the refusal name how many lines the flags removed? |
| K5 | `DEFAULT_MAX_CANDIDATES` (1) × `CONSENSUS_CHECK_TOP` (1) × `VALIDATION_RESERVE_FRACTION` (3) × #1375 | 12 listed, about 4 checked. Ranks 5-12 are never validated or enumerated. Corroborated cells sort first, so a single-finder rank 1 can drop off. | Verified. M2: 4 of 12 checked, 8 neither validated nor enumerated. The reserve half is superseded (WP-2011). | Is the reported cap tier 1 when 8 of its 12 rows can only grade `low`? |
| K6 | `MIN_AGREEMENT` (3) as ranking key and grade floor × system-major truncation × `DEFAULT_BUDGET_SECONDS` (3) | In the system the clock catches, later engines never enter. Its cells lose finders, grade `low` and sort below every corroborated cell. The inlier retry is skipped when the clock has fired. | Partly. Verified for the caught system. Completed systems keep every finder, as the dossier says. Not measured. | Should a cell from a truncated system be ranked on a finder count the clock set? |
| K7 | `REFERENCE_NET_RWP_MAX` (3, approved) × `DECISIVE_DELTA_BIC` (2) × the GUI's `best` | The approved grounds say no default path calls the pick. The GUI serves and badges it. A 1 %-off PbSO₄ cell passes the reference gate. | Verified for the GUI path. Whether a wrong class is badged today is not re-measured. | Do the 2026-10-21 grounds stand now that the GUI route calls the pick? |
| K8 | the ambiguity sweep after validation × `run_cancel` × refuting unchecked | If the clock fires during validation, the sweep skips every candidate. Then every candidate is `low`, validated ones included. | Verified in the code. Not reached in M2 (the search stopped at the reserve boundary; validation and the sweep finished). | Same as K1. Should a fully unswept result say so in INDEX_BUDGET_EXHAUSTED? |
| K9 | `fom_panel_disagrees` (refuting, result-level, no row) × the list's composition (systems reached, the ceiling, `max_candidates`) | One boolean over the reported list refutes every candidate. A longer search adds cells that win some member, and the certified cell drops from `high` to `low`. | Verified and measured: LaB6 acceptance row; M1 12 of 12; M2 12 of 12. | Should panel disagreement cap rather than refute, or be read per candidate? |
| K10 | `best_or_none` "exactly one high" × `grade` per candidate | Two cells at `high` abstain even when the data separate them (Rwp 0.098 against 0.250). | Verified and measured (LaB6 calibrated row). | Should a second `high` the data separate block the pick? |
| K11 | `not_validated` (capping) × the benchmark's `promoted` field | The benchmark indexes position lists, so no candidate can reach `high` and `promoted` is always False. | Verified in the code. | Drop the field, or record what it can vary on? |

## K1. Unreached ambiguity × the check cap × the ceiling

**Rules.** `caveats_for` writes `geometric_ambiguity` for a candidate that was not enumerated
(`consensus.py:671-674`). It is in `INDEX_REFUTING_CAVEATS` (`schemas/indexing.py:703-706`), so the
candidate grades `low` (`consensus.py:765-767`). INDEX_GEOMETRIC_AMBIGUITY: statistic 2, threshold 3,
action 3. `CONSENSUS_CHECK_TOP` = 3 (`consensus.py:94`), proposed tier 1. The `quick` ceiling
`QUICK_TOTAL_BUDGET_SECONDS` = 120 (`engines.py:2345`), proposed 3.

**Mechanism.** The checked set is the top three plus every candidate every engine found
(`checked_indices`, `consensus.py:402-431`). The gate reads `outcome.ambiguity_checked`, what the
sweep actually covered (`workflow.py:1180-1184`). Two things leave a candidate out of it:
1. Scheduling. A candidate at rank 4 or lower that two of three engines found is never scheduled.
   Without the unchecked rule it would carry `engines_disagree` (capping) and grade `medium`. With
   it, `low`. The docstring's guarantee is about `high` only: "the only kind the gate can promote
   to `high`" (`consensus.py:409`). It does not cover `medium`.
2. The clock. The sweep runs after validation on the whole-run deadline (`workflow.py:1156`) and
   checks the token between candidates (`consensus.py:611`). A stopped candidate stays unchecked.

The design relies on this reading: the reserve comment says the enumeration "is the one the gate
already reads conservatively when unasked" (`engines.py:2358-2359`). The dossier says the
streamed lists are `low` for the same reason (`indexing/CLAUDE.md:85`).

**What the result says.** A `low` that names `geometric_ambiguity` reads as "a derivative lattice
explains the lines equally well". For these candidates no derivative lattice was looked at.
INDEX_GEOMETRIC_AMBIGUITY does not fire on them (inventory row), and INDEX_BUDGET_EXHAUSTED counts
unvalidated candidates but not unswept ones (`engines.py:2312-2313`).

**Measured.** `tests/test_indexing_consensus.py:404-414` pins an unchecked candidate at `low`. M2
(corundum, quick, 107.3 s): the clock stopped the search at the reserve boundary (tetragonal and
orthorhombic truncated, monoclinic and triclinic not reached). All 4 checked candidates were swept.
Ranks 5-12 were unswept by scheduling and carry `geometric_ambiguity` with no partners. Removing
that caveat moves 0 of 8 grades, because every candidate also carries `fom_panel_disagrees` (K9).
M1 gives the same: 2 unchecked, 0 moved, all 12 carry `fom_panel_disagrees`. So on both runs K9
hides K1.

**Question.** Is an unasked ambiguity question capping or refuting? WP-1986 asked and WP-2013
rewrote the words to "refuting". If it stays refuting, can `CONSENSUS_CHECK_TOP` be tier 1? Its
cut changes the grade of rows outside it.

## K2. `validation_failed` refutes a fit that raised

**Rules.** `validation_failed` is refuting (`schemas/indexing.py:703-706`), written on status
`failed` or `diverged` (`consensus.py:685-686`). INDEX_VALIDATION_FAILED: statistic 1, action 3.
WP-2076: "a raised fit is no evidence" (`indexing/CLAUDE.md` § The governing rule).

**Mechanism.** `validate_by_lebail` turns any exception into `status="failed"`
(`workflow.py:553-570`). Its docstring calls that "evidence about the candidate"
(`workflow.py:499-501`), and the caveat's comment agrees (`schemas/indexing.py:668-670`). The help
entry says "nothing was measured for it. The candidate is neither supported nor refuted", and that
an instrument error "fails every candidate alike" (`help.py:3229-3236`). The extinction screen
treats a raised fit the other way: "a fit that raised says nothing about the absences, so its class
stays unrefuted and unscored" (`extinction.py:1452-1454`). A cancelled fit is already kept out
(`workflow.py:503-512`, tested at `tests/test_indexing_ceiling.py:156-208`).

**What the result says.** A mis-declared instrument raises on every checked candidate. Each is then
`low` by refutation, and every unchecked candidate is `low` by K1. The whole list reads as refuted
by the data, when the data were never compared.

**Measured.** No test or WP record measures a raised validation on real data.

**Question.** Should a raised fit cap (like `not_validated`), and `diverged`, which is a
measurement, stay refuting under its own caveat? This is the inventory's question on the row.

## K3. `shift_allowance_assumed` × the default paths that call `best_or_none`

**Rules.** `shift_allowance_assumed` is capping (`consensus.py:719-720`), so `high` needs a
measured or declared shift. INDEX_SHIFT_ALLOWANCE: statistic 3, threshold 3, action 3;
`DEFAULT_UNKNOWN_SHIFT_DEG` proposed 2. `best_or_none` needs exactly one `high`
(`schemas/indexing.py:2245-2263`). Default callers: the printed verdict line
(`schemas/indexing.py:2231-2237`), `index_end` (`workflow.py:1208-1215`), the CLI exit code
(`cli.py:374`), the GUI's picked row (`gui/session.py:2593`) and adopt label (`gui/session.py:2836`).

**Mechanism.** The allowance is assumed only when nothing was declared and the data-quality report
has no trusted shift (`engines.py:1263-1273`). The pair screen sets a trusted shift when it detects
one (`quality.py:343-375`; `TRUSTED_SHIFT_SOURCES`, `schemas/indexing.py:496`).

**Refuted in part.** The pair screen detects on every fitted list in the corpus (z ≥ 4.2), and on
none of the ten bethanechol position lists or HL2 (z ≈ 0) (`pairs.py:35-38`). The corundum and
LaB6 acceptance rows assert the caveat is gone (`tests/test_acceptance_indexing.py:1140-1142`,
`:2123-2127`), and M2 logged `INDEX_SHIFT_FROM_PAIRS` (allowance 0.0690°). `rietx index` always
picks from a pattern (`cli.py:362-365`). So on the corpus the CLI's exit 1 does not come from this
caveat. It comes from `engines_disagree`, `fom_panel_disagrees` (K9) and two `high` cells (K10).
The dossier sentence "On real data with no measured shift, `high` is unreachable"
(`indexing/CLAUDE.md:55`) is true as written. The GUI comment (`gui/session.py:1975`) reads as if
it held on all real data.

**Still open.** Where the screen declines on a fitted list, the caveat fires and every default
path abstains. How often that happens outside the corpus is not measured.

**Question.** Narrow the GUI comment to "where the pair screen declines"? And do position-only
callers need to know that `high` is closed to them twice (K11)?

## K4. `INDEX_DATA_INSUFFICIENT` × the flags that remove lines

**Rules.** `MIN_LINES_PER_DOF` = 5 (`schemas/indexing.py:476`, proposed 3) and
`MAX_RELATIVE_SIGMA_Q` = 1e-3 (`:481`, proposed 3). INDEX_DATA_INSUFFICIENT: action 3, still
refuses (`workflow.py:962-976`). `PEAK_UNUSABLE_FLAGS` (`schemas/indexing.py:846-849`) includes
`ghost_kbeta` and `ghost_tungsten`, set by `flag_ghosts` on the default pick
(`pick.py:95-96`, `:191`). The seven `GHOST_*` constants are B13, pending (inventory
`b13_pending`). `PEAK_MIN_USABLE_LINES` = 20 (`schemas/indexing.py:455`, proposed 2).

**Mechanism.** `assess_peak_list` counts `peaks.usable()` (`quality.py:422`), and `q()`/`q_esd()`
read usable lines only (`schemas/indexing.py:1085-1089`). The refusal fires when no system has
5 lines per DOF (`quality.py:482-485`). Cubic has 1 DOF (`schemas/indexing.py:466-469`), so this
needs fewer than 5 usable lines. Flags can reach it only on a very short list. The σ(Q)/Q arm takes
a median over usable lines (`quality.py:442`), so removing a line can move it either way.

The effect that does reach real lists is the 20-line bar. Below it, `_restrict_to_supported`
narrows the search to the systems the count supports (`workflow.py:657-681`, called at `:891`),
and every candidate caps with `fom_panel_reduced` (`consensus.py:677-682`). At 19 usable lines,
monoclinic (20 needed) and triclinic (30) are not searched. Two ghost flags on a 21-line list do
that. INDEX_PANEL_REDUCED names the systems searched (`diagnostics.py:620-631`). The count of lines
the flags removed is on the report as `n_total` against `n_usable` (`quality.py:492`); no
message joins the two.

**Measured.** No test measures a list crossing either bar because of flags.

**Question.** Should the narrowing and the refusal name the flagged lines that moved the count? And
should the per-DOF and σ(Q)/Q arms report rather than refuse (the inventory's question on
INDEX_DATA_INSUFFICIENT)?

## K5. The reported cap × the checked set × the reserve × #1375

**Rules.** `DEFAULT_MAX_CANDIDATES` = 12 (`engines.py:316`, proposed 1); `ENGINE_POOL_MULTIPLE`
= 5 (`:331`, proposed 3); `CONSENSUS_CHECK_TOP` (proposed 1); `VALIDATION_RESERVE_FRACTION` = 0.15
(`engines.py:2385`, tier 3, approved 2026-10-28).

**Mechanism.** Consensus ranks the whole merge and keeps 12 (`consensus.py:503-507`;
`engines.py:2095`). Only the checked set is validated (`workflow.py:1106-1146`) and swept (K1).
The rest read `not_validated` (capping) and unchecked `geometric_ambiguity` (refuting), so they are
`low` whatever their data. `rank_candidates` sorts corroborated cells first
(`engines.py:2080`, `:2093`). A list with 12 or more corroborated cells reports no single-finder
cell, which is WP-2112's seam (`docs/wp/2112-an-engines-first-cell-stays-in-the-reported-list.md`
§ Context).

**Measured.** M2: 12 listed, 4 checked and validated (all `converged`), 8 neither validated nor
swept. Ranks 8-12 have one finder. The reserve half is superseded: WP-1986's FAP run that validated
none of 12 was at 8 %, Le Bail and rank-order slices. WP-2011 moved to Pawley, cheapest first and
15 %, and then FAP validated every checked cell (`engines.py:2366-2373`; inventory row). #1375 has
not been re-run on this tree (WP-2112 § Tasks, first box).

**Question.** Is the reported cap a listing cap (tier 1) when two thirds of its rows can only be
`low` by construction? Or should rows outside the checked set be marked "unchecked" rather than
graded?

## K6. `MIN_AGREEMENT` × the clock's cut inside a system

**Rules.** `MIN_AGREEMENT` = 2 (`engines.py:337`, proposed 3), read by the ranking key
(`engines.py:2098-2117`) and the grade floor (`consensus.py:765-767`). `DEFAULT_BUDGET_SECONDS` =
30 per unit (`engines.py:296`, proposed 3). The `quick` ceiling (proposed 3).

**Mechanism.** The scheduler runs systems in order and engines inside each in registry order,
`dichotomy`, `svd`, `trial_error` (`engine_names()`), and checks the search deadline before each
unit (`workflow.py:998-1006`). When the deadline fires inside a system, the engines after that point
never enter it. That system is marked incomplete (`consensus.py:548-550`), so its cells cap with
`search_incomplete`. Its cells also have fewer finders. One finder is below `MIN_AGREEMENT`, so the
cell is `low` and sorts below every corroborated cell, and so is the first to leave the 12 (K5).
With the reserve, the search has 102 s of `quick`'s 120. One system can take 3 × 30 = 90 s, which
is #1374. When no lattice is corroborated, the inlier retry runs only if the clock has not fired
(`workflow.py:1019-1022`), so a clock-cut run never gets the retry.

**Refuted in part.** A completed system keeps every finder. The dossier says so
(`indexing/CLAUDE.md:62-65`), and the code agrees: an engine enters the next system only after all
engines finished the current one.

**Measured.** Not measured. M2 truncated tetragonal and orthorhombic. Corundum is trigonal, so its
truth was not touched. The `quick` comment says the truth's own system completes on all six corpus
runs (`engines.py:2333-2338`). The corpus is high-symmetry.

**Question.** In the system the clock catches, should a cell's finder count (ranking key and
floor) be read as "not reached by engine X" rather than "not found by engine X"?

## K7. The extinction screen: reference gate × ΔBIC margin × the GUI's `best`

**Rules.** `REFERENCE_NET_RWP_MAX` = 0.7071 (`extinction.py:167`, tier 3, approved 2026-10-21).
EXTINCTION_SCREEN_UNRELIABLE (tier 3, approved). `DECISIVE_DELTA_BIC` = 10 (`extinction.py:153`,
proposed 2, Kass & Raftery). `ExtinctionScreen.best_or_none` (`schemas/indexing.py:2614-2662`).

**Mechanism.** Status `unreliable` makes `best_or_none` abstain (`schemas/indexing.py:2641-2642`)
whatever the margin. Otherwise the top class needs a 10-unit margin (`:2658-2660`). The GUI route
calls it (`gui/session.py:2803`) and serves `best` (`:2804-2807`). The panel marks that class with a
`best_or_none()` chip (`gui/src/panels/Peaks.svelte:918-920`). The screen runs on any candidate,
not only a picked one (`gui/session.py:1973-1980`).

**Verified clash.** The approved grounds of EXTINCTION_SCREEN_UNRELIABLE say "no default path
calls the pick" (`_audit.py:684-685`). The GUI route calls it. The constant's own record shows
the reference gate missing a cell 1 % off: PbSO₄ at ×0.99 reads 0.45 on the Le Bail reference
"(a wrong class returned)" (`_audit.py:682`), and 0.30 on the Pawley reference re-measured on
2026-11-07 (`_audit.py:2473-2476`). Whether today's screen returns a wrong class there is not
recorded.

**Measured.** Partly: the reference readings above. Not the class returned on today's tree.

**Question.** Do the 2026-10-21 grounds still hold with a default GUI path calling the pick? If
not, is DECISIVE_DELTA_BIC the unanimity margin for that pick (the inventory's question on
EXTINCTION_SYMBOL_AMBIGUOUS), and does PbSO₄ ×0.99 need a re-run first?

## K8. The clock fires during validation, and the sweep is skipped for all

**Rules.** As K1, plus the order: validation first, then the sweep on what is left
(`workflow.py:1089-1097`, `:1153-1156`).

**Mechanism.** If the whole-run deadline fires during validation, the loop breaks
(`workflow.py:1130-1132`, `:1141-1145`). `enumerate_ambiguity` then skips every candidate, since the
token is set (`consensus.py:611`). `ambiguity_checked` is empty, so every candidate, validated or
not, gets `geometric_ambiguity` and grades `low`. A validation that finished does not lift it.
INDEX_BUDGET_EXHAUSTED counts unvalidated candidates only (`engines.py:2312-2313`).

**Measured.** Not on real data. M2 stopped the search at the reserve boundary; validation and the
sweep then finished inside the ceiling (107.3 s). The sweep was measured at 45 s of a 105 s
ceiling-bound corundum run (`consensus.py:452`, `:594-596`; `workflow.py:1089-1091`), against
the 18 s reserve, before WP-2063 made the panel cheaper.

**Question.** Same as K1. Also: should INDEX_BUDGET_EXHAUSTED count candidates the sweep did not
reach?

## K9. `fom_panel_disagrees` is one list-level fact that refutes every candidate

**Rules.** `fom_panel_disagrees` is refuting (`schemas/indexing.py:703-706`). It has no audit row
(the inventory asks about it under `INDEX_MIN_INDEXED_FRACTION`). It is computed once, over the
reported list (`consensus.py:508-510`; `fom.py:981-995`), and written onto every candidate
(`consensus.py:675-676`). The list is set by the systems reached (the `quick` ceiling), the pool and
`max_candidates`.

**Mechanism.** The flag is True when the panel's members put different candidates first
(`fom.py:991-995`). `indexed_fraction` favours large cells by design (`fom.py:1005-1007`), so a list
holding a supercell and its parent will often disagree. Adding a system adds cells, and one new cell
that wins one member makes every candidate `low`. Under `quick` the systems reached depend on wall
clock (`tests/test_indexing_ceiling.py:303-306`).

**Measured.** LaB6 (SRM 660c), four systems, `preset="full"`: the certified cell, found by all
three engines, is `low` on `fom_panel_disagrees` alone, and "on a cubic-only search the run
promotes to `high`" (`tests/test_acceptance_indexing.py:2132-2137`). The only real-data `high`
in the suite is a cubic-only search (`tests/test_acceptance_indexing.py:687`, `:2827`). M1: 12 of
12 candidates carry it. M2: 12 of 12, the certified R cell included.

**What the result says.** "The data refute this cell" for every cell, when the fact is "the list
holds cells the members rank differently". A shorter search can grade the truth higher than a
longer one.

**Question.** Should panel disagreement cap rather than refute, or be read per candidate (does this
candidate lose a member to a cell that is not its own supercell)?

## K10. "Exactly one `high`" × per-candidate grading

**Rules.** `best_or_none` returns a cell only when exactly one candidate is `high`
(`schemas/indexing.py:2259-2263`). `grade` judges each candidate alone (`consensus.py:733-770`).
`unmatched_observed` is not read as a caveat (`consensus.py:650-662`).

**Mechanism and measurement.** On the calibrated LaB6 row the certified cell is `high` with no
caveats (`tests/test_acceptance_indexing.py:2827-2829`), and so is the a·√2 I cell
(`:2864-2866`). `best_or_none` abstains (`:2867`). The rival's Rwp is more than twice the truth's
(`:2876`; 0.098 against 0.250 in the test's table). The test calls this a defect and says the block
inverts when it is fixed (`:2831`, `:2863`).

**Question.** Should a second `high` that the data separate (Rwp, `m_rev`) still block the pick?
Or is that a grading fix, so `best_or_none` stays as written?

## K11. `not_validated` × the benchmark's `promoted`

**Rules.** `not_validated` caps every candidate when no pattern is supplied (`consensus.py:683-684`).
INDEX_NOT_VALIDATED: action 3.

**Mechanism.** `tests/bethanechol_benchmark.py:287` calls `index_pattern(peaks, ...)` with no
pattern, so no candidate can be `high`. `promoted` (`:323`) is `best_or_none() is not None`, so it
is always False. The position lists also score z ≈ 0 on the pair screen (`pairs.py:36-37`), which
adds `shift_allowance_assumed`.

**Measured.** Code reading only.

**Question.** Drop `promoted` from the benchmark record, or replace it with something a run can
vary on (the top candidate's grade)?
