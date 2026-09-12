# WP-1101 — fit_peaks: standalone peak fitting at named positions

Milestone: v1.4 · Status: ✅ 2026-09-13 — `fit_peaks` exported, flagged, documented in the manual and the skill; v1.4 opened alongside
Depends on: — (first of the free-standing peaks set; opens the 11xx block)

## Goal

A caller can profile-fit peaks in a pattern — including exactly the positions
they name, with no structure, no space group and no refinement — through one
documented top-level call, `fit_peaks(data, instrument, positions) →
PeakList`. Peak-width analysis (Williamson-Hall), quick d-spacings and general
lab use become first-class, served by machinery that already exists.

## Context

- **Almost everything exists; this WP is exposure, not construction.**
  `pick_peaks` is exported and documented; the per-group fitter
  (`indexing/peakfit.py`) fits the Kα doublet as a Bragg-law-constrained pair
  with the Kα2/Kα1 ratio held at weight × the two lines' Lp ratio (holding the
  bare weight biased the fitted Kα1 by −2e-4° and −0.26 mean σ pull —
  measured, that module's docstring), shares Γ_G/Γ_L per group, applies FCJ
  at the declared apertures, and inflates esds by √max(χ²_red, 1).
  `fit_group_at` (`indexing/peakfit.py`, "One solve with **exactly** these
  components — the editing entry point") is the engine; it is unexported.
- **API shape: one convenience function, not a power-surface export.**
  `fit_peaks(data, instrument, positions, *, two_theta_range=None) →
  PeakList`, defined in `rietx.indexing`, re-exported at top level. Defining
  it there puts it at provisional tier automatically ([1078](1078-indexing-provisional.md):
  the tier derives from the *defining* module and is reached through the
  re-export). Exporting `fit_group_at`/`GroupFit`/`Detection`/`PeakGroup`
  instead would drag four more names onto a surface where provisional names
  must still all be documented ("a weaker *promise*, never thinner
  *coverage*" — `tests/api_surface.py`); `PeakList` is already the
  serializable, documented projection, and `ObservedPeak` already carries
  `fwhm`/`eta`/`q`/`q_esd` — everything W-H and d-spacing use needs.
- **Semantics: exactly the named components.** Run `detect_peaks` for the
  envelope and windows; a position inside a detected group reuses that frozen
  window; positions sharing a window are fitted together as one group; the
  fitted component set per window is exactly the caller's positions
  (`fit_group_at`'s contract — the caller has already said where the
  components are). Result peaks carry `origin="manual"`.
- **The silent trap, and its flag.** When detection saw components in a
  window the caller did not name, fitting the caller's model alone biases the
  named position and the only numeric trace is χ²_red. Affected peaks carry a
  new `PeakFlag` member (`"unnamed_neighbour"`; the Literal lives in
  provisional `schemas/indexing.py`, so the addition is cheap) and the esd
  inflation carries the numeric honesty. Evidence, not refusal.
- **The load-bearing lift** (re-read 2026-09-12; smaller than written).
  `PEAK_WINDOW_FWHM_MULT = 4.0` already lives in `schemas/indexing.py` and
  both sites import it from there. What is duplicated is the *arithmetic*:
  `gui/peaks.py` (`PeakEditor._new_group`) sizes a fresh window around one
  position — predicted FWHM × `Detection.width_scale` × mult, FCJ extent added
  on the low side only, `searchsorted` both ends, refusals naming an
  out-of-range position and a gap (`_MIN_GROUP_POINTS = 8`) — and
  `indexing/peaks.py` (`detect_peaks`'s per-group loop) does the same over a
  seed *span* with no refusals. Lift one helper into `indexing/` covering
  both, have gui import it back (gui is never imported by indexing). Pin:
  `tests/test_gui_peaks.py` stays green, plus a direct window-equality test
  against the detection loop.
- **Agent surface — superseded 2026-09-12, and the replacement is smaller.**
  This WP was written against `agent.refine_json`; [1303](1303-retire-refine-json.md)
  deleted that module in v1.3 after measuring zero use, so there is no task
  tag, no `AgentSuccess.peaks` arm, no `SCHEMA_VERSION` event and no
  `tests/test_agent_surface.py` (the file does not exist; the acceptance
  command below was corrected). `fit_peaks` is reached the way every other
  call is. Two things survive from that bullet. The *contract* fact is now
  `capabilities()`, whose `features` flag is the only thing a client branches
  on. And the agent-facing judgement — when free-standing peak fitting is the
  right answer at all, and what to do with a named position that fits nothing
  — belongs in the skill (`docs/skill/rietx/`), which is where a rule for a
  task *shape* goes (root CLAUDE.md § skill, WP-1330); the manual's
  `using/agents.md` describes the surface's shape and needs no catalogue row.
- `pick_peaks` gets re-documented as a general-purpose tool: a short
  subsection in `../manual/using/indexing.md` with an executed example —
  d-spacings from `q`, widths from `fwhm`, a Williamson-Hall computation done
  *in the example*, not shipped as a helper.
- capabilities: `"peak_fitting": "fit_peaks"` joins `_SURFACE_FLAGS`
  (`capabilities.py`) beside `"peak_picking"`; the hand-written expected-key
  set in `tests/test_capabilities.py` grows by one.

- **A named position that fits nothing is the routine case, not the mistake**
  (folded 2026-09-12 from WP-1110 item 14's mailbox entry; re-verified in the
  tree — `no_intensity` is in `PeakFlag` and in `PEAK_UNUSABLE_FLAGS`,
  `INDEXING_THRESHOLDS_VERSION` 1.3). A component that refines onto its zero
  intensity bound has no gradient on its own position, so its fitted 2θ is
  whatever the seed was; since the equilibrated `normal_covariance` it comes
  back flagged rather than wearing an ordinary-looking 0.06° esd, which two of
  the certified corundum pattern's 62 components had been published with. A
  caller naming positions — a W-H list, a d-spacing lookup — *will* name some
  where there is no peak, and that is a correct request. So `fit_peaks` must
  say what its answer is for one: return it flagged (the peak editor's
  precedent — a component a human placed is theirs to see and remove) or
  refuse, decided deliberately and written into the chapter. Not dropped
  silently: that is the version this WP tried first, and it made the GUI's add
  verb do nothing. `PeakList.usable()` is what indexing consumes, so a public
  `fit_peaks` returning a `PeakList` inherits a `usable`/`peaks` split its
  callers must be told about.
- **Window width is nearly free; window *count* is the cost** (folded from
  WP-1109's mailbox, measured on `[dev]`, darwin/arm64).
  `pseudo_voigt_derivs` costs 11.8 µs at a 25-point window and 13.6 µs at 194
  points — ~11 µs of fixed dispatch, ~0.01 µs per point — so a fitter's cost
  tracks how many windows it evaluates, essentially not how wide they are.
  Widening to be safe is close to free; shaving points to be fast bought ~13 %
  on the refinement path. The rest of that entry was the pre-1112 calibration
  of `forward.WINDOW_FWHM_MULT`, which WP-1112 deleted (windows are now sized
  per peak by `window_fwhm_mult(η)` against `WINDOW_AREA_TOL`); verified
  landed 2026-09-12, and `PEAK_WINDOW_FWHM_MULT` here is untouched and still
  independent of it.

## Non-goals

- Exporting `fit_group_at`, `GroupFit`, `Detection`, `PeakGroup`,
  `pick_peaks_with_state` — case-by-case later; `PeakList` stays the one
  public projection.
- Promoting `PeakEditor` out of `gui/`; `peaks.json` outside projects.
- A shipped Williamson-Hall / size-strain analyzer — the manual example shows
  the computation from a `PeakList`; the package fits the peaks.
- Peaks inside the refinement residual ([1103](1103-peak-components.md)) or
  the background ([1102](1102-component-seam-humps.md)).

## Tasks

- [x] Lift fresh-window sizing from `gui/peaks.py` (`_new_group`) into
      `indexing/` (shared helper; gui imports it back); behavior pinned —
      `tests/test_gui_peaks.py` unchanged-green plus a window-equality test.
      Landed as `indexing.peaks.window_indices` (the arithmetic, called by
      `detect_peaks`) + `group_at` (positions a caller named, with both
      refusals) + `MIN_GROUP_POINTS`; the census scales each width *before*
      the mean, matching `fwhm_seed_curve`'s association, so a named seed set
      reproduces detection's window bit for bit.
- [x] `fit_peaks()` in `rietx.indexing` + the `"unnamed_neighbour"` flag;
      unit tests: a position where detection found nothing, two positions in
      one window, a position in a data gap (refusal names the gap), a named
      position beside an unnamed detected neighbour (flag fires).
- [x] Top-level re-export + `"peak_fitting"` in `_SURFACE_FLAGS` + the
      capabilities expected-key set.
- [x] Manual: `using/indexing.md` — `fit_peaks` section + `pick_peaks`
      general-use subsection with executed d-spacing/W-H example; api-surface
      partition satisfied (documents `fit_peaks` at provisional tier).
- [x] Skill: the free-standing-peaks routing row + its `references/` file
      (WP-1330's rule — a task *shape*, not a body rule), naming the
      named-position-that-fits-nothing answer and the `usable`/`peaks` split;
      `rietx skill --install . --copy` re-syncs the two committed copies;
      `tests/test_skill.py` green. (Replaces this WP's agent-envelope task,
      dead since WP-1303.)
- [x] `io/recipe.py`: the three messages saying free-standing peaks are
      "the v1.4 fit_peaks work" now describe a call that exists — reword the
      refusals (a `GSASII_SPF` recipe and a top-level `single_peaks` block are
      still refused; what changes is that they can name the call to use).
- [x] Tests wrap-up (fast-suite delta stated in the handover) + ruff +
      sphinx `-W` + obs/calc/diff-style PNGs of fitted groups to
      `tests/output/` (`fit_peaks_groups.png`, the four cases).

## Acceptance

`capabilities()["features"]["peak_fitting"]` is derived-True, and the manual's
W-H numbers come from an executed block.

```sh
.venv/bin/python -m pytest tests/test_peak_picking.py tests/test_gui_peaks.py tests/test_capabilities.py tests/test_manual_api.py tests/test_skill.py tests/test_recipe.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- Rachinger (1948), J. Sci. Instrum. 25, 254 — why the doublet is fitted as a
  constrained pair, never stripped (restated from `indexing/peakfit.py`).
- Williamson & Hall (1953), Acta Metall. 1, 22 — the motivating analysis;
  manual example only.
- [1027](1027-gui-peak-picker.md) (the peak editor whose window sizing this
  lifts), [1078](1078-indexing-provisional.md) (the provisional tier).

## Handover log

- **2026-09-13** — **`fit_peaks` ships, and v1.4 is open.** Anyone with a
  pattern can now profile-fit the peaks they name — no structure, no space
  group, no refinement — and get positions with esds, d-spacings and widths
  back. That makes a Williamson-Hall analysis, a d-spacing lookup and an
  ordinary lab check on one reflection first-class uses of this package rather
  than things you had to build a refinement to reach. Two answers the call
  refuses to fudge are what took the work: a position where there is no peak
  comes back flagged and unusable rather than dropped or dressed as a
  measurement, and a window holding a component you did not name says so, which
  on the bundled fluorapatite is worth 2.7 esds on the line you actually wanted
  and 26 esds on a synthetic built to be hard. The milestone opened with its
  acceptance rows written in advance, which is the part a row written at ship
  cannot do.

  **Done.** (1) One window-sizing arithmetic: `indexing.peaks.window_indices`
  (called by `detect_peaks`) and `group_at` (positions a caller named, with the
  out-of-range and gap refusals), with `gui/peaks.py` importing them back —
  the two copies of those four lines are gone. The census scales each width
  *before* the mean, matching `fwhm_seed_curve`, so a named seed set reproduces
  detection's window bit for bit. (2) `rx.fit_peaks(data, instrument,
  positions)` in `indexing/pick.py`, re-exported at top level, provisional tier
  by defining module (1078). (3) The `unnamed_neighbour` `PeakFlag`, its
  `help.py` entry, its word in the GUI highlighter's `PEAK_FLAGS`, and the
  regenerated help-key fixture. (4) `capabilities().features["peak_fitting"]`,
  derived. (5) `using/indexing.md` § Fitting peaks you name, three executed
  blocks over the bundled fluorapatite. (6) The skill's judgement half in
  `references/diagnostics-indexing.md` under §7b, reached by widening the
  existing routing row rather than adding one — so no body cut was owed —
  plus `fit_peaks` in the api index's generator and both committed copies
  re-synced. (7) `io/recipe.py`'s three "not this package's yet" refusals now
  name the call; the refusals themselves stand, because a recipe describes a
  refinement and `fit_peaks` refines nothing. (8) `tests/output/fit_peaks_groups.png`,
  obs/calc/diff for the four cases.

  **Measured** (`[dev]`, darwin/arm64, no other suite running). Fast selection
  4486 passed / 127 skipped, 2:07 and 2:19 on two runs; full selection 4649
  passed / 136 skipped in 22:12. `test_peak_picking.py` collects 46 against 34
  at the branch base — the twelve tests this WP added, no new skips.
  `fit_peaks` costs 0.03 s for seven lines on a 5753-point lab pattern, and
  `build_example("fap")` 0.01 s, which is why the manual's blocks execute
  rather than carrying a no-exec reason. The chapter's Williamson-Hall numbers:
  1355 Å and 0.011 % from seven isolated fluorapatite lines — instrument-
  dominated, and the chapter says so.

  **Gotchas.** (1) **The `unnamed_neighbour` criterion was wrong first, and
  silently.** Written against `PAWLEY_OVERLAP_FWHM_FRAC` (0.5 FWHM) it asks an
  *apportionment* question where an *identity* question was needed, and it
  stayed quiet on a 51 m° / 26-esd bias. It now routes through
  `peakfit.reseed_candidate`, extracted from `fit_group`: the residual proposes
  a position and ΔBIC decides, one authority for both callers. The lesson
  generalises — "is this the same component?" is not "can least squares split
  these?". (2) **A new `PeakFlag` member is a four-surface edit**: the schema
  Literal, `help.py`, `gui/src/lib/rxt.ts`'s `PEAK_FLAGS`, and the committed
  `tests/data/gui/help_keys.json` — and touching `gui/src` means
  `npm --prefix gui ci && run build`, because the dist digest covers it. Two
  suites catch three of the four; the fixture rewrites itself and must then be
  committed. (3) `INDEXING_THRESHOLDS_VERSION` deliberately did **not** move: no
  `pick_peaks` answer changes, and a list that can carry the new flag comes from
  a call that did not exist at 1.3. (4) An observation left alone: in the quiet
  37.4° region of the bundled fluorapatite the frozen background envelope sits
  2-3σ *above* the data (visible in the diff panel of the committed PNG). It
  makes the empty-position answer conservative rather than wrong — a peak can
  only add intensity — but a region where the envelope sat *below* the data
  would push a named empty position to a small positive intensity instead of to
  its bound. That belongs to `background_envelope`, not here.

  **Next**, in order. [1102](1102-component-seam-humps.md) is unblocked and
  independent; its first act is to sharpen its own row in
  [`milestones/v1.4.md`](../milestones/v1.4.md) § Acceptance, which this session
  deliberately left at the level ROADMAP already commits to — a bar set by
  someone who has not read the WP is a bar set too low. Still owed to the
  milestone and nobody's WP: deleting the `AGENT_PROTOCOL.md` pointer, which
  moves `pyproject`'s wheel mapping and the links reaching it from four shipped
  milestone records (they want redirecting to the skill, not dropping).

- **2026-09-12** — pruned on arrival (`/wp-start`). The mailbox is folded into
  Context and deleted: WP-1110's named-position case and WP-1109's window cost
  model are both still true and are now Context bullets, and WP-1112's forward
  note is confirmed landed. One task died and one was corrected: the agent
  envelope (`refine_json`, `AgentSuccess`, `SCHEMA_VERSION`,
  `tests/test_agent_surface.py`) was deleted entire by WP-1303 in v1.3, so the
  contract half of that task is now `capabilities()` and the judgement half is
  a skill reference; and `PEAK_WINDOW_FWHM_MULT` already sits in
  `schemas/indexing.py` with both sites importing it, so the lift is of the
  sizing *arithmetic* only. Added: `io/recipe.py` carries three refusal
  messages (landed with WP-1306, after this WP was written) whose prose says
  the call does not exist yet.

- **2026-08-18** — created from the single-peak planning session; numbering
  opens the 11xx block (v1.1). Designed alongside
  [1102](1102-component-seam-humps.md)/[1103](1103-peak-components.md); this
  one is independently landable and carries the set's one contract-version
  event (the agent task tag + answer arm).
