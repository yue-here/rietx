# WP-1002 — CI matrix

Milestone: v1.0 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- CI: linux + macOS, Py 3.11-3.13 (+3.14 allow-fail); `[jax]`/`[torch]`
  optional jobs; nightly heavy validation with fetched data

## Inherited

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — the "fetched data" in
the scope above has a known obstacle:

- **iucr.org is behind a Cloudflare JS challenge.** Every QARR round-robin
  pattern was retrieved through the Internet Archive, URL form
  `web.archive.org/web/2020id_/…/QARR/col/<name>.prn`. A fetch-on-demand job
  needs the same route; pointing it at the live site will fail in a way that
  looks like a network flake.
- **The `slow` marker is the load-bearing runtime knob.** Full suite is ~2 min
  (was ~21 s before the real-data acceptance landed); `-m "not slow"` stays
  ~20 s. That split is what makes a per-push job viable and a nightly job
  necessary — 23 tests are currently `slow`.

From **WP-0404** (cross-backend Jacobian CI, landed 2026-07-24):

- **The `[jax]`/`[torch]` optional jobs have their target file.**
  `tests/test_cross_backend.py` is the (method × config) Jacobian-agreement
  matrix; every backend row self-skips when its package is absent, so the *same
  command* is green on a numpy-only job and covers more on an extras job. There
  is no separate "with extras" invocation to configure — install the extra and
  the rows activate. A numpy-only job still runs the central-FD and
  fp32-column-policy rows (the WP-0403 policy is not a backend and needs no
  install), so the file is never a no-op.
- **Both runtime figures above are stale**, measured 2026-07-24 on an M-series
  laptop: the full suite is **~13 min** (not ~2 min) and `-m "not slow"` is
  **~85 s** (not ~20 s). WP-0404's matrix accounts for ~42 s / ~22 s of those;
  the rest accumulated across v0.3's real-data acceptance and the v0.4 jax
  tests. CLAUDE.md has been corrected. The per-push/nightly split the scope
  above assumes still holds, but size it from a fresh measurement — the numbers
  have drifted by 6× once already.
- **jit compile, not flops, is what the jax rows cost.** The matrix caches one
  built Jacobian callable per (config, backend) so the fp32 row reuses the
  compiled one — halved that file's runtime. A CI job that shards these tests
  across workers loses the cache and pays every compile again.

From **WP-0408** (torch backend, landed 2026-07-27) — the `[torch]` extra above
is no longer hypothetical, and it splits into two jobs, not one:

- **`[torch]` activates the `torch` and `torch+fp32` rows** of
  `tests/test_cross_backend.py` plus all of `tests/test_backend_torch.py`, by the
  same self-skip mechanism as jax — install the extra, the rows appear. No
  separate invocation.
- **But the Apple-GPU tests cannot run on a hosted runner.** Every
  `torch-mps` assertion is gated on `torch.backends.mps.is_available()`, which is
  False on GitHub's macOS runners (virtualised, no Metal device). So the MPS
  claims — the only *real-hardware* evidence for WP-0403's fp32-column policy —
  are **maintainer-machine-only**, exactly like `examples/validate_cuda_mixed_
  precision.py` is CUDA-box-only. Either accept that as a documented gap or plan
  a self-hosted runner; do not read a green macOS job as "MPS verified".
- **torch is a ~500 MB wheel** (jax is ~100 MB). If the extras job is
  per-push rather than nightly, cache it deliberately; it will dominate job
  setup otherwise.
- **Both runtime figures above moved again, and one moved *down***: measured
  2026-07-27 with all extras installed and v0.4 complete, the full suite is
  **8 min 34 s** (505 tests, 38 `slow`) and `-m "not slow"` is **~90 s** —
  faster than the ~13 min recorded three days earlier *despite* adding the torch
  matrix, the true-Voigt tests and the restraint suite. Machine state moves these
  as much as the test count does. Re-measure; do not trust any number here.

From **WP-0401** (op shim, landed 2026-07-24): `tests/test_backend_shim.py`
asserts **bit-identity** against environment-pinned npz goldens in
`tests/data/backend_goldens/`. A multi-OS × multi-Python matrix is exactly the
thing that breaks bit-identity (BLAS variants, libm differences). Decide up
front whether those goldens are pinned to one canonical job or relaxed to a
tolerance elsewhere — the re-baseline rule is in `tests/data/README.md`
(regenerate via `python -m tests.test_backend_shim`, only from a green tree).

## Tasks

- [ ] Expand this stub into a full WP before starting

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
