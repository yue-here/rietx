# WP-2062 — Pawley is the structure-free default

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 2011 (the indexer's validation, built provisionally as Pawley); 1910 soft (the extinction screen's fits)
Priority: P2 2026-10-27 — a scoping WP, the decision with a named user that other WPs wait on (1542, 1910's fit mode)

## Goal

Every place where rietx chooses a structure-free fit for a user runs the
method the maintainer picks below, site by site, and every name that would
then describe the wrong fit is renamed or records the mode. The evidence for
each choice, including what TOPAS, GSAS-II and FullProf do, is in this file
and in `docs/practice.md`.

## Context

**What "default" means here.** No argument default picks Le Bail. `mode`
defaults to `"rietveld"` in `Refinement.fit` (`refine.py:4838`),
`rietx.refine()`, `Project.create`, `ProjectDoc`, `SequentialRefinement` and
the GUI's create form, and `_audit.py:3315-3320` records that none of the
seven surveyed programs defaults to Le Bail either. rietx picks Le Bail for
the user in four other ways, inventoried 2026-10-27 (an agent's read, its
load-bearing lines checked here):

| | Site | Who sees it | Pawley-ready? |
|---|---|---|---|
| A1 | the indexer's candidate validation, `validate_by_lebail` (`indexing/workflow.py`) | every `index_pattern` user, the GUI's candidate row | **switched** in WP-2011, provisionally |
| A2 | the extinction screen's fits: `_fit_class` (`indexing/extinction.py:773`), the cell-free prefit (`:825`) and the reference fit (`:983`) | `determine_extinction_symbol`, the GUI's Peaks panel | runs, but unmeasured. Its Hamilton count adds `n_lines + n_free_parameters` (`:1137-1141`), and a Pawley `n_free_parameters` already includes the intensity block, so the count would double (read, not run) |
| B1 | the GUI's Adopt sets `doc.mode = "lebail"` (`gui/session.py:2460`) | a GUI user adopting a candidate | yes: the GUI already runs Pawley projects |
| B2 | the wizard's typed cell flips the mode to `lebail` (`gui/src/lib/wizard.ts:157`, pinned by `wizard.test.ts`) | a GUI user without a CIF | yes; a frontend change needs a rebuilt dist |
| C | prose that tells a person or an agent to run Le Bail first: `docs/skill/rietx/SKILL.md` (:77-137), `docs/docs/start/first-fit.md` ("Le Bail before Rietveld", :170-181), `reference/refinement.md`, tutorials 01, 03 and 06, `examples/nac_11bm.py`, `README.md` | every reader and every agent | yes |
| D | `mccusker_default` runs `profile_only` under `lebail` and `pawley_default` under `pawley` (`strategy/staged.py:719`, `_MODE_SUBSTITUTES`); the two have identical stages | API, GUI, agent | yes; `profile_only` also serves Rietveld, so it cannot simply be renamed |

**Pawley already rests on Le Bail.** A Pawley stage with no intensities
carried in seeds its block from one Le Bail partition (`refine.py:4404-4411`,
`Stage.lebail_cycles` partitions). So no option here deletes Le Bail.
`help.lebail_cycles` said Pawley ignores the setting; WP-2011 corrected it.

**Why Le Bail is in question.** rietx's Le Bail re-extracts the intensities
only between least-squares runs (`lebail_cycles` = 3 partitions before each
solve), so one pass refines widths against intensities partitioned at the
starting profile. Measured:

- WP-2011, nine real patterns' true cells, one pass of the indexer's plan:
  Le Bail left `w` on its floor on corundum and zircon and 21 and 44 observed
  peaks unmatched; Pawley hit no floor and left 12 and 11. On a wrong cell
  the Le Bail background sank (−7.3 counts under magnetite's primitive
  rival; Pawley +13.8). Five or ten Le Bail passes did not close the gap and
  cost more than one Pawley fit.
- WP-2011's non-goals, ordinary `profile_only` against `pawley_default` over
  three passes: corundum 0.234 → 0.179 with `y` still on its floor, against
  Pawley 0.152 → 0.139; FAP 0.130 → 0.085 against 0.083 → 0.078; zircon
  0.184 → 0.172 against 0.172 → 0.149.
- Notebook 03 (aragonite): the indexer's one Pawley pass reaches Rwp 0.044,
  the notebook's own two Le Bail passes 0.053.
- Issue #740, folded into WP-1542: with cell and profile at the truth and
  only the background free, Le Bail plateaus at Rwp 1.62 % from 100 to 400
  cycles, Pawley reaches 1.06 % and the Rietveld fit of the true structure
  1.09 %. The cause found there is the background, not the partition.

**What Pawley costs and lacks** (each read at its line 2026-10-27 unless
marked):

- Cost: one intensity per reflection in θ. About equal to Le Bail below ~450
  reflections; on 11-BM NAC's 837, 3.1× on an idle machine (WP-2011,
  10-18). Above 128 columns LM steps by projected CG (WP-1953), and
  `at_bound` is then not exact (`strategy/staged.py:1858-1870`). The esd
  pass builds a dense n×n (`refine.py:6809`, `:8055`).
- `compare_rivals` raises in Pawley (`report/layer2.py:1202`).
- The exchangeability scan returns nothing in Pawley
  (`optimize/identifiability.py:191`).
- No `FROZEN_COMPILE_STALE` recompile: a Pawley result is the frozen
  compile's (`refine.py:5536`).
- Overlap groups are built per phase, so coincident reflections of two
  phases are neither restrained nor flagged (`model/forward.py:4396-4415`;
  inferred from the code, not tested).
- Its three constants (`PAWLEY_OVERLAP_FWHM_FRAC`, `PAWLEY_OVERLAP_LAMBDA`,
  `PAWLEY_OFF_DATA_SCALE_FLOOR`) are tier 3 on the ground "opt-in Pawley
  mode", measured on LaB6 and FAP only (`_audit.py:1868-1890`). A default
  that reaches users unasked removes that ground, so the generality rule
  reopens them. WP-2011's switch already does this for `index_pattern`, and
  that WP holds the decision.

**Added 2026-10-28, from WP-2011's `quick` measurement** (that file's
§ Re-measured 2026-10-28, probes 8-11):

- Cost on a pseudo-symmetric cell. Unbounded on 11-BM NAC, Pawley took 11 s
  at 1223-1241 reflections and 377 s at 2224, where Le Bail took 1.4-2.4 s.
  The 2224 are NAC's orthorhombic subcell redescribed as monoclinic with β
  90.003°, a routine shortlist member. Its last stage needed 89 LM
  iterations, at 2.4 s of projected CG and 0.8 s of dense JᵀJ each. The
  dense normal matrix and CG's dependence on conditioning are solver
  properties: a banded or sparse intensity block is a third route beside
  decision 0's two.
- Under `quick`, the default preset, Pawley validated none of NAC's
  candidates where Le Bail validated one to three. A larger validation
  reserve is no fix (probe 10). So decision 0's cost argument is measured
  now, and on the indexer's own path.
- A unit dependence. Synthetic LaB6's true cell validates at Rwp 0.164 on
  counts and 0.262 with pattern and σ divided by the maximum count. Le Bail
  is invariant (0.2339, 0.2338). It is not the off-data floor or the LM
  curvature probe. Not found. On nine real true cells no reading moved by
  more than 2e-4. A Pawley default needs it found first.
- The three Pawley constants were re-grounded for the indexer's path on
  2026-10-28 (ruling 3: no unmatched count or status moved under any swept
  value). A site this WP moves reopens them only for that site's readings.
- Names: the maintainer ruled 2026-10-28 that the rename is decided here
  (decision 3), so the names break once.

What Pawley has that Le Bail lacks: per-reflection esds, cell esds
marginalised over the intensities (`docs/solver-survey.md:249-251` calls
Le Bail's "known to be optimistic"), intensities bounded at zero, the
overlap flag `PAWLEY_OVERLAP_UNRESOLVED`, and the off-data ridge
(`PAWLEY_OFF_DATA_RIDGED`, WP-1459).

**Names.** If the method changes, these would describe a fit that is no
longer Le Bail. Public: `rietx.LeBailValidation`, `CellCandidate.lebail`,
`CandidateEvidence.lebail_status` and `.lebail_rwp`,
`rietx.indexing.validate_by_lebail`, the `validate_candidates` label "Le Bail
validation" (`help.py:4828`, `gui/src/lib/controls.ts:104`), and tutorial 03's
file name, which is a published URL. WP-2011 kept them and added
`LeBailValidation.mode`. These stay true whatever is chosen, since Le Bail
still exists: the `Mode` literal, `lebail_passes`, `lebail_cycles`,
`LEBAIL_ALTERNATION_STOPPED`, `lebail_scaffold` (both modes use it), and
`FitReport.lebail_gap`, which is a Rietveld-only diagnostic that runs no
least squares (`report/layer0.py:75-114`). The field's term for both methods
is whole powder pattern decomposition (Le Bail 2005).

**Practice** (surveyed 2026-10-27; the table and its citations are in
`docs/practice.md` § Structure-free fitting: Le Bail or Pawley). Three
findings bear on the choice:

- **rietx's Le Bail is not the one the other programs run.** GSAS-II
  (`GSASIIstrMath.py:4808`, checked), FullProf (ran), TOPAS, RIETAN-FP and
  MAUD all re-extract the intensities inside the refinement, once per
  least-squares cycle or iteration. rietx re-extracts only between whole
  solves, so the stall WP-2011 measured may be rietx's schedule rather than
  the method. WP-2011's "recalled, not checked" note is now checked.
- **TOPAS defaults to Pawley** ("The default is Pawley refinement, the
  keyword lebail triggers a Le Bail refinement", Technical Reference v5 §8,
  p.84; read by the survey agent, not by the lead). GSAS-II offers both and
  defaults to neither. MAUD advises Le Bail first, then Pawley. FullProf and
  RIETAN-FP offer Le Bail only; BGMN's mode called "LeBail" is Pawley-type.
- **No program makes a structure-free fit the default mode.** That matches
  rietx: the question here is which structure-free fit rietx runs where it
  runs one for the user, never whether `mode` should default to one.

Le Bail (2005, §IV.C, pp.318-319): two round robins could not show either
method better, and the paper gives no timings.

**The tier of each rule this WP adds.** A site moved to Pawley is a default
or an automatic action, so each move is tiered by the generality rule
(`docs/milestones/generality.md` § The rule). Its kind of ambiguity is 1
(every competent refiner would act) only if the practice survey shows the
programs agree; otherwise it is 2, and the evidence is the measurements
above, which come from lab and synchrotron single-phase patterns
(LaB6, NAC, FAP, the IUCr round-robin pure phases, aragonite).

### Inherited

- **From WP-2011, 2026-10-28: Pawley's cost on large patterns, re-measured
  with option (c) built** (WP-2011 § Option (c) probed, commit e39b8c19d on
  its branch). A Pawley stage above the BVLS cut now forms JᵀJ sparse over
  its frozen windows and preconditions the projected CG with an incomplete
  LU. A pseudo-symmetric candidate's fit fell 376 s → 34 s with no reading
  moved, so decision 0's cost argument should be re-measured before it is
  ruled on. Well-conditioned fits gained little (NAC's true cell 6.0 → 4.8
  s, FAP 1.1 → 1.3 s). What still costs on the true cell (probe 15): the
  dense J build (1.1 s of 5.8), the esds every stage computes (0.77 s), and
  recompiling the reflections of a held cell at each stage (0.89 s), each a
  separate change. Merging exact coincidences (one intensity per distinct
  d-spacing) cut NAC's true cell from 849 to 299 columns at an unchanged
  Rwp. It changes the model only where the data cannot separate the
  reflections, so it is a candidate for every site here.
- **From WP-2011, 2026-10-28 (3rd session): the validation default is
  decided, and the dense path is fast too.** Under the maintainer's
  delegation the indexer's validation fit is Pawley, `quick` keeps 15 % of
  its ceiling for validation (was 8 %), and the fits run cheapest first. On
  11-BM NAC that validates the true cell, which no fit reached at 8 %. Past
  `PAWLEY_SPARSE_DENSITY` a Pawley step now uses the exact, shifted Cholesky
  factor and a projected search (Lin & Moré 1999): lab pseudo-symmetric
  candidates went from a whole-budget solve (1204 products at 601 columns)
  to 157, readings unchanged. Two costs stay open for every Pawley site here:
  the sparse ILU path still spends its budget on a singular face (FAP as
  monoclinic C, 944 columns, 1882 of 1888 products, 12 s; a shifted ILU
  fixed it offline but slowed FAP.XRA's real fit), and the panel scoring
  that spends `quick`'s reserve is WP-2063's.

## Decisions (maintainer)

0. **Replace, or repair.** Two routes reach a converged structure-free fit.
   (a) Pawley wherever rietx runs one for the user (this WP's sites). (b)
   Re-extract the Le Bail intensities inside the solve, once per
   least-squares iteration, as every surveyed program does. (b) keeps
   Le Bail's per-fit cost, which matters on large patterns (NAC's 1668
   reflections: 107 s against 8.5 s under load, WP-2011 probe 6), but it
   changes the residual between iterations. The bounded LM's trust region
   judges each step by comparing the predicted with the actual reduction of
   one fixed objective, and the frozen-per-stage invariant (root CLAUDE.md)
   exists to keep that objective fixed. So (b) is a design WP with its own
   measurements, not a setting. (a) is the cheaper route and is what
   WP-2011 built for the indexer.
1. **Which sites move.** A1 (done provisionally), A2, B1-B2, C, D, each
   on its own; doing nothing at a site keeps Le Bail there.
2. **A2's timing.** In this WP after WP-1910 lands, or inside WP-1910
   (PR #1170 open, by @mustachefeeling), with the Hamilton count fixed first.
3. **Names.** Keep the `lebail` family and record the mode (WP-2011's
   provisional choice), or rename to the field's term with old files still
   opening (`schemas/migrate.py`'s read-point mechanism).
4. **Le Bail's own repair.** WP-1542 (a Le Bail background left at its seed,
   issue #740) continues as it is, or drops a rung once no default path runs
   Le Bail.

## Tasks

- [x] Fill § Practice from the survey, and add its section to
      `docs/practice.md`.
- [ ] The maintainer's five decisions (0-4), each recorded as `Decided YYYY-MM-DD:`.
- [ ] Per site chosen: switch, record, re-measure the numbers that site's
      tests pin, and stage the change in the release record (ROADMAP rule 6).
- [ ] Reopen the three tier-3 Pawley constants with the generality review
      if any site moves that a user reaches without asking for Pawley.

## Acceptance

Decided per site. For each site moved: its own tests and the fast suite
green, and no ranking or class decision on the acceptance suites lost.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Pawley, G. S. (1981). *J. Appl. Cryst.* **14**, 357-361.
- Le Bail, A., Duroy, H. & Fourquet, J. L. (1988). *Mater. Res. Bull.* **23**, 447-452.
- Le Bail, A. (2005). *Powder Diffr.* **20**, 316-326, doi:10.1154/1.2135315.
- WP-0306 (Pawley mode), WP-1323 (the Le Bail stop rule), WP-1542 and
  issue #740, WP-1910, WP-1953 (large Pawley stages), WP-2011.

## Handover log

- **2026-10-28** — forward notes from WP-2011's `quick` measurement added to
  § Context (Pawley's cost on a pseudo-symmetric cell, the `quick` result, a
  Pawley unit dependence, the re-grounded constants, the names ruling). Not
  started: WP-2011's go is back with the maintainer, and decision 0 now has
  a third route (a sparse Pawley solve). *Next:* WP-2011's go, then this
  WP's decision 0.

- **2026-10-27** — filed as a scoping WP by the WP-2011 session, at the
  maintainer's request ("scope out replacing Le Bail as the default
  structure-free fitting method for all of rietx"). No open WP owns the
  package-wide choice: WP-2011 owns the indexer's validation only, WP-1910
  the extinction screen, WP-1542 Le Bail's own background. The inventory is
  an agent's read of the tree at `feae4c75`; the lines this file leans on
  were checked by hand. The practice survey (one agent, seven programs)
  is in `docs/practice.md`; its GSAS-II lines were checked by hand, its
  TOPAS quote was not. *Next:* the maintainer's five decisions, decision 0
  first.
