# WP-1315 — a zip of patterns is N scans

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Track: One file, many patterns
Depends on: —
Priority: P3 2026-09-23 — a reader nobody is waiting for; members open one at a time

## Goal

A plain `.zip` whose members are patterns this build can read is a
`zip_collection`: members enumerate as scans, selected with the existing
`scan=` idiom, each read by recursion into normal dispatch — the way a
multi-range `.raw` is N scans, with a weaker manifest. As a side effect, a
real mis-dispatch dies: STORED zips are no longer claimed by the GSAS text
sniff.

## Context

From issue #134.

**Prior art is already in tree.** `.rasx` and `.brml` are zip containers
(`io/rasx.py`, `io/brml.py`) with capped member reads
(`MAX_MEMBER_BYTES`, `read(cap+1)`, never `extract()`), a `scan=` option and
`list_scans` returning `ScanInfo`. This proposal is the same shape with a
weaker manifest: a plain zip has none, so **the member-name list is the only
membership authority** — in contrast to `.rasx`, where `root.xml` overrides
names.

**Two measured behaviours motivate it.** Against a real archive
(3802 members, 1372 `.fxye`, DEFLATE, 327 MB; read-only, no vendoring
grant): `identify_format` refuses cleanly — correct under the current
registry, but 1372 patterns are unreachable without extracting to disk,
which the container rules in `io/CLAUDE.md` exist precisely to avoid. And a
latent bug on STORED (uncompressed) zips: the first member's `BANK` text
lands inside the 4 kB head sniff, `gsas.looks_gsas` claims the whole
archive, and `read_gsas` chokes on the `PK\x03\x04` bytes with "could not
convert string to float". A zip entry placed ahead of the text sniffs fixes
both — the manifest evidence is stronger than a loose-text sniff, per the
ordering rule.

**Design points, all from the issue.** Dispatch after `RASX`/`BRML` (claim
only if neither did — no `root.xml`/`DataContainer.xml`) and only if at
least one member is claimed by another registered format. `scan=k` indexes
format-claimed members in sorted name order; directory entries, dotfiles and
lock files (the archive carries a `.~lock…#`), and unclaimed members are
skipped, never counted — `scan=k` addresses the k-th *pattern*.
`scan` ⇔ `scans` biconditional; `label` is the member name, never "Scan N",
because the name is what the file itself says; `scan_count` travels in
metadata from a single directory read. σ and axis authority stay entirely
with the inner format — the container adds none.
`PATTERN_MULTISCAN_DEFAULTED` fires on member 0, because a 1372-way choice
must not be silent. Refusals name the `.zip` and how many patterns it
holds, never a bare `zipfile`/`struct` exception.

**Fixtures are synthetic only** (no vendoring grant for the real archive): a
small inline zip with two trivial readable members, one directory entry and
one unreadable dotfile — proving name-sorted enumeration, skip of
non-patterns, `scan=` selection, out-of-range refusal, and the STORED zip
no longer mis-claimed. Real-file facts recorded `tests/data/README.md`-style
without the files.

## Non-goals

- **Not nested containers** (zip-in-zip, tar), not ordering by anything but
  name — a temperature ramp's ordering is a catalogue concern, read from
  each member's own header, and stays outside the reader.
- **Not a `member="name"` selector** beside `scan=` — two vocabularies for
  one meaning.
- **Not writing or repacking.**
- **Not the bang-path syntax** (`path.zip!member`) or any zip-handle cache —
  local to the catalogue that prototyped this.

## Tasks

- [x] The `zip_collection` entry: dispatch position, membership-by-claim,
      sorted-name `scan=`, capped member reads, refusals naming the zip.
- [x] The STORED-zip fix asserted directly: a zip whose first member is
      GSAS text is claimed by the zip entry, not by `looks_gsas`.
- [x] `ScanInfo` labels = member names; `PATTERN_MULTISCAN_DEFAULTED` on
      member 0; `scan_count` in metadata.
- [ ] `capabilities()` formats arm, `help.py` reader-option coverage if any
      option is added, manual line in the data chapter, skill row.
- [ ] Synthetic fixtures + `test_readers_robust.py` arm; the real-archive
      facts as a README row.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_reader_zip.py tests/test_readers_robust.py   # first module is new, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: the two-member fixture enumerates exactly its patterns in name
order, `scan=` selects and refuses out-of-range by name, member 0 defaults
loudly, and the STORED-GSAS fixture is read as a zip — with every inner σ
and axis decision demonstrably the inner reader's.

The shipping PR carries `Closes #134`.

## References

- Issue #134 — the measurements, the design points, and the archive facts.
- `src/rietx/io/CLAUDE.md` — container rules, dispatch ordering, the σ and
  axis authorities this must not duplicate.
- `io/rasx.py` / `io/brml.py` — the container precedents (capped reads,
  `scan=`, `ScanInfo`).

## Handover log

- **2026-09-01** — created, from issue #134 (2026-09-01 triage). Settled:
  membership by claim over sorted names, dispatch position, the STORED fix;
  no open design decisions — the first task is the entry itself.
