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

1. **Start** from "Current focus" below (or the WP the user names). Read that
   one WP file — self-contained on top of CLAUDE.md. Open DESIGN.md only at
   sections the WP links; do not read other WP files. `/wp-start` encodes
   this.
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
   between), Status line and the index-row glyph below synced, forward
   references pushed into the `### Inherited` of any affected WP that is not
   closed and not yours (a handover log reaches only your own successor on the
   same WP), the `Priority:` line of any WP your close unblocks or moots
   re-rated with the date and the reason and its index cell to match, rule 4
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
5. **WP closes** (✅/🛑): delete its `Priority:` line (cell to `—`), rewrite
   "Current focus" for the successor and MOVE the outgoing narrative to the
   **in-flight milestone record** (`milestones/vX.Y.md` § "How vX.Y is
   getting here"; when no milestone is open, the last shipped record's
   narrative). Current focus stays within `CURRENT_FOCUS_CAP` lines *and*
   `CURRENT_FOCUS_WORD_CAP` words (tests/test_docs_consistency.py) and
   repeats nothing a closed WP's own file already says.
6. **Milestone ships**: finish `milestones/vX.Y.md` with the measured
   acceptance block, flip the milestone row here, check README's claims.
   **Milestone opens**: bump `pyproject.version` to `1.x.0.dev0`, and write
   the record's Scope and Acceptance rows *at the open* — the v1.3 record says
   plainly that rows written at ship are the weaker evidence.
   **A break or a user-facing addition is staged in a record on the day it
   lands** — the open milestone's, or the last shipped one when none is open.
   The notes are written from the **tag range**, not from the milestone, and
   v1.4's pass found two changes shipping with no record entry behind them
   (v1.4 record § Appendix).

`tests/test_docs_consistency.py` enforces the mechanical parts: status
vocabulary and glyph sync, the index section matching each WP's `Milestone:`
line, status cells that carry a glyph and a date and nothing else, Inherited
placement, link resolution, and the size caps on this file and CLAUDE.md.

## Current focus

**[v1.6 — the magnetic structure](#v16--the-magnetic-structure) opened
2026-09-18** ([record](milestones/v1.6.md)), the day v1.5 shipped;
`pyproject.version` is `1.6.0.dev0` and the acceptance rows were written at the
open. Seven WPs — 1326-1329, 1343, 1418, 1419 — over a reference implementation
on the `mustachefeeling` fork.

**1418's M-6 and M-7 landed 2026-09-23** (PR #389, from outside), having no
forward-model contact. The order continues with 1327's verb, then 1419 as its own PR because the
two-lists decision it carries gets waved through in a diff about something
else. **Neutron TOF stays at [§ v2+](#v2--fenced)** behind issue #193.

**Eight silent-answer fixes have landed since the ship** (1434, 1435, 1432,
1342, 1415, 1442, 1414, 1454), staged in [releases/1.5.1.md](releases/1.5.1.md), narrated
in the [v1.6 record](milestones/v1.6.md). 1432 unblocks 1419's amplitudes; so
is the `.inp` grammar 1118 refuses,
[1433](wp/1433-the-inp-grammar-still-refused.md).

**1442 filed four WPs. [1446](wp/1446-a-supercell-that-outranks-the-truth.md)
measured its premise false**: the reversed members cannot order two fitted
candidates, so [1449](wp/1449-rank-on-what-the-screen-determined.md) inherits it
and brucite's xfail stands. Then [1445](wp/1445-the-optics-nobody-declared.md), needing a
schema decision first; [1447](wp/1447-a-threshold-each-pattern-sets-for-itself.md)
and [1448](wp/1448-a-number-somebody-chose.md) block nothing.

**Two cheap unowned asks** survive, both in 1407: a Stoe `.raw` paired with its
WinXPOW export, and a blank for a `rietx compare` standard.

**Queued, unscheduled** ([§ Unscheduled](#unscheduled)): the 2026-09-01
triage's 1312-1322 plus 1323 and 1325; the 2026-09-03 triage's 1332-1341 less
1333 and 1342; 1133; the **2026-09-15 triage**'s 1415-1421, less the two in v1.6 and 1432.

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
| v1.6 | The magnetic structure: the satellite, the moment, the determination, the mode amplitude — [§ v1.6](#v16--the-magnetic-structure) | 🔄 **opened 2026-09-18** ([record](milestones/v1.6.md)) | eleven rows written at the open, the record's § Acceptance; the measured half is still to come |
| v2+ | FPA (with the peaks buffer), neutron TOF, texture, modulated structures, PDF, MCP server — [§ v2+](#v2--fenced) | ⬜ fenced | — |

## Work packages

**Numbering.** A WP number is `MMNN`: the block of the milestone it was
*opened for*, then a sequence number. The number never changes when the WP
moves — 1101–1103 opened for v1.1 and are queued for v1.4, 1069–1078 ran past
v1.0's ship — so the **`Milestone:` line in the WP file is the authority** on
where a WP stands, and the section it sits under here mirrors that line (a
test asserts it). An unscheduled WP takes the next number in the newest
block (14xx today). A retired number is never recycled: 0603 moved to v0.4 as
0408 and stays empty. Status cells here carry the glyph and the date, nothing
else; the WP file's own Status line carries the summary.

**Priority.** Which WP the next session's tokens should go to, `P1` to
`P4`, on the tables of the open sections only. The WP file's `Priority:`
line is the authority (rubric, date and reason in `wp/TEMPLATE.md`; a test
holds the cell to it); a `—` is a WP in flight or closed, whose priority is
moot. Closing a WP re-rates the ones it unblocks or moots; the tier outranks
the order any paragraph here states.

Sections are in milestone order, the same as the table above. Depends cells
name hard dependencies; *soft* marks a preferred order.

### v0.3 — multi-phase workflows

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0301](wp/0301-wyckoff-constraints.md) | Wyckoff/site-symmetry constraints (affine p = C·θ + d) | ✅ 2026-07-22 | — |
| [0302](wp/0302-atomic-coordinates.md) | Atomic-coordinate refinement | ✅ 2026-07-23 | 0301 |
| [0303](wp/0303-anisotropic-adps.md) | Anisotropic ADPs | ✅ 2026-07-23 | 0301 |
| [0304](wp/0304-qpa-hill-howard.md) | QPA: Hill-Howard ZMV mass fractions | ✅ 2026-07-23 | — |
| [0305](wp/0305-brindley-microabsorption.md) | Brindley microabsorption | ✅ 2026-07-23 | 0304 |
| [0306](wp/0306-pawley-mode.md) | Pawley mode | ✅ 2026-07-23 | — |
| [0307](wp/0307-march-dollase.md) | March-Dollase preferred orientation | ✅ 2026-07-23 | — |
| [0308](wp/0308-multi-histogram.md) | Multi-histogram stacked residuals | ✅ 2026-07-24 | — |
| [0309](wp/0309-exporters.md) | Exporters: reflection table, CIF+esds (structure side landed in 0303), QPA table | ✅ 2026-07-24 | 0304 |
| [0310](wp/0310-acceptance-srm676a-qpa.md) | Acceptance: SRM 676a + IUCr QPA round robin | ✅ 2026-07-24 | 0304, 0305 |

### v0.4 — differentiable backends

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0401](wp/0401-backend-op-shim.md) | Backend op shim (34 named ops + `window_add`/`segment_sum`) + residual purity refactors | ✅ 2026-07-24 | — |
| [0402](wp/0402-jax-backend.md) | JAX backend: chunked jacfwd | ✅ 2026-07-24 | 0401 |
| [0403](wp/0403-cuda-mixed-precision.md) | Mixed-precision policy (CUDA-deferred, CPU-testable) | ✅ 2026-07-24 | 0402 |
| [0404](wp/0404-cross-backend-jacobian-ci.md) | Cross-backend Jacobian CI | ✅ 2026-07-24 | 0402 |
| [0405](wp/0405-faddeeva-voigt.md) | True Voigt via shared Faddeeva w(z) | ✅ 2026-07-24 | 0401 |
| [0406](wp/0406-restraint-penalty-rows.md) | Restraint penalty rows | ✅ 2026-07-24 | — |
| [0407](wp/0407-esd-reconciliation.md) | esd reconciliation (Bérar-Lelann placement) | ✅ 2026-07-24 | — |
| [0408](wp/0408-torch-mps-backend.md) | torch backend (MPS fp32 forward) — was 0603 | ✅ 2026-07-27 | 0401, 0402, 0404 |

### v0.5 — corrections & microstructure

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0501](wp/0501-absorption-corrections.md) | Capillary (cylindrical) absorption | ✅ 2026-07-27 | — |
| [0502](wp/0502-surface-roughness.md) | Surface roughness (Suortti + Pitschke) | ✅ 2026-07-27 | — |
| [0503](wp/0503-stephens-anisotropic-strain.md) | Stephens anisotropic strain | ✅ 2026-07-27 | — |
| [0504](wp/0504-anomalous-scattering-xraydb.md) | Anomalous f′,f″ (bundled Cromer-Liberman, not xraydb) | ✅ 2026-07-27 | — |
| [0505](wp/0505-sequential-refinement.md) | SequentialRefinement warm start | ✅ 2026-07-28 | — |
| [0506](wp/0506-secondary-extinction.md) | Secondary extinction (Sabine) | ✅ 2026-07-23 | — |
| [0507](wp/0507-anode-wavelengths.md) | Additional anode wavelengths (Co/Cr/Fe/Mo/Ag) | ✅ 2026-07-28 | — |
| [0508](wp/0508-flat-plate-absorption.md) | Flat-plate absorption + real-data capillary acceptance | ✅ 2026-07-28 | 0501 |

### v0.6 — solver, performance & agents

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0601](wp/0601-bounded-lm-solver.md) | TOPAS-style bounded LM | ✅ 2026-07-28 | — |
| [0602](wp/0602-agent-json-surface.md) | Agent JSON surface hardened (deleted by 1303) | ✅ 2026-07-29 | — |
| [0604](wp/0604-theory-manual.md) | Sphinx + MyST theory manual | ✅ 2026-07-29 | — |
| [0605](wp/0605-batched-peak-loop.md) | Batched peak loop (spike, then decide) | ✅ 2026-07-28 | — |

### v1.0 — hardening, human GUI, indexing, API freeze, PyPI

Six sets; the ordering arguments are in the [v1.0 record](milestones/v1.0.md).
The freeze (1003) ran last so it covered a surface the GUI and indexing had
exercised; the renames ran early because the freeze covers names that embed
the brand.

#### Platform, release and the repo's own process

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1001](wp/1001-validation-matrix.md) | Validation matrix + tolerance policy | ✅ 2026-07-29 | — |
| [1002](wp/1002-ci-matrix.md) | CI matrix | ✅ 2026-07-29 | — |
| [1003](wp/1003-api-freeze-pypi.md) | API freeze + PyPI | ✅ 2026-08-16 | 1001, 1002, 1004–1036 except 1017; 1067 § Floor |
| [1031](wp/1031-docs-consolidation.md) | Planning-doc consolidation + handoff mechanization | ✅ 2026-07-31 | — |
| [1060](wp/1060-docs-ci-consolidation.md) | Docs/CI consolidation: trim what the evidence indicts | ✅ 2026-08-06 | — |
| [1061](wp/1061-workflow-robustness.md) | Session-workflow robustness: detect the missed handover | ✅ 2026-08-06 | — |

#### The human GUI

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1004](wp/1004-parameter-plan-api.md) | Parameter & plan API surface | ✅ 2026-07-30 | — |
| [1005](wp/1005-project-container.md) | Project container (`.rex/`) | ✅ 2026-07-30 | 1004 |
| [1006](wp/1006-run-control.md) | Run control: streaming, progress, cancellation | ✅ 2026-07-30 | — |
| [1007](wp/1007-capabilities-guards.md) | Capabilities, structured guards, background export | ✅ 2026-07-30 | 1004 |
| [1008](wp/1008-gui-server.md) | GUI server, session model, `rietx gui` | ✅ 2026-07-30 | 1004–1007 |
| [1009](wp/1009-textdoc-format.md) | Project text document (`.rxt`): format + parser | ✅ 2026-07-30 | 1004, 1005 |
| [1010](wp/1010-frontend-scaffold.md) | Frontend scaffold: build, committed dist, shell, plot, console | ✅ 2026-07-30 | 1008 |
| [1011](wp/1011-parameter-plan-editors.md) | Parameter editor, plan editor, run controls, disclosure | ✅ 2026-07-30 | 1010 |
| [1012](wp/1012-history-report-panel.md) | History worktree, report panel, one-click suggestions | ✅ 2026-07-30 | 1010 |
| [1013](wp/1013-text-pane-sync.md) | Text pane (CodeMirror 6) + two-way sync | ✅ 2026-07-30 | 1009, 1010 |
| [1014](wp/1014-import-structure-editing.md) | Import & in-GUI structure/instrument editing | ✅ 2026-07-30 | 1008, 1010 |
| [1015](wp/1015-structure-viewer.md) | Structure viewer, zero new dependencies | ✅ 2026-07-30 | 1010 (1014 soft) |
| [1016](wp/1016-sequential-series-panel.md) | Sequential series panel | ✅ 2026-08-05 | 1008, 1010, 1011 |
| [1029](wp/1029-gui-usability.md) | GUI usability: legibility, layout, colour, theming | ✅ 2026-07-31 | 1010–1015 |
| [1032](wp/1032-gui-repairs.md) | GUI repairs found by use (tooltips, ticks, curves, gestures, field help) | ✅ 2026-08-05 | 1010–1015, 1027, 1029 |
| [1033](wp/1033-plot-range-regions.md) | 2θ limits and excluded regions, visible and selectable | ✅ 2026-08-05 | 1032, 1005, 1009 |
| [1034](wp/1034-panel-layout.md) | Model and Text in the right panel | ✅ 2026-08-05 | 1013, 1014, 1029 (1032 soft) |
| [1035](wp/1035-symmetry-surfaced.md) | Symmetry, surfaced and editable | ✅ 2026-08-05 | 1036, 1014 (1004 soft) |
| [1044](wp/1044-gui-view-cursor-theme.md) | GUI defects found by use: the view, the armed cursor, the theme | ✅ 2026-08-06 | 1029, 1032–1033, 1027 |
| [1075](wp/1075-static-panel-conventions.md) | The static panel takes the house figure conventions | ✅ 2026-08-16 | — |

#### Indexing

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1018](wp/1018-peak-picking.md) | Peak picking: detection + full per-peak profile fitting | ✅ 2026-07-30 | — |
| [1019](wp/1019-indexing-data-quality.md) | Data-quality gate and the systematic-error model | ✅ 2026-07-30 | 1018 |
| [1020](wp/1020-indexing-core.md) | Indexing core: Q-space, reduction, Bravais, FoM panel, ambiguity | ✅ 2026-07-30 | 1018 (1019 soft) |
| [1021](wp/1021-engine-dichotomy.md) | Engine A — successive dichotomy | ✅ 2026-07-30 | — |
| [1022](wp/1022-engine-trial-error.md) | Engine B — index-heuristic trial and error | ✅ 2026-07-30 | — |
| [1023](wp/1023-engine-montecarlo.md) | Engine C — whole-profile Monte Carlo (spike, then decide) | 🛑 2026-07-30 | — |
| [1024](wp/1024-indexing-consensus.md) | Consensus, `index_pattern`, Le Bail validation, agent & CLI | ✅ 2026-07-30 | 1021–1023 |
| [1025](wp/1025-extinction-symbol.md) | Extinction symbol / space-group determination | ✅ 2026-07-30 | 1024 |
| [1026](wp/1026-indexing-acceptance.md) | Acceptance: bethanechol benchmark + known cells | ✅ 2026-08-08 | 1024 (1025 soft) |
| [1027](wp/1027-gui-peak-picker.md) | GUI peak picker + indexing panel | ✅ 2026-08-01 | 1010, 1011, 1018–1024 |
| [1030](wp/1030-engine-scaling-low-symmetry.md) | Engine cost at low symmetry + the two missing figures of merit | ✅ 2026-07-31 | 1020–1022 (1026 soft) |
| [1037](wp/1037-indexing-time-ceiling.md) | Indexing: a stated time ceiling and honest progress | ✅ 2026-08-04 | 1024 (1021, 1022 soft) |
| [1038](wp/1038-shift-reflection-pairs.md) | Pre-indexing 2θ shift from reflection pairs | ✅ 2026-08-04 | 1019, 1024 |
| [1039](wp/1039-search-line-count.md) | Which lines a search is driven by (was: how many) | ✅ 2026-08-05 | 1037 (1038 soft) |
| [1040](wp/1040-engine-svd-index.md) | Engine C (second attempt): SVD-Index | ✅ 2026-08-05 | 1020, 1024 (1038 soft) |
| [1041](wp/1041-indexing-benchmark-gallery.md) | The indexing benchmark gallery | ✅ 2026-08-05 | 1026 |
| [1042](wp/1042-anytime-results-quick-default.md) | Anytime results, and `quick` as the default | ✅ 2026-08-07 | 1037 |
| [1043](wp/1043-agent-and-human-indexing.md) | Indexing for an agent and for a human: report, don't refuse | ✅ 2026-08-07 | 1041, 1026 (1028 soft) |
| [1045](wp/1045-indexing-search-controls.md) | Indexing search controls: one surface for the GUI and the agent | ✅ 2026-08-08 | 1027, 1042 (1043 soft) |
| [1046](wp/1046-candidate-cap-before-ranking.md) | The per-engine candidate cap decides the ranking | ✅ 2026-08-09 | 1024 (1026 soft) |

#### Found by use

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1028](wp/1028-robustness-external-data.md) | Robustness on data and CIFs we did not author | ✅ 2026-08-07 | — (1007 soft) |
| [1036](wp/1036-crystal-system-settings.md) | Crystal-system cell ties: the settings the tables do not check | ✅ 2026-08-04 | — |
| [1047](wp/1047-vendor-pattern-formats.md) | Vendor pattern formats: read the files labs actually have | ✅ 2026-08-09 | 1005, 1007, 1014 (1009, 1028 soft) |

#### Report evidence, agent evals, and the rename

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1050](wp/1050-suggest-next-parameter.md) | `Refinement.suggest()`: which parameter to free next | ✅ 2026-08-08 | — |
| [1051](wp/1051-sequential-escalation.md) | Sequential escalation ladder + chain hygiene | ✅ 2026-08-09 | — |
| [1052](wp/1052-report-loop-eval.md) | Closed-loop FitReport usefulness eval (mechanical) | ✅ 2026-08-11 | — |
| [1053](wp/1053-agent-in-the-loop-eval.md) | Agent-in-the-loop report eval (refine_json) | ✅ 2026-08-11 | 1052 |
| [1054](wp/1054-abstained-branch-honesty.md) | Layer-2 honesty on the abstained branch (phantom-phase invitation) | ✅ 2026-08-12 | — |
| [1055](wp/1055-background-evidence.md) | Background evidence in the FitReport | ✅ 2026-08-12 | — |
| [1056](wp/1056-identifiability-layer.md) | Identifiability layer: correlations, soft modes, held-parameter exchangeability | ✅ 2026-08-12 | — |
| [1057](wp/1057-purpose-grade-evidence.md) | Purpose-grade evidence: Le Bail gap + protocol stopping criteria | ✅ 2026-08-12 | — |
| [1058](wp/1058-report-delivery.md) | Report delivery: the per-stage report trajectory | ✅ 2026-08-13 | — |
| [1059](wp/1059-eval-round-two.md) | Agent eval round 2: protocol v1.1 re-A/B | ✅ 2026-08-13 | 1054, 1056, 1057, 1058 |
| [1062](wp/1062-rename.md) | Rename the project to `anatase` (superseded by 1066) | ✅ 2026-08-12 | — |
| [1063](wp/1063-exchange-clause-and-rivals.md) | Fit-level exchange clause + `compare_rivals`: name the swap, ship the experiment | ✅ 2026-08-13 | 1056, 1059 |
| [1064](wp/1064-eval-round-three.md) | Agent eval round 3: measured epistemic truth, decision-grade scorer, python arm | ✅ 2026-08-13 | 1063 |
| [1065](wp/1065-decisive-swap-license.md) | What a decisive swap licenses: the follow-through sentence, measured on the row it failed | ✅ 2026-08-13 | 1063, 1064 |
| [1066](wp/1066-rename.md) | Rename the project to `rietx` | ✅ 2026-08-14 | 1062 |

#### The McCusker (1999) compliance set

The WP-1068 audit ([v1.0 record](milestones/v1.0.md) § Appendix): no
correctness defect, nine gaps — six WPs here, difference Fourier fenced to v2+,
the divergence-slit correction declined in the audit itself. 1068 itself is the
manual's second pass, which produced the audit.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1068](wp/1068-manual-second-pass.md) | Part 1 second pass: voice, figures, structure | ✅ 2026-08-15 | 1067 |
| [1069](wp/1069-structure-r-factors.md) | R_Bragg and R_F, and the stated esd method | ✅ 2026-08-15 | — |
| [1070](wp/1070-user-facing-constraints.md) | User-facing constraints: ties on the Refinement surface | ✅ 2026-08-15 | 1004 |
| [1071](wp/1071-data-support-checks.md) | Effective observations and steps per FWHM | ✅ 2026-08-15 | — |
| [1072](wp/1072-geometry-table.md) | Interatomic geometry, esds from the full covariance | ✅ 2026-08-15 | — |
| [1073](wp/1073-capillary-displacement.md) | Capillary sample displacement, eq (4) | ✅ 2026-08-15 | — |
| [1074](wp/1074-restraint-weight-schedule.md) | Restraint weight schedule (c_w) | ✅ 2026-08-16 | 0406 |

### v1.0.x — after the ship, published in 1.1.0

The 1.0.x road: the manual's remaining chapters, the honesty pass they exposed,
the extinction screen's wrong evidence, and indexing declared provisional.
Written as 1.0.2, never published, folded into 1.1.0 on 2026-08-23
([releases/1.0.2.md](releases/1.0.2.md) says so). 1067 declared the GUI's
original beta status; **its § Floor gated 1003**, the rest landed here.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1067](wp/1067-user-api-manual.md) | User & API manual (Part 1), beside the theory manual (Part 2) | ✅ 2026-08-18 | 0604, 1004–1007, 1047 |
| [1076](wp/1076-result-row-honesty.md) | A result row's unwritten fields: `at_bound` and `initial` | ✅ 2026-08-18 | 1067 |
| [1077](wp/1077-extinction-refutes-certified-class.md) | The extinction screen refutes a certified class (corundum R -3 c), and no row covers the shape | ✅ 2026-08-18 | — |
| [1078](wp/1078-indexing-provisional.md) | Indexing is provisional, and every surface says so | ✅ 2026-08-18 | 1067 |

### v1.1 — refinement speed

Measure first (1111), then the exact wins (1109), the batched Jacobian path
(1112), the evaluation-count front (1113), the algorithmic tier (1114), a gated
compiled tier (1115), and what each opened; targets and the opening baseline
in the [v1.1 record](milestones/v1.1.md) § Acceptance. The milestone also
carried the agentic-report set, the compatibility promise, two process WPs
and constant-wavelength neutron.

#### Speed

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1109](wp/1109-refinement-speed.md) | Refinement speed: where the time actually goes | ✅ 2026-08-20 | — |
| [1111](wp/1111-benchmark-harness.md) | The refinement benchmark harness, and the trigger-shaped case | ✅ 2026-08-20 | — |
| [1112](wp/1112-batched-derivative-bases.md) | The batched derivative side, and η-aware windows | ✅ 2026-08-21 | 1111 |
| [1113](wp/1113-evaluation-count.md) | Evaluation count: name the mechanism, then attack it | ✅ 2026-08-21 | 1111 (soft) |
| [1114](wp/1114-peaks-buffer-spike.md) | Peaks-buffer spike: shape reuse across 2θ | ✅ 2026-08-21 | 1112 |
| [1115](wp/1115-compiled-kernel-spike.md) | Compiled-kernel spike (gated) | ✅ 2026-08-22 | 1112, 1114 |
| [1120](wp/1120-batched-residual.md) | Batch the residual: the forward's un-taken WP-1112 win | ✅ 2026-08-22 | 1112 |
| [1121](wp/1121-per-reflection-cost.md) | The per-reflection front: what a compiled tier does not reach | ✅ 2026-08-22 | 1115 |
| [1122](wp/1122-compiled-peaks-buffer.md) | Compiled peaks buffer: the declared-tolerance tier | 🛑 2026-08-22 | 1115, 1121 (gate) |
| [1123](wp/1123-fast-tolerance-default.md) | The fast tolerance schedule, on by default | ✅ 2026-08-22 | 1113 |
| [1124](wp/1124-warm-series-continuation.md) | Warm-series continuation probe: seed the chain along its tangent | ✅ 2026-08-22 | 1111, 1123 |
| [1125](wp/1125-varpro-probe.md) | Variable-projection probe: profile the background, measure the tail | ✅ 2026-08-22 | 1113 |
| [1127](wp/1127-ladder-first-rung.md) | The ladder's first rung: which one a warm pattern starts on | ✅ 2026-08-23 | 1111, 1124, 1051 |
| [1128](wp/1128-prior-seed-before-the-gate.md) | The prior's deliberate trial runs before the ladder's gate | ✅ 2026-08-23 | — |
| [1129](wp/1129-absent-phase-support-is-a-flat-direction.md) | The absent phase's support is a flat direction, not a number | ✅ 2026-08-23 | 1110, 1123 |

#### The agentic report

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1104](wp/1104-agent-protocol-literature-audit.md) | Literature-grounding audit of AGENT_PROTOCOL.md | ✅ 2026-08-18 | — |
| [1105](wp/1105-agent-protocol-hygiene.md) | AGENT_PROTOCOL hygiene: stale claims out, vocabularies covered | ✅ 2026-08-19 | 1104 |
| [1106](wp/1106-report-placement-fields.md) | Report placement fields: structured where prose was load-bearing | ✅ 2026-08-19 | — |
| [1107](wp/1107-eval-placement-round.md) | Eval protocol 2.2: the placement round | ✅ 2026-08-19 | 1105, 1106 |
| [1108](wp/1108-license-statistics-placement.md) | The license beside the numbers: shipping the statistics placement | ✅ 2026-08-19 | 1107 |
| [1110](wp/1110-agent-surface-friction.md) | The agent surface, measured against an agent that used it | ✅ 2026-08-21 | — |

#### The promise, the manual, the process, and neutron

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1116](wp/1116-session-protocol-hygiene.md) | Session-protocol hygiene: the scan that cried wolf | ✅ 2026-08-20 | — |
| [1117](wp/1117-compatibility-promise.md) | The compatibility promise, rewritten for the users there are | ✅ 2026-08-21 | — |
| [1126](wp/1126-manual-style-pass.md) | Manual Part 1: the style pass the review asked for | ✅ 2026-08-22 | 1067, 1068 |
| [1134](wp/1134-constant-wavelength-neutron.md) | Constant-wavelength neutron: b, lambda/n harmonics, a refinable wavelength | ✅ 2026-08-25 | — |

### v1.2 — the GUI for a crystallographer

The maintainer's use notes, triaged: the style system first, the manual last,
and between them one WP per cause found in the code. Order is the table's;
the per-note assessment and the decisions are the
[v1.2 record](milestones/v1.2.md) § Scope. 1017 (opened for v1.0, deferred by
1003) closed the milestone and lifted the GUI's beta.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1201](wp/1201-gui-house-style.md) | GUI house style: tokens and registers | ✅ 2026-08-25 | — (first) |
| [1204](wp/1204-developer-mode-example-projects.md) | Developer mode and example projects | ✅ 2026-08-25 | — (1201 soft) |
| [1202](wp/1202-help-corpus.md) | The help corpus, served and meta-tested | ✅ 2026-08-25 | — |
| [1203](wp/1203-help-popover.md) | The help popover: one mechanism across the panels | ✅ 2026-08-26 | 1201, 1202 |
| [1205](wp/1205-new-project-open-browse-defaults.md) | New project: open any project, browse, sensible defaults, the wizard bug | ✅ 2026-08-26 | 1201, 1203, 1204 |
| [1206](wp/1206-typed-cell-project.md) | A project without a CIF, part 1: a typed cell | ✅ 2026-08-26 | 1205 |
| [1207](wp/1207-pattern-only-project.md) | A project without a CIF, part 2: pattern-only projects | ✅ 2026-08-26 | 1206 |
| [1208](wp/1208-plan-introduction.md) | Plan panel: the gentle introduction | ✅ 2026-08-27 | 1203 |
| [1209](wp/1209-peaks-table-numbers-flags.md) | Peaks table: numbers, columns, flags | ✅ 2026-08-27 | 1201, 1203 |
| [1210](wp/1210-peak-layer-identity.md) | The peak layer: hide it, tell it apart, data-only | ✅ 2026-08-27 | 1201 |
| [1211](wp/1211-candidate-overlay.md) | Indexing candidates on the plot | ✅ 2026-08-27 | 1210 |
| [1212](wp/1212-redraw-never-moves-axes.md) | A redraw never moves the axes | ✅ 2026-08-27 | 1210 |
| [1213](wp/1213-hover-readout.md) | The hover readout | ✅ 2026-08-27 | 1212 |
| [1214](wp/1214-model-vary-and-profile-save.md) | Model: vary in the editor, and save instrument profile | ✅ 2026-08-28 | 1201 |
| [1215](wp/1215-structure-table.md) | Model: the structure table | ✅ 2026-08-28 | 1214 |
| [1216](wp/1216-instrument-form.md) | Model: the instrument form | ✅ 2026-08-28 | 1214 |
| [1217](wp/1217-history-graph-compare.md) | History: the graph and the compare table | ✅ 2026-08-28 | 1201 |
| [1017](wp/1017-gui-manual-onboarding.md) | GUI manual, in-app help anchors, and the sync mechanism | ✅ 2026-08-28 | 1201–1217 (last) |

### v1.3 — agents and programs

The agent-facing surface refactored against two measured runs, which said the
only agents are shell-equipped sessions using the notebook API, and that none of
six refining runs stopped on a package criterion. The baseline numbers are in
[1307](wp/1307-recapture-round-1-1.md) and the [v1.3 record](milestones/v1.3.md).

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1301](wp/1301-hold-unsupported-phase.md) | An unsupported phase is held for the stage, never bounded | ✅ 2026-08-28 | — (first) |
| [1302](wp/1302-error-is-documentation.md) | The error is the documentation; the output is bounded; the result is a termination view | ✅ 2026-08-29 | — (1305 b soft) |
| [1303](wp/1303-retire-refine-json.md) | Retire `refine_json` and the schema export | ✅ 2026-08-29 | — |
| [1304](wp/1304-protocol-as-skill.md) | The protocol is a skill | ✅ 2026-08-29 | 1303 |
| [1305](wp/1305-series-deliverable.md) | The series deliverable, and the checks the agent ran by hand | ✅ 2026-08-29 | 1304 |
| [1306](wp/1306-powderline-recipe.md) | PowderLine recipe: the interchange format rietx did not have to invent | ✅ 2026-08-29 | — (1303 soft) |
| [1307](wp/1307-recapture-round-1-1.md) | Re-capture: surface round protocol 1.1 | ✅ 2026-08-29 | 1301–1305 (last) |
| [1308](wp/1308-skill-documents-its-doors.md) | The skill documents its own doors | ✅ 2026-08-30 | 1304, 1306, 1307 |

### v1.4 — free-standing peaks

Peaks without a structure: fitted standalone (1101), and the
`Instrument.extra_components` union seam — the serializable answer to TOPAS's
fit_obj — with broad humps (1102) and sharp peaks (1103) as its first members.
Opened for v1.1, shifted three times (2026-08-20, -25, -28), numbers kept.
The ship pass also deleted the `AGENT_PROTOCOL.md` pointer
([1304](wp/1304-protocol-as-skill.md) kept it for one release), at four sites
rather than the three the record scoped.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1101](wp/1101-standalone-peak-fitting.md) | fit_peaks: standalone peak fitting at named positions | ✅ 2026-09-13 | — |
| [1102](wp/1102-component-seam-humps.md) | The additive component seam + broad humps | ✅ 2026-09-13 | — |
| [1103](wp/1103-peak-components.md) | Sharp extra peaks: the second component member | ✅ 2026-09-13 | 1102 (the seam) |

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

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1401](wp/1401-a-window-into-a-run.md) | A window into a run: find the runs that already exist | ✅ 2026-09-14 | — |
| [1402](wp/1402-the-picture-costs-megabytes.md) | The live picture costs megabytes a stage, and the fit pays it | ✅ 2026-09-15 | 1401 |
| [1403](wp/1403-a-run-nobody-asked-to-record.md) | A run nobody asked to record | ✅ 2026-09-15 | 1401, 1402 |
| [1404](wp/1404-what-recording-every-fit-costs.md) | What recording every fit costs | ✅ 2026-09-15 | 1403 (1401 baseline) |
| [1405](wp/1405-the-human-stops-the-run.md) | The human stops the run | ✅ 2026-09-15 | 1403 (1401 soft) |
| [1406](wp/1406-say-that-the-fit-writes-to-disk.md) | Say that the fit writes to disk | ✅ 2026-09-15 | 1403, 1405 (1402 soft) |
| [1413](wp/1413-the-snapshot-is-what-recording-costs.md) | The snapshot is what recording costs | ✅ 2026-09-15 | 1404, 1402 |
| [1423](wp/1423-a-page-that-holds-still.md) | A page that holds still | ✅ 2026-09-16 | 1405, 1402 |
| [1430](wp/1430-the-page-is-a-file.md) | The page is a file | ✅ 2026-09-16 | 1423 |
| [1426](wp/1426-still-under-resize-and-across-a-stage.md) | Still under resize, and across a stage | ✅ 2026-09-16 | 1430, 1423 |
| [1424](wp/1424-a-row-that-names-its-run.md) | A row that tells its run apart, and a number that fits its slot | ✅ 2026-09-16 | 1430 (1423 soft) |
| [1431](wp/1431-a-caller-names-its-run.md) | A caller names its run | ✅ 2026-09-16 | 1424 |
| [1425](wp/1425-the-panels-are-the-readers-to-size.md) | The panels are the reader's to size | ✅ 2026-09-16 | 1430, 1426 |
| [1429](wp/1429-one-palette-and-one-theme-for-three-pages.md) | The GUI's tokens and the GUI's theme, on the two python pages | ✅ 2026-09-16 | 1430 (1426 soft) |
| [1427](wp/1427-what-a-poll-costs.md) | What a poll costs | ✅ 2026-09-17 | 1430 (1426 soft) |
| [1428](wp/1428-open-in-the-gui-without-touching-the-fit.md) | Open in the GUI, without touching the fit | ✅ 2026-09-17 | 1405, 1401 (1430 soft) |
| [1438](wp/1438-the-questions-the-track-left.md) | The questions the track left | ✅ 2026-09-17 | 1429, 1427, 1425, 1413 (1428 soft) |
| [1439](wp/1439-windows-red-since-every-fit-records-itself.md) | Windows, red since every fit started recording itself | ✅ 2026-09-17 | — (1403, 1404 turned it red) |

#### Coming from another code

The largest single WP in the range at 83 commits; the grammar its reader still
refuses is 1433, unscheduled.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1118](wp/1118-foreign-model-files.md) | Foreign model files: read a refinement in, write one back | ✅ 2026-09-16 | — |

#### The fit has no reference

The blank the beamline scanned, with a refinable scale and its own esds
(issue #171); its sibling 1130 stays 🛑 in § Unscheduled.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1309](wp/1309-measured-background.md) | A measured background: the container exists, the scale and the esds do not | ✅ 2026-09-17 | — |

#### What the package says about itself

Corrections to what the package says of itself, the titles below saying which.
The symbol audit (1436, 1437) found `help.py` printing an Lp 0.508× from the
one the code computes; 1440 is the milestone itself.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1310](wp/1310-report-repeats-itself.md) | The report repeats itself: stage dedup, the declared wavelength, the empty column | ✅ 2026-09-16 | — |
| [1411](wp/1411-a-manual-that-links-home.md) | A manual that links home: the landing copy, and the brand on furo's sidebar | ✅ 2026-09-14 | — |
| [1412](wp/1412-the-theme-nobody-chose.md) | The theme nobody chose | ✅ 2026-09-14 | 1411 |
| [1422](wp/1422-the-wp-two-sessions-picked.md) | The WP two sessions picked | ✅ 2026-09-15 | 1061, 1410 |
| [1436](wp/1436-k-is-the-wavevector-everywhere-else.md) | `k` is the wavevector everywhere else | ✅ 2026-09-17 | 1437 |
| [1437](wp/1437-a-formula-the-code-does-not-compute.md) | A formula the code does not compute | ✅ 2026-09-17 | — |
| [1440](wp/1440-ship-v1-5.md) | Open v1.5 over the body that landed without it, and ship it | ✅ 2026-09-18 | 1439 |

### v1.5.x — after the ship

Work landing while no milestone is open, staged in
[releases/1.5.1.md](releases/1.5.1.md) the day it lands, because v1.4's ship
pass found two changes that had shipped with no record entry behind them. The
1.0.x road is the precedent, ending included: written as a patch, folded into
the next minor if one opens first.

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

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1311](wp/1311-walking-parameter-bounds.md) | Bounds and flags for the remaining walking parameters | ✅ 2026-09-18 | — |
| [1441](wp/1441-a-constraint-the-series-can-declare.md) | A constraint the series can declare | ✅ 2026-09-18 | — (1070, 1119 are the halves) |
| [1435](wp/1435-a-hold-the-caller-declares.md) | A hold the caller declares, which a plan may not quietly override | ✅ 2026-09-18 | — (1070 is the shape) |

### v1.6 — the magnetic structure

Seven rungs, opened 2026-09-18 ([record](milestones/v1.6.md)), out of
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

**The order, set in #286 on 2026-09-16 and 2026-09-18.** 1418's M-6 and M-7
first, having no forward-model contact; then 1327's verb, one PR; M-9 with
1418; then 1419 alone, because the decision it carries — the full child group
for reflection generation, multiplicity and the metric, the ε-reduced
stabiliser only for orbit expansion of the mode field — gets decided properly
in a PR that is about it and waved through in one that is not. Refined in
#286 on 2026-09-25: PR #448 (the operation-list phase) and the k ≠ 0
supercell follow 1327's model. Then 1326, which needs neither; 1328 once #448
is in, so it opens complete; then 1343 and 1329. M-9 waits for the supercell
and 1328. Every magnetic
row in the agent skill, diagnostic codes included, goes in
`references/magnetic.md`, and the merge result of the whole set is measured
once before the first PR is cut.

**Neutron TOF is not here.** It stays fenced at [§ v2+](#v2--fenced) behind
issue #193, which its own reporter filed that way. A fence moves by a recorded
decision, the way magnetic structures left it on 2026-09-02, and not by work
existing.

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1326](wp/1326-satellites-without-a-moment.md) | Satellites at G ± k, with no moment model: is it magnetic? | 🔄 2026-09-26 | P2 | — |
| [1327](wp/1327-magnetic-structure.md) | A magnetic structure: state it, refine it, report what the powder cannot see | 🔄 2026-09-26 | P2 | 1326 |
| [1328](wp/1328-magnetic-interchange.md) | Magnetic interchange: magCIF in and out, and the readers stop refusing | 🔄 2026-09-27 | P3 | 1327 (1118 soft) |
| [1329](wp/1329-moment-in-a-series.md) | The moment in a series: the onset, the hold, the trajectory | ⬜ | P3 | 1327 (1326 soft) |
| [1343](wp/1343-the-moment-pays-for-the-width.md) | The magnetic peaks are broader, and the moment pays for it | ⬜ | P3 | 1327 (1326 soft) |
| [1418](wp/1418-the-magnetic-structure-is-determined.md) | The magnetic structure is determined, not only stated | 🔄 2026-09-25 | P2 | 1327 (1326 soft) |
| [1419](wp/1419-a-child-structure-refined-on-its-mode-amplitudes.md) | A child structure refined on its mode amplitudes | ⬜ | P3 | 1418 (1327 soft) |

### Unscheduled

Opened by evidence — an issue, an agent round, a measurement — and owned by no
milestone yet. Grouped by what the evidence says; each WP file carries it in
full, with the issues it closes. Most of the 13xx rows come from the
2026-09-01 issue triage (PRs #205, #213) and the day after; 1119, 1130 and
1133 are older; 1414–1420 are the 2026-09-15 triage's.

#### Coming from another code

What 1118 read and wrote (§ v1.5), continued. 1119 is the named variable such
a file's equations refer to; issue **#212**'s cross-phase linear restraint is
its first concrete ask, **has no WP and needs one cut** — seam written out in
[1325](wp/1325-parametric-series.md)'s `### Inherited`.

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1119](wp/1119-named-variables.md) | Named variables and equations: a `prm` of one's own | ✅ 2026-09-04 | — | — |
| [1314](wp/1314-mfile-reader.md) | A Jana2020 project reader: .m50/.m40/.m41 | ⬜ | P3 | — |
| [1319](wp/1319-structure-interchange.md) | Structure interchange: checkCIF conformance and a bare XYZ importer | ⬜ | P3 | — |
| [1433](wp/1433-the-inp-grammar-still-refused.md) | The `.inp` grammar the reader still refuses: `STR(...)` and `#if` | ⬜ | P3 | — |
| [1455](wp/1455-a-topas-tchz-profile-reads-in.md) | A TOPAS TCHZ profile reads in | ⬜ | P3 | — (1433 soft) |

#### The fit has no reference

A quantity derived sharing no assumption with the fit. 1309 shipped the other
half in § v1.5; 1130's own trigger stopped reproducing.

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1130](wp/1130-background-reference.md) | The fit has no reference: a background level it cannot argue with | 🛑 2026-09-04 | — | — |

#### The specimen is not an angle, and the neutron follow-through

Sample broadening was stored as a deg-2θ coefficient and shared across
histograms as though it were a specimen property; for **size** it is not (the
same crystallite broadens by a different angle at a different wavelength).
**1131 closed 2026-09-02**: a joint fit now shares the crystallite size and each
histogram carries its own coefficient (numbers in 1131), and every converged
fit reports a coherent domain size and a Δd/d with esds. The neutron rows follow 1134.

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1131](wp/1131-sample-broadening-is-a-specimen-property.md) | Sample broadening is a specimen property, not an angular coefficient | ✅ 2026-09-02 | — | — |
| [1133](wp/1133-diagnostic-names-its-view.md) | A diagnostic names the view that shows it | ⬜ | P3 | 1130 |
| [1132](wp/1132-neutron-specimen-absorption.md) | A neutron µR, from the table this package already ships | ⬜ | P3 | #108 |
| [1312](wp/1312-neutron-followthrough.md) | CW neutron follow-through: the seed, the resonant flag, the joint fit | ⬜ | P2 | — (1132 soft) |

#### What fires, and what stays silent

Each row is a silent wrong answer, the class the repo's rules are strictest
about; the titles below say which. Three triages feed it (2026-09-01, -03,
-15) plus the 2026-09-16 review of #286 and #293, which cut 1432 of 1342's
kind. The orbit that was not a multiplicity (1324) is closed and 1320 restates
what it measured. 1310 closed on four of six in § v1.5, and both of the two it
could not answer closed 2026-09-18 as **1434** (the bound flag) and **1435**
(a caller's hold), each file saying what changed.

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1320](wp/1320-qpa-multimodal-fraction.md) | A phase fraction the pattern cannot fix | ⬜ | P2 | — (1310 soft) |
| [1321](wp/1321-persisted-bounds-repair.md) | The bounds a Parameter field declared: repair and audit | ⬜ | P2 | — (PR #206 first) |
| [1323](wp/1323-lebail-stop-rule.md) | The Le Bail alternation has a stop rule, and a scope | ⬜ | P2 | — |
| [1324](wp/1324-symmetry-silences.md) | Symmetry silences: an orbit that is not a multiplicity, a setting nobody chose | ✅ 2026-09-02 | — | — |
| [1332](wp/1332-the-axis-a-reader-hands-back.md) | What a reader hands back: the axis, the rows, the σ column | ⬜ | P2 | — |
| [1336](wp/1336-the-fit-does-not-say-it-is-unusable.md) | The fit does not say it is unusable: the status channel and the width census | ⬜ | P2 | — (1310 soft) |
| [1337](wp/1337-an-authored-refusal-not-a-traceback.md) | An authored refusal, not a raw traceback | ⬜ | P3 | — (1311, 1321 soft) |
| [1342](wp/1342-a-freeze-that-reads-names.md) | A structural freeze that reads names, and the tie it cannot see | ✅ 2026-09-19 | — | — (1301, 1119 soft) |
| [1344](wp/1344-a-joint-fit-owes-each-histogram-its-diagnostics.md) | A joint fit owes each histogram the diagnostics its own radiation earns | ⬜ | P3 | — |
| [1414](wp/1414-a-turn-on-that-reached-nothing.md) | A `turn_on` that reached nothing says so | ✅ 2026-09-22 | — | — (1341 soft) |
| [1415](wp/1415-a-sigma-column-smaller-than-root-y.md) | A σ column smaller than √y | ✅ 2026-09-24 | — | — |
| [1417](wp/1417-delta-bic-at-powder-channel-counts.md) | ΔBIC at powder channel counts | ⬜ | P2 | — (1339 soft) |
| [1421](wp/1421-the-result-reproduces-its-own-number.md) | The result reproduces its own number | ⬜ | P3 | — (1310 soft) |
| [1432](wp/1432-a-tie-onto-a-rederived-dof.md) | A tie onto a coordinate DOF, re-applied once per write | ✅ 2026-09-19 | — | — (1119 soft) |
| [1434](wp/1434-the-bound-test-asks-the-wrong-question.md) | The bound test asks whether the value is near its limit, never whether the limit was binding | ✅ 2026-09-18 | — | — |
| [1442](wp/1442-a-ghost-search-at-chance.md) | A ghost search at chance: the Kβ flag fires where Kβ cannot exist | ✅ 2026-09-22 | — | — (1415 soft) |
| [1445](wp/1445-the-optics-nobody-declared.md) | The optics nobody declared: a source that cannot emit the line | ⬜ | P2 | — (1442 soft) |
| [1446](wp/1446-a-supercell-that-outranks-the-truth.md) | A supercell that outranks the truth, on evidence the panel already has | 🛑 2026-09-22 | — | — (1442 soft) |
| [1447](wp/1447-a-threshold-each-pattern-sets-for-itself.md) | A threshold each pattern sets for itself | ⬜ | P3 | — (1442 soft) |
| [1449](wp/1449-rank-on-what-the-screen-determined.md) | Rank on what the screen determined, not on what the peak list shows | ⬜ | P2 | — (1446 refuted the peak-list route) |
| [1454](wp/1454-auto-background-choices-survive-the-fit.md) | `auto_background`'s choices survive the fit | ✅ 2026-09-24 | — | — |
| [1456](wp/1456-an-editable-install-stamps-what-it-runs.md) | An editable install stamps what it runs | ⬜ | P2 | — |
| [1457](wp/1457-the-stage-rwp-leaves-out-the-declared-peaks.md) | The stage Rwp leaves out the declared peaks | ⬜ | P2 | — |
| [1458](wp/1458-a-tick-with-nothing-behind-it.md) | A tick with nothing behind it moves the low-angle boundary | ✅ 2026-09-24 | — | — (1327 soft) |
| [1460](wp/1460-one-degeneracy-one-finding.md) | One degeneracy, one finding | ⬜ | P3 | — (1454, 1302 soft) |
| [1463](wp/1463-a-phase-at-zero-withholds-every-esd.md) | A phase at zero withholds every esd | ⬜ | P2 | — (1320 soft) |
| [1465](wp/1465-a-width-that-became-background.md) | A phase width that became background, and an absorption screen that never ran | ⬜ | P2 | — |
| [1467](wp/1467-a-stephens-block-on-a-frozen-floor.md) | A Stephens block on a frozen floor, and a clamp the solver leans on | ⬜ | P2 | — (1318 soft) |

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

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1333](wp/1333-a-series-survives-one-pattern.md) | A series survives one pattern, and says which one it lost | ✅ 2026-09-26 | — | — (1317 soft) |
| [1334](wp/1334-the-stage-that-ran-out-of-budget.md) | The stage that ran out of budget | ⬜ | P3 | — |
| [1335](wp/1335-the-report-costs-more-than-the-fit.md) | The report costs more than the fit | ⬜ | P3 | — |
| [1420](wp/1420-a-held-phase-re-enters-or-says-it-cannot.md) | A held phase re-enters, or the chain says it cannot | ⬜ | P2 | — (1333, 1342, 1419 soft) |
| [1453](wp/1453-both-directions-name-the-lower-cost.md) | Both directions name the lower cost | ⬜ | P3 | — (1420 soft) |
| [1459](wp/1459-a-pawley-intensity-past-the-data.md) | A Pawley intensity past the end of the data | ✅ 2026-09-25 | — | — (1336 soft) |
| [1464](wp/1464-a-screen-reads-the-batch-references-first.md) | A screen reads the batch references first | ⬜ | P3 | — (PR #385 soft) |

#### One file, many patterns

The `scan=` idiom extended to containers (issues #134, #135): a plain zip of
patterns, and a NeXus/HDF5 in-situ reel behind the package's first
optional-dependency format.

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1315](wp/1315-zip-collection-reader.md) | A zip of patterns is N scans | ⬜ | P3 | — |
| [1316](wp/1316-hdf5-multiscan-reader.md) | A NeXus/HDF5 multi-scan reader, behind an extra | ⬜ | P3 | — |

#### The formats a lab still has

1047's declared follow-up, reopened by an ask for a PANalytical `.raw` that
does not exist (`.raw` is six unrelated vendors, none of them PANalytical).
1416, the positional `.xy` reader checking the shape of what it accepted
(issue #266), was folded into 1332 on 2026-09-24.

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1407](wp/1407-the-format-a-benchtop-still-writes.md) | The format a benchtop still writes: PANalytical `.udf`/`.rd`, and three named refusals | ✅ 2026-09-13 | — | — |
| [1416](wp/1416-read-xy-reads-the-files-shape.md) | `read_xy` reads the file's shape | 🛑 2026-09-24 | — | — |

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

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1317](wp/1317-series-scrubber.md) | Scrub the series along its own trace | ⬜ | P3 | — |
| [1318](wp/1318-strain-surface.md) | The Stephens strain surface, rendered | ⬜ | P3 | — |
| [1322](wp/1322-events-aggregator.md) | The run is instrumentable, and nothing says so | ⬜ | P3 | — |
| [1339](wp/1339-where-the-improvement-lives.md) | Where the improvement lives | ⬜ | P3 | — |
| [1340](wp/1340-qpa-on-a-molar-basis.md) | QPA on a molar basis, and the basis travels with the number | ⬜ | P3 | — (1320 soft) |
| [1341](wp/1341-a-joint-fit-has-no-report.md) | A joint fit has no report | ⬜ | P2 | — (1312, 1335, 1344 soft) |
| [1444](wp/1444-the-pattern-before-the-model.md) | The pattern before the model, and a title on the figure | ⬜ | P3 | — |
| [1461](wp/1461-every-browser-chart-draws-with-uplot.md) | Every browser chart draws with uPlot | ✅ 2026-09-26 | — | — |
| [1462](wp/1462-the-structure-viewer-draws-with-its-own-webgl2-renderer.md) | The structure viewer draws with its own WebGL2 renderer | ✅ 2026-09-26 | — | — (1461 soft) |
| [1466](wp/1466-the-structure-viewer-draws-coordination-polyhedra.md) | The structure viewer draws coordination polyhedra | ✅ 2026-09-26 | — | 1462 |
| [1468](wp/1468-what-the-polyhedra-still-miss.md) | What the polyhedra still miss, and the controls a chemist would reach for | ⬜ | P3 | 1466 |

#### The repo's own process

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1313](wp/1313-dist-belongs-to-main.md) | The GUI dist belongs to main | ⬜ | P4 | — |
| [1330](wp/1330-skill-references-by-shape.md) | The skill grows by reference: one file per task shape, and the row an agent can write | ✅ 2026-09-02 | — | 1304, 1308 |
| [1331](wp/1331-landing-page-in-repo.md) | The landing page enters the repository, and the data comes redacted | ✅ 2026-09-03 | — | — (1003 soft) |
| [1338](wp/1338-the-skills-own-gates.md) | The skill's own gates: the references, the private corpus, the cap race | ⬜ | P4 | — |
| [1408](wp/1408-the-manual-reads-like-a-manual.md) | The theory manual reads like a manual | ✅ 2026-09-14 | — | — |
| [1409](wp/1409-part-one-reads-like-a-manual.md) | Part 1 reads like a manual | ✅ 2026-09-14 | — | 1408 |
| [1410](wp/1410-worktree-gate-scope.md) | The worktree gate guards this checkout, not every repository | ✅ 2026-09-14 | — | — |
| [1443](wp/1443-part-one-read-by-a-newcomer.md) | Part 1 read by a newcomer: eleven passages, one word, and the version the manual describes | ⬜ | P3 | — (1409 is the shape) |
| [1448](wp/1448-a-number-somebody-chose.md) | A number somebody chose says so, and says where the argument is | ⬜ | P4 | — |
| [1450](wp/1450-a-collaborators-dataset-stays-unnamed.md) | A collaborator's dataset stays unnamed | 🔄 2026-09-24 | P1 | — |
| [1451](wp/1451-the-extinction-a-powder-has.md) | The extinction a powder has: primary, not secondary | ⬜ | P4 | — |
| [1452](wp/1452-spglib-to-moyo.md) | spglib to moyo, once | ⬜ | P3 | 1327, 1418, 1419 |

#### Candidates — named on a use case, not yet on a measurement

| WP | Title | Status | Priority | Depends on |
|---|---|---|---|---|
| [1325](wp/1325-parametric-series.md) | Parametric series: a parameter as a function of the series axis | ⬜ | P3 | — (1119 soft) |

### v2+ — fenced

Seams pre-built, implementations fenced out. **No WP files for v2+ on
purpose**: the fence is a scope-discipline decision
([DESIGN.md](DESIGN.md#locked-decisions)), and pre-writing packages invites
scope creep. Each item names what fenced it.

- **Physics.** Fundamental Parameters as a differentiable convolution stack
  (Cheary-Coelho 1992) — **with** the peaks buffer, never before
  ([1122](wp/1122-compiled-peaks-buffer.md) measured shape reuse below
  break-even without one); neutron **TOF** (CW landed in 1134; issue #193; the
  energy-dependent resonant absorption at S(Q), #113) — **built through
  rather than deferred**: the fork's branch is visible (`tof-cleanroom-20260923`),
  and **decided 2026-09-24: held until v1.6 closes**, then taken on that branch
  in its own cuts (T-1, T-2/T-3, T-5), with #442 (a bank's force-fixed CW width
  rows under 1414's "matched, not freed") going with T-1 — and issue #362 lists the constant-wavelength reads
  (`CompiledModel.tt`, `line_wavelengths`, `sigma_measured`; `viz/snapshot.py`
  and 23 more sites) a second compiled-model class meets, so the accessor seam
  it proposes waits for that class rather than preceding it; spherical-harmonics
  texture (Von Dreele 1997; #131); Z-matrices and rigid bodies (#195);
  difference Fourier / maximum-entropy maps (McCusker §6; the partition input
  exists in `lebail_update`, the consumer is structure completion; #197);
  internal-standard and amorphous QPA; **modulated structures** (superspace —
  1314 reads Jana's files without them; issue #258 holds the shared design
  for the nuclear and magnetic cases); **stacking faults** (DIFFaX-style
  recursion). Both were named 2026-09-01 as gaps a neutron-capable Rietveld
  code is asked for; no issue yet. **Magnetic structures left this fence
  2026-09-02** for § Unscheduled's track (1326–1329); the incommensurate
  case, polarised neutrons and magnetic X-rays stay fenced (1327's non-goals).
- **Solution.** Structure solution from an indexed cell; charge flipping
  (#198); search-match phase identification (prior art: the 36-cell screen at
  `guillemot-study:studies/guillemot/match_hl2.py`).
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
- **Estimation.** Posterior sampling after a converged fit (Fancher et al.
  2016, *Sci. Rep.* 6, 31625; issue #355, whose thread carries a six-rung
  decomposition B-1…B-6 measured at `6f4aa6b1`, gradient ≈ one forward
  evaluation under jax). The gate is B-3's table — the posterior interval
  against the Bérar-Lelann esd on the two vendored standards, both residual
  models — and the track stops there if every ratio sits inside a band.
- **Navigation.** From the QPA of a mixed-phase sample to the composition to
  make next (PICIP, Ritchie et al. 2025, *J. Chem. Inf. Model.* 65, 13226;
  issue #349, filed as v2+ by its author): a `rietx.navigate` subpackage on
  `indexing`'s pattern, the GPL reference implementation a test oracle only.
  Its three small asks — `PhaseQuantity.element_counts` exported, a
  weight-fraction covariance, `FitReport.unidentified_phase` — sit in 1325
  § Inherited beside #212, which wants the same field.
- **I/O.** Rietica and XND readers (#196); an RMCProfile export and PDF /
  total-scattering analysis, X-ray and neutron (#192); VESTA import/export
  (#195).
- **Infrastructure.** An MCP server over the python API (1303's rule: a tool
  surface earns its place only where it gates, renders, audits or
  parallelises); `vmap`-batched in-situ series — the only accelerator story
  this hardware supports, sized by WP-0408 at break-even ≈50-65 k elements per
  kernel and a ceiling ≈2.5-3× ([v0.4 record](milestones/v0.4.md)); notebook
  widgets.
- **Not at any version:** 2D image integration (pyFAI's job — the package
  takes 1D patterns) and single-crystal refinement.
