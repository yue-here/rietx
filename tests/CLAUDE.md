# CLAUDE.md — tests/

Scope: running, timing, counting and budgeting the test suite, and the CI
that runs it. The headline rules live in the root CLAUDE.md (they govern how
any session quotes numbers); this file holds the operating detail. The
measurement diary that taught these rules is archived in
`docs/milestones/v1.0.md` § Appendix.

## Running

**The ladder — cheapest rung first, and the expensive one fires once.** A
session's test bill is set by *how often* the top rung runs, not by how much is
tested (WP-1070's difference was one whole-suite run launched mid-edit and
therefore repeated; `docs/milestones/process.md`):

1. **The files you just touched** — seconds, continuously, while writing.
2. **The fast suite** (`-m "not slow"`, 3-5 min) — before a substantial commit,
   and once before the handover. This is the gate.
3. **The full suite** (~15-30 min) — **once, on the final tree**, and only when
   the change can move a measured number. A docs-only, test-only or GUI-only
   WP does not run it at all. Never launch it while still editing: the tree it
   collected is the tree it reports on.
4. **Re-measuring `main`** — don't. That is CI's job (§ CI), and a local
   baseline costs a second full run to answer a bookkeeping question.

**Rung 3 is exclusive across sessions**, because several share this machine (WP
work and one `/pr-review`) and two suites at `-n auto` put twice the workers on
the same cores. Not a timing question: § Budgets in tests has load turning a
real-data row's *answer*. So look before starting one — `ps aux | grep -c
'[p]ython -m pytest'`, with `lsof -a -d cwd -p <pid>` for which tree and
`ps -o etime= -p <pid>` for how long — and **observe rather than reserve**,
since a lock adds a release to forget and a stale window to wait out while a
process list cannot go stale. **`ps`, not `pgrep -f`**: `pgrep -f` misses live
suites, inconsistently between sessions (`docs/milestones/process.md`), and a
check that silently finds nothing returns a false all-clear every time, which
is worse than no check. **Count trees, not lines**: `grep` reads the command line, so a
background launch matches its own zsh wrapper too and `-c` says 1 on an idle
machine. **A ghostshift runner queues instead** (WP-2077): it starts a full
suite only through ghostshift's `bin/serial.py` (in claude-config), which holds
a machine-wide lock and also waits while `ps` shows a `python -m pytest`
outside it. A `ps` line naming `serial.py` is a queued waiter, not a running
suite. **Found one: wait or defer, and never measure anyway** — it would not be
quotable (§ Quoting numbers). Checked in `/pr-review` step 9 and `/wp-handover`
steps 7 and 10; rungs 1-2 skip it, being cheap to repeat.

- `-n` is deliberately **not** in `addopts`: a bare `pytest tests/x.py::y`
  stays serial, so `-s` and pdb keep working. `--dist loadgroup` is not
  optional — it honours the `xdist_group` marks that keep a shared fixture on
  one worker, and `conftest.pytest_configure` refuses a run without it.
- Fast unit/property tests always; real-data acceptance marked
  `@pytest.mark.slow` (`test_acceptance_nac.py`, `_srm660c.py`, `_fap.py`,
  `_capillary.py`, `_indexing.py`); what each dataset may be asked is § Key
  test data below. Every test refinement also writes obs/calc/diff
  PNGs to `tests/output/` (gitignored) for visual inspection — Rwp hides
  locally-bad fits. **The indexing suite draws through
  `tests/indexing_gallery.py`** rather than calling the renderers directly: it
  writes a JSON sidecar per dataset (one writer per file, because these rows
  span five xdist groups), and `python -m tests.indexing_gallery` turns those
  into the scoreboard and a summary page. Declare a new dataset in its
  `DATASETS`/`TRUTHS` tables — `draw()` refuses an undeclared stem, because a
  silent skip is a dataset in the suite and not in the summary.

## Key test data, and what each dataset can prove

Provenance and every reference value are in `tests/data/README.md`; what a
dataset may be *asked* is here, because a claim referenced to the wrong one is
green and worth nothing.

- `11BM_NAC.fxye` — APS 11-BM synchrotron, λ=0.4139090 from the .prm; NAC +
  CaF₂ impurity; acceptance expects a≈10.2513, Rwp<0.12. Internal consistency
  (Le Bail vs Rietveld) and the wavelength calibration, not a certificate.
- `nist_srm660c_100a.cif` — NIST LaB6 certification data, CuKα doublet +
  graphite analyzer; fits the `…_meas` block with zero fixed / displacement
  refined; expects a≈4.15678±2e-4, Rwp<0.10. The **absolute** anchor.
- `FAP.XRA` + `FAP.EXP` — GSAS-II LabData tutorial fluorapatite; the `.EXP` is
  GSAS's converged fit and supplies both the reference values and the protocol
  the test mirrors. **Cross-code consistency** check (±300 ppm), not truth.
- `qarr/*.prn` — IUCr CPD QPA round-robin patterns (samples 1a-1h, 2, 4 + six
  pure phases; 2-column ASCII, Cu Kα doublet, graphite diffracted-beam mono).
  QPA truth is the **weighed composition**; tolerances referenced to the
  published participant spread, never to σ(W). `corundum.prn` doubles as the
  SRM 676a cell-anchor specimen (c/a is the certificate-grade assertion;
  absolute axes carry lab d-scale systematics).

## Shared fixtures and xdist groups

A refinement that two suites both need is computed once, in
`tests/conftest.py` (`sample1_results`, `srm660c_baseline`), and **every
consumer must carry the matching `@pytest.mark.xdist_group`** — otherwise a
second worker rebuilds the whole fixture and the sharing costs more than it
saved. Same rule one scope down: a module fixture several tests share pins
its module (`nac`, `capillary`, `srm660c`, `stephens-brucite`,
`indexing-consensus`, …). A wrong `--dist` is refused (§ Running); a missing
mark is not, so its check stays a `--durations` scan for a setup appearing twice.

**One dataset, one group**, and runtime is set by the longest *group*, not by
total work — splitting a group is the only way to go faster, and un-sharing a
fixture to do it just moves the cost; a group whose members share no fixture
splits for free. A group ordering is a measurement with a shelf life (v1.0
record § Appendix): re-read the `--durations` list rather than the last
session's sentence about it.

## Guards that go quiet instead of red

A guard asserting that something is *absent* fails safe only if you know it can
still fail. Three ways one stops asking while staying green (WP-1062, WP-1426):

- **It pins a copy of a string that lives somewhere else.** A test filtering
  output on the literal text of a `.gitignore` rule passes and tests nothing once
  one copy is renamed. Assert the *shape* that carries the meaning — a rule
  beginning `!` is a negation — never a second copy of the line.
- **The tool answers from somewhere you did not mean.** `git check-ignore`
  consults the index first and answers for a **tracked** file without reading
  the ignore rules at all. `--no-index` is what makes it ask.
- **The instrument does not reach the thing you aimed it at.** A `layout-shift`
  entry fires when an element's *box* moves, and a chart repaints canvases inside
  one, so a moved plot area scores 0. The *page* reads the observer, the
  *picture* each uPlot pane's `over`, and a stillness test needs both. Colour
  likewise: a series' `stroke` is what it was handed (WP-1438), and what it
  painted is `RECORD`'s log of every stroke and fill (`test_watch_browser.py`).

The check all three share: make the guard fail on purpose once, and confirm the
failure message is the one you expected.

## Four eval protocols, and they pool with nothing of each other's

`tests/eval_report_agent/` asks whether an agent **reads** a FitReport it was
handed; `tests/eval_agent_surface/` (WP-1110) which **surface** it reaches for;
`tests/eval_skill_placement/` (WP-1338) whether a **routing** change loses
reads; `tests/eval_skill/` (WP-1905) whether a **body** change keeps outcomes.
What they share is the discipline, the part to copy into a fifth: **register the
round before running it**, never rewritten afterwards; enforce the condition in
a **shim** rather than in the prompt; fix the read-outs in advance (WP-1303),
and report a cell that came back **split** at N = 2 as split.

A shim has to be **invisible to its subject**: a tracer without
`functools.wraps` sent an agent reading source for a signature (WP-1110).
And **check the condition reached each cell**, off its transcript: a user-level
skill shadows a workspace one of the same name (WP-1338's § Amendment 1.1), and
one on the task's subject picks the route, so launch with `--setting-sources
project,local`; the user `CLAUDE.md` still loads (WP-1504's § Amendment 1.1).

## An eval's expected answer is a measurement, not a definition

A scored row asserts what the *data* supports, and that needs checking as much
as any guard does — **before** the grid is read, since afterwards a correction
cannot be told from moving the goalposts. Fitting each rival alone costs
seconds and settles it, where a wrong expected answer costs a whole round
(WP-1059; `tests/eval_report_agent/PROTOCOL.md` § Episode validity).

## Budgets in tests

**A wall-clock budget inside a test is a runaway guard, never a timer.** Any
test whose serial time is a large fraction of its declared budget is a load
sensor pretending to be an assertion — it passes serially and fails under
`-n auto` for reasons unrelated to what it asserts. Measured instances (v1.0
record § Appendix): `BUDGET_SECONDS` in `tests/test_indexing_engines.py`;
**the budget a test depends on may be one rank down, in the library**
(`DOMINANT_ZONE_PROBE_SECONDS`); a real-data row that reported a *different
centring* under load (`REAL_DATA_BUDGET_SECONDS`, still binding on the Linux
nightly); and completion assertions
generally — "some system did not finish" is a statement about machine load,
not the data, and belongs as "every system searched reports whether its
domain was exhausted".

**The check to run before landing any row with a budget: compare its serial
time with its declared budget; if the budget is not several times larger,
the assertion is a load sensor.**

**The numeric twin: a tolerance between two independently-converged fits
senses solver termination unless it carries the measured cross-platform
spread** — a TRF stopping point moves with platform libm while the physics does
not. **Measure that spread on the quantity the assertion names, not on its
neighbour**; a re-run is bit-identical and proves nothing (`test_acceptance_srm676a.py` §3). A pass margin under ~10x
still smells.

**The honest-budget rule and the CI budget pull against each other, so expect
to pay in scope.** When a budget fix makes something slow, narrow what is
searched — never the budget, never a silent cap (the pure phases' declared
`systems_searched`; v1.0 record § Appendix). **Where the budget
still binds, an *order* waits for a finished search** (WP-1449): a cut search's
ranking depends on load.
`_skip_unless_finished` reads each unit's clock against the recorded budget,
never `search_complete` (a cap sets it too); a *found* claim stays live.

**The fast tier grows by its tail, so its guard is a report** (WP-1506): each
added test's seconds and each file's total (`python -m tests.added_test_times`),
and one joining the tail says why it is not `slow`. **Local seconds understate a
CI leg**, so it reads CI's `junit-*` file when the branch has one (WP-1547).

## Quoting numbers

- **Do not pass `-q` yourself**: `addopts` already carries one, so `-q` on the
  command line makes it `-qq`, and at `-qq` pytest prints **no summary line at
  all** — the run looks clean, exits 0, and the passed/skipped counts you came
  to measure are simply absent. Use the root CLAUDE.md's commands verbatim; the
  ones that do show `-q` are single-file selections where the count is not the
  point.
- **Quote wall clock as a range, never as a figure**: machine state moves it
  further than most changes do (v1.0 record § Appendix); compare runs, not
  records. **Say whether another session was running** — and check first
  (§ Running), which makes "alone" a fact rather than an assumption.
- **Memory on macOS is the physical footprint**: compressed pages leave RSS
  (WP-1924). Compare peaks at equal work, since a loaded run under a
  wall ceiling searches less (`tests/repro_780.py`: `memory_bytes`, `--cpu-clock`).
- **Quote the extras with any count**: `[jax,torch]` turns most skips into
  passes, so a count needs its venv, and a traced-path change needs them
  installed or its cross-backend rows skip green (WP-1953).
- **A pass count cannot show a module that never ran.** A collection error is
  one `error` line beside five thousand passes, and every case in that file
  stops being evidence without one of them going red (WP-1439). What shows it
  is the **total**: compare passed+skipped across the matrix, never pass
  counts, which move for every legitimate skip.
- **A test that pins a number declares which *path* produced it**, not only
  which settings — the dispersion rule (root CLAUDE.md) one rank wider, because
  the compiled tier is a second default that changes arithmetic (WP-1115). It
  is on unless switched off, so a golden or a bit-identity assertion says
  `compiled.set_enabled(False)` (or `True`) rather than inheriting. The
  signature of getting this wrong is a test that **passes on darwin/arm64 and
  fails on Linux**, whose C library `exp` the symmetric kernels call (x86-64's FCJ
  kernels call SLEEF's, WP-1940) and numpy does not. `conftest.py` also asks for one
  kernel thread per xdist worker, so a wall-clock budget is not a function of the worker count.
- **A worktree needs its own venv, and quote which one you used.** The main
  checkout's `.venv` resolves `rietx` to the *main checkout's* `src`, so a
  worktree session running it measures the wrong tree — green, and about code
  it did not change. Build one per worktree (root `CLAUDE.md` § Commands has the
  command, `--python` included), and say `[dev]` vs `[dev,jax,torch]` with every figure.
  **Name the interpreter when you build it**: `uv pip install` prefers an
  inherited `VIRTUAL_ENV` over the `.venv` in the working directory, so that
  command run inside a fresh worktree can install *the worktree's source into
  the main checkout's venv* — which points another session's tests at this
  session's tree, silently and in the direction the rule above does not cover.
  `uv pip install --python <worktree>/.venv/bin/python -e ".[dev]"` cannot;
  after either, check `python -c "import rietx; print(rietx.__file__)"` in both.
  The same discipline extends to the **tree**: when `main` has moved under a
  branch, that branch's counts are not the merged tree's and the two parents'
  additions cannot simply be summed — re-measure after the merge.
- **Say which numbers moved**: after adding N tests, passed+skipped must
  move by exactly N **in the fast selection**, and a new skip is not a new
  pass (WP-1029). For the **full** selection quote
  green plus a delta consistent with the fast one; both ends of an exact check
  there costs an hour of machine time, and the baseline it needs is CI's job
  (§ Running, the ladder). The vitest suite is counted separately, by the same
  rule (v1.0 record § Appendix).
- **`--collect-only` undercounts by one per module-level `importorskip` that
  fires** (WP-1031): a module skipped at import is **one skipped test**
  in the run summary and **zero items** under `--collect-only`. Which
  modules fire depends on the venv (jax, torch, the playwright browser files
  and the rest `conftest.pytest_make_collect_report` names). So
  `collected = passed + skipped − (module-level skips that fired)` — quote
  whichever you measured, and say which.

## CI

CI runs the same commands (`.github/`). Per push and per ready PR (`ci.yml`):
ruff + the fast suite on 3.11 and 3.14, Linux, in four shards each that keep
every file and `xdist_group` whole (`shards.py`), plus a `[dev,jax]` job of the
cases reaching jax (`jax_cases.py`, whose guard names the fix for a case it
misses). A stale `shard_times.json` costs balance, never a test. **A PR changing
only the planning set runs the tests that read it instead** (the `docs` job,
WP-1506), so a new test reading that set (`PLANNING` in `ci.yml`) joins its
list, or a docs-only PR skips it until the nightly. Branch protection requires
`lint` and `ci-ok`, the job that says whether the suite `changes` chose passed.
**A draft PR runs ruff alone**, the matrix waiting for `gh pr ready` (`ci.yml`'s
header). Nightly (`nightly.yml`): the full suite `[dev,jax]` on Linux (3.13, not
a gate), the fast suite on 3.12 and 3.13 and on Windows (the release pre-upload
gate, `docs/RELEASING.md` step 4), macOS fast plus the informational goldens
step, and `[torch]`. **Read spend from the Actions usage page or `gh run list`,
never from comments or this file**: a written total rots (WP-1060).

Two consequences for local work:

- **The bit-identity goldens are pinned to `darwin/arm64`** (`GOLDEN_PLATFORM`
  in `tests/test_backend_shim.py`) and *skip* elsewhere: Linux x86-64 diverges
  by a libm and summation-order difference (WP-1002), so the gate is asserted
  where it was captured rather than loosened to a tolerance that could not
  distinguish it from a real change.
- **`tests/.jax_cache` is why the jax rows feel free locally**, but caching it
  in CI was measured and does *not* help (WP-1002): jax's persistent cache
  holds only XLA compilations above a time threshold, while per-process tracing
  and lowering are paid every run.
