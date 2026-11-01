# Contributing to rietx

This page is the mechanical half of contributing: setup, the test ladder,
the style rules a change is held to, and licensing. The design rules live
in the `CLAUDE.md` rulebooks (see [AGENTS.md](AGENTS.md)); they are written
for agents and bind humans equally.

## Setup

```sh
uv venv --python 3.12 && uv pip install -e ".[dev]"
uv pip install -e ".[dev,jax,torch]"    # + optional backends
```

A git worktree needs its own venv: the main checkout's `.venv` resolves
`rietx` to the main checkout's `src`, so tests in a worktree would measure
the wrong tree.

## Tests and lint

```sh
.venv/bin/python -m ruff check src tests examples                    # must be clean
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"    # fast suite, ~1-3 min
.venv/bin/python -m pytest -n auto --dist loadgroup                  # full suite, ~15-30 min
```

- `--dist loadgroup` is not optional: it honours the `xdist_group` marks
  that keep a shared fixture on one worker. Plain `--dist load` silently
  refits the expensive fixtures, so `tests/conftest.py` refuses a parallel
  run without it. `-n 0` is how to ask for a serial one.
- Run the fast suite before proposing a change; the full suite once, on the
  final tree, when the change can move a measured number.
- Quote any test count with the extras installed and the platform
  (`[dev]` vs `[dev,jax,torch]`; skips convert to passes with the extras).
  Quote wall clock as a range, never as a single figure.
- GUI frontend: `npm --prefix gui ci && npm --prefix gui run build`, then
  `npm --prefix gui test && npm --prefix gui run check`. The built dist
  under `src/rietx/gui/static` is committed — rebuild it in the same change
  that edits `gui/src`.

## Style essentials

The enforceable core; a test backs each of these, so a PR that skips one
fails before review reads it.

- Every physics function cites its reference (author, year, journal) in its
  docstring, and documents conventions by physics, never by letters — codes
  disagree on letter assignments (GSAS and FullProf swap the size/strain X
  and Y).
- Units: angles in degrees; Caglioti U, V, W in deg²(2θ); Biso in Å²;
  wavelengths in Å.
- Parameter paths are dot-separated and glob-matched with fnmatch — no
  brackets in paths.
- Never spell the distribution name, a format token or the state directory:
  import it from `src/rietx/_about.py`. The audit test greps only old
  names, so a freshly hardcoded current name is invisible to the suite.
- The manual is guarded: every dotted name resolves against the live
  package, every python block parses and executes or states why not, every
  bibliography entry is cited, and every displayed equation carries a
  source symbol that imports. A new public name fails the coverage
  partition until it is documented, excluded with a reason, or deferred.
- The manual (`docs/docs/`) is also read by Vale, in CI's lint job:
  British spelling, Microsoft's style guide as the base, and the house rules
  in `docs/vale/rietx/`. An error fails the job. Run it locally with
  `vale sync && vale docs/docs` (Vale 3.24, installed separately, e.g.
  `brew install vale`). A word Vale does not know goes in
  `docs/vale/terms.txt`, then `python docs/vale/terms.py` rewrites the
  accept list.
- Worked examples live in `examples/`, are included verbatim by the manual
  and executed by the suite. Never write a second copy of a walkthrough.
- A new correction ships with a record field or a diagnostic stating what
  it changed — never an Rwp comparison as its evidence.

## A heuristic needs its tier

Every decision rietx makes on its own has a row in `src/rietx/_audit.py`,
with a tier and the evidence for it. A new diagnostic code needs a row. So
does a new field on a result record, a module-level number in a directory
the table walks (`_audit.WALKED`), a default at a seat it declares
(`_audit.DEFAULT_SEATS`), and a new `suggestion=` text.
`tests/test_audit_table.py` fails until the row exists, and prints it with
the tier and evidence left for you to fill in.

The tiers are defined in `docs/milestones/generality.md` § The rule. Tier 1
is physics or arithmetic. Tier 2 is established practice: a citation that
validated it, or the same action taken by default in one of the seven
programs the rule names (GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD and
EasyDiffraction). Tier 3 is rietx's own choice. `invariant` is an efficiency setting
that cannot change an answer, and it names the test asserting its margin.
`caller` is an action that runs only when the caller turns it on. A code,
an action or a default also states its kind of ambiguity, from
`docs/DESIGN.md` § Rules, 1.

A name new to the table may not enter at `unaudited`. CI's lint job fails a
pull request that adds one, and prints every row the pull request adds,
changes or deletes. At review the `generality-review` agent drafts the case
against each of those rows, and the case for any action the change removes
or leaves to the caller. A tier-3 row, and a tier-2 automatic action, waits
for the maintainer's dated ruling in its `approved` field. The maintainer
may write that field into your branch.

**Land the machinery first.** Machinery is what a caller operates: a model,
a fit, a reported quantity. A heuristic is a choice rietx makes for the
caller. A pull request that adds a tier-3 row waits on the maintainer's
ruling, so a machinery pull request adds none. A number the machinery needs
is physics or arithmetic (tier 1), established practice (tier 2), or a
required argument on a verb no default path calls (`caller`). The tier-3
default follows in its own pull request. Adopted 2026-10-30 from #1224.

## The agent skill

`docs/skill/rietx/` is what an agent reads before driving the package on real
data: `SKILL.md`, read whole, and `references/`, one file per lookup or per
task shape, loaded when the body's routing table names it. It is the third
place a change can need to land, beside the code and the manual, and the one
that takes what you *learned running the package* rather than what you
changed in it. Two committed copies, `.agents/skills/rietx/` and
`.claude/skills/rietx/`, are regenerated from it and must stay byte-identical.

**Where a rule goes, cheapest first.** Every feature so far added to the body,
and the body is read whole by every session that loads the skill. So a
feature's guidance goes to the first of these that can hold it.

1. **The package's own output.** The `suggestion` of the `Diagnostic` that
   fires, or the entry in `src/rietx/help.py` for a name. It costs nothing
   until the output appears, and it matches the installed version. The
   installed skill is a copy, and an upgrade can leave it stale.
2. **A reference row keyed by a name the agent already holds**: a diagnostic
   code, a verb it is about to call, a file extension, a result type. A
   diagnostic code, a gate or an action needs its row in a diagnostics or
   abstention table, and `tests/test_docs_consistency.py` fails until it
   exists. Evidence too long for a suggestion goes in the code's row. A
   measured surprise about one fit goes in `references/surprises.md`.
3. **A routing row**, only for a task *shape* that no name identifies: a
   series, a batch of candidates, a magnetic phase. The shape gets its own
   file under `references/`, numbered under the body section it specialises
   (`9b` series, `9c` batch). One routing row reaches it, and its *When*
   column names the situation, never the feature. A new shape is a new file:
   copy the three-paragraph header of an existing one (the title, "Load it
   when …", the provenance line), which the tests pin.
4. **The body**, only for a rule every fit needs, and paid for by a cut in
   the same change.

A rule for changing the package, not for running it, goes in a `CLAUDE.md`.

**Sizes.** `tests/skill_caps.py` gives every skill file two limits. The
*ceiling* is where an agent stops being able to read the file in one call. The
*budget* sits below it and fails only a change that grows the file past it. The
body's budget is the specification's 5 000 tokens, and the body is over it, so
any body sentence is paid for by a cut. A reference file over its budget takes
no growth either: split it on the criterion its cap comment records. CI prints
each changed file's delta and headroom on every pull request, drafts included,
and `python -m tests.skill_caps` prints the same table locally.

**Writing a row from runs.** A reference that collects rules from runs
declares in its provenance line that every row carries its evidence, and each
row then reads: the rule as one bold imperative sentence, numbered under the
file's section; two to four sentences on what was measured — the dataset or
episode, N, the number that decides; and a closing tag,
`*(Measured: <the run>)*` or `*(Hypothesis: <what would decide it>)*`.
`references/batch.md` § Writing a row is the worked form. If an agent is
writing the rows from your logs, hand it that section and this one: every
number in a row comes from the log, and anything the log does not decide is a
Hypothesis row, never a softer Measured one. Before a row, ask whether it
holds for one fit alone — then it is the body's or §8's, not the shape's.

**Rows measured on data you cannot share** are admitted, because the package
has to be tested on data it does not ship. The tag then names a *corpus* the
file declares once in its provenance line, spelled the same way in every row,
so a reader knows before the first row which tags they can follow and which
they must take on trust — a private run that reads like a citation is the
thing this rule exists to stop. Nothing else relaxes: the numbers still come
from the log, and a scientific magnitude derived from unpublished data stays
out. The line is what the row is about: what the *run* did may be quoted —
counts, rates, wall clock, a ratio of fit qualities, which is what a rows file
is made of anyway — and what the *specimen* is may not: a cell, a phase
fraction, a domain size, a transition temperature, and a ratio of two of those
is still one of those. Quote the shape, or a published figure, instead, which
is where the lesson was anyway.

Then, in the same change:

```sh
.venv/bin/python -m pytest tests/test_skill.py tests/test_skill_cli.py tests/test_docs_consistency.py
.venv/bin/rietx skill --install . --copy      # re-sync the two committed copies
```

The first refuses a row without its tag, a private tag that does not name its
file's corpus, a reference without its header, a link that does not resolve, a
field name no type carries, a code span a table cell cuts, a file over its
ceiling, and a change that grows a file past its budget. The second
regenerates the two copies.

## Licensing

MIT. Port code only from permissively licensed sources, and update
`ATTRIBUTION.md` in the same change. BGMN, Profex and xrayutilities are
GPL: concepts only, never code. TOPAS and FullProf are closed: papers only.

**Data you cannot publish.** Name a dataset in the repository only if it
is a public download or has a peer-reviewed citation. This holds in code
comments, docstrings, tests, the manual and release notes. It covers a
sample or compound name, a run or proposal number, a file name, the
instrument and conditions of the experiment, and any property of the
specimen read off a refinement. A number the code depends on may still come
from private data. Describe the data by its kind ("a private
constant-wavelength neutron scan") and keep the number. The skill's rows
draw the same line (§ The agent skill).

## Maintainer-only machinery

Parts of `CLAUDE.md` serve the maintainer's own workflow and do not bind an
external contribution: the ROADMAP/WP session protocol and its handover
logs, the memory conventions, and the references to a local paper corpus.
If a rule points at something you cannot have (a local corpus path, a WP
file's history), say so in the PR rather than guessing around it.

Two of those files are the maintainer's to write:

- `docs/ROADMAP.md`, which says what is scheduled and in what order.
- `docs/wp/NNNN-*.md`, a work package. Its header lines place it in
  `docs/wp/README.md`, the WP index, which
  `python3 .claude/hooks/wp_index.py` generates. A test fails while the index
  is stale, so a WP file lands together with its row.

Adding to the handover log of a WP whose work you did is welcome. That log
is the record of what you measured and where you stopped, and it belongs in
the same change as the code. In the same file you may tick the tasks your PR
completes, move its `Status:` line, and record the decisions your work made.
Those stand as you wrote them. Closing the WP stays the maintainer's, in the
handover after your PR merges.

**Claiming one is welcome too.** Before starting scheduled work, open a draft pull request
that sets that WP's `Status:` line to `🔄 <date> — claimed by @you` and
regenerates the index with `python3 .claude/hooks/wp_index.py`. It
stops two people spending a week on the same work: nobody can see a claim that
lives only on your own machine, so a draft PR is the announcement. Mark it
ready when the work is. If you find a WP already at 🔄, or a draft PR open on
it, ask in the issue before starting rather than racing.

## Proposing something that is not scheduled

Open a [design proposal][proposal] and write the design there. A proposal
does not need an implementation, and unscheduled design does not go into a
WP file: the maintainer opens the work package when the work is scheduled,
and links back to the proposal. The design then exists in
one place at each stage instead of two that drift apart.

Proposals are read and answered, not queued silently. The answer may be that
the work sits behind a version fence in `docs/ROADMAP.md`, in which case the
proposal records why for whoever asks next.

[proposal]: https://github.com/yue-here/rietx/issues/new?template=design-proposal.md
