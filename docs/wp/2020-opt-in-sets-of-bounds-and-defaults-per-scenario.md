# WP-2020 — Opt-in sets of bounds and defaults for a scenario, tested on the datasets they name

Milestone: generality · Status: 🔄 2026-11-22 — parked by the maintainer: the scenario-set file reopens when a WP-2017 demotion leaves a limit or a starting value with nowhere to go; the instrument-profile record reopens on a result whose calibration source mattered and could not be traced, or a user asking for it
Track: The registry and the guard
Depends on: —
Priority: P2 2026-10-21 — the maintainer's concept, raised while declining a default backstop in WP-2002; it gives a demoted default somewhere to go other than away

## Goal

A caller can load a named set of bounds, starting values and plan settings written for one
kind of measurement, and the result says which set it ran under. A set is tested on fewer
datasets than a package default needs, and says which ones. The package defaults stay what
every competent refiner would accept; the scenario-specific choices live in sets the caller
opts into.

## Context

**The maintainer's words** (2026-10-21, answering WP-2002's sixth round, Q6 on a backstop
for a runaway instrument width): "No need to bound these values. I would like callers to
set the bounds themselves. Can you consider a new concept: opt-in sets of bounds and
defaults for particular scenarios. Instead of setting overfit defaults by default (ahem),
we load sets of defaults that have been tested on smaller numbers of datasets. This would
be like sharing a topas .inp, but more flexible or usable."

**Why it fits the generality milestone.** A tier-3 default must hold on three unrelated
dataset families, or it is demoted (`docs/milestones/generality.md` § The rule). Many
defaults hold on one family and serve it well: they were built for an in-situ series, a
nanocrystalline specimen or one instrument. Demotion today means removal. A set gives such
a choice a home where it is still one call away, and where its evidence travels with it.

**Candidates already in view** (each to be checked against the tree before it is used):

- The instrument-width backstop the maintainer declined as a default (WP-2002, Q6), and the
  chosen TCHZ width ceilings removed on 2026-10-21 (1 for U, W, X, Y; 0.5 for V).
- The sample-width backstops `params.vector.strain_cap` and `size_cap`, which exist because
  of a 248-pattern CuO→Cu series (issue #140). WP-2002 left them in place; whether they
  belong in a series set is this WP's question.
- The 2 nm crystallite-size floor removed by WP-2002's B8 ruling.
- The tier-3 rows WP-2017's second pass demotes, as it demotes them.

**What exists to build on.** `PLAN_PRESETS` and `PLAN_INFO` (plans only), the instrument
constructors (`Instrument.bragg_brentano` and the others), `save_instrument_profile` and
`load_instrument_profile`, a project directory (`.rex`), and the PowderLine recipe reader
(WP-1306), which reads a whole refinement from one file.

**Practice, recalled and not checked this session.** TOPAS users share `.inp` files and
include files of macros. GSAS-II shares instrument parameter files (`.instprm`) and copies
refinement flags between histograms. FullProf users start from example `.pcr` files.
Profex ships BGMN device files and structure templates. The survey task below checks each
of the seven programs rietx-bench runs, from source or manual.

*Superseded in part 2026-11-15.* The survey task replaced this recall with a checked section,
`docs/practice.md` § A named set of starting values, limits and refine flags. The recall
held. The survey adds that GSAS-II's `.instprm` carries values and no refine flags, and that
no program found records in its result which set it loaded.

## Findings: the inventory (2026-11-15)

Read from `rietx._audit.ROWS` on `origin/main` at `0f14ac25d`, and from
`docs/wp/2002-batch/rulings.md`. The table holds 1344 rows, 165 of them at tier 3
(15 actions, 14 codes, 111 constants, 20 defaults, 5 suggestion sites). A set holds what a
caller sets for one kind of measurement: limits, starting values and plan settings (this
WP's Goal). So the inventory asks of each candidate whether a set could hold it, what
evidence it has, and which datasets that evidence came from.

**The four candidates the Context named, checked against the tree.**

| Candidate | In the tree now | Evidence, and the datasets it was measured on | Scenario | Could a set hold it? |
|---|---|---|---|---|
| TCHZ width ceilings, 1 on U, W, X, Y and 0.5 on V | removed 2026-10-21 (sixth round, Q5). `TCHZ_CEILING_DEG` = 180 is left, a tier-3 setting for TRF's step scaling, four orders over any measured line | no measurement chose 1 or 0.5. Removing them moved one fit, CPD brucite with Stephens strain under TRF: Rwp 0.17877 to 0.17891 | weak patterns and series chains, by the ruling's argument | yes, as four limits. No dataset shows they help |
| A backstop for a runaway instrument width (sixth round, Q6 (a)) | never built; declined | an argument from the sample-width backstop; no runaway instrument width has been measured | series chains | yes, as limits. Untested |
| 2 nm crystallite-size floor | removed 2026-10-19 (B8) | one private archive of 606 TOPAS refinements. When it bound, `BOUND_HIT` reported it | nanocrystalline specimens. Below a few nanometres the Bragg-peak model itself fails, and `SIZE_UNUSUALLY_SMALL` now says so | yes, as a lower limit. One archive |
| `strain_cap`, `size_cap` (`params/vector.py:848` and after) | kept, and now tier 1: `STRAIN_CAP_RANGE_FRACTION` = 1.0 and `SIZE_CAP_RANGE_FRACTION` = 1.0, on the arithmetic that a line wider than the scan carries no information | issue #140: a 248-pattern CuO to Cu series, where Cu's `lor_strain` reached 1.1e5 and a real 16 wt % phase fell below 1 wt % | every fit | not as the WP filed it. A tier-1 default stays a package default under the generality rule (consent line in the handover entry) |
| WP-2017's demotions | none yet. WP-2017's log of 2026-11-05 reads "No demotion"; 18 of its groups are open | none | none | nothing to hold yet |

**What else is scenario-specific today, and what already carries it.**

| Setting | Tier | Evidence and datasets | Carried today by |
|---|---|---|---|
| TCHZ starting values u, v, w, x, y (`ProfileTCHZ` defaults) | 3 | start-invariance on LaB6; NAC lost its phase from w = x = 1e-2; FAP's GSAS protocol holds x | an instrument profile file, which stores calibrated values in their place |
| Beam polarisation K = 0.5 (`Source.polarization`) | 3 | a wrong K moved Biso by 12 σ at near-unchanged Rwp (WP-1311); a monochromated lab beam or a synchrotron sits near 0.99 | an instrument profile file; the result records K as assumed |
| Refinement order | 3 for `mccusker_default` | McCusker et al. (1999), the order only | nine plan presets: three lab, two magnetic, the default and its structural continuation, a profile-only plan and a Pawley plan |
| Series settings: `carry`, `carry_hkl_intensities`, `reseed`, `on_error`, the series plan | 3, ruled 2026-11-03 | CPD 1a-1h, the thermal ramp, the planted chain | the series verb's own defaults |

**The rest of the tier-3 rows.** A text match over the rows' evidence finds 37 whose evidence
names one family, synthetic problems only, or a second pass owed. Fifteen are solver
settings (13 in `optimize/`, and the two Le Bail convergence tests). Nine are magnetic: six
inside `solve_magnetic`'s ranking and three moment or width floors. Ten are diagnostics: three
codes, one suggestion site, `BOUND_HIT`'s two tests, `MODEL_FAR_FROM_DATA_RWP` and the three
`phase_support_sigma` rows. The last three are `MAX_SITE_ASSIGNMENTS`, `TCHZ_CEILING_DEG`
(above) and `HARMONIC_WEIGHT_SEED`. That seed is the one starting value among the 37, and it
is answer-invariant behind the closing stage. None is a limit, a starting
value or a plan setting that a caller would change for one kind of measurement. The match is a
regex, so the 37 is a lower bound on rows resting on one family.

**What the inventory adds up to.** No setting in the tree needs a new home today. The
removed and declined limits have no measurement showing they help any dataset. What is
scenario-specific already has a carrier: instrument values in an instrument profile file and
refinement order in a plan preset. Two things no rietx carrier holds: which datasets a profile
or preset was tested on, and, in a result, which profile file was loaded. `Provenance` has no
field for the second (`schemas/common.py:1178-1196`); whether a result names its plan preset
was not checked.

## Non-goals

- Changing a package default. Each default is decided by its own audit row.
- Building before the maintainer rules on the design brief.

## Tasks

- [x] Survey the seven programs (GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD,
      EasyDiffraction): how a user shares or loads a set of starting values, bounds and
      refinement settings, what such a file may contain, and how a result records it.
      Checked from source or manual, as `docs/practice.md` was.
- [x] Inventory the candidate settings from `_audit.ROWS` and the rulings: each with its
      evidence, the scenario it serves, and the datasets it was measured on.
- [x] A design brief for the maintainer: what a set may contain, where it lives (package
      data, a user directory, a project), how it composes with a caller's own settings and
      which wins, how a result and a history node record it, how its evidence is stated,
      and its name in the field's terms.
- [ ] Build the ruled design, with one set from the inventory and its tests.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

A loaded set changes only what it declares, the result names it, and its file states the
datasets it was tested on.

## References

- `docs/wp/2002-batch/rulings.md` § Sixth round's answers (the maintainer's words).
- `docs/milestones/generality.md` § The rule (tiers and demotion).

## Rulings

From the rulings triage of 2026-11-21, which checked the 2026-11-15 brief against the design
rules. Items 3 and 4 were answered on 2026-11-22.

Answered 2026-11-22 under the maintainer's routing rules of that day (WP-2237): each item was
settled by Claude and checked by a fresh agent that did not see the pick, or brought to the
maintainer, who answered "All as recommended".

1. *The "tested on" line in each plan preset's help text* (half of the brief's option B) is
   dropped. Settled by Claude under DESIGN.md § Rules, 2 (ruled 2026-10-27 and 2026-11-01),
   2026-11-21: no surface an agent reads while choosing carries a validation verdict, and the
   help entries are on that list. The alternative was to add the line.
2. *`strain_cap` and `size_cap` stay package defaults* (the brief's consent line). Settled by
   Claude under `generality.md` § The rule, 2026-11-21: both rows are tier 1 in `_audit.py`,
   a tier-1 row is kept, and only a tier-3 row needs the maintainer's approval. The
   alternative was to move them into a series set.
3. *Park the scenario-set file* (the brief's option C) until a WP-2017 demotion leaves a limit
   or a starting value with nowhere to go, under DESIGN.md Rule 5 (nothing is built before a
   case needs it). It is the maintainer's own concept. **Ruled by Yue 2026-11-22:** parked, as
   proposed; it reopens when a WP-2017 demotion leaves a limit or a starting value with
   nowhere to go.
4. *Record which instrument profile file a result was fitted under, or park the WP.* The
   brief is in the 2026-11-21 handover entry. **Ruled by Yue 2026-11-22:** park WP-2020
   (recommendation A), as recommended. It reopens on a result whose calibration source
   mattered and could not be traced, or a user asking for it.

## Handover log

- **2026-11-21** — A rulings triage, docs only (PR #1759). It
  read the 2026-11-15 brief against the design rules and settled what a rule settles. One
  half of that brief's lean is ruled out: DESIGN.md Rule 2 keeps a "tested on" line out of
  the help text an agent reads while choosing a preset. So one small question is left for
  the maintainer: whether a result should name the instrument profile file it ran under.
  § Rulings above records what was settled and what waits.

  #### Brief for the maintainer: record the loaded profile, or park

  **The decision.** Whether WP-2020 builds one small thing now, a record in each result of
  the instrument profile file it was fitted under, or parks until something needs a new
  home. It comes to you because it changes what a result returns (your rule on reader
  output), it changes a stored format, and its value rests on a guess about how scientists
  read old results.

  **Why it matters.** The survey and inventory found nothing in the tree that needs a
  scenario-set file today, so the 2026-11-15 brief leaned to extending the two carriers
  rietx has. Half of that lean was a "tested on" line in each preset's help text, which
  Rule 2 now rules out. The other half is this. An instrument profile file is what
  `save_instrument_profile` writes after a `lab_calibrate` fit: calibrated widths, zero
  shift and polarisation. `load_instrument_profile` reads it back with every parameter
  fixed. A result keeps the instrument values, and so does the history. It does not keep
  the name, path or hash of the file they came from. Someone reading a result months later
  sees the numbers but cannot tell whose calibration they were, or whether that file has
  since been redone. No user has reported this. Importance: minor.

  **Aim.** I read the aim as serving the person or agent who reads an old result and needs
  to know what it assumed. Correct me if the reader you have in mind is a scientist picking
  a ready-made set for a kind of measurement. That reader is served by the parked
  scenario-set file, not by this.

  **Options.**

  - (A) Park WP-2020. Nothing is built. The status says it waits for a WP-2017 demotion of
    a limit or starting value, or a user's request for a named set. Costs nothing and is
    fully undoable. A result stays silent about which file its calibration came from.
  - (B1) Record the loaded profile. `load_instrument_profile` stamps the instrument with
    the file's name, path and sha256, and the result's `Provenance` and each history node
    carry it. About half a day. It is a schema change on `Instrument` or `Provenance`. Old
    files still open, and every result built from a profile gains a field. Undoable before
    a release. After a release it is a stored-format change.
  - Dropped: a "tested on" list inside the profile file. With no shipped profile to fill
    it, it would be built before a case needs it (Rule 5).

  **Practice.** From `docs/practice.md` § A named set of starting values, limits and refine
  flags, checked from source or manual on 2026-11-15. None of the seven programs records
  the loaded file in its result. GSAS-II prints the path once to the console. TOPAS writes
  the expanded input to its log. FullProf keeps the IRF name in the rewritten `.pcr`.
  Profex's refinement preset stores its files with checksums. In rietx, a project records
  its pattern file by sha256 (`DataRef`), because there the bytes are the contract. A
  profile's values are what a fit uses, and they are already recorded. Outside diffraction
  (recall, not checked this session), Hydra saves the composed configuration beside every
  run. It records the values, not the files they came from. My knowledge of these tools
  ends in mid-2026.

  **Recommendation.** A, as a lean. In your question order:

  - Purpose: the WP's purpose has no case today. The provenance gap is a second purpose
    the survey found.
  - rietx convention: an input whose bytes matter is hashed. A profile's values are what
    matter, and they are kept.
  - Agents: an agent reading a result sees the instrument values. A file name adds only
    who calibrated.
  - TOPAS and GSAS-II: a log at most.
  - Outside diffraction: Hydra keeps values.
  - Design ethos: build nothing before a case needs it.

  The crux is whether "which file" adds anything to "which values" for a real reader. I
  think it does not yet. B1 loses there, because no program records it and nobody has
  asked. The 2026-11-15 lean to B rested partly on the help-text half, and Rule 2 now
  rules that half out. Two observations would flip me to B1: a result whose calibration
  source mattered and could not be traced, or a user asking for it.

  *Next.* The maintainer answers rulings 3 and 4. Under A the WP parks with its trigger in
  the status line. Under B1 task 4 builds the record and its test.

- **2026-11-15** — The survey and the inventory are done, and they point away from building a
  new kind of file now. Every one of the seven programs has a file for an instrument's values,
  and no program records in its result which file it loaded. Nothing in rietx today needs a
  new home. The limits this WP was filed to rehouse were removed or declined with no
  measurement showing they help, and the strain and size caps turned out to be arithmetic.
  What rietx lacks is smaller: a profile or preset cannot say which datasets tested it, and
  a result cannot say which profile it ran under. The design brief below waits on the
  maintainer, and task 4 builds whatever is ruled.

  *Done.* Survey of the seven programs: `docs/practice.md` § A named set of starting values,
  limits and refine flags (one agent per two or three programs, Sonnet, with the load-bearing
  claims re-read by the lead: GSAS-II's flags-False read and its nine coded sets, FullProf's
  47 IRFs and their readme, MAUD's `instruments.mdb` with no limits, TOPAS's "User defined
  min/max limits override the defaults"). Inventory: § Findings above. The Context's recalled
  practice is marked superseded in part.

  *Measured.* `_audit.ROWS` on `0f14ac25d`: 1344 rows, 165 at tier 3, 37 of them resting on
  one family by a regex over their evidence. None of the 37 is a limit, starting value or plan
  setting a caller would change for one kind of measurement. No test ran, because the branch
  touches `docs/` only.

  *Gotchas.* GSAS-II 5.8.4's "Save profile" may call `WriteInstprm` with its arguments
  shifted (`GSASIIfiles.py:533`). That was read from source and not run. It is GSAS-II's
  defect and bears on nothing here. FullProf's `.out` and TOPAS's OUT were not checked for
  the include or IRF file name.

  #### Brief for the maintainer: a scenario-set file, or the two carriers rietx has

  **The decision.** Whether WP-2020 builds a new kind of file (a named set of limits,
  starting values and plan settings), extends the instrument profile file and the plan
  presets instead, or waits. Two triggers send it to you. It changes the project's direction
  (a new concept on the top-level API), and two of the options change a stored format.

  **Why it matters.** A rietx default applies to every fit. The generality rule says a
  default rietx invented must hold on three unrelated dataset families, or it is demoted. Today
  demotion means deletion. Your idea (WP-2002's sixth round) was a second home: a named file a
  caller loads on purpose, tested on fewer datasets, saying which ones. You compared it to
  sharing a TOPAS `.inp`, made more usable. The survey and the inventory asked what would go
  in it. Nothing in the tree needs it yet:

  - The TCHZ width ceilings and the 2 nm size floor were removed on your rulings. No dataset
    showed they helped.
  - The instrument-width backstop was declined and never measured.
  - The strain and size caps are tier 1 now.
  - WP-2017's second pass (every tier-3 threshold on three families) has demoted nothing.

  The scenario-specific settings that remain already have a carrier. An instrument profile
  file holds calibrated widths, zero and polarisation. Nine plan presets hold the refinement
  order for lab, magnetic, Le Bail and Pawley work. Two gaps are real. A profile file or a
  preset cannot say which datasets tested it. A result cannot say which profile file it was
  fitted under, so its reader cannot tell whose calibration it assumed. Choosing badly costs
  one of two things. Build too much, and rietx carries a file format that must open forever,
  with no set worth shipping in it. Build nothing, and the next demoted default is deleted,
  and results stay silent about their calibration. Importance: moderate.

  **Aim.** I read the aim as serving two readers. One is the expert who calibrates a setup
  once and hands it on, as a TOPAS user shares an include file. The other is the agent or
  person reading a result later, who needs to know what it ran under. Correct me if the first
  reader is instead the scientist choosing a ready-made set for a measurement type.

  **Options.**

  - (A) Do nothing now. Park the WP until WP-2017 demotes a limit or a starting value, or a
    user asks for a set. Costs nothing and is fully undoable. The next demotion still has
    nowhere to go.
  - (B) Extend the two carriers. A profile file gains a name and a "tested on" list (each
    dataset and what was checked on it). Loading one writes its name, path and file hash into
    the result's `Provenance` and the history node. Each plan preset's help text gains the
    same tested-on line. About a day. It bumps the profile format's version, so it is a
    stored-format change. Old profile files keep opening. No new name reaches the API.
  - (C) Build the concept as filed. A new file holds instrument values, limits and plan
    settings together, with its tested-on list. A caller loads it by name, the caller's own
    settings win, and the result records it. Several days, a new stored format and a new
    top-level name. The first set would come from the inventory, and every candidate there is
    untested (series instrument-width limits, a nanocrystalline size floor). Hard to undo once
    files exist, since an old file must always open. The WP's acceptance also says a set
    "changes only what it declares". `load_instrument_profile` today returns every parameter
    fixed, so C needs a new loading verb as well.
  - Dropped: a set written as a python module or a macro language. rietx's parametric
    equations own expressions, and a second language breaks the one-integration-surface rule.

  **Practice.** From the survey (`docs/practice.md`, checked from source or manual):

  - GSAS-II, FullProf, MAUD and Profex ship instrument sets. Only FullProf's IRF headers name
    the standard they came from (D1A from Na₂Ca₃Al₂F₁₄, ID31 from LaB6). No program's file
    states which datasets tested it.
  - GSAS-II's instrument file and FullProf's IRF carry values without refine flags. TOPAS,
    BGMN, MAUD and RIETAN-FP files carry values, limits and flags together, because each is a
    piece of the program's own input language.
  - Where a program says which value wins, the user's own setting wins (TOPAS limits, a
    Profex copy edited in place).
  - No program records the loaded file in its result. GSAS-II prints the path once to the
    console. TOPAS writes the expanded input to its log. FullProf keeps the IRF name in the
    rewritten `.pcr`. Profex's "refinement preset" stores its files with checksums.
  - The field's words are "instrument parameter file", "resolution file", "include file",
    "template", "device file" and "refinement preset". rietx already says "preset" for plans
    and for the GUI's geometries.
  - Outside diffraction (recall, not checked this session). Hydra composes a run's
    configuration from named groups, lets later entries and the command line win, and saves
    the composed configuration beside every run. ESLint's shared configurations are extended
    by a local file, and the local file wins. My knowledge of these tools ends at mid-2026.

  **Recommendation.** B, as a lean. In your question order:

  - Purpose: a home for scenario choices, and a record of what ran.
  - rietx convention: both carriers exist and are documented, so extending them follows it.
  - Agents: an agent gains most from the result naming its profile. The tested-on list helps
    it pick a preset.
  - TOPAS: include files carry everything and let the user win, and TOPAS records an include
    only in its log.
  - Outside diffraction: Hydra's saved configuration is the precedent for recording.
  - Design ethos: build the smallest thing, and build no carrier before anything needs one.
    C fails here today. No question flipped the lean.

  The crux is whether anything in the tree needs a new carrier now. The inventory says
  nothing does. A loses to B because the result's silence about its calibration is a gap
  today, whatever WP-2017 finds. Two observations would flip me to C: a ruling that a
  specific set should exist now (say, instrument-width limits that series users can ask
  for), or a WP-2017 demotion of a limit or a starting value.

  **Consent line.** I will leave `strain_cap` and `size_cap` as package defaults, because
  their audit rows are tier 1 (a line wider than the scan carries no information) and the
  generality rule keeps tier-1 defaults, unless you object. (Settled by Claude 2026-11-21,
  § Rulings item 2: only a tier-3 row needs the maintainer, so this line no longer waits.)

  **Settled for you.**

  - The inventory counts only what a caller sets per measurement (limits, starting values,
    plan settings) and leaves solver numerics out. Grounds: the WP's Goal names those three.
    The alternative was to treat every one-family tier-3 row as a set candidate.
  - The survey went to `docs/practice.md` as one section with a row per program, under that
    file's convention and the save-every-survey rule. The alternative was a WP batch file.
  - A shipped distribution file (FullProf's IRFs, MAUD's `instruments.mdb`) is cited as
    checked against the distribution's own files. The alternative was to mark it inferred.

  *Next.* The maintainer rules on the brief: A, B or C, and under C the name. Then task 4
  builds the ruled design with one set or one extended profile and its tests, and the
  acceptance command runs.

- **2026-10-21** — Filed by the WP-2002 session from the maintainer's answer to the sixth round's Q6. Nothing built; the survey is the first task.
