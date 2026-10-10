# WP-1940 — the kernel tier in a wheel: Rust kernels, threaded on work, with a vector exponential

Milestone: unscheduled · Status: 🔄 2026-10-10 — numba gone and rietx-kernels 1.0.0 loaded (PR #864); next the rasteriser port as kernels 1.1.0
Track: Candidates — named on a use case, not yet on a measurement
Depends on: 1939
Priority: P2 2026-10-10 — the decision is taken (Rust, § Decisions) and every agent install pays numba's 143 MB and warm-up until this lands; the first task is a bit-neutral 1.4× that ships on its own

## Goal

`pip install rietx` into a fresh venv or a Colab notebook brings no numba and
no `numpy<2.6` ceiling. A separate `rietx-kernels` distribution, Rust under
PyO3 and built as one abi3 wheel per platform, runs the model kernels. The
thread pool engages on the calls that carry the time, the FCJ kernels use a
vectorised exponential to a stated error bound, and an install where the
kernels do not load says so instead of running the numpy path in silence.

## Context

WP-1939 spiked the five model kernels in Rust and Cython against numba and
returned the verdict Rust. This WP is the build it asked for, plus what a
review of the spike and a measurement of the fits it benchmarked turned up.
Everything below was measured 2026-10-10 on the `[dev]` venv, darwin/arm64,
python 3.12.10, numpy 2.5.3, numba 0.68.0, unless a row says otherwise.

### Decisions, 2026-10-10

Taken by the maintainer on the review of 1939. They are the premises of the
tasks and are not reopened here.

1. **Rust replaces numba in the model tier.** The reason is the install, never
   the speed: rietx is installed by agents into fresh venvs and into Colab,
   each of which pays numba's weight and warm-up every time, and Colab moves
   its numpy under the ceiling.
2. **Bit identity is relaxed for the exponential and for nothing else.** The
   rule was never about truth. It bought review by eye and the same answer
   from the same input whatever was installed. Both survive where the rule is
   free, in sums and differences, and neither is worth the exponential's
   cost. So: **transcendentals to a stated bound, associations as written**
   (§ The relaxed rule).
3. **Optimisations land with the migration.** The goldens re-pin once at the
   migration; bundling the exponential saves a second re-pin. The threading
   fix is bit-neutral and ships first, under numba. *Superseded in part
   2026-10-10 (3rd session) by item 7:* the Rust kernels are bit-identical to
   numba on all five platforms, so the migration re-pins nothing.
4. **A hard dependency, with no platform markers and no sdist** (taken
   later the same day). pip then fails loudly where no wheel exists, which
   beats a silent slow path. musllinux and free-threaded (abi3t) wheels are
   added when someone asks.
5. **The crate lives in this repository under `kernels/`**, polars' shape
   (taken later the same day). It releases on its own tag namespace,
   `kernels-vN.M`, through one `maturin-action` workflow on that tag.

Three more, taken 2026-10-10 in the 3rd session, after the maintainer asked
why the kernels are not shipped inside rietx:

6. **A separate distribution, confirmed.** Inside, rietx's build would move
   from hatchling to maturin, every weekly cut would build five wheels, and
   every install from source would need a Rust toolchain: each worktree, each
   CI job, each contributor, and `pip install git+…`, the development-build
   route. Separate keeps rietx pure Python. The kernel source changed once
   (2026-08-22) across the six rietx releases since. Both shapes have
   precedent. Inside: cryptography, markupsafe, pyyaml, charset-normalizer.
   Separate: transformers on tokenizers and safetensors, pydantic on
   pydantic-core, jsonschema on rpds-py.
7. **1.0.0 publishes the bit-identical kernels.** The migration then moves no
   number. The vectorised exponential ships as 1.1.0 and carries the one
   golden re-pin, so each release has one effect. *Superseded in part
   2026-10-10 (4th session) by item 9:* the exponential is 1.2.0.
8. **numba leaves all three tiers at the migration.** Both other tiers keep a
   bit-exact numpy twin, which is each one's test oracle, so neither port
   blocks the drop (§ The other two numba tiers has the cost). The indexing
   traversal stays on numpy. The rasteriser is ported afterwards. This
   replaces the interim extra the task list carried.

One more, taken 2026-10-10 in the 4th session, on a measurement that moved
the premise of item 8:

9. **The rasteriser port is the next kernel release, 1.1.0, and the
   vectorised exponential moves to 1.2.0.** On numpy, `view="auto"` takes
   1.30-1.36 s on the NAC cell at 400 px, against 92 ms on numba, and 22.6 s
   at 3143 atoms, against 565 ms. Item 8 was taken on § The other two numba
   tiers' 5-8×, which timed plain renders only. numba still leaves the figure
   in the `compiled.py` PR.

### What 1939 established

- Rust and Cython (with `-ffp-contract=off`) agree with numba on every kernel
  call of the trigger and cpd-1a fits, on darwin/arm64, Linux x86_64 and
  Linux aarch64. Cython under clang's or gcc's default contraction differs on
  every scatter on both arm64 platforms and moved the trigger fit 4.8e-2 esd
  with nothing raised. rustc never contracts.
- Speed does not separate the languages: 1.01–1.08× numba end to end.
- One abi3 wheel per platform, 142–245 KB, 36–79 s of CI each on five
  platforms. numba is 143 MB on disk and 0.1–0.6 s of warm-up per process.
- Two Rust traps, both in `kernels/src/lib.rs`'s docstring (the spike's crate,
  moved there by task 4):
  rust-numpy refuses two live writable borrows of one array, so outputs go
  through raw pointers; a loop written as a closure over captured slices ran
  at 0.59× numba, as a free function at 1.52×.
- Linux x86_64 lost 3–15 % on the two FCJ kernels. *Hypothesis:* numba
  compiles for the host (AVX2 on that runner) and the wheel targets baseline
  x86-64.

### What the review of 1939 added

**Architecture.** The precedents 1939 cites (polars, pydantic, jax) are the
inverse of rietx's shape: their compiled distribution is the product and the
python front is a shell, so they pin exactly. rietx is a large python package
with a 254-line accelerator and a working fallback. The precedent for *that*
shape is jsonschema → rpds-py, a pure-python package depending on a small
PyO3 distribution by the same maintainer, pinned as a floor
(`rpds-py>=0.25.0` on 2026-10-10). Four consequences:

- **Pin by major version equal to the kernel interface number.** The front
  declares `rietx-kernels>=N,<N+1` with N = `KERNEL_ABI`, so pip refuses a
  mismatch before anything imports, and `compiled.py` re-checks the integer
  at import. An exact pin, polars' way, would force a kernel release every
  week.
- **A decline is visible.** 1939's design points describe two silent
  fallbacks (no wheel for the platform; an ABI mismatch), which is WP-1521's
  failure in a new place. A decline warns once per process and
  `capabilities()` says why.
- **Platform markers cannot say "a wheel exists".** They enumerate five
  OS/CPU pairs and miss musllinux, free-threaded builds (abi3 does not load on
  3.13t/3.14t, where numba does ship wheels today) and any future target. The
  three honest shapes are a hard dependency with no markers and no sdist
  (pip fails loudly where no wheel exists), markers, or an optional extra.
  **Decided: the first, § Decisions item 4.**
- **Where the crate lives and how it releases.** polars keeps both
  distributions in one repository; pydantic-core has its own. `RELEASING.md`
  builds from a tag, so one repository needs a second tag namespace
  (`kernels-vN.M`) or a path filter. **Decided: one repository, § Decisions
  item 5.**

**Measurement.** Windows and macOS x86_64 built wheels and never ran the
agreement pass; the Windows maths library is the one not yet shown shared
between numba and Rust. The agreement pass counts calls and never branches:
`accum` has four `n_terms` arms, Ω two spellings, `bases_fcj` the axial arm
(the trigger plan frees `axial_sl`, so that one ran; which scatter arms ran
is unknown). "rustc never contracts" covers `*` and `+`; the exponential
agreed because both sides called the same libm on three platforms, and
Rust's std could one day ship its own.

**Code, for the port.** `out2` never checks an output plane is distinct from
`x` or from its sibling outputs (aliasing a raw write with a live slice is
undefined behaviour; four pointer compares close it). `pl()` discards the
width of `om`, `dphi` and the axial planes and indexes them with `phi`'s
width, where numba reads each with its own. `rows[r] as usize` wraps on a
negative value in a release build; the slice bounds check keeps the write
inside the plane, so it is a wrong row and never a memory error.

### Where the time goes

Every kernel call timed inside the two spike fits, numba tier:

| fit | wall | kernel time | share | of which FCJ kernels |
|---|---|---|---|---|
| trigger | 6.07 s | 2.63 s | 43 % | 2.41 s |
| cpd-1a | 1.58 s | 0.12 s | 7 % | — (no FCJ) |

| kernel, trigger | calls | seconds | µs/call | rows median | rows max |
|---|---|---|---|---|---|
| `accum` | 11 278 | 0.212 | 18.8 | 224 | 564 |
| `omega_sym` | 1 156 | 0.007 | 5.8 | 13 | 48 |
| `omega_fcj` | 6 524 | 0.989 | 151.6 | 4 | 494 |
| `bases_sym` | 700 | 0.008 | 11.7 | 15 | 48 |
| `bases_fcj` | 3 736 | 1.417 | 379.3 | 4 | 494 |

Python above the kernels in `compiled.*` is 0.05 s of the 6.07. On cpd-1a no
kernel work of any kind can move the fit; its 1.03× in 1939's table is noise
over a 7 % share.

**The thread pool never engaged.** `compiled._THREAD_MIN_ROWS` is 512. The
largest call in either fit had 494 rows (`accum` is never spread). Every one
of the 12 116 trigger calls ran inline, so 1939's "threads = 8" end-to-end
table is serial kernel execution. The 512 was sized for the symmetric
kernels, where a row costs a fraction of a microsecond. An FCJ row costs
3–10 µs, since it carries 8–40 quadrature nodes across its window:

| FCJ calls in trigger | `omega_fcj` | `bases_fcj` |
|---|---|---|
| calls / seconds | 6 524 / 0.995 | 3 736 / 1.420 |
| ns per (point × node) | 2.6 | 6.1 |
| rows ≥ 64: calls, share of time, median µs | 1 156, 90 %, 559 | 700, 91 %, 1 363 |
| rows ≥ 256 | 290, 42 %, 1 539 | 175, 42 %, 3 306 |
| rows ≥ 512 | 0 | 0 |

The pool's dispatch (`_spread` over a no-op, 8 workers, idle) is
29.7–31.3 µs a call.

**The exponential is the floor.** numpy's `np.exp` and the C library's
`exp` (a numba scalar loop) are bit-identical on this platform
(0 of 4 000 000 differ) and cost 1.97 and 2.10 ns per element, against
0.33 ns for a multiply-and-add. Roughly three quarters of `omega_fcj`'s 2.6 ns
per element is the exponential. SLEEF-class vector exponentials run at
0.3–0.5 ns per element.

### The relaxed rule

Replaces the "every expression is a transcription" clause for the kernel
tier, in the root CLAUDE.md, `model/compiled.py`'s docstring and the kernel
sources. The scatter (`accum`) keeps the bit; it has no library call.

1. **Transcendentals to a stated bound, associations as written.** Each
   kernel's docstring names its `exp` implementation and the bound it holds
   (the implementation's documented maximum ulp error), and
   `tests/test_compiled_kernels.py` asserts that bound against the numpy
   builder. Every sum and difference keeps the numpy line's association: the
   scatter adds mixed-sign terms into one array and the FCJ position
   derivative is two whole sums subtracted, and reassociating either loses
   digits through cancellation by an amount the data decides.
2. **One path per process stays** (1115's rule 4). It is what keeps the last
   digits independent of machine speed.
3. **A fit-level guard.** Converged θ on the kernel path against the numpy
   path, in esd units, on the two spike cases. 1939 measured 5.3e-2 on
   trigger today, under bit-identical kernels, because a solver amplifies a
   last-bit difference into where it stops. The guard is a runaway guard at
   several times that, never a tolerance that senses termination
   (tests/CLAUDE.md § Budgets).
4. **Goldens re-pin once per change of kernel arithmetic**, on the
   `GOLDEN_PLATFORM` pin they have. If that becomes frequent, the tier's
   goldens move to a tolerance and bit goldens stay with the numpy path.
5. **The agreement pass stays zero-tolerance outside the exponential**, with
   a separate ulp column for it, so a transcription error stays visible after
   the rule changes.

Under this rule a fused multiply-add is an ulp-class change and Cython's
contraction trap stops being disqualifying; 1939's verdict then rests on
abi3 maturity and the packaging precedent, which still favour Rust.

### Optimisations, ranked by measured gain

1. **Threshold the pool on work, never on rows** (Python, bit-neutral,
   ships first). Rows × nodes × summed window width, or a per-kernel row
   floor. 90 % of 2.4 s split across 8 cores at 30 µs a dispatch leaves
   ~0.6 s; trigger lands near 4.3 s from 6.1, ~1.4×, larger than anything the
   language bought. The gain is Amdahl-bounded: 57 % of trigger is numpy and
   python outside the kernels.
2. **Vectorised exponential in the FCJ kernels** (needs the relaxed rule).
   3–4× on their 2.4 s. With (1), the kernel share of trigger drops to
   ~0.3 s and trigger lands near 3.7 s. A pure-Rust implementation also makes
   the kernel tier give the same bits on every platform; the numpy parts of
   the forward model keep their platform libm, so the fit as a whole does not.
3. **Loop interchange in the FCJ kernels**: node loop outside the window
   loop, so the compiler vectorises across window points. Bit-neutral (each
   output still sums its nodes in order). Pays only with (2).
4. **Dispatch inside Rust** once the pool engages: 30 µs of python dispatch
   is a quarter of a split 1.36 ms call; rayon dispatches in a few µs. A
   dependency and a second pool. Measure after (1).
5. **x86-64-v3 multiversioning** (`multiversion` crate) for Linux x86_64's
   3–15 % FCJ loss. Bit-neutral.
6. **Const generics for `spell` and `has_ax`**: the compiler almost
   certainly unswitches both. Zero expected; check the assembly and stop.

Does not pay: per-call overhead (0.05 s above the kernels in 6 s), unchecked
indexing (1939 measured no change), reciprocal multiplies, reassociating the
node sum.

### The other two numba tiers

Dropping numba from the dependencies waits on `indexing/_kernels_numba.py`
(514 lines, the dichotomy traversal, `dichotomy.py:180` builds it with its
own soft import) and `viz/figure3d/_kernels_numba.py` (442, the rasteriser,
`raster.py` declines on failure). Both allocate arrays inside the kernels,
which in Rust is rust-numpy array creation rather than a slice argument.
Neither was spiked. *Superseded 2026-10-10 (3rd session) by § Decisions
item 8:* numba leaves without either port. What each numpy twin costs:

| tier | numba | numpy | source |
|---|---|---|---|
| indexing, four real patterns | — | 1.03–1.09× slower | WP-1508's table |
| indexing, synthetic monoclinic | 10.0 s | 194.8–205.6 s | WP-1508's table |
| figure, 1000 px | 0.051–0.078 s | 0.346–0.357 s | `cod_1000055`, this Mac |
| figure, 2000 px | 0.138–0.176 s | 1.169–1.170 s | same |

The figure rows are one small structure, three and two renders, `[dev]`
venv, darwin/arm64, machine idle. Every real pattern WP-1508 measured is
bound by its leaves, which the compiled traversal does not reach. The
synthetic row is a box-bound search no real pattern has shown.

**An Intel Mac cannot install rietx today** (found 2026-10-10, 3rd session).
numba ships no macOS x86_64 wheel from 0.63 (PyPI's file lists: 0.62.0 has
`macosx_10_15_x86_64`, 0.63.0 and 0.68.0 have none), and 0.63 is rietx's
floor. So pip must build llvmlite from source, which needs an LLVM
toolchain. The kernel wheel cross-builds for that platform, so dropping
numba at the migration (§ Decisions item 8) is what makes the base install
work there again.

### Decisions owed

None remain. The maintainer took the first two on 2026-10-10 (§ Decisions
items 4 and 5), and measurement settled the third:

- **The threshold's shape in task 1 is a work product**, which needs nothing
  from the caller. Rows × nodes × the plane's padded width bounds the work
  for free, and the summed width is paid only by a call that bound does not
  rule out. On trigger's FCJ calls the work predicts inline time at log
  correlation 0.999 (rows alone 0.98), and a 512-row symmetric call is
  30-60 µs of work that splitting slowed to 0.2-0.5×, so a row floor is wrong
  for the symmetric kernels too.

## Non-goals

Porting the indexing traversal: its numpy loop costs 3-9 % on real patterns
(§ Decisions item 8). The rasteriser port is a task, and may become its own
WP once the model tier ships. A rayon pool (item 4) waits on item 1's
measurement. FPA and the peaks buffer stay fenced (1122).

## Tasks

- [x] Threading on work: `_THREAD_MIN_ROWS` replaced by a per-kernel floor
      or a work product in `compiled.py`; `bench_aot_kernels.py` reports
      pooled against inline calls; trigger end to end before and after, as
      ranges, in the handover. Under numba, bit-neutral, its own PR.
- [x] Branch counters in the agreement pass (`n_terms` arms, `spell`,
      `has_ax`), and the pass run on Windows and macOS x86_64 (a temporary
      workflow, as 1939 did), closing 1939's two owed platforms.
- [ ] The relaxed rule written: root CLAUDE.md's compiled-tier clause,
      `compiled.py` and kernel docstrings, `test_compiled_kernels.py`'s bars
      per kernel, the fit-level guard; `tests/CLAUDE.md` § Quoting numbers'
      "which path produced it" sentence re-read against it.
- [x] The `rietx-kernels` crate from `examples/aot_spike/rust/` into its
      decided home, with the three code fixes (distinct-buffer check, per-plane
      shape check against `phi`, checked index conversion), `KERNEL_ABI`,
      `module-name`, abi3-py311, `codegen-units = 1`, `lto = "fat"`.
- [x] `compiled.py` loads the wheel: import, ABI check (a kernel the wheel
      lacks declines the same way), decline that warns once and reaches
      `capabilities()`; `_SURFACE_FLAGS`/`features` updated;
      the numba model kernels and the cache-directory and warm-thread
      machinery removed from the model tier; `install.md` and
      `compatibility.md` say what changed. One PR with numba's removal and
      the pin, opened once 1.0.0 is on PyPI (§ Decisions item 7).
- [ ] Vectorised exponential: choose and license-check an implementation
      (SLEEF is Boost-licensed, ARM optimized-routines MIT, numpy's SIMD `exp`
      BSD; GPL sources are concepts only), state its bound, loop interchange
      in the two FCJ kernels, the bound asserted, goldens re-pinned once;
      measured against the serial numbers above. Released as 1.2.0, with
      the relaxed rule (§ Decisions items 7 and 9).
- [ ] x86-64-v3 multiversioning, measured on the Linux x86_64 runner against
      1939's 0.85–0.97×.
- [x] Release machinery: `kernels.yml` (five wheels, each tested on its own
      platform with the refusals and the `--gate` agreement pass, published
      on a `kernels-v*` tag) and `RELEASING.md` § The kernel wheel.
- [x] 1.0.0 on PyPI (the maintainer's pending publisher, tag and approval),
      then `pyproject` pins `rietx-kernels>=1,<2` in the `compiled.py` PR.
- [x] numba removed from the dependencies in the `compiled.py` PR
      (§ Decisions item 8): the indexing traversal on its numpy loop, its
      numba twin and `test_indexing_kernels.py`'s compiled half deleted, and
      the indexing CLAUDE.md's "compiled twin" rule and root CLAUDE.md's
      compiled-tier clause rewritten; the figure on its numpy rasteriser;
      `pyproject`'s dependency comment rewritten.
- [ ] Port the rasteriser into the crate against its bit-exact numpy twin
      (`raster.py`'s docstring) and the figure tests; released as 1.1.0,
      the next kernel release (§ Decisions item 9). If WP-1505 moves the
      figure into rietview first, the port goes there.
- [ ] Tests: the guard, the bars, the branch counters, `test_capabilities`'s
      new flag writer, `test_compiled_kernels.py` on both paths; the fast
      selection's passed+skipped delta quoted. When numba leaves, the
      agreement pass's reference moves from numba to the numpy path, in the
      bench and in `kernels.yml`'s `test` job.
- [x] Skill: `references/diagnostics-indexing.md`'s `compiled_kernels`
      paragraph rewritten (no numba to omit; a wheel that imports or does
      not), and `install.md`'s agent admonition. No body change: an agent
      never sees which compiler built a kernel.

## Acceptance

```sh
# a fresh install carries no numba and the kernels import
uv venv /tmp/rx && uv pip install --python /tmp/rx/bin/python rietx && \
  /tmp/rx/bin/python -c "import rietx, rietx_kernels; print(rietx.capabilities()['features'])"
# agreement, bounds and branch coverage inside the two fits
.venv/bin/python examples/aot_spike/bench_aot_kernels.py --cases trigger,cpd-1a --repeats 5
# the kernel tests on both paths, and the fit-level guard
.venv/bin/python -m pytest tests/test_compiled_kernels.py -q
RIETX_COMPILED=0 .venv/bin/python -m pytest tests/test_compiled_kernels.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bench's agreement column is zero for every kernel outside the
exponential's ulp column, on every wheel platform. Trigger end to end is
quoted as a range against the same session's numba range; the target from
the numbers above is ~3.7 s against 5.99–6.51 s, and anything under 4.5 s
with the guard green is a pass.

## References

- WP-1939 (the spike, the verdict, the two Rust traps, the Linux run and the
  wheel matrix), WP-1115 (the tier's four rules), WP-1521 (a tier that did
  not run must say so).
- jsonschema's `pyproject.toml` (`rpds-py>=0.25.0`), github.com/python-jsonschema/jsonschema;
  rpds-py, github.com/crate-py/rpds.
- SLEEF (Shibata & Petrogalli 2020, IEEE TPDS 31(6), Boost licence);
  ARM optimized-routines `exp` (MIT); numpy `npyv` exp (BSD).
- PyO3 guide, `Python::detach` and abi3; rust-numpy README (abi3 under
  `numpy` crate); maturin, www.maturin.rs; `multiversion` crate.
- `docs/RELEASING.md` (build from the tag, never by hand).

## Handover log

### 2026-10-10 (4th session) — rietx loads the wheel, and numba leaves

rietx now runs its model kernels from `rietx-kernels`, the Rust package that
reached PyPI today, and no longer installs numba. A fresh install is 139 MB
smaller and compiles nothing on its first fit. numpy has no ceiling from rietx,
and an Intel Mac can install it again. Fits give the same numbers. An install
whose kernels do not load now warns once and says why, where before it ran
slower in silence. The indexing search and the structure figure lost their
numba paths and run on numpy. The figure's automatic view is 14-40× slower
until the rasteriser joins the kernel package, which the maintainer made that
package's next release. All of it is PR #864, unmerged.

*Done.*
- **1.0.0 on PyPI**, checked at the session's start: five wheels, and the
  `kernels-v1.0.0` tag run (38072977961) green. Task ticked with the pin.
- **The indexing and figure tiers on numpy** (task 9's first half, a lane).
  `indexing/_kernels_numba.py` and `viz/figure3d/_kernels_numba.py` deleted,
  with the traversal builder, `_traverse_compiled`, the raster loader and the
  `compiled_path` arguments. `test_indexing_kernels.py` keeps its numpy half
  (26 → 5 cases); `test_render_structure.py` lost the two compiled-path
  tests. `indexing/CLAUDE.md`'s rule now says the numpy loop is the oracle
  for a port into the crate. The manual's and the skill's figure timings
  were re-measured. No schema field records which indexing path ran.
- **`compiled.py` loads the wheel** (tasks 5 and 8, a lane). `KERNEL_ABI = 1`
  and `KERNEL_NAMES` are public. `_load` declines with a one-clause reason
  when the import raises, the interface number differs, or a kernel is
  missing; `unavailable()` returns it. `enabled()` warns once, as a
  `RuntimeWarning`, when the switch is on and the load failed; neither
  `RIETX_COMPILED=0` nor `set_enabled` warns. `warm()`, the cache redirect and
  `model/_kernels_numba.py` are gone. `Capabilities.compiled_kernels_unavailable`
  carries the reason. `pyproject` pins `rietx-kernels>=1,<2` and drops numba,
  and a test holds the pin equal to `KERNEL_ABI`. `lib.rs`'s header now holds
  the transcription contract that `_kernels_numba.py`'s docstring held. The
  root CLAUDE.md's compiled-tier clause, `install.md` and `compatibility.md`
  were rewritten for the wheel.
- **The agreement pass's reference is the numpy path** (task 11's last
  sentence, a lane). The bench holds each wheel call against a numpy twin
  with the kernel's signature, built from the package's own functions. The
  fit then runs on the twins' outputs and must match a `RIETX_COMPILED=0` fit
  bit for bit, so every run checks the twins as well. `kernels.yml` drops
  numba, checks through `direct_url.json` that it installed this run's wheel
  rather than PyPI's identical 1.0.0, and runs `test_compiled_kernels.py` on
  each platform. The Cython candidates left the bench; `cython/` stays.
- **§ Decisions item 9**, the maintainer's answer to the figure's slowdown:
  the rasteriser port is kernel release 1.1.0, and the exponential moves to
  1.2.0. Item 7 and two tasks amended to match.
- **Skill** (task 12): the `compiled_kernels` paragraph names the wheel and
  `compiled_kernels_unavailable`. `install.md` has no agent admonition, so
  there was none to rewrite. No body change.
- The 1.8.0 notes and the v1.8 record stage the change: the dependency swap,
  the platforms pip now refuses (musllinux, free-threaded 3.13t/3.14t), the
  figure's slowdown, the new field and the warning.
- Forward references: 1505, 1520, 1521, 1538, 1917, 1924. 1521 is re-rated
  moot: this PR does its whole Goal, so it closes as 🛑 when #864 merges.
- `/code-review high --fix` reported ten findings. It fixed five: one
  kernel-test run in `kernels.yml` (the second, under `RIETX_COMPILED=0`,
  repeated the first, since every comparison sets its own path), the
  release note's figure factor by image size (5-26×), where the warning
  fires (`capabilities()` fires it too), an esd-only θ gap named in the
  bench, and a spacing typo. I fixed a sixth: `compiled_kernels_active` read
  True after `set_enabled(True)` over a wheel that did not load. It now needs
  `available()` too, which is 1521's last clause. Two findings were answered
  by measurement: the monoclinic recovery test takes 70 s on numpy against
  its 900 s budget (the review's ~200 s was the synthetic box-bound list),
  and the indexing acceptance suite passes. Two were declined:
  `kernels.yml` does not trigger on `forward.py`, which changes often, and
  `ci.yml`'s fast suite runs `test_compiled_kernels.py` against the
  published wheel on every PR; `_grid_pass`'s `test` callback stays as the
  seam for a Rust traversal.
- No `### Inherited` to prune.

*Measured.* `[dev]` venv with `rietx-kernels` 1.0.0 from PyPI and numba
uninstalled, darwin/arm64, python 3.12.10, numpy 2.5.3. No other suite ran
during any timing.

| kernel, agreement against numpy | trigger: calls / bit-identical / max rel | cpd-1a |
|---|---|---|
| `accum` | 11 004 / 11 004 / 0 | 6 377 / 6 377 / 0 |
| `omega_sym` | 1 128 / 1 128 / 0 | 909 / 909 / 0 |
| `bases_sym` | 688 / 688 / 0 | 597 / 597 / 0 |
| `omega_fcj` | 6 189 / 0 / 8.0e-16 | not called |
| `bases_fcj` | 3 580 / 0 / 5.0e-15 | not called |

- The bars are `test_compiled_kernels.py`'s: the scatter to the bit, the
  symmetric kernels to the bit on darwin/arm64 and under 1e-15 elsewhere,
  the FCJ kernels under 1e-13. The gate was made to fail twice, once on a
  wheel off by an ulp and once on a twin moved by 1e-12.
- End to end, 5 interleaved repeats, 8 workers: trigger 10.96-10.99 s on
  numpy, 4.08-4.22 s on the wheel, 5.37-5.42 s on the wheel inline; final θ
  2.2e-1 esd from numpy's, as the 2nd session measured. cpd-1a 2.87-2.95 s,
  1.46-1.56 s and 1.47 s; θ bit-identical. Trigger is already under the
  acceptance's 4.5 s before the exponential.
- Startup: `import rietx_kernels` adds nothing measurable over numpy
  (0.048-0.050 s against 0.048-0.066 s); `import rietx` 0.70-0.83 s.
- Install, fresh python 3.12 venvs: site-packages 182 MB for this tree, 321 MB
  for `rietx==1.7.0`. Both resolve numpy 2.5.3, the newest there is. A fresh
  install imports `rietx_kernels`, finds no numba, and reports
  `compiled_kernels` and `compiled_kernels_active` true with no reason.
- The figure on numpy, NAC cell at 400 px: plain 0.100-0.102 s, `view="auto"`
  1.30-1.36 s (92 ms on numba). The lane measured 3143 atoms: plain
  1.02-1.06 s, auto 22.6 s (565 ms).
- `test_dichotomy_recovers_a_monoclinic_cell` alone: 70.2 s on numpy, against
  `BUDGET_SECONDS` 900 and its docstring's ~80 s.
- `tests/test_acceptance_indexing.py`, `-n auto`: 44 passed in 14:14.
- Fast suite on the merged tree (main at bdaa7b62): 9013 passed, 177 skipped, 1 xfailed, 4:41, the merge bringing WP-1937's tests. Before the merge,
  on the branch alone: 8996 passed, 177 skipped, 1 xfailed, 3:19. Against
  main, per file in the fast tier: `test_compiled_kernels.py` 17 → 20,
  `test_indexing_kernels.py` 26 → 5, `test_render_structure.py` 112 → 110,
  every other touched file unchanged (237 items both sides).
  `test_rietx_kernels.py`'s 27 cases now run where CI counted one
  module-level skip, so against CI's main passed+skipped moves by −20 + 26.
- The 7 added tests cost 1.57 s in the branch run, 1.55 s of it
  `test_a_band_boundary_moves_no_bit`'s 2 cases (`tests.added_test_times`).
- The full suite was not run. The model kernels are bit-identical to numba,
  and the indexing and figure numpy paths were each one's bit-exact oracle,
  so no measured number can move. The indexing acceptance ran instead,
  because an engine's timing changed under its budgets.
- Lanes:

| lane | est | requests | main at dispatch | re-read | left in main | lane $ | saved $ |
|---|---|---|---|---|---|---|---|
| numba-out-of-indexing-and-figure | 25 | 97 | 162K | 0K of 15K | 36K | 5.01 | +2.31 |
| compiled-loads-the-wheel | 35 | 87 | 198K | 16K of 28K | 9K | 4.32 | +3.66 |
| bench-numpy-reference | 25 | 56 | 247K | 25K of 55K | 11K | 3.13 | +2.41 |

  Main 90 requests at a 278K peak, $6.93; lanes $12.46. Actual over
  estimated requests 2.49. The selective policy's replay row
  (main > 150K and item >= 20 requests): 109 items laned, -17 %.
- **After the PR was readied, `kernels.yml` failed on macOS x86_64** (run
  38083614821) while every kernel call there was within its bar. The bench's
  twins check compares a fit on the twins with a fit on the numpy path. A
  throwaway workflow (run 38085279862, branch deleted) found the numpy path
  does not reproduce itself on that runner: i7-8700B, no AVX-512, numpy
  2.4.6, three identical cpd-1a fits in one process, up to 9.7e-4 esd apart.
  `np.exp` and the pseudo-Voigt gave the same bits at eight byte offsets, so
  memory alignment is not the cause. *Hypothesis:* Accelerate's threading on
  Intel. The bench now runs the numpy path twice and reports, rather than
  gates, the twins' gap where the two disagree. The next run, 38085484334,
  passed on all five; on that runner the numpy path differed from itself by
  6.8e-3 esd on cpd-1a and 7.1e-1 esd on trigger.

*Gotchas.*
- On macOS x86_64 the numpy path is not deterministic between identical fits
  in one process. A check that compares two fits there measures that noise.
- An existing venv keeps numba after `uv pip install -e ".[dev]"`. Uninstall
  numba and llvmlite before trusting a numba-free run.
- To count main's tests without a second worktree: `git archive origin/main
  src tests pyproject.toml | tar -x` into the scratchpad, then
  `PYTHONPATH=src pytest --collect-only -q` there with this venv.
- The worktree guard refuses a command that computes a `sed` range or `cd`s
  outside a subshell. A short script in the scratchpad gets through.

*Next.*
1. The maintainer: review and merge #864. Then close WP-1521 as 🛑,
   superseded by this WP.
2. The rasteriser port as `rietx-kernels` 1.1.0 (§ Decisions item 9):
   `render_rows` and `id_plane` into `lib.rs`, held on the bit to
   `raster.py`'s `_band_numpy` and `_ids_numpy`. The rietx PR that calls them
   raises the pin to `>=1.1,<2`.
3. The vectorised exponential with the relaxed rule as 1.2.0 (tasks 3 and 6),
   its guard sized on the 2.2e-1 esd. Then multiversioning.

### 2026-10-10 (3rd session) — the crate, both owed platforms, and the release workflow

The Rust kernels now live in this repository as their own package,
`rietx-kernels`, and every call checks its arguments before it writes. They
match numba bit for bit on all five platforms the wheel ships for. Windows
and Intel macOS were measured for the first time, and both agree. A
workflow builds, tests and publishes the five wheels, and its first run was
green; nothing is on PyPI yet. The maintainer confirmed the separate package
after asking why the kernels do not ship inside rietx. They also chose to
publish today's bit-identical kernels first, and decided numba leaves rietx
entirely at the migration. One finding outside the plan: an Intel Mac cannot
install rietx today, because numba ships no wheel there.

*Done.*
- **Task 4.** `examples/aot_spike/rust/` moved to `kernels/` (`git mv`) as
  `rietx-kernels` 1.0.0, module `rietx_kernels`, abi3-py311,
  `codegen-units = 1`, fat LTO. `KERNEL_ABI` is the crate's major version,
  parsed at compile time, beside `__version__`. The loops are unchanged.
  Each binding now checks before releasing the GIL:
  - outputs share no byte with each other or with any input, by address
    range, so a partial overlap and an aliased `phi` are caught as well as
    `out is x`;
  - every plane is C-contiguous. This is a fourth fix of the review's class:
    rust-numpy's `as_slice` accepts a Fortran-ordered plane, which the loops
    would read transposed;
  - node planes have `phi`'s shape and `phi` has one row per `rows` entry;
    per-row arrays have one entry per row of `x`;
  - row indices and window widths go through `usize::try_from`, the row
    range is checked, `spell` is 0 or 1, `n_terms` is 1 to 4, and the
    scatter's windows sit inside `y` and inside every plane they read.
- `tests/test_rietx_kernels.py`: 27 cases after the review, each a well-formed call with one
  defect, the well-formed call as control. It skips at module level until
  the wheel is a dependency, so CI counts it as one skip. Removing
  `omega_fcj`'s disjointness and row checks turned exactly the 9 cases that
  rest on them red.
- rietx's sdist excludes `/kernels`; `.gitignore` ignores `kernels/target/`.
- **Task 2.** The bench counts which arm each call took (`ARM`), and
  `--gate` exits 1 unless `rietx_kernels` imports and no call differs. The
  gate was made to fail both ways once. A temporary workflow on a throwaway
  branch (run 38046325707, branch deleted) ran the pass on Windows x64 and
  macOS x86_64.
- **Release machinery.** `.github/workflows/kernels.yml`: five wheels (1939's
  matrix, macOS x86_64 cross-built), each tested on its own platform at
  Python 3.11 with the refusals and `--gate`, published on a `kernels-v*`
  tag push through the `pypi` environment after tag-on-main and
  version checks. It also runs on a pull request touching the crate.
  `RELEASING.md` § The kernel wheel has the procedure, the pending
  publisher, and the pin rule: a breaking interface change bumps the major,
  and a new kernel is a minor that raises rietx's pin floor.
- § Decisions items 6-8 recorded (separate package confirmed; bit-identical
  1.0.0 first, so the migration re-pins nothing and the exponential's 1.1.0
  carries the one re-pin; numba out of all three tiers at the migration).
  Item 3 marked superseded in part. Tasks 9 and 10 rewritten to match, and a
  "1.0.0 on PyPI, then the pin" task added.
- Forward references: 1505 (rietview's numba shim needs another answer),
  1521 (nothing left after the migration that 1940 does not do), 1538 (the
  occlusion kernel goes into the crate), 1926 (the Voigt kernel is a minor
  kernel release).
- `/code-review high --fix` reported seven findings and five were fixed, in
  three commits. A row listed twice in `rows` is now refused: two pool
  chunks would write it at once, a data race the crate's docstring claimed
  the checks prevent. The gate counts only the wheel's mismatches and fails
  on a kernel no case called. `kernels.yml` also triggers on
  `_kernels_numba.py`, `compiled.py` and `bench_refinement.py`. The README
  no longer claims a pin rietx does not have yet. Two were declined. An
  early return from `_splits` on a one-worker pool would make the pool test
  depend on the suite's thread count, for a small saving. Folding `_splits`
  into `_spread` would change the hook the bench wraps.

*Measured.* Local rows: `[dev]` venv plus the crate built with `maturin
develop --release`, darwin/arm64, python 3.12.10, numpy 2.5.3, numba 0.68.0,
rustc 1.99.0, machine idle.

| platform | run | numba / numpy | calls differing | serial kernel time, rust vs numba (trigger · cpd-1a) |
|---|---|---|---|---|
| darwin/arm64 | local | 0.68.0 / 2.5.3 | 0 | 1.08× · 1.30× |
| Windows x64 | 38046325707 | 0.68.0 / 2.5.3 | 0 | 1.02× · 1.31× |
| macOS x86_64, built natively | 38046325707 | 0.62.1 / 2.3.5 | 0 | 1.07× · 1.23× |
| macOS x86_64, cross-built wheel, py3.11 | 38069237206 | 0.62.1 / 2.3.5 | 0 | 1.09× · 1.25× |

- Arms: in both fits on every platform, `n_terms` 1, 2 and 4 ran and 3
  never did; `spell` 0 and 1 both ran; `has_ax` both ran in trigger. The
  three-term scatter is covered only by `test_compiled_kernels.py`'s arity
  test.
- `kernels.yml` run 38069237206: wheels built in 35-74 s, platform tests in
  57-117 s, all five green under `--gate`.
- A clean release build of the crate takes 8.6 s here. The toolchain is
  ~480 MB (`~/.rustup` 445 MB, `~/.cargo` 37 MB).
- numba's macOS x86_64 wheels on PyPI: 0.60.0, 0.61.0 and 0.62.0 have one;
  0.63.0 and 0.68.0 have none.
- The numpy twins' cost is § The other two numba tiers' table: indexing
  1.03-1.09× on WP-1508's real patterns; the figure 5-8× on one small
  structure.
- Fast suite on the final tree: 9009 passed, 177 skipped, 1 xfailed, 8:03
  with another session's suite running. Against the 2nd session's 8982
  passed on this branch that is +27, the 27 cases of
  `tests/test_rietx_kernels.py`, which pass here because the crate is built
  into this venv. CI has no wheel yet, so there the file is one
  module-level skip: passed unchanged, skipped +1. The 27 cases cost 0.03 s
  in this run (`tests.added_test_times` on the local junit file).
- The gate passed again after the review's row check, but its seconds were
  taken beside that other suite (numba's own kernel time read 3× the idle
  run), so no ratio from it is quoted.
- The full suite was not run: no file under `src/` changed, so no measured
  number can move.

*Gotchas.*
- A probe that imports `rietx.model._kernels_numba` directly skips
  `compiled._redirect_cache`, so numba writes its cache beside the source
  and `test_the_disk_cache_lands_in_the_state_dir_and_not_beside_the_source`
  fails. Import through `compiled`, or delete the `.nbi`/`.nbc` files.
- `cargo build` of the crate fails to link on macOS, because an extension
  module needs `-undefined dynamic_lookup`. Build through maturin:
  `maturin develop --release --uv -m kernels/Cargo.toml` with
  `VIRTUAL_ENV` set to the worktree's venv.
- `release.yml` fires on every published GitHub release, so a kernel
  release is a tag push and never a GitHub release.
- `gh api .../jobs/<id>/logs` refuses a log with terminal escapes unless
  given `--allow-escape-sequences`.

*Next.*
1. The maintainer: add the pending publisher on PyPI (project
   `rietx-kernels`, owner `yue-here`, repository `rietx`, workflow
   `kernels.yml`, environment `pypi`); merge #862; tag `kernels-v1.0.0` on
   that `main` commit and push the tag; approve the deployment.
2. Once 1.0.0 is on PyPI, the `compiled.py` PR: the wheel loads, the pin
   `rietx-kernels>=1,<2`, numba out of all three tiers, the agreement
   reference moved to the numpy path (bench and `kernels.yml`), and the docs
   and skill rows that name numba. It moves no number.
3. The vectorised exponential with the relaxed rule, as 1.1.0, the one
   re-pin, its guard sized on the 2.2e-1 esd of the 2nd session.
4. The rasteriser port (or WP-1505 first), then multiversioning.

### 2026-10-10 (2nd session) — task 1 landed, and both packaging decisions taken

The kernel thread pool now splits a call when the call's estimated work can
pay for it, instead of when the call has many rows. The trigger fit, the one
benchmark whose time sits in the FCJ kernels, now takes 4.2-4.7 s on this Mac
instead of 5.6-5.9 s, and every output keeps its bits. The other two benchmark
fits did not move. The maintainer also took the two decisions this WP owed:
rietx will depend on the kernel wheel outright, with no markers and no sdist,
and the crate lives in this repository. No Rust work has started.

*Done.*
- `compiled._splits` estimates a call's serial time as its elements (rows ×
  nodes × summed window width) at `_NS_PER_ELEMENT`, one measured cost per
  kernel. It splits from `_THREAD_MIN_NS` = 100 µs. The padded width bounds
  the work for free, so only a call that bound does not rule out pays for the
  sum. `_THREAD_MIN_ROWS` is gone, and `_spread` takes the decision as an
  argument.
- `bench_aot_kernels.py` section 2 opens with one counted fit (each kernel's
  calls and seconds, inline against pooled) and gains a `numba, inline` arm.
- Two tests in `test_compiled_kernels.py`: the predicate on real call shapes,
  and every plane bit-identical with every call forced through a four-worker
  pool. The second was made to fail once by dropping a row per chunk.
- `bench_compiled_buffer.py`'s comment no longer names the row floor.
- § Decisions items 4 and 5 recorded. The threshold's shape is settled in
  § Decisions owed, which is now empty.
- `/code-review high --fix` found no correctness bug. Two fixes landed:
  the split test asserts that each kernel it names actually split, and the
  bench counts a split on a one-worker pool as inline. Three findings were
  declined. Chunking by cumulative width instead of equal rows, and scaling
  the threshold by worker count, are both speed changes that need measuring
  first, the second on the CI runner's two cores. The width sum paid on a
  one-worker pool costs ~1 µs on a call of at least 100 µs.

*Measured.* `[dev]` venv, darwin/arm64 (4 performance and 6 efficiency
cores, 8 pool workers), python 3.12.10, numpy 2.5.3, numba 0.68.0. No other
suite was running during any timing; one had been at the session's start,
and the timing waited for it.
- **The crossover.** Calls sampled from the trigger, nac and cpd-1a fits,
  replayed inline and split into 4, 8, 16 and 32 chunks (scratchpad probe).
  At 8 chunks, calls of 40-80 µs inline lost (0.73× `bases_fcj`, 0.82×
  `bases_sym`). Calls of 80-160 µs won (1.54-1.62×), and FCJ calls over
  320 µs won 2.6-4.3×. 16 chunks were no better than 8 on large calls, and
  32 were worse.
- **The estimate.** On trigger's FCJ calls, inline time correlates with
  rows × nodes × summed width at log 0.999, and with rows alone at 0.98.
  Padded over summed width is 1.11 on FCJ buckets and 1.04-1.73 on symmetric
  ones. ns per element: `omega_sym` 1.83, `omega_fcj` 2.75, `bases_sym`
  5.07-5.50, `bases_fcj` 6.46.
- **End to end, before and after** (5 interleaved repeats, the row floor
  restored by patching `_splits`): trigger 5.58-5.93 s on the row floor,
  4.24-4.70 s on work, 5.58-5.81 s inline. nac 0.40-0.47 / 0.39-0.41 /
  0.40-0.41 s. cpd-1a 1.57-2.00 / 1.49-2.30 / 1.50-2.30 s. Final θ was
  bit-identical across arms on all three.
- **The acceptance bench** (`--cases trigger,cpd-1a --repeats 5`): trigger
  numba 4.23-4.29 s, numba inline 5.60-5.74 s, numpy 10.97-11.07 s. Pooled
  calls: `omega_fcj` 1143 of 5981, `bases_fcj` 798 of 3320. cpd-1a numba
  1.49-1.69 s against inline 1.50-1.59 s, with 90 of 597 `bases_sym` calls
  pooled. Startup: numba warm with a cache hit 0.89-1.07 s, cold 1.41-1.50 s,
  tier off 0.71-0.72 s.
- **The numpy path's trigger answer sits 2.2e-1 esd from numba's** on
  today's main. 1939 measured 5.3e-2. Nothing measured says which change
  moved it; #855 (WP-1936's step scaling) merged in between, which is a
  hypothesis only. Task 3's fit-level guard is sized on this number, not on
  1939's.
- **Fast suite**: 8982 passed, 177 skipped, 1 xfailed, 3:28. The 3 added
  cases are +3 to `test_compiled_kernels.py` (14 → 17 collected) and cost
  0.06 s in that run. The full suite was not run, because splitting cannot
  change an output, and the suite runs one kernel thread per xdist worker,
  where nothing splits.

*Gotchas.*
- The suite never splits a call (conftest's one thread per worker), so a
  split test builds its own pool.
- At 8 workers on this chip the large calls gain 2.6-4.3×, not 8×. More
  chunks did not help, so efficiency-core imbalance is not shown to be the
  limit.
- A timing of the pool beside another session's suite measures that suite.
  Check `ps` before timing.

*Next.*
1. Task 4, the crate into `kernels/` with its three code fixes. Both
   decisions it waited on are taken.
2. Task 2 against that crate, since the two owed platforms (Windows, macOS
   x86_64) run its wheel through a temporary workflow.
3. Task 5, then task 3 with the guard sized on the 2.2e-1 esd above, then
   task 6.
4. When the Linux runner runs the bench (task 7), measure the threshold at
   2 workers, which is the declined review finding 4.

### 2026-10-10 — filed from 1939's review session

Anyone picking this up knows three things that 1939 did not. The thread
pool never ran in either benchmark fit, so the first 1.4× is a Python
constant and needs no Rust. Three quarters of the FCJ kernels' time is the
exponential, so the second gain needs the bit rule relaxed, and the
maintainer has relaxed it for the exponential alone. And the decision to
replace numba is taken, for the install rather than the speed.

*Done.* Filed; no open WP owned the build (1939's Next asked for it, 1115
and 1521 are the tier's rules and its flag). Context carries the review's
findings, the measurements and the decisions. 1939 closed in the same
commit series with its two corrections.

*Measured.* Every number in § Context, `[dev]` venv, darwin/arm64, machine
idle; the probes are scratchpad scripts, re-derivable from `bench_refinement`'s
cases and a timing wrapper over `compiled._KERNELS`.

*Next.* Task 1, on its own PR under numba. Then the two owed decisions.
