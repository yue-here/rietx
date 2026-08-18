# rietx — Roadmap

Canonical milestone **index**. The content that used to live here is split so
a work session loads only what it needs:

- **[AGENT_PROTOCOL.md](AGENT_PROTOCOL.md)** — how to *use* the package as an
  automated operator: turn-on order, degeneracies, abstention handling,
  diagnostic-code semantics, and the measured findings that change agent
  behaviour. Written for consumers, not maintainers; a WP that adds a
  diagnostic code or a correction should add its row there.
- **[DESIGN.md](DESIGN.md)** — the design record (rationale, locked decisions,
  invariants). Stable; read the specific section a work package links.
- **[milestones/](milestones/)** — shipped-milestone records with the measured
  acceptance blocks (`v0.1.md`, `v0.2.md`, …).
- **[wp/](wp/)** — one self-contained **work package (WP)** per task. Each has
  its own context, commit-sized checklist, acceptance command, and handover
  log. `wp/TEMPLATE.md` defines the format.
- **[RELEASING.md](RELEASING.md)** — how a version reaches PyPI, and the rule
  that it never goes by hand. Supersedes WP-1003's by-hand upload checklist.

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
   checklist it carries: dated handover entry prepended (newest first: done /
   in flight / next / gotchas), Status line and the index-row glyph below
   synced, forward references pushed into the `### Inherited` of any affected
   WP that is not closed and not yours (a handover log reaches only your own
   successor on the same WP), rule 4 applied to anything this session wrote
   into a CLAUDE.md, working tree clean and pushed, and the branch's pull
   request opened or updated — a session is not handed over until its work is
   reviewable, and merging stays the maintainer's. A missed handover is
   detected at the next session start (`.claude/hooks/session_start.py`) and
   repaired before new work.
4. **A CLAUDE.md takes rules, not findings.** A line enters a CLAUDE.md
   (root, `gui/`, `tests/`, `src/rietx/indexing/`) only as a standing rule
   a stranger needs in six months — a few lines, evidence compressed to one
   clause plus a pointer to the WP or milestone record that holds the
   measurement. Counts and timings a session measures go in its WP handover
   entry (root CLAUDE.md § Numbers holds the *recipe*; the dated history is
   the v1.0 appendix diary).
5. **WP closes** (✅/🛑): rewrite "Current focus" for the successor and MOVE
   the outgoing narrative to the in-flight milestone record
   (`milestones/v1.0.md` § "How v1.0 is getting here"). Current focus stays
   within `CURRENT_FOCUS_CAP` (tests/test_docs_consistency.py) and repeats
   nothing a closed WP's own file already says.
6. **Milestone ships**: finish `milestones/vX.Y.md` with the measured
   acceptance block, flip the milestone row here, check README's claims.

`tests/test_docs_consistency.py` enforces the mechanical parts: status
vocabulary and glyph sync, Inherited placement, link resolution, and the
size caps on this file and CLAUDE.md.

## Current focus

**v1.0 shipped 2026-08-16** ([record](milestones/v1.0.md)): public, gated,
hosted, on PyPI. **The freeze is live**, so two rules now bind every session:
a change to a frozen surface follows the hybrid classification in
`docs/manual/using/compatibility.md`, and a 1.0.x manual chapter that
documents a name *promotes it to frozen* — regenerate
`tests/api_surface_deferred.txt` and earn a release-notes line
([1067](wp/1067-user-api-manual.md)'s Context has the mechanics).

**No milestone is in flight.** Opening the next one is a planning decision
(version → `1.x.0.dev0`); the committed post-1.0 work, in rough order:

- **Promised in the 1.0.0 release notes, built in 1.0.x**: `.rex` zip
  transport (export/open, "the directory, zipped");
  `RefinementState.excluded_regions` with `replay` honouring the node's
  regions (1003 §B — decided, not re-opened).
- **[1067](wp/1067-user-api-manual.md)** — two Part 1 chapter lines left plus
  second passes on `agents.md` and `report.md`, each promoting names out of the
  provisional bucket (395 left, 30 % of the surface);
  **[1076](wp/1076-result-row-honesty.md)** now holds three unwritten result
  fields, all found by writing a chapter over the type that declares them.
- **[1078](wp/1078-indexing-provisional.md)** — indexing is still under active
  development, so the subsystem is declared provisional and every surface says
  so; it un-freezes what 1067's chapter froze and **gates 1.0.2**.
  **[1077](wp/1077-extinction-refutes-certified-class.md)** — the extinction
  screen refutes corundum's certified class, and no acceptance row covers the
  shape.
- **Post-1003 indexing work**: narrow what the acceptance fixtures search
  (the nightly `full` job's ~77 min of setup — the durable lever the
  timeout recalibration deferred), and the `grade` prior-counting change
  (1046 §4, on the record in `consensus.grade`).
- **[1017](wp/1017-gui-manual-onboarding.md)** — the GUI manual and
  onboarding, still deferred; the GUI stays beta until it lands.

1066's naming rule stands beside them, as a rule in root CLAUDE.md and in full
(both directions, the token list, and why no test can catch a hardcoded *new*
name) in `_about.py`'s docstring.

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
| v2+ | FPA, neutron/TOF, texture, MCP server | ⬜ fenced | — |

## Work packages

### v0.3 — multi-phase workflows (detailed, ready to start)

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

### v0.4 — differentiable backends (expanded 2026-07-24; ready to start)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0401](wp/0401-backend-op-shim.md) | Backend op shim (34 named ops + `window_add`/`segment_sum`; the WP was scoped at "~41" before the survey) + residual purity refactors | ✅ 2026-07-24 | — |
| [0402](wp/0402-jax-backend.md) | JAX backend: chunked jacfwd | ✅ 2026-07-24 | 0401 |
| [0403](wp/0403-cuda-mixed-precision.md) | Mixed-precision policy (CUDA-deferred, CPU-testable) | ✅ 2026-07-24 | 0402 |
| [0404](wp/0404-cross-backend-jacobian-ci.md) | Cross-backend Jacobian CI | ✅ 2026-07-24 | 0402 |
| [0405](wp/0405-faddeeva-voigt.md) | True Voigt via shared Faddeeva w(z) | ✅ 2026-07-24 | 0401 |
| [0406](wp/0406-restraint-penalty-rows.md) | Restraint penalty rows | ✅ 2026-07-24 | — |
| [0407](wp/0407-esd-reconciliation.md) | esd reconciliation (Bérar-Lelann placement) | ✅ 2026-07-24 | — |
| [0408](wp/0408-torch-mps-backend.md) | torch backend (MPS fp32 forward) — moved from v0.6 | ✅ 2026-07-27 | 0401, 0402, 0404 |

### v0.5 — corrections & microstructure (stubs)

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

### v0.6 — solver, performance & agents (stubs)

| WP | Title | Status | Depends on |
|---|---|---|---|
| [0601](wp/0601-bounded-lm-solver.md) | TOPAS-style bounded LM | ✅ 2026-07-28 | — |
| [0602](wp/0602-agent-json-surface.md) | Agent JSON surface hardened | ✅ 2026-07-29 | — |
| [0604](wp/0604-theory-manual.md) | Sphinx + MyST theory manual | ✅ 2026-07-29 | — |
| [0605](wp/0605-batched-peak-loop.md) | Batched peak loop (spike, then decide) | ✅ 2026-07-28 | — |

(0603 — the torch/MPS backend — moved to v0.4 as
[0408](wp/0408-torch-mps-backend.md) on 2026-07-24; the number is left unused so
the history stays readable.)

### v1.0 — hardening, human GUI & release (GUI WPs added 2026-07-29)

Order: backend API first (1004–1007, each independently useful without the
GUI), then server (1008–1009), then frontend (1010–1016); the freeze (1003)
is the milestone's last row so it covers a surface the GUI has exercised.
Both docs WPs (1017, 1067) are post-v1.0 — see that section below.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1001](wp/1001-validation-matrix.md) | Validation matrix + tolerance policy | ✅ 2026-07-29 | — |
| [1002](wp/1002-ci-matrix.md) | CI matrix | ✅ 2026-07-29 | — |
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
| [1015](wp/1015-structure-viewer.md) | Structure viewer, zero new dependencies | ✅ 2026-07-30 (+ scene pass same day) | 1010 (1014 soft) |
| [1016](wp/1016-sequential-series-panel.md) | Sequential series panel | ✅ 2026-08-05 | 1008, 1010, 1011 |
| [1029](wp/1029-gui-usability.md) | GUI usability: legibility, layout, colour, theming | ✅ 2026-07-30, second pass 2026-07-31 | 1010–1015 |
| [1032](wp/1032-gui-repairs.md) | GUI repairs found by use (tooltips, ticks, curves, gestures, field help) | ✅ 2026-08-05 | 1010–1015, 1027, 1029 |
| [1033](wp/1033-plot-range-regions.md) | 2θ limits and excluded regions, visible and selectable | ✅ 2026-08-05 | **1032** (same file), 1005, 1009 |
| [1034](wp/1034-panel-layout.md) | Model and Text in the right panel | ✅ 2026-08-05 | 1013, 1014, 1029 (1032 soft) |
| [1035](wp/1035-symmetry-surfaced.md) | Symmetry, surfaced and editable | ✅ 2026-08-05 | ~~1036~~ ✅, 1014 (1004 soft) |
| [1044](wp/1044-gui-view-cursor-theme.md) | GUI defects found by use: the view, the armed cursor, the theme | ✅ 2026-08-06 | 1029, 1032–1033, 1027 |
| [1031](wp/1031-docs-consolidation.md) | Planning-doc consolidation + handoff mechanization | ✅ 2026-07-31 | — |
| [1003](wp/1003-api-freeze-pypi.md) | API freeze + PyPI | ✅ 2026-08-16 — two-strength freeze written and bound; repo public + CI gating + un-shaping as one change; Pages hosting; 1.0.0 uploaded after the Windows gate caught three real portability defects | 1001, 1002, 1004–1036 **except 1017** (deferred), 1067 § Floor |

### v1.0 — indexing (added 2026-07-29)

Unit-cell determination from a pattern, and the peak picking it needs. Added
into v1.0 on the same argument that un-fenced the GUI: `index()` is a
top-level entry point, a peer of `refine()`, and the freeze (1003) should
cover a surface that has been exercised. It also closes a seam the package
declared long ago — `report/layer2.py` has emitted the
`reindex_or_recheck_cell` action since v0.2 with nothing behind it.

Order: peaks and quality first (1018–1019, useful on their own), then the
shared core (1020), then the three engines (1021–1023, independent of each
other), then consensus (1024), space groups (1025), acceptance (1026), GUI
(1027). [1030](wp/1030-engine-scaling-low-symmetry.md) was added 2026-07-30 and
sits between 1026 and its own grade: the benchmark cannot be scored until a
monoclinic search finishes.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1018](wp/1018-peak-picking.md) | Peak picking: detection + full per-peak profile fitting | ✅ 2026-07-30 | — |
| [1019](wp/1019-indexing-data-quality.md) | Data-quality gate and the systematic-error model | ✅ 2026-07-30 | 1018 |
| [1020](wp/1020-indexing-core.md) | Indexing core: Q-space, reduction, Bravais, FoM panel, ambiguity | ✅ 2026-07-30 | 1018 (1019 soft) |
| [1021](wp/1021-engine-dichotomy.md) | Engine A — successive dichotomy | ✅ 2026-07-30 | — |
| [1022](wp/1022-engine-trial-error.md) | Engine B — index-heuristic trial and error | ✅ 2026-07-30 | — |
| [1023](wp/1023-engine-montecarlo.md) | Engine C — whole-profile Monte Carlo (spike, then decide) | 🛑 no-go 2026-07-30 | — |
| [1024](wp/1024-indexing-consensus.md) | Consensus, `index_pattern`, Le Bail validation, agent & CLI | ✅ 2026-07-30 | 1021–1023 |
| [1025](wp/1025-extinction-symbol.md) | Extinction symbol / space-group determination | ✅ 2026-07-30 | 1024 |
| [1026](wp/1026-indexing-acceptance.md) | Acceptance: bethanechol benchmark + known cells | ✅ 2026-08-08 — criterion 1 generated: global **−8** of ±20 (ties DICVOL91), runner beside the gallery | 1024 (1025 soft) |
| [1027](wp/1027-gui-peak-picker.md) | GUI peak picker + indexing panel | ✅ 2026-08-01 | 1010, 1011, 1018–1024 |
| [1030](wp/1030-engine-scaling-low-symmetry.md) | Engine cost at low symmetry + the two missing figures of merit | ✅ 2026-07-31 | 1020–1022 (1026 soft) |
| [1037](wp/1037-indexing-time-ceiling.md) | Indexing: a stated time ceiling and honest progress | ✅ 2026-08-04 | 1024 (1021, 1022 soft) |
| [1038](wp/1038-shift-reflection-pairs.md) | Pre-indexing 2θ shift from reflection pairs | ✅ 2026-08-04 | 1019, 1024 |
| [1039](wp/1039-search-line-count.md) | Which lines a search is driven by (was: how many) | ✅ 2026-08-05 | 1037 (1038 soft) |
| [1040](wp/1040-engine-svd-index.md) | Engine C (second attempt): SVD-Index | ✅ 2026-08-05 — landed with the zero-error column; scoreboard re-measured in 1041 | 1020, 1024 (1038 soft) |
| [1041](wp/1041-indexing-benchmark-gallery.md) | The indexing benchmark gallery | ✅ 2026-08-05 — PNGs on every row, scoreboard generated (9: 6/2/1/0), contamination curve, aggregate refuted | 1026 |
| [1042](wp/1042-anytime-results-quick-default.md) | Anytime results, and `quick` as the default | ✅ 2026-08-07 | 1037 |
| [1043](wp/1043-agent-and-human-indexing.md) | Indexing for an agent and for a human: report, don't refuse | ✅ 2026-08-07 | 1041, 1026 (1028 soft) |
| [1045](wp/1045-indexing-search-controls.md) | Indexing search controls: one surface for the GUI and the agent | ✅ | 1027, 1042 (1043 soft) |
| [1046](wp/1046-candidate-cap-before-ranking.md) | The per-engine candidate cap decides the ranking | ✅ 2026-08-09 — reported cap applied once by consensus, `corroborated` the first ranking key | 1024 (1026 soft) |

### v1.0 — cross-cutting, found by use

Neither indexing nor GUI: gaps that surfaced from driving the package over
files, CIFs and figure conventions we did not author. Close narratives, and
the `guillemot-study` prior art 1028 rests on, are in the
[v1.0 record](milestones/v1.0.md).

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1028](wp/1028-robustness-external-data.md) | Robustness on data and CIFs we did not author | ✅ 2026-08-07 | — (1007 soft) |
| [1036](wp/1036-crystal-system-settings.md) | Crystal-system cell ties: the settings the tables do not check | ✅ 2026-08-04 | — |
| [1047](wp/1047-vendor-pattern-formats.md) | Vendor pattern formats: read the files labs actually have | ✅ | 1005, 1007, 1014 (1009, 1028 soft) — before 1003 |
| [1075](wp/1075-static-panel-conventions.md) | The static panel takes the house figure conventions | ✅ 2026-08-16 — layout, palette, axes and scales; the raw difference is the default and the rows moved below it | — (before 1003: four new `plot_result` keywords) |

### v1.0 — report evidence, agent evals, and the rename

What a report has to say for a caller to act on it, measured against real
agents rather than asserted — then the two renames, which ran early because
the freeze covers names that embed the brand.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1050](wp/1050-suggest-next-parameter.md) | `Refinement.suggest()`: which parameter to free next | ✅ | — (before 1003 if frozen) |
| [1051](wp/1051-sequential-escalation.md) | Sequential escalation ladder + chain hygiene | ✅ 2026-08-09 — three rungs, keep-best; a diverged pattern seeds nothing and joins no median | — |
| [1052](wp/1052-report-loop-eval.md) | Closed-loop FitReport usefulness eval (mechanical) | ✅ 2026-08-11 — the §9 loop runs closed in CI; recovers what separates, refuses what does not, `src/` untouched | — |
| [1053](wp/1053-agent-in-the-loop-eval.md) | Agent-in-the-loop report eval (refine_json) | ✅ 2026-08-11 — 48/48-run pilot: A/B null on outcomes; the bottleneck is when the report is read, not what it says | 1052 |
| [1054](wp/1054-abstained-branch-honesty.md) | Layer-2 honesty on the abstained branch (phantom-phase invitation) | ✅ 2026-08-12 | — |
| [1055](wp/1055-background-evidence.md) | Background evidence in the FitReport | ✅ 2026-08-12 — both failure modes in `FitReport.background`; the over-flexible fixture wins on Rwp and GoF and lands 2.6× further from truth | — |
| [1056](wp/1056-identifiability-layer.md) | Identifiability layer: correlations, soft modes, held-parameter exchangeability | ✅ 2026-08-12 — a converged report names the zero↔displacement exchange; R² is design-matrix-identical on the clean control, the partner's 128σ-vs-1.6σ discriminates | — |
| [1057](wp/1057-purpose-grade-evidence.md) | Purpose-grade evidence: Le Bail gap + protocol stopping criteria | ✅ 2026-08-12 | — |
| [1058](wp/1058-report-delivery.md) | Report delivery: the per-stage report trajectory | ✅ 2026-08-13 | — |
| [1059](wp/1059-eval-round-two.md) | Agent eval round 2: protocol v1.1 re-A/B | ✅ 2026-08-13 | 1054, 1056, 1057, 1058 |
| [1062](wp/1062-rename.md) | Rename the project to `anatase` (superseded by 1066) | ✅ 2026-08-12 — ~300 files; formats decoupled from the brand (`.rex`/`.rxt`), audit test greps the old token | — (blocked 1003) |
| [1063](wp/1063-exchange-clause-and-rivals.md) | Fit-level exchange clause + `compare_rivals`: name the swap, ship the experiment | ✅ 2026-08-13 — THRESHOLDS_VERSION 0.8; the miner puts the clause in context before the ridge in 6 of the 7 cells | 1056, 1059 (before 1003) |
| [1064](wp/1064-eval-round-three.md) | Agent eval round 3: measured epistemic truth, decision-grade scorer, python arm | ✅ | 1063 |
| [1065](wp/1065-decisive-swap-license.md) | What a decisive swap licenses: the follow-through sentence, measured on the row it failed | ✅ | 1063, 1064 (before 1003) |
| [1066](wp/1066-rename.md) | Rename the project to `rietx` | ✅ 2026-08-14 — 363 files, zero numbers moved; format tokens survived a second rename; no WP filename may carry a brand token | 1062 (blocked 1003) |

### v1.0 — the repo's own process (added 2026-08-06)

From a measured review of how this repo works, not of what it computes: the
docs were ballooning, CI paid twice per merged PR, and the handover was
*remembered* rather than enforced.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1060](wp/1060-docs-ci-consolidation.md) | Docs/CI consolidation: trim what the evidence indicts | ✅ 2026-08-06 | — |
| [1061](wp/1061-workflow-robustness.md) | Session-workflow robustness: detect the missed handover | ✅ 2026-08-06 | — |

### Post-v1.0 — the docs WPs (1067 spans the release), and what they found

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1017](wp/1017-gui-manual-onboarding.md) | GUI manual, in-app help, onboarding | ⬜ deferred 2026-08-14 | 1011–1016, 1029, 1032–1035 (soft) |
| [1067](wp/1067-user-api-manual.md) | User & API manual (Part 1), beside the theory manual (Part 2) | 🔄 2026-08-17 — § Floor landed, so 1003 is unblocked; the McCusker set's pass landed (Part 2 takes its four equations, `using/results.md` splits off, restraints documented, three figures); `using/data.md`, `using/model.md`, `using/refining.md`, `using/history.md` and `using/indexing.md` landed and froze 624 names (395 left — 30 % of the surface, which the refining chapter grew by 24 by finding a derivation blind spot), with the promotions accumulating in the written, unreleased `docs/releases/1.0.2.md`; the project half went into `files.md` rather than a `projects.md` that would have restated it; two chapter lines and two second passes remain | 0604, 1004–1007, 1047 |
| [1068](wp/1068-manual-second-pass.md) | Part 1 second pass: voice, figures, structure | ✅ 2026-08-15 — voice, sectioning, `concepts.md` + `files.md`, four diagrams, three figure pairs; the McCusker read fixed a false attribution and produced the compliance audit | 1067 |
| [1076](wp/1076-result-row-honesty.md) | A result row's unwritten fields: `at_bound` and `initial` | ⬜ | 1067 |
| [1077](wp/1077-extinction-refutes-certified-class.md) | The extinction screen refutes a certified class (corundum R -3 c), and no row covers the shape | ⬜ | — |
| [1078](wp/1078-indexing-provisional.md) | Indexing is provisional, and every surface says so — **gates the 1.0.2 release** | ⬜ | 1067 |

The GUI keeps moving, so it **ships as a beta feature** and is documented once
the panels settle. 1067 declares that beta status; its **§ Floor gates
[1003](wp/1003-api-freeze-pypi.md)** and the rest lands in 1.0.x, so it stays
open past the milestone by design rather than being split.

### The McCusker compliance set (added 2026-08-15)

The WP-1068 audit (`milestones/v1.0.md` § Appendix): no correctness defect,
nine gaps — six WPs below, difference Fourier fenced to v2+, the
divergence-slit correction declined in the audit itself. Ordering
recommendations are the Depends cells, grounds in 1003's `### Inherited`;
the freeze decides.

| WP | Title | Status | Depends on |
|---|---|---|---|
| [1069](wp/1069-structure-r-factors.md) | R_Bragg and R_F, and the stated esd method | ✅ | — (before 1003 recommended) |
| [1070](wp/1070-user-facing-constraints.md) | User-facing constraints: ties on the Refinement surface | ✅ | 1004 (before 1003 recommended) |
| [1071](wp/1071-data-support-checks.md) | Effective observations and steps per FWHM | ✅ | — (before 1003 recommended) |
| [1072](wp/1072-geometry-table.md) | Interatomic geometry, esds from the full covariance | ✅ 2026-08-15 — distances and angles over the frozen orbits, J·Cov·Jᵀ with the diagonal-only twin beside it, `_geom_` CIF loops | — (landed before 1003) |
| [1073](wp/1073-capillary-displacement.md) | Capillary sample displacement, eq (4) | ✅ 2026-08-15 — eq (4) with derived signs, position templates and actions keyed by geometry (THRESHOLDS 1.0); measured: 11-BM is where it must *not* be refined | — (1.0.x) |
| [1074](wp/1074-restraint-weight-schedule.md) | Restraint weight schedule (c_w) | ✅ 2026-08-16 — eq (7)'s c_w per stage, identity default bit-identical; measured: a flat c_w = 1 converges to a 4.834 Å bond at Rwp 0.0393, the schedule to 1.872 Å at 0.0327 | 0406 (1.0.x) |

## v2+ (seams pre-built, implementations fenced out)

Fundamental Parameters Approach as a differentiable convolution stack
(Cheary-Coelho 1992); neutron CW; TOF (new Source/Profile implementations
behind the frozen seams); spherical-harmonics texture (Von Dreele 1997);
rigid bodies; MCP server wrapping `refine_json`; internal-standard/amorphous
QPA; `vmap`-batched in-situ series; notebook widgets. *(The human GUI was
un-fenced from this list into v1.0 on 2026-07-29 — WP-1004…1017; grounds in
[DESIGN.md](DESIGN.md#locked-decisions).)*

Fenced **by** the v1.0 indexing WPs (1018…1027, 2026-07-29), i.e. deliberately
left undone by work that could plausibly have grown to include them:
multi-phase indexing (index the residual after subtracting a solved phase);
search-match phase identification, whose prior art is the 36-cell screen at
`guillemot-study:studies/guillemot/match_hl2.py`;
the full Bayesian extinction-symbol posterior (Markvardsen et al. 2001 — the
ΔBIC/Hamilton nested comparison is the v1.0 form); a fourth engine in the
Conograph topograph lineage (Oishi-Tomiyasu's reversed/symmetric M_N *is* in
scope, as a figure of merit); derivative-lattice ambiguity above index 4; and
structure solution from an indexed cell.

Added to this fence 2026-08-06 (user: v1 wants a robust engine, not a headline —
push further testing post-v1): the **low-symmetry real-data corpus** — NBS
Monograph 25, public domain, 16 orthorhombic + 29 triclinic peak-list patterns,
DICVOL04's own test corpus (sourcing notes in WP-1043 § corpus; until it lands,
every indexing-scoreboard summary says "high-symmetry" out loud), plus the
SDPDRR-2/CONOGRAPH profile acquisitions; and **Boultif-Louër volume tightening**
(the gated design is recorded in WP-1042 § Deferred).

Added 2026-08-15 (the McCusker audit): **difference Fourier / maximum-entropy
maps** (§6) — the partition input exists (`lebail_update`); the consumer is
structure completion, fenced beside structure solution, and the debugging
half the paper uses maps for is Layer 0/2's job here.

No WP files for v2+ on purpose — the fence is a scope-discipline decision
([DESIGN.md](DESIGN.md#locked-decisions)), and pre-writing packages invites
scope creep.

One note against the day that fence is revisited: **`vmap`-batched in-situ series
is the only accelerator story this package's hardware supports**, and WP-0408
measured its size — break-even ≈50-65 k elements per kernel, ceiling ≈2.5-3×
because the work is memory-bound, so a single pattern is below break-even even
after batching ([v0.4 record](milestones/v0.4.md), [WP-0408](wp/0408-torch-mps-backend.md)).
