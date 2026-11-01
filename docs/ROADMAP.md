# rietx — Roadmap

The **index**: what shipped, what is in flight, what is queued, what is fenced —
one row per work package, in milestone order. The content lives one rank down,
so a session loads only what it needs:

- **[wp/](wp/)** — one self-contained **work package (WP)** per task: context,
  commit-sized checklist, acceptance command, handover log. `wp/TEMPLATE.md`
  defines the format and the status vocabulary.
- **[milestones/](milestones/)** — one record per milestone: scope, the measured
  acceptance at ship, the rolling narrative between them, dated appendices.
  [`milestones/process.md`](milestones/process.md) is the record for the repo's
  own process (the always-loaded caps and their diary).
- **[releases/](releases/)** — the notes a user reads on upgrade, one per
  version. `1.0.2.md` describes a release that was folded into 1.1.0 and never
  published, and says so at the top.
- **[DESIGN.md](DESIGN.md)** — the design record (rationale, locked decisions,
  invariants). Stable; read the section a WP links.
- **[skill/rietx/](skill/rietx/SKILL.md)** — the agent skill: how to *use* the
  package as an operator. A WP that adds a diagnostic code or a correction adds
  its row there.
- **[VALIDATION.md](VALIDATION.md)** (generated) — every real-data assertion and
  what its tolerance is referenced to; **[solver-survey.md](solver-survey.md)**
  — methods from outside crystallography, surveyed and dispositioned;
  **[RELEASING.md](RELEASING.md)** — how a version reaches PyPI, never by hand.

## Session protocol

1. **Start** from "Current focus" below and the In flight and Next lists at
   the top of [the WP index](wp/README.md), or from the WP the user names.
   Read that one WP file — self-contained on top of CLAUDE.md. Open DESIGN.md
   only at sections the WP links; do not read other WP files, except to find
   an owner before filing one (`wp/TEMPLATE.md`). `/wp-start` encodes this.
   **On arrival at a WP, prune its `### Inherited` first**: fold still-true
   entries into Context or Tasks, delete stale ones (say why in your handover
   entry). The section is a mailbox, emptied on every visit and deleted —
   fully consumed — when the WP closes.
2. **During**: land tasks as small commits prefixed `WP-NNNN:`; check items
   off in the WP file as they land.
3. **End** — or whenever interruption threatens — run `/wp-handover`. The
   checklist it carries: dated handover entry prepended (newest first, in one
   of `wp/TEMPLATE.md`'s two forms, opening with a plain-language paragraph on
   what the work *means* and closing on the next actions, working detail
   between), Status line set and the WP index regenerated, forward
   references pushed into the `### Inherited` of any affected WP that is not
   closed and not yours (a handover log reaches only your own successor on the
   same WP), the `Priority:` line of any WP your close unblocks or moots
   re-rated with the date and the reason, rule 4
   applied to anything this session wrote into a CLAUDE.md,
   working tree clean and pushed, and the branch's pull request opened or
   updated — a session is not handed over until its work is reviewable, and
   merging stays the maintainer's. **Invoke the command, never reproduce its
   checklist**: a handover written by hand skips the steps that cost work.
   Two hooks watch for a miss — `handover_owed.py` (Stop) holds one stop open
   when a WP branch is clean and pushed and the session never ran the command,
   and `session_start.py` flags at the next session start (two rules: the WP
   file older than the work, or the log older than the commits), which is
   repaired first.
4. **A CLAUDE.md takes rules, not findings.** A line enters a CLAUDE.md
   (root, `gui/`, `tests/`, `src/rietx/io/`, `src/rietx/indexing/`) only as a
   standing rule a stranger needs in six months — a few lines, evidence
   compressed to one clause plus a pointer to the WP or milestone record that
   holds the measurement. Counts and timings a session measures go in its WP
   handover entry (root CLAUDE.md § Numbers holds the *recipe*; the dated
   history is the v1.0 appendix diary). A rule an agent *driving* rietx
   needs is neither: it goes in the agent skill — the body if it holds for
   every fit, the task shape's `references/` file otherwise (root CLAUDE.md
   § skill, WP-1330).
5. **WP closes** (✅/🛑): delete its `Priority:` line, regenerate the index,
   and MOVE the outgoing narrative to the **record of the release in flight**
   (`milestones/vX.Y.md` for `pyproject.version`'s X.Y, § "How vX.Y is getting
   here"), whichever milestone the WP sits under. A close does not edit Current
   focus (WP-1507). The index lists what is in flight and what is next, so
   Current focus holds milestone prose: written when a milestone opens or
   ships, and by `/issue-review` when a triage moves the order. It stays
   within `CURRENT_FOCUS_CAP` lines *and* `CURRENT_FOCUS_WORD_CAP` words
   (tests/test_docs_consistency.py).
6. **A milestone is named and a release is numbered** (WP-1540). An open or
   queued milestone carries a lowercase name (`magnetic`), so one that runs
   late holds back nothing but itself; v1.0.2 and v1.6 were both held that
   way. **Milestone opens**: write `milestones/<name>.md` with its Scope and
   Acceptance rows *at the open* — the v1.3 record says plainly that rows
   written at ship are the weaker evidence — plus a `###` section and a table
   row here. **Milestone completes**: measure its acceptance in its record and
   flip its row; it ships in the next release. **Release is cut** weekly, and
   at once for a P1 fix (`RELEASING.md` § When): it carries what `main` holds,
   numbered over the last
   release (a minor when anything was added); finish `milestones/vX.Y.md` with
   the measured ship block naming the milestones it completes, check README's
   claims, then move `pyproject.version` to the next minor's `.dev0` and open
   that version's record. **A break or a user-facing addition is staged on the
   day it lands**, in the release record and the staged notes.
   The notes are written from the **tag range**, not from the milestone, and
   v1.4's pass found two changes shipping with no record entry behind them
   (v1.4 record § Appendix).

`tests/test_docs_consistency.py` enforces the mechanical parts: the header
vocabulary (status, priority, milestone, track), an index equal to the
generator's output, a link from every heading here to its rows, Inherited
placement, link resolution, and the size caps on this file and CLAUDE.md.

## Current focus

**The next release is 1.11** (`pyproject.version` `1.11.0.dev0`), cut from what `main` holds
([record](milestones/v1.11.md), [staged notes](releases/1.11.0.md)). 1.10.0 shipped 2026-10-24 ([notes](releases/1.10.0.md)).

**Two milestones are open and three are queued, by name.** [magnetic](#magnetic--the-magnetic-structure)
opened 2026-09-18 as v1.6; [generality](#generality--every-decision-rietx-makes-holds-beyond-the-data-it-was-tuned-on)
opened 2026-10-18; rietview, rigid-bodies and structure-solution were
queued as v1.7, v1.8 and v1.9. Threads #286, #426, #561 and #562 quote those
numbers, so each row in § Milestones says which it was. **Neutron TOF stays at
[§ v2+](#v2--fenced)** behind issue #193, but for its T-1 cut ([1927](wp/1927-tof-t1-the-axis-and-its-readers.md), 2026-10-08).

**Ten silent-answer fixes have landed since 1.5.0** (1434, 1435, 1432,
1342, 1415, 1442, 1414, 1454, 1456, 1465), staged in the notes and narrated
in the release record.

**What is in flight and what is next** are the first two lists of
[the WP index](wp/README.md), generated from the WP files (WP-1507). A close
no longer edits this section.

**Two cheap unowned asks** survive, both in 1407: a Stoe `.raw` paired with its
WinXPOW export, and a blank for a `rietx compare` standard.

**Parked, blocking nothing:** the 1.0.0-notes promises (`.rex` zip transport,
`excluded_regions` honoured by `replay` — 1003 § B); the indexing narrowing and
the `grade` prior-counting change (1046 § 4); the model-cost estimate (1113
§ Findings); the two v1.1 speed fronts nobody owns (the per-reflection 19.4 %,
1121; the `refit=` choice that discards half a trigger series' wall, 1124);
and `toy_roughness`, the one backend state whose Jacobian no second opinion
covers (1119 § Gotchas).

## Milestones

| Milestone | Scope | Status | Acceptance |
|---|---|---|---|
| v0.1 | Vertical slice: synchrotron CW, Rietveld + Le Bail | ✅ **shipped** ([record](milestones/v0.1.md)) | 11-BM NAC: a = 10.251285(12) Å, Rwp 9.2%, CaF₂ impurity auto-flagged |
| v0.2 | Lab diffractometer + FitReport attribution + viz | ✅ **shipped 2026-07-22** ([record](milestones/v0.2.md)) | SRM 660c LaB6: a = 4.156895(25) Å (+28 ppm vs NIST value for this dataset, Bérar-Lelann-inflated esd), Rwp 8.7%; GSAS-II FAP tutorial: Rwp 9.73% vs GSAS's 10.05% on identical channels, cell +116 ppm (uniform d-scale convention offset) |
| v0.3 | Multi-phase QPA, Pawley, aniso ADPs, multi-histogram | ✅ **shipped 2026-07-24** ([record](milestones/v0.3.md)) | SRM 676a corundum: c/a +30 ppm vs certificate (absolute axes −313/−283 ppm, uniform d-scale); IUCr round robin: sample-1 worst 5.1 wt% (traces ≤1.3), sample 2 worst 2.9 wt% with brucite March-Dollase r=0.67, sample 4 characterised as the designed Brindley failure (µR fence fires) |
| v0.4 | Differentiable backends: JAX jacfwd, mixed precision, torch-MPS; true Voigt; restraints | ✅ **shipped 2026-07-27** ([record](milestones/v0.4.md)) | Cross-backend Jacobian agreement (analytic/FD/jax/torch × 8 configs + multi-histogram + stage boundaries) inside the 5e-3 rel-L2 fp64 bar; an all-fp32 Apple-GPU refinement of SRM 676a lands Δa = −3.5e-8 Å from numpy fp64 (bar 3e-5); wall-clock reported, not gated — and it is a *finding*: MPS is 46-182× slower (launch-latency-bound) and jit'd jacfwd is within 2.1× of the analytic assembly at best, so the batched peak loop is a numpy-path win (WP-0605), not GPU enablement |
| v0.5 | Corrections & microstructure (absorption, Stephens, f′f″) | ✅ **shipped 2026-07-28** ([record](milestones/v0.5.md)) | capillary absorption validated at **both** levels: the Rouse (1970) cylinder factor against a quadrature of the exact ITC eq. (6.3.3.4) integral across 0 ≤ µR ≤ 1 *and* 0 ≤ sin²θ ≤ 1 (0.0035, the paper's own bound), and on real 11-BM SRM 660a LaB₆ data in a documented 0.81 mm bore — Rwp moves 3e-8, the cell 8e-12 Å, and *both* Biso move by the predicted 0.0166542 Å². Plus the two accuracy wins no fit statistic shows: dispersion takes the round-robin QPA error from RMS 2.26 → 0.69 wt %, and a mis-declared flat-plate thickness biases Biso by up to −1.5 Å² |
| v0.6 | TOPAS-style bounded LM, agent surface, batched peak loop, theory manual | ✅ **shipped 2026-07-29** ([record](milestones/v0.6.md)) | bounded LM 0.74–1.04× vs scipy TRF (CPU — the expected Amdahl tie), identical minima on 2/3 protocols, ΔBIC −13 on the third, and the Stephens cone enforced as a linear inequality (brucite 12/43 → 0/43 outside, at higher Rwp); FCJ node memo 1.23× bit-identical; agent schema generated from live registries with a registry-membership meta-test; theory manual builds `-W`-clean with every fenced constant injected from the live package and five anti-divergence guards in the fast suite |
| v1.0 | Hardening, human GUI, indexing, API freeze, PyPI | ✅ **shipped 2026-08-16** ([record](milestones/v1.0.md)) | full suite green at ship: 2509 passed / 126 skipped locally (`[dev]`, macOS) and CI-green on Linux `[dev,jax]` (run 31966606174, full job 1h57); GUI end-to-end and the bethanechol individual-program grading landed by their WPs (record § Acceptance); repo public with six required checks gating `main`; manual + AGENT_PROTOCOL at yue-here.github.io/rietx, all URLs verified; `rietx` 1.0.0 on PyPI, fresh-venv install + `capabilities()` verified from the index; Windows fast suite green as the classifier's pre-upload gate — a gate that caught three real defects (CRLF-unstable checkouts, an SO_REUSEADDR double-bind in the GUI server, cp1252 example pipes) before the irreversible step |
| v1.1 | Refinement speed: seconds not minutes — and the 1.0.x work folded in (1.0.2 was never published) | ✅ **shipped 2026-08-23** ([record](milestones/v1.1.md)) | trigger-shaped cold fit **5.69-5.72 s** against the milestone's opening **50.11-50.43 s** (8.8×) and the 10-pattern warm series **49.24-49.30 s** against **266.78-269.61** (5.4×), best-of-3 idle, darwin/arm64 `[dev]`; seven of nine warm patterns at 0.88-2.33 s (median 2.02) with two at 10.53/20.26 — the ~1 s band **met on the maintainer's judgement and recorded mis-specified**, judged on the per-pattern table as WP-1124 required; stretch (cold < 1 s) **measured unreachable** and recorded as such; every landed WP with its equivalence bar, never an Rwp comparison |
| v1.2 | The GUI for a crystallographer: house style, one help mechanism, onboarding, the panels a first-time user meets | ✅ **shipped 2026-08-28** ([record](milestones/v1.2.md)) | all six rows met on the release tree: one token layer and nine control registers with no size at a call site; one help mechanism over a 119-entry corpus crossed against the live vocabularies both ways, its 47 remaining authored titles a per-file budget that fails both ways; a project created from a blank state four ways in a real browser (a shipped example, browse, a typed cell, no structure at all); zero axis movement on hover, tab change and a whole exclude drag, 4 → 1 reacts per drag; refine flags, typed coordinates and a saved instrument profile in the Model panel; and the manual guarded by two partitions (77 routes, nine panels), 18 generated screenshots and a generated glossary — suite counts in the record's ship appendix |
| v1.3 | Agents and programs: the termination view, the hold, the skill, the interchange format | ✅ **shipped 2026-08-30** ([record](milestones/v1.3.md), [notes](releases/1.3.0.md)) | six rows written at ship rather than at the open, and recorded as the weaker evidence that is: one integration surface, the python API, `rietx.agent` deleted on **zero** traced calls across four rounds; a result answering "done or not, and why" in one call, its diagnostics 35.2 → 3.5 kB from dedup and cap alone; an unsupported phase **held** rather than bounded (13 sub-onset ramp patterns: a cell 14.9 Å from truth free, 0.163 Å bounded by hand, **not reported** here); the protocol a 31 968 B skill read whole with a derived gate that found **four** undocumented entry points on its first run; the PowderLine recipe at **11-93 ppm** from TOPAS on all five free cell parameters; and the block measured — round 1.1, eight cells, $38.39, **seven of eight** stopping on a criterion this package states against **zero** in the 86-run baseline — suite counts in the record's ship appendix |
| v1.4 | Free-standing peaks: fit_peaks + the extra-components seam | ✅ **shipped 2026-09-13** ([record](milestones/v1.4.md), [notes](releases/1.4.0.md)) | seventeen rows, **every one written before the work rather than at the ship** — 1101's five at the open, 1102's and 1103's sharpened by the sessions that had read them — and all seventeen met on the release tree (record § Appendix). The measured half: `fit_peaks` answers a named position that fits nothing and flags the unnamed neighbour beside one; the union's second member costs no new field and its landing is read from data, not from a class name; and the operando case is reported against its own alternative rather than flattered — declaring two injected holder lines recovers the SRM 660c cell to −1.0 ppm where ignoring them costs +7.6 ppm and inflates the cell esd 7.5×, while **excluding** the regions recovers it too, to +0.6 ppm, for 4.8 % of the channels |
| v1.5 | A window into a run: the live watcher, foreign model files, a measured background | ✅ **shipped 2026-09-18** ([record](milestones/v1.5.md), [notes](releases/1.5.0.md)) | nine rows, **none of them written at the open**, because the milestone was opened 496 commits behind its own work — the record says plainly that this is weaker evidence than v1.3's at-ship rows and reads as an inventory. The measured half: the live view at 180-329 kB a stage against the replaced page's 4.51-6.03 MB; a default-on recorder costing 1.03-1.28×, which **fails** its own 1.05× gate on two cases of three and was kept anyway with the reason recorded; a console that froze the main thread for 997 ms on a 60 000-event run, capped at the route; four foreign formats read and written; and `help.py`'s Lp corrected from 0.508× of the one the code computes |
| v1.6 | The first release numbered at its cut: what `main` held on 2026-10-03, completing no milestone | ✅ **shipped 2026-10-03** ([record](milestones/v1.6.md), [notes](releases/1.6.0.md)) | 217 pull requests since v1.5.0, every user-facing change named in the notes or dispositioned in WP-1541's handover; the magnetic rungs ship unfinished and say what is missing; the Windows pre-upload gate, red every night since 2026-09-28, green on the release commit; VALIDATION.md's measured column re-run on the release tree; suite counts in the record's ship appendix |
| v1.7 | The first weekly cut: what `main` held on 2026-10-08, completing no milestone | ✅ **shipped 2026-10-08** ([record](milestones/v1.7.md), [notes](releases/1.7.0.md)) | 89 pull requests since v1.6.0, every user-facing change named in the notes or dispositioned in WP-1546's handover; rigid bodies ship as a provisional first piece; the Windows pre-upload gate, red since 2026-10-05, green on the release commit; VALIDATION.md's measured column, Part 1 and the skill re-run on the release tree; suite counts in the record's ship appendix |
| v1.8 | Every parameter in its own units: what `main` held on 2026-10-12, completing no milestone | ✅ **shipped 2026-10-12** ([record](milestones/v1.8.md), [notes](releases/1.8.0.md)) | 47 pull requests since v1.7.0, every user-facing change named in the notes or dispositioned in WP-1954's handover; cut on the merge of WP-1929, a P1 fix for esds that followed where the solver stopped; WP-1953's large Pawley stage ships as a stated limit, and so does the Windows pre-upload gate's one red test, a report-loop stop that differs on Windows; VALIDATION.md's moved rows, Part 1 and the skill re-run on the release tree; suite counts in the record's ship appendix |
| v1.9 | A parameter as a function of each pattern's coordinates: what `main` held on 2026-10-14, completing no milestone | ✅ **shipped 2026-10-14** ([record](milestones/v1.9.md), [notes](releases/1.9.0.md)) | 41 pull requests since v1.8.0, every user-facing change named in the notes or dispositioned in WP-1961's handover; cut early at the maintainer's ask, once WP-1959's kernel wheel was on PyPI and rietx's floor rose to it; VALIDATION.md re-measured on the release tree; suite counts in the record's ship appendix |
| v1.10 | Every fit ends in a closing stage: what `main` held on 2026-10-24, completing no milestone | ✅ **shipped 2026-10-24** ([record](milestones/v1.10.md), [notes](releases/1.10.0.md)) | 128 pull requests since v1.9.0, every user-facing change named in the notes or dispositioned in WP-2043's handover; the tag waited on WP-2044, a P1 fix for an esd that depended on the platform; the Windows pre-upload gate, red since 2026-10-20, fixed twice more on the day (#1151) and its suite green on the release commit, the job cut off by its limit in cleanup; VALIDATION.md re-measured on the release tree; suite counts in the record's ship appendix |
| v1.11 | The next release: what `main` carries when it is cut, and the milestones complete by then | 🔄 **accumulating since 2026-10-24** ([record](milestones/v1.11.md)) | written at the cut |
| magnetic | The magnetic structure (was v1.6): the satellite, the moment, the determination, the mode amplitude — [§ magnetic](#magnetic--the-magnetic-structure) | 🔄 **opened 2026-09-18** ([record](milestones/magnetic.md)) | eleven rows written at the open, the record's § Acceptance; the measured half is still to come |
| rietview | rietview (was v1.7): the structure figure an agent composes — cuts, extents, a figure that reports on itself, a real-agent measurement, the split — [§ rietview](#rietview--the-structure-figure-an-agent-composes) | ⬜ **queued 2026-09-27** | written at the open |
| rigid-bodies | Rigid bodies (was v1.8): a fragment refined as one body, its atoms reported with esds — [WPs](wp/README.md#rigid-bodies): 1801-1813, the seam decided by 1803 and the rest cut from its record | ⬜ **queued 2026-09-30** | written at the open |
| structure-solution | Structure solution (was v1.9): a difference-Fourier map, a cost from the Pawley intensities, direct-space search — [WPs](wp/README.md#structure-solution): 1901-1902, the map then the cost; #197 and #198 left the fence 2026-09-30 | ⬜ **queued 2026-09-30** | written at the open |
| generality | Every decision rietx makes holds beyond the data it was tuned on: every verdict, action and threshold tiered, the unproven demoted, a guard against the next one — [§ generality](#generality--every-decision-rietx-makes-holds-beyond-the-data-it-was-tuned-on) | 🔄 **opened 2026-10-18** ([record](milestones/generality.md)) | eight rows written at the open, the record's § Acceptance |
| v2+ | FPA (with the peaks buffer), neutron TOF, modulated structures, PDF — [§ v2+](#v2--fenced) | ⬜ fenced | — |

## Work packages

**The index is generated** (WP-1507). The WP tables are
[wp/README.md](wp/README.md), written by `python3 .claude/hooks/wp_index.py`
from each WP file's header, under the headings of this section. The headings
and their prose stay here. So filing, starting, closing or re-rating a WP edits
that WP's file and the regenerated index, and never this file. A test fails
while the index is stale, and a local merge resolves it row by row (the
`wpindex` driver the SessionStart hook sets). A WP under a `####` track names
that heading verbatim on a `Track:` line. A new track is a `####` heading here,
with its prose and a link to its anchor in the index.

**Numbering.** A WP number is `MMNN`: the block of the milestone it was
*opened for*, then a sequence number. The number never changes when the WP
moves (1101–1103 opened for v1.1 and are queued for v1.4), so the
**`Milestone:` line in the WP file is the authority** on where a WP stands,
and the index places its row by that line. An unscheduled WP takes the next
number in the newest block (15xx today, claimed 2026-09-27 for rietview). A
named milestone claims the next free hundred when it is queued. A retired number is never recycled: 0603 moved to v0.4 as 0408 and
stays empty.

**Priority.** Which WP the next session's tokens should go to, `P1` to `P4`.
The WP file's `Priority:` line is the authority (rubric, date and reason in
`wp/TEMPLATE.md`), and the index shows its tier. Closing a WP re-rates the ones
it unblocks or moots, and the tier outranks the order any paragraph here
states.

Sections are in milestone order, the same as the table above.

### v0.3 — multi-phase workflows

The WPs are in [the index](wp/README.md#v0-3).

### v0.4 — differentiable backends

The WPs are in [the index](wp/README.md#v0-4).

### v0.5 — corrections & microstructure

The WPs are in [the index](wp/README.md#v0-5).

### v0.6 — solver, performance & agents

The WPs are in [the index](wp/README.md#v0-6).

### v1.0 — hardening, human GUI, indexing, API freeze, PyPI

Six sets; the ordering arguments are in the [v1.0 record](milestones/v1.0.md).
The freeze (1003) ran last so it covered a surface the GUI and indexing had
exercised; the renames ran early because the freeze covers names that embed
the brand.

#### Platform, release and the repo's own process

The WPs are in [the index](wp/README.md#v1-0-platform-release-and-the-repo-s-own-process).

#### The human GUI

The WPs are in [the index](wp/README.md#v1-0-the-human-gui).

#### Indexing

The WPs are in [the index](wp/README.md#v1-0-indexing).

#### Found by use

The WPs are in [the index](wp/README.md#v1-0-found-by-use).

#### Report evidence, agent evals, and the rename

The WPs are in [the index](wp/README.md#v1-0-report-evidence-agent-evals-and-the-rename).

#### The McCusker (1999) compliance set

The WP-1068 audit ([v1.0 record](milestones/v1.0.md) § Appendix): no
correctness defect, nine gaps — six WPs here, difference Fourier fenced to v2+,
the divergence-slit correction declined in the audit itself. 1068 itself is the
manual's second pass, which produced the audit.

The WPs are in [the index](wp/README.md#v1-0-the-mccusker-1999-compliance-set).

### v1.0.x — after the ship, published in 1.1.0

The 1.0.x road: the manual's remaining chapters, the honesty pass they exposed,
the extinction screen's wrong evidence, and indexing declared provisional.
Written as 1.0.2, never published, folded into 1.1.0 on 2026-08-23
([releases/1.0.2.md](releases/1.0.2.md) says so). 1067 declared the GUI's
original beta status; **its § Floor gated 1003**, the rest landed here.

The WPs are in [the index](wp/README.md#v1-0-x).

### v1.1 — refinement speed

Measure first (1111), then the exact wins (1109), the batched Jacobian path
(1112), the evaluation-count front (1113), the algorithmic tier (1114), a gated
compiled tier (1115), and what each opened; targets and the opening baseline
in the [v1.1 record](milestones/v1.1.md) § Acceptance. The milestone also
carried the agentic-report set, the compatibility promise, two process WPs
and constant-wavelength neutron.

#### Speed

The WPs are in [the index](wp/README.md#v1-1-speed).

#### The agentic report

The WPs are in [the index](wp/README.md#v1-1-the-agentic-report).

#### The promise, the manual, the process, and neutron

The WPs are in [the index](wp/README.md#v1-1-the-promise-the-manual-the-process-and-neutron).

### v1.2 — the GUI for a crystallographer

The maintainer's use notes, triaged: the style system first, the manual last,
and between them one WP per cause found in the code. The order was 1201,
1204, 1202, 1203, then 1205-1217, and 1017 last. The per-note assessment and
the decisions are the
[v1.2 record](milestones/v1.2.md) § Scope. 1017 (opened for v1.0, deferred by
1003) closed the milestone and lifted the GUI's beta.

The WPs are in [the index](wp/README.md#v1-2).

### v1.3 — agents and programs

The agent-facing surface refactored against two measured runs, which said the
only agents are shell-equipped sessions using the notebook API, and that none of
six refining runs stopped on a package criterion. The baseline numbers are in
[1307](wp/1307-recapture-round-1-1.md) and the [v1.3 record](milestones/v1.3.md).

The WPs are in [the index](wp/README.md#v1-3).

### v1.4 — free-standing peaks

Peaks without a structure: fitted standalone (1101), and the
`Instrument.extra_components` union seam — the serializable answer to TOPAS's
fit_obj — with broad humps (1102) and sharp peaks (1103) as its first members.
Opened for v1.1, shifted three times (2026-08-20, -25, -28), numbers kept.
The ship pass also deleted the `AGENT_PROTOCOL.md` pointer
([1304](wp/1304-protocol-as-skill.md) kept it for one release), at four sites
rather than the three the record scoped.

The WPs are in [the index](wp/README.md#v1-4).

### v1.5 — a window into a run

Twenty-six WPs with commits in `v1.4.0..main`, every one opened unscheduled and
merged before the milestone was; the [record](milestones/v1.5.md) says what
opening it late costs. 1408-1410 closed on 2026-09-14 *before* the tag was cut
at 16:13 and shipped in 1.4.0, so they stay in § Unscheduled with the rows that
are still open.

#### The live-watcher track

Eighteen rungs answering a question the package could not answer before: what
is my fit doing right now. 1428 was the last of the track proper, 1438 answered
the twelve questions it handed the maintainer, and 1439 is the bill for writing
the track on POSIX.

The WPs are in [the index](wp/README.md#v1-5-the-live-watcher-track).

#### Coming from another code

The largest single WP in the range at 83 commits; the grammar its reader still
refuses is 1433, unscheduled.

The WPs are in [the index](wp/README.md#v1-5-coming-from-another-code).

#### The fit has no reference

The blank the beamline scanned, with a refinable scale and its own esds
(issue #171); its sibling 1130 stays 🛑 in § Unscheduled.

The WPs are in [the index](wp/README.md#v1-5-the-fit-has-no-reference).

#### What the package says about itself

Corrections to what the package says of itself, the titles in the index saying which.
The symbol audit (1436, 1437) found `help.py` printing an Lp 0.508× from the
one the code computes; 1440 is the milestone itself.

The WPs are in [the index](wp/README.md#v1-5-what-the-package-says-about-itself).

### v1.5.x — after the ship

Work landing while no milestone is open, staged in
[releases/1.5.1.md](releases/1.6.0.md) the day it lands, because v1.4's ship
pass found two changes that had shipped with no record entry behind them. The
1.0.x road is the precedent, ending included: written as a patch, folded into
the next minor if one opens first. The road ends with WP-1540. A fix now lands
as `unscheduled` and ships in the next release, so no new WP joins this
section.

Issue **#374** — a *supported* phase's cell walking to hundreds of Å inside one
stage, along a direction it shares with a second free phase's cell and which
`phase_support` cannot see — is in the contributor's PR #385, a post-solve
clamp with a `CELL_RUNAWAY` diagnostic. Its review is `/pr-review`'s; no WP
here, since 1110 and 1301, whose windows it sits beside, are closed. A second
instance (2026-09-24 on the thread) is Le Bail with lengths gone negative, so
the review checks the clamp in that mode and a positivity test beside it. A
third (2026-09-25) is a 204-fit phase screen, replayed on main and on main with
#385: raises 30 → 1, unphysical cells 59 → 0, and 31 results still move a
length over 15 % with no `CELL_RUNAWAY` (WP-1464 has the table).

The WPs are in [the index](wp/README.md#v1-5-x).

### magnetic — the magnetic structure

Seven rungs, opened 2026-09-18 as v1.6 ([record](milestones/magnetic.md)), out of
§ Unscheduled where 1326–1329 sat from 2026-09-02 and out of the v2 fence
before that. Three readers refuse a magnetic structure with one sentence, and
the unexplained-intensity report names a magnetic contribution as a cause it
cannot test; CW neutron shipped in 1134, so the fence's premise was gone. 1326
needs no moment (a satellite is a position); 1327 takes the two decisions PR
#221 left open and holds an unsupported moment at zero (1301's rule). 1343 is
1327's price: no magnetic size term, so a broad magnetic peak is fitted by a
low moment (#277). The operator layer landed from outside 2026-09-10 (PR #290,
`crystallography.magnetic`, spglib's 1651 groups). 1419 alone is *nuclear*
(#286, #293), sharing 1418's mode vectors and 1327's operator-list phase.

The order the rungs land in, set in #286, is in the
[record](milestones/magnetic.md#the-order).

**Neutron TOF is not here.** It stays fenced at [§ v2+](#v2--fenced) behind
issue #193, which its own reporter filed that way. A fence moves by a recorded
decision, the way magnetic structures left it on 2026-09-02, and not by work
existing.

The WPs are in [the index](wp/README.md#magnetic).

### rietview — the structure figure an agent composes

Queued 2026-09-27, the block claimed the day WP-1470 closed, as 1301-1307
were filed for v1.3 before it opened. 1470 drew one cell of one phase as the
GUI draws it. This track makes the figure something an agent composes: a
part of the structure kept by a mask (1501), an extent beyond one cell
(1502), a figure that reports the numbers a look would give and picks its
own view (1503), the surface measured with real agents before more is added
(1504), and the code leaving as `rietview` when a named trigger fires
(1505). The name was chosen on 2026-09-27; the survey and the trigger are in
1505. The maintainer asked on 2026-10-02 for an SVG (1536), POV-Ray and glTF
(1537), and ambient occlusion (1538). 1504 is costed and closed (2026-10-23, 40 of 42 on the fixed surface), so it opens by the maintainer's word.

The WPs are in [the index](wp/README.md#rietview).

### rigid-bodies — a fragment refined as one body

Queued 2026-09-30 from issue #561. The seam was measured first (1803) and the rest re-cut from its record on 2026-10-06: the derived block (1804), then `RigidBody` (1805), which every later WP needs. [The WPs](wp/README.md#rigid-bodies).

### structure-solution — a map, a cost and a search

Queued 2026-09-30 from issue #562. The map, then the cost, then a search (WP-1515). [The WPs](wp/README.md#structure-solution).

### generality — every decision rietx makes holds beyond the data it was tuned on

Opened 2026-10-18 from the maintainer's concern that features are fitted to the test
cases that produced them ([record](milestones/generality.md)); it applies [DESIGN.md](DESIGN.md)
§ Rules to the tree. The record § The rule is the one authority: three tiers
(physics, practice, rietx's own) per statistic, threshold and action; an action of any
tier survives only if every competent refiner, shown the number, would take it, and a
tier-3 threshold must also hold on three dataset families, each against its reference; a named dissenter demotes it
to a ranking or to the number, by Rule 1's kinds. 2001 writes the rule, table and guard; 2002–2007 audit one seam each, 2002
first, a gate after 2004; 2010 audits features against Rule 2; 2008 slims the skill to the API and sourced traps; 2009 rewrites the rules that reward a firing code. [The WPs](wp/README.md#generality).

#### The registry and the guard

2001: the rule written down, the audit table every later WP fills, the tripwire test and the fresh-context review the handover dispatches on a hit. 2014: that review on every other path into main, outside PRs and unwatched directories included. 2019: opt-in sets of bounds and defaults for one scenario, tested on the datasets they name, where a default too narrow for the package goes. 2037: the fifth aim, attention is a cost; a number in a field and a diagnostic only where it tells fits apart, a response per code with relevance derived from the declared purpose, a default view that prints by level, and a caller override (lands before 2003). 2038: the softening of unanimity for a recorded, cheap-to-undo default, a brief for the maintainer and not a change. [The WPs](wp/README.md#generality-the-registry-and-the-guard).

#### The audits

One seam each, the same task shape: lanes read and tier, the lead tables, the maintainer rules in a batch, approved demotions land with any moved golden recorded against its reference. 2002 the single-fit actions (first, since every fit runs them), 2003 the chain, 2004 the FitReport, 2005 `refine.py`'s codes, 2006 the readers and crystallography, 2007 indexing; 2010 every feature against Rule 2, outside the gate. [The WPs](wp/README.md#generality-the-audits).

#### The prose

2008 the skill slimmed to the API, the feedback surface and sourced traps; 2009 the rulebooks, findings out and the generator rules rewritten. [The WPs](wp/README.md#generality-the-prose).

### Unscheduled

Opened by evidence — an issue, an agent round, a measurement — and owned by no
milestone yet. Grouped by what the evidence says; each WP file carries it in
full, with the issues it closes. Most of the 13xx rows come from the
2026-09-01 issue triage (PRs #205, #213) and the day after; 1119, 1130 and
1133 are older; 1414–1420 are the 2026-09-15 triage's.

#### Coming from another code

What 1118 read and wrote (§ v1.5), continued. 1119 is the named variable such
a file's equations refer to; issue **#212**'s cross-phase linear restraint is
its first concrete ask, and [1942](wp/1942-a-soft-restraint-on-a-sum-across-phases.md)
carries it.

The WPs are in [the index](wp/README.md#unscheduled-coming-from-another-code).

#### The fit has no reference

A quantity derived sharing no assumption with the fit. 1309 shipped the other
half in § v1.5; 1130's own trigger stopped reproducing.

The WPs are in [the index](wp/README.md#unscheduled-the-fit-has-no-reference).

#### The specimen is not an angle, and the neutron follow-through

Sample broadening was stored as a deg-2θ coefficient and shared across
histograms as though it were a specimen property; for **size** it is not (the
same crystallite broadens by a different angle at a different wavelength).
**1131 closed 2026-09-02**: a joint fit now shares the crystallite size and each
histogram carries its own coefficient (numbers in 1131), and every converged
fit reports a coherent domain size and a Δd/d with esds. The neutron rows follow 1134.

The WPs are in [the index](wp/README.md#unscheduled-the-specimen-is-not-an-angle-and-the-neutron-follow-through).

#### What fires, and what stays silent

Each row is a silent wrong answer, the class the repo's rules are strictest
about; the titles in the index say which. Three triages feed it (2026-09-01, -03,
-15) plus the 2026-09-16 review of #286 and #293, which cut 1432 of 1342's
kind. The orbit that was not a multiplicity (1324) is closed and 1320 restates
what it measured. 1310 closed on four of six in § v1.5, and both of the two it
could not answer closed 2026-09-18 as **1434** (the bound flag) and **1435**
(a caller's hold), each file saying what changed.

The WPs are in [the index](wp/README.md#unscheduled-what-fires-and-what-stays-silent).

#### A long run is not one fit

Three costs a multi-hundred-pattern campaign paid and a single fit never sees
(2026-09-03 triage): a raise on one pattern taking a chain of hundreds with it,
including a *converged* fit's esd computation (1333); 3.9 % of stages burning
46.6 % of stage time by exhausting their budget for a 1.23 % median cost
reduction (1334); and a report path costing 26× the fit it reports on (1335).
Two are pure cost; 1333 also hides a silent wrong answer, a verification pass
that died reading as one that passed. Together they decide whether a batch is
affordable. The 2026-09-15 triage adds 1420: a phase 1301 held cannot get
back in when its frozen structure is collinear with a supported phase, and
the chain says nothing (issue #267).

The WPs are in [the index](wp/README.md#unscheduled-a-long-run-is-not-one-fit).

#### One file, many patterns

The `scan=` idiom extended to containers (issues #134, #135): a plain zip of
patterns, and a NeXus/HDF5 in-situ reel behind the package's first
optional-dependency format.

The WPs are in [the index](wp/README.md#unscheduled-one-file-many-patterns).

#### The formats a lab still has

1047's declared follow-up, reopened by an ask for a PANalytical `.raw` that
does not exist (`.raw` is six unrelated vendors, none of them PANalytical).
1416, the positional `.xy` reader checking the shape of what it accepted
(issue #266), was folded into 1332 on 2026-09-24.

The WPs are in [the index](wp/README.md#unscheduled-the-formats-a-lab-still-has).

#### Render what the fit already knows

Views over quantities already computed, no new physics: a series navigated by
its own T/t trace (1317, with issue #218's forward-pass exposure), the Stephens
S_HKL block as a strain surface (1318), and a run's own `events.jsonl`
aggregated after the fact (1322). The 2026-09-03 triage adds three: the
localisation statistic `rietx compare` computes, over any two results on one
pattern (1339); a mole fraction from the scale and the cell volume, on a basis
that travels with it (1340); and the report a joint fit has never had (1341).
The 2026-09-21 triage adds 1444, the pattern drawn before any model exists and
a title on a figure (issues #394, #405). Issue **#343**, a third colour scheme
(Solarized) over 1429's token module, is answered on its thread rather than
filed: welcome as a PR carrying a measured token set that meets the one
separability floor, and not scheduled here.

The WPs are in [the index](wp/README.md#unscheduled-render-what-the-fit-already-knows).

#### Data and metadata in, a structure out

A pattern and what the person knows, in; a structure an agent can defend, out.
Opened 2026-09-28 by the review of `solution case 1`. 1514-1516 each scope a
milestone for what left § v2+ that day; 1517 counts the eight steers.

The WPs are in [the index](wp/README.md#unscheduled-data-and-metadata-in-a-structure-out).

#### The repo's own process

The WPs are in [the index](wp/README.md#unscheduled-the-repo-s-own-process).

#### Candidates — named on a use case, not yet on a measurement

The WPs are in [the index](wp/README.md#unscheduled-candidates-named-on-a-use-case-not-yet-on-a-measurement).

### v2+ — fenced

Seams pre-built, implementations fenced out. **No WP files for v2+ on
purpose**: the fence is a scope-discipline decision
([DESIGN.md](DESIGN.md#locked-decisions)), and pre-writing packages invites
scope creep. Each item names what fenced it.

- **Physics.** Fundamental Parameters as a differentiable convolution stack
  (Cheary-Coelho 1992) — **with** the peaks buffer, never before
  ([1122](wp/1122-compiled-peaks-buffer.md) measured shape reuse below break-even
  without one); neutron **TOF** (CW landed in 1134; issue #193; the energy-dependent
  resonant absorption at S(Q), #113) — **built through rather than deferred**: the
  fork's branch is visible (`tof-cleanroom-20260923`); **decided 2026-09-24: held until magnetic
  closes**, then cut T-1, T-2/T-3, T-5; **amended 2026-10-08: T-1 (axis, readers) cut as
  [1927](wp/1927-tof-t1-the-axis-and-its-readers.md)**, closed 2026-10-23 with T-2's inheritance in its Context; the rest still waiting, with #442 (a bank's CW
  width rows) decided inside T-1, and #618 (Mantid's instrument values: with provenance,
  never the files), and #1067 (TOF pulse shapes as a registry, after T-2/T-3) — and issue #362 lists the constant-wavelength reads
  (`CompiledModel.tt`, `line_wavelengths`, `sigma_measured`; `viz/snapshot.py` and
  23 more sites) a second compiled-model class meets, so the accessor seam it
  proposes waits for that class rather than preceding it; difference Fourier /
  maximum-entropy maps (McCusker §6; the partition input exists in `lebail_update`, the consumer is
  structure completion; #197); internal-standard and amorphous QPA; **modulated
  structures** (superspace — 1314 reads Jana's files without them; #258 the shared
  design, #678 its cut, N-W1 landed as PR #682; N-W2's group half and N-W3 cut 2026-10-16
  after T-1 merged, as [1992](wp/1992-nw2-magnetic-superspace-groups.md) and [1993](wp/1993-nw3-satellites-at-a-real-q.md)). **Magnetic structures left this fence 2026-09-02** for § Unscheduled's track (1326–1329); the incommensurate
  case, polarised neutrons and magnetic X-rays stay fenced (1327's non-goals).
  **Rigid bodies (#195), direct-space solution and stacking faults left it
  2026-09-28** for scoping in § Unscheduled (1514–1516; DESIGN.md has why); body TLS and the TOPAS rigid import stay (#759, 2026-10-16).
  **Spherical-harmonics texture (#131) left it 2026-10-14** as [1960](wp/1960-spherical-harmonics-texture.md).
- **Solution.** Charge flipping (#198; 1515 decides whether it follows, and
  #197 with it); search-match phase identification (#990 asked to unfence it; kept
  fenced 2026-10-16; prior art: the 36-cell screen at `guillemot-study:studies/guillemot/match_hl2.py`).
- **Indexing, fenced by 1018–1027.** Multi-phase indexing (index the residual
  after subtracting a solved phase); the full Bayesian extinction-symbol
  posterior (Markvardsen et al. 2001 — ΔBIC/Hamilton is the v1.0 form); a
  fourth engine in the Conograph lineage (Oishi-Tomiyasu's reversed/symmetric
  M_N *is* in scope, as a figure of merit); derivative-lattice ambiguity above
  index 4; the **low-symmetry real-data corpus** — NBS Monograph 25, public
  domain, DICVOL04's own test set, sourcing in 1043 § corpus; until it lands
  every scoreboard summary says "high-symmetry" out loud — and the
  SDPDRR-2/CONOGRAPH profile acquisitions; Boultif-Louër volume tightening
  (design in 1042 § Deferred).
- **Estimation.** Posterior sampling after a converged fit (Fancher et al. 2016,
  *Sci. Rep.* 6, 31625; issue #355, B-1…B-6 on its thread, gradient ≈ one
  forward evaluation under jax). **Stopped after B-3, decided 2026-10-02**: the
  Gaussian posterior sat within 0.84–1.05 of the uninflated esd on both vendored
  standards. It reopens on a fit where that ratio leaves 0.8–1.25, or on a
  posterior truncated at a physical bound.
- **Navigation.** From the QPA of a mixed-phase sample to the composition to
  make next (PICIP, Ritchie et al. 2025, *J. Chem. Inf. Model.* 65, 13226;
  issue #349, filed as v2+ by its author): a `rietx.navigate` subpackage on
  `indexing`'s pattern, the GPL reference implementation a test oracle only.
  Its three small asks — `PhaseQuantity.element_counts` exported, a
  weight-fraction covariance, `FitReport.unidentified_phase` — sit in 1942
  beside #212, which wants the same field.
- **I/O.** Rietica and XND readers (#196); an RMCProfile export and PDF /
  total-scattering analysis, X-ray and neutron (#192); VESTA import/export
  (#195).
- **Infrastructure.** No MCP server (dropped 2026-10-18, [DESIGN.md](DESIGN.md)
  § Locked decisions, scope discipline); `vmap`-batched in-situ series — the only accelerator story
  this hardware supports, sized by WP-0408 at break-even ≈50-65 k elements per
  kernel and a ceiling ≈2.5-3× ([v0.4 record](milestones/v0.4.md)); notebook
  widgets.
- **Not at any version:** 2D image integration (pyFAI's job — the package
  takes 1D patterns) and single-crystal refinement alone; joined to a powder pattern, v2+ (#1068).
