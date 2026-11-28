# WP-2319 — a jax test returns its memory when it ends

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P3 2026-11-28 — a cost-only item: the fast suite passes either way, and the memory it returns is a Linux workstation's at `-n 8`; CI's runners are unmeasured

## Goal

After each test that reached jax, `tests/conftest.py` frees the compiled
executables and returns the freed pages to the OS, so the fast suite's peak
memory at `-n 8` on Linux falls from about 26 GB to about 14 GB with the same
pass, skip and xfail counts.

## Context

Issue #1847 (mustachefeeling, 2026-11-25), a proposal with measurements.

**What holds the memory.** `make_jax_jacobian` jits a new closure per call,
and jit embeds the model's arrays in the compiled executable (the module
docstring of `backend/jax_backend.py` says so). Those executables stay
referenced until `jax.clear_caches()`. Freed, glibc keeps the pages, so the
resident size barely moves until `malloc_trim(0)` returns them. The reporter
measured that either half alone does almost nothing.

**The reporter's numbers** (commit `0e79e455f`, a 32-core Linux workstation
under WSL2, glibc 2.43, Python 3.12.14, jax/jaxlib 0.11.2, fast suite at
`-n 8 --dist loadgroup`, 15909 passed, 291 skipped and 30 xfailed in every
arm). They are the reporter's and are not reproduced on this tree:

| after each jax test | suite peak RSS | worst worker at end | wall |
|---|---|---|---|
| nothing (today) | 26.2 GB | 5.0 GB | not comparable |
| `gc.collect()` + `malloc_trim(0)` | 25.2 GB | 5.1 GB | 314 s |
| `gc.collect()` + `jax.clear_caches()` + `gc.collect()` + `malloc_trim(0)` | 14.2 GB | 1.9 GB | 327 s |

"A jax test" was every test in `test_backend_jax.py` plus the `[jax…]`
parametrisations of `test_cross_backend.py`, 92 tests. Those 92 left 16.3 GB
behind across 8 workers; `test_jacobian_matches_analytic[jax-toy_body]` alone
left 4.5 GB. The other ~16 100 tests left about 0.7 GB a worker. The wall
cost is about 4 %, small because conftest note 2's persistent compile cache
(`tests/.jax_cache`) turns each recompile into a disk read. On an arm64 Mac
the same sequence, with `malloc_zone_pressure_relief` in place of the trim,
moved the end RSS by about 0.2 GB (4.3 → 4.1 GB), so the gain is a glibc one.

**The shape.** An autouse fixture beside conftest note 3's figure autoclose,
which closes figures only when pyplot was imported, so the tests that never
plot pay nothing. This one acts only when the test reached jax. Two keys are
on offer: `"jax" in sys.modules` plus the item, or `tests/jax_cases.reaches`,
the reader CI's `--jax-cases` selection already uses (conftest note 5). The
second is one authority for "reached jax" and is the convention to take.
After the test: `jax.clear_caches()`, `gc.collect()`, then `malloc_trim(0)`
through `ctypes.CDLL("libc.so.6")`, guarded to Linux and wrapped so a
non-glibc libc (musl) skips it. A `gc.collect()` after every test would cost
more than it saves.

Checked against the tree at `02341ffdb`: nothing under `tests/` or `src/`
calls `clear_caches` or `malloc_trim`; conftest notes 2, 3 and 5 are as the
issue describes them.

No source module changes. The tier of the one rule added (when to free) is
none: it is test hygiene, not a heuristic in the package.

### Inherited

## Non-goals

- Changing `make_jax_jacobian`'s per-call jit. That is a speed question for
  the jax backend, and the closures are what the agreement matrix tests.
- Sizing CI's `-n` or its runners. That follows the measurement here.

## Tasks

- [ ] Measure the baseline first on this tree: the fast suite's peak RSS on
      Linux at the `-n` a developer uses and on CI's `--jax-cases` job, with
      counts. If CI's jax job peaks well inside its runner's memory, say so
      and keep the change for local runs only.
- [ ] The autouse fixture in `tests/conftest.py`, keyed on
      `tests/jax_cases.reaches`, with its note in the module docstring.
- [ ] Tests: the fast suite's counts unchanged (passed + skipped + xfailed,
      exactly), and the peak RSS before and after on Linux, quoted with venv
      and platform.
- [ ] Skill: none. Test hygiene changes nothing an agent driving rietx does.

## Acceptance

The fast suite's counts are identical before and after, and its peak RSS on
Linux falls, both quoted with venv and platform in the handover.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_backend_jax.py tests/test_cross_backend.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #1847, with the reporter's probe described there (per-test RSS from
  `/proc/self/status`, peak after resetting VmHWM through
  `/proc/self/clear_refs`).
- glibc `malloc_trim(3)`; jax `jax.clear_caches`.

## Handover log

- **2026-11-28** — created, from the 2026-11-28 issue triage (issue #1847).
  Checked against the tree at `02341ffdb`: no `clear_caches` or `malloc_trim`
  anywhere under `tests/` or `src/`, and conftest's notes 2, 3 and 5 hold as
  quoted. No open WP owns it: WP-2036 (the nightly legs) owns a full suite
  that finishes, not its memory, and no other open WP touches `conftest.py`'s
  hygiene. Next: the baseline task, since CI's own numbers decide whether
  this is worth a fixture there.
