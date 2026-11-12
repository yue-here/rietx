# WP-1806 — first public case: acridine form IX

Milestone: rigid-bodies · Status: ✅ 2026-11-12 — the body agrees with a free-atom control in rietx (PR #1545)
Depends on: 1805

## Goal

A rigid body over acridine form IX's 14 non-H atoms refines against the deposited
pattern and agrees with a free-atom fit of the same data in rietx. This is chunk R4
of issue #561, sized M.

## Context

- Data: COD 2242872 (CC0; NSLS X16C, 0.6998 Å; Stephens et al. 2019). Origin and
  orientation free, no torsions.
- The deposited `_pd_proc_intensity_net` column still carries the background (never
  within 14σ of zero), so the test refines a 10-term Chebyshev plus one broad hump
  (corrected 2026-11-12; `tests/data/README.md` has the measurement).
- **The bar (Yue, 2026-11-05, #561): a free-atom control in rietx.** The same model
  refines with the heavy atoms free, under the same data, profile and background as
  the body, and the body must agree with it. The deposited coordinates and cell are
  another model's answer under another protocol (Rule 2), so they go to a record
  table that asserts nothing.
- The bar was the published esds until 2026-11-05. An outside spike,
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

## Non-goals

- Hydrogens (WP-1810), torsions (WP-1808).

## Tasks

- [x] pdCIF reader: accept the net-intensity and weight columns, with a diagnostic where it repairs
- [x] The data file and a provenance row in `tests/data/README.md`
- [x] The authors' profile; the template-superposition floor, measured and recorded
- [x] The acceptance test + obs/calc/diff PNGs to `tests/output/`
- [x] Part 1: a 10° / 0.3 Å perturbed start returns to the same minimum
- [x] Part 1: an intra-body distance reports `None`, and an inter-body one reports a full esd
- [x] Part 1: a simulated known answer is recovered, and a regular-hexagon template fails
- [x] Part 1: the per-atom table goes to `tests/output/` as a record
- [x] Part 2: the free-atom control under the same profile and background, compared with the body atom by atom
- [x] Part 2: the cell joins the per-atom record table (|Δ|, published esd, rietx esd, ratio), asserting nothing
- [x] Skill: none expected; say why at handover (none: the work is a test; the handover entry says why)

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

- **2026-11-12** — Part 2 is done and the WP closes. The rigid body on the real
  acridine pattern now has the bar Yue chose: the same model refined with its 14
  heavy atoms free lands where the body does. The free fit needed no restraints. Its
  worst disagreement with the body is 2.3 esds, and a wrong template (regular
  hexagons) breaks the same bar at 8.7. The shift along c that the 27 October
  comparison blamed on the body is not the body's. The free atoms sit 0.0027 Å below
  the deposit along c, the body 0.0019 Å below the free atoms, and each gap is about
  one esd. The published cell now sits in the deposit record table and asserts
  nothing. Filed as PR #1545 by a ghostshift runner.

  *Done.* `tests/test_acceptance_acridine_ix.py` gains
  `test_the_body_agrees_with_the_free_atom_control` (slow, group `acridine-ix`) and
  the `free_control` fixture. The control is the body's starting atoms with the body
  removed. Its 14 heavy atoms free their `dof.*`, and each H ties its `dof.k` to its
  carrier's (`RIDES_ON`, Hi on Ci), so it takes the carrier's shift. Biso ties,
  profile, background and the four-stage plan are the body's own (`_fit` branches on
  whether the phase has a body). No restraint is used, and the test asserts so. The
  bar (`CONTROL_BOUND` = 4) covers each of the 42 heavy-atom coordinates and the
  molecule's mean position along x, y and z. Each is divided by the esd of the
  body-minus-control difference, √(σ²_control − σ²_body), with the body's σ put on
  the control's GoF × Bérar-Lelann scale (Hausman 1978, nested fits of one pattern).
  Four of those over 45 statistics fail a correct body with probability ≤ 0.3 %, the
  known-answer row's reasoning. The control's table goes to
  `tests/output/acridine_ix_control_table.md`. The cell rows (a, b, c, β: |Δ|,
  published esd, rietx esd, ratio) join `acridine_ix_deposit_table.md`. Body and
  control also draw a 6.5-12.5° zoom PNG. `tests/validation_matrix.py` and
  `docs/VALIDATION.md` carry the row (`own_result`, `ceiling`).

  *Measured* (this runner, macOS arm64, Python 3.12.10, worktree `[dev]` venv).
  Rwp 0.058424 body, 0.057799 control; GoF 2.065 and 2.048; Bérar-Lelann 1.869 and
  1.848. Body against control: worst 2.29 (C8 along b), median 0.62 over 42
  components, none over 4. Mean position: x 0.54, y 1.27, z 0.97 esds. Along c the
  body sits 0.0019 Å below the control (esd of the gap 0.0020), and the control
  0.0027(31) Å below the deposit. The control from a second start (the body's
  answer) lands 0.00023 Å from the first, about 0.02 of the smallest difference esd,
  so the bar does not sense where the solver stopped. Positive arm, run once by
  probe and not kept in the suite: the regular-hexagon body on the real pattern
  scores 8.68 (C6 along b), 7 of 42 components over 4, Rwp 0.0648. The control's
  unrestrained bonds scatter ±0.033 Å about the body's. The body's own H leave
  their carrier's shift by at most 0.0015 Å, which bounds how far the two models
  fail to nest. The two control fixtures cost about 105 s for the test pair alone on
  a machine shared with other runners. Mike's owed note from part 1 stands: over
  eight noise seeds of the simulated arm, the heavy atoms' mean z error ran −1.02 to
  +0.19 esd, rms 0.44, so esds on this pattern may run conservative.

  *Gates*, on this branch with origin/main merged in (`a6e3ead25`), same venv. Fast
  suite: 14 564 passed, 424 skipped, 32 xfailed in 12:28, through the shared
  machine's suite queue. The added test is `slow`, so it moves no fast count, and
  `tests.added_test_times` has nothing to rank. The acridine file with its slow rows:
  6 passed in 9:00, the four part-1 slow rows included. Lint as CI runs it is clean: ruff, the tutorials' format,
  `audit_delta`, and Vale at 0 errors. `test_docs_consistency.py` with
  `test_validation_matrix.py`: 801 passed. `tests.reader_output` exits 0. The full
  suite did not run: the change is a test and its records, which tests/CLAUDE.md
  exempts.

  *The c-shift reading, settled by Claude under the 2026-11-05 ruling.* The ruling
  said: the body is cleared if the free atoms show its shift along c, and the WP
  stops to investigate if they land on the deposited z and the body does not. It
  named no number and asked for one read off the control's own esds. Read so, the
  stop branch does not fire, because the body agrees with the control along c to
  1.0 esd. The control's 0.0027 Å shift has the body's sign and 58 % of its size,
  and is 0.86 esd from the deposit. So the control cannot tell the deposit from the
  body along c. What it does say is that a free-atom fit of these data lands where
  the body lands. The alternative reading is that "show the body's shift" needs the
  control significantly off the deposit, which these data cannot give at all. Under
  that reading the WP would stay open with no measurement able to close it. Yue may
  reverse this.

  *Review* (`/code-review high`, ten findings). Fixed five: the mean position goes
  through `physical_covariance` with its guards, an unguarded `sqrt` now asserts with
  the axis, `tie_equal` names its source, the deposit table parses the CIF once, and
  the table's Å column says it is a fractional difference times the cell edge. The
  esd-scale finding was right and is fixed by the common scale above. The first
  probe of the positive arm crashed on it, a hexagon body's esd exceeding the
  control's on its own scale. Declined with measurements: the nesting finding (the
  H non-nesting is ≤ 0.0015 Å); the margin finding (bar 4 against 2.29 is a
  statistical margin, and the measured start spread is 0.02 esd; a cross-platform
  spread is not measured); two small duplications (`_published_cell_esds` beside
  `_published`, `_draw_zoom` beside `_draw` in another module).

  *Skill:* none. The work is a test and its record. An agent checking its own rigid
  body has `check_rigid_bodies`, whose released arm is WP-1989's subject.

  *Forward:* WP-1989 `### Inherited` gains the measured result that a shift tie
  keeps riding H riding on this pattern, and its soft dependency on this WP is
  discharged.

  *Next:* none here. The rigid-bodies milestone's next real-data work is WP-1989's
  released arm, which can reuse this control's construction.

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
