# Hardening the API and its design rules: two plans

Written 2026-11-23 on `f9adf0e57`, the review behind WP-2302, WP-2303 and WP-2304. The practice survey behind it is
`docs/practice.md` § How an API meets a caller's mistake. A blind reviewer critiqued the first
draft; this version takes in its twelve points, listed at the end with what changed.

## The probe: what the rule text does when agents implement and review

**Set-up.** A toy package, `minirefine`, built in rietx's shape: a parameter table with
`set_vary`, globs, locked and tied entries, plans whose stages replace the vary flags, and a
`fit(mode=...)` that checks `mode` only when it builds the result. Three versions of its
rulebook:

- **v0**: today's Rule 4 API test.
- **v3**: v0 plus the misuse clause as prose (Russell's scale; remove the mistake or raise;
  warn when a request changed less than it named).
- **v4**: v3's clause plus a test obligation, two meta-tests (a misuse test per public verb;
  every `Literal` argument refused at entry), and `mode` already checked at entry.

Six Opus implementers, one per version and task, were told only to read the rules and do the
task. The tasks were `Model.hold`/`unhold` (the trap behind WP-1435) and excluded regions with
an `exclude_policy` choice (WP-1033's ground). A hidden set of 12 misuse calls the agents never
saw was then run on each result. Three Opus reviewers, one per version, reviewed one flawed
`hold` with five planted defects. Files: `probe/build.py` makes the package and its rule versions, `probe/score.py` is the
hidden misuse set, and `probe/REVIEWS.md` holds the reviews. The agents' finished packages
were not kept.

**Implementers.** Outcomes of the 12 misuse calls:

| Rules | Silent | Warned | Raised or defined out |
|---|---|---|---|
| v0 | 4 | 0 | 8 |
| v3 | 2 | 1 | 9 |
| v4 | 1 | 3 | 8 |

- Each difference between rows is one case in one run. The exclude task separated the
  versions on one case only (an interval outside the data). No conclusion about the rule text
  rests on these counts.
- All three `hold` implementers kept `hold("cel.*")` silent when the glob matched nothing. The
  toy's `set_vary` docstring declares that silence, and rietx's own CLAUDE.md describes `hold`
  the same way, so this is partly recall of that file.
- The warning clause softened refusals. v3 raised on `set_vary(True)` for a held path. v4,
  whose rule text repeats "a warning is for a request that changed less than it named", only
  warned there and on holding a tied path. rietx itself raises on a held literal
  (`refine.py:3557-3570`).
- Messages followed the nearest example. v4's base raises `fit(mode=) takes one of [...]`, and
  the v4 agents wrote every new message in that form.
- No implementer fixed a defect it did not have to touch: the late `mode` check survived all
  four v0 and v3 runs. Whether a meta-test would have forced that fix was not measured, because
  v4's base had it fixed already.

**Reviewers.** All three caught the bare-string defect and the silent typo. None flagged the
silent glob. The rule text made no visible difference.

**Limits.** One run per cell, a toy package, and every agent loaded rietx's CLAUDE.md. Each
agent's notification reported 105-111k tokens, about 970k for the nine.

**What it says.** Two observations are robust enough to act on. Conventions already in the
code spread to new code, whether they are good (a message that names its argument) or bad (a
silent empty glob). And loose rule wording can move an agent the wrong way: the warning clause
turned two refusals into warnings. So the rule must be precise about when to raise, the
existing surface must be fixed because new code copies it, and the checks carry the weight.
That checks reach unedited code is an inference, not a measurement.

---

## Plan 1: harden the design rules

**Why it matters.** The rules are read by the agent that implements and the agent that
reviews. The probe shows that they copy the code around them, and that a loosely worded rule
can make them softer than the code already is. **Aim.** A caller's likeliest mistake fails at the
first bad call, whoever writes the code. **Practice.** Bloch's fail fast and Russell's scale
(practice.md); NEP 52's allow-list test as the model of a check that caps growth.

**Steps.**

1. **Rule 4, "A new API".** Append:

   > It names its likeliest misuse, and a test makes that call. The mistake is removed where
   > Rule 1's first kind allows. Otherwise a literal the call cannot honour raises before any
   > work, naming the argument and the fix. A pattern the caller passed that matches nothing
   > warns. A pattern skips the rows it cannot change without a word when it changed others.

   This is the policy `Refinement.set_vary` already follows, written down. A plan's globs reach
   the table directly (`refine.py:5206`), so WP-1414's silence for plans is untouched.

2. **Rule 5, "Convention".** Append: "A convention that lets a caller's likeliest mistake pass
   in silence is a convention found wrong." The existing clause then applies: it is changed
   everywhere in one change. This leaves the first sentence of "Conflicts" (the API's shape
   follows rietx convention) as it is.
3. **Why this package exists.** Point "The API follows current Python practice" at the
   practice.md section, so the claim has its survey.
4. **Mechanisms**, one entry in the project CLAUDE.md § Invariants, each a test:
   - **M1.** Every choice argument of a public callable is refused at entry. A meta-test passes
     each a bad value and asserts a `ValueError` naming the argument, with `compile_model`
     patched to fail if reached, so "before any work" is checked. The valid members come from
     the live registries (`PLAN_PRESETS`, `least_squares.SOLVERS`, `backend.api.BACKEND_NAMES`,
     `get_args(Mode)`), never a second copy. A table gives each callable a cheap example call.
   No skill or review checklist gains prose.

**Order.** Steps 1 to 3 are one docs change, landed 2026-11-23 with the WPs filed below. M1
fails on today's tree, so it lands with WP-2302.

**Dropped.** A misuse test per public verb (M2), dropped 2026-11-23 on Yue's go-ahead: the
check proves only that a test exists, a stub passes, and 138 callables would enter a backlog.
The rule's "a test makes that call" is held at review instead. A rule that one argument name
means one thing, and its `help.py` arm (M4): the rule would prejudge the `path` question in
Plan 2 E, and the arm means writing a meaning for about 162 argument names. The `**kw` check
(M3) went with Plan 2 F.

**Decisions for Yue.** Steps 1 and 2 amend your rules. Approved 2026-11-23 ("as you advise").

## Plan 2: shore up the API's weak points

Each item names its siblings and what it deliberately leaves alone.

**A. `mode` refused at entry** (fail fast; settled). `mode` is typed `Mode`, a `Literal`
(`schemas/common.py:38`), and still fails late. `refine`, `refine_sequential`, `Refinement.fit`
and `run_stage` raise a pydantic error about an internal schema, `refine(mode="rietvled")`
after 2.8 s of a 4.1 s fit. `Refinement.parameters(mode=...)` and `Refinement.suggest(mode=...)`
take it too, and `parameters` answers silently. Check membership at entry with `refine_multi`'s
message form. Siblings: the 22 choice arguments typed as plain `str` are surveyed under M1.
`solver` and `backend` already refuse at the call and name their choices, so only those that do
not are changed. No argument is retyped as `Literal` where a registry exists. Free text
(`label`, `title`, `header`, `x_label`) is left alone. M1 lands here.

**B. `set_vary(path, False)` undone by a plan** moves to WP-2300, which owns how a parameter is
declared fixed. The first draft's diagnostic is withdrawn. It needed state outside the models,
which no node records before the first fit (`refine.py:3518-3521`). Its grounds were also
wrong: Rule 1's first kind is the package acting, and this only reported. WP-2300 inherits one
measurement to make first: which calls still read a vary flag a caller set, given that a plan
starts every fit from nothing free (WP-1208).

**C. A glob that matches nothing, on a direct call.** `set_vary`, `hold`, `unhold`, `untie`
and `tie_equal` return `[]` in silence. Plans already reach the table directly
(`refine.py:5206`), so these public verbs can warn without touching plans. Two things come
first:

1. Separate "matches nothing" from "changes nothing". A repeated `hold` returns `[]` by design,
   and that case stays silent.
2. Audit the internal callers of the five verbs: `gui/session.py:1867, 1870, 4210`,
   `gui/textdoc.py:1318`, `report/layer2.py:1434`, `strategy/parameter_interval.py:277`,
   `strategy/fraction_profile.py:216`, `strategy/magnetic.py:1369`, `sequential.py:1286`. The
   GUI never shows a python warning, so its callers need the GUI's own message channel.

**D. Reader repairs reach the fit's diagnostics.** Carry the reader's notes on `PatternData`,
and have the fit copy them into `result.diagnostics`, deduplicated by code, since the fit
already repeats `PATTERN_DEAD_CHANNELS`. An agent reads `result.diagnostics` every time. The
pattern file is stored as bytes, so the field changes no stored format. The first draft's
"warn once" step is dropped: one warning covers a batch of 200 files, the weak channel
`set_vary`'s docstring already rejects. Not generalised: `Structure` and `Instrument` carry
CIF and instrument-file repairs too, but both are stored in history nodes, so a field there is
a stored-format change and waits for its own decision.

**E. Names.**

- `two_theta_range` as a requested window becomes `two_theta_limits`: `pick_peaks`,
  `fit_peaks`, `rx.viz.plot_result` (`viz/plots.py:775`) and `pick_peaks_with_state`
  (`indexing/pick.py:75`). Grounds: Rule 5's convention (10 calls to 2) and GSAS-II's own term,
  "Limits". `DataRef.two_theta_range` (`schemas/project.py:91`, stored in `project.json`) is the
  span the data covers, so it keeps its name. The split becomes the rule: "limits" requests a
  window, "range" describes one. The fields in `schemas/indexing.py:2363` and
  `report/schemas.py:989` are measured against that split before anything moves.
- No compatibility shim. A shim needs `**kw` or a sentinel, and rietx's few users are in
  direct contact. The changelog names each rename.
- The "how many" family (`top_n`, `top_k`, `max_classes`, `check_top`) is measured first. The
  names may mean different things.
- `path` names a file in the writers and a parameter dot-path in `tie`, `help_for` and
  `profile_interval`. Renaming either is a name on the top-level surface with no field
  standard, so it is a decision for Yue. Options: leave it and say which in each docstring, or
  rename the dot-path arguments to `param`.

**Dropped from the first draft.** F, replacing `**kw` with explicit arguments. The forwarders
already raise `TypeError` at binding, naming the bad keyword. Explicit copies would drift from
`fit`'s signature with no parity test, and they would break `Project.fit`'s
`kw.setdefault`, where `two_theta_limits=None` today overrides the document's window.

**Not done, with reasons.** The 209-name namespace (typed results are Rule 4's contract with
agents). Long keyword-only lists (scientific Python practice; keyword-only arguments remove
Bloch's transposition risk). Paired function-and-method spellings (lmfit's precedent).

**Packaging.** Three WPs, combined by seam: **A + E** (entry checks and names; M1), filed as WP-2302; **C**
(glob verbs, beside WP-2300), filed as WP-2303; **D** (readers, under `io/CLAUDE.md`), filed as WP-2304. B goes into WP-2300's
`### Inherited`.

---

## Critique

### What the blind review changed

| # | Point | Change |
|---|---|---|
| 1 | v4's row miscounted; each step of the gradient is one case | Table corrected (1/3/8); counts no longer carry a conclusion |
| 2 | The warning clause turned refusals into warnings | Rule 4 wording now raises on a literal and warns only on a pattern |
| 3 | "Only a check reaches unedited code" was never measured | Labelled an inference |
| 4 | Three `hold` runs, not six; CLAUDE.md describes `hold`; reviews unsaved | Corrected; contamination stated; reviews saved to `probe/REVIEWS.md` |
| 5 | Plans already bypass the public verb; internal callers listed; repeat `hold` returns `[]` | C rewritten around the audit and the matches/changes split |
| 6 | Step 2 contradicted Rule 5's first sentence and WP-1414; step 3 prejudged `path` | Step 2 moved to "Convention"; step 3 dropped |
| 7 | `two_theta_range` siblings undercounted; `DataRef`'s is stored; shim needs `**kw` | E widened; `DataRef` keeps its name under a describe/request split; shim dropped |
| 8 | `mode` is already `Literal`; `solver`/`backend` already refuse; retyping duplicates registries | A and M1 check against the registries |
| 9 | F gains little and breaks `setdefault` | F and M3 dropped |
| 10 | B's diagnostic needs unrecorded state and had the wrong grounds | B moved to WP-2300 |
| 11 | M2 keys collide; M4 costs ~162 meanings; presence checks only | M2 keyed by qualified name, later dropped on cost (2026-11-23); M4 dropped |
| 12 | "Warn once" is the channel the package rejects | D1 dropped; D2 deduplicates by code |

### Weaknesses that remain

1. **The probe cannot pick between v3 and v4.** It shows wording and conventions matter. It
   does not show the test obligation helps. A second probe would need an arm with meta-tests
   on an unfixed base, several runs per cell, and agents that do not load rietx's CLAUDE.md.
2. **Rule 4's misuse test is held by review alone.** With M2 dropped, nothing checks that a
   new verb's test exists or makes the likeliest mistake. The probe's reviewers missed the one
   silence that looked deliberate.
3. **M1's example table is upkeep.** Each callable with a choice argument needs a cheap call.
4. **C's GUI callers need a non-warning channel.** The plan names the need, not the channel.
5. **Raising where rietx was silent breaks scripts** (Hyrum's law). rietx's users are few and
   in direct contact, so the cost is small and known.
