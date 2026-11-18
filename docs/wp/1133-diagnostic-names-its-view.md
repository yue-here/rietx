# WP-1133 — A diagnostic names the view that shows it

Milestone: unscheduled · Status: 🔄 2026-11-18 — claimed by @yue-here (ghostshift runner)
Track: The specimen is not an angle, and the neutron follow-through
Depends on: — (WP-1130 closed 🛑 2026-09-04; it did **not** deliver the panel,
and this WP inherits it along with the argument that licenses it — see
### Inherited)
Priority: P3 2026-09-23 — a diagnostic that is right and says less than it could

## Goal

A finding says which rendered view makes it legible, the operator protocol
says which channel answers which kind of question, and the one claim still
open — that an image pays for itself on a question an agent cannot name in
advance — is measured as round trips rather than asserted.

## Context

Split out of [1130](1130-background-reference.md) at its 2026-08-27 review.
1130's Finding 8 is the full record; the load-bearing numbers are restated
here so this file stands alone.

### What the 2026-08-23 session measured about the image channel

The premise is that the package supplies information and the agent supplies
the reasoning, so which channel carries the information efficiently is a
design question, not a rendering detail. The only controlled evidence is that
session grading itself, and it is a negative followed by a qualified positive.

- **Vision did not find the error.** The maintainer's obs/calc/diff plot was
  in context from the first message; the model did not raise the background,
  the maintainer did. Told, the model matched the supplied hypothesis to
  whichever background sat highest rather than detecting anything. Its one
  unaided visual judgement was **inverted**: a background well below the
  inter-peak valleys read as sound, one at the valley level as suspect, when
  the second was the closest of five to TOPAS (0.75–0.81) and the four
  "sound" ones were at 0.50–0.59.
- **Vision found it once, from a purpose-built panel**: the anchored curve
  tracing the data floor with every fitted background ~30 counts beneath it.
  Two properties separated that panel from the standard one, and both are
  constructible. The same error, as a fraction of panel height: standard
  obs/calc/diff over 14–70°, **2.6 %**; its 18–25° zoom, **4.9 %**; y cropped
  to the background's own range with the reference overlaid, **14.0 %**. More
  decisive than the scale is **a reference inside the frame**: with only the
  fit in frame the eye's sole comparator is its prior, and the prior was
  wrong. A uniform factor of two in level leaves a smooth monotone decay,
  which has no visual signature at all.
- **Cost, for a question already known.** The per-region table carrying the
  finding is ~123 tokens; the figure at 1373×1000 is ~1830 (vision ≈ w·h/750
  after the 1568 px long-edge downscale), a factor of ~15, plus ~1 s of
  matplotlib against a numpy pass. Vision is not the cheap channel for a
  question you can name. Where it might earn its tokens is the question that
  cannot be named in advance — "what is wrong with this fit" — and there the
  comparison is against the *round trips* an agent would otherwise spend
  discovering which statistic to compute. That comparison is unmeasured and
  is this WP's third task.

Consequence: a plot presents a reference and never replaces one, and the
surface should say which channel answers which question rather than leaving an
agent to guess.

### The seams

`GuardFinding` (`strategy/staged.py`) carries `code`/`paths`/`value`/`message`
and every guard `Diagnostic` (`schemas/common.py`) carries `where` and
`value`; neither says which rendered view makes the finding legible.
`viz.plot_for_vlm` is the montage. 1130 was to add a background panel to it
and closed without one (Inherited, Gap C).
`tests/eval_report_agent/` and `tests/eval_agent_surface/PROTOCOL.md` hold the
eval discipline: register the read-out before running, enforce the condition
in a shim rather than the prompt, real subagents with model and effort as
variables, and no pooling across rounds.

### Inherited

- **2026-09-28, from [1338](1338-the-skills-own-gates.md): a real-agent round here launches with
  `--setting-sources project,local`.** `~/.claude/skills/rietx` is a
  symlink to the maintainer's checkout, and a user-level skill shadows a
  workspace one of the same name, so without the flag every cell reads the
  checkout's body and a `bare` cell is not bare. Check which body each
  cell was handed off its transcript (`tests/eval_skill_placement/
  runner.condition_held`).

From **WP-1406** (2026-09-15), which documented the track this WP was waiting on:

- **There is a rendered view to name now, and it is live rather than a file.**
  `rietx watch` serves every run a fit records, drawing the obs/calc/difference
  plot from `snapshot.json` and redrawing it in place per stage. So a finding
  that wants to say "look at this" has a second answer beside a written page: a
  URL into a run that is still being written. Its chapter is
  `docs/manual/using/cli.md` § `rietx watch`, and what a run holds is
  `using/refining.md` § Watching a run.
- **The view is per stage, which changes the round-trip question this WP
  measures.** The old `fit.html` was one page at the end of a run. A watcher
  view exists while the fit is still going, so "an image pays for itself on a
  question an agent cannot name in advance" can now be asked about a *mid-run*
  image, which is a different and probably stronger case. Worth deciding
  deliberately rather than inheriting the end-of-run framing.
- **No naming mechanism was added.** `Diagnostic` still has no field pointing at
  a view, and WP-1406 deliberately added none. This WP is still the one that
  decides whether a finding names its view and how.

From **WP-1130** § Gap C, 2026-09-04. **This WP's dependency changed shape
rather than being discharged.** 1130's line above — "the background panel with
a reference in the frame is the first view worth pointing at" — assumed the
reference would be an *anchored background estimate*. That estimator is now 🛑
on measured evidence: it returns **zero** anchors on `FAP.XRA` at every window
and 19 of 59 498 on `11BM_NAC.fxye`, and on the one pattern where it works it
has 1 anchor in the 486 channels of the region that matters. The fallback of
bracketing between the two shipped estimators is also refused *as a threshold*
— over eight realisations of a known background it contains the truth in all
seven regions in four, and it fires on a correct fit in two regions of seven.

What survives for this WP is the distinction 1130 had to draw to keep the panel
alive, and it is a **1133-shaped** distinction rather than a background one: **a
reference good enough to *show* is not good enough to *fire* on**, because a
reader compares and a guard thresholds. That is an argument about what a *view*
is for, and it is now the strongest single reason this WP exists. 1130's panel
is still coming and is still the first view worth pointing at; its reference is
a labelled band, not a curve.

*Superseded in part, 2026-11-18.* The panel is not coming. 1130 closed 🛑 on
2026-09-04 and no open WP carries the panel (`grep -l "background panel"
docs/wp/` finds only 1130 and this file). So the montage holds the overview,
the Δ/σ panel and the worst-region zooms, and nothing else. A background level
still has no view, because a uniform factor of two in level leaves a smooth
monotone decay with no visual signature (§ What the 2026-08-23 session
measured).


From **WP-1307** (round 1.1, E-RAMP complete 2026-08-29, four cells): **making
the plotting library present did not make the package's plotting surface the
way an agent draws.** Round 1.1 installs `rietx[viz]` in every workspace
*precisely* so `plot_result`, `plot_for_vlm` and `write_html` are usable — that
was 1.1's declared repair of a round-1.0 defect, where four of six agents
hand-rolled an SVG writer because no plotting library was installed and no
conclusion was drawn from it. The repair did not take. Across **four cells, two
models (`sonnet` and `opus-5`) and both conditions, all three surfaces were
called zero times.** The one cell that plotted at all (`ramp-bare-opus5`) wrote
matplotlib by hand against the machine's user-level figure-style skill, saved
three PNGs and read them back.

Two things follow for this WP, and they pull in opposite directions.

- The **positive** half of 1133's open claim gains its first unprompted
  observation: an agent that had no instruction to draw anything drew three
  figures and looked at them, mid-run, while deciding. Availability was not the
  blocker for *drawing*.
- The **channel** claim is untouched, and the read-out that would have measured
  it did not fire. Nothing here says the montage pays for itself, because no
  agent reached the montage. A view an agent renders for itself is not the view
  a diagnostic named, and 1133's question is the second one.

So the design question this sharpens is not "is the image channel worth it" but
**why a hand-rolled plot beat a purpose-built one that was installed and
documented**. Whatever this WP builds, presence plus documentation is now
measured as insufficient to get it called: a finding has to *name* the view at
the point the reader is deciding. That is this WP's own thesis, and round 1.1
is the first evidence that the weaker version of it fails.

Round 1.1's four cells are E-RAMP only; the four E-ZRM reel cells are
outstanding, so this is a finding at N = 4 on synthetic data, not a rate.

### Task 3, the proposed round (2026-11-18; registered, not run)

**Two of the task's three inputs are gone.** 1130's panel never shipped (Gap C
above). 1130's trigger fit no longer carries the error: re-run on the tree in
1130's own session, its background lands at 0.90–1.22 of TOPAS's under nine
protocol variants, against the 0.50–0.71 the session measured
(`1130-background-reference.md`, lines 435–457). So the round below uses
three bundled fits with one planted error each, and the montage as it is.

**Fits.** Each is a synthetic pattern from a bundled CIF with one error planted
in the model the agent is handed, and no diagnostic naming it.

- F1, a missing minor phase: a second phase at 5 wt % in the data, absent from
  the model. The montage's overview marks its peaks as unmatched.
- F2, a wrong zero shift held fixed: 0.03° off, every other parameter refined.
  The worst-region zooms show a derivative-shaped residual.
- F3, a background held at half its true level between the peaks. The montage
  has no reference for it, so the image is predicted **not** to help here.

**Conditions**, enforced in the workspace and never in the prompt.
`numbers`: the venv has no matplotlib, so `plot_for_vlm` raises on import.
`montage`: the montage PNG is in the workspace and the prompt names its path.
Both get the result as JSON, the script that made it, and the skill.

**Prompt**, identical in both: "This refinement is wrong in one way. What is
wrong, and what would you change?"

**Read-outs, fixed before any run.**

- R1: the planted error named, scored by a rubric of accepted phrasings per
  fit, written before the first run.
- R2: tool calls before the final answer.
- R3: input plus output tokens, and cost.

**Decision rule.** The image earns its claim if the `montage` arm wins R1 on
F1 or F2 at equal or fewer R2 calls. If it wins on neither, the skill's
hypothesis clause is deleted and `Diagnostic.view`'s `see:` line is
reconsidered. A win on F3 would contradict the 2026-08-23 measurement, and is
reported as that, not as support.

**Cost** (extrapolated from `tests/eval_skill_placement` round 1.0, $0.30–0.47
a run for haiku and sonnet and $1.26–2.07 for opus, on a task that read a
printed fit; this one runs code, so take one to three times that):

| option | runs | estimate | settles |
|---|---:|---:|---|
| A: sonnet, N = 2 | 12 | $6–18 | whether the effect exists on one model |
| B: sonnet and opus, N = 2 | 24 | $25–90 | whether it holds across models |
| C: three models, N = 3 | 54 | $60–200 | a rate per model, to N = 3 |

The repo-side work (fits, shim, scorer, `runner.py` from
`tests/eval_skill_placement/`) costs no money and is the next session's first
item once an option is picked. Launch with `--setting-sources project,local`
(Inherited, 1338).

## Non-goals

- **Not embedding an image in a diagnostic.** The pointer is a name; the
  caller decides whether to spend the tokens.
- **Not a new montage.** `plot_for_vlm` is the montage; a view this WP names
  must already be drawable, and the one 1130 adds is the first.
- **Not the background reference itself.** That is 1130.

## Tasks

- [x] **The view pointer.** A field on `Diagnostic` (and the `GuardFinding`
      constructor feeding it) naming the rendered view that shows the finding —
      a member of a closed vocabulary drawn from what `plot_for_vlm` can render,
      so a name with no renderer fails a meta-test (the root CLAUDE.md's
      declared-name rule). `None` where no view helps, which is most findings,
      and honest. Manual Part 1 gains the field or the partition fails.
      *Landed 2026-11-18 as a lookup, not a stored field*: `Diagnostic.view`
      reads `rietx.help.DIAGNOSTIC_VIEW_OF` by code, as `explanation` reads
      `DIAGNOSTIC_HELP` (WP-1985: a per-code text is never stored). So no
      `GuardFinding` constructor changes and the JSON form is unchanged.
      The vocabulary is `rietx.help.DIAGNOSTIC_VIEWS`: `plot_for_vlm.overview`
      and `plot_for_vlm.residual`, each the matplotlib `gid` of its panel.
      Three codes name one, each checked on a rendered fit that fires it.
      The notebook fold prints a `see:` line; `str(diagnostic)` does not
      (WP-1985: the text form leaves out what is the same for every finding).
      Manual: `reference/result.md` § Diagnostics.
- [x] **The channel rule in the skill** (`AGENT_PROTOCOL.md` became the skill
      in v1.3). Numbers for a question you
      can name (~15× cheaper), an image for one you cannot, and never an image
      without a reference in the frame. One row, the measurements above as its
      evidence.
      *Landed 2026-11-18 in `references/diagnostics.md`'s preamble*, beside the
      `d.explanation` line, since `d.view` is how the pointer reaches an
      agent. `judging.md` was the guess and is closed to growth: 34 575 B
      against a 34 600 B budget (`tests/skill_caps.py`). The body is over its
      budget too, so a row there would be paid for by a cut. The
      image-for-an-unnamed-question clause is tagged `(Hypothesis: …)` until
      task 3 measures it.
- [ ] **Measure the round-trip case.** Give an agent a fit and "what is wrong
      with it", with and without the montage (1130's panel in it), and count
      calls to answer as well as tokens — on 1130's trigger fit and on two
      bundled fits with a planted error each. Pre-register the read-out. The
      result may be that the image buys nothing; that is a result to record
      and act on by removing the pointer's claim, not to soften.
      *2026-11-18*: the round is registered in § Task 3, the proposed round,
      which replaces 1130's panel and trigger fit. Its spend waits on the
      maintainer's pick from that section's menu.
- [ ] Tests (the vocabulary meta-test; the field's JSON round trip; the eval's
      shim) + the montage PNGs the eval used to `tests/output/`.

## Acceptance

Every view name a diagnostic can carry has a renderer, and the round-trip
measurement is recorded with its pre-registered read-out and a decision.

```sh
.venv/bin/python -m pytest tests/test_diagnostic_views.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- [1130](1130-background-reference.md) § Finding 8 — the measurements
  restated above.
- `tests/eval_report_agent/` and `tests/eval_agent_surface/PROTOCOL.md` — the
  eval discipline the third task follows.

## Handover log

- **2026-08-27** — created, split out of 1130 at its review; nothing measured here yet.
