# WP-NNNN — <title>

Milestone: v0.X · Status: ⬜
Track: <a #### heading under the milestone's ROADMAP section; no line if none>
Depends on: WP-MMMM (or —)
Priority: P? YYYY-MM-DD — <the rubric row it meets, and the move if any>

<!--
Before filing, fold first: a new WP is the answer only when no open WP (⬜ or
🔄) owns the work. A follow-up often belongs to one already queued, and a
second WP for the same work splits its evidence between two files — two of
WP-1469's four follow-ups (1525, 1526) were withdrawn the day they were filed,
as folds into 1317 and 1420. So read the index's open rows, then the Goal and
Tasks of every WP a title makes plausible (protocol step 1's exception to
reading one WP file), and fold into the owner as a dated `### Inherited` entry,
re-rating its Priority line if the evidence moves its row. Never into a ✅/🛑
WP: what a closed WP's fix did not cover is a new WP. File only when none
owns it, and write why into the first handover bullet ("no open WP owns the
step scan"; "1420 fences the threshold out"), because a check that leaves no
trace cannot be told apart from one that never ran.
Numbering: MMNN — the block of the milestone this WP is OPENED for, then the
next free sequence number (v1.1 → 11xx, rietview → 15xx; a named milestone
claims the next free hundred when it is queued); an unscheduled WP takes the
newest block. The number never changes when the WP moves, so it is not where the WP
stands: the Milestone line is, and the WP index (README.md here, generated)
places the row by it. Never recycle a retired number.
Milestone values: a lowercase name for an open or queued milestone
(`magnetic`, a row of ROADMAP's table), vN.N for one that shipped as that
version, vN.N.x (shipped after that milestone, in its patch releases; closed
by WP-1540), unscheduled. A name never becomes a number: the release that
ships it is numbered when it is cut (ROADMAP protocol rule 6).
Track: the #### heading, verbatim, that the WP sits under in its milestone's
ROADMAP section. A section without tracks takes no line. A heading ROADMAP
lacks fails tests/test_docs_consistency.py.
Depends on: the index reads WP numbers (and #N) off this line. A number
outside brackets is hard, and one followed by "soft" is a preferred order:
"1327 (the moment); 1326 soft (the satellites)" shows as "1327 (1326 soft)".
Status values: ⬜ not started · 🔄 in progress · ✅ shipped · 🛑 no-go.
Format: "Status: <glyph> <YYYY-MM-DD> — <free text>". The date is required
for every glyph except ⬜; the free text is optional and may wrap.
After editing any of these lines, run `python3 .claude/hooks/wp_index.py`
to rewrite the index; a test fails while it is stale (WP-1507). The index
shows the glyph and the date only; the free text lives on this line.
Priority values: P1 · P2 · P3 · P4 — which WP the next session's tokens
should go to, rated at the write and re-rated by whichever handover
moves it. Every ⬜ WP carries one. A closing session deletes the line, so a
✅/🛑 WP carries none and its index cell reads `—`; a 🔄 WP may keep the
one it had. The index carries the tier only; the date and the one
clause of reason live on this line, and a re-rating rewrites it in place
("P1 2026-10-02 — was P2: 1442 landed, nothing blocks it").
The rubric is weighted shortest job first (SAFe: cost of delay over size),
scored on Nielsen's severity axes (how often, how badly, and whether it
persists), with the repo's own severity class on top: a wrong number that
nothing flags outranks one that raises, and one on a path few fits run
is P2.
  P1  paid by every user on every run: a silent wrong answer in a shipped
      path (a number a user quotes, wrong, nothing fired), a required check
      red on main, data loss; or the last rung of a feature whose other
      rungs shipped, the value already paid for and the remainder small.
  P2  a feature the open milestone was opened for; a scoping WP, the
      decision with a named user that other WPs wait on; a defect that
      fires wrongly (a raise or a flag) and costs a user a workaround.
  P3  a workaround covers it: a reader nobody is waiting for, a view over
      what the fit already knows, a cost-only item with no user at the
      wall, a diagnostic that is right but says less than it could.
  P4  bookkeeping: process, hygiene, wording, a rename, anything whose
      absence changes no number and no decision.
Then at most one move, and the line says which: up a rung when what remains
is small against what is already paid (a finishing rung, a WP whose last
blocker shipped); down a rung when nothing in it can start, waiting on a
decision nobody has taken or a hard dependency that has not shipped, and the
line names what lands to lift it. So closing a WP re-rates its dependants
(handover step 5), and a fold from /issue-review re-rates the WP it lands
in when the evidence moves its row.
Worked, from the 2026-09-23 backfill: 1333 is P1 (a chain of hundreds lost
to one raise, and a check that died reading as passed); 1341 is P2 (a joint
fit cannot be inspected; refining apart is the workaround); 1328 is P3
(waits on 1327's model; P2 when it lands); 1448 is P4 (provenance
bookkeeping, changes no number).
A WP file must be self-contained: a session that reads ONLY this file
(plus the auto-loaded CLAUDE.md) can start work. Link specific DESIGN.md
sections instead of restating them, but restate anything short and
load-bearing (a formula, a threshold, a fence) directly.
-->

## Goal

1–2 sentences: what exists, and works, when this WP is done.

## Context

Everything a fresh session needs and cannot get from CLAUDE.md alone:
- Source files to touch, and the seams to extend.
- Relevant invariants (link `../DESIGN.md#...` sections; restate the short ones).
- Prior measured findings that constrain the design.
- Licensing fences (what may be ported, what is concepts-only).
- The tier of each rule this WP adds ([generality § The rule](../milestones/generality.md#the-rule)):
  physics, named practice, or new judgement. For new judgement, name the dataset families
  it was measured on and the reference for each. A default or automatic action also names
  its kind of ambiguity ([DESIGN § Rules](../DESIGN.md#rules), 1). A new topic names its
  reference (dataset, published number, tolerance) before any code is written, or says
  none exists and that it ships not yet validated.

### Inherited

Facts another WP's session established that change the work here. The
session protocol forbids reading other WP files, so a note left in some other
WP's handover log is unreachable from this one — if it matters here, it has to
be restated here, with the source WP named so it can be audited.

Written by the **other** session as it signs off (protocol step 3), not by
whoever works this WP. Typical entries: a constant or helper now exported for
reuse (import it, do not redeclare); a design bullet in this file that has
since gone stale; a deliberate deferral *into* this WP; a measured gotcha
that would silently mislead the work here.

**This is a mailbox, not an archive**: every session on this WP prunes it on
arrival (fold still-true entries into Context or Tasks, delete stale ones and
say why in the handover entry), and closing the WP deletes the section —
consumed. `tests/test_docs_consistency.py` asserts no WP closed after
2026-07-31 still carries one.

## Non-goals

Explicit fences: what looks adjacent but belongs to another WP or milestone.

## Tasks

Each item ≈ one commit, independently landable, prefixed in the commit
message with the WP id (`WP-NNNN: ...`). Check off as they land.

- [ ] ...
- [ ] ...
- [ ] Tests (unit/property; acceptance if this WP carries it) + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: the routing row, reference row or body rule an agent driving rietx needs from this WP, or "none" and why (root CLAUDE.md § skill)

## Acceptance

Measurable criterion + the exact command(s) that verify it, e.g.:

```sh
.venv/bin/python -m pytest tests/test_xxx.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

Papers (author, year, journal), datasets, cross-code targets.

## Handover log

Append-only, newest first. An entry is REQUIRED before ending any session
that touched this WP.

**Two entry forms, both dated, both read by
`.claude/hooks/session_start.py`** (which is why
`tests/test_docs_consistency.py` pins them): a one-line
`- **YYYY-MM-DD** — <text>` bullet, or, once a WP takes more than one session
in a day — the normal cadence here — a `### YYYY-MM-DD [(Nth session)] —
<title>` heading with the entry below it. Nothing else counts as an entry, and
an entry the hook cannot see is a handover that did not happen.

**Every entry opens with a plain-language paragraph saying what the work
*means*** — what a reader who has not seen the diff now knows, or can do, that
they could not before — and closes by naming the next action. Between them go
the working details: *Done* / *Measured* / *In flight* / *Next* / *Gotchas*.
The lede is the part a person reads; the rest is the part a successor reads.
Write it as the answer to "so what?", never as a list of commits.

- **YYYY-MM-DD** — created.
