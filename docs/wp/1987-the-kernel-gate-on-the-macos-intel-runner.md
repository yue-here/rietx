# WP-1987 — The kernel gate on the macOS Intel runner

Milestone: unscheduled · Status: ✅ 2026-11-16 — the gate holds the twins on macOS x86_64 again, numpy and SciPy on OpenBLAS there (PR #1599)
Track: The repo's own process
Depends on: —

## Goal

The Kernels workflow's `test macos-x86_64` job passes when the kernels are right, or the
gate says on that runner why a fit cannot be checked. A red job then means a kernel defect.

## Context

**What fails.** `.github/workflows/kernels.yml` runs on a pull request that touches the
kernel crate, `src/rietx/model/compiled.py`, `src/rietx/indexing/dichotomy.py`, the kernel
tests or the bench (its `paths:` list). Its `test` job runs
`examples/aot_spike/bench_aot_kernels.py --cases cpd-1a,trigger --skip 2,3 --gate` on each
wheel's own platform. `--gate` exits 1 unless every kernel was called, every call met its
bar, and each case's fit on the kernels' outputs (the "twins") reproduced the numpy path.
A case whose numpy path does not reproduce itself is reported as `unchecked` rather than
gated (`agreement()`, which fits the numpy path twice to find that out).

**Measured 2026-10-16** (run 38924988380, PR #1017, rietx-kernels 1.3.0, python 3.11.9,
numpy 2.4.6, macOS 15.7.9 x86_64):

| job | cpd-1a twins vs numpy | numpy vs itself | trigger twins vs numpy | gate |
|---|---|---|---|---|
| windows-x64 | bit-identical | (identical) | bit-identical | pass |
| linux-x86_64 | bit-identical | (identical) | bit-identical | pass |
| linux-aarch64 | bit-identical | (identical) | bit-identical | pass |
| macos-arm64 | bit-identical | (identical) | bit-identical | pass |
| macos-x86_64 | 1.6e-02 esd | **4.4e-02 esd** | **2.2e-01 esd** | fail |

On macos-x86_64 every kernel call met its bar (0 past it). The cpd-1a numpy path did not
reproduce itself, so that case went unchecked. The trigger numpy path happened to
reproduce itself in its two runs, so the twins' 0.22 esd gap was gated and failed. The
same job failed with the identical gate line on two unrelated PRs: `pr/solve-kernels-rust`
(job 116958675622, 2026-10-16) and `idx/c4-inlier-acceptance` (job 115989721856,
2026-10-14). PR #1017 only reworded a message in `dichotomy.py`.

**Hypothesis, not measured.** The macOS Intel numpy path is not deterministic run to run on
that runner, so the gate's "reproduced itself" test is a sample of two that passes by chance.
If so, the twins' gap is that noise, and the kernels are not at fault. The candidates are
numpy's BLAS on that wheel (Accelerate on macOS 14+) and its threading. A twins gap of 0.22
esd against a self-gap of 0.044 esd in the other case does not settle it either way.

**Superseded in part, 2026-11-16.** WP-1999 (`214512864`, 2026-11-02) already took the
gate's second branch for the platform as a whole: `bench_aot_kernels.NONDETERMINISTIC`
names macOS x86_64 and the twins' gap is reported there, never gated. The job has been
green on every Kernels run that reached it since (13 of 13 to 2026-11-13, PR #1557's kernels
1.5.0 among them). What that left open is the hypothesis above: the twins are not checked
on that platform at all.

**Measured 2026-11-16** (fork run 43874967910, `macos-15-intel`, i7-8700B with AVX2 and no
AVX-512, python 3.11, numpy 2.4.6, SciPy 1.17.1; five numpy-path fits in one process, as
the gate runs them, pool workers 1):

| BLAS | threads | trigger: distinct results in 5 | cpd-1a: distinct in 5 |
|---|---|---|---|
| Accelerate (the macOS 14 wheels, as installed) | default | 3 | 4 |
| Accelerate | `VECLIB_MAXIMUM_THREADS=1` | 3 | 3 |
| OpenBLAS (the same versions' pre-macOS-14 wheels: numpy `macosx_10_9`, SciPy `macosx_10_14`) | default (4) | 1 | 1 |
| OpenBLAS | `OPENBLAS_NUM_THREADS=1` | 1 | 1 |

The gaps on Accelerate are of the size the gate met (trigger up to 3.0e-06 esd, cpd-1a up
to 1.8e-06, with the same 7 and 9 rows changing esd only). OpenBLAS gives the same digest
at one thread and four. So the source is Accelerate, and not its threading; numpy's and
SciPy's BLAS calls on a fixed 7000 × 30 matrix (`A.T @ A`, `lstsq`, both `svd`s, `eigh`,
`solve`) were each bit-identical 40 times in a row at every alignment, so it is not a call
that misbehaves on every input either.

**Prior art in this repo.** WP-1930 reproduced a Linux-only answer on a Mac by nudging one
start value by 1e-14 relative. The same probe tells a fit that sits on a knife edge from a
kernel that is wrong. WP-1940 built the gate; its record is in its WP file (closed).

## Non-goals

- The kernels' own bars, which held on every platform.
- Making the gate pass by loosening it without a measurement that says why.

## Tasks

- [x] Reproduce on a macOS Intel machine or the runner (a `workflow_dispatch` of
      `kernels.yml` on a branch): run the numpy path of the trigger case five times and
      record whether it reproduces itself. *(2026-11-16: it does not under Accelerate,
      and does under OpenBLAS; Context § Measured 2026-11-16. Run on the fork from a
      probe-only branch, `wp1987-probe`, since a fork's dispatch needs the file on its
      default branch.)*
- [x] If the numpy path is not deterministic there, find the source (BLAS, threads), and
      either pin it for the gate's fits (`threadpoolctl`, an environment variable in the
      job) or make the gate's self-check take enough repeats to see the noise.
      *(2026-11-16: the source is Accelerate, and one Accelerate thread does not pin it,
      so neither listed fix applies. `kernels.yml` swaps numpy and SciPy on that runner
      for the same versions built on OpenBLAS, asserting the swap took, and
      the bench lifts that platform's exemption only when numpy and SciPy are both on
      OpenBLAS, so the gate holds the twins there again and still reports them on
      Accelerate or any other BLAS.)*
- [x] If the numpy path is deterministic and the twins still drift, treat it as a kernel
      defect on x86_64 macOS and bisect the kernels the trigger fit calls. *(2026-11-16:
      not reached. The numpy path is not deterministic under Accelerate; whether the twins
      hold under OpenBLAS is what the restored gate now measures.)*
- [x] Skill: none, the gate is CI-only.

## Acceptance

`kernels.yml`'s `test macos-x86_64` job passes on a PR that touches `kernels/**`, three
runs in a row, or fails with a message that names the platform's non-determinism.

## References

- `examples/aot_spike/bench_aot_kernels.py` (`agreement`, `main`'s `--gate`).
- `.github/workflows/kernels.yml` (`test` job).

## Handover log

- **2026-11-16** — closed. The macOS Intel runner's numpy path does not reproduce itself
  because of Accelerate, the BLAS that numpy's and SciPy's macOS 14 wheels use. The number
  of Accelerate threads makes no difference. With the same versions built on OpenBLAS,
  every fit is bit-identical. So the Kernels test job swaps numpy and SciPy for those
  wheels on that runner, and the gate holds the kernels' twins to the numpy path there,
  as it does on the other four platforms. Since WP-1999 the gate had only reported the
  twins' gap there. A red job on that runner can again mean a kernel defect. An
  Accelerate install, such as a developer's Intel Mac, still gets the report. PR #1599.

  - *Measured*: Context § Measured 2026-11-16 (fork run 43874967910, eight jobs). The
    positive arm held: Accelerate as installed gave 3 and 4 distinct results in 5 fits.
    Acceptance check on the fork (run 43881637331, `wp1987-gate`, this branch's
    `kernels.yml` test job on `macos-15-intel`): three runs with the swap, each reporting `scipy-openblas` for both libraries, each with the twins bit-identical to the numpy path on cpd-1a and on trigger, gated, the job green (`tests/test_compiled_kernels.py` 29 passed in each). The control without the swap (Accelerate) printed NONDETERMINISTIC, measured the numpy path against itself at 3.4e-07 esd (cpd-1a) and 3.0e-06 (trigger), and reported rather than gated, green. That run installed the
    published rietx-kernels 1.5.0 wheel, not one built in the run, because GitHub's macOS
    arm64 runners refused the cross-build for capacity (run 43879055791, "not acquired by
    Runner of type hosted"). `kernels/` is unchanged since the `kernels-v1.5.0` tag. Local,
    `.venv` `[dev]`, macOS arm64, python 3.12, numpy 2.5.5:
    `tests/test_compiled_kernels.py` 28 passed, 1 skipped (one test function added,
    `test_the_exemption_names_the_blas_not_only_the_platform`). `ruff check src tests
    examples` clean. `python -m tests.reader_output` exit 0: unchanged against the
    merge-base `bc77a934e`. The fast and full suites were not run: the branch touches the
    bench, one test file and the workflow, and none of them moves a measured number.
  - *Done*: `kernels.yml` gains a `macos-x86_64`-only step after the install. It
    reinstalls numpy and SciPy at their resolved versions with `--python-platform
    x86_64-apple-darwin` and `MACOSX_DEPLOYMENT_TARGET=13.0`, which selects the pre-macOS-14
    OpenBLAS wheels (for python 3.11 numpy's `macosx_10_9` and SciPy's `macosx_10_14`),
    with no source build allowed, and asserts that both report an OpenBLAS BLAS. In the bench,
    `nondeterministic()` exempts a `NONDETERMINISTIC` platform unless both numpy and SciPy
    name an OpenBLAS (`REPRODUCIBLE_BLAS`), as read by `BLAS` from both libraries'
    `show_config(mode="dicts")`. Any other name, or a build that names no BLAS, stays
    exempt on macOS x86_64. The header line prints the BLAS. No thread pin is set:
    OpenBLAS gave the same digest at one thread and at four.
  - *Review*: a read-only review subagent found no bugs. It made three findings, and all
    were applied: the unknown-BLAS case stays exempt, the test asserts that the BLAS is
    read on the platform it runs on, and the spacing around the new test.
    A second read-only review (on PR #1599, 2026-11-17) made four findings, all applied.
    The swap allows no source build (`--only-binary numpy --only-binary scipy`; `uv pip`
    has no `--no-build-package`), so a missing wheel fails at once by name. The exemption
    is an allowlist, lifted only when both libraries name an OpenBLAS, so conda-forge's
    generic `blas`, `mkl` or a source build's `none` stay reported. The wheel wording names
    the pre-macOS-14 tags. A test drives `_blas()`'s fallback to `"unknown"`
    (`test_a_build_config_that_cannot_be_read_is_unknown_and_exempt`). Local, macOS arm64,
    python 3.12, numpy 2.5.5: `tests/test_compiled_kernels.py` 29 passed, 1 skipped. The
    workflow change is checked only by CI. `MACOSX_DEPLOYMENT_TARGET=13.0` is kept: it
    documents the wheel choice.
  - *Not done*: why Accelerate on that CPU (i7-8700B, AVX2) varies from fit to fit. Every
    BLAS call probed on a fixed 7000 × 30 matrix was bit-identical 40 times at all eight
    alignments, so the variation needs inputs the probe did not build. It does not reach
    the gate any more. No issue was filed: nothing in rietx is wrong, and Rosetta 2 does
    not show it (WP-1999).
  - *Generality*: not dispatched. `_audit.py` is unchanged, and the one new rule
    (`NONDETERMINISTIC`) is in the CI bench under `examples/`, not in the package.
  - Next: nothing for this WP. If GitHub retires `macos-15-intel`, or numpy or SciPy stops
    publishing pre-macOS-14 x86_64 wheels, the swap step fails by name (it allows no source
    build) or its assert does. The choice
    then is between dropping the platform from the gate and restoring WP-1999's report.

- **2026-10-16** — filed at the maintainer's request from WP-1985's PR (#1017), where the
  job failed on a message reword. No open WP owns the kernel gate: 1939, 1940, 1959 and
  1966 name it and are all closed, and a closed WP takes no fold.
