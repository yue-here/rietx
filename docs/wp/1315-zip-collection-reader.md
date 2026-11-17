# WP-1315 — a zip of patterns is N scans

Milestone: unscheduled · Status: ✅ 2026-11-16 — PR #1592; follow-ups in #1593
Track: One file, many patterns
Depends on: —

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

The tier of each rule this WP adds (written 2026-11-16, at close): the dispatch position and
the claim of an archive that cannot be opened are tier 1, the bytes settling it; membership by
claim and sorted-name order are tier 3, ours (issue #134's design, adopted 2026-10-11); reading
member 0 by default is the shared `PATTERN_MULTISCAN_DEFAULTED` convention, whose row is still
unaudited; passing the other reader options on is the caller's. The generality review's
verdicts are in the 2026-11-16 handover entry.

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
- [x] `capabilities()` formats arm, `help.py` reader-option coverage if any
      option is added, manual line in the data chapter, skill row.
- [x] Synthetic fixtures + `test_readers_robust.py` arm; the real-archive
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

- **2026-11-17** — decisions-walk item 1 made in #1592: a member claimed only by the ASCII
  catch-all or by the `.cif` suffix counts as a pattern only on content evidence (a row of
  two numbers; a `_pd_meas`/`_pd_proc`/`_pd_calc` tag), and is skipped otherwise.
  `zip_collection._has_profile`; `tests/test_reader_zip.py` gains the log, parameter-file and
  structure-CIF case and a pdCIF case. Item 2 stands as settled: member 0 is read, with
  `PATTERN_MULTISCAN_DEFAULTED`.

- **2026-11-16** — closed by a ghostshift runner; PR #1592, follow-ups in #1593.

  A plain `.zip` of pattern files now opens with `read_pattern` without being extracted:
  each member another reader claims is one scan, in sorted member-name order, and the
  member's own reader decides its σ and axis. The stored-zip mis-dispatch of #134 is gone:
  a stored zip whose first member is GSAS text used to be claimed by the GSAS reader and
  fail on the archive's bytes, and it now reads as a zip. What the spec's claim rule costs
  is now visible too: the ASCII reader claims any text, so a log or a README among the
  members counts as a pattern and refuses on read, and the generality review rated that rule
  and the member-0 default weak. Both are the maintainer's to rule, in #1593.

  *Done.* `src/rietx/io/formats/zip_collection.py`, registered after `brml` and above
  every text sniff. Membership by claim through the registry's own order (without this
  format); a refusal's claim, a nested plain zip, an empty member, a directory entry
  (`\`-terminated too), a dotfile and a member past the 128 MB container cap are skipped and
  not counted. A member is staged to a private temporary file one at a time (every reader
  takes a path; the name never becomes a path), read by its reader, and deleted. A member
  that cannot be decompressed claims the archive so the read refuses naming it; a member
  holding several scans of its own is refused by name, since `scan=` already selects the
  member. Inner messages and diagnostics are rewritten to name `<member> in <zip>`, never
  the staged file. `metadata` keeps the inner reader's keys, with `source_file` the
  member's full name and `scan`/`scan_count` the archive's. `axis`, `bank`, `block` pass to
  the member's reader; `nonpositive_sigma` is ruled by `read_pattern` as for every format.
  `read_pattern`'s post-read checks now quote the reader named in `metadata["format"]`
  (a container's member reader; for every other format the same one as before). No reader
  option added, so `help.py` is unchanged; `capabilities()` reads the registry.
  Tests: `tests/test_reader_zip.py` (new, 30), a stored-zip arm in the robustness harness's
  synthetic set and a `zip_collection` row in its non-finite classification;
  `test_readers.py::test_a_zip_that_is_not_a_rasx_is_not_claimed` now expects the member
  refusal, since a zip of one text member is a zip collection. Docs: `pattern-files.md`
  (table row, note, `scan`), the `io/CLAUDE.md` row (cap 572 → 573), the skill's Reading
  data sentence, `tests/data/README.md` § Zip collections, the 1.12.0 release note.

  *Measured.* `test_a_stored_zip_of_gsas_text_is_a_zip_not_a_gsas_file` fails on the parent
  (origin/main bc77a934e: `identify_format` → `gsas`, `read_pattern` raises on the FXYE
  bank holding `PK\x01\x02…`). Fast selection on a Linux x86-64 workstation ( the shared rietx-py312 venv, `-m "not slow" -n 8 --dist loadgroup`, tree 94a6a8e12, run as a co-tenant beside four other jobs): 14890 passed, 280 skipped, 32 xfailed, 0 failed, 619 s, 6.1 GB peak, 741 % CPU on 8 cores. The branch adds 40 tests (30 in `test_reader_zip.py`, 10 in `test_readers_robust.py`: the synthetic zip arm and nine non-finite cases); no baseline was run for the exact delta, which CI's main run gives.
  `tests.added_test_times` on that junit: the 28 named tests of `test_reader_zip.py` (30 cases) cost 0.08 s together, none in the tail.
  Canary (same tree, `-n 4`, the reader, robustness, readers, capabilities, audit, help and
  docs-consistency files): 610 passed, 1 skipped, 44 s, 442 MB, 160 % on 4 pinned cores.
  `tests.reader_output`: exit 0, unchanged against bc77a934e. Full selection not run: no
  measured number can move (a reader for a format nothing read before).

  *Review.* A read-only review agent read the branch (the runner rules forbid
  `/code-review`, which edits the main checkout). Fixed in 94a6a8e12: a corrupt LZMA member
  escaped as `LZMAError` from `identify_format` (392 of 2643 fuzzed variants); two members
  of one name read the last twice; a multi-scan member's own "pass scan=" advice selected an
  archive member and its count was overwritten; the staging path and name leaked into
  refusals; the post-read checks quoted the zip, losing the centidegree hint. Not taken:
  listing an unreadable member in `list_scans` rather than failing the listing (a
  `ScanInfo` has no field to say why, and NaN ranges break the GUI's JSON) — in #1593 with
  the claim rule it follows from; a cheaper claim from bounded heads (the cost is stated in
  the module docstring instead). The `rasx`/`brml` `NotImplementedError` the review found
  predates this WP and is #1593 item 3.

  *Review fix-ups* (a second read-only review of the PR, 2026-11-16). A short member name
  was rewritten inside other words of a message, and a quoted staged path was rewritten
  twice (`… in readme.zip in readme.zip`); the staged name is now replaced in one pass and
  only where it stands whole. `test_nothing_is_left_on_disk` now asserts that staging used
  the directory it inspects. The PR also opened a second route to #1593 item 3: a nested
  zip of version 7.0 is sniffed by `rasx`/`brml` on every read of the outer archive, so
  `scan=0` on a good member crashed. Item 3's one-class fix (`NotImplementedError` in both
  sniffs) is applied here, with a test that fails without it.

  *Gotchas.* The ZipExtFile reads at most the declared size and checks the CRC, so the
  `len(raw) > cap` branch is defensive only (a lying header fails as a bad CRC, refused by
  name). An `.xlsx`/`.docx` is now a zip collection refused through a member.

  *Generality* (the `generality-review` definition, run as a general-purpose Opus agent;
  its sections below with line numbers dropped, otherwise unedited; no `fails`). Author's
  answers under the weak verdicts: membership and member 0 are the WP's adopted design and
  go to the maintainer in #1593; item 4's three gaps (a)–(c) were fixed in 94a6a8e12.

  ### `zip_collection` dispatch position, and claiming a zip that cannot be opened (`io.formats.PATTERN_FORMATS`, `zip_collection.looks_zip_collection`)

  **Verdict: holds.** The case for acting is stronger: the position only affects files that start with zip magic, and none of the readers below it reads a zip. The one side effect worth recording is under item 2: almost any zip with a text member now passes the gate.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | "after `rasx`/`brml`, above every text sniff, since a *stored* archive shows its first member's text to them" (`io/CLAUDE.md` row; `formats/__init__.py` comment). Unreadable zip: "claimed, so its refusal names it as a zip" (`looks_zip_collection` docstring) | It decides which reader opens a file beginning `PK\x03\x04` that neither vendor manifest claims. A truncated zip is refused as "begins like a zip archive but is not a readable one". | holds |
  | 2. Kind of ambiguity | none given (no audit row; the table cannot see dispatch order) | Kind 1. The magic bytes settle it, and every reader below this entry (`ras`, `uxd`, `xrdml`, `udf`, `pdcif`, `gsas`, `chi`, the refusals, `xy`) recognises text or a first line, never a zip. | holds |
  | 3. Case against | none given | One weak case. A zip carrying `root.xml` or `DataContainer.xml` anywhere in its tree, which `rasx` (Rigaku) or `brml` (Bruker) then declines, is still refused by this entry (regex `(^|/)root\.xml$`). It falls through to the text sniffs, so the #134 stored-zip mis-dispatch (the `gsas` reader claiming the archive) survives for that sub-case. Truncated zips: a recovery tool such as `zip -FF` would salvage the members. rietx refuses instead, which moves no number. | weak case |
  | 4. Case for | the #134 measurement: a stored zip of one `.fxye` was claimed by `gsas` and failed with "could not convert string to float" (WP file § Context; re-run on 7d9be3cb in the issue comment) | Verified by `test_a_stored_zip_of_gsas_text_is_a_zip_not_a_gsas_file` (README: "fails on the parent commit") and `test_an_archive_that_stops_early_is_refused_by_name`. Before this change the crash named no file, against CLAUDE.md's rule that a reader raises naming the file. | strong |
  | 5. Tier | none given | Tier 1 (the bytes) for both the position and the unreadable-zip claim. No program default applies. `docs/practice.md` has no entry on archives (grep). | tier 1 |
  | 6. Families | synthetic only; one real archive measured read-only (`tests/data/README.md` § Zip collections) | One real archive, deflated, which "never showed" the stored case. The stored case is synthetic. That is enough for a kind-1 dispatch rule. | adequate |
  | 7. What says it fired | `identify_format(...).name == "zip_collection"`; `DataRef` records the claiming format | Correct: the claiming format is recorded. | holds |

  Evidence that would change the verdict: a zip that a format below `zip_collection` should legitimately claim.

  ### Membership by claim: which members count as scan k (`zip_collection._claim`, `_skipped`, `_candidates`, `_member_bytes`)

  **Verdict: weak.** The case against is stronger as built. `xy` (the ASCII catch-all) claims any non-binary text, and `pdcif` claims any `.cif` by suffix. So "a member a reader claims" means "any text member", and `scan=k` addresses the k-th pattern only in an archive with no companion files. Two of the author's own choices also differ from the issue.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | "`scan=k` reads the k-th pattern in sorted name order … skipped, and never counted, so that `k` addresses a pattern and not a byte-blob" (module docstring) | It decides what counts as a pattern and in what order. Skipped without any record: directory entries and dotfiles (WP's choice); members claimed by a refusal (`dif_peaklist`, `peak_list`, `total_scattering`, `raw_unclaimed`); nested plain zips; members past 128 MB (author's choices). | — |
  | 2. Kind | none given | Membership is kind 1 where a reader truly recognises the format (`gsas` BANK, `ras` first line). It is not kind 1 where the claim is `xy`'s "not binary" or `pdcif`'s suffix. Those are the cases the docstring concedes ("a log … counts as one, and reading it refuses"). Order is a convention (kind 3: the archive states none). | partly mis-kinded |
  | 3. Case against | the docstring concedes text members count; the WP lists natural ordering as a non-goal | (a) **Companion text counts.** `.instprm`, `.prm`, `.log`, `.txt` and structure `.cif` files are all claimed. Codepoint order puts uppercase `README.txt` before lowercase pattern names, so k shifts and member 0 can be a non-pattern. (b) **The gate admits almost any zip.** `.xlsx`, `.docx` and `.odt` are zips of XML text, which `xy` claims, so they are now claimed and refused with a message naming a member such as `[Content_Types].xml`. The old refusal listed what the build reads. `tests/test_readers.py::test_a_zip_that_is_not_a_rasx_is_not_claimed` was edited to accept exactly this change ("member 'notes.txt'" in place of "Supported"). (c) **Asymmetry.** A refusal-claimed member is skipped, but a log is counted and refused. The skipped kind carries the more informative message. A zip of `.gr` files (total scattering) or of `.raw` files from an unknown vendor now gets "holds no member a reader in this build claims", losing the `total_scattering` and WP-1407 six-vendor explanations. (d) **Oversize members.** The issue says "refuse past `MAX_MEMBER_BYTES`". The code skips them. It trusts the archive's declared size to skip, and the docstring says "a lying archive then hides one". (e) **Order.** Plain codepoint sort puts `T_100K` before `T_20K`, whereas Finder and Explorer sort numerically. GSAS-II, as I recall, extracts a zip member the user picks from a list. I recalled that and did not check it in this repository. | substantive |
  | 4. Case for | "the member-name list is the only membership authority" and "stable and inspectable" (issue #134; WP § Context) | Name order is stable and reproducible, and `list_scans` shows each label, so a caller can see what k means before choosing. Skipping dotfiles covers the real archive's `.~lock…#` and macOS `__MACOSX/._*` files. A real 1-D pattern over 128 MB is about 1000× a large one ("7001 points is 100 kB", `rasx.py`), so the oversize skip rarely matters. | moderate |
  | 5. Tier | none given | Tier 3, rietx's own (from the WP and issue). No program default was checked. `docs/practice.md` has nothing. | tier 3 |
  | 6. Families | one real archive: "3802, of which 1372 are GSAS `.fxye`" (README) | **Not measured where it matters.** The reader was never run on that archive. Only `identify_format` on main was, so the `scan_count` it would report there is unknown. Neither the README nor the issue says what the other 2430 members are. If they are text, `scan_count` is not 1372. Synthetic fixtures only; one family. | not shown |
  | 7. What says it fired | `list_scans` labels; `metadata["scan_count"]` | No field or code says how many members were skipped or why. Visibility comes only from comparing `list_scans` with the archive listing. | weak |

  Evidence that would change the verdict: `scan_count` and the first five `list_scans` labels on the #134 archive, read in place. Alternatively, a claim rule that leaves out the `xy` catch-all and the `pdcif` suffix match, or counts and refuses refusal-claimed members as it already does text members.

  ### Reading member 0 when `scan` is not given (`read_zip_collection` → `base.multiscan_default`; `PATTERN_MULTISCAN_DEFAULTED`, the warning that scan 0 of N was read because none was named)

  **Verdict: weak.** The case for (the convention six multi-scan formats share, with a warning that names `list_scans`) is real. The case against is stronger here than for a vendor file: member 0 is whichever name sorts first, and under item 2 it can be a non-pattern.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | "a 1372-way choice must not be silent" (WP § Context) | It reads the alphabetically first claimed member and warns at `level="warning"`. | — |
  | 2. Kind | none given; the code's row is `Row("PATTERN_MULTISCAN_DEFAULTED", "code")`, still on `UNAUDITED_BASELINE` | Kind 3. Which pattern of a ramp the caller wants depends on the purpose, which the archive cannot state. | row unaudited |
  | 3. Case against | none given | In a `.raw` or `.xrdml`, range 0 is the instrument's own first measurement. In a zip, member 0 is a person's naming accident, and with companion text it may be a README that raises on read. A refiner handed 1372 patterns would not pick the first by codepoint. Refusing when N > 1 and `scan` is None, with the count and a pointer to `list_scans`, costs one call. | substantive |
  | 4. Case for | "as every multi-scan format does" (dispatch brief) | Convention: DESIGN.md § Rules, 5 favours one shape, and `bruker_raw`, `rasx`, `brml`, `ras`, `uxd` and `xrdml` all default and warn. The warning carries N and suggests `list_scans`. A one-member archive stays silent (`test_a_single_pattern_archive_reads_without_a_default_warning`). | moderate |
  | 5. Tier | none given | Tier 3, rietx's own. No program default checked. | tier 3 |
  | 6. Families | none | No real archive read. | none |
  | 7. What says it fired | `PATTERN_MULTISCAN_DEFAULTED`, `metadata["scan"]="0"` | Fires (`test_reading_member_zero_by_default_is_loud`). | holds |

  Evidence that would change the verdict: member 0 of the #134 archive turning out to be a `.fxye`, or the audit of `PATTERN_MULTISCAN_DEFAULTED` itself ruling the default-and-warn shape kept for every format.

  ### Passing `axis`, `bank`, `block` and `nonpositive_sigma` on to the member's reader (`_read_member`; `ZIP_COLLECTION.options`)

  **Verdict: weak.** Passing on the options the caller named holds. Three consequences the author did not flag are the stronger evidence, and each breaks the claim that "every inner σ and axis decision [is] demonstrably the inner reader's".

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | "The other reader options (`axis`, `bank`, `block`) are handed on to that reader and reported there when it does not take them" (module docstring) | The options pass on as stated. `nonpositive_sigma` is popped in `read_pattern` and applied to what comes back. An option the member's reader does not take raises `READER_OPTION_IGNORED` (an info code saying an option was not applied) at the member level. | holds |
  | 2. Kind | none given | Kind 1: the caller named the options. | holds |
  | 3. Case against | none given | (a) **`scan` cannot reach the member.** The archive consumes it, so a member that holds several scans (`.rasx`, `.brml`, `.ras`, `.uxd`, `.xrdml`, which the author admits as members) is only ever readable at its scan 0. Its own `PATTERN_MULTISCAN_DEFAULTED` then fires naming the staged file, and its suggestion "Pass scan=<0…N-1>" selects an archive member instead. `test_a_vendor_container_inside_is_a_pattern` uses a single-scan `.rasx` and so cannot see this. (b) `metadata.update(scan=…, scan_count=…)` overwrites the member reader's own `scan`/`scan_count`, so the inner count disappears. (c) The post-read axis check in `read_pattern` (`_axis_diagnostics`) runs under the zip's format. Its centidegree hint is gated on `fmt.name == "xy"`, so a BANK-less GSAS member read by `xy` loses the "divided by 100" lead. The refusal names the zip and not the member, and offers `axis='tof'` because the zip lists `axis`, even when the member's reader (`gsas`) does not take it. | substantive |
  | 4. Case for | tests `test_the_other_reader_options_reach_the_member_reader`, `test_an_option_the_member_reader_does_not_take_is_reported_there`, `test_the_nonpositive_sigma_rule_applies_to_a_member`, `test_every_sigma_and_axis_decision_is_the_member_readers` | Verified for single-scan members. Refusing the options would cost the caller a dead end. | holds for single-scan |
  | 5. Tier | none given | Caller class for the passing-on itself, since the caller named each option. The three gaps are defects, not tiers. | caller |
  | 6. Families | synthetic | — | — |
  | 7. What says it fired | `READER_OPTION_IGNORED` at the member level; `metadata["declared_axis"]` | Present for the options passed on. Nothing says a member's inner scans were not offered. | partial |

  Evidence that would change the verdict: a test with a two-scan `.rasx` or `.xrdml` member showing its scan 1 reachable (or refused by name), and the member's `scan_count` kept beside the archive's.

  ### Skill sentence in `docs/skill/make_api_index.py`, Reading data paragraph (rendered into the three `references/api.md` copies)

  **Verdict: holds.** It names a verb (`rx.io.readers.list_scans`) and an option, and it warns an agent off unzipping to disk, which is what Rule 4 asks of a skill row. It leaves out the one trap an agent would hit.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides unasked | "A plain `.zip` of pattern files is N scans: `scan=k` reads the k-th member a reader claims, in name order, and `rx.io.readers.list_scans` labels each by its member name." | Prose, not code; it decides nothing. It sits in `api.md`, which every session loads whole. | — |
  | 2. Kind | n/a | Describes behaviour. | — |
  | 3. Case against | none given | The package's own output already covers most of it: `capabilities()` lists the format, and the `PATTERN_MULTISCAN_DEFAULTED` suggestion names `list_scans`. Per WP-1338 (the skill's cheapest-place rule), that leaves the sentence's own value as "a zip is readable at all". It omits the trap from items 2 and 3: text and `.cif` members count, and codepoint order can make member 0 a non-pattern. "A member a reader claims" is literally true, but an agent will not read it that way. | minor |
  | 4. Case for | the skill's Reading data paragraph already routes on dispatch-by-content | It stops an agent from extracting to disk, the cost #134 measured. Short. | holds |
  | 5. Tier | n/a | Not tiered; the audit cannot see skill prose (`_audit` docstring). | — |
  | 6. Families | n/a | — | — |
  | 7. What says it fired | n/a | — | — |

  Evidence that would change the verdict: a run in which an agent handed a zip with a README reads member 0, gets a refusal, and does not recover. If the item 2 claim rule stays, the sentence should name that trap.

- **2026-09-01** — created, from issue #134 (2026-09-01 triage). Settled:
  membership by claim over sorted names, dispatch position, the STORED fix;
  no open design decisions — the first task is the entry itself.
