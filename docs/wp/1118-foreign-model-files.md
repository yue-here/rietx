# WP-1118 — foreign model files: read a refinement in, write one back

Milestone: unscheduled · Status: 🔄 2026-09-10 — the TOPAS `.inp` reader
landed (PR #98), the FullProf `.pcr` reader (PR #111) and the GSAS-I `.PRM`
instrument-parameter reader (PR #248); the model-format registry, the GSAS
`.EXP` half and every writer remain
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
documented, and the `Z`-term round-trip question is already in Inherited
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

`capabilities()` publishes the pattern formats `read_pattern` opens; model
formats need their own arm, and the meta-test that fails on a registry member
missing from its arm applies unchanged. A new format token is spelled in
`_about.py`, never inline (root CLAUDE.md § Conventions).

### Inherited

- **2026-09-04, from [WP-1130](1130-background-reference.md) § Gap A/B, which
  drove the `.inp` reader on a real workshop file.** Two things it found,
  neither a bug.
  1. **`#if` blocks the files people actually ship.** Of the four `.inp`s in
     the Durham ZrMo₂O₈ workshop archive, **three refuse** at their first `#if`
     — `d8_01612_vt_reel_02.inp`, `_reel_01.inp` and `_vt_02.inp` — and only
     `d8_01612_fit_01.inp` reads. The refusal is *correct* (which branch was
     refined is unknown and reading on would report a model mixing both) and
     the message is good. What it means is that the multi-pattern reel files —
     the ones a series is actually run from, and the case WP-1110's agent round
     named as the hardest part of the work — are outside the reader's reach.
     1130 got its model by stripping the `#if`/`#endif` blocks in a scratchpad,
     which is a workaround no user should have to invent. Worth deciding: a
     `#prm`-only integer evaluator would resolve `#if (#out pattern_count > 1)`
     and the `Run_Number` guards, which is most of what these files use `#if`
     for.
  2. **`TOPAS_FEATURES_NOT_IMPORTED` named the thing that mattered, and nothing
     downstream could act on it.** The file's `spherical_harmonics_hkl` strain
     block on one phase was reported and dropped; 1130 then measured that this
     one phase owned **24 % of the fit's χ²**, and that supplying rietx's own
     equivalent (Stephens `Phase.microstrain`) took Rwp 0.1092 → 0.0878. So the
     diagnostic is doing its job and the gap is a *conversion*, not a
     capability: rietx has the physics. If `to_structure` ever grows a
     hkl-strain arm, note that the `.inp`'s coefficients are **fixed**
     (`!ahkl_c00` … `!ahkl_c44p`, taken from another range), so importing them
     imports a held model — and 1130 also measured that freeing such a block
     can make other phases `PHASE_UNCONSTRAINED`, so this is not a change to
     make silently.
- **2026-09-04, from [1119](1119-named-variables.md): the equation boundary you
  parked there is decided, and it is drawn short of a parser.** 1119 shipped
  `Refinement.add_variable` — a caller's own `Parameter` at `vars.<name>` that
  other parameters follow by affine tie, with `tie` now taking several sources
  — and **deliberately no expression string**, for four reasons its Decisions
  § 4 records in full (chiefly that it would be the second parser for one
  language, against the nonlinear DSL `Parameter.expr` is reserved for). So:
  the object a reader would target now exists, and the arithmetic your two
  readers carry privately (`topas.symbol_table`/`_resolve`/`_arith`, the
  `.pcr` codeword decoder) is still theirs — 1119 explicitly did not redeclare
  it. **The consequence for the registry-shape task and for #107**: a general
  macro pass is *not* blocked on rietx growing an expression language, because
  rietx is not growing one; if `STR(...)` needs a macro pass, it is a `.inp`
  grammar concern that lives entirely in `io/projects/topas.py` and answers to
  the Technical Reference, not to anything here. Decide it there.

- **2026-09-03, from the issue triage (issue #234): the `.gpx` non-goal's
  stated reason does not hold, and the real obstacle is worse than the one
  written down.** A `.gpx` is **not** one pickled object and not a container
  format: it is a headerless sequence of `pickle.dump(item, f, protocol=2)`
  calls, one per top-level GSAS-II tree item (`Controls`, `Phases`, each
  `PWDR <name>`), each a list of `[label, data]` pairs, read back by looping
  `pickle.load(f, encoding="latin-1")` until `EOFError`. Established from
  GSAS-II's own `GSASIImiscGUI.py` (`ProjFileSave`/`ProjFileOpen`) read as
  specification only, and corroborated on **146 real `.gpx` files** from a
  private archive: every one unpickles to completion with stdlib `pickle` plus
  `numpy` and nothing else — no GSAS-II import, no `ModuleNotFoundError`, and
  exactly **three** non-builtin types across the whole corpus (`numpy.float64`,
  `numpy.int64`, `numpy.ndarray`). **So a reader needs no GSAS-II dependency.**

  The obstacle that does hold: `pickle.load` will import and call **any**
  callable named in the stream, so a `.gpx` reader is an arbitrary-code-
  execution surface over a user-supplied file, and every reader rietx has today
  — pattern formats, `.inp`, `.pcr`, `.cif` — is text. The archive corpus
  cannot settle it: 146 benign files prove nothing about a malicious one, and
  "the files I have are fine" is the corpus-faith argument this WP already
  rejected for cell ties. **This is a security-posture decision for the
  maintainer, not a technical one**, which is why the reporter wrote no reader.
  Their four options: (1) a **restricted unpickler** — subclass
  `pickle.Unpickler` and override `find_class` to an allow-list, refusing every
  other global *by name*, the same "report or refuse, never drop" discipline
  `io/projects/coverage.py` applies to format keywords; `find_class` is
  pickle's only import hook, so this closes the hole rather than narrowing it,
  and it is the established pattern (PyTorch's `weights_only=True`,
  `numpy.load(allow_pickle=False)`), with a measured allow-list of builtins
  plus `numpy.ndarray`, `numpy.dtype`, `numpy.core.multiarray._reconstruct`.
  (2) A **`pickletools.genops` opcode walk** — strictly stronger and strictly
  more code to own for the same result; (1)'s trust boundary is already
  provable. (3) **Read GSAS-II's text instead** — `.EXP`/`.PRM`, already spec'd
  and licence-clear here, with the corpus's 79 `.lst` files; the cost is real,
  a `.lst` being a refinement *listing* rather than a round-trippable model, so
  a lesser deliverable and not a substitute. (4) **Require an export** via
  GSASIIscriptable to CIF — zero new attack surface, work moved to the user.
  The reporter's inclination is (1) if `.gpx` is wanted at all, (3) as this
  WP's honest next task if it is not, and they offer to implement either.
  **Decided 2026-09-03 by the maintainer: (1), the restricted unpickler.**
  The task is below; the reporter's offer to implement it stands.

  Two corrections that cost nothing to carry: **"pysas" is not GSAS-II's python
  interface** (that name is an unrelated XMM-Newton toolkit; the documented one
  is **GSASIIscriptable**), and if `.gpx` proceeds the corroborating corpus
  should widen first — all 146 files are plain CW-powder Rietveld projects, so
  image data, single-crystal (HKLF), sequential-fit results and magnetic phases
  are untested, and GSAS-II's docs place `G2VarObj` instances in some
  `Constraints` records where this corpus has only plain strings.

- **2026-09-02, from the magnetic scattering track
  ([1328](1328-magnetic-interchange.md)): the `.pcr` reader refuses a
  magnetic phase with the TOPAS reader's sentence, and 1328 lifts both.**
  `coverage.py`'s `magnetic structure` feature stays `Stance.REFUSED` until
  1327's model exists; a FullProf phase with Jbt = ±1 landing here now takes
  the same stance and the same sentence ("the nuclear half would look
  complete"), through the registry rather than a raise, so that 1328 changes
  one table. Do not map a Fourier-component magnetic phase onto a nuclear
  structure in the meantime.

- **2026-09-02, from [1324](1324-symmetry-silences.md): a space-group symbol
  without a setting suffix now has one authority, and a reader landing here must
  decide which side of it the format sits on.**
  `crystallography.symmetry.setting_alternatives(symbol)` returns
  `(taken, others)` for a bare symbol the tables hold in more than one setting —
  40 of them, read off gemmi rather than listed — and `("", ())` for a symbol
  carrying its own. The fit-time report `SPACE_GROUP_SETTING_ASSUMED`
  (`refine._symmetry_silence_diagnostics`) fires on the first case only, so a
  reader that resolves the setting itself keeps its callers silent: this is
  exactly what `normalize_space_group`'s trailing-`Z` → `:2` mapping already
  buys the `.inp` route, and what `cif.py` gets from preferring gemmi's own
  reading of the file. **The `.pcr` reader and the exporter registry inherit the
  question**: FullProf writes the symbol without a suffix in the common case, so
  either the `.pcr` route establishes the setting from evidence the file carries
  (the way `read_small_structure` picks R from the cell) or it hands a bare
  symbol on and the caller gets the warning — both are defensible, but the
  choice is now visible and should be made deliberately rather than inherited.
  An **exporter** has the mirror obligation: write `get_spacegroup(sym).xhm()`,
  not the phase's stored string, or a round-trip through a foreign format
  launders a resolved setting back into an ambiguous one.

- **2026-08-30, from [1308](1308-skill-documents-its-doors.md): the skill now
  has a routing row for *you were handed another program's input file*, and a
  reader added here must claim it.** The row is in `SKILL.md`'s routing table
  and points at `references/api.md` § In plus the manual's `recipe` page; § In's
  own paragraph opens the case by name and currently names only `read_recipe`.
  A second such reader (TOPAS `.inp`, `.EXP`/`.PRM`, `.pcr`) therefore has two
  obligations beyond the code, and `tests/test_skill.py` enforces only the
  first: every new public verb must appear in `docs/skill/make_api_index.py`'s
  `SECTIONS` or in `SKILL_EXCLUDED_VERBS` with a reason (the gate goes red until
  it does), and — no test for this — that routing row's wording says "a
  PowderLine recipe", the only such reader that exists, and will need widening.
  § In's paragraph states the same fence the other way, that a `.inp`, an
  `.EXP`/`.PRM` and a `.pcr` have no reader and are still transcribed by hand;
  a reader landed here must delete that sentence as well as add its row, or the
  skill will keep telling an agent to transcribe a file it can now open.
  Measured caution: SKILL.md sits at **31 973 B of its 32 000 B cap**, 27 B of
  headroom, so widening the row costs bytes that must be bought elsewhere.
  WP-1308's entry records the three tightenings it used and that no cap was
  raised.

- **2026-08-23, from [1131](1131-sample-broadening-is-a-specimen-property.md):
  rietx has no constant Lorentzian instrument term, so a GSAS-II profile cannot
  round-trip.** GSAS-II's CW Lorentzian is `γ = X/cosθ + Y·tanθ + **Z**`;
  `ProfileTCHZ` declares exactly `u, v, w, x, y` and no sixth term
  (`schemas/instrument.py:507-543`, and `params/vector.py:489` and `:953` both
  hard-code that five-name tuple). An `.instprm` with a nonzero `Z` therefore has
  nowhere to land, and the honest reader behaviour — carry it or refuse it by
  name — is this WP's call, not a physics question: Von Dreele's own teaching
  slide says `X, Y, Z = 0` is normal and that 11-BM has them zero, so `Z` earns
  a schema field for round-tripping and not for modelling. 1131 fenced it here
  explicitly rather than folding it in. Note also, for the same reader, that
  rietx's `profile.x` is the 1/cosθ (size) coefficient and matches GSAS-II's `X`
  by law, while TOPAS's `pkx`/`pky` map to rietx's `y`/`x` and **not** by letter
  (measured in WP-1130).

- **2026-09-02, from [1330](1330-skill-references-by-shape.md): the skill's
  body cap is 33 000 B and the body sits at 32 964 B — 36 B of headroom, not
  the 27 B against 32 000 the 1308 note above quotes.** The rule that now
  governs the routing-row widening that note asks for: a routing row, or any
  body sentence, is paid for by a cut in the body named in the commit, and
  the cap moves only in a commit that says so (`tests/test_skill.py`'s
  docstring, root CLAUDE.md § skill). Two things changed shape for the rows
  this WP still owes. Every reference file now opens with a pinned
  three-paragraph header (H1, "Load it when …", the provenance line), so
  `references/api.md` § In and `references/diagnostics.md` keep theirs
  when edited. And the skill's routing table is keyed by *situation*: the
  row for a foreign input file must name the situation ("you were handed
  another program's input file") and list the formats in § In, never a
  reader's name in the *When* column. `docs/wp/TEMPLATE.md` now carries a
  standing **Skill** task line; this WP's "skill rows for the new diagnostic
  codes" task is that line already.

## Non-goals

- **Not a TOPAS-compatible engine.** No macro language, no `prm` expression
  evaluator, no `fit_obj`. A construct with no model here is reported, not
  emulated.
- **GSAS-II `.gpx` is no longer fenced out — it is a task, behind a
  restricted unpickler** (decided 2026-09-03 on issue #234; the Inherited
  entry has the measurements). Until that day this bullet fenced it for a
  reason measured false. What stays out: any `.gpx` content the corroborating
  corpus does not cover — image, single-crystal, sequential-fit and magnetic
  projects — until the corpus widens, and a `.gpx` *writer*, which is the
  writers task like every other format. `.EXP`/`.PRM` are text and documented.
- **Not the additive component seam.** A `fit_obj` or a `.pcr` extra peak lands
  on `Instrument.extra_components`, which is [1102](1102-component-seam-humps.md)'s.
- **Not a pattern reader.** `io/`'s existing registry keeps that job.

## Tasks

- [ ] Decide the answer's shape (model + vary set, or a `Project`) and stand up
      the model-format registry beside `PATTERN_FORMATS`, with the diagnostics
      channel and the "report or refuse, never drop" rule written down first.
      *Half landed with the TOPAS reader* — the diagnostics channel, the rule
      (`io/CLAUDE.md` § Project readers) and a per-format shape (`TopasModel`
      + `to_structure`). What remains is the registry itself, whether the
      answer is a `Project`, and whether the readers are top-level `rx.`
      exports; #107, #103 and [1314](1314-mfile-reader.md) all wait on it.
- [x] TOPAS `.inp` reader — the format with the evidence behind it.
- [ ] GSAS `.EXP` + `.PRM` reader, and make `tests/test_acceptance_fap.py` take
      its protocol from the reader instead of from transcribed constants.
      — the `.PRM` half landed (`rx.read_gsas_prm`, PR #248, merged 2026-09-10,
      `ff69ec34`); `.EXP`, and the acceptance suite taking its protocol from
      either, remain.
- [x] FullProf `.pcr` reader. — PR #111, merged 2026-09-03 (`b717cc98`)
- [ ] GSAS-II `.gpx` reader behind a **restricted unpickler** (decided
      2026-09-03, issue #234): subclass `pickle.Unpickler`, override
      `find_class` to an allow-list — builtins plus `numpy.ndarray`,
      `numpy.dtype`, `numpy.core.multiarray._reconstruct`, the set measured on
      146 files — and refuse every other global **by name**, the same "report
      or refuse, never drop" rule as the format keywords. Loop
      `pickle.load(f, encoding="latin-1")` to `EOFError`; the tree is a list of
      `[label, data]` pairs per top-level item. Widen the corpus before
      shipping (image, HKLF, sequential, magnetic; `G2VarObj` in
      `Constraints`). GSAS-II's own source is read as specification only.
- [ ] Origin-choice honesty: `SPACE_GROUP_ORIGIN_ASSUMED` when a multi-origin
      symbol resolves unpinned, and the TOPAS suffixes accepted on input
      (issue #101; lift `normalize_space_group` from the #98 draft).
- [ ] The writers, each naming what did not cross — GSAS-II included — with
      export → re-import round-trip as each format's acceptance (issue #148).
- [ ] `capabilities()` arm, skill rows for the new diagnostic codes
      (`docs/skill/rietx/` — `AGENT_PROTOCOL.md` is a redirect stub since
      WP-1304), a Part 1 manual section, and an `ATTRIBUTION.md` row per
      format. The TOPAS half of the diagnostic rows and its `ATTRIBUTION.md`
      row landed; still owed, and now **false rather than merely missing**,
      are `SKILL.md`'s routing row and `references/api.md` § In, which both
      still say a `.inp` has no reader (Inherited, from WP-1308).
- [ ] Fixtures with provenance rows in `tests/data/README.md`; tests, and the
      obs/calc/diff PNGs for any refinement one of them drives.

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
