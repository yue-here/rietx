# WP-1316 — a NeXus/HDF5 multi-scan reader, behind an extra

Milestone: unscheduled · Status: 🔄 2026-11-16 — reader, extra and σ tiers in PR #1607; the Poisson self-check and follow-ups in #1618
Track: One file, many patterns
Depends on: —
Priority: P3 2026-09-23 — a reader nobody is waiting for; the reel exports as files

## Goal

`read_pattern` opens a NeXus/HDF5 file (`.nxs`/`.h5`) — typically an in-situ
reel, one 2-D block of N patterns against a shared 1-D axis — as N scans
under the existing `scan=`/`ScanInfo` idiom, behind a `rietx[hdf5]` extra,
with the axis and σ policies reused verbatim from `io/CLAUDE.md`. No new σ
machinery, no new axis rule.

## Context

From issue #135.

**Dispatch is first and structural**: the HDF5 magic
`\x89HDF\r\n\x1a\n` at offset 0. Today `.nxs` is refused by `looks_binary`
at the `xy` catch-all — unreadable by this build; h5py is not a dependency.

**Authority tiers, cheapest first.** NeXus application definitions
(NXsxrd/NXmonopd) and `NXdata` with `@signal`/`@axes` where declared are the
structural, trusted tier — a schema-named `@axes` cannot disagree with
itself. Attribute-less HDF5 falls back to axis-discovery heuristics **plus
`PATTERN_X_AXIS_ASSUMED`**, because that is inference. The three-way axis
rule applies unchanged: recognisably 2θ reads silently; recognisably
something else (a Q axis, an ω rocking curve, a φ pole-figure ring) raises
naming what the file holds; unrecognisable reads as 2θ and says so.

**A private prototype establishes the rules and is ported, not copied**
(`probe_nexus`, maintainer-local): walk with `h5py.visititems` for a 1-D
numeric dataset whose length matches a block dimension, strictly monotonic,
with a plausible 2θ span (0 ≤ x0 < 180, x1 ≤ 180, span > 5°) or Q span
(0 ≤ x0 < 30, x1 ≤ 30, span > 1 Å⁻¹); the matching axis length picks the
block orientation. These discriminators are also what reject the ML trap — a
naive "2-D and big enough" test would swallow 1290 256×256 weight matrices.
A Poisson self-check (adjacent-channel difference std ≈ √(2·mean); measured
0.39 against ~13 on a simulated file) flags synthetic data — **at most a
diagnostic, never a refusal**.

**σ tiers, reused verbatim**: explicit `errors`/`NXdata@uncertainties` when
present (structural, trusted); Poisson √max(y,1) for a counts block;
**withheld with `PATTERN_INTENSITY_SCALED`** where the block is a rate or
the scale cannot be verified. Plus `ScanInfo` per row, `scan=` selection,
`PATTERN_MULTISCAN_DEFAULTED` on scan 0, refusals naming the `.nxs` rather
than an h5py exception, and the WP-1110 item-17 rule: a series coordinate is
surfaced on `ScanInfo` only where the format names it, never invented off an
unnamed axis.

**The extra can only add** (the numba precedent in `io/CLAUDE.md`): there is
no `rietx[slow]` that installs fewer formats, so `rietx[hdf5]` pulls h5py
and enables this one format, the base install stays lean, and
`capabilities()` reports the format only when h5py imports. Unlike numba —
required, because the numpy fallback runs the same expressions — there is no
pure-python HDF5 fallback, so h5py gates the format rather than
accelerating a path.

**Fixtures are synthesized, never vendored** (~1290 archive `.nxs`/`.h5`
exist and none may ship): h5py packs the NeXus structure literally — an
`NXdata` group with `@signal`/`@axes`, a small 2-D block, a 1-D 2θ axis,
sharing no constants with the reader — or files come from the NeXus
standard's own examples with licence checked per file. Real-file facts
(block shapes `(3134, 2051)`, `(27, 3590)`; the discriminators; the
counts-vs-synthetic check) go in `tests/data/README.md` without the files.

**The extra is `hdf5`** (the reporter's answer on #135, 2026-10-12, folded
from `### Inherited` on 2026-11-16): it names the dependency (h5py), not the
application definition, since the reader also takes attribute-less HDF5
through axis discovery and `nexus` would describe less than it reads. The
`_about.py` token is `HDF5_EXTRA`.

- The tier of each rule this WP adds ([generality § The rule](../milestones/generality.md#the-rule)):
  the 0°/180° ends of a found 2θ axis are physics (tier 1); the span floors
  (`MIN_TWO_THETA_SPAN_DEG` 5°, `MAX_Q_PER_ANGSTROM` 30, `MIN_Q_SPAN_PER_ANGSTROM`
  1) are new judgement (tier 3), from the maintainer's prototype on the
  archive's ~1290 HDF5 files (issue #135), one family by lab. They decide
  which dataset the **search** tier takes as the axis — never a declared one —
  and every reading they admit carries `PATTERN_X_AXIS_ASSUMED`; a found axis
  that fits Q but is too narrow for 2θ is refused naming both readings. Among
  declared axes the abscissa is a 2θ name, else the one name the axis rule
  refuses, else an unclassified axis only where nothing else could be one (a
  1-D signal's, or the sole one on a 2-D signal's last dimension, NeXus's
  fastest-varying, tier 3); two unknown axes are refused. No action on the data, no default, no new
  code: the σ tiers and the axis rule are the existing ones.

### Inherited

- **2026-11-17, from the issue triage round (issue #1446).** Decided
  2026-11-16 by the maintainer: raw time-of-flight reduction (per-pixel event
  or histogram NeXus, vanadium, empty can, grouping) is out of scope. WP-2146
  carries the named refusal of a raw `.nxs` and the "focus with Mantid" how-to.
  When this reader lands, a raw spallation run must still be refused by that
  message. Recognising one needs the NeXus structure (an `NXevent_data` group,
  or per-pixel detector data without a focused `NXdata`), which only h5py can
  read, so the distinction lives here once h5py is present.

## Non-goals

- **Not detector-image HDF** — an `NXdetector` frame stack is not a profile
  (the `.brml` `RecordedRawDataView` precedent).
- **Not general HDF5 ingestion** — the span discriminators are the fence.
- **Not Q → 2θ conversion** — needs a wavelength the reader must not assume;
  a recognisable Q axis raises, naming it.
- **Not NXcanSAS, not writing.**
- **Stays local to the maintainer's catalogue**: series assembly, the
  synthetic-suspect campaign flag, ramp subsampling.

## Tasks

- [x] The extra: `[hdf5]` in `pyproject.toml`, soft import, `capabilities()`
      formats arm gated on the import; the format token spelled in
      `_about.py`.
- [x] The reader: magic dispatch, tiered axis authority, block orientation,
      `scan=`/`ScanInfo`/`PATTERN_MULTISCAN_DEFAULTED`, refusals naming the
      file.
- [x] σ tiers.
- [ ] The Poisson self-check as a diagnostic.
- [x] Synthetic fixtures + `test_readers_robust.py` arm + the README facts
      row; skill row and manual line.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_reader_hdf5.py tests/test_readers_robust.py tests/test_capabilities.py   # first module is new, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: with h5py absent the build imports, refuses the format by name and
reports it unavailable; with it, the declared-`@axes` fixture reads
silently, the bare-HDF5 fixture reads with `PATTERN_X_AXIS_ASSUMED`, a Q-axis fixture raises naming Q, and a 256×256 matrix is
refused.

The shipping PR carries `Closes #135`.

## References

- Issue #135 — the design, the prototype's rules, the archive facts.
- The NeXus format standard (NXdata, NXmonopd) — https://www.nexusformat.org.
- `src/rietx/io/CLAUDE.md` — the σ tiers, the axis rule, the extra
  precedent; WP-1110 item 17.

## Handover log

- **2026-11-16** — first slice, PR #1607 (ghostshift runner). `read_pattern`
  now opens a NeXus/HDF5 in-situ reel as N scans when h5py is installed
  (`pip install 'rietx[hdf5]'`), and without it recognises the file and refuses
  it by name with that line, where it used to fall to the ASCII reader as
  "binary". A file that declares its patterns (`NXdata` `@signal`/`@axes`) is
  trusted; one that declares nothing is searched and always says the axis was
  assumed; a Q, d, ω, φ, radian or temperature axis is refused rather than read
  as 2θ. The Poisson self-check is not built; it and six smaller follow-ups are
  issue #1618.
  - *Done:* `[hdf5]` extra (h5py ≥ 3.8; also in `[dev]` so CI runs the tests),
    `_about.HDF5_EXTRA`, `PatternFormat.requires`, `ReaderCapability.available`
    / `.requires` (the format stays listed, `available=False`, rather than being
    dropped — the acceptance's "reports it unavailable"), `io/formats/hdf5.py`
    third in dispatch, `tests/test_reader_hdf5.py` (33), `tests/writers_hdf5.py`,
    the robust harness's `hdf5`/`hdf5_bare` truncation arms and `hdf5` non-finite
    row (+11), the manual's pattern-files rows, the io/CLAUDE.md row, the skill's
    `PATTERN_X_AXIS_ASSUMED` row, the `tests/data/README.md` facts section. A
    read-only review found two silent misreads (a temperature taken as x; a 2θ
    in radians read as degrees), both fixed with tests, plus pyFAI's
    unit-suffixed names, a float legacy `@signal`, non-finite ranges in
    `list_scans`. The generality judge's findings: span discriminators *weak*
    (one family; the narrow-span refusal now names both Q and a narrow 2θ
    window), `_x_dim`'s last-dimension fallback *weak* (now refuses two unknown
    axes, or one on the first dimension), tie-break and σ *hold*; it recommends
    walking `hdf5.py` in `_audit.WALKED` (a question for the maintainer below).
  - *Measured:* fast selection on the final tree (d6c106076), `[dev]` + h5py 3.16.0,
    darwin/arm64, `-n 4`, beside other sessions' work (the workstation was
    memory-saturated: two co-tenant runs not admitted in 20 and 12 min):
    14730 passed, 432 skipped, 32 xfailed, 0 failed, 14:28. This session adds
    44 tests, all passes with h5py present: 33 in `test_reader_hdf5.py` and 11
    `hdf5` rows in `test_readers_robust.py`; without h5py all 44 skip (the module
    and the arms `importorskip`). `tests.added_test_times`: 0.14 s over the
    27 functions, none near the tail. Workstation canary (`923890c77`, 7 files):
    607 passed, 1 skipped, 1 failed (this branch's `io/CLAUDE.md` cap, fixed).
    `python -m tests.reader_output`: exit 0, unchanged.
  - *Gotchas:* `io/CLAUDE.md` is at its 572-line cap (`test_docs_consistency`);
    the row fitted by joining one wrapped paragraph. The workstation's shared venv has no
    h5py: the prcheck installed it `--no-deps --target` into the job dir and
    put that on `PYTHONPATH`, leaving the venv alone.
  - *Open question for the maintainer:* should `io/formats/hdf5.py` join
    `_audit.WALKED`? Then `MAX_TWO_THETA_DEG` is tier 1 and the three span
    floors tier 3 (grounds: the prototype's archive family, one by lab; every
    reading they admit warns), each needing your dated approval.
  - *Next:* the Poisson self-check (#1618 item 1), which needs a code and an
    audit row; then a way to choose among several `NXdata` groups (#1618 item 2).

- **2026-09-01** — created, from issue #135 (2026-09-01 triage). Settled:
  tiers, discriminators, the extra's shape; first open item is the extra's
  name (`hdf5` vs `nexus`) and the format token.
