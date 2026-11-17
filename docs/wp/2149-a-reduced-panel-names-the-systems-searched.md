# WP-2149 — INDEX_PANEL_REDUCED names the systems the run searched

Milestone: unscheduled · Status: 🔄 2026-11-17 — all tasks landed in PR #1637; the message wording waits on Yue
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-17 — a message that names crystal systems a run never searched, beside a neighbour that says so; `systems_searched` on the result is right, so a reader who checks it has the truth

## Goal

Every indexing message that says what a run searched quotes what that run
searched. A short peak list's `INDEX_PANEL_REDUCED` no longer names systems
outside the search, and its neighbour `INDEX_SYSTEMS_NOT_COVERED` no longer
advises searching a system the list cannot support.

## Context

**The defect, reproduced at `96f721c26`.** Tutorial 03b's aragonite pattern,
cut at 45° 2θ, gives 15 usable lines. The search spec declares
`systems=("orthorhombic",)`. The result's `systems_searched` is
`["orthorhombic"]`. Its two messages disagree:

- `INDEX_PANEL_REDUCED`: "The search runs over cubic, hexagonal,
  orthorhombic, tetragonal, trigonal and the ranking panel omits: …".
- `INDEX_SYSTEMS_NOT_COVERED`: "6 crystal system(s) were not searched.",
  `where` = cubic, hexagonal, trigonal, tetragonal, monoclinic, triclinic.

The script is a copy of the tutorial's setup plus `assess_peak_list` and
`index_pattern` without `data=` (no validation fit, under a minute). Found in
PR #1570's notebook output on 2026-11-15. WP-2041's handover recorded it with
"no owner found".

**Why it happens.** The message is built in
`indexing/diagnostics.py:619-632` (`quality_diagnostics`), from
`DataQualityReport.systems_supported`. That list says which systems the line
count can over-determine: at least `MIN_LINES_PER_DOF` usable lines per metric
degree of freedom. `quality_diagnostics` runs inside `assess_peak_list`
(`indexing/quality.py:437` and `:504`), before any search exists, and
`index_pattern` copies those diagnostics into the result unchanged
(`indexing/workflow.py:971` and `:1199`). The search itself runs over
`workflow._restrict_to_supported(spec, quality)` (`workflow.py:657-684`,
called at `:891`). That function takes the caller's systems that the list
supports. Where none of the caller's systems is supported, it keeps the
caller's request.

So the sentence "The search runs over S" is wrong in three cases:

1. The caller narrowed the systems (the reproduced case). The message names
   supported systems the caller excluded.
2. The caller's systems share nothing with the supported set. The search runs
   over the caller's systems, and the message names a disjoint list.
   (Read in the code, not run.)
3. `assess_peak_list` is public (`rietx.indexing.assess_peak_list`), and a
   caller may run it with no search at all. The message then describes a
   search that never happened.

**The siblings**, every place the same claim is made from the support list
instead of the run's record:

- `indexing/diagnostics.py:921-927`, `INDEX_SYSTEMS_NOT_COVERED`. Its list
  (`SYSTEM_ORDER` minus `systems_searched`) is correct. Its suggestion,
  "Search the missing systems before you conclude anything about the
  specimen", fails for a system that `_restrict_to_supported` dropped. On
  this list monoclinic and triclinic are unsupported, so a caller asking for
  all seven gets five searched, and a re-run drops the same two again. The
  message cannot tell "not requested" from "dropped because the list cannot
  determine it". (Read in the code, not run.)
- `help.py:3101-3109`, the `INDEX_PANEL_REDUCED` help entry: "The search
  still runs over the crystal systems the line count supports." It omits "of
  those requested".
- `help.py:3220-3227`, the `INDEX_SYSTEMS_NOT_COVERED` help entry: "Search the
  missing systems before you draw a conclusion." Same gap as its message.
- `help.py:5202-5211`, the `SearchSpec.systems` field entry: "Which crystal
  systems the search covers." It does not say that a list below 20 usable
  lines narrows them.
- `docs/docs/reference/peaks.md:431`: "The search still runs, over the
  supported systems only." It should say the requested systems the list
  supports.

**Checked and correct**, so outside this WP: `INDEX_ABSTAINED`'s `where`
(`diagnostics.py:904`) quotes `systems_searched`. `INDEX_SEARCH_INCOMPLETE`
(`engines.py:2172-2224`) and `INDEX_BUDGET_EXHAUSTED` (`engines.py:2306-2311`,
built at `workflow.py:1164-1175`) quote the run's own lists. The run notes
(`workflow._spec_notes`, `:1269-1270`) quote the spec after the restriction.
`IndexingEvidence.systems_supported` (`schemas/indexing.py:2082`) is labelled
as what the list supports. The GUI's `searchCoverage`
(`gui/src/lib/peaks.ts:301`) reads `systems_searched`. The refusals at
`schemas/indexing.py:1850`, `:1861` and `:1960` list `SYSTEM_ORDER` or
`engine_names()` as the valid choices, which is their job.

**Two ways to fix the message**, for the session to choose:

- Keep it in `quality_diagnostics` and make it a statement about the list:
  "The list supports a search in S." That reads true in all three cases and
  needs no search. The run's record stays in `systems_searched` and
  `INDEX_SYSTEMS_NOT_COVERED`.
- Move the systems clause to the result-level diagnostics
  (`diagnostics.py`, beside `INDEX_SYSTEMS_NOT_COVERED`), where
  `result.systems_searched` exists. A standalone `assess_peak_list` then says
  nothing about a search.

`INDEX_SYSTEMS_NOT_COVERED` needs the dropped systems named apart from the
unrequested ones. `_restrict_to_supported` knows which it dropped. Nothing
records it today.

**Reader output goes to the maintainer.** Each change here rewrites text a
caller reads, so the wording goes to Yue before merge (ruled 2026-11-01). The
PR body quotes old and new text for each message. `python -m tests.reader_output`
diffs a Rietveld fit's printed text and does not exercise indexing, so the
quote is the evidence.

**Tier.** No new heuristic. The two codes and their `.suggestion` rows exist
in `rietx._audit` (`INDEX_PANEL_REDUCED`, `INDEX_SYSTEMS_NOT_COVERED`). A
message rewrite keeps their tier. If a code is added for the dropped systems,
it needs its row.

### Inherited

## Non-goals

- `MIN_LINES_PER_DOF`, the 20-line bar or `_restrict_to_supported`'s choice of
  systems. The search is right. Only what the messages say about it moves.
- WP-2007's tier audit of the indexing codes.

## Tasks

- [x] Rewrite `INDEX_PANEL_REDUCED`'s systems clause by one of the two routes
      above. A test covers the three cases: a narrowed request, a disjoint
      request, and `assess_peak_list` alone. Route 1 (a statement about the
      list); `tests/test_indexing_quality.py` § What the messages say was
      searched.
- [x] `INDEX_SYSTEMS_NOT_COVERED` names the systems the list could not
      support apart from those not requested, and its suggestion fits each.
      Record which systems `_restrict_to_supported` dropped where the
      diagnostic can read it. The split reads `quality.systems_supported`,
      already on the result and the authority the restriction reads, so no
      second record was added (handover entry says why).
- [x] The help entries (`help.py` 3101, 3220, 5202) and
      `reference/peaks.md:431` say the same as the new messages.
- [x] Rebuild tutorial 03b, whose saved output prints both codes, and read
      the new text in it. Tutorial 03 too, whose saved output prints
      `INDEX_SYSTEMS_NOT_COVERED`; its markdown names neither code.
- [x] Quote old and new text in the PR body for the maintainer.
- [x] Skill: none expected. `diagnostics-indexing.md`'s `INDEX_PANEL_REDUCED`
      row does not repeat the systems claim. Revisit if the dropped-systems
      split adds a code.

## Acceptance

On the reproduced case (15 lines, `systems=("orthorhombic",)`), no message
names a system outside `systems_searched` as searched, and no suggestion asks
for a search the list cannot support.

```sh
.venv/bin/python -m pytest tests/test_indexing_quality.py tests/test_indexing_consensus.py tests/test_help.py
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-2041's handover (PR #1570), where the pair was first printed.
- WP-1043, the split between "can be searched" and "can be scored".

## Handover log

- **2026-11-17** (ghostshift runner, PR #1637) — The two indexing messages
  about crystal systems now say true things. On a short peak list,
  `INDEX_PANEL_REDUCED` names the systems the list has enough lines for,
  and no longer says a search ran over them. `INDEX_SYSTEMS_NOT_COVERED` now
  separates the systems the run left out that the list could support from
  those it could not. It asks for a search only of the first kind. For the
  second it names the lines a cell needs. Nothing about the search moved,
  only the text. The wording waits on Yue.

  *Done.* Route 1 for the first task: `INDEX_PANEL_REDUCED` is a statement
  about the list ("Only cubic, hexagonal, trigonal, tetragonal, orthorhombic
  have at least 5 usable lines per metric degree of freedom, enough to
  determine a cell."), in `SYSTEM_ORDER`. It stays in `quality_diagnostics`,
  so a standalone `assess_peak_list` still says it. Route 2 would have lost
  that for no gain. `INDEX_SYSTEMS_NOT_COVERED` (`diagnostics._not_covered_text`)
  splits `missing` by `quality.systems_supported`. Its `where` is unchanged.
  On an abstained list it points at `INDEX_DATA_INSUFFICIENT` and asks for no
  search, a third member of the class the WP did not list. Help entries
  (`INDEX_PANEL_REDUCED`, `INDEX_SYSTEMS_NOT_COVERED`, `SearchSpec.systems`)
  and `reference/peaks.md` match. Tutorials 03 and 03b rebuilt, since 03's
  saved output prints the second code too. `/code-review high --fix` found
  seven items. Four were fixed (a shared `_ADD_LINES` remedy constant, a dead
  branch, a format-then-parse list, a set rebuilt per pass) and one more by
  hand (the help entry's abstained case). Declined: threading the
  undeclared-instrument advice into this suggestion (a larger change, and
  `INDEX_DATA_INSUFFICIENT` carries it where the list abstains). Declined
  with a docstring note: gating the split on the scoring bar. At 25 lines a
  budget-unreached triclinic is told it needs 30 lines, where a re-run would
  search it. The goal sentence says no suggestion asks for a search the list
  cannot support, and `systems_supported` is the package's definition of
  support.

  *Settled by Claude.* (1) Route 1 over route 2, on the smallest-change rule
  and because `assess_peak_list` is public. (2) No record of the systems
  `_restrict_to_supported` dropped, against the task's wording. The split
  reads `quality.systems_supported`, already on the result and the authority
  the restriction reads (root CLAUDE.md, one authority per fact; a second
  surface is a projection). A record would let the message say "dropped from
  your request". The message avoids "not requested" altogether, because a
  system the budget left unreached was requested and is missing too.

  *Measured.* `python -m tests.reader_output` exit 0 (it fits Rietveld only;
  the WP said so). Before and after text for the reproduced case is in the
  PR body. Fast suite and gate counts are in the PR body (venv `[dev]`,
  macOS arm64).

  *Question for Yue.* Do the new texts of `INDEX_PANEL_REDUCED` and
  `INDEX_SYSTEMS_NOT_COVERED` belong, line by line? The PR body's "What a
  reader receives" has the old and new text.

  Next: Yue's ruling on the wording. Then merge, and close the WP.

  Ruled by Yue 2026-11-17: the reworded `INDEX_PANEL_REDUCED` and
  `INDEX_SYSTEMS_NOT_COVERED` accepted (reader output).

- **2026-11-17** — created, from the 2026-11-17 issue triage round (no
  issue; the defect came from WP-2041's handover). Checked against the tree at
  `96f721c26`: case 1 reproduced with the tutorial 03b setup; cases 2 and 3
  and the `INDEX_SYSTEMS_NOT_COVERED` sibling read in the code, not run. No
  open WP owns it: WP-2007 audits the indexing codes' tiers and leaves their
  text alone, WP-2078 and WP-2147 are about ranking, and WP-2041 is closed.
  Next: choose the route for the first task, then write the tests.
