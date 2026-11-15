# WP-1956 — a cell pays for the lines it predicts and the pattern lacks

Milestone: unscheduled · Status: ✅ 2026-11-08 — the line screen charges absences at the grade (PRs #941, #1177, #1302); task 5 ruled kept (#916, 2026-11-07); tutorial 03's grades handed to WP-2041, three follow-ups to issue #1468
Track: What fires, and what stays silent
Depends on: 1449 soft (the index 2–4 refutation it widens); 1511 soft (one Le Bail protocol per cell)

## Goal

An indexing candidate whose predicted lines the pattern lacks is charged for
them at the grade, beyond the index 2–4 sublattices WP-1449 asks about, and the
absence test reads inputs a candidate cannot buy: a background shared by every
candidate or owned by the pattern, and the peak list's measured width. A correct
cell with a glide (Si 3/18, corundum, magnetite) stays unrefuted, and an
unresolved split stays unpunished.

## Context

**What is measured** (issue #916, synthetic Si, reproduced on c3d0367 to the
digit). `indexing.workflow.absent_reflections` (`workflow.py:180`) integrates
each candidate's own co-refined Le Bail background, and a wrong cell's fit buys
its absences away by sinking that background:

| cell | Rwp | predicted_but_absent | background vs the true 7700 counts |
|---|---|---|---|
| truth, cF a₀ | 0.013 | 5/18 | −7 |
| cI √2·a₀ | 0.828 | 0/59 | −3782 |
| cF 1.006·a₀ | 0.904 | 0/18 | −2823 |
| cP a₀ (triage's arm) | | 0/50 | −3233 |
| cP 2a₀ (triage's arm) | | 0/290 | −8422 |

So the detector fires only on the truth. Under `preset="quick"` (121 s, 17
lines) a distorted hR cell (a = 3.8450, c = 9.3904) ranks first with no
refuting caveat, and the true cF 5.4306 ranks second, the only candidate
carrying `predicted_but_absent`. cI 7.6800 is refuted only through an index-4
check against a tI parent (`consensus.supercell_checks`, `consensus.py:174`,
volume index 2 to `ambiguity.MAX_AMBIGUITY_INDEX` = 4).

**Why nothing confident is returned today, and why that is not a fix.** Every
candidate is graded `low` through `fom.fom_panel_disagrees` (`fom.py:775`),
computed once per run (`consensus.py:460`) and attached to every candidate
(`:610-611`), so `best_or_none()` is `None`. The reporter's follow-up measured
that flag quiet on arms where wrong cells reached `medium` or `high` (the cI cell
was graded `medium` on `f22e9a7c` under a steeper background). Their conclusion,
taken here: the flag is not to be relaxed, scoped per candidate or removed before
this repair, and any redesign of it is measured with this WP, on the same arms.

**The design was recorded and left unowned.** WP-1043 (✅) measured the same
pathology on magnetite (the rival's background driven negative, mean −11.4
counts, so net > 3σ at every channel and the detector cannot fire). It recorded
the fix as candidate-independent inputs (a floored or pattern-owned background,
the peak list's measured width), and the bound a repaired detector meets there:
14 of 163, not most of 163. It also recorded that the repair re-measures every
`predicted_but_absent` count in the tree and "should be scheduled deliberately,
not folded into a passing WP" (1043's tasks and its last handover).

**The question the issue asks** (from #916): should a cell pay at the grade,
and with which inputs: one background shared by all candidates, the measured
width, line-set containment rather than lattice containment for
`supercell_chance`?

**The reporter's measured proposal** (#916, 2026-10-13 06:56Z; a spike outside
the tree, on the issue's own seeds, not re-run here). Three findings and a
fourth from the public lab patterns in `tests/data/qarr`:
1. *The inputs were the whole of the sign problem.* Fed the picker's background
   envelope and the peak list's widths and shapes (no Le Bail),
   `absent_reflections` reads 24/40 on cI √2·a₀, 21/36 on cP a₀, 107/140 on
   cP 2a₀ and 9/35 on the hR cell, against 3/15 on the truth (its d-glide);
   the candidates' own fits read 0, 0, 0, 0 and 3. A resolved split reads only
   7/77, its partners sitting in real lines' tails.
2. *The reversed questions are asked in the search window* (3 × σ_eff with the
   allowance folded in, ±0.15° on a 0.023° FWHM). At one FWHM (floored by 3σ)
   after the candidate's common shift is estimated from its forward matches, the
   hR cell's seen fraction falls 0.77 → 0.34 (truth 0.73) and the resolved
   split's 0.99 → 0.56; the unresolved split stays at 1.00 like the truth. An
   allowance bounds a common offset and should widen the forward match only.
3. *WP-1449's chance test reaches every one of these cells* once the parent
   relation is "every observed line the parent indexes, the child indexes"
   rather than a volume ratio of 2-4, keeping its uncancellable-extras guard and
   null: all refuted (0 of 12, 8, 85, 2, 7, 14, 12 extras seen), the unresolved
   split undecided, and the truth as a child of anything never refuted. In the
   search window the hR cell and the resolved split read *supported*.
4. *No absolute absent count can refute*: corundum's own cell reads 5 over the
   full range on real lab data. Inside de Wolff's window (Q of the 20th line)
   the truths read 0 (corundum) and 2 (magnetite) and the wrong cells 7 or
   more, so the count can cap. "Refuted" should mean seen no more often than
   chance (k ≤ n·p₀), not "not significant at α".

The proposal, for the maintainer: (a) a candidate-independent line screen (peak
list + envelope + the existing overlap and quiet rules) supplies the reversed
member at the resolution and the `predicted_but_absent` count; (b)
`supercell_checks` asks indexed-set containment with a three-band verdict; (c)
`predicted_but_absent` caps rather than refutes, and the extinction screen
separates the glide from the oversized cell. The Le Bail validation keeps the
forward question with a shared frozen profile.

**Rules that bind it** (`src/rietx/indexing/CLAUDE.md`): never a confident
singleton; a new indexing rule lands in that file; run
`tests/test_acceptance_indexing.py` before closing anything that touches an
engine or the ranking. Indexing is provisional by declaration
(`PROVISIONAL_MODULES`).

## Non-goals

- The blind search and enumeration ceilings (WP-1924), dedup across a reduction
  boundary (WP-1932), peak picking (WP-1909), the extinction screen (WP-1910).
- WP-1511's per-cell Le Bail evidence, which fences the blind search itself.
- A refinement's own Le Bail background left too low at its seed (WP-1542): the
  opposite sign, in another call.

## Tasks

- [x] **Decision (maintainer):** the reporter's (a)-(c) above, whole or in
      part, recorded as `Decided YYYY-MM-DD:` here and answered on #916.
      *Decided 2026-10-14: (a)-(c) whole, as PR #941 builds them; answered
      in PR #941's review.*
- [x] Rebuild the issue's synthetic Si arms as a test fixture: the truth, cI
      √2·a₀, cF +0.6 %, cP a₀, cP 2a₀, the steeper-background arm, and a
      tetragonal descent of the true lattice; exact and picked lines.
- [x] Candidate-independent inputs for `absent_reflections`: the shared or
      pattern-owned background and the measured width (WP-1043's design).
- [x] Charge absences at the grade beyond index 2–4, with the glide and
      unresolved-split guards; re-measure every `predicted_but_absent` count in
      the tree and record the moves.
- [x] #1263: the containment refuter's null counted in the seen test's own
      windows, the assumed shift bound flooring only the power check (`split`).
      *Built 2026-11-01 (PR #1302). Decided 2026-11-01 (maintainer): `split`
      lands on top of #1251's `g`.*
- [x] Revisit `fom_panel_disagrees` only on the same arms, after the repair.
      *Measured 2026-11-02 on `a5c99e0fe` under `preset="full"` (PR #1353,
      handover entry below). Decided 2026-11-07 (Yue): revisited after the
      repair; kept. The lattice-aware form waits for a lattice comparison with
      ten times the margin (handover entry of 2026-11-07).*
- [x] Tests, and `tests/test_acceptance_indexing.py` green.
- [x] Skill: the indexing reference row for any changed caveat or grade rule.

## Acceptance

On the #916 arms every wrong cell reads a non-zero `predicted_but_absent` and
ranks below the truth, with the truth's grade not lowered by its 5/18 glide
absences; Si, corundum and magnetite keep their correct cells.

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #916 (body, and the follow-up on `fom_panel_disagrees`).
- WP-1043 (the magnetite measurement and the recorded design), WP-1449.

## Handover log

- **2026-11-08** — closed (ghostshift runner, PR #1469; no code changed). The repair this WP
  asked for is on `main`: a wrong indexing cell can no longer buy a count of zero missing lines
  by refitting its background, because the count is now read at the peak list's widths against
  the picker's background, and the correct cell's glide absences are not charged. Yue ruled
  the last task on 2026-11-07 (the `fom_panel_disagrees` flag stays as it is). What was left
  was bookkeeping for two other places, and this close does it without new measurements:
  tutorial 03's grades go to WP-2041 as what is on record, and three unowned follow-ups go to
  issue #1468.

  *Done.* WP-2041's `### Inherited` gains the entry its 2026-10-24 note asked for. It quotes
  the full range from the committed notebook, built by 1.11.0's rebuild `3791ef632` on a tree
  holding PRs #941, #1177 and #1302 (#1353 changed no code): CELL at `high`, 24 of 87 lines
  absent. It quotes the 45° cut from PR #941's merge (`0070d696`): NO CELL, the true cell
  `medium`. It says that neither was re-measured after #1177 and #1302, and that WP-2041's
  own third task re-runs both on `main`. That re-run is a measurement, so it stays WP-2041's
  rather than being taken here. WP-2041's Priority line now names this close as its blocker
  gone. The `### Inherited` section is deleted with the Priority line: the tutorial 03 and
  aragonite entries are consumed by WP-2041's note, the #941 release bullets went into
  `docs/releases/1.11.0.md`, the 10-27 Pawley count note is already in WP-2041's
  `### Inherited`, task 5's two triage entries are consumed by the task and by issue #1267
  (`quick` under load, still open), and the empty peak list (WP-2011's), the
  n·p₀ < 1 chance hit (PR #941's round 5) and the lattice-aware form's revisit are issue
  #1468.

  *Not run:* the code review (a prose-only branch), the fast suite (no code or test
  changed), the generality judge (no heuristic added). Issue #916 is left for the
  maintainer: this PR carries no closing keyword for it.

  *Next:* none here. WP-2041's third task, then issue #1468 when the maintainer schedules it.

- **2026-11-07** (rulings, PR #1455) — task 5 ruled, and every task is now ticked. Decided
  2026-11-07 (Yue): `fom_panel_disagrees` stays as it is (issue #916). The flag keeps capping the
  truth's grade on 15 of the 19 #916 arms. In exchange, it holds down the wrong cells that rise above
  `low` on 7 of the 19 arms without it.
  The lattice-aware form would lift three truths. Its safe tolerance band is too narrow to trust
  beyond the arms it was measured on, so it is recorded here for a later revisit.

  *Recorded for the revisit.* The lattice-aware form ("TL") fires only when the members' co-winners
  share no lattice, comparing lattices by line set. Its measured window for that line-set tolerance
  is 7e-4 to 2e-3, relative in Q. Below 7e-4, #916 arm b's tI and cF descriptions of one lattice read
  as two. From 2.2e-3, LaB₆'s tetragonal descents promote wrong cells to `high`. So the margin is
  under 3×, and both edges come from one synthetic Si family and one lab LaB₆ pattern. Inside the
  band TL promotes no wrong cell on 27 runs and lifts #916 arm b and brucite to `medium`, and
  zincite to `high` (entry of 2026-11-02). Revisit TL when a lattice comparison has a margin of 10×
  or more, for example one built on reduced cells. The build is then the one the 2026-11-02 entry's
  *Next* describes, with that table re-run as its acceptance.

  *Left before close.* The `### Inherited` entry of 2026-10-24 from WP-2041 asks this WP's closer
  to re-measure tutorial 03's full range and its 45° cut on `main`, and to write their grades and
  caveats into WP-2041's `### Inherited`. That has not been done. The other five `### Inherited`
  entries were not pruned in this rulings pass.
  *Next:* run tutorial 03's two cuts on current `main`, write the grades into WP-2041's
  `### Inherited`, prune this file's `### Inherited`, then close this WP.

- **2026-11-05** (post-merge record) — PR #1353 merged at `7ac1f54c1`. Its own
  entry is below and lacked the sha. Status stays 🔄, and task 5 still waits on
  the maintainer's ruling on #916.

- **2026-11-02** — task 5 measured: `fom_panel_disagrees` on the #916 arms after
  PR #1302, with no whole-run ceiling (ghostshift runner, PR #1353; no code
  changed). The reporter's 10-30 reading holds once the clock is taken out. Removing the flag
  still lets wrong cells rise above `low` on 7 of the 19 arms, and on LaB₆ as
  picked three reach `high`. The lattice-aware form ("TL": fire only when the
  members' co-winners share no lattice) promotes no wrong cell on any of the 27
  runs. It lifts the same three truths as before: #916 arm b and brucite to
  `medium`, zincite to `high`. New: its line-set tolerance now has a measured window. Arm b needs at
  least 7e-4 (relative, in Q) to count its tI and cF descriptions as one lattice, and LaB₆'s descents promote
  wrong cells to `high` from 2.2e-3, so the safe band is 7e-4 to 2e-3, under a
  factor of 3. Also new: without the ceiling, both exact-position negative arms
  fire where `quick` left them quiet, so the flag's cost on correct cells is
  larger than the 10-30 table showed. The rule is still the maintainer's.

  *Measured* (pearl, `[rietx-py312]` venv, Linux x86-64 under WSL2, Python 3.12,
  one pinned core per run, 8 runs at a time; tree `a5c99e0fe` = main plus this
  branch's claim commit; main's later indexing commits are docstring and
  CLAUDE.md text only). The harness is the reporter's
  (`planning/magnetic/checks/spikes/fom-panel-disagrees-20261012/`, outside the
  tree, not committed) with `preset="quick"` → `"full"` and nothing else
  changed. Each synthetic arm ran twice, at the default 30 s per engine × system
  and at 300 s. Each acceptance row ran on its fixture as written (`full`, 300 s
  per unit). No run reported `INDEX_BUDGET_EXHAUSTED`. No acceptance row's unit
  reached its budget. Synthetic units that did were all orthorhombic, monoclinic
  or triclinic. Every `not_validated` sits below `CONSENSUS_CHECK_TOP`'s three,
  so none is a cut validation. TL at 1e-3 unless stated.

  | run | lines | flag | truth: shipped / no flag / TL | wrong cells above `low` without the flag (30 s; 300 s) |
  |---|---|---|---|---|
  | #916 arm b | 11 | fires | low / medium / **medium** | — ; — |
  | Si flat 12–60° | 16 | fires | low / medium / low | hR 5.431 × 4.208, oC → medium; hR → medium |
  | cP a = 4.0, picked | 48 | fires | #2 low / medium / low | tP a/√2 (ranked #1), tI → medium; + oF |
  | cP, exact positions | 39 | **fires** | low / medium / low | — ; oC → medium |
  | Si 12–100°, picked | 30 | fires | low / medium / low | oC → medium, both |
  | Si 12–100°, exact positions | 25 | **fires** | low / medium / low | — ; oI → medium |
  | tP c/a 1.01, picked | 62 | quiet, both | medium | — |
  | Si + four cP 2a₀ lines | 34 | fires | low / medium / low | — ; hR → medium |
  | brucite | 28 | fires | low / medium / **medium** | — |
  | corundum SRM 676a | 46 | fires | low / medium / low | — |
  | corundum, `cos_theta` | 46 | fires | low / medium / low | — |
  | FAP | 135 | fires | low / high / low | — |
  | LaB₆ SRM 660c as picked | 30 | fires | low / high / low | tP ×2, cI a√2 → **high**; tP → medium |
  | LaB₆ calibrated | 24 | quiet | high | (cI a√2 already `high`, #941's Q3) |
  | fluorite, magnetite | 17, 17 | quiet | medium | — |
  | NAC 11-BM | 262 | fires | low / medium / low | — |
  | zincite | 27 | fires | low / high / **high** | — |
  | zircon | 55 | fires | low / medium / low | — |

  Against the reporter's `quick` table on `e016f187d`: the tP c/a 1.01 arm
  is quiet at both unit budgets, which #1267's account predicts. Both
  exact-position arms now fire. Small subcells won M₂₀, F_N, `m_rev` and
  `m_sym`: oC 2.716 × 2.716 × 3.136 Å on Si, mP 2.36 × 2.83 × 2.89 Å on cP. They
  are found in the orthorhombic and monoclinic units, which `quick`'s ceiling
  had cut. The `cos_theta` corundum and FAP rows no longer promote a trigonal P
  cell without the flag. So the flag lowers 15 of the 19 truths (all but
  tP c/a 1.01, LaB₆ calibrated, fluorite and magnetite).

  *TL's tolerance*, re-read from the saved results at 3e-4 to 5e-3 (finer
  near both edges). Arm b's truth is lifted from 7e-4; at 6e-4 the tI 3.8411 ×
  5.4293 Å and cF 5.4312 Å descriptions read as two lattices and TL fires. LaB₆
  as picked promotes tP ×2 and cI a√2 to `high` from 2.2e-3 (quiet at 2.0e-3).
  FAP's truth reaches `high` from 2.2e-3 too, inside the band that fails on LaB₆,
  so it is no gain. Brucite and zincite are lifted at every tolerance tried.
  Nothing else moves between 3e-4 and 2e-3. The lower edge is how far two
  refined descriptions of one lattice sit apart (arm b's tI c = 5.4293 Å
  against its cF a = 5.4312 Å is 7e-4 in Q). The upper edge is where LaB₆'s
  tetragonal descents start to read as its cubic lattice. Both edges come from
  these arms (one synthetic Si family, one lab LaB₆ pattern), so a tolerance
  chosen inside the band is untested beyond them.

  *Not done.* No code: TL is a rule change and waits on the ruling. The
  per-unit budget still cuts low-symmetry units of the synthetic arms at 300 s
  (`trial_error.monoclinic` on five arms, the tP arm's triclinic units too).
  The flag reads identically at 30 s and 300 s on every arm, so the reading
  does not hang on it. `python -m tests.reader_output`: exit 0, unchanged.

  *Next.* The maintainer rules on #916. If lattice-aware, build TL in
  `fom.fom_panel_disagrees`, with co-winners by exact tie and lattices by line
  set at a tolerance inside 7e-4 to 2e-3, and re-run this table as its acceptance,
  arm b, brucite and zincite rising and nothing else. If kept, tick task 5 as
  "revisited after the repair; kept". Then the WP's last open item is WP-2041's
  tutorial 03 count.

- **2026-11-01** — #1263, built as the reporter's `split` rule (ghostshift runner,
  PR #1302). Decided 2026-11-01 (maintainer): `split` lands on top of #1251's
  `g` (PR #1302). The containment refuter compared how many of a cell's extra lines sit
  on an observed line with a chance count taken in wider windows, floored at the
  assumed shift bound (0.15° 2θ when nothing is measured). The seen count itself
  is taken at the resolution after the cell's own common shift. So "expected by
  chance" overstated chance, by 1.1–1.5× on the real-data acceptance rows where
  the floor binds and 4–15× on narrow synthetic lists, and the refuter called
  extras "no more than chance" that were seen well above it. Now the chance
  rate is the seen test's own, and the floor bounds only whether the test had
  the power to refute at all, which is what #951's row needs. One verdict
  moved across the 244 pairs the indexing tests ask, on wrong cells. Which rule
  lands, `split` on top of #1251's `g` or `g` alone, is the maintainer's call at
  merge: the WP recorded it so (it narrows the approved tier-3
  `INDEX_SUPERCELL_REFUTED` action, and turns on the reading of #951 that the
  shift bound limits the power check and leaves the null alone).

  *Done.* `PatternScreen.p0` is the unfloored union of the reversed windows;
  `PatternScreen.p0_power` (new, `None` when no floor is declared) is the floored
  one. `SupercellEvidence.p0_power` (new) carries it, and `p_floor` reads it;
  `n_seen ≤ n·p0`, both p-values and `SupercellCheck.p0` read the unfloored
  rate. The `supercell_chance` (index 2–4) route is untouched: its seen test and
  its `chance_rate` already share the matching window. Docstrings that claimed
  the windows matched (`SupercellEvidence.p0`, `containment_evidence`,
  `SupercellCheck`) now say which windows; the `indexing/CLAUDE.md` clause, the
  thresholds-1.12 note, the `_audit.py` row's evidence (tier unchanged) and the
  1.11 release note say so. The skill row got the full stop #1251's round 2
  asked for, re-synced to both copies. Option "pass the floor into
  `seen_at_resolution`" was not built: the rulebook forbids asking a reversed
  question in the search window (±0.15° on a 0.023° FWHM read a resolved split
  as supported).

  *Measured* (`[dev]` venv, macOS arm64, Python 3.12.10). The dense triclinic
  fixture (#1230's aP2 kind, 289 lines): p₀ 0.228, and a 2·10⁴-point Monte Carlo
  of `seen_at_resolution` reads 0.228; the floored rate is 0.667. The truth's
  extras over the six-times-larger rival are 128 of 373 seen, against 85 by
  chance (p 2.5e-7) and 249 at the floored rate. None sits on a line the rival
  leaves unexplained, so the pair is undecided under `split` alone, under `g`
  alone and under both. #951's list: p₀ 0.0115 (p₀² 1.3e-4) against 0.172 floored
  (0.030 > α 0.01), so its 0-of-2 pair stays undecided. A pytest plugin logged
  every containment pair's verdict under main's floored null and under `split`
  (`~/.cache/ghostshift/rietx/issue-1263/gs_split_log.py`, not committed) over
  `test_acceptance_indexing.py` plus the screen, consensus, reduce and
  width-allowance files: 227 passed in 18:22 at `-n 4` on a loaded machine. Of
  244 distinct pairs, 243 keep their verdict; one goes refuted → undecided, a
  wrong cubic P 23.75 Å child of a wrong hexagonal 18.53 × 10.40 Å parent on
  `test_an_unidentified_pattern_stays_unidentified` (23 of 100 seen against 18.6
  by chance, 27.7 floored), still refuted by four other parents. No pair gains
  `supported`. Without `g`, `split` alone moves five pairs to undecided. The
  floor binds on 75 of the acceptance rows' 153 pairs. `python -m
  tests.reader_output`: exit 0, unchanged (a Rietveld fit; it does not reach
  indexing). What a reader sees that does change: `INDEX_SUPERCELL_REFUTED`'s
  "N expected by chance" and `SupercellCheck.p0` drop by the ratios above
  wherever the floor binds.

  *Added after review.* `SupercellCheck.p0_power` (new, additive, schema note
  under 0.60; `None` without a floor and in a record from before #1263),
  written by `consensus.supercell_checks`, so a record reproduces its own
  verdict: #951's pair stores p₀ 0.0115 with 0 of 2 seen, which alone reads as
  refuted, beside the 0.172 the power check read. The texts giving the old
  reason for `undecided` are corrected (`SupercellCheck`, `verdict`, `p_floor`,
  the reference page's band and table, the theory page's power paragraph, which
  also gains the k ≤ n·p₀ refutation and #1230's condition it lacked). The
  reference page's text twin sits within a few characters of its 50 000 cap
  after this, so the next addition there splits the page.

  */code-review high --fix.* Seven findings. Applied three, all text: the
  `p_floor` docstring, the dense fixture's line count (289 usable), #951's
  test docstring's inequality. Built one after the judge agreed: the
  `p0_power` record field above. Declined three, each a behaviour change for
  its own measurement: (1) p₀ is not conditioned on the extras being far from
  every parent line; on the dense fixture the conditional rate is 0.206
  against p₀ 0.228, so n·p₀ still overstates chance by about 1.1× there (the
  floored rate overstated it 3×), next action below; (2) `p0_floor_deg`'s
  default 0 leaves `supercell_checks(screen=None)` without a power floor, as
  before this branch (both rates were unfloored there, so nothing regressed),
  and the keyword's name now describes a rate it no longer sets; (3) p₀ is
  counted about the raw observed positions while the seen test reads each
  candidate's shift-corrected ones, a gap the Monte Carlo bounds at 0.015 on
  one constant-shift pattern.

  *Generality* (judge's sections, unedited):

  INDEX_SUPERCELL_REFUTED (code row, tier 3, ambiguity 2, approved
  2026-10-21). Verdict: **holds.** "The new null is arithmetic that a test
  verifies. The cost of refuting less was measured at one flipped verdict, on
  a wrong cell that four other parents still refute. I found no case for
  keeping the old null." Q5 note: the `approved` date was not refreshed,
  although this entry says the rule is the maintainer's call at merge; a batch
  reader of the table will not see that request. Q6 note: the 244 pairs are
  not broken down by family, and all of them are development data (C3's
  thresholds were measured on them), which this entry did not say.

  The split (a heuristic the table cannot see). Verdict: **weak**; Q7
  **fails**: "No field carries `p0_power` … for #951's pair, a reader computes
  0.0115² = 1.3e-4 < 0.01 with 0 of 2 seen, expects `refuted`, and reads
  `undecided`. Four texts still give the old reason." Q3 against the power
  half: "#951's lines were missing because a weak-line intensity filter removed
  them, not because of a 2θ shift. The shift bound protects it only by the
  arithmetic of n = 2: 0.172² = 0.030 > 0.01. The same filtered superstructure
  with three extras gives 0.172³ = 0.0051 < 0.01 and would be refuted. … This
  proxy predates the branch, but the floor now carries the guard's whole
  weight." Q5: the null half is tier 1 (arithmetic, verified by the Monte Carlo
  test); the power half is tier 3 at best, its two constants
  (`fom.MATCH_SIGMA`, `engines.DEFAULT_UNKNOWN_SHIFT_DEG`) at `unaudited`.
  Q6: no count of how many verdicts the power check alone keeps undecided.
  "Evidence that would change the verdict: a `SupercellCheck` field carrying
  the power rate …, with those four texts corrected … And a count of how many
  acceptance pairs the power check alone keeps undecided."

  *Author's answer under the fail:* the field and the four texts are done
  (above). Not done: the count of pairs the power check alone keeps undecided.
  The proxy the judge names (#951's guard rests on n = 2, not on the shift)
  predates this branch and goes to the maintainer with the rule.

  *Gate* on the final tree (`f4f6f3c14` plus this entry; `main` had not moved
  from `b0e0e4b71`): the fast selection 13 188 passed, 310 skipped, 32 xfailed,
  0 failed in 8:13 alone on the machine (`[dev]`, macOS arm64, Python 3.12.10).
  One test added (`test_the_null_is_the_chance_rate_of_the_seen_test_itself`,
  0.02 s); the dense row was rewritten, not added. No pre-branch baseline was
  run locally, so the +1 is CI's to confirm. The full suite did not run; the
  slow rows this change can move are `test_acceptance_indexing.py`'s, measured
  above. ruff clean.

  *Not done.* The three #1230 truths under `preset="full"` were not re-run here;
  the reporter's runs read #1 for `split + g`, and `g` alone already holds them
  at #1 on main.

  *Next.* With `split` decided, the next refinement of the null is the declined review finding (1): count p₀
  only over the range farther than the resolution from every parent line, per
  pair, and re-run the 244-pair log (`gs_split_log.py`'s method) on it. Then task 5
  (`fom_panel_disagrees`), under `preset="full"` or a ceiling no arm binds, per
  #1267's entry above.

- **2026-10-13** — created, from the 2026-10-13 issue triage (issue #916).
  Checked against the tree at c3d0367: every symbol the issue names exists
  where it says, nothing touching `absent_reflections`, `supercell_checks` or
  the grade moved since the issue's `dd20f0fd7`, and the three rows, the
  hR-first ranking and the all-`low`-through-the-panel-flag reproduce. No open
  WP owns it: WP-1043 recorded the repair as unowned and asked for it to be
  scheduled on its own, WP-1449 (✅) shipped the index 2–4 refutation only,
  WP-1511 fences the blind search, and WP-1542 is the opposite sign in a
  refinement. The reporter's measured proposal landed on #916 the same
  morning and is in § Context. *Next:* the maintainer's decision on its
  (a)-(c), then task 2.
- **2026-10-14** — from the PR review (PR #941): @yue-here decided (a)-(c)
  whole, including `predicted_but_absent` moving from the refuting set to a
  cap and the matching rewrite of `src/rietx/indexing/CLAUDE.md`'s
  whole-profile validation clause. Round 1 is at `f5617cb8`. Its
  before-merge items: `INDEX_ABSTAINED` still calls `predicted_but_absent`
  refuting, a module fixture with no `xdist_group`, the phantom-supercell bar
  dropped from 95 % to 50 % without a count, `contains` admitting a mutual
  containment at equal volume, `to_cell_candidate` scoring on the old seen
  fraction, and a direct `validate_by_lebail` screening on the peak list's
  range and per-line σ. *Next:* #941's round 2.
- **2026-10-25** — PR #941 (C3, by @mustachefeeling) merged at round 6, landing
  in `fe4cbcc3` through #939's head, which carried #941's and #993's synced
  heads. The indexer now asks its reversed questions of inputs a candidate
  cannot buy: a line screen over the peak list and the picker's background
  envelope, at the measured resolution (`RESOLUTION_FWHM`, 1 FWHM). A wrong
  cell can no longer read zero absences by refitting its own background.
  `predicted_but_absent` caps rather than refutes, and fires on the
  uncancellable absences inside de Wolff's first twenty lines (true cells 0–2,
  wrong cells 7–79). The generalised containment check refutes the
  oversized cell. Indexing thresholds go to 1.12, the 1.11 cycle's one bump,
  which #993's and #939's notes share. The review's sync commit `ed62646d`
  parked the release bullets in `docs/releases/1.11.0.md`. Gate: the five
  PRs of the 2026-10-25 batch stacked on `deff4c30` (tree `8273948f`), whole
  suite 12 243 passed, 206 skipped, 42 xfailed, 0 failed in 35 min (macOS
  arm64, `[dev,jax]`, Python 3.12.10). #941's own CI head failed only
  `guides/moment.py` on Linux 3.14, twice; #939's head, which contains it,
  passed (WP-2036's guide-precision cause). Task 5 stays open: nothing
  revisited `fom_panel_disagrees` on the #916 arms. *Next:* task 5, and
  WP-2041 re-measures tutorial 03's absence count on this tree.

- **2026-10-31** (`/pr-review`) — PR #1177 (by @mustachefeeling) merged as `8260c78b` after two rounds: the four things #941 left open. `RESOLUTION_FWHM` stays 1.0: swept 0.5-1.0 on 15 real runs, one rank moves (PbSO₄ X-ray at 0.7, the truth second behind a cell within 0.5 % of its metric), and nothing above 1.0 ran on real data. The windowed cap gains a density form and an excess over the run's cleanest candidate, reported and never gated (`LeBailValidation.*_in_window`). `INDEX_PREDICTED_BUT_ABSENT` reads the validation's counts and fires at `info` when every uncancellable absence lies above de Wolff's window. The screen pairs absences with merged lines by index, and `screen_for` is memoised per run. Re-measured under the Pawley validation (#1191): identical cell for cell. Gated in a stack of seven on `main` `d87c8cc9` (tree `21beeca9`, Mac arm64, Python 3.12, `[dev,jax]`): full suite 13 427 passed, 230 skipped, 48 xfailed, 0 failed; GUI, ruff and the `-W` manual build clean. #1257 stayed out on a hung CI job, and `main` after the six merges equals the checked six-PR tree `86997f50`. Gap, not blocking: the `RESOLUTION_FWHM` row's source list counts 12 sources and omits SRM 676a, which the sweep ran.
