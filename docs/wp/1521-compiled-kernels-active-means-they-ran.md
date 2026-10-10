# WP-1521 — `compiled_kernels_active` says the kernels ran, per tier, or says it does not know

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1508 declined it at review, for a signal both tiers report)
Priority: P4 2026-10-10 — moot once PR #864 merges: WP-1940 does its whole Goal, and it closes as 🛑 then

## Goal

`capabilities()` never reports a compiled tier as active once its build has
failed. It reports the model tier and the indexing tier separately, because
their builds can fail separately, and before anything is built it says that
it has not been.

## Context

**The flag.** `capabilities.py` sets `"compiled_kernels_active":
compiled.enabled()`, and its comment says a client asks it "why is this build
slow". `model.compiled.enabled()` is read once and cached from the
`RIETX_COMPILED` switch and `available()`, which asks whether numba imports.
It never learns whether a build succeeded.

**Two tiers, two latches, one flag.**
- *Model tier* (`model/compiled.py`). `_kernels()` catches a failed
  `_kernels_numba.build()` and sets `_UNAVAILABLE`, so a **later**
  `available()` reads `False`. But `enabled()` keeps the `True` it cached
  before the failure, so `compiled_kernels` flips to `False` while
  `compiled_kernels_active` stays `True`.
- *Indexing tier* (`indexing/dichotomy._traversal_kernels`, WP-1508). It is
  built lazily on first dichotomy use under its own `_KERNELS_FAILED` latch,
  and it declines to the numpy loop. Neither `available()` nor `enabled()`
  sees that latch, so both flags can read `True` while every search runs
  numpy.

WP-1508's review found the second gap and declined it there. The model tier's
flag has the same gap, and the fix is "a signal both tiers report, not a
branch here".

**Two constraints on the fix.**
- **A capability query must not compile** (`capabilities.py`'s own comment;
  the indexing build is 4.4 s cold). Before a build the honest answer is "not
  built yet", which is `None` rather than `True`. That is root CLAUDE.md's
  rule that a field's empty state must not read as an answer (WP-1076).
- **The field is a versioned contract's member.** `capabilities()` is quoted
  by clients and meta-tested (every `*_version` field, every arm from a live
  registry, `_SURFACE_FLAGS` against `__all__`). A per-tier shape is a
  change to what a client reads. Keep `compiled_kernels_active` meaning what it
  says, or deprecate it through `docs/manual/using/compatibility.md` the way
  that page describes, and state which in the release note.

**Why the rate is low.** numba is a required dependency, so this fires only on
an install where it imports and a build fails (both builds are
`pragma: no cover`). No fit's number moves, since both tiers are held
bit-identical to their numpy paths or to a stated bar. What is wrong is a
report about speed.

### Inherited

- **2026-10-10, from WP-1940 (4th session, PR #864).** This WP's whole Goal
  lands with that PR. The indexing traversal lost its compiled path, so one
  compiled tier is left. Its import is the build, so `compiled_kernels` and a
  build cannot disagree. A decline warns once a process, and
  `Capabilities.compiled_kernels_unavailable` says why. Close this WP as 🛑,
  superseded by 1940, once #864 merges.

- **2026-10-10, from WP-1939 (amended the same day by its review, now
  WP-1940).** The numba model tier is being replaced by a Rust wheel
  (1940 § Decisions). Nothing is then built at run time, so "a build failed
  after import succeeded" cannot happen in the model tier. The question does
  **not** go away: it moves to "the wheel is absent, or its `KERNEL_ABI`
  mismatches, and the fit ran the numpy path in silence", which is the same
  failure one import earlier. 1940's task 5 makes that decline warn once and
  reach `capabilities()`. The indexing tier's half stands until its kernels
  move. Read 1940 § Context before starting here, and fold this WP into 1940
  if 1940 lands first.
- **2026-10-10, from WP-1940 (3rd session).** numba now leaves all three
  tiers at the migration (1940 § Decisions item 8), so the indexing tier's
  half goes too: the traversal runs its numpy loop, and nothing is built at
  run time anywhere. Once 1940's `compiled.py` PR lands, nothing here is
  left that 1940 does not do. Fold or close this WP then.

## Non-goals

The tiers' fallback behaviour (correct as it is: decline, never raise, one path
a process). The `RIETX_COMPILED` switch. Making a capability query build
anything.

## Tasks

- [ ] One reading per tier, e.g. `built()` → `True | False | None`: the latch
      each tier already keeps, exposed. `enabled()` stays the hot-path switch.
- [ ] `capabilities()` reports both tiers without compiling. Tests: a forced
      build failure in each tier (monkeypatch `_kernels_numba.build` to raise)
      reads `False` for that tier and leaves the other alone; a fresh process
      reads `None` before any build.
- [ ] `docs/manual/using/install.md` (which says the flag "is whether the next
      refinement will use it", and runs it in a python block); a
      release-note line.
- [ ] Skill: `references/diagnostics-indexing.md`'s speed-flag paragraph
      quotes `features["compiled_kernels_active"]`. Reword it, then re-sync
      the copies with `rietx skill --install . --copy`.

## Acceptance

After a failed build no flag reads active for that tier. Before any build no
flag claims one ran.

```sh
.venv/bin/python -m pytest tests/test_capabilities.py tests/test_compiled_kernels.py tests/test_indexing_kernels.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

WP-1115 (the model tier and its flags); WP-1508 (the indexing tier; the
declined review finding); WP-1007 (`capabilities()`); WP-1076 (a field's empty
state).

## Handover log

- **2026-09-28** — filed from WP-1508's review, where it was declined for a
  signal both tiers report.
