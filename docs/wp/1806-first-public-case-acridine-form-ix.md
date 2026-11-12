# WP-1806 — first public case: acridine form IX

Milestone: rigid-bodies · Status: 🔄 2026-11-12 — claimed by ghostshift MacBook-Air-c4aacd (Part 2, the free-atom control)
Depends on: 1805
Priority: P3 2026-10-23 — the first real-data proof of the body; 1810 closed without it (PR #955), and 1989 waits on it soft for its public case and pdCIF reader

## Goal

A rigid body over acridine form IX's 14 non-H atoms refines against the deposited
pattern and agrees with a free-atom fit of the same data in rietx. This is chunk R4
of issue #561, sized M.

## Context

- Data: COD 2242872 (CC0; NSLS X16C, 0.6998 Å; Stephens et al. 2019). Origin and
  orientation free, no torsions.
- The deposited intensities are background-subtracted, so the test holds the background
  at zero and says so.
- The bar was the published esds until 2026-11-05 (`### Inherited`). An outside spike,
  reported on #561 on 2026-10-06, found two obstacles. This WP clears both first:
  1. The pdCIF reader refuses this file's `_pd_proc_intensity_net` with
     `_pd_proc_ls_weight` columns. The fix lands in `io/` under that subtree's rules
     (`src/rietx/io/CLAUDE.md`).
  2. With a plain profile the body landed 0.09–0.10 Å RMS from the deposited atoms. A
     start 10° and 0.3 Å off reached the same minimum to 0.04 Å. So the authors'
     profile is needed: anisotropic Stephens strain and a high-order background, read
     from the paper.
- The deposited model may not be a rigid body. Measure the best rigid superposition of
  the template onto the deposited atoms before setting the test's tolerance, and record
  it. If that floor exceeds the published esds, bring the number back to the
  maintainer before loosening anything.

### Inherited

- **Decided 2026-11-05 (Yue, #561): the bar is a free-atom control in rietx.**
  This is the brief's option C, and it replaces the 2026-10-16 bar below. The same
  model refines with the heavy atoms free, under the same data, profile and
  background as the body. Restraints may hold the free atoms stable, and the test
  says which. The deposited coordinates cannot judge the body, because they are
  another model's answer under another protocol (Rule 2). The per-atom table
  against them stays as a record and asserts nothing. If the free atoms show the
  body's shift along c, the body is cleared. If they land on the deposited z values
  and the body does not, the body owns the shift and the WP stops to investigate.
  The ruling names no number for "the same shift". Part 2 reads it off the
  control's own esds and brings it to Yue if the reading is not clear.

- **Superseded 2026-11-05. Decided 2026-10-16 (maintainer, from the issue triage, #561): the bar is
  option (c), and the body may be built from the deposited coordinates.** Each
  body atom passes within the larger of its published esd and rietx's own esd
  for that atom. The published esds come from a free-atom refinement with a
  different profile and background, so they are one reference among two.
  Option (b), removing the mean translation, was declined because it hides the
  body's position. `body_from_atoms` on the deposited heavy atoms is allowed,
  since an idealised template already sits 0.019 Å off. The Context line
  holding the background at zero is wrong per the entry below and is corrected
  when this WP starts.

- **2026-10-16, from the issue triage (#561): the reporter's R4 groundwork
  contradicts two lines of this WP and asks the maintainer to choose the
  bar.** Three comments, 2026-10-15 23:20Z to 2026-10-16 07:06Z, none recorded
  here; figures are the reporter's, not re-run (the groundwork is on private
  runs of COD 2242872). (1) The deposited `_pd_proc_intensity_net` is not
  background-subtracted (minimum 249 counts, never within 14σ of zero;
  deposited calc ≥ 301), so Context's "hold the background at zero" is wrong:
  the authors' calc includes a 10-term Chebyshev plus a broad hump, and the
  2026-10-06 spike's 0.09 Å came mostly from the zero background (Rwp 0.46).
  The pdCIF reader half is only the missing `_pd_proc_intensity_net` tag plus
  a diagnostic for a far-from-zero "net" column, open as PR #1006. (2)
  Template floor against the published esds: the deposited heavy atoms as the
  body give 0; a planar copy gives 0.019 Å RMS (C5 at 6 esd); regular hexagons
  0.064 Å (30 esd). So the bar is reachable only with `body_from_atoms` on the
  deposited coordinates. (3) Acceptance fit (Chebyshev 10 + hump, TCHZ,
  Stephens 2/m, FCJ, March-Dollase (100)): Rwp 0.0584 against the published
  0.0503; misses on C5 (3.45 esd), C11 (1.29), C12 (1.32), all along c, from
  one rigid translation of the body (mean Δz −0.0043 Å against a fit esd of
  0.0024 Å on the origin). No background or profile variant brings C5 inside 2
  esd; FCJ off is unusable (Rwp 0.142). The test is held until the maintainer
  chooses: (1) keep "every atom within the published esds" and drop the test,
  (2) compare after removing the body's mean translation, (3) a bound in
  rietx's own esds. Also asked, unanswered: OK to build the body from the
  deposited coordinates with the bar unchanged. Profile needs FCJ asymmetry
  and a 1000 ppm Stephens seed. Tree checked at 2c94d848: `body_from_atoms`
  exists (`crystallography/bodies.py:56`); #1005, #1006, #995 open.

- 2026-10-31, from the issue triage (issue #561): the acceptance fit misses
  the maintainer's option-(3) bar on three atoms (reporter, 2026-10-27, main
  at feae4c75). The model is the 16 October one: 14 heavy atoms, 9 riding H,
  Chebyshev 10 plus one hump, TCHZ, FCJ, Stephens 2/m at 1000 ppm,
  March-Dollase (100). Rwp is 0.05839. Read per component, C5, C11 and C12
  miss along c at 2.22, 1.32 and 1.32 of the bar. Every x and y component is
  at most 0.30 of its bar, and the cell passes. The miss is one translation of
  the body along c. The origin's z is 1.9 of rietx's own esd from the
  deposited value. The background moves it. Chebyshev 12 takes C5 to 1.35 but
  ends at a higher Rwp (0.0598). So it found another minimum along a
  Chebyshev-hump degeneracy (ρ up to −1.000), not a better background. On
  2026-10-30 the reporter proposed splitting the acceptance. Part 1 would
  assert now what the body owns: a 10° / 0.3 Å perturbed start returns to the
  same minimum (0.0001 Å); an intra-body distance reports `None`; a simulated
  known answer is recovered while a regular-hexagon template fails. Part 2
  would add the option-(3) assertion once the maintainer rules on the 27
  October numbers. This WP does not say whether the bar is read per component
  or as a 3-D distance. C5 fails both readings. Checked against the tree at
  d87c8cc91: the acceptance task is unticked and no acridine acceptance test
  exists. The reporter's figures were not re-run.

- **2026-11-05, settled by Claude under Yue's instruction to action clear
  calls: the acceptance may land in two parts.** Options B and C of the
  decision brief on this WP's bar both take the split, so it holds whichever
  Yue picks. Part 1 lands now. It holds the perturbed-start check, the
  intra-body and inter-body distance esds, and the simulated known-answer test
  where a regular-hexagon template must fail. The per-atom table goes to
  `tests/output/` as a record and asserts nothing. Part 2 stays Yue's and
  undecided: what the miss along c means for the 16 October bar, and whether
  the assertion stays. The brief's option C, not ruled, replaces the assertion
  with a free-atom control fit under the same profile. Acceptance is unchanged
  because the bar is not ruled. Part 1's items are unticked Tasks below. Filed
  in PR #1414.

## Non-goals

- Hydrogens (WP-1810), torsions (WP-1808).

## Tasks

- [x] pdCIF reader: accept the net-intensity and weight columns, with a diagnostic where it repairs
- [x] The data file and a provenance row in `tests/data/README.md`
- [x] The authors' profile; the template-superposition floor, measured and recorded
- [ ] The acceptance test + obs/calc/diff PNGs to `tests/output/`
- [x] Part 1: a 10° / 0.3 Å perturbed start returns to the same minimum
- [x] Part 1: an intra-body distance reports `None`, and an inter-body one reports a full esd
- [x] Part 1: a simulated known answer is recovered, and a regular-hexagon template fails
- [x] Part 1: the per-atom table goes to `tests/output/` as a record
- [ ] Part 2: the free-atom control under the same profile and background, compared with the body atom by atom
- [ ] Part 2: the cell joins the per-atom record table (|Δ|, published esd, rietx esd, ratio), asserting nothing
- [ ] Skill: none expected; say why at handover

## Acceptance

- The body agrees with the free-atom control of `### Inherited` (2026-11-05). The cell
  is compared with the published cell in the record table and asserts nothing (2026-11-07).
- An intra-body distance reports `None` (through `VARIANCE_CANCELLATION_FLOOR`), and an
  inter-body one reports a full esd.
- The provenance row exists.

## References

- Stephens et al. (2019), *Acta Cryst.* E75, 489.
- Issue #561; PR #596.

## Handover log

- **2026-11-07** — Yue ruled on Acceptance's "the cell matches the published cell": it
  goes, and the cell joins the per-atom record table, asserting nothing. Grounds, from the
  maintainer's question sequence run by the shift lead: the published cell is Stephens et
  al.'s refined answer under their own profile, so it is another model's answer under
  another protocol (Rule 2), as the coordinates were on 2026-11-05. rietx gates a cross-code
  cell only where the test mirrors that code's protocol (the FAP suite's ±300 ppm against
  GSAS's `.EXP`), and this test reads the authors' profile from the paper. A tolerance
  between two separately converged fits also senses where each solver stopped unless it
  carries a measured spread (`tests/CLAUDE.md` § Budgets in tests), and none is measured.
  Part 1's test already asserts nothing about the cell; it uses the published cell only to
  build its synthetic pattern. What would reopen a gate: the authors' own input file, so the
  test can mirror their protocol. Part 2 gains the record-row task. PR #1454.

- **2026-11-06** — Part 1 is on main. Mike's PR #1416 merged as `fd6232320`
  (PR head `170dee168`, main `263227986`), after two review rounds at heads
  `4935f767e` and `86ad3c53a`. The rigid body now has its own checks on the
  real acridine pattern. A start 10° and 0.3 Å off returns to the same answer.
  A distance inside the body carries no esd, and one between molecules carries
  a full one. A simulated pattern's known answer is recovered, and a
  regular-hexagon template fails it. Nothing yet says whether the body is
  right about the deposit. That is Part 2, the free-atom control.
  Handover filed in PR #1443 by a ghostshift runner.

  *Done.* `tests/test_acceptance_acridine_ix.py` holds the four Part 1 checks
  under the authors' profile read from the paper. FCJ H/L is held at 0.01,
  because S/L and H/L are one direction on this pattern. The per-atom table
  against the deposit goes to `tests/output/acridine_ix_deposit_table.md` as a
  record and asserts nothing. `tests/validation_matrix.py` and
  `docs/VALIDATION.md` carry the suite's rows. The data file and its
  provenance row were already on main (`af5fb4571`), so that task is ticked
  with this merge. The template floor is 0.064 Å RMS for the regular-hexagon
  template, worst atom 0.096 Å (round-1 review), and zero for the body built
  from the deposited atoms.

  *Measured* (the review runner's, macOS arm64, Python 3.12.10, `[dev,jax]`).
  Start-independence: gap 1.6e-6 Å against a 1e-3 Å bar. The esd rule: 212
  intra-body rows `None`; 112 inter-body rows full, 100 of them more than 1 %
  off the diagonal-only esd. The known answer's 0.64 is the best of eight
  seeds. Over seeds 1806 and 1-7 the worst |Δ|/esd ran 0.64 to 2.27, median
  1.5, so the margin to the bound of 4 is about 1.8×. The full `-m slow` gate
  on `170dee168` gave 949 passed, 14 skipped, 19 xfailed, 1 failed, in 1710 s.
  The one failure is
  `tests/test_pair_diagnostic_class.py::test_the_two_site_winner_finds_each_site_its_own_moment`.
  It found m1 = 0.6995 μ_B against an expected 3.5, a swapped minimum. It
  fails identically, run alone, on bare main `263227986`. So it is main's and
  not this PR's, and the lead merged on that ground. The fast suite on the
  round-2 merged tree gave 14 165 passed, 157 skipped, 36 xfailed.

  *Owed by Mike* (his note on the PR). The known-answer row's `measured` should
  quote the seed range above. Part 2 should note that the esds on this pattern
  may run conservative: over those seeds the 14 heavy atoms' mean z error ran
  −1.02 to +0.19 of an esd, rms 0.44.

  *Gotchas.* The test writes no obs/calc/diff PNG, so that task stays open for
  Part 2. Acceptance's "the cell matches the published cell" is unruled. It may
  be a comparison against another model's answer under Rule 2, as the
  coordinates were.

  *Next:* Part 2, the free-atom control under the same profile and
  background, compared with the body atom by atom, with its PNGs. Bring the
  cell clause to Yue with it.

- **2026-10-06** — created by WP-1803's re-cut. The maintainer kept the
  published-esd bar, so the reader fix and the authors' profile are tasks here and the
  size grows from S to M.
- **2026-10-25** — PR #1006 (by @mustachefeeling) merged at round 4 as
  `f9a983d7`. `read_pattern` reads a pdCIF whose only intensity column is
  `_pd_proc_intensity_net`, as the acridine deposit (COD 2242872) has, and
  says so (`PATTERN_INTENSITY_NET`, `metadata["intensity_item"]`). A net
  column that never comes within 5σ of zero fires `PATTERN_NET_HAS_BACKGROUND`
  (warning, tier 3, ruled 2026-10-24), 14.1σ on this deposit; the message
  names both readings, a background left in or no empty baseline in range,
  and the suggestion prescribes neither. A `_pd_proc_ls_weight` of zero now
  excludes its point only (`PATTERN_ZERO_WEIGHT_EXCLUDED`), where 1.10.0
  dropped the whole weight column. The review's sync commit `4072cedb` moved
  the notes to `docs/releases/1.11.0.md`. Gate: the stacked full suite of
  WP-1956's 2026-10-25 entry. Merged by the maintainer over a red `fast py3.14
  2/2`, whose one failure is `examples/guides/moment.py` (WP-2036): that
  guide's code path is identical to #939's head, which passed it. Skill: the
  three codes have rows in `references/diagnostics-reading.md`. *Next:* the
  data file and its provenance row, then the authors' profile.
- **2026-11-05** — PR #1414 records that the acceptance may land in two parts
  (`### Inherited`, same date) and adds Part 1's items to Tasks. No test lands
  with it, and the Acceptance section is unchanged. *Next:* as above, then
  Part 1. Part 2 waits on Yue's ruling on the bar.
- **2026-11-05** — Yue ruled on the bar: option C, a free-atom control in rietx
  (`### Inherited`). Goal, Context, Acceptance and Tasks now say so, and Part 2 is that
  control. Filed in PR #1423. *Next:* Part 1 in PR #1416, then the control.
