# WP-2078 — Weak lines from another phase push the true cell off rank 1

Milestone: unscheduled · Status: 🔄 2026-11-12 — tasks 1-4 done (PR #1543); waits on the maintainer decision written in the 2026-11-12 handover entry
Track: What fires, and what stays silent
Depends on: — (1969 soft: the inlier rule answers the same failure by another mechanism; 2066 soft: the reporter's dichotomy rows predate it)
Priority: P2 2026-11-02 — a ranking defect with a hand workaround: on the reporter's private benchmark the true cell ranks first on 48 of 172 host and one-impurity lists under all three engines, and on 75 when the search is given only the lines at or above 1 % of the strongest; thinning the list by hand is the workaround

## Goal

On a picked list that carries weak lines the host phase does not own (a
second phase, picker noise), the indexer still ranks the true cell first. A
host whose weak lines are its own (a superlattice) keeps its true cell. A
position-only list searches exactly as it does today.

## Context

**Source.** Issue #1291 (2026-11-01), a proposal by the recurring
contributor, with a re-run on `main` posted the same day. The proposal: index
a picked list on its usable lines at or above 1 % of the strongest usable
line, beside the list as picked.

**What the reporter measured.** An internal benchmark on private patterns,
quoted as counts only. Twenty host patterns (lab, synchrotron and neutron,
including the Si, LaB₆, CeO₂ and Al₂O₃ standards). Three derived families:
imp1 (153 lists, one impurity phase injected each), thin (68 lists, lines
removed at random) and controls. The derived families are not independent of
the hosts. Picking was `pick_peaks` at `PEAK_FDR_Q` = 0.01 with every flag
kept. Truth compared by `rank_of_lattice` (band 5e-3, 0.5°). The re-run is on
`f4db776`, preset `quick`, a 120 s ceiling per list, one thread.

Truth at rank 1 on host + imp1 (172 lists with a truth):

| engine | as picked | 1 % floor | 2 % floor |
|---|---|---|---|
| svd | 40 | 67 | 57 |
| dichotomy | 53 | 71 | 62 |
| trial_error | 35 | 57 | 60 |
| all three | 48 | 75 | 63 |

- Paired against the same engine as picked, the 1 % floor gains on all three
  families and loses no host list. The exact McNemar p lies between 1.5e-8
  and 1.1e-5.
- The 2 % floor loses lists: imp1 +17/−9 under dichotomy and +23/−9 under all
  three, plus a host list under svd.
- Why not higher: two hosts carry structural weak lines (a pyrochlore's
  superlattice lines, a trirutile-type oxide). At 2 % and 5 % the floor
  removes the lines that separate the true cell, and a subcell or a wrong cell
  ranks first. On those hosts the working window is about a factor of 2 wide.
- Controls: no control gains a candidate graded `medium` under any single
  engine. Under all three engines, three controls that contain a real lattice
  gain `medium` candidates on the floored lists. The reporter reads that as a
  grading question (several descriptions of one lattice graded `medium`).
- A strongest-N cap (N = 8 to 20) came close only as five searches merged,
  and fell behind on thin (22 against 25).
- Removing broad lines, dropping tail- or bound-flagged lines, and σ×3 on
  flagged lines did not help.
- The dichotomy rows predate PR #1301 (WP-2066), which changes the dichotomy
  search. The svd and trial_error rows do not depend on it.

**Where the gain is: the searched list.** The re-run split search from
scoring with a harness wrapper. Arm X searched the list as picked, then
merged, ranked and validated against the 1 % list. Under svd it gained
nothing (g = 0.00, where g = 1 would put the whole gain in scoring); under all
three engines g = 0.15. Arm Xr also narrowed the searched systems to those the
1 % list supports, because a list under 20 usable lines searches only
`quality.systems_supported` (`workflow._restrict_to_supported`). That gave
g = 0.26 under svd. So about a quarter of svd's gain is the narrower systems,
and the rest is which lines the search is given. **The reverse split was not
measured**: search on the floored list, score on the full list. That is the
shape of the seam the package already has (below), so it is the cheapest
candidate and task 2 measures it.

**Checked against the tree at `992b7048f`.** Every name the issue cites
exists.
- `engines.search_line_order` (`indexing/engines.py:1140`) drives the search
  with the strongest `DEFAULT_SEARCH_LINES` = 20 lines (`:140`), drawn from a
  low-Q pool of `SEARCH_POOL_MULTIPLE` × 20. Scoring reads every usable line.
  WP-1039 measured that raising N bought nothing and that the rank, not the
  count, fixed `11BM_NAC.fxye`.
- `PEAK_UNDRIVEN_FLAGS = {"weak_line"}` (`schemas/indexing.py:872`; `:858` at `992b7048f`) is the
  existing "scored, never driven" seam (#934): a flagged line stays in
  `usable()` and never enters the driven set. Below `DRIVEN_MIN_LINES` = 6
  unflagged lines the strongest flagged ones come back. `weak_line` is a
  significance screen (Benjamini–Hochberg on I/σ_I at `PEAK_FDR_Q` = 0.01,
  `:314`). The issue measured that the harmful lines pass it: moving the q
  from 0.001 to 0.05 moved the false-kept count only from 139 to 151.
- `DEFAULT_N_UNINDEXED` = 2 (`engines.py:173`): a cell is accepted only if
  all but two driven lines index. Reading, not measured: a third non-host line
  among the driven twenty refuses the truth, which is the failure WP-1969's
  inlier rule (`INDEX_INLIER_RETRY`) retries when no two engines agree.
- Ties in `search_line_order` fall back to Q order, and
  `PeakList.from_positions` gives every line weight 1. A relative floor
  therefore removes nothing from a position-only list, and the bethanechol
  benchmark searches unchanged.
- `consensus.grade` (`consensus.py:759`) grades `low` when
  `len(set(found_by)) < MIN_AGREEMENT`. An arm merged "like an engine" under
  its own name would let one engine on two lists count as two opinions. That
  is the hazard the arm design must close: `found_by` stays engine names.
- `rank_of_lattice` is a test helper (`tests/indexing_gallery.py:373`).
- `tests/reader_output.py` diffs a Rietveld fit's printed text. It does not
  cover `str(IndexingResult)`, so this WP shows that diff by hand.

**Prior art, surveyed 2026-11-12** (task 1; `docs/practice.md` § Which lines
an indexing search is given). Every program read chooses its search lines by
count and position, the first twenty or so, and reviews or scores with every
line. TOPAS and McMaille let intensity weight a line. GSAS-II, DICVOL, TREOR,
ITO and Conograph never read it. One program floors by intensity by default:
EXPO's N-TREOR09, at a value its chapter does not state (secondhand, through
ITC Vol. H ch. 3.4). No front end read (GSAS-II, WinPLOTR) offers an
intensity threshold when it builds the list. The literature offers a floor as
a *second attempt*: Bergmann et al. (2004) gave every program both the raw
list and the I ≥ 5 % Imax list, and called removing weak peaks a retry, not a
routine step. Their Table 5, four standalone programs × two entries × two
modes: 5 runs better, 1 worse (McMaille, first → not found), 10 unchanged;
after a zero correction 4 better, 0 worse, 12 unchanged. Both entries carry
known impurity lines. So a floor applied before every search is tier 3; a
floor tried after the full list fails has precedent (tier 2).

**Folded from `### Inherited` on 2026-11-12.** Both entries still hold at
`a86dcf9d4`; they now sit here and in task 4.
- **A pure-phase sibling (issue #1382, finding 2; triage 2026-11-05).** On
  `tests._synthetic_silicon.silicon_pattern("flat")` the picker splits the 111
  line into extra components at 28.60° and 28.77°, so the list has 10 usable
  lines where the range holds eight. At `541f0daf7` a trigonal R 3.841/9.380
  ranked first with 9 of 10 lines and cubic F 5.431 second with 8 of 10, all
  three engines finding both. Pawley separated them (R: Rwp 0.118, GoF 4.45;
  F: Rwp 0.0299, GoF 1.12) and the rank did not read it. Here the lines the
  host does not own are picker artefacts, not a second phase. Task 4 measures
  it as fixture (d). The issue's finding 1 is WP-2113.
- **The dichotomy rows are pre-#1301 (WP-2066, closed 2026-11-03).** The
  reporter's one real-data re-measure after #1301, a private orthorhombic-F
  lab list (#1258), moved dichotomy's ranking down: the truth went 5th → 6th
  on its grid cells, and `index_pattern` returned no truth on either tree.
  Task 4 measures dichotomy on `main`, never against the issue's table.

**Tier and the maintainer's gates.** Three gates belong to the maintainer and
none is settled by this file.
1. **The floor's value is a new constant.** Unless the survey finds it as
   established practice (tier 2), it is tier 3, rietx's own. A tier-3 `_audit`
   row needs both grounds and the maintainer's dated `approved` field
   ([generality § The rule](../milestones/generality.md#the-rule)). The
   mechanical ground asks for three unrelated dataset families against a
   reference, with a stated failing case. The reporter's benchmark is private,
   so the public evidence must be built here (task 3).
2. **The default ranking changes**, so `str(IndexingResult)` and
   `CellCandidate` ranks change for a reader. That goes to the maintainer
   before merge. It likely moves `INDEXING_THRESHOLDS_VERSION` (now 1.12).
3. **The kind of action** ([DESIGN § Rules](../DESIGN.md#rules), 1). A hard
   cut acts for every caller. A second arm whose candidates consensus ranks
   with the as-picked arm's lets the data score both. That choice is the
   judgement ground's.

**Cost.** The reporter ran each list under its own 120 s ceiling. A second
arm inside one `quick` run shares one whole-run ceiling, so it either halves
each arm's search or cuts trailing systems. Measured 2026-11-12 (below): the
arm roughly doubles a search's wall time, and on one held-out list the
ceiling then cut the run that had found the truth.

**The families (task 3, 2026-11-12).** Nineteen lists, plus four reruns with
only the host's crystal system declared.
- *Fixtures*, development data: (a), (b), (c) of task 2, and (d), the flat
  synthetic silicon of #1382 (10 usable lines, 8 its own), searched with no
  system declared, as the issue reproduced it.
- *Certified rows of the indexing acceptance corpus*, development data, since
  the indexer's rules were tuned on them: corundum (SRM 676a), zincite,
  zircon, brucite, magnetite, fluorite, NAC, FAP and SRM 660c LaB₆. Each is
  searched over the systems and volume its acceptance row declares.
- *IUCr CPD round-robin mixtures, host plus traces*: cpd-1a (95 % fluorite;
  development data, it is the acceptance corpus's abstention row), cpd-1b (94 %
  corundum) and cpd-1c (94 % zincite), both held out, since no indexing test
  searches them. Truth is each phase's cell; the host is the one that matters.
- *11-BM SRM 660b LaB₆ + cBN*, held out (no indexing test searches it).
- *Controls*: HL2-1 (`hl2_peaks.txt`, the unidentified pattern; development)
  and cpd-1g (three phases at about a third each; held out). A control "gains"
  when a candidate is graded `medium` or `high`.

**Measured (task 4, 2026-11-12).** The harness was session scratch, so each candidate's construction is stated here. `[dev]`, arm64 Mac,
`preset="quick"` (120 s whole-run ceiling), all three engines (plus single-engine rows on (a) and (d)), 187 runs, none raising. The
machine was shared with other runners at a load of 25-105 on 10 cores, so every
wall time is a loaded one, and a run the ceiling cut (`*`) reads machine load,
not the data (WP-1449). Candidates: (1) nothing; (2) the floored list searched
and scored; (3) the floored list driven and the full list scored, by flagging
each line under the floor `weak_line` (the #934 seam); (4) a second search per
engine unit on the floored list, its candidates mapped back onto the full list
and merged under the engine's own name; (5) `n_unindexed="inliers"`. The
truth's rank, then its grade's initial (`l` low, `m` medium, `h` high); `—`
absent.

| list | (1) | (5) | (2) 0.5 % | (3) 0.5 % | (4) 0.5 % | (2) 1 % | (3) 1 % | (4) 1 % | (2) 2 % | (3) 2 % | (4) 2 % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| (a) Mo + MoO₃ trace | — | — | 1m | 2l | 5l | 1m | 3l | 9l | 1m | 3l | 9l |
| (b) double perovskite | 1m | 1m | 1m | 1m | 1m | 2l | 1m | 1m | 3l | 1l | 1l |
| (c) Si + planted | — | — | — | — | — | — | — | — | — | — | — |
| (d) flat Si, picker splits | 2l | 2l | 1m | 1l | 1l | 1m | 1l | 1l | 1m | 1l | 1l |
| SRM 660c LaB₆ | 1l | 4l | 1l | 1l | | 1h | 1l | 1l | 2l | 1l | |
| zincite | 1l | 1l | | | | 1l | 1l | 1l* | | | |
| zircon | 1l* | 1l | 1l | 1l | | 1l | 1l | 1l* | 1l | 1l | |
| brucite | 1l | 1l | 1l | 1l | | 1l* | 1l* | 1l* | 1m* | 1l* | |
| magnetite | 1m | 1m | | | | 1m | 1m | 1m | | | |
| FAP | 1l | 1l | 1l | 1l | | 1l | 1l | 1l* | 1l | 1l | |
| fluorite, cubic only | 1m | 1m | | | | 1m | 1m | 1m | | | |
| corundum, trigonal only | 1l* | 1l* | | | | 1l* | 1l* | 1l* | | | |
| NAC | 1l* | 1l* | | | | 1m* | 1l* | 1l* | | | |
| cpd-1a host, cubic only | 1l | 1l | | | | 1m | 1l | 1l | | | |
| cpd-1b host, trigonal only | 1l* | 1l* | | | | 1l* | 1l* | —* | | | |
| cpd-1c host | 1l* | 1l | 1l* | 1l* | | 1l* | 1l* | 1l* | 1l* | 1l* | |
| LaB₆ + cBN, either phase | — | — | | | | — | — | — | | | |

Blank cells were not run. The 1 % floor removes 0-4 lines from a certified
list (FAP 43 of 135 and NAC 144 of 262, both synchrotron-like long lists),
31 of 38 from (a), 19 of 35 from (b), 4 of 29 from (c) and 1 of 10 from (d).
What the table says:
- **Only the hard floor (2) puts (a)'s truth first.** (3) and (4) find it
  (every engine does) but rank it 2nd-9th: scored on the full list, cells that
  also index the oxide's 29 lines outrank the host's. So the gain is in which
  lines *score*, not only which drive, and the #934 seam cannot deliver it.
- **The hard floor costs (b)'s supercell from 1 %** (the cubic subcell ranks
  first), while (3) and (4) keep it at every floor. That is the trade the
  reporter saw on a pyrochlore, reproduced on a public fixture.
- **(d) is fixed by every floor in every form**; (c) by none, since its planted
  lines sit at 1-5 % of the strongest.
- **The hard floor moves SRM 660c LaB₆**, the absolute anchor. At 1 % it removes
  one line, flagged `kalpha2_residual` (71.94°, 0.6 % of the strongest), and the
  grades go from all `low` to the truth `high` *and* the tetragonal a/√2 rival
  `high` beside it, nine candidates at `medium` or above
  (`INDEX_MULTIPLE_SOLUTIONS`). At 2 % it also removes an
  `asymmetry_unmodelled` line (1.75 %) and the tetragonal rival ranks first.
  A run, not cut. The rival is the known isospectral one positions alone
  cannot separate (`test_positions_alone_cannot_separate_lab6_from_a_half_volume_rival`).
- **The inlier rule (5) helps no list** and drops SRM 660c to 4th, as WP-1969
  measured.
- **The second arm (4) costs time**: zincite 60 → 108 s, zircon 62 → 100 s,
  FAP 73 → 124 s, corundum (trigonal) 66 → 110 s. On cpd-1b (trigonal only)
  the ceiling then cut it, and its corundum, first under (1), went missing.
- **Controls**: no candidate graded `medium` or above on HL2-1 or cpd-1g under
  any candidate (both runs ceiling-cut).
- **Per engine** (single-engine runs on (a) and (d); a single engine grades
  `low` by construction): under (1) no engine finds (a)'s truth; under (2) at
  1 % each ranks it first. Under (3) svd ranks it 1st, trial_error 2nd and
  dichotomy not at all; under (4) 3rd, 4th and absent. On (d) svd ranks Si
  first unfloored, dichotomy and trial_error second; every engine ranks it
  first under (2), (3) and (4) except trial_error (2nd) under (3) and (4).
- **Not measured**: the reporter's controls question on real patterns that
  contain a lattice; a finished search on the cut real lists (a quiet machine,
  or a declared ceiling, would give one).
- **Side finding**: on LaB₆ + cBN (held out, two major phases, 92 usable lines)
  no candidate finds either phase, in 8-17 s, with `INDEX_INLIER_RETRY` and
  `INDEX_SEARCH_INCOMPLETE`. A floor is no answer there; it goes to WP-1969.

**The trigger (2026-11-13).** Ruled (B), the floor runs only when the
full list's search gives no answer, and the ruling asked first whether a
trigger exists that stays silent on correct runs whose candidates are all
`low`, SRM 660c among them. The package already has one test of "no answer":
`workflow._no_agreement`, no lattice that two engines agree on. It is the
inlier retry's trigger. Two readings of it were measured on all 19 lists plus
the four host-system reruns, as picked, under `preset="full"`. That preset has
no whole-run ceiling, but each (engine × system) unit keeps its own budget,
and on a shared machine (load 12-88 on 10 cores) some units reached it (`*`).
A cut unit can only remove candidates, and on every cut row the truth still
ranked first. Each cell ran once.

- *T1*, the test read on the first pass, before the inlier retry. It fires on
  8 runs: fixtures (a) and (c), LaB₆ + cBN, the cpd-1g control, and four
  correct runs, cpd-1a and cpd-1b each with all systems and with only the
  host's system (the truth first, `low`). So it does not separate.
- *T2*, the same test read after the inlier retry. It fires on 2 runs: (a)
  and LaB₆ + cBN. It is silent on every run whose truth ranked first (13
  lists, 17 runs, SRM 660c included) and on both controls. It misses two wrong
  runs. (c) has its truth absent, but no floor tested finds it either. (d)
  has its truth 2nd, which the floor would fix; there two engines agree on the
  trigonal cell, so nothing says "no answer". Read off the earlier `quick`
  runs (results.jsonl), T2 is also silent on every correct run. It fires
  there on cpd-1b and cpd-1g too, both cut by the whole-run ceiling, which is
  why the retry also requires an uncut search.

| list | first pass agrees? | after inlier retry agrees? | truth | cut | load |
|---|---|---|---|---|---|
| (a) Mo + MoO₃ trace | no | **no** | — |  | 21-35 |
| (b) double perovskite | yes | yes | 1m |  | 31-28 |
| (c) Si + planted | no | yes | — |  | 26-29 |
| (d) flat Si, picker splits | yes | yes | 2l |  | 27-28 |
| magnetite | yes | yes | 1m |  | 29-35 |
| fluorite, cubic only | yes | yes | 1m |  | 36-33 |
| cpd-1a, cubic only | no | yes | 1l |  | 33-32 |
| LaB₆ + cBN | no | **no** | — |  | 31-28 |
| corundum, trigonal only | yes | yes | 1l | * | 27-21 |
| cpd-1b, trigonal only | no | yes | 1l | * | 22-25 |
| zircon | yes | yes | 1l | * | 21-26 |
| zincite | yes | yes | 1l |  | 33-30 |
| brucite | yes | yes | 1l | * | 30-28 |
| FAP | yes | yes | 1l |  | 28-31 |
| SRM 660c LaB₆ | yes | yes | 1l |  | 28-13 |
| NAC | yes | yes | 1l |  | 12-41 |
| fluorite | yes | yes | 1m | * | 41-30 |
| corundum | yes | yes | 1l | * | 28-65 |
| cpd-1a | no | yes | 1l | * | 65-45 |
| cpd-1c | yes | yes | 1l | * | 47-88 |
| cpd-1b | no | yes | 1l | * | 82-26 |
| cpd-1g (control) | no | yes | none of three | * | 26-25 |
| HL2-1 (control) | yes | yes | no truth | * | 25-88 |

"Agrees" means a lattice two engines found. Truth: rank, then grade initial;
for the mixtures, the host. The 5 % floor on (a) puts its truth first,
`medium`, in 20 s (5 % keeps 5 of the host's 6 lines). The other floors
(0.5, 1 and 2 %) put it first too.

**The retry as built, on the T1 lists (2026-11-13).** The code at
`a6bf12e82`, from a snapshot, `preset="full"`, `[dev]`, arm64 Mac, load 30-80:

IMPL_TABLE

**Licensing.** Concepts only from papers. No program code is consulted.

### Inherited

(none)

## Non-goals

- The significance screen (`weak_line`, `PEAK_FDR_Q`). The harmful lines are
  real peaks.
- The picker's false lines (WP-1968, closed).
- The acceptance rule and its inlier retry (WP-1969), except as a rival
  measured on the same lists in task 4.
- The absent-line charge (WP-1956).
- The unexplained-lines diagnostics. They keep reading the full list.
- The controls' "several descriptions of one lattice graded `medium`". Task 4
  records whether it reproduces on public controls. If it does, it is filed
  on its own.

## Tasks

- [x] Practice survey into `docs/practice.md`, a new section on which lines an
      indexing search is given. Rows: TOPAS (LSI and SVD index), GSAS-II's
      indexing, FullProf's WinPLOTR front end to DICVOL, TREOR and ITO,
      Conograph, McMaille, and the indexing literature (International Tables
      Vol. H's indexing chapter, Werner's and Shirley's guidance). Read
      Bergmann et al. (2004) Table 5 for whether the 5 % sets scored better
      than the raw ones. Mark each claim checked or inferred. The section says
      whether a relative floor is practice (tier 2) or new (tier 3).
      *Done 2026-11-12: tier 3 as a default, tier 2 as a retry (Context).*
- [x] Synthetic fixtures, built in-test from rietx's forward model (the
      reporter offered to write them). (a) A host with an injected weak
      second phase, where the floor must move the truth to rank 1. (b) A
      superlattice host whose weak lines are structural, where the floor must
      not lose the true cell. (c) WP-1969's synthetic Si with twelve lines
      planted at 1-5 % of the strongest, which a 1 % floor mostly keeps.
      Record the truth's rank on `main` under the default.
- [x] Public measurement families for the tier-3 mechanical ground: the
      indexing acceptance corpus (`tests/test_acceptance_indexing.py`'s
      certified rows), the IUCr CPD round-robin mixtures (`qarr/`), and the
      11-BM LaB₆ + cBN mixture. Say which are development data.
      *Done 2026-11-12: Context, "The families".*
- [x] Measure the candidates on the fixtures and the families, every engine,
      under `preset="quick"` with one shared ceiling: (1) nothing; (2) the
      floored list searched and scored (the issue's form); (3) the floored
      list driven and the full list scored, through the `PEAK_UNDRIVEN_FLAGS`
      seam; (4) a second arm merged per engine, `found_by` holding engine
      names only; (5) WP-1969's inlier rule as the default. For each: truth
      rank, grade, wall time, controls gaining a `medium` candidate, and
      SRM 660c LaB₆ at rank 1. Floors at 0.5, 1 and 2 %.
      *Done 2026-11-12 at 0.5, 1 and 2 % on the fixtures, at 1 % on every family; Context, "Measured".*
- [x] Decision (maintainer): the design, the floor's value and its tier, from
      the brief tasks 1-4 produce. Recorded here as `Decided YYYY-MM-DD:` and
      answered on #1291.
      *Ruled by Yue 2026-11-13: option (B), an intensity floor tried as a
      retry only when the full list's search gives no answer. The trigger
      ("no answer") is measured first, and must not fire on correct runs
      whose candidates are all `low`, such as SRM 660c. If no trigger
      separates, the fallback ((C) plus a printed suggestion) is not ruled
      and comes back to Yue.* Decided 2026-11-13: (B). The trigger
      separates (Context, "The trigger"): no lattice two engines agree on,
      read after the inlier retry. The value, 5 % of the strongest, and its
      tier 2 are Bergmann et al.'s, settled by the runner under the tier rule.
      The answer on #1291 is owed by the shift lead, from the PR.
- [x] Build what the decision picks, with its `_audit` row and any
      `INDEXING_THRESHOLDS_VERSION` move.
      *Done 2026-11-13: `engines.WEAK_LINE_RETRY_FLOOR`, `INDEX_WEAK_LINE_RETRY`,
      three tier-2 rows; the version stays 1.12 (an "Also 1.12" note).*
- [x] Reader-output diff: `str(IndexingResult)` on the acceptance rows before
      and after, in the PR body, for the maintainer.
      *Done 2026-11-13: no acceptance row triggers the retry, so their text is
      unchanged; fixture (a)'s before and after are in the PR body.*
- [x] Tests: the three fixtures as rows, a test that a `from_positions` list
      searches bit-identically, obs/calc/diff PNGs to `tests/output/`.
      *Done 2026-11-13: (a)'s xfail flipped; a position-only list sets no line
      aside, so the retry's branch is never entered.*
- [x] Skill: a row in `references/` keyed by the new name if the arm or the
      floor shows in the result, or "none" and why.
      *Done 2026-11-13: `references/abstention.md`, keyed by the code.*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_indexing_driven_set.py tests/test_indexing_consensus.py tests/test_indexing_inliers.py tests/test_indexing_engines.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

Fixture (a) ranks the truth first, fixture (b) keeps it first, and every
certified row of `tests/test_acceptance_indexing.py` keeps its rank. A
position-only list returns the same candidates as on `main`.

## References

- Bergmann, J., Le Bail, A., Shirley, R. & Zlokazov, V. (2004). *Z.
  Kristallogr.* 219, 783-790. The bethanechol round robin; set B is the
  I ≥ 5 % Imax treatment.
- de Wolff, P. M. (1968). *J. Appl. Cryst.* 1, 108-113. M₂₀ on the first
  twenty lines.
- Issue #1291 and its re-run comment (2026-11-01).
- WP-1039 (the driven twenty), WP-1969 (the inlier rule), #934 (scored, never
  driven).

## Handover log

- **2026-11-12** — tasks 1, 3 and 4, by a ghostshift runner, in PR #1543. A
  floor on line intensity is not what other indexing programs do by default.
  They search the first twenty or so lines and score with all of them, and the
  literature tries a 5 % floor only as a second attempt after the full list
  fails. On public data, a floor applied before every search does fix the
  trace-phase fixture and the picker-artefact silicon. It also discards the
  superlattice fixture's own ordering lines from 1 %, and it changes the grades
  on SRM 660c LaB₆. The two gentler forms the WP proposed keep the superlattice
  but do not fix the trace phase. So the design now waits on one decision.

  *Done:* the practice survey (`docs/practice.md`); the families and the
  measurement (Context, "The families" and "Measured"); the Inherited prune;
  a note to WP-1969 (LaB₆ + cBN ends in no cell).
  *The nightly reading the 2026-11-05 entry owed cannot be taken from the
  log*: the full job runs pytest without `-rs`, so a skip is not named, and
  neither weak-lines row is among the 25 slowest (the 25th took 141 s on
  2026-11-06 and 138 s on 2026-11-11). Each row therefore took under ~140 s
  there, which a cut search and a finished one both satisfy. Still owed; a
  `-rs` on the nightly, or a junit artifact, would answer it.
  *Gotchas:* on a shared machine most real-data runs under `quick` reach the
  120 s ceiling. Read a cut run (`*` in the table) as load, and rerun with the
  host's system declared, as the table's "only" rows do.

  **Decision for the maintainer (the task "Decision (maintainer)").** The
  question: how should rietx treat weak lines when it indexes? A fixed
  intensity floor before every search, a floor tried only when the full list
  gives no answer, or nothing? Sent because it sets a new default constant and
  changes what `str(IndexingResult)` ranks, and both are the maintainer's gate
  (Context, "Tier and the maintainer's gates").
  - *Why it matters.* The indexer drives its search with the strongest twenty
    lines and scores every candidate on all of them. A second phase present at
    a trace, or a peak the picker split in two, adds lines no cell of the host
    explains, and the true cell then ranks below wrong cells or vanishes
    (fixture (a): absent; fixture (d): second behind a trigonal cell). A
    superlattice has weak lines of its own, and those are what tell its true
    cell from a subcell (fixture (b)). Trace lines and ordering lines overlap in
    intensity: (a)'s oxide sits under 0.6 % of the host's strongest line, and
    (b)'s ordering lines run 0.1-2.3 %. A user would see either a wrong cell
    ranked first on a slightly impure sample, or a subcell ranked first on an
    ordered one. Moderate: a hand workaround exists (thin the list), and a
    wrong cell here is graded `low`.
  - *Aim.* Ranking the host's cell first for someone indexing a real sample
    with a minor impurity, without losing ordered structures.
  - *Options.* (A) A fixed floor before every search (the issue's form).
    Measured: fixes (a) and (d) at 0.5, 1 and 2 %. Keeps (b) at 0.5 % but
    loses it from 1 %. On SRM 660c it removes one `kalpha2_residual` line at
    1 % and grades the truth and its known half-volume tetragonal rival both
    `high`; at 2 % the rival ranks first. Tier 3, since no program does it by
    default except EXPO's N-TREOR09, whose value is unstated. (B) The same
    floor as a retry, run only when the full list's search yields no answer.
    This is Bergmann et al.'s practice and DICVOL91's old advice, so tier 2.
    (b) and SRM 660c would not trigger it, since both rank their truth first
    unfloored. Not measured: what "no answer" means is the open part. Absent
    truth and an all-`low` list both occur on correct runs here (SRM 660c is
    all `low`), so the trigger needs its own measurement. (C) Nothing. The
    hand workaround stays, and the WP closes with this record. Dropped as
    measured failures: driving with the floored lines through the #934 seam,
    and a second search per engine (each leaves (a)'s truth 2nd-9th; the
    second costs about twice the time and lost one answer to the ceiling).
    The inlier rule as default helped no list and dropped SRM 660c to 4th.
  - *Practice.* `docs/practice.md` § Which lines an indexing search is
    given: count-and-position line choice everywhere; a floor as a
    second chance in the bethanechol round robin (5 runs better, 1 worse,
    10 unchanged of 16 at 5 % of Imax).
  - *Recommendation.* Lean (B). The crux is that no fixed value separates a
    trace phase from a superlattice's own weak lines, because their
    intensities overlap. (A) must then lose one of the two at any value, and
    it also moves the absolute anchor's grades. (B) acts only on lists that
    already failed, which is where practice uses a floor. Its cost is a
    trigger rule to measure before the value is set. A measurement showing
    that every usable trigger also fires on correct runs, such as SRM 660c's
    all-`low` list, would flip this to (C).

  *Settled by the runner, each reversible:* (d) searched with no system
  declared, as #1382 reproduced it (declared cubic it ranks first already);
  per-engine runs only on (a) and (d) (cost; elsewhere `found_by` on the
  truth says which engines found it); 0.5 and 2 % floors on the fixtures and
  six real lists only; the cut lists rerun with the host's system declared
  rather than a larger ceiling (the device task 2's rows use); the harness
  left as scratch, with each candidate's construction written in Context.
  *Next:* the maintainer's answer to the decision above. Then, for (B),
  measure a trigger rule on these lists before choosing the value; for (C),
  close the WP.

- **2026-11-05** (post-merge record) — PR #1341 merged at `4eecc6632`. It
  carries task 2's own entry, the second of the two below. Task 2 is done and
  the WP stays open.
  *Owed:* the slow rows of `RANK_ON_MAIN` have run on macOS only. The first
  Linux nightly after this merge is their first reading on another platform,
  so read `test_truth_rank_on_main[a-0]` there (fixture (a) as picked). That
  search took 17-30 s on the Mac, and a CI leg runs 3-4× slower, against the
  120 s ceiling. If the ceiling cuts it, the row and
  `test_a_trace_second_phase_leaves_the_truth_first` both skip, and (a)'s range
  needs narrowing again. If the row passes, its rank stands on both platforms.
  *Next:* that reading, then task 1 (free) and task 3.

- **2026-11-02** — created, from the 2026-11-02 issue triage (issue #1291).
  Checked against the tree at `992b7048f`: every symbol the issue names
  exists, and `PEAK_UNDRIVEN_FLAGS` is an existing seam the issue did not
  measure. No open WP owns which lines drive a search. WP-1969 owns the
  acceptance rule on the same failure, and its open follow-up (the inlier
  rule as default) is measured here as a rival rather than folded, because
  it waits on WP-1956 and this does not. WP-1039, which set the driven
  twenty, is closed. The reporter's numbers are quoted from the issue and
  not reproduced; their data is private. Filed in PR #1315. *Next:* tasks 1
  and 2, which need no decision.

- **2026-11-02** — task 2, by a contributor's PR whose claim covers task 2
  only. Builders in `tests/_synthetic_weak_lines.py`, rows in
  `tests/test_indexing_weak_lines.py`. (a) is molybdenum with an α-MoO₃
  trace (Sitepu, O'Connor & Li 2005) whose strongest line is 0.6 % of the
  host's, over 12.1-55° (12.1-60° took 51 s alone and 122 s in a full-suite
  run, cut by the ceiling, so its rows skipped; 55° takes 17-30 s; 12.1-45°
  left the host four lines, one short of a cubic search's five): 38 lines
  picked, 6 the host's and 29 at the oxide's positions. (b)
  is an idealised ordered double perovskite, F m -3 m at 2·a_p, with 10 %
  antisite disorder, so its twelve ordering lines run 0.1-2.3 % of the
  strongest. (c) is #933's Si with twelve planted lines. Today's picker finds
  29 usable lines where #933 had 53. The truth's rank on `main` at the
  default with `systems=("cubic",)` declared, as picked / 0.5 / 1 / 2 %:
  - (a): absent / 1 / 1 / 1;
  - (b): 1 / 1 / 2 / 3, the cubic subcell first from 1 %;
  - (c): absent at all four.

  Si with nothing planted ranks first. Undeclared, the default binds its
  120 s ceiling on every as-picked list (`INDEX_BUDGET_EXHAUSTED`, lower
  systems cut), so its rank there is a load reading (WP-1449); that is why
  the rows declare the system. Read undeclared on one laptop, (a) over the
  original 12.1-60° range: absent / 1 / 1 / 1, (b) 1 / 1 / 1 / 12, (c) absent at all four. (a) reproduces the
  failure and the 1 % floor fixes it; with the system declared, the same
  floor loses (b)'s supercell. (a)'s acceptance row is
  `xfail(strict=True)`. *Next:* task 1 (free), task 3, then task 4 on these
  rows.
