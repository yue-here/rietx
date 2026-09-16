# CLAUDE.md — src/rietx/io/

Scope: the **pattern readers** — how a file is claimed, what a reader may
repair, where σ comes from, and the per-format rules. The clauses that change
behaviour *outside* this subtree stay in the root CLAUDE.md (§ Invariants);
everything here is detail a session working under `io/` needs and nobody else
does. Measured stories and provenance are elsewhere: `docs/wp/1047-*.md` for
the decisions, `tests/data/README.md` for what each fixture can prove,
`ATTRIBUTION.md` for the licence fences.

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

Every text sniff goes through `base.head()`, a bounded 4 kB read — its
predecessor decoded a whole file and then sliced, an O(N) decode per dispatch on
a 60 MB pattern. It is deliberately **not cached**: `restage` re-reads the same
path, so a path-keyed cache would be a correctness hazard for exactly the file a
user just replaced. There are **two stated exemptions**, of two different
classes — the distinction is the point, since the next format to want one should
see which it is asking for. **`.chi`'s count check is O(N)**, behind a bounded
shape gate, and buys what the shape cannot: that format against the catch-all.
**`gsas`'s `TIME_MAP` escalation is bounded** — one further `head(p, 64 kB)`, and
only once a `TIME_MAP` token is seen in the first 4 kB, because such a step table
is what pushes a real file's first `BANK` past the window (`vnb5053.dat`, byte
6068). So no dispatch became O(N) in file size — the invariant the 4 kB bound
holds — and a bounded escalation behind a shape gate is the cheaper class, to be
reached for before a second O(N) one.

`xy` is not total (`matches = not looks_binary(head)`), so `identify_format`'s
terminal refusal is reachable and its message is **built from the registry**.

## What a reader may repair

Root CLAUDE.md's rule — a silent correction is a reader's to make, and only
where the deviation is a *report* rather than a *contradiction* — applied to 2θ
order in `base.ascending()`, the one place it lives:

| deviation | verdict | action |
|---|---|---|
| strictly descending | report — the same measurement stored backwards; reversal is lossless | reverse, `PATTERN_SCAN_REVERSED` |
| duplicate 2θ, equal y | report — a format artefact | drop the repeat, `PATTERN_DUPLICATE_POINTS` |
| duplicate 2θ, **different** y | contradiction — averaging invents a datum, dropping picks one | **raise**, naming the 2θ |
| non-monotone (stitched, restarts) | contradiction — concatenate, sort or separate are three measurements | **raise**; name `scan=` only where the format has it |
| non-constant step | neither | nothing — SRM 660c is 24 stitched regions and is legal |

`ascending(..., fmt=)` takes the format so the non-monotone refusal names
`scan=` **only** where the option exists: telling someone to select a scan in a
file that cannot hold several is a wrong instruction, not a vague one.

## Refusals

A reader raises `ValueError`/`OSError` **naming the file**, never its parser's
exception — six container parsers will otherwise raise `struct.error`,
`zipfile.BadZipFile` and `ET.ParseError`, and the last subclasses `SyntaxError`,
so it escapes `preview_pattern`'s allowlist as a 500. Each parser converts at
its own boundary, and `base.pattern_data()` is that boundary **at the schema**
too: a `PatternData` validator is the last one every reader crosses, and its
pydantic report names a field rather than a file.

`test_readers_robust.py` is what keeps this true — every real fixture truncated
at 20 offsets, plus a synthetic arm for formats with no vendorable file. It has
found two real bugs so far (both ragged-array crashes on a row cut mid-line),
which is the argument for running it before believing a new parser.

A **container** adds one more: nothing is extracted to disk and no member is read
whole on trust. `ZipInfo.file_size` is a number in the archive's *own* header, so
each member is read `read(cap + 1)` and refused past `rasx.MAX_MEMBER_BYTES`, and
`extract()` — which writes files, and historically wrote them outside the
destination — is never called. A 651 kB `.brml` carries a 4.5 MB member no reader
here opens, so the file's size says nothing about a member's.

`PatternFormat.refuses` marks a format recognised **in order to be declined** —
a `.dif` peak list is not a profile. One field rather than a side table, so
`capabilities()` stays honest without `reader_formats` meaning two things.

**A refusal claims only what its evidence allows, and its registry position is
part of the claim** (WP-1407). Three tiers: matched on **content** (`dif`'s hkl
triple) asserts what the file is; matched on the **suffix** (`peak_list`, no
sample of `.pks`/`.udi` obtainable) says in the message that it matched the name
and not the columns, and gates *negatively* — refuse unless the file reads as a
plain two-column profile, which keeps `.dif`'s escape for a misnamed scan; and
claiming **nothing** (`raw_unclaimed`) names `.raw`'s six vendors and picks
none, since the likeliest one is Stoe and no description of Stoe exists in any
licence anywhere. A claims-nothing entry goes **below the ASCII catch-all**, so
it can shadow no reader — asserted as a property (`xy` last *of the readers*,
everything after it a refusal), never as an index.

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
  attribute *on* the data element, where neither can disagree with itself.
  Verified anyway: every `COUNTS` block integral to the last of 3774 points, and
  every intensity in both real single-scan `.xrdml` fixtures.
- **Free text** — measured, not trusted, by `base.sigma_by_arithmetic`: counts
  are integers, and a rate times its counting time is. Both Rigaku formats
  declare the unit this way and real files get it wrong — a `.ras` declaring
  `counts` while storing 84.3047, and **two of the three** real `.rasx` files
  declaring counts and storing values no scale in 1/400…400 makes integral. The
  third `.rasx` declares counts and is integral, which is the same test deciding
  both ways within one format.
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
product runs continuously through the transition. `.xrdml` **applies** it (the
raw series dips 87 % at the attenuated point of a substrate peak); `.brml` leaves
the values alone and puts the factor into σ only (the stored series is
continuous, and `y/a` is the integral one); the two Rigaku formats **report**
without deciding, because no obtainable file has a varying column. Numbers in
`tests/data/README.md`. Whichever way it lands, σ goes through the factor —
√counts·a is not √y — and that is the case GSAS-II gets wrong by weighting 1/y
regardless.

## The stored number need not be the measured one

σ above is about a *scale* a reader can name. `.rd` is the sharper case: the
stored `uint16` is **√-compressed**, `counts = v²//100` (WP-1407), and read raw
it yields a profile with every peak in the right place and every intensity
wrong — which no reader can see in its own output and no truncation harness can
catch. Three rules generalise (measurements: `tests/data/README.md` § Philips):

- **A format may encode its counts, and only a real file says so.** Four
  independent confirmations here; any one alone would have been thin.
- **The permissive description can be the defective one.** PyXRD's
  `rd_parser.py` is the BSD-2 source a port would legally start from, and it
  omits the decode, drops the last point and shifts the axis half a step. A
  licence says what may be copied, never what is right, so a description is
  checked against a file before it is believed and the file settles a
  disagreement between two.
- **A format's own redundancy is the gate to reach for**, ahead of any invented
  check — `.rd` states its length twice and its maximum once, `.udf` states its
  point count two ways. Disagreement is **refused, not repaired**: a wrong parse
  there puts the 2θ of every point in doubt.

## The axis is never trusted

Most vendor files are **not powder scans** — 4 of the 5 real `.uxd` files
obtained are pole figures or rocking curves, and one rocking curve sits under a
marker called `_2THETACOUNTS`, so a block marker is not evidence either. A
non-2θ scan parses perfectly and refines to a confidently wrong cell, so all
three formats that state an axis use the same three-way policy:

- recognisably 2θ → read, silently;
- recognisably something else → **raise**, naming what the file actually holds
  (a q or d axis, a rocking curve, a pole-figure ring);
- unrecognisable → read as 2θ **and say so** (`PATTERN_X_AXIS_ASSUMED`).

**A format stating no axis at all is a fourth case and emits nothing** (WP-1407,
`.udf`, following `.xy`): the policy is for formats that *have* a field to
classify, and a warning firing on 100 % of a format's files trains people to
ignore it. The assumption goes in `sniff`, where a UI shows it — a decision with
evidence, since all 56 real `.udf` files are powder scans over classic 2θ ranges
against `.uxd`'s four-of-five that were not.

The policy is `base.check_axis()` and the **classifying is not part of it**: the
authority differs per format and is always the field that *means* the axis —
`.chi`'s line-2 label, `.ras`'s `*MEAS_SCAN_AXIS_X`, `.uxd`'s `_DRIVE`,
`.xrdml`'s `scan/@scanAxis`, `.raw`'s flagged drive record — and those are
inputs of five different shapes. So each format classifies for itself and passes
the verdict in; a sixth adds a vocabulary, never a row to a shared table. And
where a format states the axis **twice**, both statements are asked and have to
agree: `.raw`'s scanned drive is the record that is flagged *and* parked at the
range's start angle, because one real file is not enough to trust either alone.
One code rather than four because
the operator's answer is identical in every case, and four near-duplicate rows
in the agent skill was the smell (factored WP-1047 at the fourth consumer,
which is where the previous session said the trigger was).

## Metadata

`METADATA_KEYS` is **data**, and `base.metadata()` refuses an undeclared key,
because two consumers *match* on these keys — the import wizard's anode
pre-selection and a preview's scan count — and neither can match on a name each
reader spells for itself. `scan_count` travels from the **single** read, so a
preview never parses a 60 MB file twice; `list_scans` is for the CLI and the
scan picker, not the preview path.

A file's own wavelength is **recorded, never used**: the anode presets are the
authority on wavelengths, and the real fixtures give 1.540598 and 1.540593
against the package's 1.5405929 — a ~3 ppm spread that is real and far inside
what the SRM 660c acceptance allows.

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
| `bruker_raw` | one of four magic strings at offset 0 — **first**, being the only entry whose sniff names the format *and* its version | measured by arithmetic; neither version declares a unit, and the counting time is **ms** in v4, seconds in v3 | multi-range; **nothing is located by counting and nothing is a fixed stride** — v4 is walked to EOF and strided by `datumSize` (`2Theta` occurs twice in the single-range real file; `datumSize` is 8 there), v3 by `data_record_length` past `total_size_of_extra_records`. **v1 and v2 are named and refused**: no corroborated description of either exists. v3's global gate — the declared ranges must account for the file — judges the leftover by **content, not length**: a range read at the wrong offset leaves counts behind and counts are not zeros, so a zero pad is admitted (a real 82-range VT reel pads with 3280 of them) and any non-zero tail past one datum's slack still refuses, naming its first byte's offset |
| `philips_rd` | magic `V3RD` or `V5RD` at offset 0 — **second**, on the same footing as `bruker_raw` and disjoint from it by construction, which matters because `.raw` has six vendors and `.rd` two | the Poisson fallback, and no arithmetic test: the √ encoding establishes that the decoded quantity is a count | single-scan. **Intensities are √-compressed**, `counts = v²//100`, truncating like xylib and the kit's own converter (§ The stored number). Data at **250** for V3 and **810** for V5. Three gates, all the file's own redundancy and all measured on 28 real files: `len == data_start + 2n`, `n == round((end−start)/step) + 1`, and `uint16@136 == max(v)`. **V5 is read on the length gate alone and says so when it fails** — no V5 file exists anywhere and its offset rests on one description copied twice, which would ordinarily be Bruker v1/v2's refusal footing; it is read because `n` comes from header fields, so the gate tests the header offsets *and* the data start jointly and a wrong 810 cannot shift a pattern silently. `.sd` is that V5, not a separate format, so there is no by-name refusal for it. The anode code at 85 is the one enumerated field carried into the pattern (`suggest_instrument` matches on it, and λα1 says the same thing, so the file states it twice); the diffractometer and focus codes decode correctly on all 28 and agree with the kit's prose, but no `METADATA_KEYS` entry means an instrument model and nothing would consume one |
| `udf` | both of `DataAngleRange` and `ScanStepSize` present as `Key,Value,/` lines in the bounded head — the two the parser needs to build an abscissa at all, so a file matching them is a `.udf` or is nothing | the Poisson fallback; the format declares no intensity unit anywhere, and every value in all 56 real files is whole | single-scan; not a legacy format (a PANalytical Aeris on sale today writes it). **A value may contain commas** — `Title1` runs to ten fields — so a line splits on the *first* comma only, and an empty value (`Title2,,/`) is a present key. The abscissa is reconstructed from the range and the step, never stored, so the point count is the gate. The block is a bare marker line (`RawScan` in all 56) then comma-separated integers terminated by `/`, the comma before it optional. **`ScanStepTime` is not seconds per step** on a PIXcel-class detector and nothing is derived from it: 5246 points at the stated 18.87 s would be 27 hours against a scan the file's own name calls eight minutes. **No axis field**, so no `PATTERN_X_AXIS_ASSUMED` (§ The axis is never trusted) |
| `rasx` | a zip holding a `Data<N>/Profile<N>.txt` member | the same arithmetic as `.ras` | multi-scan; `root.xml` is the authority on order and membership, not the zip name list; every member read through a cap, because `ZipInfo.file_size` is the archive's own claim |
| `brml` | a zip holding a `DataContainer.xml` **and** a `RawData<N>.xml` | derived through the absorber, √(y/a)·a | multi-scan; **every column is located from `DataViews`, never counted** — 2θ is column 2 and the intensity column 7 in the real files, so GSAS-II's fixed `entry[2]`/`[4]` is one layout's coincidence. A `RecordedRawDataView` of `Length > 1` is a detector frame and is refused |
| `ras` | first line `*RAS_DATA_START` | measured per file (above) | multi-scan; third column is an attenuator and is **never applied** — no spec says whether column 2 is already corrected, and all five obtainable files have it constant, so `RAS_ATTENUATOR_PRESENT` names the affected 2θ range instead |
| `uxd` | first non-`;` line begins `_FILEVERSION` | marker suffix + `_STEPTIME` | multi-range; the header snapshot must be taken when the **marker opens** the block, not at close — keys persist across ranges, so otherwise a 2 s range's σ comes from a 20 s one |
| `xrdml` | the document's first element is `<xrdMeasurements>` | one composition, `y = c·s` | multi-scan; the namespace is **versioned** (1.6 and 2.1 both current), so nothing matches on it and every lookup is by local name |
| `pdcif` | `.cif` suffix, through gemmi | the file's esd or weight column | `block` selects; a `_meas` and a `_calc` block are different patterns |
| `gsas` | `^BANK \d+` in the first 4 kB, or one bounded read further when a `TIME_MAP` token sits in that window | ESD/FXYE column, else Poisson | disjoint from `bruker_raw`'s magic by construction, so the `.raw` collision resolves either way. **A `TIME_MAP` step table can push the first bank past the 4 kB sniff window** (real: `vnb5053.dat` from the GSAS distribution's examples, first bank at byte 6068 behind a 71-row `(10I8)` table) — so the sniff missed it and it fell to `xy`, refused there with the wrong cause (a 2θ direction, from records read as columns). The `TIME_MAP` token is GSAS-shaped evidence and lands in the window, so a file showing it earns one more bounded read (64 kB) to look past the table — the `.chi` count-check discipline (§ Dispatch), never a widened window for every file; a table larger than that stays unsniffed, the same tradeoff the 4 kB bound itself makes. **The bank record makes two independent declarations and they are read as two**: the *bintype* governs how the x axis is computed, the *type flag* governs how one data record is laid out, and nothing couples them. Only `CONS`/`CONST` is read — one rule under two vendor spellings (a start angle and a step, in centidegrees), the manual's token being `CONS`, and the rule the centidegree fold rests on. **Every other bintype is refused by name, each saying what its axis actually holds**, and the reason is *scope, not evidence*: none of the manual's other eight is 2θ — a flight time (`RALF`, `SLOG`, `LOG6`, `TIME_MAP`), a d-spacing (`COND`), a Q (`CONQ`), a detector position (`LPSD`), a photon energy (`EDS`) — and `PatternData` holds 2θ, so supporting any of them is a schema change before it is a parser change. This is § The axis is never trusted's *recognisably something else* row, reached through the bintype instead of an axis label. Matched **exactly, never by prefix**: `COND` and `CONQ` share three characters with `CONS`. **The bintype is read from a loose header match** (bank number, channel and record counts, bintype) taken *before* the strict record parse, because the coefficient count differs per bintype — a `CONS` bank writes a start and a step, a `TIME_MAP` bank a lone map number — so matching with the strict CONS record first skipped a real one-coefficient `TIME_MAP` bank and reported it a *missing* BANK record, the by-name refusal never reached (the ≥2-coefficient `RALF`/`SLOG`/`CONQ` banks matched the strict record and were named all along; `TIME_MAP` was the one that slipped, and it is also the one whose step table triggers the sniff-window miss above). Letting the bintype decide the layout was the wrong-answer path: a non-`CONS` bank was *forced* to FXYE behind a divisible-by-three test on its value count, so a `RALF` bank of ESD pairs read as three-column x/y/esd whenever its pair count was a multiple of three, and a `RALF`/`SLOG` FXYE bank had its microseconds divided by 100 and called degrees — an ISIS PEARL file came back as a plausible 2528-point 15.00–194.88° scan. **GSAS-II has that second bug too** (`G2pwd_fxye` divides by 100 with no bintype branch anywhere), so it is not a source to copy here. On the flag side, **`STD`/`ESD`/`FXYE` are the layouts read and every other flag is refused by name**, `ALT` and `FXY` included: `STD` is also what a bank stating *no* flag means — four obtainable real files write it that way — and that default is why an unrecognised flag was silent, an `ALT` or `FXY` bank falling through to counts-only with its own x column entering the intensity array while an axis was synthesized from `c1`/`c2`, the result tagged `gsas-alt` with the flag used as a label rather than a decision. Here the reason really *is* the fixture: every obtainable `ALT` file is also a `RALF` bank (refused one decision earlier, so it cannot exercise an ALT reader at all) and no `FXY` file was found anywhere, and for ALT the manual's Fortran format and GSAS-II's scale factors disagree by 100× on x and 10× on y/esd, so neither source is safe alone. The flag is matched as a **keyword**, because it is the record's last field and a bank writing an odd number of coefficients leaves one *in* the flag's position (`BANK 1 4 4 CONST 1000 20 0` was read as flag `0` and tagged `gsas-0`); a number there is absence, not a flag, so that file still reads as STD. **The three layouts that are read also differ in whether a field has a position or only a separator, and that too is behaviour, not style**: an `ESD` bank is read *positionally* — ten 8-character fields to an 80-column record — because a value that fills its field leaves no separating space and fuses with its neighbour, which real 11-BM patterns do at 100 000 counts and dim siblings never do. `FXYE`/`FXY` are free-format and stay whitespace-split (`mg090.fxye`'s tokens are 9–10 characters wide, so slicing would destroy it); `STD`'s field is a 2-character repeat count plus a 6-character value, so its values cannot reach the field's edge and fusion is structurally impossible there. Widths and the fusion measurements: `tests/data/README.md` § GSAS ESD |
| `chi` | four-line header whose declared count matches the rows | third column when written | the count gate is the one O(N) sniff |
| `dif_peaklist` | `.dif` **and** peak-list content | — | refused; matched on evidence not suffix, so a real profile misnamed `.dif` still reaches `xy` |
| `peak_list` | the `.pks` (Stoe) or `.udi` (PANalytical) suffix, **unless** the file reads as a plain two-column profile | — | refused; matched on the *name*, because no sample of either format could be obtained — and the message says so rather than implying a content test. The negative gate keeps `.dif`'s escape |
| `xy` | text, not binary — **last of the readers** | third column when written | a NUL in the first 4 kB is refused by name unless behind a BOM: ASCII-range UTF-16LE is valid UTF-8 with interleaved NULs, and Windows vendor software exports it |
| `raw_unclaimed` | a binary `.raw` every reader above declined — **last of everything**, so it can shadow nothing | — | refused, **claiming nothing**: it names the six vendors who write `.raw`, says this build reads Bruker v3/v4 and Philips PC-APD, and picks none. This is where a Stoe reader hangs if files ever arrive — the cheap ask is a few `.raw` files paired with the WinXPOW ASCII export of the *same* scans, which is an exact oracle |

## `recipe.py` — a whole refinement, and **not** a pattern format

`read_recipe`/`write_recipe_tables` speak the PowderLine `GSASII_Rietveld` JSON
recipe (WP-1306). It lives here because it reads a file and is deliberately
**outside `PATTERN_FORMATS`**: a recipe carries a structure, an instrument, a
plan and refine flags too, so it returns a `Recipe`, nothing dispatches to it,
and none of the sniffing, `scans`, `READER_OPTIONS` or σ policy above reaches
it. Chapter: `docs/manual/using/recipe.md`; measured convention table:
`tests/data/README.md` § v1.3. What generalises to the next foreign format:

- **Measure its units against its own reference output before writing the
  reader**, then use the format's prose only as corroboration. Three rows
  PowderLine does not state anywhere were found that way.
- **A row the format states two ways is refused, not picked** — `Zero` is
  centidegrees in one upstream module and degrees in another, 100× apart. §
  What a reader may repair, one rank up: a contradiction is the caller's.
- **Magnitude decides drop against refuse, and the refine flag does not.** A
  value at the model's identity is dropped with a diagnostic even when flagged;
  a non-zero one raises.
- **Never adopt the other engine's project defaults, and never carry a quantity
  normalised in its units** — the Chebyshev coefficients and the phase scale
  are re-seeded, each saying so.
- **A parameter that cannot move is held, not declared free**: a softplus
  coefficient at zero has gradient ≈ its own value, so freeing one is WP-1076's
  dead column. Drop the flag at `warning` naming what it costs.

## Adding a format

1. **Check the fixture licence per *file*, before writing the reader.** A repo
   LICENSE covers the repo's own work, not user-contributed instrument output,
   and a repo may have none at all. This has already cost the two best fixtures
   found (`xrd-toolkit`'s real `.ras`; every real `.uxd`). If a file cannot be
   vendored, that format's whole test strategy changes — and what the real file
   established goes in `tests/data/README.md` regardless, since that is then the
   only place the design is checkable.
2. **Byte offsets, magic strings, tag names and element paths are
   specification facts** — merger, not expression — so they may be written down
   from any source, including one whose licence would bar a port. Extract them
   into a table first, then write the parser **with the source file closed**.
   `ATTRIBUTION.md` § Format specifications records which source each came from.
3. One module, exporting a `PatternFormat`; add it to `PATTERN_FORMATS` in
   dispatch order and say why the position is right.
4. Add its fixture to `test_readers_robust.py` — `REAL_FIXTURES` if it has one,
   the synthetic arm if it cannot. A **binary** format's synthesized fixture is
   written in `tests/writers_xrd.py` and **packs its offsets literally, never
   from the reader's own table**: a writer that shares constants with the parser
   can only confirm that the parser agrees with itself. Text formats' writers
   stay inline in `test_readers.py`, where a line is self-describing and the
   circularity does not arise.
5. A new rule lands here; it earns a root CLAUDE.md clause only if it changes
   behaviour outside `io/`.

## Project readers (`io/projects/`)

A **project reader** reads someone else's refinement *input* — the solved model
and the protocol that produced it — not a pattern. One module per format,
ordered in `PROJECT_FORMATS` (`registry.py`) and reached through
`read_project_model`, which dispatches on content like `read_pattern` and for the
same reason. Six rules the pattern readers do not need:

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
  called by `instrument_profile.py`'s `.prm` reader a package away. Un-shared,
  the two read `ICONS` two ways for a milestone and the corpus hid it: a
  whitespace split is right only while `IREF`/`IDAMP` stay blank (WP-1118).
- **A refusal's reason can expire, so audit the refusals when a parser gets
  sharper** — not only what it reads. "No file establishes this" is the
  perishable kind. The `.prm` reader refused every Kα doublet for want of a
  stated intensity weight, and the want was an artefact of not knowing which
  field `KRATIO` was; read by column it is `EmissionLine.weight` exactly
  (WP-1118).
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
  signature.** `ProjectFormat.reports_at` is `"read"` for a `.inp` (species and
  origin, at parse), `"build"` for a `.pcr` (codewords becoming a `Structure`),
  `"both"` for a `.EXP` (histograms at read, species at build). A wrong value
  does not raise — it hands the caller an empty list, which reads as "this file
  needed no repairs" — so a meta-test pins it against `inspect.signature`,
  **partitioned both ways**: an undeclared channel is dropped in silence.
- **Derive the obligations from the specification; use files to corroborate.**
  Sweeping an archive and fixing what broke finds the bugs one lab's dialect
  contains, in rounds, and never the bugs that raise nothing — three of
  WP-1118's six grammar corrections are invisible to any sweep (a parameter's
  *name* is its refine flag; a block comment *nests*; a conditional is a token,
  not a line). Enumerate the keyword space from the spec, classify **every**
  name read / refused / deliberately ignored, and decide even at zero
  incidence. Numbers: `tests/data/README.md` and the WP. **That classification is
  a table, not a habit** — `projects/coverage.py` declares one stance per
  construct (read / ignored / reported / refused) with the argument for it, and
  `PHASE_SCOPE` is partitioned against the spec's own phase tree by test, so a
  keyword without a stance fails rather than being dropped in silence. Support
  for a construct arrives by moving its row; until then every import that meets
  it says so.
- **A reader that *runs* what it reads resolves an allow-list, and refuses a
  name rather than a record** (WP-1118). A `.gpx` is a sequence of pickles, so
  loading one calls whatever it names: `projects/gsas2.ALLOWED_GLOBALS` is the
  whole trust boundary and is **data a caller can read**, every other name is
  refused *by name*, and the **file is refused entire** — half a project is not
  a model. Two halves of that are measured rather than chosen. The vendor's own
  classes are admitted as **inert stand-ins** — no `__reduce__`, no
  `__setstate__`, so the machinery can only fill a dict — because refusing
  `G2VarObj` refuses 10 of 34 real projects, and PyTorch's `weights_only`
  unpickler is the same shape for the same reason. And **an allow-list taken
  from one archive is wrong**: 7 of the 11 globals the public corpus names were
  outside the list a 146-file private one produced.
- **A binary format's sniff is not its magic bytes** (WP-1118). 11 of those 34
  files carry no pickle protocol header at all, so the test is "opens as one
  **and** names one of its own tree labels" — a writer need not follow its own
  format's convention, and a suffix is not evidence either (§ Dispatch). The
  registry's order inherits the pattern readers' rule with its first binary
  member: binary first, because every other sniff decodes with
  `errors="ignore"` and meets a pickle as text with its bytes dropped.
- **Every schema object a conversion builds is built in one place, inside one
  guard.** A pydantic `ValidationError` reaching a caller names a `Parameter`
  and never the file, which is § Refusals losing to the thing it forbids;
  `read_gsas_prm` paid for that once (WP-1118) and `gsas2.to_structure` closes
  the class rather than adding a third instance. The two shapes a real corpus
  contains are still refused by **name** first — a negative `Uiso`, and a phase
  with no sites, which is how GSAS-II stores a Le Bail extraction — because a
  message naming the phase is worth more than one naming the field.
- **A project reader refuses where a pattern reader would repair.** A pattern
  reader repairs only where it can say it did; a project reader mostly cannot,
  because its output is a whole model and a caller cannot see which part is the
  file's. Four classes are refused **by name** (numbers still readable on the
  model): an unevaluated pre-processor directive, a card whose attachment moved
  (`for`/`load`/`move_to`), a macro whose body lives in a library, and a file
  whose phases belong to different patterns — the last a *selection*, following
  `read_pattern`'s `scan=`: `to_structure(model, dataset=N)`, never concatenated.
