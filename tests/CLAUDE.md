# CLAUDE.md — tests/

Scope: running, timing, counting and budgeting the test suite, and the CI
that runs it. The headline rules live in the root CLAUDE.md (they govern how
any session quotes numbers); this file holds the operating detail and the
evidence. The measurement diary that taught these rules is archived in
`docs/milestones/v1.0.md` § Appendix.

## Running

**The ladder — cheapest rung first, and the expensive one fires once.** A
session's test bill is set by *how often* the top rung runs, not by how much is
tested (WP-1070 spent ~80 min and earned ~43; the whole difference was one
whole-suite run launched mid-edit and therefore repeated):

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
process list cannot go stale. **`ps`, not `pgrep -f`**: measured 2026-09-15,
`pgrep -f pytest` exited 1 against a live `pytest -n 4` that `pgrep python`
and `ps` both saw, and it is not stable between sessions — a check that
silently finds nothing returns a false all-clear every time, which is worse
than no check. **Count trees, not lines**: `grep` reads the command line, so a
background launch matches its own zsh wrapper too and `-c` says 1 on an idle
machine. **Found one: wait or defer, and never measure anyway** — it would not be
quotable (§ Quoting numbers). Checked in `/pr-review` step 9 and `/wp-handover`
steps 6 and 9; rungs 1-2 skip it, being cheap to repeat.

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
fixture to do it just moves the cost. A group ordering is a measurement with
a shelf life: "indexing does not set the wall clock" expired unnoticed at
~550–590 s against `stephens-brucite`'s 533 until a `--durations` re-read
caught it, and moving the LaB6 rows into their own `indexing-acceptance-lab6`
group was free because nothing in the group shared a fixture. Re-read the
`--durations` list rather than the last session's sentence about it.

## Guards that go quiet instead of red

A guard asserting that something is *absent* fails safe only if you know it can
still fail. Three measured ways one stops asking (the first two WP-1062, both
green for months; the third WP-1426):

- **It pins a copy of a string that lives somewhere else.** `test_gui_dist`
  filtered `check-ignore` output on the literal text of a `.gitignore` rule, so
  renaming the path in one file and not the other left it passing and testing
  nothing. Assert the *shape* that carries the meaning — a rule beginning `!` is
  a negation — never a second copy of the line.
- **The tool answers from somewhere you did not mean.** `git check-ignore`
  consults the index first and answers for a **tracked** file without reading
  the ignore rules at all; every file that test checks is committed, so the
  rules were never asked. `--no-index` is what makes it ask.
- **The instrument does not reach the thing you aimed it at.** A `layout-shift`
  entry fires when an element's *box* moves, and a chart repaints canvases inside
  one, so a stage boundary that moved plotly's plot area 19 px scored exactly 0.
  The *page* reads the observer, the *picture* each uPlot pane's `over`, and a
  stillness test needs both. Colour likewise: a series' `stroke` is what it was
  handed (a plotly tick row painted another, WP-1438), and what it painted is
  `RECORD`'s log of every stroke and fill (`test_watch_browser.py`).

The check all three share: make the guard fail on purpose once, and confirm the
failure message is the one you expected.

## Two eval protocols, and they pool with nothing of each other's

`tests/eval_report_agent/` asks whether an agent **reads** a FitReport it was
handed; `tests/eval_agent_surface/` (WP-1110) asks which **surface** an agent
reaches for when handed files and a job. Different episodes, answer contracts
and scoring, so a cell in one is comparable to nothing in the other and neither
version number governs both. What they share is the discipline, and it is the
part to copy into any third: **register the round before running it**, never
rewritten afterwards; enforce the condition in a **shim** rather than in the
prompt; fix the read-outs in advance. The second one earned that last rule
twice over: its headline result (no cell called the JSON surface it was about,
deleted in WP-1303) was not one of its read-outs, and its `pointed` cell came
back **split** at N = 2, reported as split, not resolved.

A shim also has to be **invisible to its subject**. Round 1.0's tracer wrapped
without `functools.wraps`, so `inspect.signature` showed the wrapper and an
agent went reading source to recover a signature.

## An eval's expected answer is a measurement, not a definition

A scored row asserts what the *data* supports, and that needs checking as much
as any guard does — **before** the grid is read, since afterwards a correction
cannot be told from moving the goalposts. Two of WP-1059's three rows failed
it, both expecting `ambiguous` where the data in fact chose: one converges to
truth under the default plan, the other's one-parameter rivals differ by χ²
4.075 against 3.489 (5332 points; the R² 0.9977 saying otherwise is geometric).
Fitting each rival alone costs seconds; that round cost 1.7 M tokens. Both:
`tests/eval_report_agent/PROTOCOL.md` § Episode validity.

## Budgets in tests

**A wall-clock budget inside a test is a runaway guard, never a timer.** Any
test whose serial time is a large fraction of its declared budget is a load
sensor pretending to be an assertion — it passes serially and fails under
`-n auto` for reasons unrelated to what it asserts. Four measured instances:
`BUDGET_SECONDS` in `tests/test_indexing_engines.py` (180 s against an
~85–105 s search, broken by adding one unrelated module); **the budget a
test depends on may be one rank down, in the library**
(`DOMINANT_ZONE_PROBE_SECONDS`, a hard-coded 10 s against a 4.3 s serial
cost); a real-data row that reported a *different centring* under load
(73 s serial, 258 s loaded, 60 s declared — `REAL_DATA_BUDGET_SECONDS`, now
300 s and still binding on the Linux nightly); and completion assertions
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
neighbour**: sized on `a` at 2.5e-6, the same bar fired 12 days later on `c`,
7x wider and bit-identical across two runs, so a re-run proves nothing. Every
number: `test_acceptance_srm676a.py` §3. A pass margin under ~10x still smells.

**The honest-budget rule and the CI budget pull against each other, so expect
to pay in scope.** When a budget fix makes something slow, narrow what is
searched — never the budget, never a silent cap (the pure phases' declared
`systems_searched`, 15:33 → 8:09; v1.0 record § Appendix). **Where the budget
still binds, an *order* waits for a finished search** (WP-1449): finished,
brucite ranks a supercell first, and cut, the truth in one run of two.
`_skip_unless_finished` reads each unit's clock against the recorded budget,
never `search_complete` (a cap sets it too); a *found* claim stays live.

## Quoting numbers

- **Do not pass `-q` yourself**: `addopts` already carries one, so `-q` on the
  command line makes it `-qq`, and at `-qq` pytest prints **no summary line at
  all** — the run looks clean, exits 0, and the passed/skipped counts you came
  to measure are simply absent. Use the root CLAUDE.md's commands verbatim; the
  ones that do show `-q` are single-file selections where the count is not the
  point. This wastes whole runs before anyone notices the line is missing
  rather than the run being quiet.
- **Quote wall clock as a range, never as a figure**: the same green tree
  measured 7:37 and 5:44 minutes apart on one machine, 11:52 on a busier
  one, and 12:40 while it also ran a headless browser, three vite builds and
  a second pytest. Machine state moves it further than most changes do;
  compare runs, not records.
  That 12:40 is the same tree as the 5:44, so **say whether another session was
  running** — and check first (§ Running), which makes "alone" a fact rather
  than an assumption.
- **Quote the extras with any count**: installing `[jax,torch]` converts
  most skips into passes, so a bare "N tests" figure means nothing without
  the venv it was measured in.
- **A pass count cannot show a module that never ran.** A collection error is
  one `error` line beside five thousand passes, and every case in that file
  stops being evidence without one of them going red — `tests/test_runs.py`
  was unrun on Windows for three nights that way (WP-1439). What shows it is
  the **total**: passed+skipped agreed across platforms at 5450 once the
  import was guarded, and was 51 short of it before. Compare totals across the
  matrix, never pass counts, which move for every legitimate skip.
- **A test that pins a number declares which *path* produced it**, not only
  which settings — the dispersion rule (root CLAUDE.md) one rank wider, because
  WP-1115 added a second default that changes arithmetic. The compiled kernel
  tier is on unless switched off, so a golden or a bit-identity assertion says
  `compiled.set_enabled(False)` (or `True`) rather than inheriting. The
  signature of getting this wrong is a test that **fails under `-n auto` and
  passes alone**: the background compile finishes at a different point in each.
  `conftest.py` also asks for one kernel thread per xdist worker, so a
  wall-clock budget is not a function of the worker count.
- **A worktree needs its own venv, and quote which one you used.** The main
  checkout's `.venv` resolves `rietx` to the *main checkout's* `src`, so a
  worktree session running it measures the wrong tree — green, and about code
  it did not change. Build one per worktree (`uv venv --python 3.12 && uv pip
  install -e ".[dev]"`), and say `[dev]` vs `[dev,jax,torch]` with every figure.
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
  pass (WP-1029 added six: five passes and one skip, which is the
  version of this check that earns its keep). For the **full** selection quote
  green plus a delta consistent with the fast one; both ends of an exact check
  there costs an hour of machine time, and the baseline it needs is CI's job
  (§ Running, the ladder). The vitest suite is counted
  separately — its 207 was once quoted as 206 until the next session re-ran
  it, the same lesson one suite over.
- **`--collect-only` undercounts by one per module-level `importorskip` that
  fires** (resolved 2026-07-31, WP-1031, by diffing junitxml nodeids against
  the collection list): a module skipped at import is **one skipped test**
  in the run summary and **zero items** under `--collect-only`. Three
  modules can fire (`test_backend_jax`, `test_backend_torch`,
  `test_manual`'s sphinx), so on a numpy-only `[dev]` venv the historical
  figures were two short of passed+skipped in both selections
  (1385 vs 1383, 1306 vs 1304) and on `[dev,jax,torch]` the gap is zero. So
  `collected = passed + skipped − (module-level skips that fired)` — quote
  whichever you measured, and say which. (The "1378 collected" the docs
  once carried was a sum, not a measurement — that part stands.)

## CI

CI runs the same commands (`.github/`). Per push and per PR (`ci.yml`, the
branch-protection required checks): ruff + the fast suite across 3.11–3.14
plus a `[dev,jax]` fast job, Linux, **no path filter** — a filtered job is a
required check that never reports on a docs-only PR. **A draft PR runs ruff
alone**, the matrix waiting for `gh pr ready` (`ci.yml`'s header). Nightly
(`nightly.yml`): the full suite `[dev,jax]` on Linux, the Windows fast suite
(the OS classifier's backing and the release pre-upload gate), macOS fast +
the informational goldens step (the guard in `test_backend_shim.py` is the
local half of that trade), and `[torch]`. The free-tier shaping this
replaced — cadences priced against 2000 min/month, macOS at 10× — was undone
at WP-1003's visibility flip; its measured arithmetic is in git history and
DESIGN.md. **Read spend from the Actions usage page or `gh run list`, never
from comments or this file**: a written cross-workflow total rots — one sat
at 303 against a measured ≈495.

Two consequences for local work:

- **The bit-identity goldens are pinned to `darwin/arm64`**
  (`GOLDEN_PLATFORM` in `tests/test_backend_shim.py`) and *skip* elsewhere:
  measured, Linux x86-64 diverges by 1 ulp to 1.7e-13 relative — a libm and
  summation-order difference — so the gate is asserted where it was captured
  rather than loosened to a tolerance that could not distinguish it from a
  real change.
- **`tests/.jax_cache` is why the jax rows feel free locally** — deleting it
  takes the two jax files from ~12 s to 107 s — but caching it in CI was
  measured and does *not* help (8:18 warm against 8:12 cold): jax's
  persistent cache holds only XLA compilations above a time threshold, while
  per-process tracing and lowering are paid every run.
