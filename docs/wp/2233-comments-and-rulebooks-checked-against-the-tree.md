# WP-2233 — Comments and rulebooks checked against the tree, and their size limits held from main

Milestone: unscheduled · Status: ✅ 2026-11-21 — comment, docstring and rulebook citations checked against the tree; rulebook byte limits held from the base
Track: The repo's own process
Depends on: —

## Goal

A comment, docstring or rulebook that names code, a file or a test that no longer exists fails
CI. The always-loaded rulebooks have byte limits read from the base, so a change cannot raise
its own limit, and a change that raises one is visible as nothing else.

## Context

**Why.** Agents read comments and rulebooks as true. A comment that cites a deleted function
sends the next session looking for it, or rebuilding the old design around it. The manual
already has this guard (`tests/test_manual_api.py::test_every_dotted_name_resolves`). So does
`gui/CLAUDE.md` (`tests/test_docs_consistency.py::test_gui_rulebook_paths_resolve`, WP-2134).
The library's own prose has none.

**Measured 2026-11-21** (worktree `.venv`, macOS arm64, `origin/main` at `592e3250f`). The
filing session's prototypes lived in its scratchpad, which is not kept, so the method is
restated here.

- `src/rietx` holds 11 866 comment blocks and docstrings: 5 160 docstrings, 5 609 `#` blocks
  and 1 097 trailing comments. They carry 0.69 lines of prose per line of code, against 0.31
  for `numpy/_core` and 0.18 for GSAS-II 5.8.4.
- **Sphinx-role targets** (`:func:`, `:data:`, `:class:`, `:meth:`, `:attr:`, `:mod:`, `:exc:`,
  `:obj:`, `:const:`): 6 596 in `src`. A prototype resolver fails on 72. For 6 of the 72 the
  name occurs in no code token anywhere in `src`. The other 66 are wrong locations or gaps in
  the resolver, and are unsorted. The prototype's order was:
  1. the target taken as absolute from `rietx.`;
  2. relative to the citing module and each parent package;
  3. a builtin, or an importable top-level module;
  4. an attribute, annotation or pydantic field of any class defined in the citing module.

  Step 4 is looser than how Sphinx's Python domain looks names up, which uses the enclosing
  class. It therefore misses some stale names. Strip whitespace from a target before reading
  its `Title<target>` form, because targets wrap across lines.
- **Plain backtick names**: 193 identifier-like segments cited in ``literal`` spans are absent
  from every code token in `src`, `tests`, `gui/src`, `kernels`, `examples` and `docs/docs`.
  Most are foreign vocabulary: TOPAS keywords, GSAS-II functions, vendor file fields and
  chemical formulas. About 40 were checked by hand, and a second reviewer confirmed the first
  eleven below. Each is a present-tense pointer to code that is gone (the line given is where
  the block starts):
  - `gui/session.py:178` `AgentError.details` (`rietx.agent` was deleted by WP-1303)
  - `schemas/plan.py:280` `agent._RequestBase._known_plan`. An empty plan is still refused,
    at `refine.py:6213`, so only the pointer is wrong.
  - `strategy/staged.py:495` `MultiRefinement.fit` (no such class)
  - `strategy/staged.py:181` `VALIDATION_WINDOW_SLACK_DEG`, now
    `indexing.workflow.VALIDATION_SLACK_BOUNDS_DEG`
  - `schemas/indexing.py:703` `rietx.indexing.consensus.confidence_for`
  - `schemas/indexing.py:837` `PEAK_SEPARABLE_MAX_CHI2`
  - `indexing/trial_error.py:76` `DOMINANT_ZONE_PROBE_STEP`
  - `model/forward.py:1079` `refine._attach_origin`
  - `schemas/sequential.py:1280` `_disagreement`
  - `crystallography/magnetic/operators.py:415` `test_moment_path_is_clean_by_design`
  - `viz/figure3d/raster.py:334` `_outline`. Only `_outline_numpy` exists, and the Rust side
    has `draw_outline`.
  - `io/projects/topas.py:400` `:func:`magnetic_group_number``
  - `strategy/magnetic.py:197`, a role reading `moments.:SEED_TILT` once whitespace is
    stripped. It probably wraps across lines. Unconfirmed by grep.
- **Repo paths and test IDs in comments**: 544 citations in `src`. The reviewer's quick scan
  found these files missing: `tests/test_ticks.py`, `tests/test_row_layout.py`,
  `tests/test_operator_order_independence.py` and `tests/test_epsilon_bookkeeping.py`. A
  `tests/test_bccg.py::…` citation needs its node checked. `test_gui_rulebook_paths_resolve`
  already resolves such tokens for one rulebook.
- **Dotted `rietx` literals** (``a.b`` whose first segment is a rietx module): 578, of which
  102 do not resolve. Most of the 102 are file names such as ``project.py`` and
  ``project.json``, which the path check above covers.
- **Version changelogs in comments.** WP-1117's rule, stated
  above each constant, is that "the comment says what changed". `/pr-review`'s sync
  procedure (`.claude/skills/pr-review/SKILL.md`, the `Also in M` notes) is built on it. Four
  blocks sit directly above a `*_VERSION =` constant:
  - `schemas/common.py:20`, `SCHEMA_VERSION`: 707 lines
  - `report/schemas.py:34`, `THRESHOLDS_VERSION`: 277 lines
  - `schemas/indexing.py:38`, `INDEXING_THRESHOLDS_VERSION`: 203 lines
  - `schemas/project.py:33`, `PROJECT_FORMAT_VERSION`: 33 lines

  They name removed things on purpose (`SEQUENTIAL_WIDTH_GROWTH`, `Z_INTEGER_TOLERANCE`,
  `RefineRequest`). Each history's share of its file: 50 173 B of 77 822 B in `common.py`
  (64 %, which had 96 commits in the month to 2026-11-21), 19 039 B of 107 166 B, 14 894 B
  of 155 025 B, and 2 358 B of 10 034 B. They move out under ruling 5. `/pr-review`'s sync
  does not need them beside the constant: it resolves the notes as text and reads the number
  from `common.py`, which stays.
- **Rulebooks.** No CLAUDE.md cites a WP number without a WP file. The prototype path check
  over the other five rulebooks flagged GUI routes (`/api/params`), slash commands
  (`/pr-review`) and `module.attr` forms (`projects/gsas.split_records`). Those are false
  positives for a path check. The number of real misses is not yet measured.
- **The size caps do not hold.** `SIZE_CAPS` in `tests/test_docs_consistency.py` caps lines
  for six documents. `AGENTS.md` and `src/rietx/gui/CLAUDE.md` are not among them. The root
  CLAUDE.md's diary has 37 rows from 2026-08-14 to 2026-10-31: 35 raises and 2 cuts (906 →
  760, 760 → 722), from 600 lines to 995. Some jumps carry no row (644 → 648, 732 → 929).
  `docs/ROADMAP.md` has 38 rows. Each raise was made by the session that needed the room, in
  the same change. The failure message encourages raising. It says "Do not delete facts to
  fit" (`test_docs_consistency.py:1265`), and diary rows quote it back ("Raised rather than
  shaved, per the failure message's own instruction"). The root file was condensed twice
  before (WP-1031: 1142 → 601 lines; WP-1060: → 553) and regrew both times. It is now 86 775 B
  and 12 826 words. WP-2009 measures about 21k tokens a request.
- **What CI can see.** The lint job checks out with `fetch-depth: 2` (`ci.yml:137`, `:211`).
  The test and docs jobs use the default depth of 1. `origin/main` is never present.
  `tests/skill_caps.py::base()` (lines 195-214) already answers "what is the base":
  `RIETX_CAPS_BASE` if set, `HEAD^1` on a pull request, `None` on a push to `main`, and the
  merge-base with `origin/main` locally. `tests/audit_delta.py` reads the **base's** tables with
  `git show` and AST, never by import. It fails a change by **name**, never by count, because a
  count lets a change delete one entry to buy room for another (its docstring, lines 26-29).
  Both run as lint-job steps (`ci.yml:174`, `:191`).
- **CI cost of the resolver**, one run each: 3.5 s to tokenize and parse all 262 files, 2.2 s
  to import all 260 modules, about 3.5 s for the prototype end to end. Small against the fast
  suite's 3-5 min. The import is shared with any test on the same worker.

**Rulings, maintainer, 2026-11-21.**
1. Narration in comments ("until WP-N", "since WP-N") is **tracked, not gated**, for now. The
   trend is measured before any gate is decided.
2. **No hook asks the maintainer** before a size limit is raised. The limit is held by reading
   it from the base (task 6).
3. The user-level CLAUDE.md in the separate `claude-config` repository is out for now.
4. Enforcement is structural wherever possible. A failure message carries the rule it
   enforces and where the text goes, so the checks need no new CLAUDE.md prose.
5. **The four version histories leave the source**, one file per contract, following
   established practice (a changelog file). This changes where WP-1117's "the comment says
   what changed" is written, not what it requires: every bump still carries its note.

**What this holds and what it does not.** Reading limits from the base stops a change from
raising its own limit. It does not stop a one-line raise PR that an unattended shift merges
under the "merge clear-cut PRs" ruling: every PR comes from one account, so nothing on GitHub
can tell an agent from the maintainer. Task 6 makes such a raise a change of its own that
fails if it carries anything else, and that prints a warning in CI. A raise becomes visible.
It is not prevented. Nothing structural checks whether a comment's reasoning, or a number it
quotes, is still true when every name in it resolves. For example, `schemas/instrument.py:2229`
says "One member today, `HumpComponent`", and the union now has two members.

**Seams to extend.**
- `tests/skill_caps.py`: `base()`, `rev_exists`, the git helpers, and the
  budget-and-ceiling pattern, with its ceiling gap of twice the worst day's growth
  (`REFERENCE_GAP_BYTES`).
- `tests/audit_delta.py`: reading the base by `git show` and AST, and failing by name.
- `tests/test_manual_api.py`: `_step` and `_resolve_absolute`.
- `tests/test_docs_consistency.py`: `test_gui_rulebook_paths_resolve`, `_RULEBOOK_BASES`,
  `_RUNTIME_DIRS`, and `SIZE_CAPS` with its diary.
- `docs/milestones/process.md` § The caps diary.

**Tier.** Every rule here is named practice. Cross-reference resolution is Sphinx's
`nitpicky`, which cannot run here because the manual renders no docstrings (`docs/docs/conf.py`
has no autodoc). A throwaway autodoc build with `nitpicky` would cover role targets in
docstrings only. It would miss `#` comments, ``literal`` names and paths. Its cost was not
measured. Ruff's pydoclint port (`DOC`, preview in 0.17.6) checks docstring sections against
signatures, and `src` has none, so it cannot apply. Name allowlists checked against the base
are `audit_delta.py`'s pattern. History belongs in version control and decision records (Martin
2008, *Clean Code*, ch. 4, "journal comments"). No dataset is involved.

## Non-goals

- The rulebooks' content pass (findings out, rules rewritten): WP-2009. This WP builds the
  checks and the limits that 2009's result then lands under.
- Gating comment narration: ruling 1.
- A hook or approval step for a limit raise: ruling 2.
- `claude-config`'s user-level CLAUDE.md: ruling 3.
- A cap on comment-block length. The long `#` blocks are mostly `#:` attribute doc-comments,
  which is Sphinx's docstring syntax, and a blank line or a string literal gets round any cap.
- An LLM reviewer in CI reading the comments a diff touches. It is probabilistic, and it spends
  subscription quota on every PR.
- Checking that quoted numbers are still true: see "What this holds".
- Banning WP citations in comments. A pointer to the decision record is the kind that stays
  true.
- The skill (`docs/skill/rietx/`): already capped by `tests/skill_caps.py`.

## Tasks

- [x] **The version histories leave the source** (ruling 5).
      - Move each of the four histories, byte for byte, to one file per contract outside
        `src`, for example `docs/contracts/schema.md`. Leave a one-line pointer above each
        constant.
      - Rewrite WP-1117's rule text above each constant to name the file.
      - Rewrite `/pr-review`'s sync paragraph (`.claude/skills/pr-review/SKILL.md`, the
        schema number and `INDEXING_THRESHOLDS_VERSION` items) for the file.
      - Grep `tests/`, `docs/` and `.claude/` for every other reader of the comments first.
      - Add a test that each file's newest entry names its constant's current value, so a
        bump without a note fails.
- [x] **The resolver, as a stdlib-plus-import script** (`tests/code_references.py`).
      It covers role targets, dotted `rietx` literals, and repo paths and test IDs
      (a token with a `/` or `::`, resolved against the repo root, `src/rietx` and
      `tests/`), by the order in Context. It prints every miss.
- [x] **The sweep.** Fix every miss the script prints, including the pointers listed in
      Context. Fix a resolver gap in the resolver. Foreign vocabulary goes on an allowlist
      in the script, each entry with a reason.
- [x] **`tests/test_code_references.py`**, landing green after the sweep. Every
      reference resolves or sits on the allowlist. The failure message says: a comment
      names code that is gone, so rewrite it against the code it describes, and put
      history in the WP or the release notes. A lint-job step fails a change that adds
      an allowlist name absent at the base, read from the base by `git show` and AST,
      as `audit_delta.py` does. It runs in the fast suite. Quote its duration from
      `--durations`.
- [x] **Rulebook references.** Generalise `test_gui_rulebook_paths_resolve` to every
      `CLAUDE.md`, `AGENTS.md` and `.claude/skills/*/SKILL.md` (`pr-review` names code).
      Skip GUI routes and slash commands by form: a leading `/` and no file extension.
      Resolve `module.attr` forms with the resolver. Measure the real misses first. Fix a
      pointer here. Where the clause around it is one WP-2009 rewrites, add the miss to 2009's
      Inherited entry.
- [x] **Narration counted.** A stdlib script that runs on any revision (`git show <rev>:<path>`)
      and counts, per top-level package, the blocks matching `until WP-\d{4}`,
      `since WP-\d{4}`, `before WP-\d{4}` and `(was|were) .{0,60} until`. On 2026-11-21, 56
      blocks matched the "until" pattern. Record today's counts in the handover. No CI step:
      because it runs on any revision, the follow-up can compute the trend from history. At
      close, file a P4 WP dated six weeks on that runs it over weekly commits and decides
      whether to gate or drop.
- [x] **Byte limits held from the base.**
      - Move the limits to a stdlib module as a table read by AST: a budget and a ceiling per
        always-loaded document. That is every `CLAUDE.md`, `AGENTS.md` and `docs/ROADMAP.md`,
        which adds the two that `SIZE_CAPS` lacks.
      - Count bytes, because reflowing changes a line count.
      - **Ceiling**: checked in pytest on every tree, `main` included. Set it at the budget
        plus `skill_caps.py`'s gap rule, measured on each file's own merge history.
      - **Budget**: compared by a lint-job step against the base's table, read by `git show`
        and AST, with the base from `skill_caps.base()`. A file over the base's budget may not
        grow.
      - **Raises**: a change whose budget or ceiling is above the base's fails unless it
        touches only the table and the diary, and it prints a `::warning`.
      - **Missing base**: fail closed on a pull request whose base is missing, or whose base
        has no row for a new document. A new rulebook enters at a stated default.
      - **Failure message**: names "cut, or move the text to the WP or the record". It never
        names raising.
      - **Pins and diary**: pin each budget at today's bytes. WP-2009's landing re-pins it
        downward, and a cut needs no separate change. `SIZE_CAPS` and its line diary retire to
        `docs/milestones/process.md` beside the existing one.
- [x] Tests. Show each check failing once against a planted break: a renamed function, a
      deleted test file, a grown rulebook, a raise inside a content change, and a pull
      request with no base.
- [x] Skill: none. The skill is for driving rietx, and this changes only how the package's own
      prose is checked.

## Acceptance

```sh
.venv/bin/python -m tests.code_references
.venv/bin/python -m pytest tests/test_code_references.py tests/test_docs_consistency.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The tree is green after the sweep. A planted rename of a cited function, or a deleted cited
test file, fails `test_code_references.py` with a message naming the citing file and line. A
pull request that grows a rulebook over the base's budget fails. One that raises a limit
alongside any other edit fails, and a pull request with no base fails.

## References

- Martin, R. C. (2008). *Clean Code*, ch. 4, Comments ("journal comments", "misleading
  comments"). Prentice Hall.
- Ousterhout, J. (2018). *A Philosophy of Software Design*, ch. 12-16. Yaknyam Press.
- Sphinx `nitpicky` mode: the cross-reference check this reproduces for docstrings no page
  renders.

## Handover log

- **2026-11-28** — repair, by a ghostshift close-only runner. The session-start
  scan flagged two `WP-2233:` commits made after this file was last touched. The entry below
  records them. They were CI fixes on the closing PR, #1757, and reopen no work. Nothing else
  changed, and the status stays ✅. Both entries correct this WP's own record and ask for no work.

- **2026-11-21** (reconstructed post hoc) — two commits landed after the close entry. Both rode
  PR #1757 before it merged as `e439a8f48` that evening, and CI was green on its final head
  `f1e524fda`. The rulebook path check passed in the session's checkout and failed in CI. A
  build output, `docs/docs/_generated`, existed locally and not in CI's clean checkout.
  `0b536d21c` made the rulebook check and the comment check ask git instead of the disk. A path
  `.gitignore` covers counts as generated and passes on every checkout. CI still failed,
  because `git check-ignore` matches the directory-only rule `docs/docs/_generated/` against the
  bare path only while the directory exists. `16734c9b6` makes `code_references.generated()`
  ask with a trailing slash too. Its planted test now checks a missing directory,
  `kernels/target`, and no longer creates `_generated` mid-suite. Both commits changed
  `tests/code_references.py` and `tests/test_docs_consistency.py` only. The commits do not say
  whether the fast suite ran locally after them.

- **2026-11-21** — closed, every task ticked. A comment, docstring or rulebook that cites
  code, a file or a test the tree no longer has now fails CI with the citing file and line.
  The always-loaded rulebooks have byte budgets read from the base, so a change cannot raise
  the limit it is measured against, and a raise is a change of its own that CI warns about.
  The four version histories (1199 lines, 64 % of `schemas/common.py`) now live in
  `docs/contracts/`, with a test that fails a bump carrying no note. The sweep found 36 stale
  citations in `src` and 2 in the rulebooks, and fixed every one. What still passes unseen: a
  plain backtick name that is not a module path (``FooError``), and any comment whose
  reasoning or quoted number has gone stale while its names resolve.

  *Done*, in task order:
  1. The histories moved word for word (a word-level comparison of the removed comment text
     against each new file matched exactly) to `docs/contracts/{schema,report-thresholds,
     indexing-thresholds,project-format}.md`. The rule above each constant names its file.
     `tests/test_capabilities.py::test_every_contract_bump_carries_its_note` fails when the
     highest version an entry's lead names is not the constant's value. The manual's
     compatibility chapter and `/pr-review`'s sync paragraph point at the files. The
     events, textdoc and grammar contracts keep their few-line notes beside the constant.
  2. `tests/code_references.py`: role targets, dotted rietx literals, repo paths and test
     IDs, over every `#` block and string statement in `src/rietx`. Two resolution steps
     beyond the Context's four, each a measured gap: a top-level name of any rietx module
     (a role in a module that does not import the class it names), and a variable-style
     literal (``model.y_obs``) whose parts are all rietx class attributes. A relative lookup
     now tries the submodule import before the namespace, because `rietx.refine` the
     function shadows `rietx.refine` the module: that one gap was 72 of the first run's 111
     literal misses.
  3. The sweep. First run 193 misses; resolver gaps fixed to 49; 36 rewritten in `src`, 9
     foreign paths and one recipe key allowlisted with reasons. Every Context pointer is
     fixed, including the plain-name ones the resolver does not cover (`AgentError.details`,
     `_known_plan`, `MultiRefinement.fit`, `_disagreement`, `_outline`,
     `test_moment_path_is_clean_by_design`, the wrapped `SEED_TILT` role).
  4. `tests/test_code_references.py` and the lint step `python -m tests.code_references
     --delta`.
  5. `test_gui_rulebook_paths_resolve` became `test_rulebook_paths_and_names_resolve`, over
     13 rulebooks. Measured before fixing: 24 misses, of which 2 were real
     (`profiles/fcj.py` in the root rulebook, my own renamed test in `gui/CLAUDE.md`), both
     pointer fixes, neither in a clause WP-2009 rewrites. The other 22 were checker gaps
     (placeholders such as `vX.Y`, runtime directories, `report.regions`-style names).
  6. `tests/narration_count.py`; no CI step.
  7. `tests/rulebook_limits.py` replaces `SIZE_CAPS`; the table and its line diary moved
     verbatim to `docs/milestones/process.md` § The caps diary.
  8. Planted breaks for each check, in the three test files.

  *Settled by Claude* (each listed in the PR for the maintainer):
  - An allowlist entry new against the base fails unless the change touches nothing else,
    under task 7's raise rule. The WP said "fails" and named no route for a legitimate
    entry. The alternative, a report only, would let a stale rietx name be allowlisted
    inside the change that stales it.
  - The change that adds `code_references.py` or `rulebook_limits.py` passes its own lint
    step, because the base has no table to compare with. The diff shows every entry.
  - Ceilings use the last 30 days of `main`'s merges, the window `skill_caps` measured its
    gap over. The whole history's worst days (6 781 B on CLAUDE.md, 14 463 B on
    `gui/CLAUDE.md`) were consolidation days with no cap in force. Files no merge grew in
    the window (AGENTS.md, `src/rietx/gui/CLAUDE.md`) take `REFERENCE_GAP_BYTES`, 2 000 B.
  - A new rulebook enters at budget 8 000 B and ceiling 10 000 B.
  - Plain backtick names were left unchecked: 193 on 2026-11-21, mostly TOPAS keywords,
    GSAS-II functions, vendor fields and formulas, so a check needs an allowlist of about
    150 foreign names first.

  *Measured* (`[dev]` venv, macOS arm64):
  - `test_every_comment_citation_resolves`: 12-14 s alone and 28 s in the loaded fast run
    below, most of it importing every rietx module. It stays in the fast tier, because a
    stale citation is caught on the push that makes it; the reason is in its docstring.
  - Narration at this branch's HEAD, blocks per pattern: until WP 38, since WP 56, before
    WP 61, was … until 13; 158 blocks in all (159 at `origin/main` before the branch).
  - Rulebook bytes pinned as budgets: CLAUDE.md 86 787, ROADMAP 52 042, `gui/CLAUDE.md`
    45 159, io 55 732, indexing 27 747, tests 19 733, AGENTS.md 2 009,
    `src/rietx/gui/CLAUDE.md` 155. 30-day worst days of growth: 418, 1 636, 693, 1 344,
    1 503, 306 B.
  - Fast suite on the final tree: 15112 passed, 442 skipped, 32 xfailed, in 34:52, while two
    other sessions ran suites. The 28 added test functions are 62 cases, and they replace 2
    (`test_gui_rulebook_paths_resolve` and the old line-cap test), so the net is +60 cases.
    `added_test_times` gives 101.9 s over the added tests in this one loaded run:
    `test_code_references.py` 57.7 s, `test_docs_consistency.py` 43.4 s (the rulebook checks),
    `test_rulebook_limits.py` 0.7 s. No full suite: nothing here moves a measured number.

  *Review* (`/code-review high --fix`): five findings, four fixed in one commit. Three source
  comments still pointed at the moved histories and now name their `docs/contracts/` file.
  `skill_caps.changed_files` returned an empty set when `git diff` failed, which would have let a
  raise pass as a change of its own; it now raises. The narration counter now survives a file
  that will not tokenize. A wall clock quoted as one figure became a range. Skipped: for a rietx
  module that will not import (an optional backend), the resolver accepts any attribute after
  the first; walking class bodies by AST is more code than that case earns.

  *Generality*: not dispatched. `_audit.py` is untouched and nothing here is a heuristic that
  acts on a fit.

  *Gotchas*: a budget at today's bytes closes every rulebook to growth, so the next rule
  added anywhere pays with a cut. That is the WP's intent, and WP-2009 re-pins downward.
  `docs/contracts/` is outside the reference check on purpose, since its notes name
  removed things.

  Next: none here. WP-2236 (filed at close, P4, not before 2027-01-02) runs the narration
  counter over six weeks of `main` and brings a gate-or-drop decision. WP-2009 re-pins the
  budgets when its content pass lands.

- **2026-11-21** — created. Fold check: WP-2009 owns the rulebooks' *content* (findings out,
  rules rewritten), and an Inherited entry there points here. No open WP owns a check on code
  comments, or on how the size limits are enforced. A second reviewer read the draft and
  checked it against the tree. The resulting revisions were these:
  - Limits are read from the base the way `audit_delta.py` reads it. CI has no `origin/main`.
  - Raises are made visible, not prevented.
  - Allowlist names are checked against the base instead of a count.
  - The task order is resolver, sweep, then test.
  - Repo paths and test IDs joined the check, after the reviewer found 4 of them dead.
  - The reviewer found WP-1117's rule keeping the changelogs in comments. The maintainer
    then ruled that they move out (ruling 5).
  - The block-length cap and the CI narration step were cut.

  Next: the version histories out, then the resolver script and its first full list of
  misses.
