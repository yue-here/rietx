# WP-1987 — The kernel gate on the macOS Intel runner

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Track: The repo's own process
Depends on: —
Priority: P3 2026-10-16 — a red check on the PRs that touch the kernel paths; not a required check, and no fitted number is shown wrong

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
| OpenBLAS (the same versions' macOS 10.13 wheels) | default (4) | 1 | 1 |
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
- [ ] If the numpy path is not deterministic there, find the source (BLAS, threads), and
      either pin it for the gate's fits (`threadpoolctl`, an environment variable in the
      job) or make the gate's self-check take enough repeats to see the noise.
- [ ] If the numpy path is deterministic and the twins still drift, treat it as a kernel
      defect on x86_64 macOS and bisect the kernels the trigger fit calls.
- [ ] Skill: none, the gate is CI-only.

## Acceptance

`kernels.yml`'s `test macos-x86_64` job passes on a PR that touches `kernels/**`, three
runs in a row, or fails with a message that names the platform's non-determinism.

## References

- `examples/aot_spike/bench_aot_kernels.py` (`agreement`, `main`'s `--gate`).
- `.github/workflows/kernels.yml` (`test` job).

## Handover log

- **2026-10-16** — filed at the maintainer's request from WP-1985's PR (#1017), where the
  job failed on a message reword. No open WP owns the kernel gate: 1939, 1940, 1959 and
  1966 name it and are all closed, and a closed WP takes no fold.
