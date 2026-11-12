# WP-1045 — Indexing search controls: one surface for the GUI and the agent

Milestone: v1.0 · Status: ✅ 2026-08-08
Track: Indexing
Depends on: 1027, 1042 (1043 soft)

## Goal

A caller who knows something can say it, in either chair: the GUI's indexing
panel grows the controls a human would set — engines, crystal systems, cell
parameter ranges, budget/preset — the agent schema exposes the same fields, and
both gain **priors**: a structural analogue's cell or space group, tried first.
One spec behind both surfaces; priors steer the search, they never gate it.

## Context

### The user's design call, 2026-08-06

> In the indexing GUI, user should be able to specify engines, crystal systems
> and cell parameter ranges, plus any things I've forgotten. This should mirror
> the agent surface, where agents might have more information such as structural
> analogues, so they might try similar SGs or cells first.

Two ideas, and the second is the design-bearing one.

**1. The controls are one surface with two views.** Everything the GUI form
offers is a `SearchSpec` field or an `index_pattern` kwarg, and the agent tool
schema already quotes engine names from the live registry (WP-0602's rule). So
this is the capabilities pattern once more: the GUI form, the agent schema and
`SearchSpec`/`index_pattern` are held in bijection by a meta-test — a field
exposed in one and absent in another is a test failure, not a drift. Enums are
quoted live: engines from `engine_names()`, systems from `SYSTEM_ORDER`,
presets from `SEARCH_PRESETS` (landed, WP-1042). Two of the three views
already expose the preset — `SearchSpecSpec.preset` on the agent and
`rietx index --preset` on the CLI, both validating against the live
registry — so the mirroring here absorbs them, never re-invents them.

**2. A prior steers, never gates.** An agent (or a human with a database hit)
often holds a structural analogue — an isostructural compound whose cell and
space group are approximately right. The package's premise (a reasoning
consumer given good surfaces beats a mechanical rule) says give the reasoner a
way to *state* that knowledge, under three rules:

- **Priors reorder and seed; they never inject candidates past the engines.**
  A prior's system jumps the `SYSTEM_ORDER` queue in WP-1042's scheduler, and a
  prior cell can seed engine starting points (trial_error's base-line
  assignment, svd's starting basin, dichotomy's volume bracket). A prior cell
  that is real is then *found* by the engines from the seeded start, so
  `found_by` and `grade` keep their meaning — at least two independent finders.
  A prior confirmed only by `refine_with_shift` and not by any engine enters the
  candidate list with its provenance and grades `low` structurally, which is the
  honest reading: stated, shift-consistent, unconfirmed.
- **A prior narrows *order*, never the box** — no system dropped, no range
  tightened by a prior (the no-silent-caps rule). Explicit narrowing stays the
  caller's own act and is already recorded in `spec_notes`.
- **A prior used is recorded** — `INDEX_PRIOR_USED` naming what was supplied
  and what it changed — because assumed knowledge must never look like measured
  knowledge (the `INDEX_SHIFT_ALLOWANCE` precedent).

### The inventory (what "specify" concretely means)

Already in `SearchSpec`, needing only exposure: `systems`, `centrings`
(per-system), the axis-length range `min_d_axis`/`max_d_axis`, the volume range
`min_volume`/`max_volume` (float or per-system), `n_unindexed`,
`n_search_lines`, `k_sigma`, `budget_seconds`/`total_budget_seconds` (the
preset, once 1042 lands), `max_candidates`, `seed`. On `index_pattern` itself:
`engines`, `validate`, `check_top`, `two_theta_limits` (the project's excluded
regions already govern picking). New in this WP: the prior block only. The
panel need not show all of it at top level — disclosure is a GUI question
(gui/CLAUDE.md) — but everything above must be *reachable*, and everything
reachable must round-trip the project document as a project setting.

### GUI notes

The panel extends WP-1027's indexing panel; mutating verbs return 409 while a
run is in flight (gui/CLAUDE.md); control state is a *project* setting
(`project.json`), not history. Provisional candidates and the evidence view are
what the panel *shows* (WP-1042/1043); this WP is what the panel *asks* — but
the showing half has two gaps that are this WP's scope: the GUI has no preset
control and no consumer for the streamed per-system graded shortlists (each
`consensus:<system>` `stage_end` carries them in the WP-1043 evidence shape).

The panel's data and pictures already exist (WP-1043): consume
`IndexingResult.evidence()` (every caveat with its refuting/capping kind, the
figures that ranked beside `quality.fom_undefined`'s absent-for-cause ones,
the three whole-profile numbers together) and `viz.plot_indexing(result,
peaks, …)` (tick rows + Le Bail panel from a result alone, matching window
rebuilt from `provenance.notes`) — never re-derive either. Any esd the panel
plots inherits 1041's two plotly facts: a `null` in `error_y.array` draws
byte-identical to a zero-height bar, and an esd smaller than a pixel must
stay invisible. Candidates carry `cov_af` unevenly — exactly the null-bar
case.

### Two search bounds that are `SearchSpec`'s business (measured in 1028)

Both measured 2026-07-30 on the certified SRM 660c LaB6 pattern; 1028 § (k)
has the full text. Both become *this* WP's to fix the moment `SearchSpec` is
the one mirrored surface, because a control exposed in a form and a schema
must not carry a hidden second meaning.

- **`sigma_sys_deg` means two different things and only one of them indexes.**
  `ShiftScreen.sigma_sys_deg` is the scatter the winning shift template
  *leaves* (0.0078° on the certificate-probe trim; 1043's flag trim reads
  0.0025° — the probe's list still held the aliased 43.5° tail, inflating the
  residual 3×; the shift amplitude is identical under both). Declare that as
  `SearchSpec.sigma_sys_deg` and the search returns **no candidate at all**:
  it matches against **uncorrected** positions (`refine_with_shift` runs only
  after a candidate survives), so the window must still span the shift itself
  (+0.037°, 4.3× larger). The obvious protocol — measure the systematic on a
  standard, declare it — fails *silently*. Pinned by
  `test_what_the_unflagged_tail_components_cost_the_certified_cell`.
- **`volume_envelope` is a least-squares *mean line* used as a hard search
  ceiling.** Against Smith (1977): average discrepancy 10.6 %, deviations
  −29 % to +32 %, and low is the *ordinary* case (missing weak lines produce
  it). With p the fraction of possible lines detected the bound stands at
  1.4025·p × truth, so it **excludes the true cell below p = 0.713** — and
  28.7 % is Smith's own quoted worst case, so there is no margin.
  `VOLUME_ENVELOPE_SLACK = 1.5` exists but only in `consensus.py`, to *flag*
  an already-found candidate; the fatal uses feed the raw envelope
  (re-verified 2026-08-07 on this tree: `dichotomy.py:613`,
  `trial_error.py:306,513`, `svd.py:758`). The guard test
  `test_volume_envelope_contains_the_true_volume` feeds a complete line list
  at p = 1.0 and is blind to the calibration. Docstrings were corrected
  2026-07-30 to say "estimate"; the behaviour fix is owed here.

### Open design question: validation starvation under `quick` (from 1042)

Measured on 5 of 6 heavy corpus runs: the search consumes the whole ceiling
and validation gets zero fits — honest (`not_validated` + the budget
diagnostic's slice wording), but a `quick` first click then never sees the
mandatory whole-profile check. Whether `quick` should *reserve* a validation
share is a control-surface decision that needs a measured design, not a
hardcoded fraction — it lands with this WP's budget/preset controls.

## Non-goals

- The evidence view and its visual check — WP-1043. Streaming, presets and the
  scheduler — WP-1042.
- Search-match phase identification and multi-phase indexing (v2+ fence) — a
  prior here is a *cell hypothesis for this pattern*, not phase ID.
- Any change to `grade` or the gate.

## Tasks

- [x] The bijection meta-test: GUI form fields ↔ agent schema ↔
      `SearchSpec`/`index_pattern` kwargs, with enums quoted from the live
      registries (the `capabilities()` meta-test is the template) —
      `tests/test_search_controls.py` + `gui/src/lib/controls.test.ts` over
      the committed corpus `tests/data/gui/index_controls.json`.
- [x] Expose the existing inventory in the GUI panel (disclosure per
      gui/CLAUDE.md) — preset control included — and round-trip it through the
      project document (`ProjectDoc.indexing`, whole-object on the verb); give
      the panel its consumer for the streamed per-system graded shortlists.
- [x] `prior_cells` / `prior_spacegroups` on `SearchSpec`: schedule reordering
      + engine seeding (svd's starting basin — the one engine with a start)
      + `INDEX_PRIOR_USED`; the steer-never-gate rule pinned by
      a test — a deliberately wrong prior changes no
      final rank and no grade, only when things were searched
      (`tests/test_indexing_priors.py`; structural, not statistical:
      prior-only candidates never enter the Borda ranking).
- [x] `agent.refine_json`'s index task and `tool_definition()` accept the same
      fields (the shared `SearchSpecSpec` + `check_top`);
      `docs/AGENT_PROTOCOL.md` gains the "state what you know" passage with
      the calcite structural-analogue worked example and the
      `INDEX_PRIOR_USED` row.
- [x] Resolve `sigma_sys_deg`'s two meanings *before* the field is exposed:
      renamed — `SearchSpec.shift_allowance_deg` (and
      `effective_shift_allowance`, the stats key, the note, the agent field,
      `--shift-allowance`); the only `sigma_sys_deg` left is the screen's
      scatter.
- [x] Apply `VOLUME_ENVELOPE_SLACK` at the three engines' fatal uses
      (`search_volume_ceiling`, the one authority), with a regression test
      that feeds an *incomplete* line list (raw envelope 0.94× truth at
      p = 0.6 on the corundum-setting cell).
- [x] The validation-share design question, measured then decided (§ Context):
      **yes** — `VALIDATION_RESERVE_FRACTION = 0.08` of a declared ceiling,
      taken only when validation will run, plus ambiguity deferred to *after*
      validation (`consensus.enumerate_ambiguity`; the enumeration — 45 s on
      ceiling-bound corundum, one sweep uninterruptible — otherwise consumed
      the reserve first while validation is the mandatory check). Measured on
      the three heavy qarr patterns: validated fits went 0/0/0 →
      2/6/3 at the same 120 s wall (a fit costs 0.3–1.9 s against 11–60 s
      for a trailing search system — a ~30:1 trade). Stated on the surface
      through the constant, the `quick` preset's description, and
      `INDEX_BUDGET_EXHAUSTED`'s existing three-state reading.

## Acceptance

A poisoned prior costs time, never truth: on a scoreboard dataset, a wrong prior
cell changes no final rank and no grade, and the result records that the prior
was tried. A correct analogue prior (a certified cell perturbed by a few hundred
ppm) surfaces the truth in the first streamed shortlist. GUI and agent runs with
identical controls produce identical `spec_notes`.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_consensus.py \
    tests/test_search_controls.py tests/test_indexing_priors.py \
    tests/test_agent_surface.py tests/test_capabilities.py -n auto --dist loadgroup
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- [WP-1042](1042-anytime-results-quick-default.md) § What `quick` is — the
  scheduler priors reorder; [WP-1043](1043-agent-and-human-indexing.md) — the
  evidence view a prior-only candidate lands in.
- `capabilities()` (WP-1007) and the agent schema registry meta-test (WP-0602)
  — the two bijection precedents this WP's meta-test copies.
- `indexing/engines.py` `SearchSpec` — the one object all three views expose.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **search controls** (WP-1045, `gui/src/lib/controls.ts`, the Peaks
panel's disclosure) are `ProjectDoc.indexing` rendered as a form — the same
`SearchSpecSpec` the agent request carries, so the two chairs are two views
of one spec. Five rules. **The document is the authority and the commit is
whole-object**: every change POSTs the entire `indexing` block on the verb (a
partial merge could let two half-specs disagree), and the draft re-syncs from
the document on every head move — including after a refusal, so the form
never shows a value the server refused. **Vocabularies come from
`/api/capabilities`** (`indexing_engines`, `crystal_systems` in search order,
`centrings`, `shift_templates`, `search_presets`), never from literals — a
fourth engine appears with no GUI change. **The field inventory is the
bijection's GUI leg**: `controls.ts` declares every field with its widget
kind, label and `title` (WP-1029's no-mute-fields rule, pinned), and
`controls.test.ts` replays the committed corpus
`tests/data/gui/index_controls.json` (the fnmatch mechanism — python owns the
model, TS proves the form states it). **A prior cell is parsed locally**
(six numbers, refused with a reason in the form's own error field — which is
deliberately not the peak verbs' failure field), while a prior space-group
symbol is validated server-side and refused in gemmi's words. And **the
streamed shortlists are the shell's to fold**: `consensus:<system>`
`stage_end` frames collect in App (cleared on `index_start`, kept after the
run so the anytime answer stays readable beside the final one) and render
with the conservative-grade caveat in the tooltip — a streamed grade can
rise, never fall.

## Handover log

- **2026-08-08** — the whole WP in one session (started 2026-08-07 on the
  1042-merged main; 13 commits). **Done — all seven tasks**, each with its
  checkbox's detail above; the shape of the session:
  the two 1028 fixes first (they change `SearchSpec` semantics the surface
  then exposes), then the shared model + meta-tests, then priors, then the
  GUI, then the docs, then the validation reserve. Highlights a successor
  should know exist: `tests/test_search_controls.py` (the bijection +
  the literal two-chairs acceptance, byte-identical `spec_notes`),
  `tests/test_indexing_priors.py` (steer-never-gate pinned structurally),
  `gui/src/lib/controls.ts` + `controls.test.ts` replaying the committed
  corpus `tests/data/gui/index_controls.json`, `indexing/priors.py`,
  `consensus.enumerate_ambiguity` (ambiguity now runs *after* validation),
  and four new `capabilities()` vocabulary arms.
  **Measured** (main checkout venv `[dev,jax,torch]`, darwin/arm64 M4):
  full **2086 passed / 6 skipped in 31:07** at `-n 4` — against 1042's
  same-venv 2052 / 6, **+34 exactly** (16 search-controls, 14 priors, 2
  quality, 1 scheduler, 1 capabilities), all passes, no new skips; fast
  measured 1977+2-then-fixed → the green tree's fast selection is those
  same +34 over the merge-base's. `-n auto` was killed twice at ~46 % on a
  swap-exhausted machine (23 of 24.5 GB) — `-n 4` finished; treat that as
  machine state, not a suite property. vitest **390 → 401** (+8
  `controls.test.ts`, +3 App mount tests), `svelte-check` clean, dist
  rebuilt. `test_acceptance_indexing.py` standalone after the engine
  changes: 41 passed in 22:20. Scoreboard regenerated **unchanged**: 7
  first / 2 below first / 0 refused. Validation-reserve evidence: bare
  quick on corundum/zincite/brucite validated **0/0/0** (walls
  120.6/122.3/120.4 s; a fit costs 0.3–1.9 s against 11–60 s per trailing
  search system); the first attempt (5 %, ambiguity first) recovered only
  brucite — corundum's ambiguity enumeration (45 s in 1042's record, one
  candidate's sweep uninterruptible) ate the reserve — and the shipped 8 %
  + validation-first gives **[0,1] / [0,1,2,3,4,6] / [0,1,2]** at
  120.2/120.1/112.7 s, the truth's own validation included on every one.
  **Next**: nothing in flight here. For successors: the panel's `centrings`
  chips and the priors editors have not been driven in a real browser
  (WP-1017's concern, noted in its Inherited); `prior_spacegroups`
  validate via gemmi only server-side.
  **Gotchas**: the indexing dossier's 250-line cap was *full* on arrival —
  a new rule section pays by compressing older ones (facts kept, narrative
  to the records); the prior *check* can basin-hop and claim confirmation
  (`PRIOR_DRIFT_MAX` bounds it to 10 % in volume); compare any seeded find
  with `same_lattice`, never cell tuples (WP-1040's trap, hit again on the
  monoclinic seed); `_ROUND_TRIP` in `test_search_controls.py` needs a row
  per new `SearchSpec` field — the coverage assert forces it, which is the
  point; and `viz._window_from_result` reads the provenance note under its
  new name with a legacy fallback for pre-1045 results (pinned).
- **2026-08-06** — created in the 1042/1043 review session from the user's
  design call (controls + agent mirror + analogue priors). Split so 1043 keeps
  the output half (evidence, visual check) and this WP the input half; sized
  after 1042's scheduler and presets exist, which is why it depends on 1042.
