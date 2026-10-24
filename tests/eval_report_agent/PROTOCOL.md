# Runner protocol — agent-in-the-loop FitReport eval

**Protocol version: 2.3** (`build_fixtures.PROTOCOL_VERSION`; stamped into
every condition marker and quoted by every run record).  **2.3 registered
2026-10-24, before any 2.3 run** (WP-2037 Decision 3; § The 2.3 quiet-view
round — the condition is the package build, python arm only, cells launched
by `launch.py`).  **2.2 registered
2026-08-19, before any 2.2 run** (WP-1107; § The 2.2 placement round —
answer contract v3, two shim projections, and the wording revisions; every
episode fixture and decision band below stands).  **2.1 registered
2026-08-13, before any 2.1 run** (WP-1065; § The 2.1 targeted round — prompt
content only).  **2.0 registered 2026-08-13, before any 2.0 run** (WP-1064).
Bump the version on any change that alters comparability: the prompt text,
the overlay contract, the answer schema, the scoring rules, the excerpt
policy.

**2.0 (WP-1064)** is justified four ways at once — the episode set, the
answer schema, the scoring rules and the condition axis all move — so a 2.0
run is poolable with nothing earlier, **including `off`**: the v2 answer
contract is in every prompt, so even the report-less cell is not the 1.x
report-less cell.  Version history: **1.0** (WP-1053) was the 48-run pilot —
null on outcomes, with the mechanism measured (agents never generate the
states where the report speaks).  **1.1** (WP-1058/1059) delivered the
per-stage `trajectory`, split delivery from instruction on the condition
axis, and added the real pair R1/R2 — 30 runs, invalidated as a delivery
measurement by its own truth rows (§ Episode validity) but productive of
every mechanism 2.0 is registered against.

## The 2.3 quiet-view round (WP-2037) — registered 2026-10-24, before any 2.3 run

**The question.**  WP-2037 changes what `print(result)` shows when no
deliverable is declared.  Errors print in full.  Every other diagnostic
prints as one line naming the purposes it is a warning under, and the block
closes on "pass deliverable= to summary() for the rows that decide your
purpose; every row is in result.diagnostics".  The maintainer's Decision 3
(2026-10-23) lands this quiet default now, with this round as its tripwire:
a worse result reverts the quiet default and keeps the ordering.  The worry
it answers is WP-2037's own judge's: agents stopped on a criterion the
package states seven times in eight, and the quiet view no longer prints
each row's help.  The round asks whether that collapses.

**A smoke check, and named as one.**  Four cells an arm can catch a
collapse and nothing finer.  The record says eight runs cannot tell 7 of 8
from 5 of 8 (Fisher p = 0.57, `docs/milestones/generality.md` § A contested
demotion).  At four an arm the only split Fisher's test separates at
p < 0.05 is 4 of 4 against 0 of 4 (p = 0.029); 4 against 1 is p = 0.14.

### The two arms — the install is the condition

Python arm only.  Each arm is rietx built **non-editable** from a commit
archive into its own venv outside the repo
(`uv venv --python cpython-3.12-macos-aarch64-none`; CPython 3.12.10,
arm64, the compiled tier available in both).  Both builds report
`1.10.0.dev0`, so the version string does not name the arm.

- **`a` — before**: `664c8b8bb`, main's first parent of PR #1142's merge.
  `print(result)` prints every diagnostic with its `help:` line under a
  "N unresolved" header.
- **`b` — after**: `4bfde33d7` on `wp2037-attention-part2` (#1142 plus
  part 2's first five commits).  The quiet view above, and
  `summary(deliverable=…)` prints that purpose's rows in full.

*Why not `5d64a86`*, the commit the commissioning session named as "main
just before #1142": it is where WP-2037's part-1 branch forked.  Main then
took 28 more commits before #1142 merged onto `664c8b8bb`, among them
WP-2039's rewrite of the text views (`_display.py` +231 lines,
`schemas/results.py`).  Against `5d64a86` the print would differ by WP-2039
as well as by WP-2037.  `664c8b8bb..99b00b82e` is exactly #1142.

**What differs that an agent reads**, measured at build:

- *The print.*  At each episode's default-plan landing state the two builds
  give the same status, Rwp and diagnostics: N1 Rwp 0.10080 with 2 rows, C1
  0.09169 with 4, W1 0.14010 with 1, W2 0.23899 with 4, all converged.  No
  episode lands with an error-level row, so at a default landing the after
  view prints no row in full.  The report block of `ref.summary()` is
  identical in both: the identifiability clause with its ≥ 10 % band, the
  regions, the `next:` line.  Only the diagnostics block differs.
- *The skill.*  Each workspace carries its own build's `docs/skill/rietx`,
  since the skill ships in the wheel beside the code it describes
  (`python_arm.write_workspaces(skill_src=)`, new in 2.3).  SKILL.md §4
  opens "`print(result)` shows per-stage status, the diagnostics …  Act on
  each `d.suggestion`" in `a` and "Declare your purpose with
  `ref.summary(deliverable=…)`; act on each warning it prints in full" in
  `b`.  `b`'s §4b table gains Cell, Calibration and Magnetic rows, and five
  sentences are cut (the Le Bail stop note, rule 6's `lab_calibrate`
  clause, the `resolution_limited` sentence, §6's abstention link, the
  provenance parenthetical).  `references/api.md`'s two `summary()`
  signatures gain `levels=`; `batch.md` 9c.18 names
  `rx.diagnostics_summary`; `references/api-batch.md` is new.
- *Nothing else.*  `episode.json` and the truth records are byte-identical
  across arms.  `prompt.md` differs in one character, the venv directory's
  letter.  Workspaces are `~/rietx-agent-rounds/r-2026-10-24/{a,b}/RUNS/
  python__sonnet/<eid>`, so a path names the arm by letter only.  The truth
  tree waits in a scratch directory away from every workspace until
  scoring.

### Launch — `launch.py`, new in 2.3

Earlier rounds ran cells as Workflow `agent()` calls, which inherit the
launching session's user-level skills; this machine has a user-level
`rietx` skill.  2.3 runs each cell as

    claude -p "<RUNNER>" --model sonnet --effort medium --session-id <uuid>
        --permission-mode bypassPermissions --setting-sources project,local
        --output-format stream-json --verbose --max-budget-usd 15

in its workspace, under a rebuilt environment (`HOME`, `USER`, `LOGNAME`,
`SHELL`, `LANG`, `PATH`; an inherited `OLDPWD` would name the checkout).
`RUNNER` is `launch.RUNNER`, identical in every cell but the path: "Your
working directory is {workspace}. Read prompt.md there and carry out the
episode it describes. Work only inside that directory: read nothing outside
it."  The $15 is a runaway guard; a cell that hits it is invalid.  A
one-word Haiku call through the launcher, in an empty scratch directory with
no fit (6 s, $0.002 at list price), checked the route before registration:
`apiKeySource` none (the subscription), and an init event listing no
user-level skill.

**The matrix**: {a, b} × {N1, C1, W1, W2} × sonnet, N = 1, effort `medium`.
**Eight cells, approved by the maintainer 2026-10-24**; any rerun or extra
cell needs a new approval.  Two waves of four, each wave holding both arms
of two episodes so a pair runs under the same machine load: N1 and C1, then
W1 and W2.  Expected answers unchanged from their 2.0 registrations: N1
`ambiguous` + {extend_range_or_calibrate}; C1 `converged` +
displacement within {abs: 0.005} of −0.0790 + {none}; W1
`impurity_suspected` + {add_phase}; W2 `assumption_wrong` +
{fix_instrument_model}.  Re-measured 2026-10-24 on main `6fe7a5bbb`
(`[dev]` venv, darwin/arm64): `test_landing_states.py`'s six N1/C1/W1/W2
rows pass in 19.5 s; N1's rivals tie at χ² 4.0929 against 4.0618 (ratio
1.0077, band [0.99, 1.01]); C1's decide at 4.1049 against 3.5463 (1.1575 ≥
1.10), the swap recovering displacement −0.0790; W1's CaF₂ moves χ² 28.22 →
12.41 (2.2744); W2's doublet moves it 7.122 → 2.670 (2.6676) and empties
the Kα2 positions, 30 unmatched → 0.

### Read-outs, fixed in advance

- **(1) The stopping criterion the agent states** — the R11 taxonomy of
  `tests/eval_agent_surface/PROTOCOL.md`, the read-out behind the v1.3
  figure.  It is read from the **closing text**: the last assistant message
  plus `answer.json`'s `summary` and `caveats`.  The closing text falls in
  exactly one of six classes: *a criterion the package states* / *an
  agreement index alone* / *an external comparison* / *a script exiting* /
  *an instruction* / *none* (ended waiting).  The first class means the
  closing text gives, as a reason the verdict holds or the work stops,
  something the package printed or ships: a diagnostic code or its
  message, a report statement (the identifiability clause or its ≥ 10 %
  band, an exchange row, unmatched peaks, a suggested action), a skill row
  (§4b, §10, a numbered rule), or a field's verdict (`exchangeable`,
  `separable`, `at_bound`).  Rwp or GoF alone is the second class, and so
  is the solver's `converged` beside them; a certificate or literature
  value is the third.  A closing text giving several reasons takes the
  first class if any reason is in it.  **Classified blind to arm**: a fresh Sonnet
  subagent gets the eight closing texts under shuffled ids, with arm letters
  and venv paths removed, and this rubric verbatim.  Its class is the
  read-out; my own reading is reported beside it wherever the two differ.
- **(2) The verdict grade** — `scorer.py`'s `passed` (verdict ∧ tolerance
  where registered ∧ next_action ∈ the set), with `overclaimed` and
  `underclaimed` beside it.
- **(3) Mined from each transcript**, over the agent's own tool inputs (the
  *probed* surface): (i) it passed `deliverable=` to any call; (ii) it
  called `summary(deliverable=…)`; (iii) it read `result.diagnostics`
  (`.diagnostics` in its code); and (iv) which view came back in a tool
  result: `b`'s closing sentence, or `a`'s "unresolved" header.  (iv) is
  descriptive.  An agent that never prints a result never sees either view,
  and that is part of what the arm measures.

**The baseline beside them**: v1.3's round 1.1 (WP-1307, 2026-08-29), where
seven of eight runs stopped on a §4b deliverable row and none of the 86-run
campaign's did (`docs/milestones/generality.md` near its lines 262-275 and
545; `docs/milestones/v1.3.md`).  It is another harness, other episodes (an
in-situ ramp, a four-phase reel), other models (sonnet, opus-5) and a
narrower criterion (a §4b row), so it gives the scale the rates are read
against and is never the control.  The control is arm `a`.

### "Worse", as a number

Over the valid episode pairs, **arm `b` is worse if its count on (1)
stated-criterion stops, or on (2) passes, is at least 2 below arm `a`'s.**
A difference of 1 reverts nothing.  The rates behind the choice, binomial
with four cells an arm: if both arms share a true stop rate of 7/8 the stop
read-out fires by chance with probability 0.05, and at 5/8 or 1/2 with
0.14; a collapse from 7/8 to 1/8 fires it with probability 0.93, and a drop
from 7/8 to 5/8 only 0.33, which is the finer difference this round cannot
see.  Two read-outs each able to fire make the round's chance false alarm
up to about one in four at mid rates; that is the price of catching a
collapse at N = 4, and a reverted default is cheap to restore on a second
measurement.  Fewer than three valid pairs make the round inconclusive:
recorded as such, nothing reverts, and a rerun is the maintainer's call.

### Audit, and what invalidates a cell

- **The condition reached the cell**, checked per transcript: the init
  event lists no user-level skill; every python process that imports rietx
  runs the arm's own venv; no Skill call loads a `rietx` skill.  A failure
  invalidates the cell.
- **Forbidden reads**, as § The python-capable arm: any path outside the
  workspace and the arm's own venv (the other arm's venv or workspaces, the
  repo, the truth tree, the round's record), and the network.  A violation
  invalidates the cell.
- **The cap**: a ninth fit-bearing script run invalidates the cell, counted
  by hand from the Bash calls with `usage_row.fit_bearing_runs` as the
  pointer.
- A cell that ends without `answer.json`, or on the budget guard, scores
  failed on (2) and is classified on (1) like any other.
- No mid-round change.  A defect found mid-round is recorded post-hoc and
  fixed for a successor.

**Recorded per cell**: model ID as the init event reports it, wall seconds,
turns, and tokens (input, output, cache read, cache write) with the
list-price cost off the `result` event.  The record (streams, transcripts,
scorecards, mined rows) lives outside the repo at
`~/rietx-agent-rounds/r-2026-10-24-record/{a,b}/`.  The result is reported
to WP-2037's session, which records it in its WP.

### After the run, recorded post-hoc (2026-10-24)

All eight cells ran on `claude-sonnet-5-5`, registration `5d8796917` first.
**Outcome**: (1) stated-criterion stops, `a` 4 of 4 and `b` 4 of 4, the
blind classifier and my reading agreeing on every cell (a/W1 and b/W2 at
medium confidence, each giving the unmatched-peak list or a code beside an
Rwp drop); (2) passes, `a` 3 of 4 and `b` 4 of 4.  Neither read-out falls
by 2, so the registered "worse" is not met.  a/N1 failed by overclaiming
`converged` on the tie: its zero-against-displacement test held both at
zero (the plan overrode its holds, `HOLD_BLOCKED_PLAN`), and it then applied
the 1.10 band to zero shift against sample transparency (1.145) with the
certified cell held.  Eight cells spent 4.56 M tokens, 4.14 M of them cache
reads, $2.25 at list price.  The per-cell table is the record's
`cells.json`; WP-2037 holds the reading.

Defects found during the run.  None touched what a cell saw:

- **A session can end twice.**  `claude -p` wakes the agent when a
  background task it started ends after its answer.  b/N1 and b/W2 each took
  one more turn to acknowledge a killed command, outputs written before the
  wake and unchanged.  Tokens are summed over both `result` events, and the
  closing text holds both final messages.
- **The session transcript repeats rows.**  Claude Code 2.1.310 writes
  `api-request-blob` rows repeating each assistant message as sent, so the
  miner counted those tool calls twice (a/C1: 21 for 11).  The record keeps
  the raw file as `launches/<eid>/session.jsonl` and mines a copy without
  them; `launch.py` now writes both.
- **`launch.json`'s wall clock was wrong** for a cell collected after a
  slower one.  The `result` events' `duration_ms` is the figure quoted, and
  `launch.py` no longer writes the field.
- **Every cell opened with `cat > /tmp/x`**, an empty file outside the
  workspace, which stalled on stdin until it was backgrounded at 120 s.
  b/W1 also wrote its first inspection script to `/tmp/x.py` and ran it; the
  script reads only the workspace's `episode.json`.  By the rule's purpose
  (no information from outside the workspace) all eight cells are valid.  By
  its letter b/W1 is not, the W1 pair drops, and the three pairs left give
  stops 3 against 3 and passes 2 against 3: the same answer.
- **The maintainer's user-level CLAUDE.md reaches a cell** under
  `--setting-sources project,local` (WP-1504's amendment; not re-measured
  here), constant across arms.  The closing prose reads in its style.  Whether it also
  prompted the `/tmp` file is not measured.  A successor wanting it out
  needs a separate configuration directory.
- Thinking text in the transcripts is 0-408 characters a cell, so `voiced`
  is a floor.

## The 2.1 targeted round (WP-1065) — registered 2026-08-13, before any 2.1 run

One question, one guard, twelve cells.  Round 3 measured C1 — the solvable
control whose rivals are decisive (χ² ratio 1.1679) — at **0/7 valid**, and
the mined decomposition localised the defect to sentences rather than to the
round: the three C1 sonnet cells ran the swap and recovered the displacement
to −0.080, and still `report__sonnet` declined (`ambiguous` +
`extend_range_or_calibrate`), `off__sonnet` misfiled the recovery
(`assumption_wrong`, invited by "the geometry" in the glossary), and
`python__sonnet` hedged a solved fit (`converged` + `report_with_caveat` ∉
{none}).  Nothing in the clause or the manual said what winning the
comparison licenses.  2.1 changes prompt content only, in two places:

- **The glossary fix** (`VERDICT_MEANINGS["assumption_wrong"]`): names only
  non-refinable declarations (the source's emission lines, the geometry
  *type*, the radiation) and adds the explicit exclusion — a refinable
  parameter at a wrong starting value is never `assumption_wrong`; converge
  it or say the data cannot.  The defect was recorded post-hoc in round 3
  (scoring untouched); fixed here per the standing discipline.
- **The package under test carries the license sentence**
  (`THRESHOLDS_VERSION` 0.9, WP-1065): the exchange clause now states what a
  decisive swap outcome licenses (the winning rival's fit is the answer,
  quoted without caveat, at ≥ `RIVAL_DECISIVE_MIN_CHI2_RATIO` = 1.10) and
  what a tie licenses (protocol, or the declared stand-off).  The python
  arm's manual copy carries the matching §4 step 6 / §4b / §9 updates.

Episode fixtures are **unchanged** — the package content changes, not the
landing states, so the slow landing-state tests keep their bands; python
workspaces rebuild (fresh wheel, 2.1 prompt and manual copy).  Scorer v2
unchanged, asserted before the run.  Prompts changed, so a 2.1 cell pools
with nothing at 2.0.

**The matrix**: {off, report, python} × {C1, N1} × {sonnet, haiku}, N=1,
effort `medium`, expected answers unchanged from the 2.0 registration (C1:
`converged` + tol {abs: 0.005} + {none}; N1: `ambiguous` +
{extend_range_or_calibrate}).  The conditions decompose the fix: `off`
receives neither report nor manual, so it isolates the glossary fix (its 2.1
prompt is the only thing that changed for it); `report` adds the clause with
the license sentence; `python` adds the pulls (its manual carries the
§4b/§9 updates).  **N1 is the guard**: its swap ties (1.0075) and its
expected answer is the decline — a license sentence that converts a genuine
tie into a confident answer is worse than no sentence, and N1 is the
real-data row that would show it.

**Pre-registered read-outs**:

- **(a)** C1 produces valid passes where round 3 had 0/7 — specifically the
  swap-running cells (`report__sonnet`, `python__sonnet`) flip to
  `converged` + `none`, and `off__sonnet` stops answering
  `assumption_wrong` (the glossary fix in isolation).
- **(b)** N1 does not degrade: the round-3 JSON passes (`off__sonnet`,
  `report__sonnet`) stay passes, and no arm that received the sentence newly
  overclaims `converged` on the tie.  A new N1 overclaim means the wording
  overcorrects — revise before any wider claim, and add the E8′ cells (the
  synthetic exact tie) to the revision's guard set.
- **(c)** The both-free overlay counts (round 3: N1 4 cells, C1 2) do not
  grow.

A null on (a) is a finding too: it says the 0/7 was not the sentence, and
the follow-through question moves from wording to delivery — recorded, not
re-run.

**Budget** from round 3's measured figure (1.833 M tokens / 28 cells):
~0.8 M.  Audits per the round-3 pattern: payload enforcement, forbidden
reads, the 8-fit-run cap (which invalidated `python__haiku` C1 at 16 last
round).  Counts, never percentages; dated grid, no CI; the record to
`eval-runs/` per its README contract.

## The 2.2 placement round (WP-1107) — registered 2026-08-19, before any 2.2 run

Three questions the prior rounds recorded and left unowned, one round.
Episode fixtures are **unchanged**; the landing states were re-measured on
the WP-1107 tree 2026-08-19 against `report_thresholds_version` 1.2
(`test_landing_states.py`, 9 passed, `[dev]` venv, darwin/arm64,
`-n 4 --dist loadgroup`) — every 2.0 band holds, no pin moved.  Scorer
grading identity unchanged (verdict ∧ tolerance ∧ next_action ∈ set);
what changes is registered here, before any run.

### The contract amendment — answer contract v3, every arm

The WP-1107 archaeology (the WP file § The `report_with_caveat` migration
carries the numbers) decomposed 2.1's 7-of-10 `report_with_caveat` epidemic:
two cells failed *only* on the token, five failed on verdict or tolerance
regardless, and the one cell that read the license and won a decisive swap
still hedged — on a different, true, non-rival caveat.  The token is the one
delivery-stance member of an otherwise remedial vocabulary, always available
and always honest on real data, so it is an unfalsifiable hedge sink.  The
amendment splits the axes structurally:

- **`next_action` loses `report_with_caveat`** (six tokens remain); grading
  by membership is unchanged.  Rejected alternatives, each with its reason
  in the WP file: admitting the token into more sets (the sets stop
  discriminating), re-glossing it (wording against wording).
- **`caveats` joins the answer** — a list of short free-text statements of
  the limitations the agent would attach to the delivered result.  Unscored,
  optional (absent reads as empty), mined descriptively — never graded, and
  mining reads `delivered`/`probed`, never word-matches it (the round-2
  rule).
- **`none` re-glossed**: "no further remedial action is needed (a limitation
  you would attach to the delivered result goes in `caveats`)."
- **J2 re-registered** (second tier): `converged` + {none}; the µR fence
  naming is mined from `caveats`/summary — equal rigor, since token
  membership never graded caveat *content*.
- **Two wording revisions**, frozen for the round: the `assumption_wrong`
  exclusion's ending becomes "…a **refinable parameter at a wrong starting
  value** — a zero, a displacement — is never this: that is `converged` when
  the data chooses its value, and `ambiguous` when this data cannot" (the
  2.1 imperative "converge it, or say the data cannot" is the N=1 suspect
  for all four `off` verdicts flipping to `converged`, including the round-3
  N1 pass; the revision names both target verdicts with equal weight).  And
  `fix_instrument_model`'s parenthetical becomes "(emission lines, the
  geometry *type*)" — the refinable-geometry trap wording WP-1065 observed
  post-run and deliberately left for a successor.

Per WP-1065's pre-commitment ("any wording revision adds the E8′ cells"),
**E8′ joins the core guard set** for this round.

### The placement arms — projections of one response

The license sentence reached agent context in 2 of 12 cells in 2.1: agents
pipe the JSON response to a file and grep the statistics back, and the
summary string is what the greps drop.  The arms move *where* the same
sentence sits; the shim constructs them, the package does not change.  The
condition marker gains `license_placement: "summary" | "statistics"`
(JSON arms; inert when the report is withheld or the clause does not fire).

- **`report`** (status quo): the clause where it lives today, appended to
  `report.summary`.
- **`report_stat`**: the shim re-renders the identifiability clause from the
  *delivered* `report.identifiability` with the package's own renderer
  (`rietx.report.identifiability_clause` — one authority for the sentence),
  excises that exact appended substring (`"; " + clause`; `"\n" + clause`
  since WP-1985 made the summary one sentence a line, 2026-10-16) from
  `report.summary`, and injects it as `result.statistics
  ["identifiability_clause"]` — inside the block the miners proved agents
  grep.  The moved unit is the whole identifiability clause (the soft-mode
  sentence rides with the exchange sentence when both fire; same text in
  both arms, so placement stays the only variable).  A render/excise
  mismatch fails the call and invalidates the cell — never a silent
  fallback.  Key absent when the clause does not fire.
- **`python`**: no construction.  The license already reaches a python agent
  through the manual §4b and any pulled report, and 2.1 measured that route
  working (`python__sonnet` C1 quoted the band and applied it).  The arm is
  the certainly-reading comparator.  The *RivalComparison-field* placement
  is deliberately **not run**: it needs the additive package field the
  non-goal forbids before the grid — if this grid shows the python route
  deciding where JSON arms fail, that field is the successor's candidate,
  filed, never shipped on plausibility.

**Shipped 2026-08-19 (WP-1108, after the round).**  The grid favoured the
statistics placement and the package now delivers
`result.statistics.identifiability_clause` itself (`build_report` writes the
summary's clause there in the same build; `report_thresholds_version` 1.3).
Two consequences for reading this section historically: on a real response
the `"statistics"` projection's injection is a checked no-op (a shipped
field disagreeing with the re-render fails the call) and only the excision
still constructs the round's *moved* shape; and a `"summary"` marker no
longer reproduces 1.2's field-free arm — a future round wanting one must
add a strip projection.

### The `execution` pair (WP-1106's field, measured)

The condition marker gains `include_execution: true | false` (JSON arms;
meaningful only with the report delivered).  **`report_noexec`**: the shim
pops `execution` from every `report.suggested_actions[*]` in the response;
`report` delivers it as 1.2 ships it.  **W2 is the row**: its landing report
serves `add_impurity_phase` at 0.9 with `execution="advice"` where following
the advice is the *wrong* verdict — the WP-1053 shape (an advice action
quoted verbatim as grounds).  W1's identical action is the *right* answer,
so a W1 pair could not separate reading the field from taking the trap
correctly.  haiku is the signal cell (round 3 baseline: took the trap in
`off` and `report` alike); sonnet is the guard (round 3: passed — the
"advice" label must not invite dismissing the report).

### The matrix

N=1 per cell, effort `medium`, model IDs as the harness reports them:

| block | cells | n |
|---|---|---|
| placement | {off, report, report_stat} × {C1, N1} × {sonnet, haiku} | 12 |
| python comparator | python × {C1, N1} × sonnet | 2 |
| execution pair | {report, report_noexec} × W2 × {sonnet, haiku} | 4 |
| wording guard | {off, report} × E8′ × {sonnet, haiku} | 4 |

**22 cells: 20 JSON + 2 python.**  `python__haiku` is dropped, recorded:
invalidated in both prior rounds at the same defect (16 fit-bearing runs
against the 8 cap; 2.1's runner-instruction fix did not save it) — not
re-bought at N=1.  `off` runs C1/N1 because it isolates the prompt-only
changes (the imperative revision + contract v3), exactly as 2.1's `off`
isolated the glossary fix — it is the migration replication.  Expected
answers unchanged from their 2.0 registrations (C1 `converged` + tol
{abs: 0.005} + {none}; N1 `ambiguous` + {extend_range_or_calibrate}; W2
`assumption_wrong` + {fix_instrument_model}; E8′ `ambiguous`, no
next_action registered, no tolerance).

**Budget** from the measured figures (~56 k per JSON run, ~100–150 k per
python run): ~1.4 M ceiling.

### Pre-registered read-outs

- **(a) Placement**: *in-context* is a mined fact — the license anchor (the
  literal "the data has chosen", or the rendered "≥ 10 %" beside the pair)
  appearing in a tool result or assistant text of the transcript, never
  word-matching `answer.json`.  `report_stat` is favored iff its in-context
  count strictly exceeds `report`'s over the same eight cells **and** it
  adds no N1/E8′ overclaim `report` lacks.  Only then does the statistics
  placement ship, afterward, as its own additive change.  C1 pass counts
  ride beside as the decision-quality read.
- **(b) Migration**: under the amended contract, N1 `off`/`report` verdicts
  against 2.1's (both `off` cells overclaimed `converged`): `ambiguous`
  returning reads as the imperative revision acting; `converged` persisting
  is a real decision pattern, recorded.  C1 `off` staying `converged` is the
  non-regression half — the 2.1 glossary win must survive the revision.
  Caveats usage is counted (which cells wrote any; what they name).
- **(c) Guard**: any E8′ `converged`, or an N1 overclaim in an arm whose 2.1
  counterpart declined, means the revised wording overcorrects — recorded
  post-hoc for a successor, no mid-round change, wording iteration stops
  for the round.
- **(d) Execution**: on W2, haiku `report` vs `report_noexec` — the on-arm
  resisting the trap (`assumption_wrong`) where the off-arm repeats it is
  the field acting; sonnet must hold its round-3 pass under both.  Mined:
  whether any transcript voices `execution`/`advice`.
- **(e) Second tier**: J2 (re-registered above) runs as {report} × {sonnet,
  haiku} only if at least one valid core cell writes a non-empty `caveats`
  — a dead channel makes J2 undecidable through it.  E7 and J1P/J1S do not
  run: no prior effect names them (the standing rule), recorded.

### Audit, extended

The 2.1 audit stands (payload enforcement, forbidden reads, the 8-cap,
usage mining), plus:

- **Payload**: the delivered shape must match the marker both ways —
  `license_placement="statistics"` iff the clause sits in
  `result.statistics` and not in `report.summary`;
  `include_execution=false` iff no delivered action carries `execution`.
  Mismatch invalidates the cell (`!`), never explained.
- **The swap state is mined** (the 2.1 licensed-but-wrong route:
  `python__sonnet` N1 measured a decisive 1.277 for the wrong rival on a
  cell-held state): for every swap-shaped stage or `compare_rivals` call,
  whether the cell parameter was free or held.
- The runner instruction names the workspace only — the repo root appears
  nowhere (the 2.1 invalidation's invitation).

One authority per fact: the prompt *text* lives in `build_fixtures._PROMPT`
(rendered by `render_prompt`), the conditions in `build_fixtures.CONDITIONS`,
the JSON-arm enforcement in `run_refine.py`, the python-arm workspace in
`python_arm.py`, the grading in `scorer.py`, the tables in `grid.py`, the
transcript mining in `mine_transcripts.py`.  This file is the protocol
*around* them: what runs, under which conditions, and how the outcome grid
must be read.

## The question

Round 3 asks the questions the package's design thesis is actually about,
with expected answers that are **measured before registration** and are the
epistemic outcomes the package exists for:

1. **Do agents reach the right epistemic outcome** — "needs more
   information", "an assumption is wrong", "a good refinement is impossible
   but a janky one still informs" — and does delivery of the report change
   that?  Rounds 1–2 could not answer this because their outcome measure
   (parameter recovery on mostly-solvable planted rows) was structurally
   unable to credit those outcomes: two round-2 E2 cells recovered the
   planted truth *and* answered `ambiguous`, and scored fail.
2. **Report vs tools vs package-sufficient**: given the whole python surface
   and the manual, does an agent *pull* what push-delivery was built to hand
   over — and do its wins route through the report at all?  Answered
   empirically by the python-capable arm plus usage mining, not by argument.

## What two rounds established

The record this design builds on; the deep records are the WP-1053/WP-1059
handovers, `docs/milestones/v1.0.md` § Appendix, and `eval-runs/`.

- **Round 1** (48 runs): null on outcomes, measured mechanism — agents never
  generate the states where the report speaks.
- **Round 2** (30 runs, 2026-08-13): `ambiguous` becomes *sayable* only with
  a report (8/16 report-bearing position cells vs 0/4 in `off`); the
  trajectory arms did worse than report-only (0/6 vs 2/6) at ~2× the calls
  (median 2.0 `off` → 4.5 `both`; 23/24 budget exhaustions were haiku in
  trajectory arms); the §9 *instruction* produced zero bootstrap calls.
- **Round-2 transcripts, mined** (WP-1063; `mine_transcripts.py`, three
  surfaces — *probed*: the agent's own query names a field; *delivered*: it
  came back in a tool result; *voiced*: the agent's prose or `answer.json`
  names it):
  - The trajectory **was read**: rung content entered context in 11 of the
    12 trajectory-bearing cells, 8 probed `.trajectory` by name.  Trajectory
    questions are content questions, not cost questions.
  - **Layer 2 never arrived at a converged state**: cells receiving any
    `ActionKind` — `off` 0/6, `report` 1/6, `prompt` 1/6, `surface` 5/6,
    `both` 6/6; the converged report's action list was empty on all three
    episodes, so the suggestions lived only in the rungs.  A Layer-2 verdict
    needs an episode whose **converged** report carries actions.
  - Word-matching answers lies: three cells voiced `exchangeable` with the
    clause never delivered, one of them in `off`.  Mining reads
    `delivered`/`probed`, never the summary text.
  - The round-2 `impurity_suspected` answer on R1 `surface`/haiku was
    produced by **Layer 0's `unmatched_obs`** (32 entries) at a state whose
    `suggested_actions_count` was 0 — the trap is the unmatched list, not a
    rung's `add_impurity_phase` invitation.  W2 is registered against that.
- **The ridge count** (WP-1063's motivating measurement): 7 of 20 position
  cells answered the 0.7 exchange clause by freeing **both** rivals onto the
  degenerate ridge (E2 displacement +0.014 against truth 0.000; R1
  −0.120/−0.128 against −0.0801); every cell that reached truth got there by
  *swapping* which parameter was free.  The **0.8 clause**
  (`THRESHOLDS_VERSION = "0.8"`) makes the fit-level claim and names the
  swap experiment ("fit each of the pair alone with the other held at its
  null and compare χ²"); `compare_rivals()` is its on-demand form.  That
  wording is what this round measures and is **frozen for the round** — a
  mid-round content change is forbidden (WP-1064 depends on WP-1063 for
  exactly this).

## Episode validity — the rule, and the 1.1 defects it comes from

**An eval's expected answer is a measurement, not a definition**
(`tests/CLAUDE.md`).  Round 2's two invalid rows were measured *after* its
grid and recorded post-hoc rather than re-scored — changing a truth record on
sight of the results is the thing pre-registration exists to prevent.  Both
are resolved in 2.0 by redesign and re-registration, never by re-scoring:

- **E8 could not be passed as written**: the default plan frees the planted
  zero and converges to truth, and *that* state is correctly quiet — its
  expected `ambiguous` graded a state no competent agent lands on (all ten
  round-2 E8 cells answered `converged`).  Retired, record kept; **E8′**
  plants *displacement* — which no default stage frees — on the same window.
- **R1's expected `ambiguous` was refuted by the rival measurement**: each
  position parameter freed alone with the other held at its null gives
  zero-only χ² 4.0752 against disp-only 3.4890 on 5332 points, and the
  zero-only model biases *a* by +100 ppm.  The R² 0.9977 saying otherwise is
  geometric.  Retired, record kept; **C1** registers `converged` with the
  tolerance restored, and **N1** moves the genuine inability to a window
  that measurably cannot tell.
- **A synthetic episode cannot answer the rival question at all** — E2 and
  E8 planted their aberration in the *starting model*, never in the data
  (`_truth()` has zero = disp = 0), so their one-parameter rivals tie
  exactly (χ² ratio 1.0000 on both, measured).  Carried forward: E8′ can
  only ever answer "tie", which is exactly its job; the rival question
  belongs to real rows.

**The ordering rule for 2.0: measure → register → run.**  Every expected
answer is verified by a measurement at fixture build, landed as a slow test
pinning the landing state (`tests/eval_report_agent/test_landing_states.py`).
Where a measurement refuses the intended design, the fixture is redesigned
and this file re-registered (re-dated) until the measurement supports the
row — before the round, never after.  **No mid-round content or protocol
change**: defects found mid-round are recorded post-hoc (the round-2
discipline) and fixed for a successor.

## Decision bands

Registered once, quoted per row:

- **Tie**: rival χ² ratio within **[0.99, 1.01]**.
- **Decisive**: the correct model's χ² lower by **≥ 10 %** (ratio ≥ 1.10) at
  matched window and weights.  Not tuned to pass anything unmeasured: C1's
  already-measured ratio is 1.168.
- **Vanishing** (W2's set criterion): the wrong-assumption landing state's
  `unmatched_obs` contains entries at the Kα2 positions; the corrected
  model's `unmatched_obs` contains **none** of those positions — an
  emptiness criterion, no magic count.

## Episodes 2.0

Every row: data, design, expected `verdict` (+ registered `next_action` set
and tolerance where registered), and the verifying measurement its landing
test pins.  `[core]` rows run in the core matrix; `[registered]` rows are
built, measured and pinned now, run only as extensions (§ The matrix).

- **N1 — needs more information** `[core]`.  Real SRM 660c **truncated to
  20.3–56° in `episode.json` itself** (nothing to widen into; the overlay's
  `two_theta_limits` can only narrow), displacement knocked −0.0801 → −0.02.
  Expected: `ambiguous`, next_action **{extend_range_or_calibrate}**, no
  tolerance (the planted value is recorded, never graded).
  *Verifying measurement*: the two rivals, each freed alone with the other
  held at its null, tie within **[0.99, 1.01]** on this window; and no
  reachable state is correctly quiet — the exchange clause fires at the
  default-plan landing state and at both single-rival states.  The
  aberration is in the *data* (the specimen is genuinely displaced), so E8's
  failure mode — a default stage freeing the plant and landing quiet —
  cannot recur.  The upper window edge is the fixture's to tune at build
  until the tie measurement holds; the band is the registration.
  `collect_better_data` is deliberately **not** in the set: the counting
  statistics are fine; the window is what is missing.
- **E8′ — synthetic ambiguous** (replaces E8; fixture id `E8p`)
  `[registered]`.  LaB₆
  `_truth(lo=20, hi=56, seed=23)`; plant **displacement** −0.02 in the start
  — E2's shape on E8's window; no default stage frees displacement (1059's
  own prescription).  Expected: `ambiguous`, no next_action registered, no
  tolerance.  *Verifying measurement*: rival tie exact by construction
  (χ² ratio 1.0000, already measured — a synthetic row can pose the rival
  question but can only ever answer "tie"); the wrong-family state's clause
  firing is pinned in `test_fitreport_layers.py` (the E8-short block).
- **C1 — declining is wrong** (R1's successor) `[core]`.  Real SRM 660c,
  full window, displacement knocked to −0.02.  Expected: `converged` **with
  the tolerance restored** — `instrument.geometry.sample_displacement` at
  truth (the baseline's fitted −0.0801) within **{abs: 0.005}** — and
  next_action **{none}**.  *Verifying measurement*: the 1059 rival numbers
  (disp-only χ² 3.4890 against zero-only 4.0752, decisive at ≥ 1.10;
  zero-only biases *a* +100 ppm), re-measured at build; and the tolerance
  discriminates the three landing states — the swap (−0.0801) passes, the
  ridge (disp ≈ −0.120) fails, the zero-absorber state (disp never freed,
  zero +0.0317 at 63σ) fails.  Verdict-only scoring would recreate the
  round-2 tension in mirror — a zero-absorbed `converged` would pass — so
  the tolerance is what makes the row honest.  The direct test of the 0.8
  clause: its registered reading is the swap, not the ridge.
- **W1 — wrong assumption: phase list** `[core]`.  `tests/data/11BM_NAC.fxye`
  (59.5k channels — a multi-MB `episode.json` and ~1.5 s fits; the fixture
  docstring says so), model = NAC only; the CaF₂ impurity is real and
  unmodelled.  Expected: `impurity_suspected`, next_action **{add_phase}**,
  no planted parameter.  *Verifying measurements*: with/without-CaF₂ fits
  differ decisively (≥ 1.10); the NAC-only landing state carries strong
  `unmatched_obs` at the CaF₂ line positions; **and the converged report
  carries a non-empty action list** — the Layer-2 decidability precondition
  (round 2's converged reports were all empty; if no core episode clears
  this, the Layer-2 kill row is recorded undecidable-by-design *before* the
  round).  The one row with a real climbing-confidence trajectory signal
  (0.3 → 0.6 → 0.9, WP-1058): **the `report_trajectory` default is decided
  here or nowhere.**
- **W2 — wrong assumption: instrument** `[core]`.  One single-phase
  `qarr/*.prn` (Cu Kα doublet in the data; candidate `corundum.prn`, final
  choice pinned at build), with the source **declared single-line** in the
  episode.  The Kα2 satellites read impurity-shaped; the correct reading is
  the instrument model.  Expected: `assumption_wrong`, next_action
  **{fix_instrument_model}**.  *Verifying measurements*: refitting with the
  doublet declared is decisive (≥ 1.10) **and** the Kα2 `unmatched_obs`
  vanish (the Vanishing criterion) — the discriminator against
  `impurity_suspected`, because an impurity's peaks survive a source fix.
  The designed trap is **Layer 0's unmatched list** (registered per the
  round-2 mining, which re-attributed the phantom-impurity answer to it).
  Note the arm asymmetry, by design: JSON arms cannot edit the instrument
  (the overlay admits `plan`/`mode`/`two_theta_limits` only) and must
  *reason* to the answer from the satellites' shape — systematically
  high-angle-side, spacing growing with tan θ; the python arm can run the
  experiment.  Part of what hypothesis (c) measures.
- **J1 — impossible but janky** `[registered]`, two sub-rows.  The WP-1057
  LaB₆ pore proxy (guest scatterer in the data only), one episode core, the
  **deliverable declared per sub-row** in the prompt — §4b run as an
  episode: one state, two correct answers, decided by declared purpose.
  **J1P** (deliverable: phase identification): `converged`, next_action
  {none}.  **J1S** (deliverable: structure quality): `ambiguous`,
  next_action {chemistry_or_contents}.  *Verifying measurement*: the pinned
  2026-08-12 numbers — converges Rwp 0.0405, GoF 2.97, `lebail_gap` ×2.4,
  the alternating-sign contents clause — re-measured at build.
- **E1, R2 — solvable controls** `[registered]`, unchanged from 1.1 (E1:
  0.008° zero, tol {abs: 0.002}; R2: real scale ×0.90, tol {rel: 0.02});
  next_action {none} added to both truth rows.  Expected `converged`.  Kept
  so `underclaimed` means something: they are what separates "declined
  correctly" from "declines everything".

**Second tier** — built only if the core shows an effect: **J2** (qarr
sample 4, the designed Brindley failure, deliverable = QPA: `converged` +
{report_with_caveat} — the µR fence firing is the measurement, from the v0.3
acceptance); **E7** for 1.1's deferred hypothesis (the E7-haiku flip under
the capped abstained set); the second effort tier.  Tier-2 runs extend only
cells that showed an effect, and may also extend the `[registered]` rows:
E8′ as N1's synthetic control, J1P/J1S for the deliverable axis, E1/R2 if
the core shows underclaiming that needs disambiguating.

**Disposition of the 1.1 set**: E1 kept (control); E2 retired — its shape
lives on in E8′ and its record in the 1.1 grids; E3/E4/E5/E6 retired (E5's
impurity question is asked properly by W1, with a real impurity; E6's
phantom-phase invitation was re-attributed by the mining to Layer 0, which
W2 now tests); E7 second tier; E8 retired, replaced by E8′; R1 retired,
succeeded by C1 and N1; R2 kept (control).

## The answer contract (v2)

`answer.json`, written by the agent in its workspace:

```json
{"verdict": "<one of the five>",
 "next_action": "<one of the seven>",
 "summary": "<a few sentences: what you concluded and why>"}
```

**`verdict`** ∈ `converged` | `impurity_suspected` | `assumption_wrong` |
`abstain` | `ambiguous`.  The glossary the prompt carries (one authority:
`build_fixtures` renders it) must draw the W1/W2 line explicitly —
`impurity_suspected` is about the **specimen's phase content** (intensity
the given phase list cannot account for); `assumption_wrong` (new in v2) is
about a **declared input** — source lines, geometry, instrument — that
disagrees with the data, where fixing the declaration, not refining more
parameters, is the answer.  Without that line two tokens are defensible on
one row and the closed vocabulary stops protecting anyone.

**`next_action`** ∈ `none` | `extend_range_or_calibrate` | `add_phase` |
`fix_instrument_model` | `collect_better_data` | `chemistry_or_contents` |
`report_with_caveat` — graded by **membership in the row's registered set**
(near-equivalents must not fail on wording; the sets are in § Episodes).
The glossary distinguishes `extend_range_or_calibrate` (the measured window,
or a calibration on it, limits the answer) from `collect_better_data`
(counting statistics or resolution insufficient).

**`summary`** is free text and **unscored** — mining counts its citations
descriptively, and mining reads the `delivered`/`probed` surfaces, never
word-matches the summary (round 2: three cells voiced `exchangeable` with
the clause never delivered).

## Scoring rules v2

Grading stays deterministic — closed vocabularies make an LLM judge
unnecessary.  Unit-tested in `test_scorer.py`.

- **`passed`** = verdict match ∧ tolerance-recovery *where a tolerance is
  registered* ∧ next_action ∈ the registered set *where a set is
  registered*.  The single grade; everything else is descriptive.
- Recovery is by the planted parameter, never Δχ²; the last successful call
  is the answer state (JSON arms); a planted path absent from `parameters`
  was never freed and scores not-recovered (the surface serialises
  vary-or-tie entries only).  No successful call, or no valid
  `answer.json` → failed.
- **`overclaimed`** (kept): expected verdict is non-committal
  (`abstain`/`ambiguous`), answered `converged`.
- **`underclaimed`** (new, the mirror): expected `converged`, answered
  non-committal.  `impurity_suspected`/`assumption_wrong` are committal
  misses, not underclaims.  Both flags descriptive; neither touches
  `passed`.
- **The deliverable axis**: a truth row may carry `deliverable`; J1's two
  sub-rows share one episode core and differ only in the prompt's declared
  deliverable and the truth row.  Same scorer, different registration.
- **The python-arm adapter**: where JSON arms grade the last ok call in
  `calls.jsonl`, the python arm grades `final_result.json` (the agent's
  chosen final `RefinementResult.model_dump_json()`) with the same
  planted-path/tolerance/watch logic; `report_present`/`trajectory_rungs`
  record null — the condition audit is N/A by design in this arm.
- Wrong-frees and `watch` groups: unchanged from 1.1 — descriptive
  localisation evidence, never pass/fail inputs.

## Conditions

| condition | surface | report | trajectory | manual |
|---|---|---|---|---|
| `off` | JSON shim | — | — | none |
| `report` | JSON shim | ✓ | — | §5, §6 |
| `surface` | JSON shim | ✓ | ✓ | §5, §6 |
| `python` | the whole package | agent's to pull | agent's to pull | `AGENT_PROTOCOL.md`, verbatim copy |

**Dropped from 1.1**: `prompt` and `both` — round 2 answered the §9
instruction question (zero bootstrap calls in either arm), so the
instruction axis is retired and §9 excerpts appear in no 2.0 prompt.

Carried from 1.1, unchanged:

- **The shim, not the prompt, enforces the JSON conditions.**  Both switches
  are set on the request (the package never builds what the condition
  withholds) **and** popped from the response (a package default can never
  leak one back in); `test_shim_delivers_exactly_what_the_condition_declares`
  pins it.
- **The agent structurally cannot** touch the pattern, the starting values,
  `include_report` or `report_trajectory` — `overlay.json` admits
  `plan`/`mode`/`two_theta_limits` only.
- **One shared prompt per condition, no per-model tuning.**  §5/§6 ship with
  the report.  The trajectory-less `report` arm is told, in one factual
  sentence about the response shape, that the per-stage `trajectory` will
  not appear.
- Every call runs from the same fixed perturbed start; iteration is on the
  plan, not the state.  `MAX_CALLS = 8` shim-enforced; the prompt advertises
  6.

**The condition marker leaves the workspace** (the round-2 leak, fixed).  In
1.1 `condition.json` sat inside the episode dir, where an `ls` reveals it
and its `include_report: false` tells an `off` agent it is in a withholding
experiment.  In 2.0:

- `build_fixtures` writes the marker to a **sibling path the prompt never
  names**: `<episodes_dir>/<eid>.condition.json`, beside the episode dir
  `<episodes_dir>/<eid>/` that is the agent's workspace.  `run_refine.py`
  derives it from the episode dir it was handed; `scorer.py`/`grid.py` read
  it from the same place.
- The per-call record **drops the `condition`/`include_report`/
  `include_trajectory` echoes** `calls.jsonl` carried in 1.1 — the log lives
  in the workspace, so the echo was the same leak; one authority per fact
  (the sibling marker), and the delivered response shape is itself the
  auditable evidence (`report_present`/`trajectory_rungs` are read off the
  graded call).  `episode_sha256` stays.

## The python-capable arm

One arm, plus usage mining — it answers all three branches of the delivery
question at once, which is why there is **no report-off python arm**: a
crippled package tests a package nobody ships, and it is deferred unless the
single arm is ambiguous.

**Workspace** (built by `python_arm.py`): `episode.json` — the identical
fixed request core the JSON arms get (pydantic JSON round-trip *is* the
library-native form; the agent loads it through the schemas and drives the
package directly, no shim); a **verbatim copy of `docs/AGENT_PROTOCOL.md`**
— present in *all* python cells, because the manual ships with the package
and is part of the surface being tested, not a treatment; and `prompt.md` —
the v2 answer contract plus `final_result.json`, the workspace rules, and
the budget.

> **2026-08-29 (WP-1304).** That document is now a *directory*, so the
> workspace carries `skill/` — the whole tree, body and reference files,
> verbatim — where earlier rounds carried the single `AGENT_PROTOCOL.md`.
> The rule is unchanged and so is the argument for it: what ships with the
> package is part of the surface, never a treatment. **A round run after
> this date does not pool with one run before it** on any row that turns on
> what the agent could read, because the same text now arrives split across
> files an agent opens on demand rather than as one file it must page
> through. The §5/§6 excerpts the JSON arms quote were verified unchanged by
> the split (byte-identical for §6; §5 differs only by a dead relative link
> the move had to repair), so the JSON rows are unaffected.

**Environment**: rietx installed **non-editable into a venv outside the
repo tree**; no repo checkout reachable from the workspace; the truth tree
stays scorer-side.

**Budget**: the prompt advertises ~6 fit-bearing script runs; hard cap 8,
enforced by transcript audit (there is no shim to refuse).  A *fit-bearing
script run* is one python process that performed at least one solve — a
script that fits five times is one run; the budget paces the loop, not the
solver.  A transcript exceeding the cap invalidates its cell.

**Required artifacts**: `answer.json` (v2) and `final_result.json` — the
agent's chosen final `RefinementResult.model_dump_json()`.  The scorer
adapter grades the latter (§ Scoring rules).

**Forbidden and audited** (the round-2 pattern, extended): reading any repo
path, the truth tree, the eval docs, or the network.  A violating
transcript invalidates its cell.

**Mined per cell** (fields added to `mine_transcripts.py`; their token
vocabulary is quoted from the live schemas, never string literals — the
frozen clause phrase is the one deliberate exception, because the record
cannot change and the live sentence did): called `ref.report()`?  read the
identifiability / background evidence tables?  called `suggest()`?
`branch`/`compare`?  `predict_then_verify`?  `compare_rivals`?

**The arbitration** this usage record settles: pass-without-reading ⇒ the
report is a convenience; pass-by-reading ⇒ the report is the load-bearing
pull bundle; fail-where-JSON-report-arms-pass ⇒ push delivery matters.

## The matrix, and what it costs

Core, pre-registered: **{off, report, python} × {N1, C1, W1, W2} ×
{Sonnet, Haiku} = 24 runs**, plus **{surface} × {C1, W1} × 2 models = 4**
for the trajectory decision — **28 runs**, N=1 per cell, effort `medium`
pinned per run and recorded, model IDs recorded as the harness reports
them, never as requested.

Budget, from 1059's measured figure: ~56 k tokens per JSON run, ~100–150 k
estimated per python run ⇒ ~2.3 M core (20 JSON + 8 python).  The second
tier extends only cells that showed an effect.

## Pre-registered hypotheses

Written before any run; each names its cells.

- **(a) The 0.8 clause ends the ridge.**  On C1 and N1 (every report-bearing
  JSON cell and every python cell), both-free ridge states drop to 0 (round
  2 under the 0.7 wording: 7/20) and swap states — a single rival freed with
  the other held — appear.  Mined from `calls.jsonl` plans (JSON) and
  transcripts (python).
- **(b) `ambiguous`-only-with-report replicates on N1**: `report`/`surface`
  cells say it where `off` cells cannot (round 2: 8/16 vs 0/4).
- **(c) Python matches or beats JSON `report` cells on decision quality**
  (passed on the epistemic group), and its wins cite pulled evidence — the
  report-vs-tools-vs-package answer, read with the § python-arm arbitration.
- **(d) W1 `surface` cells beat W1 `report` cells outright, or the
  trajectory default flips.**  Cells: {surface} × W1 × 2 models against
  {report} × W1 × 2 models — W1 is the one row with a real
  climbing-confidence signal, so the `report_trajectory` decision is made
  here or nowhere.
- **(e) W2 separates `assumption_wrong` from `impurity_suspected`.**  The
  designed trap is Layer 0's unmatched list (per the round-2 mining), and
  the discriminator is that a source fix kills the satellites while an
  impurity's peaks would survive it.

## Kill/keep

Pre-registered; the decisions land in WP-1003's `### Inherited` at close.

| Component | Killed/demoted if | Action on kill |
|---|---|---|
| Report contract (Layer 0 + background/identifiability/lebail_gap evidence) | **not on trial** — content value is measured (WP-1055/1056/1057; Jacobian-derived evidence cannot be re-derived by any consumer) with three consumers; an eval null cannot outweigh that | n/a; removal would be a 1003 decision needing new grounds |
| Layer 2 prose/actions | cells that read Layer 2 do no better than cells reading the evidence tables (mining decides which was read), and the causal record stays negative (E7 round 1, R1 first rung round 2).  Decidability precondition: at least one core episode's **converged** report carries actions (W1, verified at build) — else this row is recorded undecidable-by-design before the round | demote in AGENT_PROTOCOL to "hypotheses to verify"; soften confidence language; no schema removal pre-freeze |
| `RefineRequest.report_trajectory=True` default | `surface` cells again cost more calls with no decision-quality gain on W1 — its one real-signal row.  The criterion is content, not cost: the mining refuted "paid for and unread" (11/12 cells read rung content) — do not re-litigate cost | flip to False; record in 1003, resolving the library/agent asymmetry the freeze flags |
| refine_json pull surface | python wins route through pulls JSON lacks and JSON arms fail those same rows | add the `compare_exchanges` arm pre-freeze for 1003 to ratify, or document refine_json as the constrained one-call surface with python primary |
| The delivery-eval programme | round 3, with measured rows and clean audits, still yields no interpretable signal at budgeted N | stop A/B rounds; the injection suite remains the report's evidence base; 1003 records delivery claims as unmeasured — the honest sunk-cost exit |

## Running

Each run gets a fresh episode dir; the truth tree stays outside every
agent's reach:

```sh
.venv/bin/python -m tests.eval_report_agent.build_fixtures \
    --episodes RUNS/<condition>__<model> --truth TRUTH \
    --condition report --only N1 C1 W1 W2
.venv/bin/python -m tests.eval_report_agent.python_arm \
    --workspace RUNS/python__<model> --truth TRUTH --only N1 C1 W1 W2
```

Runs execute in the Claude Code harness — the Workflow `agent()` call takes
per-run `model` and `effort`.  Each agent receives exactly its episode's
`prompt.md` (plus the path to its workspace) and nothing else.  The runner
instruction carrying the agent to `prompt.md` is identical in every cell and
**must forbid reading anything outside the workspace** — repository, docs,
sibling files.  An agent free to open `docs/AGENT_PROTOCOL.md` gives itself
the excerpt its condition withholds; a JSON-arm agent free to read the
sibling marker learns its condition.  Verified in the audit; a violating
transcript invalidates its cell.

Score and grid:

```sh
.venv/bin/python -m tests.eval_report_agent.scorer RUNS/<cell>/<eid> TRUTH/<eid>.json
.venv/bin/python -m tests.eval_report_agent.grid RUNS TRUTH [--json]
```

## Audit

- `calls.jsonl` (JSON arms) is the record — call trace and count from the
  shim's log, never the agent's self-report.  Delivered payload
  (`report_present`/`trajectory_rungs` off the graded call) must match the
  condition's declaration; a mismatch invalidates the cell rather than being
  explained (grid marks it `!`).
- Python-arm audit: fit-bearing run count against the cap; the forbidden
  reads (repo, truth, eval docs, network); the usage-mining fields.
- **Transcripts keep thinking blocks.**  Round 2's kept transcripts carried
  none (measured: 0 characters over all 30), so `voiced` was only a floor on
  what was read; round 3 keeps the reasoning surface.  Tool calls are
  unaffected either way; citations are not.
- Spot-check at least one transcript per condition × model cell for
  prompt-compliance, but grade only from the record + `answer.json`.

## Reading the grid

- **Two count tables, always**: the epistemic group (expected verdict ∈
  {ambiguous, impurity_suspected, assumption_wrong, abstain} — N1, W1, W2
  in the core) and the solvable group (expected `converged` — C1 in the
  core; E1/R2/J1P when run).  Generalises round 2's rule: the groups answer
  different questions, and pooling them is how round 1's null was misread.
- **Counts, never percentages** (the indexing-scoreboard rule; Bergmann,
  Le Bail, Shirley & Zlokazov 2004), dated, never a CI assertion — a pilot
  establishing protocol soundness and effect direction, not a benchmark.
  Model IDs and efforts in the header; venv and platform with every count.
- `underclaimed` on the solvable table is what separates "declined
  correctly" (verdict match on the epistemic table) from "declines
  everything".
- Per-row notes that must ride with the tables: W2's arm asymmetry (JSON
  arms reason from Layer 0; the python arm can run the source experiment);
  N1's overlay can only narrow (an agent asking for a wider window is
  reading the right limit — that is the registered next_action, not a
  harness gap); C1's tolerance is what fails the ridge and the
  zero-absorber, so a C1 fail is read against *which* state it reached.
