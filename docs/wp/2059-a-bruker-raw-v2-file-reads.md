# WP-2059 — a Bruker RAW v2 file reads, checked against two descriptions and one real file

Milestone: unscheduled · Status: 🔄 2026-10-30 — the v2 reader, its writer and the local-only real-file test merged from outside as PR #1202 (`efb1d466`); the maintainer's decision on a Durham licence line is open
Track: The formats a lab still has
Depends on: —
Priority: P3 2026-10-26 — a reader with a workaround (convert elsewhere); the refusal's stated reason, one uncorroborated description, no longer holds

## Goal

`read_pattern` reads a single-range Bruker DIFFRAC RAW version 2 (`RAW2`) file,
with every structural field checked against the file's own size, and refuses
every other v2 shape by name. v1 stays refused.

## Context

**The report (issue #1164, mustachefeeling, 2026-10-25).** The v2 refusal rests on
ATTRIBUTION.md:315: GSAS-II described v2, nothing corroborated it, and "one
uncorroborated description with no file to check it against is how a reader
comes to return a plausible wrong pattern". The contributor supplied the missing
piece: a real public v2 file (`Pbso4.raw`, Durham TOPAS tutorial "Structure
solution - inorganics"; the PbSO₄ round-robin X-ray pattern, Hill 1992), a hand
decode, and the same file read by TOPAS-64 v6 as a black box (background only,
zero iterations), 6001 of 6001 counts identical, 2θ to 5e-7°. A control arm
(TOPAS re-exporting a plain two-column file) showed TOPAS's export does not
round, and two planted changes were found, so a pass is not vacuous.

**Checked at c0e32ab29, 2026-10-26.** The file, fetched from
`https://topas.webspace.durham.ac.uk/wp-content/uploads/sites/261/2021/08/Pbso4.raw`,
is 24 328 bytes, SHA-256
`80e990bc360a3628dca6b0efca3ce03278b00136c4183c2088c0d52041a018d7`. Layout:

| field | offset | type | value |
|---|---|---|---|
| magic | 0 | 4 ASCII | `RAW2` |
| block count | 4 | uint32 LE | 1 |
| block header length | 0x100 | uint16 LE | 68 |
| points n | 0x102 | uint16 LE | 6001 |
| step (° 2θ) | 0x10C | float32 LE | 0.025 |
| start (° 2θ) | 0x110 | float32 LE | 10.0 |
| counts | 0x100 + header length | n × float32 LE | 67 … 15 702, whole numbers, last 368 |

The file ends exactly at 0x100 + 68 + 4n. **GSAS-II 5.8.4 agrees field for
field** (`imports/G2pwd_BrukerRAW.py:65-92`, read as a spec only): block header
at 256, header length and step count as uint16, step and start at +12 and +16,
data at 256 + header length, and the uint32 at 4 as the block count. So two
descriptions and one black-box reading agree. Do not copy GSAS-II's clamp of
counts below 1 up to 1 (`:89-90`). The counts are the file's.

The same pattern is in the tree already: `tests/data/gsas2_pbso4.gpx`'s
`PWDR PBSO4.XRA` (6000 points, GSAS-II licence, `tests/data/README.md:33`).
Against it the RAW counts agree at 5998 of 6000 points. They differ at 143.375°
(RAW 278, gpx 275) and 153.725° (RAW 276, gpx 275), and RAW has one more point
at 160.000° (368). The test pins the RAW values.

**The reader's rules.** Read the data offset from the header-length field,
never a constant. Gates the file can fail: magic; block count = 1 (else refused
by name, "a multi-range v2 file", until one is seen); n > 0; 0x100 + header
length + 4n equal to the file size, as v3's "ranges account for the file
exactly" gate. Return 2θ and counts; σ by the Poisson fallback, as for the
other raw-count readers; the header fields above in `metadata` only through
`METADATA_KEYS`. Header fields not decoded here (wavelengths, temperature) are
not read. `io/CLAUDE.md` § Adding a format and the `bruker_raw` row govern
dispatch, and ATTRIBUTION.md:315 changes from "not implemented" to the two
descriptions and the black-box check.

**Licence.** TOPAS is closed: a black-box measurement only, as WP-1911
records the rule, and nothing of it is committed. GSAS-II: concepts and spec
only (ATTRIBUTION.md:239). `Pbso4.raw` states no licence on the Durham page
(checked 2026-10-26), so it is never vendored.

**Test data.** A writer in the test suite packs v2 from a **literal** offset
table, never importing the reader's constants (the v3 rule,
`tests/writers_xrd.py`), using the gpx's own counts, which are in the tree
under a licence. The real file joins `tests/local_data.py` as a
`durham-topas/pbso4` entry by URL and SHA-256, and a test runs against it only
where it has been fetched, pinning 6001 points, the first and last x and every
count. That pin is a published file's numbers, so it may be committed.

**Tier.** None new: a reader of a format's own fields. Any new diagnostic code
takes its `_audit` row at tier 1.

### Inherited

## Non-goals

- RAW v1 (no description at all).
- Multi-range v2 files, until a real one is seen; refused by name.
- The v2 header's wavelength, anode and date fields: GSAS-II reads them at 168-210, but no second description corroborates them.

## Tasks

- [ ] Decision (maintainer): test data by the literal-offset writer plus the local-only real file (default), or also ask Durham for a licence line.
- [x] The v2 arm of the Bruker reader with the gates above; the refusal text for v1 and multi-range v2.
- [x] `tests/writers_xrd.py`: a v2 writer from a literal table; tests for the positive arm and each gate failing (wrong size, block count 2, n = 0).
- [x] `tests/local_data.py`: the `durham-topas/pbso4` entry; a test pinned to the real file's SHA-256 and counts, skipped where absent.
- [x] ATTRIBUTION.md:315 and `io/CLAUDE.md`'s `bruker_raw` row rewritten; `tests/data/README.md` notes the local-only file.
- [x] Skill: none. A reader that opens a file needs no agent guidance, and the old refusal named no skill row (check `references/` for a "re-export as RAW4" line and remove it if present).

## Acceptance

A synthetic v2 file reads to its literal counts; each gate refuses its broken
twin by name; the real file, where fetched, reads to 6001 points equal to the
pinned counts.

```sh
.venv/bin/python -m pytest tests/test_readers.py -q
.venv/bin/python -m tests.local_data durham-topas/pbso4
.venv/bin/python -m ruff check src tests examples
```

## References

- Hill, R. J. (1992). *J. Appl. Cryst.* 25, 589-610 (the PbSO₄ round robin).
- GSAS-II 5.8.4, `imports/G2pwd_BrukerRAW.py` (spec only).
- Durham TOPAS tutorial "Structure solution - inorganics", `Pbso4.raw`.
- Issue #1164.

## Handover log

- **2026-10-30** (`/pr-review`) — merged from outside as PR #1202 (`efb1d466`) after three rounds. `read_pattern` reads a single-range Bruker RAW v2 file, each field at its named offset, with gates for one block, n > 0, 0x100 + header length + 4n equal to the file size, and a finite non-zero step. Counts are returned as stored, with no clamp to 1. `write_raw2` in `tests/writers_xrd.py` packs v2 from a literal offset table and fills unnamed bytes with `0xA5`, so a field read at the wrong offset fails a gate. Eight mutants of the reader each turn their own test red. The real-file test (`Pbso4.raw`, 6001 points, every count pinned) skips where the file is not fetched, and the file is never vendored. Round 3 corrected the unclaimed-`.raw` message and the `raw_unclaimed` row to say that single-range v2 is read and only v1 is refused, with a test on the wording. It also wrote the v2 axis policy into the `bruker_raw` row with its evidence as it is: one real file and two descriptions, thinner than the `.udf` row's 56. `io/CLAUDE.md` stays at its 561-line cap beside #1138. The collection grew by 11 (`test_readers.py` 202 to 212, `test_readers_robust.py` 87 to 88). Open: the maintainer's choice on asking Durham for a licence line. Gate (a stack of eleven PRs on main `b40bc994`, tree `307eff83`; macOS arm64, `[dev,jax]`, Python 3.12): 13 217 passed, 216 skipped, 48 xfailed, 0 failed, with ruff, the `-W` manual build and the GUI ladder green.

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1164). Checked against the tree at c0e32ab29: the reader refuses `Pbso4.raw` as "Bruker RAW version 2 … only one description of it exists"; the file (SHA-256 as the issue's) decodes as the table above, GSAS-II's description agrees field for field, and the counts match the gpx's X-ray histogram at 5998 of 6000 points. No open WP owns it: WP-1047 and WP-1407 (the vendor formats) are ✅. Next: the test-data decision, then the reader.
