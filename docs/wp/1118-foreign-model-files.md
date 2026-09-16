# WP-1118 — foreign model files: read a refinement in, write one back

Milestone: unscheduled · Status: 🔄 2026-09-16 — the TOPAS `.inp` reader
(PR #98), the FullProf `.pcr` reader (PR #111), the GSAS-I `.PRM`
instrument-parameter reader (PR #248), the model-format registry over them and
the GSAS `.EXP` reader (#103), whose acceptance rewire showed the FAP suite
refines 20 parameters where GSAS refined 28; `read_gsas_prm` now reads its
fixed-format records by column and a Kα doublet with them (PR #332), and
refuses an out-of-range value naming the file; the GSAS-II `.gpx` reader landed
2026-09-16 behind a restricted unpickler (#234), whose corpus pass corrected the
`.EXP` reader's GOF claim; every writer remains
Depends on: — (WP-1110 found it; WP-1102 owns the one seam that overlaps)

## Goal

Reading a TOPAS, GSAS or FullProf control file returns the model it describes —
the `Structure`/`Instrument` pair **and the refine flags**, which are the
protocol — and says in diagnostics what it could not carry across. Writing emits
the same model back in the target's own language, naming what has no counterpart
there. Bringing an existing refinement into rietx stops being a transcription
exercise, and checking rietx against the code it came from stops being one too.

## Context

**The evidence is WP-1110's agent round, item 19.** Six agents refined a
68-pattern in-situ series transcribed by hand from a TOPAS `.inp`, and all six
named the transcription as the hardest part of the work — including having to
infer that a missing backtick means "fixed". A mistyped coordinate stays
symmetry-valid and fails silently, so the failure mode is a plausible wrong
answer rather than an error. Nothing in the package helps.

**This repo already pays the same cost.** `tests/data/FAP.EXP` is GSAS's
converged fit and `INST_XRY.PRM` its instrument file; every reference value and
the whole refine protocol of `tests/test_acceptance_fap.py` was read out of them
**by hand** and lives as constants in the test and in `tests/data/README.md`.
Same for `11bm_gsas.prm`'s wavelength. A reader would give those constants one
authority instead of a transcription, which is DESIGN.md's v0.2 lesson —
comparing against another code means adopting its *protocol*, not its numbers —
made mechanical.

**The refine flags are the payload, not the numbers.** A control file says which
parameters were free, which were held, what was excluded and in what order the
author freed things. That is the part a person cannot reconstruct from a CIF
plus a pattern, and it is the part that decides whether a cross-code comparison
means anything (DESIGN.md § "Learned in v0.2": a guessed protocol gave Rwp 16 %
and +390 ppm on fluorapatite, the mirrored one 9.73 % against GSAS's 10.05 %).
So the answer's shape is a model **plus** a vary set or a `PlanSpec`, never a
`Structure` alone.

**The write direction, sharpened by issue #148 (2026-09-01 triage).** The
writers task below gains its strongest test for free: **round-trip** — export
→ re-import must reproduce the model bit-for-bit wherever the format can
carry it, the cheapest adversarial test the readers can get, no external
fixture needed — so it belongs in this WP's acceptance, not only its tasks.
GSAS-II joins the write targets (`.instprm` + CIF-shaped structure — text,
documented, and the `Z`-term round-trip question sits on the writers task
below). Every convention the validation campaign measured (FCJ vs A_T2,
K = 1 vs 0.5 polarization, U vs B vs β, FWHM vs σ, centidegrees) becomes a
written decision with a citation on the writer. Deliberately **not** here:
an RMCProfile export (data + starting configuration, not a protocol —
issue #192's territory), and Rietica/XND in either direction — issue #196
proposes those readers as a beyond-the-majors widening of this family;
right home, deliberately unscheduled, no corpus, and the read/write
asymmetry is intentional.

**Two things arrive with the TOPAS files (issues #107, #101).** Seven
archive files open phases with the macro form `STR(R-3)` /
`STR(######, "#name#")`, which the line-based split cannot see. PR #98 took
the minimum honest fix with it, which was independent of any design:
recognise the spelling and **refuse naming it**, because a reader may decline
a construct but may not describe it as absent. So such a file now raises,
counting the phases it states, instead of parsing **zero phases** and letting
`to_structure` answer "a Pawley or indexing-only .inp is legal and has none".
What is still undone is *reading* them, and two already-fixed macro bugs hide
behind them, so **PR #98's incidence figures are floors until this is
decided**. Whether `STR(...)` is special-cased or the reader grows a general
macro pass is the registry-shape task's decision (and a general pass borders
[1119](1119-named-variables.md)'s equations scope — decide the boundary
there, not twice). Second, origin choice:
`gemmi.SpaceGroup("Pn-3m").ext` is `'1'`, so a structure transcribed from an
origin-choice-2 source gets choice 1's symmetry with nothing raised — wrong
structure factors under a healthy-looking fit — while the TOPAS spelling
`Pn-3mZ` raises, and stripping the letter inverts the meaning. The
translation table exists in the #98 draft (`normalize_space_group`: `Z`→`:2`,
`S`→`:1`, `R`→`:R`, `H`→`:H`); the **diagnostic is the load-bearing half**
and is general — it fires for any multi-origin symbol left unpinned, from
any reader, in the reader diagnostics channel where such reports belong.

**Two things the `.inp` reader met on a real workshop archive** (WP-1130, and
neither is a bug). Of the four `.inp`s in the Durham ZrMo₂O₈ archive **three
refuse** at their first `#if` — the multi-pattern reel files, which are exactly the
case WP-1110's agent round named as the hardest part of the work. The refusal is
correct (which branch was refined is unknown, and reading on would report a model
mixing both), but 1130 got its model by stripping the `#if`/`#endif` blocks in a
scratchpad, which is a workaround no user should have to invent: a `#prm`-only
integer evaluator would resolve `#if (#out pattern_count > 1)` and the `Run_Number`
guards, which is most of what these files use `#if` for. And
`TOPAS_FEATURES_NOT_IMPORTED` named the thing that mattered while nothing downstream
could act on it — the dropped `spherical_harmonics_hkl` block sat on a phase owning
**24 % of the fit's χ²**, and supplying rietx's own equivalent (Stephens
`Phase.microstrain`) took Rwp 0.1092 → 0.0878. So that gap is a *conversion*, not a
capability: rietx has the physics. If `to_structure` ever grows an hkl-strain arm, the
`.inp`'s coefficients are **fixed** (`!ahkl_c00` … `!ahkl_c44p`, taken from another
range), so importing them imports a held model — and freeing such a block can make
other phases `PHASE_UNCONSTRAINED`, so it is not a change to make silently.

**A magnetic phase stays refused in both readers until the model exists.**
`coverage.py`'s `magnetic structure` feature is `Stance.REFUSED`, and a FullProf phase
with Jbt = ±1 takes the same stance and the same sentence ("the nuclear half would
look complete") through the registry rather than a raise, so
[1328](1328-magnetic-interchange.md) lifts both by changing one table. Do not map a
Fourier-component magnetic phase onto a nuclear structure in the meantime. Still true
2026-09-13: there is no moment on `main` — WP-1343 scoped the magnetic *broadening*
term and [1327](1327-magnetic-structure.md) still owns the model itself.

### The licence fences, which are stricter here than anywhere else in `io/`

`ATTRIBUTION.md` carries the standing rows; each new format adds its own. What
they already establish:

- **TOPAS is closed — papers and its own documentation only.** The `.inp`
  language is described in the TOPAS-Academic Technical Reference (v8 § 2.17 is
  already cited by WP-1110 § "The cell window, measured"), and real `.inp` files
  are a second description. No implementation is consulted: BGMN/Profex and
  xrayutilities are GPL, so **concepts only, never code** (root CLAUDE.md §
  Licensing).
- **FullProf is closed — manual and papers only** (Rodríguez-Carvajal 1993). The
  `.pcr` layout is documented there.
- **GSAS/GSAS-II is a *spec-only* source with a grant-back clause.** The `.EXP`
  and `.PRM` layouts are documented in Larson & Von Dreele (2004) LAUR 86-748;
  GSAS-II's own importers may be read as a specification and never ported.
  `ATTRIBUTION.md`'s GSAS-II row is the standing statement of this.
- **The Bruker `.raw` v3 precedent decides what to do with a thin spec**: a
  version with one uncorroborated description and no file to check it against is
  **refused by name**, because that is how a reader comes to return a plausible
  wrong model.

### Seams to extend, and the one rule that gets harder

`src/rietx/io/CLAUDE.md` (auto-loads under `io/`) is the rulebook: one module per
format, an ordered registry whose order is behaviour, a bounded `head()` sniff,
and refusals that name the file rather than the parser's exception. Three things
are different for a *model* file and must be decided before any parser is
written:

- **A second registry, not an arm of `PATTERN_FORMATS`.** The answer's shape
  differs (a model, not a `PatternData`), and `DataRef` exists to record which
  pattern reader claimed a file. A control file *points at* a pattern; that
  pattern still goes through `read_pattern` as now.
- **"A reader may repair only where it can say that it did" binds harder here.**
  A `.inp` holds constructs this package has no model for — macros, `prm`
  expressions and their dependency graph, `fit_obj`, penalties, `local`s — and
  silently dropping one changes the model rather than the presentation. So the
  reader reports every construct it did not carry, by name, and **refuses** where
  the construct would change the answer it is about to return. `Parameter.expr`
  is refused at construction (WP-1110 item 5), so a `prm` expression that is not
  expressible as a tie has no landing site by design.
- **The writer fails in the opposite direction and needs its own rule.** A
  Stephens strain block, a P-spline background, a restraint weight schedule or a
  staged `PlanSpec` may have no counterpart in the target. Precedent from
  WP-1110 item 14: **mark, never clamp** — name what did not cross at write time
  rather than emitting a file that looks complete.

- **There are now three reader *kinds*, and the third arrived without a home.**
  `rx.read_gsas_prm` (PR #248) returns an `Instrument` and sits in
  `io/instrument_profile.py` beside the native JSON profile reader: it is neither a
  `PATTERN_FORMATS` entry nor an `io/projects/` project reader. `io/CLAUDE.md`'s "one
  module per format" is scoped by its own first line to the *pattern* readers, so
  nothing governs it — while the drift that rule exists to prevent is now real, since
  that module carries two formats' fences. Raised with the maintainer at the merge, no
  decision taken; it is this task's to settle, and the registry now has **four**
  instances to answer its shape from (`read_topas_inp`, `read_fullprof_pcr`,
  `read_gsas_prm` and `read_recipe`) rather than one.
- **A general macro pass is not blocked on an expression language, because rietx is
  not growing one** ([1119](1119-named-variables.md) § Decisions 4, which shipped
  `Refinement.add_variable` and deliberately no expression string). The object a reader
  would target now exists; the arithmetic the two readers carry privately
  (`topas.symbol_table`/`_resolve`/`_arith`, the `.pcr` codeword decoder) stays theirs.
  So if `STR(...)` needs a macro pass it is a `.inp` grammar concern living entirely in
  `io/projects/topas.py` and answering to the Technical Reference — decide it there,
  not here.
- **A bare space-group symbol now has one authority, and each format sits on a side of
  it** ([1324](1324-symmetry-silences.md)).
  `crystallography.symmetry.setting_alternatives(symbol)` returns `(taken, others)` for
  the 40 symbols the tables hold in more than one setting, and the fit-time report
  `SPACE_GROUP_SETTING_ASSUMED` fires only where a reader handed a bare symbol on. A
  reader that resolves the setting itself keeps its callers silent — which is what
  `normalize_space_group`'s trailing-`Z` → `:2` mapping buys the `.inp` route. FullProf
  writes the symbol without a suffix in the common case, so the `.pcr` route either
  establishes the setting from evidence the file carries (as `read_small_structure`
  picks R from the cell) or hands the bare symbol on; both are defensible and the choice
  should be deliberate.

`capabilities()` publishes the pattern formats `read_pattern` opens; the model formats
need their own arm — and so, on the evidence above, may the third kind — with the
meta-test that fails on a registry member missing from its arm applying unchanged. A new
format token is spelled in `_about.py`, never inline (root CLAUDE.md § Conventions).

## Non-goals

- **Not a TOPAS-compatible engine.** No macro language, no `prm` expression
  evaluator, no `fit_obj`. A construct with no model here is reported, not
  emulated.
- **GSAS-II `.gpx` is no longer fenced out — it is a task, behind a
  restricted unpickler** (decided 2026-09-03 on issue #234; the task line below
  carries the measurements). Until that day this bullet fenced it for a
  reason measured false. What stays out: any `.gpx` content the corroborating
  corpus does not cover — image, single-crystal, sequential-fit and magnetic
  projects — until the corpus widens, and a `.gpx` *writer*, which is the
  writers task like every other format. `.EXP`/`.PRM` are text and documented.
- **Not the additive component seam.** A `fit_obj` or a `.pcr` extra peak lands
  on `Instrument.extra_components`, which is [1102](1102-component-seam-humps.md)'s.
- **Not a pattern reader.** `io/`'s existing registry keeps that job.

## Tasks

- [x] Decide the answer's shape and stand up the model-format registry beside
      `PATTERN_FORMATS`. — 2026-09-13. The unit is a **refinement**, not a
      foreign file: `PROJECT_FORMATS` + `read_project_model` dispatch on
      content, the answer is `ProjectModel` (the format's own model, tagged —
      never a union with blanks), `read_gsas_prm` and `read_recipe` stay
      outside it with their reasons written down, and the readers are top-level
      `rx.` exports with a `capabilities().project_formats` arm. #107, #103 and
      [1314](1314-mfile-reader.md) are unblocked.
- [x] TOPAS `.inp` reader — the format with the evidence behind it.
- [x] GSAS `.EXP` + `.PRM` reader, and make `tests/test_acceptance_fap.py` take
      its protocol from the reader instead of from transcribed constants.
      — the `.PRM` half landed (`rx.read_gsas_prm`, PR #248, merged 2026-09-10,
      `ff69ec34`); the `.EXP` half and the acceptance rewire landed 2026-09-15
      (`rx.read_gsas_exp`, `PROJECT_FORMATS` member `gsas_exp`). `Closes #103`.
      Two follow-ups this task **did not** do, each with its numbers in the
      handover entry: the plan still frees no coordinate DOFs where GSAS freed
      twelve (measured, nearly free to close), and `read_gsas_prm` reads the
      same `ICONS` record by whitespace split rather than by column.
      **The first is decided, 2026-09-15: the suite keeps its 20 and keeps the
      assertion.** Freeing the twelve coordinate DOFs was measured cheap
      (Rwp 0.096966 → 0.096677, 0.1 ppm on the cell, no wall clock), and the
      maintainer's call is that a suite stating the difference is worth more
      than one closing it: the two recorded acceptance numbers stay where they
      are, and the parameter-count gap stays asserted rather than removed. The
      second is the task line below.
- [x] `read_gsas_prm` reads its fixed-format records **by column**, closing the
      class the `.EXP` reader's first decision opened. A `.prm`'s `INS` records
      are the `.EXP`'s `HST`/`INS` records under a different four-character
      key, and this reader splits three of them on whitespace: `ICONS`,
      the `PRCF1` header and its continuation lines. `ICONS` is where it bites
      and the corpus hides it — `11bm_gsas.prm` leaves `IREF`/`IDAMP` blank, so
      its six tokens happen to land on the right meanings, while
      `INST_XRY.PRM` writes `IDAMP` and is **refused** for having seven.
      One record read two ways by two readers in one package is the thing this
      codebase most dislikes, so the record grammar gets one authority.
      Whether the doublet `INST_XRY.PRM` also carries can then be read is the
      second half: the `KRATIO` the old reader could not locate is field 8, and
      that file states it.
      — landed 2026-09-15. `projects/gsas.py` grew `read_icons`,
      `read_prcf_header` and `split_records`, all public and all called by the
      `.prm` reader; the coefficient names come from `CW_PROFILE_COEFFICIENTS`
      rather than a second literal list. The four real calibration files read
      **bit-identically** (measured against `origin/main`'s module over the
      whole `model_dump`), `INST_XRY.PRM` is refused for its `GP` of 0.1
      rather than for a token count, and a doublet is now read: the refusal's
      stated reason had expired. `io/CLAUDE.md` takes the two rules, the cap
      368 → 383.

- [x] FullProf `.pcr` reader. — PR #111, merged 2026-09-03 (`b717cc98`)
- [x] GSAS-II `.gpx` reader behind a **restricted unpickler** (decided
      2026-09-03, issue #234). — landed 2026-09-16. `rx.read_gsas2_gpx`,
      `PROJECT_FORMATS` member `gsas2_gpx` (first, being the one binary
      member), `projects/gsas2.to_structure`, seven `GSAS2_GPX_*` diagnostics.
      **The corpus was widened first, and it moved three decisions.** The
      public GSAS-II tutorial corpus (34 projects, redistributable, unlike this
      WP's other two formats) covers every kind #234 listed as untested, and
      `Closes #234`.
      (1) The allow-list in #234 is **incomplete**: eleven globals appear and
      seven are outside it, so a list measured on one 146-file archive would
      refuse 10 of 34 real projects. `G2VarObj` and `ExpressionObj` are
      admitted as **inert stand-ins** rather than refused, which is PyTorch's
      `weights_only` shape and the reason a refusal aborts the whole file
      rather than a record.
      (2) The sniff cannot be the magic bytes — 11 of the 34 carry no pickle
      protocol header at all.
      (3) `Rvals['GOF']` is the **square root** of reduced χ², which is the
      opposite of what `projects/gsas.py` claimed about it; corrected there in
      the same branch, with the GDNFT claim itself left standing.
      Two shapes the specification never mentions are refused by name because a
      real corpus contains them: a negative `Uiso` (7 of 34) and a phase with no
      sites (GSAS-II's Le Bail extraction). 19 of the 34 build a structure and
      15 refuse, each naming its phase.
- [ ] Origin-choice honesty: `SPACE_GROUP_ORIGIN_ASSUMED` when a multi-origin
      symbol resolves unpinned, and the TOPAS suffixes accepted on input
      (issue #101; lift `normalize_space_group` from the #98 draft).
- [ ] The writers, each naming what did not cross — GSAS-II included — with
      export → re-import round-trip as each format's acceptance (issue #148).
      Two obligations already banked. An exporter writes
      `get_spacegroup(sym).xhm()`, never the phase's stored string, or a
      round-trip through a foreign format launders a resolved setting back into
      an ambiguous one ([1324](1324-symmetry-silences.md)). And **a GSAS-II
      profile cannot round-trip today**: GSAS-II's CW Lorentzian is
      `γ = X/cosθ + Y·tanθ + Z` while `ProfileTCHZ` declares exactly `u, v, w,
      x, y` (verified 2026-09-13; `params/vector.py` hard-codes that five-name
      tuple twice), so an `.instprm` with a nonzero `Z` has nowhere to land.
      Carry it or refuse it by name is this WP's call, not a physics question —
      Von Dreele's own teaching slide says `X, Y, Z = 0` is normal and 11-BM has
      them zero, so `Z` earns a schema field for round-tripping and not for
      modelling ([1131](1131-sample-broadening-is-a-specimen-property.md) fenced
      it here). For the same reader: rietx's `profile.x` is the 1/cosθ (size)
      coefficient and matches GSAS-II's `X` by law, while TOPAS's `pkx`/`pky`
      map to rietx's `y`/`x` and **not** by letter (measured in WP-1130).
- [ ] `capabilities()` arm, skill rows for the new diagnostic codes
      (`docs/skill/rietx/` — `AGENT_PROTOCOL.md` is a redirect stub since
      WP-1304), a Part 1 manual section, and an `ATTRIBUTION.md` row per
      format. The TOPAS half of the diagnostic rows and its `ATTRIBUTION.md`
      row landed, and the GSAS `.EXP` half on 2026-09-15 (arm, six
      `GSAS_EXP_*` rows in `references/diagnostics-projects.md` §7g, a Part 1
      section over the whole `GsasModel` tree, and an `ATTRIBUTION.md` row).
      **The `.gpx` half landed 2026-09-16**: the arm is derived from
      `PROJECT_FORMATS` so it needed no edit, seven `GSAS2_GPX_*` rows joined
      `references/diagnostics-projects.md` §7g (whose family prefix list in
      `tests/test_skill.py` grew with them), `rx.read_gsas2_gpx` joined
      `make_api_index.py`'s In section, a Part 1 section documents the whole
      `Gsas2Model` tree, and `ATTRIBUTION.md` has its row. **Still open for the
      writers.**
      **Superseded in part, 2026-09-13**: `references/api.md` § In
      was repaired somewhere between 2026-09-03 and 2026-09-13 and now names
      both `rietx.io.projects.read_topas_inp` and `read_fullprof_pcr`, says
      they have no top-level `rx.` entry point yet, and carries `rx.read_gsas_prm`
      — so it is no longer false.
      **Superseded again, 2026-09-15**: `SKILL.md`'s routing row is not owed
      either, and the claim that it was has never been true. Line 41 reads
      "you were handed another program's input file, not a pattern" and routes
      to `references/api.md` § In, which is the **situation** in the *When*
      column and the formats in § In, exactly as
      [1330](1330-skill-references-by-shape.md) asks. It landed 2026-08-30 in
      `7bc3e3d0` under WP-1308, before the note above it was written. No row in
      the file says "a PowderLine recipe"; the word `recipe` in that row is a
      manual page in the third column, which is how it was misread. Nothing is
      owed on the skill for the readers that have shipped. The byte-headroom
      cautions inherited from WP-1308 (27 B), PR #98 (32 B) and 1330 (36 B) are
      stale, and so are 09-13's replacements: measured 2026-09-15, `SKILL.md`
      is 31 951 B of its 33 000 cap (**1 049 B free**) and `references/api.md`
      32 796 B of 36 000 (**3 204 B free**). A body sentence is still paid for
      by a cut named in the commit; there is simply room to pay.
- [ ] A `#prm`-only integer evaluator for `.inp` `#if` guards, so the
      multi-pattern reel files read instead of refusing (§ Context; WP-1130
      measured three of four workshop files out of reach). Scope it to integer
      `#prm` comparisons — it is not the macro language, and § Non-goals still
      holds.
- [ ] Fixtures with provenance rows in `tests/data/README.md`; tests, and the
      obs/calc/diff PNGs for any refinement one of them drives. — the GSAS
      `.EXP` half landed 2026-09-15: `FAP.EXP`'s row says it is now the
      reader's corroborating fixture, and the file also **ships in the wheel**
      (`src/rietx/data/examples/`, `LICENCES` in `test_example_projects.py`)
      because the `fap` example reads its protocol from it. The `.gpx` half
      landed 2026-09-16 — `gsas2_pbso4.gpx` and `gsas2_lacamno3_magnetic.gpx`,
      the first project-reader fixtures this WP could **vendor at all**, since
      the GSAS-II tutorials carry a redistribution grant where TOPAS's and
      FullProf's corpora are private. Nothing enters the wheel. The 34-project
      survey behind them has its own section in `tests/data/README.md`. Open
      for the formats with no fixture yet.

## Acceptance

The repo already holds the file that can prove it. `FAP.EXP` is GSAS's converged
fluorapatite refinement and `tests/test_acceptance_fap.py` mirrors its protocol
from hand-read constants:

```sh
.venv/bin/python -m pytest tests/test_acceptance_fap.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

The bar is that the reader reproduces that protocol field for field — the free
set, the held Caglioti terms, the excluded region, the wavelengths — with the
acceptance test then reading it rather than restating it, and the measured
answer unmoved.

Issue closure rides the tasks, not the WP: the PR landing the `STR(...)`
decision carries `Closes #107`; the origin-choice task `Closes #101`; the
`.EXP`/`.PRM` task `Closes #103`; the writers task `Closes #148`. Issue
#196 (Rietica/XND) stays open — it is this family's recorded boundary, not
work this WP does.

## References

- Larson, A. C. & Von Dreele, R. B. (2004), *GSAS General Structure Analysis
  System*, LAUR 86-748 — `.EXP` and `.PRM` layouts.
- Coelho, A. A., *TOPAS-Academic Technical Reference* (v8) — the `.inp` language.
- Rodríguez-Carvajal, J. (1993), *Physica B* **192**, 55 — FullProf, and its
  manual for the `.pcr` layout.
- `ATTRIBUTION.md` — the GSAS-II spec-only row and the GPL/closed fences.
- [1110](1110-agent-surface-friction.md) § "Found by the round" item 19; DESIGN.md
  § "Learned in v0.2".

## Handover log

### 2026-09-16 — the GSAS-II `.gpx` reader, and the corpus that changed three answers

Someone can now hand this package a GSAS-II project file and get back the model
it describes: the phases, the sites, the instrument, and the part nobody can
rebuild from a CIF plus a pattern, which is which parameters that refinement was
free to move. A `.gpx` also carries two things the older formats have no room
for, and both come across: the constraints the run held its variables under, and
the list naming every variable it refined. None of it needs GSAS-II installed.

The obstacle was never the format. A `.gpx` is a sequence of python pickles, and
loading a pickle runs whatever it names, so opening a downloaded one would be
handing a stranger's file the keyboard. The reader resolves an allow-list and
refuses every other name, naming it, without reading the file at all.

The part worth knowing is that **the allow-list could not have been written from
one archive**. Issue #234 proposed one measured on 146 private projects; read
against the 34 public tutorial projects, seven of the eleven names that actually
occur are outside it, and two of those are GSAS-II's own classes, which appear in
10 of the 34. Refusing them by name would have refused those ten files entire.
They are admitted as inert stand-ins instead — a class with no `__reduce__` and
no `__setstate__`, which the pickle machinery can only fill with data — which is
the same shape PyTorch's `weights_only` unpickler uses, and it is why the
constraints are readable at all. Widening the corpus before writing the reader
was the whole of this session's method, and it moved two more answers: the sniff
cannot be the magic bytes, because 11 of the 34 files carry no pickle protocol
header; and GSAS-II's `GOF` is the **square root** of reduced χ², which is the
opposite of what this repo's `.EXP` reader said about it.

*Done* — six commits on `wp1118-gsas2-gpx`, cut from `origin/main` at `6d42926e`.

- `src/rietx/io/projects/gsas2.py` (1 100 lines) — the reader.
  `rx.read_gsas2_gpx` returns a `Gsas2Model`; `projects.gsas2.to_structure`
  builds a `Structure` carrying the file's own refine flags.
  `ALLOWED_GLOBALS` is the trust boundary as **data**, with a reason per entry
  and a meta-test partitioning it against the resolver both ways.
  `TREE_ITEM_STANCE` declares one stance per tree-item kind, sharing
  `coverage.Stance`'s vocabulary, so an unclassified item is reported rather
  than dropped.
- `PROJECT_FORMATS` gains `gsas2_gpx` **first**, being the registry's one binary
  member: every other sniff decodes with `errors="ignore"` and would meet a
  pickle as text with its bytes dropped. `capabilities().project_formats` needed
  no edit, being derived from the registry.
- Seven `GSAS2_GPX_*` diagnostics, rows in the skill's §7g, a Part 1 section over
  the whole `Gsas2Model` tree, and an `ATTRIBUTION.md` row naming which document
  was read as specification.
- `tests/test_projects_gsas2.py` (37 tests) and two vendored fixtures. These are
  the **first project-reader fixtures this WP could vendor at all**: the GSAS-II
  tutorials carry a redistribution grant where TOPAS's and FullProf's corpora are
  private research inputs.
- `projects/gsas.py`'s GOF corroboration corrected, in `GsasModel.reduced_chi2`,
  in `_reduced_chi2` and in the test docstring that repeated it. The GDNFT claim
  itself stands: that record states the words.
- `io/CLAUDE.md` takes three rules and the cap goes 383 → 410.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch), python
3.12.12, darwin/arm64, alone on the machine (checked with `ps aux | grep`).

- Fast selection `-n auto --dist loadgroup -m "not slow"`, on **current main
  merged into this branch**, which is the only tree anything ever tests that
  resembles what lands: **4997 passed, 133 skipped**, 2:10. On the bare branch
  before the merge it was 4990/132.
  The delta is derived per file rather than by re-measuring `main`. This
  session added **45**: 39 in `test_projects_gsas2.py`, 3 in
  `test_projects_gsas.py` and 1 in `test_gsas_prm.py` (the last four from the
  review pass), plus **2** parametrised cases the new registry member adds to
  `test_projects_registry.py` (`[gsas2_gpx]` on the `reports_at` and
  declared-field rows). Against the 4951 the previous session measured on the
  branch that is now `origin/main`, that is 4996, and the merge with WP-1423's
  main accounts for the remaining +1 pass and the one new skip — **which is
  WP-1423's, not this session's**: nothing here added a skip. Two parents'
  additions do not sum, so the 4997 is quoted as the merged tree's figure and
  not as either parent's.
- `tests/test_acceptance_fap.py`: 3 passed, 3.19 s. It reads its protocol from
  the `.EXP` reader, which this session touched (comments only), so it is the
  row that would notice.
- **No full selection.** Nothing this session added is reachable from a fit: the
  new reader has no caller inside the package, and the `.EXP` edits are
  docstrings. No measured number can move.
- The corpus, read with the finished reader: 34 projects read, **0 refused**; 19
  build a structure and 15 refuse by name (7 for a negative `Uiso`, 5 for
  anisotropic sites, 2 for stating no phases, 1 for a Le Bail phase with no
  sites). The survey behind those numbers is in `tests/data/README.md`
  § GSAS-II `.gpx`.
- The centidegree convention is corroborated **across formats** by a file this
  repo already held: the tutorial `.gpx` of the 11-BM instrument states `U`, `V`,
  `W` of 1.163, −0.126, 0.063, and `read_gsas_prm` converts
  `tests/data/11bm_gsas.prm` to 1.163e-4, −1.26e-5, 6.3e-6 deg². `Zero` is the
  exception and is degrees in GSAS-II, by its own specification and by the
  magnitude of the nine non-zero values in the corpus (0.0004° to 0.0219°).

*Reviewed* — `/code-review high --fix` over the branch diff, and it found the
class this session thought it had closed. Six fixes accepted, each with the test
it was missing; the review reproduced every one before changing anything.

- **The `.EXP` reader had the same hole the `.gpx` reader was written to
  avoid.** A file stating a negative `Uiso` reached `rx.Parameter` and came back
  as a pydantic `ValidationError` naming a `Parameter` and never the file. The
  refusal and the one-guard build are now in both readers, which is what
  "generalise the fix" should have meant while writing the second one rather
  than after.
- Two in the new reader, both on malformed input: the id-resolving passes
  assumed a tree-item shape the main loop had already reported as unreadable
  (a bare `[42]` raised `TypeError` out of the reader), and an empty atom row
  reached `row[-1]`.
- `GsasHistogram.two_theta_range` could come back `(None, 129.98)` under a
  `tuple[float, float] | None` annotation, which is WP-1076's shape in a field
  nobody had looked at.
- `BANK` was the one record in `instrument_profile.py` not read by column, in a
  module whose whole argument is that they are: a record carrying a comment
  after its `I5` count was reported as an absent record.
- Two dead names removed (`seen` here, `_EIGHT_PI2` in `viz/compare.py`).

Two findings were looked at and left, both recorded here rather than silently:
the `.EXP` row's `extensions=(".exp", ".EXP")` renders a second suffix that buys
nothing when matching is content-based, and `_matches_gsas_exp`'s `lines[:-1] or
lines` drops the last complete record when the head covers the whole file, which
can only bite a `.EXP` whose one vocabulary key sits on its final card.

*Gotchas* — three, each a place the next session should not assume.

- **The excluded-region path is specification-only.** Not one of the 195
  histograms in the corpus has one, so `Limits[2:]` rests on GSAS-II's own
  statement in `GSASIIstrIO` and is exercised by a `.gpx` the test module writes
  rather than by a real file.
- **The anisotropic refusal is liftable by a measurement, not by an opinion.**
  126 of the corpus's 439 sites are anisotropic and all of them are refused,
  which follows the `.EXP` and `.pcr` readers. Whether GSAS-II's `Uij` are CIF
  `U^ij` is testable rather than arguable: feed them through
  `crystallography.wyckoff.adp_basis` and see whether they lie in the
  site-symmetry subspace, which a wrong off-diagonal convention would break.
- **A `magPhases` key makes a nuclear phase half a model.** Ten corpus phases are
  typed `nuclear` and carry one, and they build correctly; what does not come
  across is the magnetic scattering in the file's own Rwp, so the figures are not
  comparable. That is a warning rather than a refusal, and it is a different
  shape from the magnetic phase the same code refuses.

*Next*, in order, with what decides between them.

1. **Origin-choice honesty** (#101), still the cheap one:
   `normalize_space_group` is drafted in the #98 branch and the task closes an
   issue.
2. **The writers** (#148). One of its two banked obligations is now evidenced
   rather than open: `Z` is zero in **all 95** constant-wavelength histograms
   the corpus states it on, so nothing anybody writes needs the field, and
   refusing a non-zero `Z` by name costs nothing a round-trip can see. Growing
   `ProfileTCHZ` a sixth coefficient is measurable work — the five-name tuple is
   hard-coded in four places and 121 files name a profile path — and it would be
   a declared name with no writer until the forward model computed it.
3. The `#prm` integer evaluator for `.inp` `#if` guards.


### 2026-09-16 — the handover the column read never wrote, and the refusal the repair found

A session that finishes its work and never writes it down leaves the next person
reading commit messages. This is that record. The entry below reconstructs what
the column read did; this one covers the repair that wrote it.

The repair was meant to be bookkeeping. It turned up two things instead. One is
a claim in this file that had never been true. The other is a defect in the
merged reader, and it is the one worth knowing. Handed a `.prm` whose numbers
fall outside what this package's schema holds, `read_gsas_prm` did not refuse
it. Pydantic did, naming a `Parameter` and never the file, which is the one
shape `io/CLAUDE.md` forbids a reader. It refuses by name now.

*Done* — on `wp1118-prm-columns-handover`, cut fresh from `origin/main`. The
column session's branch was already merged, so a commit on it would have been
stranded where the merge could not carry it.

- The reconstructed entry below, the Status line, and WP-1314's `### Inherited`.
- `0efac867`, the refusal, with its parametrised test.
- The stale claim in the skill task, repaired in place and dated.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch), python
3.12.12, darwin/arm64, alone on the machine (checked with `ps aux | grep`, not
`pgrep`).

- The four `.prm` fixtures re-read on the merged tree. They come back
  single-line at λ 0.41391, 0.41313, 0.41368 and 0.41330 Å, each weight 1.0,
  and `INST_XRY.PRM` refuses naming `GP`. That corroborates the shape of the
  answer. It does not re-verify the bit-identity claimed in the entry below,
  which needs the pre-branch module and stays that session's measurement.
- **The column session recorded no selection count. This one measured**, on
  the repair branch, alone on the machine: fast selection
  `-n auto --dist loadgroup -m "not slow"` → **4951 passed, 132 skipped**, 3:23.
  Five of those are this repair's own parametrised refusal test, so `origin/main`
  stands at 4946, derived per file rather than by re-measuring it
  (`tests/CLAUDE.md` rung 4).
- **That figure does not yield the column session's delta.** The 1st session
  measured 4925 passed on *its branch*, `7747a14e`, and the tree that became
  `origin/main` is that branch merged into a `main` which had moved under it.
  Two parents' additions do not sum (`tests/CLAUDE.md` § Quoting numbers), so
  the attributable figure here is the per-file one: `tests/test_gsas_prm.py`
  went 29 → 38 test functions.
- `tests/test_gsas_prm.py` 40 → 45 cases with the refusal test, all passing.
  `test_manual_api.py`, `test_docs_consistency.py` and `test_skill.py`: 101
  passed. `ruff check src tests examples` clean.
- No full selection. On a successful read the refusal converts nothing and
  reorders nothing, so no measured number can move.

*The review pass* — `/code-review high --fix`, run by this repair. It found
something in the merged code rather than in the repair. That is the case step 9
of the handover exists for.

Read what it is before relying on it. The diff under review was this branch's,
which is documentation, so the reader was opened as **context** and never as
reviewed scope. One defect surfaced that way. PR #332's code has had exactly one
systematic review and it is the column session's own (`2a96b536`); nothing here
re-reviewed it, and a second defect of the same kind would not have been found.

`read_gsas_prm` converts the file's numbers onto the schema by assignment, and
`Base` validates on assignment while `Parameter` carries a bounds validator. A
`.prm` stating a negative `GW` therefore raised pydantic's `ValidationError`
naming `Parameter`, with no file in it, which is the shape `io/CLAUDE.md`
§ Refusals forbids a reader. The conversion now sits in `_build_instrument`, and
a schema error at that boundary comes back as a `ValueError` naming the file and
quoting every value it converted. The same exposure ran through `LAM1`, `LAM2`,
`POLA`, `KRATIO`, `GU` and the two axial terms, so the test is parametrised over
five of them (`0efac867`).

Two smaller things came with it. The build moved above the diagnostics block.
The emission site's own comment already promised that, and the test now asserts
the caller's list is empty when a file is refused. And the manual
documented the two diagnostics in the wrong order. `GSAS_PRM_FIELD_DROPPED`
precedes `GSAS_PRM_GEOMETRY_ASSUMED`, checked on `11bm_gsas.prm`, and that error
predates the reorder.

One finding was declined as written. The patch's docstring and its test comment
both said a GSAS fit of a broad laboratory pattern lands `GW` negative
"routinely". Nothing in this session measured that. The docstring now states the
measurement that was made and says plainly that the frequency was not.

*Next*, in order, with what decides between them.

1. **The GSAS-II `.gpx` reader behind the restricted unpickler.** It is the last
   reader, and the writers task cannot be scoped until every reader's model
   exists. Its own first step is widening the corpus. That is measurement, and
   it can start before any unpickler is written.
2. **Origin-choice honesty** (#101), the cheap one. `normalize_space_group` is
   already drafted in the #98 branch and the task closes an issue.
3. The writers (#148), then the `#prm` integer evaluator for `.inp` `#if`
   guards.

One thing the WP file called owed is not owed. This repair checked `SKILL.md`
before repeating the claim, and line 41 already names the situation and routes
to `references/api.md` § In. It landed 2026-08-30 under WP-1308, before the
note calling it missing was written, and the "PowderLine recipe" the note
quotes is a manual page in the row's third column. The task text now says so,
with the byte headroom re-measured: `SKILL.md` has 1 049 B free of 33 000 and
`references/api.md` 3 204 B of 36 000, both tighter than the 09-13 figures they
replace.


### 2026-09-15 (2nd session) — `read_gsas_prm` by column, and the refusal whose reason had expired (reconstructed post hoc)

A lab `.prm` written for a copper tube states two wavelengths. rietx refused
every such file, and the reason it printed was that no file said how to weight
the second line against the first. The file did say. The reader could not find
the number because it read the record by splitting on spaces, and under that
reading the intensity ratio lands where the polarization is. Located by column
it is exactly the second emission line's weight, so a doublet now opens and
comes back with both lines.

Behind that sits the part worth carrying. A `.prm`'s `INS` records and a
`.EXP`'s `HST` records are the same GSAS records under different four-character
keys, and this package was parsing three of them two ways. The corpus hid it.
Every 11-BM file here leaves `IREF` and `IDAMP` blank, so six tokens happened to
land on the right meanings and the reader looked correct, while the one file
that writes `IDAMP` was refused for having seven. The grammar now has one home
and both readers call it.

*Reconstructed post hoc*, from `git log --stat` over the branch's four commits,
their bodies, and the state of the checklist. The session left no entry of its
own. Where the diff does not say why something was done, this entry says so
instead of supplying a reason.

*Done* — four commits on `wp1118-gsas-prm-columns`, merged as PR #332
(`3e759b54`).

- **The grammar** (`c4b20256`). `io/projects/gsas.py` grew
  `GsasIcons`/`read_icons`, `GsasPrcfHeader`/`read_prcf_header` and
  `split_records`, all public and all called by `instrument_profile.py`'s
  `.prm` reader a package away. The coefficient names come from
  `CW_PROFILE_COEFFICIENTS`, the table the `.EXP` reader was already using.
- **The docs** (`e2d2d6d2`). The reader's own docstring described six `ICONS`
  fields read by position and a doublet refused for want of a convention, and
  both had gone false. `docs/manual/using/files.md` gains the doublet and loses
  a sentence saying a GSAS `.EXP` has no reader, which the 1st session had
  already made untrue. The skill's `GSAS_PRM_FIELD_DROPPED` row names the
  fields the column layout identifies, and `references/api.md` now tells an
  agent not to add a Kα2 line after reading one. The addition is staged in the
  v1.4 record. Post-ship work goes there while no milestone is open.
- **The review pass** (`2a96b536`), over three blank fields the column read made
  reachable. A six-token split refused a record missing any field, so no field's
  absence had had an answer of its own. A blank `POLA` was the one that
  mattered. The `Instrument.debye_scherrer` constructor defaults its
  polarization to 0.99 and every real file in the corpus states 0.99, so falling
  back on the default would have put this package's number into an instrument a
  caller reads as the file's. It is refused by name. A blank
  `PRCF1` profile type reached the unrecognised-type refusal and printed `None`,
  and it now says the header states no type. Two diagnostic rows asserted `= 0`
  for fields they had not read, which is the defaulted-field lie one message
  over.
- **The claim** (`46611638`) carried the FAP-freedom decision the 1st session had
  left to the maintainer. The suite keeps its 20 free parameters and keeps
  asserting the difference against GSAS's 28.

*Measured* — the session's own numbers, in the same worktree and `.venv` as
the 1st session, `[dev]` only (no jax, no torch), python 3.12.12, darwin/arm64.

- The four real calibration files here read **bit-identically**: `11bm_gsas.prm`,
  `11bm_lab6_gsas.prm`, `11BM_LaB6_cBN_mg2044.prm` and `mg090.prm`, measured
  against `origin/main`'s module over the whole `model_dump`.
- `INST_XRY.PRM` is refused for its `GP` of 0.1, a stock GSAS placeholder, where
  before it was refused for a token count.
- `tests/test_gsas_prm.py` went 29 → 38 test functions, 12 added and 3 removed.
  The three that went asserted the split reading: the token-count refusal, the
  doublet refusal and the reserved-field refusal. The file collects 40 cases and
  all 40 pass on the merged tree, re-measured 2026-09-16 by the repair above.
- `src/rietx/io/CLAUDE.md`'s cap went 368 → 383, and the file landed at 381.

*Gotchas*

- **The `PRCF` continuation records stay a token read**, deliberately. GSAS
  prints coefficient labels inside the 15-column fields on some files, so
  `11BM_LaB6_cBN_mg2044.prm` is 61 characters where `4E15.6` is 60, and its
  second field reads `     GV -0.1260` by column. Sharpening the rest of the
  reader does not licence sharpening this.
- `tests/data/README.md` had `INST_XRY.PRM`'s `POLA` as 0.5. It is 0.7, and the
  0.5 beside it is `KRATIO`. That pair is the whole reason the file is worth
  keeping, since `FAP.EXP` states only `POLA` and the two are conventionally
  equal.
- The two rules this session put in `io/CLAUDE.md` are aimed at the next project
  reader. Staying outside the registry is about dispatch and never about
  parsing, so one vendor's several file kinds read a record through one
  function. And a refusal's reason can expire, so a parser getting sharper is a
  reason to audit its refusals too.

### 2026-09-15 (1st session) — the GSAS `.EXP` reader, and the protocol it turned out nobody had

Someone handed GSAS's own converged refinement can now open it with one call and
get back the model *and the refine flags* — which parameters that refinement was
free to move. That last part is the whole point, because a CIF carries the
converged coordinates and a raw file carries the pattern, and neither says what
was refined. This repo had been paying the cost itself: the fluorapatite
acceptance suite's cell, seven sites, wavelengths, held Caglioti terms and
excluded region were constants somebody read out of `FAP.EXP` by hand, and
`viz/compare.py` held a second copy of the same numbers. Both now read the file.

Reading the protocol instead of transcribing it immediately found something the
transcription had hidden: **GSAS refined the coordinates and this package's plan
does not**, so the suite whose docstring said "both codes refine the same
parameter set" was refining 20 parameters against GSAS's 28. That is now
asserted as a difference rather than implied as an agreement, and closing it is
measured and cheap — the decision is the maintainer's because it moves two
recorded acceptance numbers.

*Done* — seven commits, `wp1118-gsas-exp-reader`.

- **The reader** (`48c2d105`): `io/projects/gsas.py`, `rx.read_gsas_exp` and its
  `to_structure`. `GsasModel` carries phases, histograms and one entry per
  phase-and-histogram pair, which is where GSAS keeps the profile coefficients.
- **The registry member** (`1b528789`): `gsas_exp` in `PROJECT_FORMATS`, top-level
  exports, the `capabilities()` arm, a Part 1 section over the whole `GsasModel`
  tree, six `GSAS_EXP_*` skill rows, and an `ATTRIBUTION.md` row.
- **The acceptance rewire** (`e419cf4c`), the WP's own stated bar, plus
  `viz/compare.py`'s `fap` standard, which was the second transcription.
- **`FAP.EXP` ships** (`3138217d`) and **the sniff measures bytes** (`d5821955`);
  both are below.

*The three decisions, and what each rules out.*

1. **Every field is read by column, never by splitting on whitespace.** A
   fixed-format record whose optional numeric fields are blank collapses under
   `str.split()` into a shorter list whose entries then mean something else.
   `ICONS` is where it bites: the layout is `LAM1 LAM2 ZERO [IREF] [IDAMP] POLA
   IPOLA KRATIO`, so a file leaving `IREF`/`IDAMP` blank splits into six tokens
   that line up and one writing `IDAMP` splits into seven that do not. **What
   this rules out**: reading any further GSAS record positionally off a split.
2. **Profile coefficients are named per function type.** CW type 2's fourth is
   `LX` and type 3's fourth is `GP`, so one index-to-name map would mis-assign
   every width in the file. A type this build cannot name is **refused by name**
   rather than read positionally — the Bruker `.raw` v3 bar applied to a
   coefficient order. Type 4 is the refused one: the manual describes it only as
   "between 14 and 27 coefficients … `S400`, etc.", which enumerates nothing.
3. **The registry's `reports_at` gained a `"both"`.** It was a two-valued
   `Literal` because the two formats it shipped with each repair at one end. A
   `.EXP` repairs at both, so either single value would have dropped one channel
   **in silence** — the caller gets an empty list, which reads as "this file
   needed no repairs". **What this rules out**: a fourth format declaring one
   end and quietly having two, because the meta-test now partitions both ways.

*Measured* — this worktree's `.venv`, `[dev]` only (no jax, no torch, so the
cross-backend rows self-skip), python 3.12.12, darwin/arm64, nothing else
mid-suite either time (checked with `ps aux | grep`, not `pgrep`):

- Fast selection `-n auto --dist loadgroup -m "not slow"`: **4925 passed, 132
  skipped**, 2:23. The delta is **+35 passed, +0 skipped**, derived per file
  rather than by re-measuring `main` (`tests/CLAUDE.md` rung 4 says not to):
  24 from `test_projects_gsas.py`, 6 from `test_projects_registry.py` (2 dispatch
  rows, 2 new tests, and +1 each on the two meta-tests parametrised over
  `PROJECT_FORMATS`, which went from two members to three), 5 from
  `validation_matrix.py` (one new Claim × five parametrised families).
  `test_example_projects.py` gained a `LICENCES` entry and no test case, and
  the new acceptance row is `slow`-marked so it is outside this selection.
- Full selection, **once, on the final tree**: **5096 passed, 141 skipped**,
  23:28. Run because the change moves the inputs of a real-data acceptance row.
- `tests/test_acceptance_fap.py`, the WP's named acceptance: 3 passed.
- `ruff check src tests examples` clean.
- **The acceptance bar, stated as an identity rather than a tolerance.** The
  recovered protocol reproduces the file's own variable count: 21 structural
  (2 cell + 12 coordinate DOFs + 7 Biso) + 1 scale + 3 background + 3 profile =
  **28**, and `REFN GDNFT` says 28 in a record the reader never consults. The
  flags are spread over eleven records, so no single-field misreading survives
  that row.
- **The measured answer is unmoved.** Over the seven quantities the suite
  reports, the largest relative change is **5.3e-10** (`lor_size`), with Rwp at
  3.4e-14 and the cell at 2.6e-13 — solver termination noise from starting at
  the file's 9.371724 and 0.0335183 rather than the rounded 9.3717 and 0.0335.
  The Caglioti terms did not move at all: `1e-2**2 == 1e-4` exactly in IEEE754,
  so the centidegree conversion returns the same doubles the constants were.

*The review pass found ten things and the first of them was the bug this
reader exists to prevent.* `_continuation` appended only the values `_num` could
parse, so one unreadable coefficient field **compacted the list and renamed
every later coefficient**. Fortran writes a three-digit exponent with no `E`
(`0.200000-100`), which Python will not parse. Reproduced against the pre-fix
code, a six-coefficient function-2 block came back `GU=2.0, GV=5.0,
GW=3.35183, LX=2.48803, LY=0.0` — five plausible numbers, each under the wrong
name, nothing raised. Naming coefficients per function type cannot help once the
*values* have shifted under the names, so the careful part of this reader was
guarding one end of a hazard that came in at the other. Two siblings of the same
shape are now refusals too: a header declaring more coefficients than its records
carry, and a blank numeric field reaching a `float`-annotated model field as
`None`. The rest were smaller — `EXPR HTYP<n>` record numbers ignored (a file
with more than twelve histograms overwrote histogram 1 with record 2's type), the
HAP and histogram gates disagreeing about single-crystal data because `SXC`'s
third letter is `C`, `str.splitlines()` breaking on `\x85` where the
byte-measuring sniff does not, gemmi's space-group error escaping unwrapped, and
two stale docstrings plus `io/CLAUDE.md`'s `reports_at` bullet. Nothing was
declined; nine tests came with them.

*In flight*: nothing. The branch is one session's work and complete.

*Gotchas*:

- **The manual contradicts itself twice, and both would have shipped a plausible
  wrong number rather than an error.** The CW function 2 paragraph lists its
  eighteen coefficients twice, as physics symbols and as GSAS names, and the two
  are **transposed at positions 8 and 9**; GSAS's own EXPEDT listing prints
  `#8(shft)` and this file's converged sample displacement sits at index 8, and
  function 3's two tuples agree, which is what shows it to be a slip. And
  `CELVOL` is `2F15.3` in every file here against a printed `2F10.3`, which at
  the printed width reads 523.755 as **52.0**. Both are in the module docstring
  and asserted by test. `RPOWD` also carries undocumented fields past its
  declared `2F10.4`; those are **not** read, and the observation count comes
  from `REFN STATS`, which the manual does declare.
- **Polarization and a Kα2/Kα1 ratio are both conventionally 0.5, and they sit
  in adjacent fields on one record.** `FAP.EXP` states POLA and leaves KRATIO
  blank; the old test comment attributed that 0.5 to the ratio. What fixed the
  order is `INST_XRY.PRM` beside it, which states POLA 0.7 *and* KRATIO 0.5 in
  the same slots. A reader that took the wrong field would agree with the right
  one on this file and disagree on the next.
- **Adding a file to a `Standard` can remove an example project.** WP-1204's
  sentence is "adding a file adds an example", and `Standard.available` reads it
  backwards too: making the `fap` standard read `FAP.EXP` put that file in
  `Standard.files`, which is not in the wheel, so `fap` silently stopped being an
  example and **five tests went red in three suites that have nothing to do with
  this reader** — both GUI example-server rows, two example rows, a peak-picking
  panel, and the manual's indexing chapter, whose python block calls
  `build_example("fap", …)`. Shipping the file is the same licence answer
  `FAP.XRA` already has.
- **The head decode drops bytes, so the sniff measures bytes.** `head()` decodes
  UTF-8 with `errors="ignore"`, and a `.EXP` is a Latin-1 byte format whose
  `DESCR` title is whatever the experimenter typed. One accented character
  shortens that record to 79 characters in the decoded text while it is still 80
  bytes on disk, and the width half of the sniff then rejects the whole file.
  Found by reading the shared decoder, not by a failing file; the guard was
  checked the way `tests/CLAUDE.md` asks, with the byte version passing and the
  text version it replaced failing on the same fixture.
- **GSAS's `X` flag means "refine as permitted by symmetry".** Carried onto
  `x`/`y`/`z` directly it makes `ParameterTable` refuse the whole import of a
  file GSAS refined happily, because fluorapatite's F4 sits on a zero-freedom
  special position with its flag set. It goes through the site-symmetry basis
  GSAS was speaking about instead.
- **An anisotropic site reads but refuses to build.** The six `UIJ` values are on
  the model; which off-diagonal convention they follow is settled by no file
  here, and a wrong factor of two is a silently wrong Debye-Waller factor at high
  Q. Same refusal `fullprof.to_structure` makes about a `β` block, and it lifts
  the same way — with a corroborating file.
- **The `.pcr` species normaliser is imported from `fullprof`, which is the third
  caller of it.** It is not a format fact and its own docstring says it exists to
  give every project reader one spelling, so the import is deliberate rather than
  a shortcut; a shared home for it is the obvious tidy-up and was left alone to
  keep this diff on the new reader.

*Next*, in order:

1. **Decide whether this suite adopts GSAS's coordinate freedom** — the one
   question this work raised and did not answer. Measured 2026-09-15: adding a
   coordinate stage takes Rwp 0.096966 → 0.096677, moves the cell by 0.1 ppm,
   costs no wall clock and still converges. So it is nearly free and changes no
   conclusion, but it moves two recorded acceptance numbers (the headline Rwp,
   and the "20 → 18 free parameters" table in
   `test_tying_the_similar_atoms_bisos_buys_precision`), which is why it is a
   deliberate change rather than something to slip in.
2. **`read_gsas_prm` reads the same `ICONS` record by whitespace split.** It is
   correct on its corpus only because those files leave `IREF` and `IDAMP` blank,
   so the six tokens happen to line up; it **refuses `INST_XRY.PRM`**, a file in
   this repo, for having seven. The failure is safe rather than silent, which is
   good design, but the two readers now read one record two ways and that is the
   thing this codebase most dislikes. Reading it by column would fix the class.
   It would not by itself make that file readable — the reader also refuses a
   doublet, and a `.EXP` is what could now establish the intensity-weight
   convention it says no file gives it.
3. **The `STR(...)` decision** — issue #107, still offered by its filer, and 1119
   settled that it needs no expression language.

The `.gpx` reader (#234), the writers (#148) and the `#if` evaluator are all
larger and none is blocked, so they wait on someone choosing them.

### 2026-09-13 — the registry, and the question it had to answer first

Someone handed another program's refinement file can now open it with one call.
`rx.read_project_model("whatever.inp")` works out from the file's contents which
program wrote it, reads it, and hands back what the file said plus a
`.to_structure()` carrying the file's own refine flags. Before today the two
readers that could do this existed but were reachable only by importing them by
name, and `rx.capabilities()` did not mention them, so nothing could ask what
this build opens. The part that needed deciding was not the plumbing: it was what
the registry is *for*. Four readers in this package open a foreign file, they do
not answer the same question, and forcing them into one shape would have meant a
model with a blank where a file simply had nothing to say — which reads as an
answer. The decision taken is that the registry's unit is a **refinement**, and
two of the four stay outside it with the reason written down rather than left to
be inferred.

*Done* — six commits, `wp1118-model-format-registry`.

- **The mailbox pruned first** (`3a7f57a7`). Eight `### Inherited` entries folded
  into Context, Seams and Tasks and the section deleted. Three had gone stale in
  the ten days since the file was last edited, and the worst of them was stale in
  the reassuring direction: WP-1308, PR #98 and WP-1330 all warn that `SKILL.md`
  has 27, 32 or 36 bytes of headroom and that a routing row must be bought with a
  cut. Measured today it has **1 597 B** free, because WP-1103 and #284 cut the
  body after those notes were written. `references/api.md` § In had likewise
  stopped being false — it already named both readers. The third was an omission
  rather than a rot: `rx.read_gsas_prm` (PR #248) had landed as a *third reader
  kind* and the registry task did not carry it.
- **The registry** (`5ba04e58`): `io/projects/registry.py` with `ProjectFormat`,
  `ProjectModel`, an ordered `PROJECT_FORMATS`, `identify_project_format` and
  `read_project_model`; top-level exports for all of it plus `rx.read_topas_inp`
  and `rx.read_fullprof_pcr`; a `capabilities().project_formats` arm with the
  membership meta-test `reader_formats` is held to; `io/CLAUDE.md` § Project
  readers +3 rules (cap 350 → 368, argued); a Part 1 chapter; and the skill's
  routing row and § In.
- **The read's reports made durable** (`5e85b7d5`), found reviewing the commit
  before it — below.
- Two prose corrections and an encoding fix.

*The three decisions, and what each rules out.*

1. **The unit is a refinement, not a foreign file.** `read_gsas_prm` carries a
   machine and no model at all — no phases, no sites, no fitted numbers — so it
   stays beside `load_instrument_profile`, which is the argument its own merge
   made and the organising question the 09-10 entry recorded as raised and
   unanswered. `read_recipe` is a refinement but resolves to something ready to
   fit and is a build-wide feature. A pattern is the other registry's. Admitting
   any of them would empty every field this registry declares about a model, on
   one member. **What this rules out**: a future reader is placed by asking "does
   this file state a refinement" before it is written, not after it has a home.
2. **The answer is the format's own model, tagged.** `ProjectModel` names the
   format and hands on `TopasModel`/`FullProfModel` untouched. A shared shape
   would need an optional field wherever a format is silent, and a caller could
   not tell "this file carried none" from "the reader found none" — WP-1076 one
   registry over. What each format carries beyond a structure is declared in
   words (`ProjectFormat.carries`) so a client asks instead of reading `None` and
   guessing, and the conversion keywords pass through rather than being flattened
   into one vocabulary, since two formats' options sharing a name would not share
   a meaning.
3. **Dispatch is on content, never the suffix.** `.inp` is written by unrelated
   programs — WP-1407's rule one rank up, that a file extension does not name a
   format here. FullProf goes first because `COMM` is a line the format
   *requires*; TOPAS's evidence is a line-start keyword in a 64 kB head, the
   weaker test, and the order is that difference. The `.inp` sniff runs the head
   through the reader's **own** `strip_comments`, so a commented-out `xdd` is not
   a statement and the sniff is not a second grammar to keep in step.

*Measured* — worktree `.venv`, `[dev]` only (no jax, no torch, so the
cross-backend rows self-skip), python 3.12.12, darwin/arm64, `pgrep` clean both
times:

- Fast selection `-n auto --dist loadgroup -m "not slow"`: **4632 passed, 132
  skipped**, ~2:05-2:08 (three runs, 124.7 s / 127.6 s / 128.3 s; the first is
  the final tree). The delta is **+24 passed, +0 skipped** —
  `tests/test_projects_registry.py` collects 24 and every one passes; no other
  file's collection moved, `test_capabilities.py`'s edit being one assertion
  inside an existing test.
- `tests/test_acceptance_fap.py`, the WP's named acceptance: 2 passed.
- `ruff check src tests examples` clean; `sphinx -W` clean.
- **The full suite did not run**, and deliberately: `tests/CLAUDE.md`'s rung 3
  fires only when a change can move a measured number, and nothing here touches
  the forward model, the solver or the statistics. The FAP acceptance was run
  anyway because this WP names it.
- **Import cost, since `import rietx` now pulls in two ~2 500-line parsers**:
  `rietx.io.projects` is **13.1 ms cumulative** of a 535–663 ms total (three
  runs), about 2 %. `scipy.signal`, reached through `rietx.background`, is 274 ms
  of the same total. Not worth a lazy-import mechanism the package does not have
  for any other export; recorded so the next reader added knows what it costs.

*In flight*: nothing. The branch is one session's work and complete.

*Gotchas*:

- **The asymmetry in `reports_at` was very nearly a trap, and the review caught
  it two screens from a test arguing against it.** A `.inp` reports its repairs
  while parsing and a `.pcr` while codewords become a `Structure`, so the first
  design routed the caller's list on that flag — and silently dropped it when a
  caller passed one to `to_structure` on a `.inp`. They got an empty list back,
  which reads as "this file needed no repairs". The fix is `Recipe`'s: the read
  reports into a list of the front door's own, lands on
  `ProjectModel.diagnostics` whether or not anyone asked, and a caller's list is
  **extended** from it rather than handed to the reader, so it stays the caller's
  own object. The general shape to watch for: a per-format flag that routes a
  caller's channel is a place where being wrong is silent.
- **Two declared names have no writer among the members, and the review was
  right to say so out loud.** `ProjectFormat.refuses` is `None` on both, because
  neither is a recognise-in-order-to-decline format — so the `if f.refuses is
  None` filter it exists for was unreachable. `ProjectModel.diagnostics` is
  always `()` for `fullprof_pcr`, whose read has no channel at all, so a
  format-agnostic caller writing `if model.diagnostics:` is silent on every
  `.pcr` however much it repaired. Neither is WP-1076's defaulted `False` — both
  are the honest empty state — but both were claims resting on a docstring. Now:
  the docstring says which formats an empty tuple means anything about, and the
  filter is exercised against a stub member that sets `refuses`, rather than
  asserted from the table and believed.
- **`.inp` and `.pcr` fixtures cannot be vendored, so the `.pcr` ones are
  `test_projects_fullprof`'s builders imported.** A second fixture writer for one
  format is a second description of its layout, and the two would drift on
  exactly the 19-field control line that format refuses a file over — which it
  did, on the first run, against a hand-written 18-field one.
- **The WP file read at session start was three days stale.** `/wp-start` reads
  the WP file in step 2 and enters the worktree in step 3, so the read comes from
  the main checkout — which was six merges behind `origin/main`, and missing the
  09-10 entry recording PR #248. Reconciled by re-reading from the worktree. The
  cheap habit: after `EnterWorktree`, re-read the WP file.
- **The review pass found six things, four of which it fixed, and the two it
  left were both worth acting on.** The one that mattered: `_TOPAS_LINE`
  *restated* the grammar's opener tuple instead of reading it, so an opener
  added to `topas._BLOCK_OPENERS` would keep parsing through `read_topas_inp`
  while `read_project_model` answered "not a refinement file this build can
  read" — drift in one direction and in silence. The alternation is now built
  from that tuple (verified byte-identical to the literal it replaced), with
  `STR` the one member taken out and spelled `STR(`. Also fixed: the binary
  hint on the refusal, matching `identify_format`; the `diagnostics` docstring;
  and a manual sentence claiming the sniff decides "without reading" a file it
  reads 64 kB of. Of the two left to me, the partial-diagnostics one turned out
  to be a docstring claiming a parity it did not keep — `read_pattern` hands its
  list straight down, so a read that repairs and then refuses keeps what it
  repaired, and this door copied only on success. Fixed with a `finally`, and
  **no reader in this build can reach the case today** (every TOPAS diagnostic is
  appended after its last raise, and FullProf reports at build), so it is tested
  through a stub member at the door where the promise lives.
- **Two documentation gates fired on this work and both were right.**
  `test_manual_api.py` put 90 public names in no bucket, which is what made
  `rietx.io.projects` a declared-provisional module (the WP-1078 mechanism —
  honest here, since the registry landed with two formats and three queued) and
  bought the Part 1 chapter. `test_skill.py` demanded the four new verbs in
  `make_api_index.py`'s `SECTIONS`. Neither would have fired had the readers
  stayed off the top level, which is the argument for putting them there.

*Next*, in order:

1. **The GSAS `.EXP` reader** — issue #103, whose filer volunteered for it once
   the registry shape landed, and it has. They bring two spec findings for its
   docstring (GSAS-II's `Rvals['GOF']` is reduced χ² rather than its root;
   instrument parameters are `[default, current, refine_flag]` triples, current
   at index 1). It is the task with a fixture already in the repo — `FAP.EXP` is
   GSAS's converged fluorapatite fit — so it is also what lets
   `test_acceptance_fap.py` take its protocol from a reader instead of from
   transcribed constants, which is this WP's stated acceptance.
2. **The `STR(...)` decision** — issue #107, whose filer offered either fix once
   told which. 1119 settled that it needs no expression language, so it is a
   `.inp` grammar question living entirely in `io/projects/topas.py`.
3. **The `#if` evaluator**, newly a task line: three of four workshop `.inp`s
   refuse at their first `#if`, and those are the multi-pattern reel files
   WP-1110's agent round named as the hardest part of the work.

The writers (#148) and the `.gpx` reader (#234, its reporter's offer standing)
are both larger and neither is blocked, so they wait on someone choosing them
rather than on anything here.

### 2026-09-10 — the `.PRM` half of the GSAS task landed from outside (PR #248)

Merged in a `/pr-review all` pass, not a WP session; this entry exists because
an outside contributor has no reason to prefix a commit `WP-1118:` or to edit
this file, so nothing would otherwise have recorded it. PR #248
(`ff69ec34`) adds `read_gsas_prm` in `src/rietx/io/instrument_profile.py`,
a new top-level export, `docs/manual/using/files.md` prose, two diagnostic codes
with their skill rows, and 609 lines of tests.

**What it makes possible.** An `INST_XRY.PRM`-shaped GSAS-I instrument-parameter
file now becomes an `Instrument` without transcription. That is the first half of
the `.EXP`/`.PRM` task above and the half that unblocks the *protocol* argument:
`tests/data/INST_XRY.PRM` is in the repo already, so the FAP acceptance suite's
wavelength and profile constants can start coming from the reader rather than
from constants typed out of the file.

**What it deliberately does not do.** No `.EXP` reader — the converged fit,
the vary set and the excluded regions are still transcribed, so the task line
stays unticked. It is not wired into the model-format registry (which does not
exist yet, and is this WP's first unticked item), and it is neither a
`PATTERN_FORMATS` entry nor an `io/projects/` project reader: it is a third
reader kind with no registry of its own.

**What the review established, and the gotchas.**

- The io rulebook's hardest clauses are met and I verified each: every refusal
  names the file rather than leaking a `float()` exception; the unit is measured
  three independent ways against the format's own reference output rather than
  taken from LAUR 86-748's prose; and the `ZERO` field, which the format states
  two ways, is **refused rather than chosen** — the same disposition a CIF whose
  angle contradicts its symbol gets. Drift is refused (`GP`, the reserved
  coefficients, `ALAM2`, `ZERO`, the reserved `ICONS` field), identity-valued
  drops are reported (`GSAS_PRM_FIELD_DROPPED`), and everything frozen carries
  `vary=False`.
- **An organising question this raises and does not answer**: `io/CLAUDE.md`'s
  "one module per format" is scoped by its own first line to the *pattern*
  readers, so it does not govern this reader — but the reason behind it does,
  and `instrument_profile.py` now carries two formats' fences (the native JSON
  `FORMAT_KEY`/`FORMAT_VERSION` and GSAS-I's spec citation and refusal tables).
  Whether the third reader kind gets its own module rule, or its own registry
  alongside `PATTERN_FORMATS` and `io/projects/`, is open and is the thing the
  registry item above should settle. Raised with the maintainer at merge; no
  decision taken.
- Measured on the merged tree, bench venv `[dev,jax]`, macOS arm64, four cores,
  alone: `tests/test_gsas_prm.py` + `test_acceptance_wavelength.py` +
  `test_skill.py` + `test_manual_api.py` — 91 passed, ~24 s; the fast selection
  4353 passed / 78 skipped, ~2.5 min; ruff clean. The full `-m slow` suite ran
  once on a combined tree carrying this and seven other PRs.

### 2026-09-03 — the `.gpx` fence lifted, behind a restricted unpickler

The maintainer decided issue #234: a GSAS-II `.gpx` reader is in scope, built
on a `pickle.Unpickler` whose `find_class` admits an allow-list and refuses
every other name. The Non-goals bullet that fenced it out for a reason
measured false is rewritten, the task is on the list with the measured
allow-list and the corpus-widening caveat, and the reporter's offer to
implement it stands. Nothing else in this WP moved. Next action: the
contributor's PR, or the next session on this WP, builds the reader against
the widened corpus.

### 2026-09-03 — the FullProf `.pcr` reader landed (PR #111)

A FullProf `.pcr` control file now opens the same way a TOPAS `.inp` does.
`rietx.io.projects.read_fullprof_pcr` returns what the file states — phases,
cell, sites, displacement parameters, the magnetic blocks, the run's own
agreement figures — and `projects.fullprof.to_structure` builds a `Structure`
from it carrying the **file's own refine flags**, decoded out of FullProf's
`10·n + multiplier` codewords. The codeword is the whole point of the format for
this WP's purpose: it is where a `.pcr` records both *which* parameters were
refined and *which of them moved together*, and neither is recoverable from a
CIF plus a pattern. Where a tie is one rietx already carries — a single atom's
coordinates following its own site-symmetry DOF — it is reproduced; where it is
not, the reader says so by name rather than dropping it, and says whether the
reader could restore it with one `Refinement.tie_equal` call. The other format
is unmoved: `.EXP`/`.PRM` still has no reader, and there is still no writer in
any direction.

*Reviewed, not written, in this session.* PR #111 ran six review rounds on the
`/pr-review` bench between 2026-08-26 and 2026-09-03 (the PR opened 2026-08-24); this entry is written at
the merge, from those rounds and from the merged tree, and is the handover the
step-9 clause added by the 2026-09-02 repair session says a contributor's
`WP-NNNN:` commits owe.

*Done* — all of it PR #111 (`mustachefeeling/fullprof-pcr-reader`, head `a99ce2ef`), merged
2026-09-03 as `b717cc98`, +4462/−35 across 14 files:

- `src/rietx/io/projects/fullprof.py` (2326 lines) — the reader. The package
  `__init__` gains `read_fullprof_pcr` and `FullProfPcrError` and nothing else;
  `to_structure` stays module-level, which is the shape #98 chose so the two
  formats' conversions cannot shadow each other through the package export.
- The answer's shape, matching the TOPAS reader's: `FullProfModel` is *what the
  file states*, `to_structure(model, *, nuclear_only=False,
  drop_parameter_ties=False, diagnostics=None)` is the conversion. `Biso` is
  FullProf's B and rietx's `biso` is also B — no 8π² conversion — and
  `species_raw` sits beside `species` on every `FullProfAtom`, so the spelling
  repair is checkable against the file structurally, not only through a
  diagnostic.
- **53 refusals, each naming file and line** through `FullProfPcrError`
  (a `ValueError`, so `io/CLAUDE.md`'s "raise naming the file, never the
  parser's exception" holds). The reader handles the single-pattern
  constant-wavelength layout completely and refuses the rest by name.
- Four diagnostics, each with a row in all three synced skill copies:
  `FULLPROF_SPECIES_NORMALISED`, `FULLPROF_ORIGIN_CHOICE`,
  `FULLPROF_OCCUPANCY_UNCHECKED`, `FULLPROF_TIE_DROPPED`. The skill's
  `references/diagnostics.md` was over its own cap on `main` (35 914 of 36 000
  B); this PR splits the project-reader codes out into
  `references/diagnostics-projects.md`, taking that file to 32 125 B and the new
  one to 10 273 B. **That split is what buys `diagnostics.md` its next few
  years, and it is an argument for landing this PR that has nothing to do with
  FullProf.**
- `tests/test_projects_fullprof.py` (1934 lines, 85 tests) — every fixture
  synthesized inline, because no real `.pcr` may be vendored, and every line in
  them quoted in a comment from a named archive file and line.
- `tests/data/README.md` — the six-file corpus section, which is the only place
  the real-file evidence is checkable, plus **two limits recorded rather than
  smoothed over**: the corpus contains no cross-atom tie at all, and its cell
  ties are tetragonal and cubic only. Both are why the corresponding rules are
  derived from symmetry and from what a restoring call can express, rather than
  from what six files happen to contain.
- `ATTRIBUTION.md` — one row. FullProf is closed and no FullProf source was
  consulted; the format's facts come from six real archive files plus
  Rodríguez-Carvajal's manual and the ILL school notes already cited. No `.pcr`
  is vendored and nothing enters `src/rietx/data/`, so the wheel's licence fence
  is not reached.

*Measured* (merged tree `a99ce2ef` onto `origin/main` `b2ab4950`, a
fast-forward, so CI measured the same tree; `/pr-review` bench `.venv`
`[dev,jax]`, python 3.12.12, darwin/arm64, nothing else running): the **full
suite**, `-n auto --dist loadgroup` with no marker, is **4452 passed, 80
skipped** in 35m21s. `ruff check src tests examples` clean. The fast selection
was not run separately and no collection delta is quoted here — the full run
covers it, and round six's `+139` was measured against a `main` that has since
moved.

The full suite was run **once, on the final tree**, and that tree is the one
that merged: after the contributor's force-push (below) the merged commit's
tree object was compared against the tested one and they are the same object,
`b2dc6a8f22ee59ab1ff2bb89535c9a8f4d5db79f`, so no re-run was owed.

*In flight*: nothing of this WP. PR #111 was the last open contributor PR
against it.

*Gotchas*:

- **A coordinate tie is restored through the DOF path, not the column path.**
  `atom_tie_recoverability` says whether `FULLPROF_TIE_DROPPED`'s group can be
  re-declared, and the call it needs is `tie_equal` on
  `phases.i.atoms.j.dof.k` for a coordinate group but on the column path
  (`.biso`, `.occ`) for a Biso or Occ group — because a coordinate column
  already follows its own dof by site symmetry, and root `CLAUDE.md`'s
  "symmetry outranks a user tie" makes `tie_equal` on `.z` **refuse**. The
  diagnostic's message named the column spelling on both arms until round five;
  it now names the DOF spelling where that is what works, and the skill row
  carries the raising example so a driving agent meets the refusal before it
  hits it.
- **The split is derived from what a restoring call can express, never from the
  corpus.** All six archive files contain single-atom ties only, so the corpus
  reaches neither arm of the report-versus-refuse decision. A rule inferred
  from it would have been an accident. The same reasoning made
  `cell_parameter_ties` ask `crystallography.symmetry.cell_constraints` rather
  than trust incidence: the archive's cell ties are tetragonal and cubic only,
  where the space group masks the defect — exactly the limit
  `TOPAS_CELL_COUPLING_DROPPED` hit the sibling reader over, for the same
  reason.
- **A `.pcr`'s own comments lie, in two ways, and the parser trusts neither.**
  A column's `!` header text changes with `Jbt` (`Ang` and `Mom` share a
  column), so header text is discarded before the walk and the reader keys on
  position; and a phase's inline `!Phase No.` can disagree with block order, so
  the reader counts blocks. A parser keyed on the header breaks on exactly the
  magnetic phase.
- **`ATZ` and `Pr3` are quantities, not counts.** Reading the phase-control
  line with `cur.ints()` throughout would refuse every real file — hence
  `_PHASE_INTEGER_FIELDS` naming which columns are integers.
- **A negative `Biso` is a real FullProf outcome, and it is refused rather than
  repaired.** One archive file carries O1 at −0.67266 Å². rietx's zero bound
  cannot clamp it without changing every high-Q intensity, so the file is
  refused by name; this is the `io/` rule that a reader may repair only where
  it can say what it did, applied where the repair would not be sayable.
- **FullProf's `Occ` is degenerate with the phase scale**, so only the *ratio*
  between sites is recoverable and a phase whose ratios disagree is refused.
  That ratio test does double duty: it is also what *verifies* the origin-choice
  preference for a bare symbol (`F D -3 M` → `F d -3 m:2`) rather than trusting
  it.
- **A magnetic phase reads but does not build.** Present alongside nuclear
  phases, `to_structure` refuses rather than returning the nuclear subset
  silently.
- **The skill's caps are now a live constraint, and a merge can cross one that
  neither branch crossed.** `references/diagnostics.md` sat at 35 914 of 36 000
  B on `main` before this PR's split. Two additions can each be under a cap
  while their merge is over it, and branch protection here is `strict: false`,
  so nothing but a review on the merged tree ever measures that — seen for real
  on #233 the same week.

- **A contributor's commit identity is a merge gate, and nothing checks it.**
  `58efff0a` on this branch ("merge main") was authored `m <m@m>` from a
  misconfigured local `user.email`. GitHub attributes a commit to whoever owns
  the address, `m@m` is verified on a **real and unrelated account**, and that
  account was therefore listed among this PR's participants. It was caught at
  review and fixed by a rebase before the merge; `main` had never carried the
  address, and after the force-push the branch is 11 commits under one
  identity. Two things make this worth a rule rather than an anecdote. It is
  **invisible to every check we run** — CI, `ruff`, the suite and branch
  protection are all indifferent to authorship, and the GitHub UI shows the
  contributor's avatar on the PR while the commit underneath carries someone
  else. And it is **cheap before the merge and expensive after**: removing it
  from `main` would mean rewriting merged history behind the two protection
  toggles only the maintainer can operate. So a `/pr-review` pass over an
  outside PR should read `.commit.author.email` and the **resolved**
  `.author.login` per commit, not the PR's author field. A second failure mode
  sits beside it and reads the same way in the UI: an address that is not
  verified on the contributor's account resolves to **nobody**, so the work
  lands on `main` credited to no one — four commits across #111 and #233 were
  in that state, and the fix there is verifying the email, not rewriting
  anything.
- **`SKILL.md` came out of this with 11 bytes of headroom** — 32 989 B against
  `test_skill.py`'s 33 000 cap, because #242 landed in the body while this
  branch was in flight. This PR's `diagnostics.md` split fixes the *references*
  side and buys that file years; the body itself now has room for nothing, and
  the next addition to it needs the same treatment first.

*Next*: unchanged — the **registry-shape task** is still the single gate on the
`.EXP`/`.PRM` offer (#103), the `STR(...)` decision (#107) and
[1314](1314-mfile-reader.md)'s Jana reader, and still settles whether
`read_topas_inp` and `read_fullprof_pcr` become top-level exports with a
`capabilities()` arm. Two of the three readers now exist, which makes the
registry's shape a question with two real instances to answer it rather than
one.

### 2026-09-01 (2nd session) — the TOPAS `.inp` reader landed (PR #98, reconstructed post hoc)

A TOPAS `.inp` no longer has to be transcribed by hand.
`rietx.io.projects.read_topas_inp` opens one and returns what the file states —
phases, cells, sites, ADPs, the emission profile, the run's own Rwp/GoF — and
`projects.topas.to_structure` builds a `Structure` from it that carries the
**file's own refine flags**, which is the half nobody can reconstruct from a CIF
plus a pattern. What the reader will not do is guess: every construct of the
format declares a stance in a table, so a keyword nobody wrote a branch for
fails a test rather than vanishing, and a file whose phases cannot be honoured
without it is refused by name instead of returned half-built. That table is what
nine review rounds bought — each round found one more construct being dropped in
silence, which is a property of the reader's structure and not of the nine
constructs, so the tenth is now a row rather than a round. The other two formats
are unmoved: `.EXP`/`.PRM` and `.pcr` still have no merged reader, and there is
still no writer in any direction.

*Reconstructed post hoc.* Written from `git log --stat` over PR #98's 46 commits
(`a3268cd1`..`03179f2a`, merged `0576726f`) and the state of the tree they left.
The review ran on the `/pr-review` bench, which writes no handover entry, so
what follows is what the commits show; where the diff does not say why, this
entry does not invent a reason.

*Done* — all of it PR #98 (`mustachefeeling/topas-inp-reader`), merged
2026-09-01, +6078/−1 across 11 files:

- `src/rietx/io/projects/` — a package for readers of someone else's *refinement
  input*, beside `io/formats/`, one module per format. The package `__init__`
  exports `read_topas_inp` and `TopasInpError` only, out of `topas.py`'s 2668
  lines; `to_structure` stays module-level so #111's FullProf `to_structure`
  has nothing to shadow through the package export.
- The answer's shape, for this format: `TopasModel` is *what the file states*
  and seeds nothing (a site with no `beq` carries `None`, not 0.5), and
  `to_structure(model, *, cell_limits=True, aniso=False, dataset=None)` is the
  conversion, applying `TopasPhase.vary` / `TopasSite.vary` onto each
  `rx.Parameter(vary=…)`. `vary` is a **tri-state**: a key absent means the file
  said nothing, which is not "held".
- `coverage.py` (360 lines) — one declared stance per construct, `READ` /
  `IGNORED` / `REPORTED` / `REFUSED` (6 / 3 / 9 / 5, 23 `FEATURES` rows over a
  178-keyword `PHASE_SCOPE`), partitioned by test against the reference's own
  §5.1 phase tree, so a keyword with no stance fails and a stance naming a
  keyword outside the scope fails too.
- Six diagnostics, each with a row in all three synced skill copies:
  `TOPAS_SPECIES_NORMALISED`, `TOPAS_ORIGIN_TRANSLATED`, `TOPAS_BLOCK_SKIPPED`,
  `TOPAS_CELL_COUPLING_DROPPED`, `TOPAS_FEATURES_NOT_IMPORTED`,
  `TOPAS_FEATURE_REFUSED`.
- `src/rietx/io/CLAUDE.md` § Project readers (+29) — two standing rules: derive
  the obligations from the specification and use files only to corroborate (three
  of the six grammar corrections here are invisible to any archive sweep — a
  parameter's *name* is its refine flag, a block comment *nests*, a conditional
  is a token not a line); and a project reader **refuses** where a pattern
  reader would repair, four classes by name, with `to_structure(model,
  dataset=N)` following `read_pattern`'s `scan=` rather than concatenating.
- `ATTRIBUTION.md` — the `.inp` row, citing the Technical Reference section by
  section and each supported cell macro on its own line, recording that the
  606-file private archive is corroboration only and is not redistributable.
  `tests/data/README.md` (+54) holds the archive facts against the file each was
  read off.
- `tests/test_projects_topas.py` — 159 tests, every fixture synthesized inline
  because no `.inp` may be vendored.

*Measured* (this handover session, macOS darwin 25.5.0, worktree `.venv`
python 3.12, `[dev]` extras — no jax/torch, so the cross-backend rows self-skip):
`-m "not slow"` is **3919 passed, 122 skipped**, in the 2-3 min band this
selection runs in on this machine (two runs, 125 s and 156 s). That was
measured on `origin/main` itself — the branch is that commit plus
documentation, and this handover adds no test — so it is the merged tree's
count. The full selection was
not run: nothing here can move an acceptance number, and the reader carries no
physics.

*In flight*: PR #111 — the FullProf `.pcr` reader, same contributor — is open
with 9 commits, head `71fb7094`. Its review has already produced
`FULLPROF_TIE_DROPPED` and the decision to analyse a cell codeword tie against
symmetry rather than against corpus incidence. **Nothing of it is merged**, and
its commits are reachable only through the PR ref, not through any local branch.

*Gotchas*:

- **`STR(...)` is refused by name, not supported** (#107). The line-based
  split still cannot see a phase opened with the macro form, but PR #98 took
  the minimum honest fix with it (`_STR_MACRO`, `topas.py:1866`; the test
  names seven affected archive files — `rigidb`, `split_fum`, `SPODI`, `D20`
  and three `AT027-23_*`): such a file raises `TopasInpError` counting the
  phases it states, rather than returning zero. Those files therefore parse
  not at all, so PR #98's incidence figures are still **floors**, and what is
  parked at the registry-shape task is only *whether* the macro is read — a
  special case or a general macro pass. The Context section above was written
  before this merge and said the file still got the wrong diagnosis; this
  handover corrected it in place.
- **The skill now contradicts the build.** `references/api.md` § In still reads
  "a TOPAS `.inp` … has none, so those are still transcribed by hand", and
  `SKILL.md`'s routing row for *you were handed another program's input file*
  still names only a PowderLine recipe. Both are false as of this merge. The fix
  is WP-1308's Inherited note above, still unspent: SKILL.md measures 31 968 B
  against its 32 000 B cap — 32 B of headroom, not the 27 B that note quotes —
  so widening the row costs bytes bought elsewhere, and three copies
  (`docs/skill/`, `.agents/skills/`, `.claude/skills/`) must stay in sync.
- **No registry and no `capabilities()` arm.** There is no `PROJECT_FORMATS`
  beside `PATTERN_FORMATS`; the reader is found by importing it. The meta-test
  that fails on a registry member missing from its arm therefore has nothing to
  check yet.
- `read_topas_inp` is not a top-level `rx.` export, so `tests/test_skill.py`'s
  public-verb gate never fired for it and `docs/skill/make_api_index.py` carries
  no row. Whether it *should* be top-level is part of the answer's-shape task,
  not an oversight to patch.
- No Part 1 manual section for the reader.
- **This handover was owed and nothing flagged it.** 45 `WP-1118:` commits (of
  the PR's 46) merged with the WP file untouched, and `session_start.py`
  compares the newest handover-entry date against the commits' — the same
  day's issue-triage session
  had touched the file, so the date rule passed. A `/pr-review` merge writes no
  handover entry by design, so a contributor PR carrying a WP prefix is the one
  shape of work this repo can land with no record on the WP. **Closed in
  `.claude/commands/pr-review.md`** (this session, after the entry above was
  written): the triage call now reads `commits[].messageHeadline`, which is the
  only place that shape is visible at all — rank 1 batches such a PR when the WP
  is in flight, and step 9 makes the handover entry part of the merge
  disposition rather than a later session's archaeology. The scan is unchanged
  and still cannot ask for the entry; what changed is that the run holding the
  reading is now the one that writes it.
- Name audit, for the classes no test catches: all six diagnostic codes have
  skill rows, all four `Stance` members have writers in the table, the reader
  adds no physics (so no Part 2 equation is owed) and claims no Rwp comparison
  as evidence.

*Next*: the **registry-shape task**, which is now the single gate on three other
pieces of work — the `STR(...)` decision (#107), the `.EXP`/`.PRM` offer (#103)
and [1314](1314-mfile-reader.md)'s Jana reader — and which also settles whether
`read_topas_inp` becomes a top-level export with a `capabilities()` arm. Then
the skill correction above: small, independent of the registry, and currently
telling an agent to transcribe by hand a file the build can open.

### 2026-09-01 (1st session) — the issue triage folded four issues in

The issue triage folded four issues in rather than opening WPs beside this
one: #148 (write direction — round-trip as
acceptance, GSAS-II as a target), #107 (the `STR(...)` decision, parked at
the registry-shape task), #101 (the origin-choice task), #196 (Rietica/XND
named as the family's deliberate boundary). Two standing offers recorded:
the filer of #103 volunteers for the `.EXP`/`.PRM` task once the registry
shape lands, bringing two spec findings for its docstring (GSAS-II's
`Rvals['GOF']` is reduced χ², not its root; instrument parameters are
`[default, current, refine_flag]` triples, current at index 1) — and #107's
filer offers either fix once told which. The Jana reader is
[1314](1314-mfile-reader.md), gated on this WP's first task. Next: the
answer's shape, unchanged.

- **2026-08-21** — created, from WP-1110 item 19. Stub: the fences, the seams
  and the acceptance are settled; the answer's shape is the first open decision.
