# WP-1806 — first public case: acridine form IX

Milestone: rigid-bodies · Status: 🔄 2026-10-25 — the pdCIF reader merged (PR #1006); open: the data file, the authors' profile, the acceptance test
Depends on: 1805
Priority: P3 2026-10-23 — the first real-data proof of the body; 1810 closed without it (PR #955), and 1989 waits on it soft for its public case and pdCIF reader

## Goal

A rigid body over acridine form IX's 14 non-H atoms refines against the deposited
pattern and lands every body atom within the published coordinate esds. This is chunk R4
of issue #561, sized M.

## Context

- Data: COD 2242872 (CC0; NSLS X16C, 0.6998 Å; Stephens et al. 2019). Origin and
  orientation free, no torsions.
- The deposited intensities are background-subtracted, so the test holds the background
  at zero and says so.
- **The bar stays the published esds** (re-affirmed 2026-10-06). An outside spike,
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

- **Decided 2026-10-16 (maintainer, from the issue triage, #561): the bar is
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

## Non-goals

- Hydrogens (WP-1810), torsions (WP-1808).

## Tasks

- [x] pdCIF reader: accept the net-intensity and weight columns, with a diagnostic where it repairs
- [ ] The data file and a provenance row in `tests/data/README.md`
- [ ] The authors' profile; the template-superposition floor, measured and recorded
- [ ] The acceptance test + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: none expected; say why at handover

## Acceptance

- Every body atom lies within the published coordinate esds, and the cell matches the
  published cell.
- An intra-body distance reports `None` (through `VARIANCE_CANCELLATION_FLOOR`), and an
  inter-body one reports a full esd.
- The provenance row exists.

## References

- Stephens et al. (2019), *Acta Cryst.* E75, 489.
- Issue #561; PR #596.

## Handover log

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
