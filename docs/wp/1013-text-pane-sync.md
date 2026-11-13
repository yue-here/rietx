# WP-1013 — Text pane (CodeMirror 6) + two-way sync

Milestone: v1.0 · Status: ✅ 2026-07-30
Track: The human GUI
Depends on: WP-1009, WP-1010

## Goal

The power-user surface: a CodeMirror 6 pane over the WP-1009 `.rxt`
rendering with rectangular selection, continuous validation, and explicit
apply — the Profex/TOPAS-jEdit lineage, without merge hell.

## Context

- CM6 with `rectangularSelection` (jEdit-style column edits — the reason
  the format is column-aligned) and multi-cursor. Syntax highlighting via a
  `StreamLanguage` regex highlighter — **no lezer grammar build**; the
  Python parser (WP-1009) is the only parser, so the frontend must not
  grow a second one that can drift.
- Sync engine (`gui/src/lib/sync.ts`, framework-free): the server session
  is the single source of truth; the pane is a dirty buffer.
  - Clean pane → every model change pushes a fresh render + revision over
    SSE, applied as a minimal diff to preserve cursor/scroll.
  - Typing → 300 ms debounce → `PUT /api/textdoc {text, base_revision,
    validate_only: true}` → parse errors as CM lint diagnostics at
    line/col (WP-1009 guarantees 1-based line numbers on every error).
  - **Apply is explicit** (Cmd-Enter): continuous validation, explicit
    application. Conflict → 409 + "model changed underneath" banner; no
    three-way merge — re-render and let the user re-apply.
- Applied deltas run as the same public verbs the forms use (WP-1009
  already guarantees this), so they appear in the console as API calls and
  in history as nodes — a text bulk-edit is undoable by checkout like
  everything else.
- CM6 is the one real frontend dependency beyond Svelte/plotly; it lands in
  the committed dist as `vendor-cm.js` (stable filename, WP-1010). MIT
  licensed — no ATTRIBUTION.md entry needed for an unmodified dependency,
  but the lockfile pin is the version statement.

### Inherited

From **WP-1011** (landed 2026-07-30): **the form side now follows the text
document's comparison rule**, which is what makes a two-way sync coherent rather
than merely bidirectional. A cell counts as edited when its text differs from the
*rendered* value (`lib/table.ts`'s `editState`), exactly as `textdoc.changes`
diffs against the rendered document — so a value shown at the precision its esd
justifies (`4.1568(2)` for 4.156783) is not silently truncated by a round trip
through either surface. If this pane's sync ever compares against the stored
float on one side and the rendered string on the other, that asymmetry is where
the drift will come from.

Two smaller ones. The **command palette** (`lib/palette.ts`, Cmd-K) is where a
"Format document" / "Apply text" command belongs — every entry carries the Python
call it makes, and its `isShortcutTarget` is already the rule that stops a
single-letter shortcut firing inside an editor. And **the sidebar is a tab strip
whose tabs all stay mounted**, so a text pane holding unsaved edits survives a
visit to the parameter table; add a tab rather than a route.

From **WP-1012** (landed 2026-07-30): the tab strip is now five tabs wide
(Parameters, Plan, Report, History, Build) in a sidebar clamped to
`clamp(340px, 38%, 560px)` — a *sixth* labelled tab is where the strip stops
fitting, so this WP is the one that has to decide whether the text pane is a tab, a
second column, or a full-width mode. It is also the panel with the strongest case
for not being in the sidebar at all: it is the only one whose content is
line-oriented and wide.

Two facts that bear directly on the sync's state machine. **The head is still the
one reload signal**, and WP-1012 added two more writers of it — a `checkout` from
the history panel and an applied suggestion from the report panel — so the text
pane's CAS revision will go stale from panels that are not it, and the
`STALE_REVISION` path is now easy to hit by hand rather than a theoretical race.
And **the shell reloads the result on the run's *outcome*, not on a state
transition** (WP-1012 fixed a case where a fast stage left stale curves on screen);
if the text pane derives anything from "a run just ended", read that logic in
`App.svelte` rather than re-deriving it.

From the **v1.0 GUI plan** (2026-07-29): two-way text sync is the plan's
top-listed correctness risk. The mitigations are structural and already
decided — single server-side parser, CAS revisions, explicit apply,
all-or-nothing deltas — do not relitigate them; test the state machine
instead.

From **WP-1008** (GUI server, landed 2026-07-30): the text pane's transport is
`GET/PUT /api/textdoc`, **reserved and 404-ing** until WP-1009 fills it in, so
this WP inherits routing for free. Two constraints from the session model: the
PUT is a mutating verb and must 409 with `RUN_IN_FLIGHT` during a run like every
other (the state refusal outranks a parse complaint — tell the user the fit is
running, not that their text is invalid), and a text edit that changes *settings*
persists immediately (`project.json` is written by the verb, not by Save), which
is what keeps "nothing to confirm on close" true.

From **WP-1009** (text document, landed 2026-07-30) — the primitive is done and
`GET/PUT /api/textdoc` are live. What the sync engine has to know:

- **`PUT` is compare-and-set on a `revision`** (`textdoc.revision(text)`, a short
  sha256 of the rendered document). A stale `base_revision` is a 409
  `STALE_REVISION` and there is no merge — the document is *regenerated from
  state*, so a three-way merge would be merging two renderings of the same
  authority. The response to a successful `PUT` carries the re-rendered `text`
  and its new `revision`, so the pane can adopt them without a second round trip.
- **`validate_only: true`** does everything but apply and returns
  `{valid, delta, would_change}` — that is the continuous-validation call, and it
  is cheap (no fit, no compile).
- **An invalid document applies none of itself.** The 400 carries
  `error.details[]`, one entry per problem, each with a 1-based `line`, a
  `where` dot-path and the offending `text` — enough to place a squiggle without
  parsing prose. The frontend gets a regex highlighter and no grammar, by
  decision, so this list is the only diagnostics channel.
- **A re-render discards the user's comments** (see that WP's handover for why
  storing them was rejected). The pane should say so before it replaces the
  buffer — "apply, then re-read" is the flow, and a user who has annotated the
  document will otherwise lose notes they had no reason to expect were transient.
- Canonical output normalises **glob lines** away (`profile.* @` becomes one line
  per parameter on the next render). That is deliberate bulk-edit sugar, and it is
  the clearest case where the buffer *must* be replaced after an apply rather than
  patched.
- `PUT` is a mutating verb: 409 `RUN_IN_FLIGHT` while a run is going, and the
  state refusal outranks a parse complaint.

From **WP-1010** (frontend scaffold, landed 2026-07-30): `api.ts` already has
`textdoc()` / `putTextdoc(text, baseRevision, validateOnly)`, and CodeMirror will
be the **first real dependency in the dist** — everything so far is 48.7 kB of JS
because plotly is served from the Python package rather than bundled. Budget for
it deliberately (the WP-1010 report: ≤250 kB gz first load, 52.8 kB used), and
consider whether `vendor-cm.js` should be a separate chunk — `vite.config.ts`
currently forces one chunk (`codeSplitting: false`) to keep the committed dist
reviewable, which is a decision to revisit rather than inherit silently.

## Non-goals

- No lezer grammar, no client-side parsing beyond the regex highlighter.
- No autosave-on-type applying deltas (validation only until Cmd-Enter).
- No format changes — the `.rxt` spec is WP-1009's; a needed change goes
  there first.

## Tasks

- [x] Text panel: CM6 + `rectangularSelection` + multi-cursor +
      `StreamLanguage` highlighter, loaded as `vendor-cm.js`.
- [x] `lib/sync.ts` state machine (clean/dirty/validating/conflict) +
      minimal-diff application preserving cursor/scroll on re-render. The
      trigger is the **head**, not an SSE frame — see the handover log.
- [x] Debounced validate-only PUT → lint diagnostics; Cmd-Enter apply;
      409 conflict banner + re-render path.
- [x] vitest: sync state-machine transitions (clean edit, concurrent model
      change, conflict, re-apply); highlighter never claims validity (only
      the server does). 85 → 139 cases.
- [x] `tests/test_gui_server.py`: textdoc CAS-conflict row (two writers,
      second gets 409, no partial apply).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1009 (format + parser — normative); Profex's synced-text behaviour as
  the UX precedent.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

The **text pane** (WP-1013, `gui/src/panels/Text.svelte`, `gui/src/lib/`) is the
`.rxt` document in CodeMirror 6, a tab of the one column (WP-1034), and the one panel
whose content is line-oriented, the format's columns being aligned precisely so a
rectangular selection can hit one field. It stays mounted while hidden (a typed
buffer survives a look at the parameter table) and builds its editor on first
entry. Four rules. **The head is the reload signal** — no third SSE frame type was
added, because the head already moves for every writer and the parameter table
already reloads on it. **There is no merge and no force-apply**: a stale buffer
re-reads and re-applies, which is also what the server's 409 `STALE_REVISION`
says, and the reason is sharper than "merging is hard" — the loser's document
carries the winner's *old* values for every row it did not touch, so applying it
would silently revert them. **Only the server decides validity**: `lib/rxt.ts` has
no `error` token to emit (asserted from both sides, with the shared vocabulary
pinned to `textdoc._KEYWORDS` and `StageSpec.model_fields` by
`test_the_highlighter_quotes_the_parsers_words`), and *indentation is the parser's
own dispatch*, so an indented `plan` is a parameter named `plan`. And **a response
carrying an older `seq` is dropped** — a 300 ms debounce puts two validations in
flight across one pause and they can land out of order. CodeMirror is a separate
committed chunk (`assets/vendor-cm.js`, 328 kB) imported *dynamically*, so it
stays off the boot path; `tests/test_gui_dist.py` asserts the split, because a stray static import would
inline the library and no byte count would say so. The editor's document and its diagnostics are `$effect`s
over the sync state, never pushed — pushing let a head move wipe a squiggle while
the problem list still named the line.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
- **2026-07-30** — **landed.** All five checklist items; vitest 85 → 139,
  `svelte-check` clean, ruff clean, the fast suite green. Driven end to end
  in Chrome for Testing, which is where the one defect came from.

  **Four decisions, three of which the charter left open.**

  *The pane is a **mode**, not a sixth tab.* WP-1012 handed this WP the
  question and it decides against the strip: five tabs already fill a
  `clamp(340px, 38%, 560px)` sidebar, and this is the one panel whose content
  is line-oriented — the format aligns its columns *so that a rectangular
  selection can hit one field*, which a 340 px column undoes. So the whole
  window, toggled from the header and from the palette (`t`). It stays
  **mounted while hidden**, exactly as the tabs do, because a buffer with
  typed-but-unapplied edits has to survive a look at the parameter table; the
  editor itself is built on first entry.

  *The **head** is the reload signal — there is no new SSE frame type.* The
  charter said "every model change pushes a fresh render + revision over SSE",
  which would have meant a third frame type beside events and run state.
  Unnecessary: the head already moves for every writer (a run, a checkout, an
  applied suggestion, a form edit), the parameter table already reloads on it,
  and WP-1008's rule that the run state is not an event exists precisely so
  that new frame types are decisions rather than reflexes. `GET /api/textdoc`
  on `head` costs one render of the parameter rows, and only while the pane is
  open.

  *CodeMirror is split out **and** off the boot path*, which serves WP-1010's
  one-chunk decision rather than reversing it. Two independent reasons, and
  they point the same way: a committed dist has to diff reviewably, and ~330 kB
  of minified third-party bytes inside `app.js` would sit in the middle of
  every application diff; and `panels/Text.svelte` imports the adapter
  dynamically, so the page still loads `app.js` and nothing else. Measured:
  `app.js` 104.7 → **114.2 kB** (40.4 kB gzip) for the pane's own code,
  `vendor-cm.js` **328 kB** (106 kB gzip) fetched on first open. In the
  browser: **boot-to-interactive 81 ms** with zero textdoc/vendor requests
  before the pane is opened, and **132 ms** from the click to a mounted editor.
  `tests/test_gui_dist.py` asserts the split rather than trusting it — a stray
  static import would inline the library, and no byte count would say so.

  *There is no force-apply.* A stale buffer has exactly one exit and it is the
  one the server's 409 recommends: re-read, re-apply. Sending the *new*
  revision with the old text would be a merge by another name — and worse than
  the usual kind, because the loser's document also carries the winner's old
  values for every row it did not touch, so it would silently revert them.
  That is now the sharpest of the Python tests.

  **The defect, and it took a browser.** `load` cleared the editor's
  diagnostics unconditionally, so a head moving underneath an *invalid* buffer
  wiped the squiggle and the gutter marker while the problem list below still
  named the line — two views of one answer, able to disagree. jsdom could not
  see it: the vitest assertions read `textContent`, which is the list. The fix
  is structural — the editor's document *and* its diagnostics are now
  `$effect`s over `sync`, so the four places that change the state push nothing
  and cannot forget to. The regression test asserts through
  `diagnosticCount(view.state)`, and was checked by re-introducing the push and
  watching it fail. Measured before/after on a head move: gutter 1 → 0 and
  underline 1 → 0, now 1 → 1.

  **Two things worth knowing before touching this.**

  `lib/rxt.ts` has **no `error` token** and that is the property the whole
  design rests on: the frontend colours the document and only the server can
  call it wrong. It is asserted from both sides (`rxt.test.ts` and
  `test_textdoc.py::test_the_highlighter_quotes_the_parsers_words`), and the
  same Python test pins the shared *vocabulary* — keywords, flag words,
  annotation words, and the stage keys, which are derived from
  `StageSpec.model_fields` rather than restated. One rule there came from
  reading `textdoc.parse` rather than the format: **indentation is the parser's
  own dispatch**, so an indented `plan` is a parameter named `plan`, not a
  keyword line.

  And a response carrying an older `seq` is **dropped**. With a 300 ms debounce
  two validations can be in flight across one pause and they can land out of
  order; without the guard the slow first answer paints squiggles at line
  numbers the buffer no longer has.

  Verified in the browser, in order: 81 ms boot → open → nine token classes
  painted → an alt-drag down the vary column drew **7 selection rectangles**
  on the `@` column → edit → one validate PUT → `ready to apply` → Cmd-Enter →
  `limits 3.5 22` applied and persisted across a reload → `mode nonsense` →
  one problem at line 4 in the parser's own words → a `PATCH /api/params` from
  outside → **stale**, edit intact, Apply disabled → Re-read → in sync. No
  unhandled page errors.
