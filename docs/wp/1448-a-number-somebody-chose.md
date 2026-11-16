# WP-1448 — a number somebody chose says so, and says where the argument is

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P4 2026-09-23 — provenance bookkeeping; changes no number

## Goal

A value in this package declares which of three things it is: taken from a
publication, measured here by a named run, or chosen by a person. The third
kind carries a pointer to where the alternatives are written down.

## Context

Filed 2026-09-22 at the maintainer's ask, during WP-1442. The trigger was a
question: the repo records literature provenance carefully, and for a decision
reached in conversation there is no equivalent. The audit below is what exists
today.

**Literature provenance is solid and enforced.**

- `ATTRIBUTION.md` records every source, its licence, and exactly what was used,
  with the GPL fence stated per entry.
- Root CLAUDE.md: "Every physics function cites its reference (author, year,
  journal) in the docstring", and documents conventions by physics rather than
  by letters.
- `tests/test_manual.py` requires every displayed equation in the theory manual
  to carry a `*Source:*` line whose symbol imports, so renaming a physics symbol
  fails the build.

**"How well do we know this" is enforced, but only in the agent skill.** Every
row of a `references/` file must close with `*(Measured: …)*` or
`*(Hypothesis: …)*`, and `tests/test_skill.py` rejects a tag that names nothing
— added after `*(Measured: some runs I did)*` passed (issue #241). That test is
the working model for anything proposed here.

**Decisions have a format and no requirement.** `docs/DESIGN.md` § Locked
decisions carries entries with dated `*Amendment (2026-07-24)*` and
`*Measured (2026-07-27, WP-0408 landed)*` sub-bullets, including what was
expected against what happened ("Apple-GPU acceleration did not materialise").
That is the right shape. Nothing says which decisions must appear there, and no
test reads it.

**In the code the practice is ad hoc.** Fourteen places say some version of
"this package's own", "had no source", "quoted, never tuned"
(`optimize/statistics.py`'s McCusker bands, `io/formats/*.py`'s hand-written
parsers, `help.py`'s 25 Å² default). Useful, unenforced, and not a vocabulary.
*Superseded in part (2026-11-16, checked on `bc77a934e`):* the 25 Å² default is
gone (WP-1534), and a grep of `src/rietx` for those phrasings now finds 19
"this package's own", 12 "no source" and 8 "never tuned", most of them about
parsers and wording rather than a value. Two more phrasings carry case 3
already: "decided YYYY-MM-DD" (9 sites, most naming a WP) and "ruled
YYYY-MM-DD" (161, nearly all the generality rulings).

**What landed since this was filed (premise check, 2026-11-16).** The
generality audit (WP-2001, opened 2026-10-19) now records case 3 for part of
the tree. `rietx._audit.ROWS` gives every module-level number under
`_audit.WALKED` and every default at `_audit.DEFAULT_SEATS` a tier, and tier 3
("rietx's own") must carry `grounds` and a dated `approved`
(`tests/test_audit_table.py`). On `bc77a934e` 165 rows are tier 3. So for a
walked number the *approval* of a choice is recorded and enforced. Three parts
of this WP's gap remain: (1) nothing at the value tells a reader of the code
that it was chosen, since the table is a 484 KB file nobody reads beside
`diagnostics.py`; (2) nothing points at where the alternatives are, and 55 of
the 165 tier-3 rows name no WP in `grounds` or `evidence`; (3) what the audit
cannot see by declaration (an inline literal, a number in a dict, a design
choice with no number, such as "report-only, no threshold") has no record at
all. `GHOST_MIN_PARENTS` and `GHOST_RATIO_TOL` are still at `unaudited`.

**The gap, stated exactly.** For a constant in the code, nothing distinguishes:

1. it comes from a paper — covered, cited, enforced;
2. it was measured here, by a run somebody could repeat — covered by convention
   and by the WP handover the code cites, not enforced;
3. **somebody chose it**, and the argument for choosing it over the
   alternatives happened in a conversation.

The worked example is this WP's sibling. `GHOST_MIN_PARENTS = 5` reads like
case 2, because the measurement that supports it is in its docstring. But the
decision to use a fixed count *at all* — rather than a control run per pattern,
which was measured, costed at 1.4 % of the peak fit, and rejected — was a
conversation. Nothing in the tree says the alternative existed. WP-1447 now
records it because the maintainer asked for it in the same breath, which is the
point: it took an explicit ask.

The same applies to `GHOST_RATIO_TOL = 2.0`, where the measurement says 1.3,
1.5, 2.0 and 3.0 are equally specific and 2.0 was chosen because it is the
widest at which "a common ratio" still means something. That last clause is a
judgement wearing a measurement's clothes.

**What is not the problem.** Handover logs are dated and detailed, and the code
cites the WP number, so a determined reader can reconstruct most of it. The
failure is that nothing *prompts* the record, so it happens when someone
remembers, and the alternatives are the first thing lost.

## Non-goals

- A second citation system. Literature provenance works; this sits beside it.
- Recording conversations. The artefact wanted is the decision and the
  alternatives, not a transcript.
- Blocking a commit on a missing tag for values that are plainly derived.

## Tasks

- [x] The vocabulary: a third tag beside the skill's two, for a value chosen
      rather than derived, naming the date, that it was a decision, and where
      the alternatives are. Decide whether it reads in code comments, in the
      WP, in DESIGN.md, or in more than one, and write the answer here.
      **Decided 2026-11-16.** The tag takes the skill's shape, because a
      reader who knows `*(Measured: WP-1500 — a run)*` reads this one
      without a key (DESIGN.md Rule 5, convention first):

      `*(Chosen: WP-1447, 2026-09-22 — a fixed bar over a control run per pattern)*`

      The pointer comes first, as a `Measured` tag's WP does: `WP-NNNN`, or
      a `docs/` path and a heading (`docs/DESIGN.md § Locked decisions`).
      Then the date the choice was made, then what was chosen over what.
      **It reads in the code**, in the `#:` comment or docstring of the
      value, because the goal is that the value declares itself where a
      reader meets it. The tag is a pointer and never the argument, which
      stays in the record it names, so this is not a second citation system.
      The other two kinds keep the form they already have: a paper is cited
      in the docstring (author, year, journal), and a measurement names the
      WP whose handover holds the run. Neither takes a tag here.
      **Not in the skill.** A skill row resting on rietx's own choice is cut
      by DESIGN.md Rule 3, so a `Chosen` skill row would be a contradiction.
      **Beside the audit table, not instead of it.** A walked number keeps
      its `_audit.ROWS` row, whose tier 3 is the maintainer's approval to
      keep it. The tag says where the alternatives are, and the row says it
      was approved. Whether a tier-3 row must also name that pointer is the
      maintainer's call (handover, 2026-11-16).
- [x] Where the alternatives live. DESIGN.md § Locked decisions already has the
      format and the dated-amendment habit; the question is whether a
      WP-scoped decision belongs there or in the WP, and what the rule is.
      **The rule: in the record where the choice was made, under its date.**
      A choice made inside one WP goes in that WP's handover entry of the
      day, alternatives and all, because the WP is what the code already
      cites and its log is dated. A choice that binds later WPs (a
      package-wide default, a convention) goes in DESIGN.md § Locked
      decisions, as an entry or a dated *Amendment*. A maintainer ruling
      recorded in a milestone file (`docs/milestones/generality.md`
      § Decisions with the maintainer, 2026-10-18) stays there. The tag
      names whichever holds it. A choice later revisited gets a new dated
      entry and a new tag date; the old entry stays.
- [x] The meta-test, modelled on `test_skill.py`'s: a tag that names nothing is
      a failure. Decide what it can actually check — a date, a resolvable WP or
      DESIGN.md anchor — and do not claim more.
      **`tests/test_chosen_values.py`.** It checks that every `*(Chosen`
      under `src/rietx` parses whole (so a misspelt tag fails, not passes
      unread), that its date is real and not in the future, that its WP file
      exists or its `docs/` file has the named heading, and that the record
      mentions the date (in the WP file, or inside the named section). It
      **cannot** check that the record holds the alternatives, only that the
      pointer lands on a record of that day; nor that an untagged value was
      not chosen, which is why the tag is a convention and not a gate on
      every number. The check runs on a fixture tree too (ten failing tags,
      four passing), and was made to fail twice on purpose: with no tags in
      the tree, and with one live date moved a day.
- [x] A pass over the values that are case 3 today. Start from the fourteen
      "this package's own" / "no source" sites and from any constant whose
      docstring argues rather than measures.
      **Done 2026-11-16: five tags, each checked against its record.** Tagged
      where a WP entry of the day records the choice and its alternatives:
      `background.diagnostics.GHOST_MIN_PARENTS` (WP-1447, 2026-09-22),
      `_ghost_consensus`'s parent count (WP-1442, 2026-09-22), `SAMPLING_HEIGHT_FRACTION` (WP-1415, 2026-09-21), and
      the report-only `split_share` in `report/schemas.py` and
      `report/localisation.py` (WP-1339, 2026-09-03). Each replaced a
      "decided YYYY-MM-DD" phrase or sat beside "Chosen with that margin";
      no number moved.
      *Not tagged, and why.* Of the "this package's own" / "no source" /
      "never tuned" sites, most describe a parser or a wording, not a value.
      `B_iso` unbounded (WP-1534) follows the default of all three programs
      it names, so it is established practice, not a free choice. Five
      sites argue a choice and have **no record of the alternatives** to
      point at: `background.select`'s "conventional 3σ, no source cited"
      (named in WP-2002, never decided there), `schemas.interval
      .PARAMETER_INTERVAL_CHI2_TOL` ("Chosen, not measured", WP-1929 records
      no alternative), and three that predate the WP-1066 rename and so
      lost their history (`indexing.fom`'s ⟨ΔQ⟩ floor,
      `crystallography.symmetry.SYMMETRY_ANGLE_TOL_DEG` and
      `crystallography.cif.CIF_ANGLE_CORRECT_MAX_DEG`).
      `GHOST_RATIO_TOL`, the worked example above, is not tagged either:
      its 1.3/1.5/2.0/3.0 sweep is written only in its docstring, and
      WP-1442's 2026-09-22 entry names the constant without it.
      Inventing a record for them would be the failure this WP describes.
      The 161 "ruled YYYY-MM-DD" phrases are the generality rulings, whose
      record is `docs/milestones/generality.md`; converting them is a
      maintainer's call (handover, 2026-11-16).
- [x] Root CLAUDE.md § Conventions takes the rule, in the form it takes rules:
      a few lines, evidence compressed, pointing here.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_skill.py tests/test_chosen_values.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- `tests/test_skill.py` § the `*(Measured: …)*` tag and issue #241 — the
  working precedent, including what a tag check can and cannot enforce.
- `docs/DESIGN.md` § Locked decisions — the format, with WP-0408's amendment as
  the best existing example.
- WP-1442 and WP-1447 — the decisions that prompted this, and the only two
  currently recorded to the standard proposed.

## Handover log

### 2026-11-16 — the tag, its test and a first pass; PR #1628, follow-ups in #1629

A value somebody chose can now say so where a reader meets it, and say where
the alternatives are written. The tag has the same shape as the skill's
`Measured` tag, and points at the WP entry or design-record section of the day
the choice was made. A test fails any tag that does not land on a record of
that day. Five values carry it. The pass mostly showed how little can be
tagged honestly: five more values argue a choice and have no record of what
was rejected. The WP's own worked example, `GHOST_RATIO_TOL`, is one of them,
because its sweep was written into the docstring and never into the WP. What
it ruled out: the audit table already holds the *approval* of a chosen number
(WP-2001, after this WP was filed), so the tag is only a pointer, and the
question of whether a tier-3 row must carry the same pointer goes to the
maintainer.

*Done* (PR #1628, draft until this entry). Premise checked against
`bc77a934e` and the Context updated in place; the moot `### Inherited` entry
(`BISO_BOUNDS`, deleted by WP-1534) removed. Tasks 1-2 decided above. Task 3
is `tests/test_chosen_values.py` (16 cases: the live scan, 4 passing and 10
failing fixture tags, the line-wrap reader). Task 4 tagged five sites in
`background/diagnostics.py` and `report/`, with no number moved. Task 5 is a
four-line bullet in root CLAUDE.md § Conventions; CLAUDE.md sat exactly on its
995-line cap, so the cap is now 1000 with its logged row, landed at 999.
Review (a read-only subagent, not `/code-review`): two findings, both taken. A
`docs/` pointer could not name a heading with a comma, and the
`GHOST_RATIO_TOL` tag pointed at a record without its alternatives, so it was
removed.

*Not done, deliberately.* The `Status:` line stays ⬜ and `docs/wp/README.md`
is untouched, because open PR #1601 edits the index; flipping it to ✅ once
that PR merges is in #1629. The WP is otherwise complete.

*Generality.* No judge dispatched: the branch does not touch `_audit.py`, and
adds no heuristic, only comments on existing values and a test.

*Measured* (a Linux x86-64 workstation, Python 3.12 venv, [dev]-equivalent,
co-tenant beside one other job): canary `pc1448c` 102 passed in 25 s on 4
pinned cores; fast suite `pc1448f` 14 866 passed, 280 skipped, 32 xfailed in 522 s (8 pinned cores, 746 % CPU, peak 6.2 GB) on `9c06c4414`, the tree before this entry. Local (darwin arm64, worktree
`.venv` [dev]): the acceptance files `test_docs_consistency`, `test_skill`,
`test_chosen_values` and `test_audit_table` 238 passed before the review fixes
(the review added one case); ruff clean; `python -m tests.reader_output` exit 0
(reader output unchanged); `rietx_vale.sh` 0 errors.

*Gotchas.* A tag's record check reads the whole WP file for the date, so a
Status line alone can satisfy it; the test's docstring says so. The date of a
`docs/` pointer may sit in the heading itself (generality.md's decisions
heading), so the section read includes the heading line.

Next, in order: the maintainer rules #1629's four questions (the first decides
whether `test_audit_table.py` grows a pointer check); after #1601 merges, flip
this WP to ✅ and regenerate the index; new choices take the tag as they land.

### 2026-09-22 — filed

The repo is careful about where an idea came from when the idea came from a
paper. It is careless when the idea came from a person. A constant that somebody
chose looks exactly like a constant that was measured, because the measurement
supporting the choice gets written into the docstring while the choice does
not, and the alternatives that were rejected disappear with the session that
rejected them.

Nothing here is missing machinery so much as a prompt: `DESIGN.md` already has
the right format and the agent skill already has an enforced epistemic tag. The
work is deciding the vocabulary, deciding where a decision belongs, and making
it fail when it is absent.

Next: the vocabulary, since every other task depends on it.
