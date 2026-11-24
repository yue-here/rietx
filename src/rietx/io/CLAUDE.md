# CLAUDE.md — src/rietx/io/

Scope: the **pattern readers** — how a file is claimed, what a reader may
repair, where σ comes from, and the per-format rules. The clauses that change
behaviour *outside* this subtree stay in the root CLAUDE.md (§ Invariants);
everything here is detail a session working under `io/` needs and nobody else
does. Measured stories and provenance are elsewhere: `docs/wp/1047-*.md` for
the decisions, `tests/data/README.md` for what each fixture can prove, each
format module's docstring for its own measurements, `ATTRIBUTION.md` for the
licence fences.

The organising rule: **one module per format**, because a format's spec
citation, its parser, its `sniff`/`sigma` prose, its options and its licence
fence are one fact each and ten fences in one file drift. `readers.py` is the
front door only (`read_pattern`, `identify_format`, `list_scans`), so adding a
format never moves a call site.

## Dispatch

`PATTERN_FORMATS` is an **ordered** tuple and the order is behaviour — the
first format whose `matches` returns True reads the file. Strongest evidence
first: magic bytes and container manifests, then a required first line or XML
root, then suffix, then a loose text sniff, then the ASCII catch-all **last**.
Binary-claiming formats go first so nothing tries to decode their bytes.

Every text sniff goes through `base.head()`, a bounded 4 kB read (WP-1047). It is deliberately **not cached**:
`restage` re-reads the same path, so a path-keyed cache would be a correctness
hazard for exactly the file a user just replaced. There are **two stated
exemptions**, of two different classes, so the next format to want one sees
which it is asking for. **`.chi`'s count check is O(N)**, behind a bounded
shape gate, and buys what the shape cannot: that format against the catch-all.
**`gsas`'s `TIME_MAP` escalation is bounded** — one further `head(p, 64 kB)`,
only once a `TIME_MAP` token is seen in the first 4 kB, because such a step
table can push a real file's first `BANK` past the window (`formats/gsas.py`).
So that dispatch stays bounded in file size, the invariant the 4 kB bound
holds, and a bounded escalation behind a shape gate is the cheaper class,
reached for before a second O(N) one.

`xy` is not total (`matches = not looks_binary(head)`), so `identify_format`'s
terminal refusal is reachable and its message is **built from the registry**.

## What a reader may repair

Root CLAUDE.md's rule — a silent correction is a reader's to make, and only
where the deviation is a *report* rather than a *contradiction* — applied to 2θ
order in `base.ascending()`, the one place it lives:

| deviation | verdict | action |
|---|---|---|
| NaN or ±inf in 2θ, count or σ | report — the file states no value there; a zero monitor's division writes one | drop the row **first**, `PATTERN_ROWS_DROPPED` naming the 2θ runs; no finite row left → **raise** |
| σ ≤ 0 | report — no weight; ruled once, on `read_pattern`'s hook, never by a reader (WP-1952) | keep the value, leave the channel out of the fit (`PatternData.in_range_mask`), `PATTERN_SIGMA_NONPOSITIVE`; `nonpositive_sigma="poisson"` weights it √max(y, 1), silently, the caller having asked; no positive σ at all → the column is not read |
| strictly descending | report — the same measurement stored backwards; reversal is lossless | reverse, `PATTERN_SCAN_REVERSED` |
| duplicate 2θ, equal y | report — a format artefact | drop the repeat, `PATTERN_DUPLICATE_POINTS` |
| duplicate 2θ, **different** y | contradiction — averaging invents a datum, dropping picks one | **raise**, naming the 2θ |
| non-monotone (stitched, restarts) | contradiction — concatenate, sort or separate are three measurements | **raise**; name `scan=` only where the format has it |
| non-constant step | neither | nothing — stitched regions are legal (SRM 660c) |

The finite-row drop (`base.finite_rows`, WP-2079): **a reader's decisions before
`ascending` skip non-finite values and drop none of their rows**, so the report
sees every one. pdCIF keeps σ = +∞ (its zero-weight marker), Bruker RAW refuses
(stride evidence), and `pattern_data` refuses whatever non-finite value is left.

`ascending(..., fmt=)` takes the format so the non-monotone refusal names
`scan=` **only** where the option exists: telling someone to select a scan in a
file that cannot hold several is a wrong instruction, not a vague one.

## Refusals

A reader raises `ValueError`/`OSError` **naming the file**, never its parser's
exception — container parsers otherwise raise `struct.error`,
`zipfile.BadZipFile` or `ET.ParseError`, the last a `SyntaxError` subclass that
escapes `preview_pattern`'s allowlist as a 500. Each parser converts at its own
boundary, and `base.pattern_data()` is that boundary **at the schema** too: a
`PatternData` validator is the last one every reader crosses, and its pydantic
report names a field rather than a file.

`test_readers_robust.py` keeps this true — every real fixture truncated at many
offsets, plus a synthetic arm for formats with no vendorable file. Run it before
believing a new parser (WP-1047).

A **container** adds one more: nothing is extracted to disk and no member is read
whole on trust. `ZipInfo.file_size` is a number in the archive's *own* header, so
each member is read `read(cap + 1)` and refused past `rasx.MAX_MEMBER_BYTES`, and
`extract()`, which writes files, is never called. A file's size says nothing
about a member's (`formats/brml.py`). The member read converts
`rasx.MEMBER_READ_ERRORS` (shared with `.brml`): besides `BadZipFile`, `zipfile`
raises `NotImplementedError`, `RuntimeError`, `zlib.error` and
`lzma.LZMAError` there, none of them a `ValueError` (issue #1593).

`PatternFormat.refuses` marks a format recognised **in order to be declined** —
a `.dif` peak list is not a profile. One field rather than a side table, so
`capabilities()` stays honest without `reader_formats` meaning two things.

**A refusal claims only what its evidence allows, and its registry position is
part of the claim** (WP-1407). Four cases: matched on **content** (`dif`'s hkl
triple) asserts what the file is; matched on the **suffix** (`peak_list`, no
sample of `.pks`/`.udi` obtainable) says in the message that it matched the name
and not the columns, and gates *negatively* — refuse unless the file reads as a
plain two-column profile, which keeps `.dif`'s escape for a misnamed scan; a
**fourth**, a format whose content cannot be told from a profile (a bare G(r)
export is two plain columns), may be refused on its **name** alone, the message
saying only that the name matched and that renaming the file gets past it
(`total_scattering`'s `_SUFFIXES`); and claiming **nothing** (`raw_unclaimed`)
names `.raw`'s six vendors and picks none, the likeliest one having no
description in any licence (`formats/raw_unknown.py`). A claims-nothing entry
goes **below the ASCII catch-all**, so it can shadow no reader — asserted as a
property (`xy` last *of the readers*, everything after it a refusal), never as
an index.

## Options

Two levels: `READER_OPTIONS` is the build-wide vocabulary, `PatternFormat.options`
the subset a format honours, and `set(READER_OPTIONS) == ⋃ fmt.options` is a
meta-test. That split is what makes a **typo** (raises) different from an option
this format does not take (dropped, and *reported* as `READER_OPTION_IGNORED` —
a UI carrying a value across a change of file is normal, an API caller who
passed `scan=2` believed they selected something). `DataRef` records the
**effective** options, because those are what re-opening must replay.

`fmt.scans` and `"scan" in fmt.options` are held in **biconditional** by
meta-test: a format that lets a caller choose must be able to say what there is
to choose between. Reading scan 0 by default is never silent —
`base.multiscan_default()` emits `PATTERN_MULTISCAN_DEFAULTED`.

## σ, and how much a file's own word is worth

`PatternData.sigma` is the file's esds when it has them; `None` means the
Poisson fallback √max(y, 1), which is **correct** for raw counts and wrong by
√t for anything already divided by a counting time. So a rate gets a *derived*
σ — `base.sigma_from_cps()`, written √(y·t)/t rather than √(y/t) so a channel
that counted zero gets the same floor a counts channel gets.

Which of the two a file holds is decided by **what kind of declaration it
makes**, and the three cases are the whole rule:

- **Structural** — trusted. `.uxd` names the unit in the token that opens the
  data block (`_2THETACOUNTS` / `_2THETACPS`) and `.xrdml` in a schema-enumerated
  attribute *on* the data element, where neither can disagree with itself
  (verified on the real fixtures, `tests/data/README.md`).
- **Free text** — measured, not trusted, by `base.sigma_by_arithmetic`: counts
  are integers, and a rate times its counting time is. Both Rigaku formats
  declare the unit this way and real files of each get it wrong (v1.0 record).
- **Neither settles it** — σ is **withheld** with `PATTERN_INTENSITY_SCALED`,
  never faked. The caveat says the fallback is being applied to a quantity whose
  scale could not be verified.

Deriving the counting time is part of this: `.uxd` gives `_STEPTIME` in seconds
directly, `.ras` gives a speed whose **unit** must be read (`deg/min`, so a step
÷ speed in minutes — assuming seconds would make every σ wrong by √60), and a
header that states no unit leaves the time *unknown* rather than defaulted.

The counting time is not the only scale, so a format that scales twice
**composes rather than branching**: the Poisson quantity is the raw count `c`,
the stored value is `y = c·s` for a scale the reader can *name*, and `s ≡ 1` is
raw counts and gets no σ. `base.sigma_from_scaled` is that; `.xrdml` composes an
attenuation factor with `1/t`.

**An attenuator's convention is measured, never adopted** — four formats have
one and they have given three different answers. The test is the same each time:
find a file where the factor *varies*, and ask which of the raw series and the
product runs continuously through the transition. `.xrdml` **applies** it;
`.brml` leaves the values alone and puts the factor into σ only; the two Rigaku
formats **report** without deciding, because no obtainable file has a varying
column. Numbers in `tests/data/README.md` and WP-1047. Whichever way it lands,
σ goes through the factor — √counts·a is not √y, which GSAS-II's 1/y weighting
gets wrong.

**A σ identical on every point is reported and kept** (`PATTERN_SIGMA_CONSTANT`,
WP-1332), on the same hook as the dead-channel check and for its reason: it
makes the fit unweighted whichever reader produced it. `xy` adopts any
positive third column, so a placeholder there became σ in silence (#266).

## The stored number need not be the measured one

σ above is about a *scale* a reader can name. `.rd` is the sharper case: the
stored `uint16` is **√-compressed**, `counts = v²//100` (WP-1407), and read raw
it yields a profile with every peak in the right place and every intensity
wrong — which no reader can see in its own output and no truncation harness can
catch. Three rules generalise (measurements: `tests/data/README.md` § Philips):

- **A format may encode its counts, and only a real file says so.**
- **The permissive description can be the defective one.** PyXRD's BSD-2
  `rd_parser.py`, the source a port would legally start from, is wrong three
  ways (`formats/philips_rd.py`). A licence says what may be copied, never what
  is right, so a description is checked against a file before it is believed
  and the file settles a disagreement between two.
- **A format's own redundancy is the gate to reach for**, ahead of any invented
  check — `.rd` states its length twice and its maximum once, `.udf` states its
  point count two ways. Disagreement is **refused, not repaired**: a wrong parse
  there puts the 2θ of every point in doubt.

## The axis is never trusted

Most vendor files are **not powder scans**, and a block marker is not evidence
either (v1.0 record, `.uxd`). A non-2θ scan parses perfectly and refines to a
confidently wrong cell, so every format that states an axis uses one policy:

- recognisably 2θ → read, silently;
- recognisably a **neutron flight time in µs** → read as a TOF pattern
  (`PatternData.tof`), silently — the second quantity the container holds;
- recognisably something else → **raise**, naming what the file actually holds
  (a q or d axis, a rocking curve, a pole-figure ring);
- unrecognisable → read as 2θ **and say so** (`PATTERN_X_AXIS_ASSUMED`).

**The second row is declared, never inferred** (no *value* can decide it: a GSAS
**bintype**, a stated `xy` unit or the caller's `axis=` on `xy` settles it, a bare
mention with no unit takes the fourth row). `base.pattern_data(..., axis=...)` is the only way one is
declared (default `"two_theta"`); `gsas` refuses a file whose banks are not
all one axis kind. **A bank is a detector and picking one is the caller's**:
`read_gsas(path, bank=n)` selects by the file's own `BANK` number, and
several banks with no `bank=` are refused by name. `gsas_banks(path)` lists a
bank it cannot open rather than failing the listing; not `scan=`, since a bank
is a detector, not a range of one experiment.

**A format stating no axis at all is a fourth case and emits nothing** (WP-1407,
`.udf`, following `.xy`): the policy is for formats that *have* a field to
classify, and a warning firing on every file of a format trains people to
ignore it. The assumption goes in `sniff`, where a UI shows it, and rests on
evidence (the real `.udf` files are all powder scans, `tests/data/README.md`).

The policy is `base.check_axis()` and the **classifying is not part of it**: the
authority differs per format and is always the field that *means* the axis —
`.chi`'s line-2 label, `.ras`'s `*MEAS_SCAN_AXIS_X`, `.uxd`'s `_DRIVE`,
`.xrdml`'s `scan/@scanAxis`, `.raw`'s flagged drive record — and those are
inputs of five different shapes. So each format classifies for itself and passes
the verdict in; a sixth adds a vocabulary, never a row to a shared table. And
where a format states the axis **twice**, both statements are asked and have to
agree: `.raw`'s scanned drive is the record that is flagged *and* parked at the
range's start angle, neither being trusted alone. One code for every format,
because the operator's answer is identical in every case (WP-1047).

**The range is checked once, for every format, on `read_pattern`'s
post-dispatch hook** (WP-1332). Past 180° raises; at or below 0° reads and
reports `PATTERN_X_AXIS_IMPLAUSIBLE`. The split is § What a reader may
repair's: a contradiction raises, a report says so. It exists because the
classifying above cannot see a *unit* (a centidegree axis that fell to `xy`).
A new format inherits it and adds no range check of its own. It abstains on a
flight-time axis, which violates the bound by construction and was declared
rather than assumed.

## Metadata

`METADATA_KEYS` is **data**, and `base.metadata()` refuses an undeclared key,
because two consumers *match* on these keys — the import wizard's anode
pre-selection and a preview's scan count — and neither can match on a name each
reader spells for itself. `scan_count` travels from the **single** read, so a
preview never parses a file twice; `list_scans` is for the CLI and the scan
picker, not the preview path.

A file's own wavelength is **recorded, never used**: the anode presets are the
authority on wavelengths, and the files' own values differ from them by a few
ppm, far inside what acceptance allows (WP-1047).

The **series coordinate is metadata too, and it is a reader's to surface**
(WP-1110 item 17): on an in-situ run it is the point of the experiment, so a
caller with no `x=` for `refine_sequential` has nothing to plot a trajectory
against. It travels twice, because it is asked at two times — in
`PatternData.metadata` after a scan is read, and on `ScanInfo` (and in its
`label`) before one is chosen, since the ranges of a reel scan the same axis
over the same angles and enumerate as N identical rows without it. Surface only
a coordinate the **format itself names**: `.raw` v3's range header has a
temperature field, and Rigaku's `CW_Temperature*` axes are the cooling water.
Reading a specimen coordinate off an axis named for something else is inventing
a convention, which is the one repair a reader may never make.

## Per format

| format | claimed by | σ | notes |
|---|---|---|---|
| `bruker_raw` | one of four magic strings at offset 0 — **first**, being the only entry whose sniff names the format *and* its version | measured by arithmetic; neither version declares a unit, and the counting time is **ms** in v4, seconds in v3 | multi-range; **nothing is located by counting and nothing is a fixed stride** — v4 is walked to EOF and strided by `datumSize`, v3 by `data_record_length` past `total_size_of_extra_records`, v2 (WP-2059) by four bytes from the header length at 0x100, with 0x100 + header length + 4n equal to the file size and a block count of 1 (a multi-range v2 file is refused by name; counts are never raised to 1). **v2 states no axis, so it is § The axis is never trusted's fourth case and emits nothing**: its block header has no scan-type or drive field, so a non-2θ v2 file would read as 2θ silently. **v1 is named and refused**: no description of it exists. v3's global gate — the declared ranges must account for the file — judges the leftover by **content, not length**: a range read at the wrong offset leaves counts behind and counts are not zeros, so a zero pad is admitted and any non-zero tail past one datum's slack still refuses, naming its first byte's offset |
| `philips_rd` | magic `V3RD` or `V5RD` at offset 0 — **second**, on the same footing as `bruker_raw` and disjoint from it by construction (`.raw` has six vendors, `.rd` two) | the Poisson fallback, and no arithmetic test: the √ encoding establishes that the decoded quantity is a count | single-scan. **Intensities are √-compressed**, `counts = v²//100`, truncating like xylib and the kit's own converter (§ The stored number). Data at **250** for V3 and **810** for V5. Three gates, all the file's own redundancy: `len == data_start + 2n`, `n == round((end−start)/step) + 1`, and `uint16@136 == max(v)`. **V5 is read on the length gate alone and says so when it fails**: no V5 file is obtainable, but `n` comes from header fields, so the gate tests the header offsets *and* the data start jointly and a wrong 810 cannot shift a pattern silently. `.sd` is that V5, not a separate format, so there is no by-name refusal for it. The anode code at 85 is the one enumerated field carried into the pattern (`suggest_instrument` matches on it, and λα1 states it again); the diffractometer and focus codes decode, but no `METADATA_KEYS` entry means an instrument model and nothing would consume one |
| `udf` | both of `DataAngleRange` and `ScanStepSize` present as `Key,Value,/` lines in the bounded head — the two the parser needs to build an abscissa at all, so a file matching them is a `.udf` or is nothing | the Poisson fallback; the format declares no intensity unit anywhere, and the real files' values are whole | single-scan; not a legacy format (a PANalytical Aeris on sale today writes it). **A value may contain commas** (`Title1`), so a line splits on the *first* comma only, and an empty value (`Title2,,/`) is a present key. The abscissa is reconstructed from the range and the step, never stored, so the point count is the gate. The block is a bare marker line (`RawScan`) then comma-separated integers terminated by `/`, the comma before it optional. **`ScanStepTime` is not seconds per step** on a PIXcel-class detector and nothing is derived from it. **No axis field**, so no `PATTERN_X_AXIS_ASSUMED` (§ The axis is never trusted) |
| `rasx` | a zip holding a `Data<N>/Profile<N>.txt` member | the same arithmetic as `.ras` | multi-scan; `root.xml` is the authority on order and membership, not the zip name list; every member read through a cap, because `ZipInfo.file_size` is the archive's own claim |
| `brml` | a zip holding a `DataContainer.xml` **and** a `RawData<N>.xml` | derived through the absorber, √(y/a)·a | multi-scan; **every column is located from `DataViews`, never counted** (GSAS-II's fixed column indices are one layout's coincidence). A `RecordedRawDataView` of `Length > 1` is a detector frame and is refused |
| `ras` | first line `*RAS_DATA_START` | measured per file (above) | multi-scan; third column is an attenuator and is **never applied** — no spec says whether column 2 is already corrected, and no obtainable file has it varying, so `RAS_ATTENUATOR_PRESENT` names the affected 2θ range instead |
| `uxd` | first non-`;` line begins `_FILEVERSION` | marker suffix + `_STEPTIME` | multi-range; the header snapshot must be taken when the **marker opens** the block, not at close — keys persist across ranges, so otherwise a 2 s range's σ comes from a 20 s one |
| `xrdml` | the document's first element is `<xrdMeasurements>` | one composition, `y = c·s` | multi-scan; the namespace is **versioned** (1.6 and 2.1 both current), so nothing matches on it and every lookup is by local name |
| `pdcif` | `.cif` suffix, through gemmi | the intensity column's own `_su`/`_esd` column, then the su in parentheses on every intensity, then the weight column, where a zero weight excludes its point (the dictionary's "not used for refinement"; `PATTERN_ZERO_WEIGHT_EXCLUDED`); a column with a negative entry, a null (`?`, `.`) or no positive one is dropped whole, and `PATTERN_WEIGHT_UNUSABLE` says the Poisson fallback was used and counts the negative and the missing entries separately | `block` selects; a `_meas` and a `_calc` block are different patterns. **`_pd_proc_intensity_net` is read last, and reported**: `PATTERN_INTENSITY_NET` and `metadata["intensity_item"]` say a net column was read, because the item is defined as background-subtracted. A net column never within `NET_BACKGROUND_MIN_SIGMA` σ of zero contradicts its label, and `PATTERN_NET_HAS_BACKGROUND` says so; y is not shifted. `_pd_calc_intensity_net` is a model and is never read as y |
| `gsas` | `^BANK \d+` in the first 4 kB, or one bounded read further when a `TIME_MAP` token sits in that window (§ Dispatch); or a bank line behind `#` carrying the whole loose header, read only where the file has no live bank (`GSAS_BANK_COMMENTED`, issue #230; a passing mention must not claim an ASCII file) | ESD/FXYE column, else Poisson | disjoint from `bruker_raw`'s magic by construction, so the `.raw` collision resolves either way. A `TIME_MAP` table larger than the 64 kB escalation stays unsniffed, the same tradeoff the 4 kB bound itself makes. Measurements, manual citations and the bugs each rule closed: `formats/gsas.py`'s docstring. **The bank record makes two independent declarations and they are read as two**: the *bintype* governs how the x axis is computed, the *type flag* governs how one data record is laid out, and nothing couples them — letting the bintype decide the layout was the wrong-answer path. GSAS-II's `G2pwd_fxye` divides every bank's x by 100 with no bintype branch, so it is not a source to copy. **Bintypes.** Only `CONS`/`CONST` is read as an angle — one rule under two vendor spellings (a start angle and a step, in centidegrees), the manual's token being `CONS`. `TIME_MAP`, `RALF` and `SLOG` land on `PatternData.tof` in µs; `COND` (a d-spacing), `CONQ` (a Q), `LPSD` (a detector position), `EDS` (a photon energy) and `LOG6` (a flight time on a Model 6 clock whose step table is not in the data file) are refused by name, each saying what its axis holds, and supporting any of them is a schema change before it is a parser change. This is § The axis is never trusted's second and third rows, reached through the bintype. Matched **exactly, never by prefix**: `COND` and `CONQ` share three characters with `CONS`. **A TOF axis is read only where the file states it exactly**: `TIME_MAP` *tabulates* its steps in a separate record — triples of (first channel, flight time, step) in clock ticks, then a terminator checked against the bank's declared channel count — so it is exact in every record layout; `RALF`/`SLOG` state *binning constants*, so they are read from an `FXYE` record (which writes its own x column) and refused under `ESD`/`STD`, where an axis rebuilt from the coefficients is a **near miss** nothing downstream can see. A `#` in column 1 inside a bank body is a comment and is skipped, not a terminator. **A `TIME_MAP` record ends a bank as a `BANK` record does** and closes the bank its rows belong to (the manual allows header-and-record sets in any order). **The bintype is read from a loose header match** (bank number, channel and record counts, bintype) taken *before* the strict record parse, because the coefficient count differs per bintype (a `CONS` bank writes a start and a step, a `TIME_MAP` bank a lone map number). **Flags.** `STD`/`ESD`/`FXYE` are the layouts read and every other flag is refused by name, `ALT` and `FXY` included; `STD` is also what a bank stating *no* flag means. No obtainable file can exercise an ALT or FXY reader, and for ALT the manual and GSAS-II disagree on the scale, so neither source is safe alone. The flag is matched as a **keyword**, because it is the record's last field and a bank writing an odd number of coefficients leaves one *in* the flag's position; a number there is absence, not a flag. **Field positions are behaviour, not style**: an `ESD` bank is read *positionally* — ten 8-character fields to an 80-column record — because a value that fills its field fuses with its neighbour. `FXYE`/`FXY` are free-format and stay whitespace-split, their tokens overrunning 8 columns; `STD` is read positionally too, as `(10(I2,F6.0))` — a 2-character counter number (NCTR; blank or zero is one) then a 6-character value — because a whitespace split interleaves the counter numbers among the counts (issue #1061). The counter number is checked and never folded into the value, and any NCTR above one emits `PATTERN_INTENSITY_SCALED` naming the range, since the manual does not say whether the value is then a total or a per-counter mean. Widths and the fusion measurements: `tests/data/README.md` § GSAS ESD |
| `chi` | four-line header whose declared count matches the rows | third column when written | the count gate is the one O(N) sniff |
| `dif_peaklist` | `.dif` **and** peak-list content | — | refused; matched on evidence not suffix, so a real profile misnamed `.dif` still reaches `xy` |
| `peak_list` | the `.pks` (Stoe) or `.udi` (PANalytical) suffix, **unless** the file reads as a plain two-column profile | — | refused; matched on the *name*, because no sample of either format could be obtained — and the message says so rather than implying a content test. The negative gate keeps `.dif`'s escape |
| `total_scattering` | an `#L` line labelling r against G/g or Q against S/F, or a PDFgetX2 (`History written` + `Get_XPDF` banner) or PDFgetX3 (`[DEFAULT]`, bare in 2.1.0 or behind `#` in 1.0, + `qmaxinst`/a version) header, **whatever the suffix**; with neither, the `.gr`/`.sq`/`.fq` suffix alone — directly above `xy`, the one entry these files fell to (#1240) | — | refused with `PATTERN_TOTAL_SCATTERING` at `error`, appended to `diagnostics=` and carried on `TotalScatteringRefused.diagnostic`: the one refusal with a code, so a caller branches on what the file *is*. PDFgetX2's `#L` line sits past the window, so its **banner** is the content evidence rather than a bounded escalation; and its lines end `\r\n`, which `$` under `re.M` does not match. A suffix-only match says so and offers the rename escape; an `#L` labelling I against Q is a diffraction pattern and not claimed. Reading these files is #192, fenced. No fixture in `test_readers_robust.py` (§ Adding a format, step 4): a refusal parses nothing, as for `dif_peaklist` and `peak_list` |
| `xy` | text, not binary — **last of the readers** | third column when written | a NUL in the first 4 kB is refused by name unless behind a BOM: ASCII-range UTF-16LE is valid UTF-8 with interleaved NULs, and Windows vendor software exports it. **A row is data only at the file's most common column count** (a tie goes to the last row's), and the rest are dropped and reported by line (`PATTERN_ROWS_DROPPED`): a numeric header row was otherwise read as a point (#266), and a *minimum* count lets one short row strip σ from every row. **A line inside the data that is not a row of numbers is reported by line** under the same code (WP-1952): inside is between the first and last row at the file's column count, since a header above is ordinary and a footer below cannot be a lost point. It reads on where GSAS-II refuses, naming the line. `,` and `;` separate like whitespace (GSAS-II's importers read both), so `;` also opens a comment line, as in `.uxd`; a field opening `#` or `!` ends the row silently, since no number changes, while `'` and `/` open a comment only at line start, as inside a row they begin a quote or a path. **A comma inside a number is refused, never converted**, on one row: a whitespace- or `;`-separated field that is a number with its commas (`10,02`, `1,234`) is a decimal comma or a thousands separator and cannot be told apart, and a row without one only held a value that needed none (`10` beside `10,5`). A CSV row is one field or has a field ending in its comma, so it never matches. Quoted fields are refused by name. **A comment stating the x-axis unit is read** (Mantid's `' The X-axis unit is: Time-of-flight` → a TOF pattern; `dSpacing`, `MomentumTransfer`, `Wavelength`, `Energy` → refused by name; anything else stated → `PATTERN_X_AXIS_ASSUMED` quoting it). The pattern requires the word `axis` or `unit` and an `x` starting a word, so a comment that merely ends in a colon (`# Max: 90`) does not read as a stated unit of "90". **A FullProf `XYDATA` file's five heading lines are a heading** (manual p. 74): `TEMP tsamp` becomes `temperature_k`, and the `INTER` multipliers are **applied** as defined (x × `fac_x`, y and σ × `fac_y`, `XYDATA_INTER_APPLIED`); a file with no σ column takes the fallback on the multiplied y, √(fac_y·y), which the manual leaves open and FullProf run as a black box settles (`formats/xy.py`). `Interpol = 1` stays refused by name, since interpolating to a constant step makes a different pattern. **`axis=` is the caller's declaration** (`AxisKind`'s spellings, #1064), for a headerless bank that has nothing else to say what x is: recorded as `declared_axis`, never inferred, and a unit the file states that contradicts it is **refused quoting both**, never resolved by picking one; every other format states its own axis and drops the option |
| `raw_unclaimed` | a binary `.raw` every reader above declined — **last of everything**, so it can shadow nothing | — | refused, **claiming nothing**: it names the six vendors who write `.raw`, says this build reads Bruker v2 (single-range)/v3/v4 and Philips PC-APD, and picks none. This is where a Stoe reader hangs if files ever arrive — the cheap ask is a few `.raw` files paired with the WinXPOW ASCII export of the *same* scans, which is an exact oracle |

## `recipe.py` — a whole refinement, and **not** a pattern format

`read_recipe`/`write_recipe_tables` speak the PowderLine `GSASII_Rietveld` JSON
recipe (WP-1306). It lives here because it reads a file and is deliberately
**outside `PATTERN_FORMATS`**: a recipe carries a structure, an instrument, a
plan and refine flags too, so it returns a `Recipe`, nothing dispatches to it,
and none of the sniffing, `scans`, `READER_OPTIONS` or σ policy above reaches
it. Chapter: `docs/docs/reference/recipe.md`; measured convention table:
`tests/data/README.md` § v1.3. What generalises to the next foreign format:

- **Measure its units against its own reference output before writing the
  reader**, then use the format's prose only as corroboration.
- **A row the format states two ways is refused, not picked** — `Zero` is
  centidegrees in one upstream module and degrees in another, 100× apart. §
  What a reader may repair, one rank up: a contradiction is the caller's.
- **Magnitude decides drop against refuse, and the refine flag does not.** A
  value at the model's identity is dropped with a diagnostic even when flagged;
  a non-zero one raises.
- **Never adopt the other engine's project defaults, and never carry a quantity
  normalised in its units** — the Chebyshev coefficients and the phase scale
  are re-seeded, each saying so.
- **A flag the model cannot honour as written is dropped at `warning`, naming
  what it costs**: a half `LG_eta` puts at its off state stays fixed, so the
  recipe's η stands and the fit is one parameter short (`RECIPE_FLAG_DROPPED`).

## Adding a format

1. **Check the fixture licence per *file*, before writing the reader.** A repo
LICENSE covers the repo's own work, not user-contributed instrument output, and
a repo may have none at all. If a file cannot be vendored, that format's whole
test strategy changes — and what the real file established goes in
`tests/data/README.md` regardless, since that is then the only place the design
is checkable. 2. **Byte offsets, magic strings, tag names and element
paths are specification facts** — merger, not expression — so they may be
written down from any source, including one whose licence would bar a port.
Extract them into a table first, then write the parser **with the source file
closed**. `ATTRIBUTION.md` § Format specifications records which source each
came from. 3. One module, exporting a `PatternFormat`; add it to
`PATTERN_FORMATS` in dispatch order and say why the position is right. 4. Add
its fixture to `test_readers_robust.py` — `REAL_FIXTURES` if it has one, the
synthetic arm if it cannot. A **binary** format's synthesized fixture is written
in `tests/writers_xrd.py` and **packs its offsets literally, never from the
reader's own table**: a writer that shares constants with the parser can only
confirm that the parser agrees with itself. Text formats' writers stay inline in
`test_readers.py`, where a line is self-describing and the circularity does not
arise. 5. A new rule lands here; it earns a root CLAUDE.md clause only if it
changes behaviour outside `io/`.

## Project readers (`io/projects/`)

A **project reader** reads someone else's refinement *input* — the solved model
and the protocol that produced it — not a pattern. One module per format,
ordered in `PROJECT_FORMATS` (`registry.py`) and reached through
`read_project_model`, which dispatches on content like `read_pattern` and for the
same reason. Rules the pattern readers do not need:

- **The registry's unit is a *refinement*, and the other foreign-file readers
  sit outside it on purpose** (WP-1118). `read_gsas_prm` carries a machine and
  no model, so it stays beside `load_instrument_profile`; `read_recipe` resolves
  to something ready to fit and is a build-wide feature; a pattern is the other
  registry's. A new reader answers this before it is written, because admitting
  one that carries no model would empty every field this registry declares.
  **Staying outside it is about dispatch, never about parsing.** A record
  belongs to the vendor, so one vendor's several file kinds read it through one
  function: `projects/gsas.py` holds GSAS's grammar — `read_icons`,
  `read_prcf_header`, `split_records`, `CW_PROFILE_COEFFICIENTS` — public, and
  called by `instrument_profile.py`'s `.prm` reader a package away (un-shared,
  the two read `ICONS` two ways; WP-1118).
- **A refusal's reason can expire, so audit the refusals when a parser gets
  sharper** — not only what it reads. "No file establishes this" is the
  perishable kind (WP-1118: the `.prm` reader's Kα-doublet refusal ended once
  `KRATIO` was read by column as `EmissionLine.weight`).
- **The answer is the format's own model, tagged — never a union with blanks.**
  `read_project_model` returns a `ProjectModel` naming the format and handing on
  `TopasModel`/`FullProfModel` untouched, because a shared shape would need an
  optional field wherever a format is silent and a blank reads as an answer
  (WP-1076, one registry over). What each format carries beyond a structure is
  declared in words (`ProjectFormat.carries`), so a client asks rather than
  reading `None` and guessing. Same rule for the conversion keywords: they pass
  through, never flattened into one vocabulary, since two formats' options that
  share a name would not share a meaning.
- **Where a format reports its repairs is a declared fact, checked against the
  signature.** `ProjectFormat.reports_at` is `"build"` for a `.pcr` (codewords
  becoming a `Structure`) and `"both"` for a `.inp` (species, origin at parse;
  merged site twins, magnetic parts at build), a `.EXP` (histograms at read;
  species at build) and a `.gpx`. A wrong value raises nothing: its empty list
  reads as "no repairs", so a meta-test pins it against `inspect.signature`,
  **partitioned both ways**, since an undeclared channel is dropped too.
- **Derive the obligations from the specification; use files to corroborate.**
  Sweeping an archive and fixing what broke finds the bugs one lab's dialect
  contains, in rounds, and never the bugs that raise nothing (WP-1118). Enumerate
  the keyword space from the spec, classify **every** name read / refused /
  deliberately ignored, and decide even at zero incidence. Numbers:
  `tests/data/README.md` and the WP. **That classification is a table,
  not a habit** — `projects/coverage.py` declares one stance per construct (read
  / ignored / reported / refused) with the argument for it, and `PHASE_SCOPE` is
  partitioned against the spec's own phase tree by test, so a keyword without a
  stance fails rather than being dropped in silence. Support for a construct
  arrives by moving its row; until then every import that meets it says so.
- **A reader that *runs* what it reads resolves an allow-list, and refuses a
  name rather than a record** (WP-1118). A `.gpx` is a sequence of pickles, so
  loading one calls whatever it names: `projects/gsas2.ALLOWED_GLOBALS` is the
  whole trust boundary and is **data a caller can read**, every other name is
  refused *by name*, and the **file is refused entire** — half a project is not
  a model. Two halves of that are measured rather than chosen. The vendor's own
  classes are admitted as **inert stand-ins** — no `__reduce__`, no
  `__setstate__`, so the machinery can only fill a dict — because refusing
  `G2VarObj` refuses real projects, and PyTorch's `weights_only` unpickler is
  the same shape for the same reason. And **an allow-list taken from one archive
  is wrong**.
- **A binary format's sniff is not its magic bytes** (WP-1118). Real `.gpx`
  files can carry no pickle protocol header at all, so the test is "opens as one
  **and** names one of its own tree labels" — a writer need not follow its own
  format's convention, and a suffix is not evidence either (§ Dispatch). The
  registry's order inherits the pattern readers' rule with its first binary
  member: binary first, because every other sniff decodes with
  `errors="ignore"` and meets a pickle as text with its bytes dropped.
- **Every schema object a conversion builds is built in one place, inside one
  guard.** A pydantic `ValidationError` reaching a caller names a `Parameter`
  and never the file, which is § Refusals losing to the thing it forbids;
  `gsas2.to_structure` closes the class (WP-1118). A phase with no sites (a
  GSAS-II Le Bail extraction) is refused by **name** first, a message naming the
  phase being worth more; a file's B is kept whatever its value, `Atom.biso`
  having no default bound (WP-1534).
- **A project reader refuses where a pattern reader would repair.** A pattern
  reader repairs only where it can say it did; a project reader mostly cannot,
  because its output is a whole model and a caller cannot see which part is the
  file's. Four classes are refused **by name** (numbers still readable on the
  model): an unevaluated pre-processor directive, a card whose attachment moved
  (`load`/`move_to`/`for`, bar the expanded `for xdds`/`for strs`), a macro
  whose body lives in a library, and a file whose phases belong to different
  patterns — a *selection*, following `read_pattern`'s `scan=`:
  `to_structure(model, dataset=N)`, never concatenated; a TOF one refuses, #193.
- **Where a file states its symmetry twice, the operators outrank the symbol —
  and where it states it once, the reader says so** (WP-1118, issue #101). A
  Hermann-Mauguin symbol is ambiguous for some of gemmi's settings, the `:1`/`:2`
  origin choices and the `:H`/`:R` axis choices, and gemmi has to pick one. A
  format that also writes the operations has already chosen:
  `crystallography.symmetry.setting_from_operators` takes the expanded group
  and returns the setting that matches exactly, so the choice is an equality
  checked rather than a convention adopted — the same footing as § Adding a
  format's rule that a unit is measured against the format's own reference
  output. GSAS-II writes them (`SGData['SGOps']` × `SGCen` × `SGInv`), and
  phases in its public corpus state a bare two-setting symbol whose operators
  are the other origin choice (`tests/data/README.md`). A `.EXP` and a `.inp`
  state only a symbol, so they
  cannot be read this way and raise `SPACE_GROUP_SETTING_ASSUMED` **at read**
  instead — from `symmetry.setting_diagnostics`, the one builder a fit uses too,
  since a reader and a fit are reporting one fact. The next reader answers which
  of the two it is before it is written; `.m50` states operators
  ([1314](../../../docs/wp/1314-mfile-reader.md)).

## `instrument_tof.py` — a calibration, not a model and not a pattern

Neither a `PatternFormat` (returns an `Instrument`, no pattern) nor a project
reader (no model). `instrument_profile.py` is its native sibling and shares
its contract: **every parameter comes back `vary=False`**, because freeing
DIFC beside a free cell reopens the flat direction a free wavelength does one
axis over.

- **The calibration is never in the data file** — no DIFC in any GSAS
  bintype — so a pattern out of `formats/gsas.py` reads in microseconds with
  no way back to a d-spacing until one of these readers runs.
- **Records are split by the shared card grammar, fields read by column**:
  `projects/gsas.split_records` gives key and payload; each field is read at
  the manual's FORTRAN columns by this module's own parser, which refuses a
  non-numeric field (`gsas._num` reads it as blank). A value outside its
  field is a misread, not a tolerance. A record the manual does not list (`FPATH1`) is read at its observed layout, one token, else refused, like `BNKPAR`.
- **One instrument per bank, returned as a dict** — several banks are what a
  TOF instrument *is*, so picking one is the silent-selection failure.
- **Strict to the documented layout, refused by name otherwise** (each in
  the docstring). **Two one-reading repairs are recorded** (WP-2146): a lone
  unnumbered `PRCF` set is set 1; zeros past a record's last field are read.
  sig-2 needs σ²(d) > 0 over the `I ITYP` window. A LANSCE-shaped file
  (8-slot type-1 `PRCF`) is **refused**, read only by `legacy/`. A bank with
  no `PRCF` reads with an all-zero `ProfileTOF`, which says so. `ICONS`' POLA,
  IPOLA, KRATIO pass blank **or zero**, FORTRAN's one reading (F77 §13.5.9).
- **`.instprm` is one public reader on `Type`**: `read_gsas2_instprm` hands
  a file stating `Type: PNT` *by path* to `read_tof_instprm`, before
  `projects/gsas2.read_instprm` (written from GSAS-II's modules) sees it, so
  the TOF path keeps its own observed grammar — never a `_tof`-suffixed second
  public name. Keys with no published TOF law are accepted only at exactly
  zero; **`difB` is read because dropping it is silent**.

## `legacy/` — a documented deviation, read only when asked

A real file's departure from a *published* format, accepted as named, only
when a caller names the reader; the strict reader keeps refusing it and nothing
dispatches here (`legacy/__init__.py`, each module's docstring). **Call the
strict reader, never copy it**: restate the records in the documented layout
and hand them to `instrument_tof._banks_from_records`, whose one keyword
(`fifth_pair=`) is the only other door, so every check applies and a clean file
comes back byte for byte. **`model/` is out of reach**: a deviation it refuses
stays refused. **Token-reading is a named deviation, never a fallback**
(`BNKPAR` alone, restated in columns; a token that does not fit leaves the
strict refusal standing). Evidence is another program's **output** run as a
black box, never its source, recorded with its version.

## Project writers

A writer is its own reader's inverse and its acceptance is the **round trip**:
export, re-import, compare field by field. No fixture is needed and none is
added. Rules the readers do not need (WP-1118: `.inp`, `.pcr`, `.EXP`, `.prm`).

- **Refuse on the way out whatever the reader refuses on the way in**, and
  refuse it where the value is still in hand rather than leaving the file on
  disk to fail in someone else's program. An anisotropic site under a
  convention `to_structure` declines to assume, a setting the format cannot
  spell — and a **non-finite** value, which `repr` writes as `inf` and no real
  program parses. The reader's own refusals are the list to work from; where
  the reader refuses *for want of evidence*, § What a reader may repair's rule
  decides the direction — magnitude, not the refine flag, so a value at the
  model's identity is dropped and a non-zero one raises (a `.prm`'s `ICONS
  ZERO`, whose unit no file here settles). **A species is the exception**
  (WP-1527): written as the atom rietx computed (`scattering.written_species`),
  a neutral substitute reported, a moment's ion kept, and refused only where
  the file has no label (an isotope, `Cval`), never for a charge.
- **A fixed-column writer owes two things a token writer does not.** The field
  is the *budget*: spend it (`gsas.write_field`, `%g` descending from seventeen
  digits, which is the value's own `repr` wherever that fits) and name what
  still had to narrow, once per file rather than once per value, since on a
  converged model most values narrow. **How much of it is spendable is the
  *reader's* question, not the field's** — a field read by column may fill
  itself, one read by token must leave a separator (a `.prm` `PRCF` field,
  `_PRM_COEFFICIENT_DIGITS`; WP-1118). And
  **write the decimal point** — a Fortran `F`/`E` edit descriptor supplies one
  from its own `d` when the field has none, so `90` in an `F10.6` field is 9e-5
  to the program the file is *for* while `float()` here reads 90. That is the
  one class a round trip through this package cannot catch, so it is checked
  against a real file's own spelling instead. The characters are the field's
  too: a line break splits a card in two under keys nothing wrote, and a
  character the file's encoding cannot spell must be refused at the field
  rather than at the encode, which names a byte offset into the finished file.
- **A fact two programs read differently gets an oracle** (WP-1527, WP-1911; a
  species, a setting, a scale), since a round trip passes whatever the target
  makes of it: a test that reads the file by the target's measured rule, shares
  nothing with this reader, and is held first to its measurement table.
- **A flag narrower than the model merges free, and the group is named.** GSAS
  states one refine flag for a whole cell and one for a site's three
  coordinates, both meaning "as symmetry permits". Freeing keeps more of the
  caller's protocol than holding, and the protocol is what these files are for.
- **The write grammar is shared exactly as the read grammar is**:
  `projects/gsas.write_field`/`write_record` are public and
  `instrument_profile.py`'s `.prm` writer calls them. Two writers spelling one
  record two ways is how the two *readers* came to disagree about `ICONS`.
  `projects/gsas2.centidegree_factor` is that rule on a *conversion* (the
  `.gpx` reader divides by it); `instprm_factor` adds 8 ln 2 for `.instprm`.
- **Two programs can read one string opposite ways, so state the fact in the
  channel the *target* reads and name which reader takes which** (WP-1118).
  GSAS-II resolves a bare `F d -3 m` to origin choice 2 and answers a
  colon-suffixed symbol with `P 1`, where gemmi resolves it to choice 1: so the
  GSAS-II phase CIF states the setting three times, bare symbol, resolved
  symbol and operator loop, rather than picking one. Two corollaries for a
  writer: a **value** narrower than the model merges and is named, as a refine
  flag is (one `(S+H)/L` against two axial terms), and a value the *target*
  floors (`SH/L` at 0.002) is reported at write, being the class no round trip
  through this package can see.
