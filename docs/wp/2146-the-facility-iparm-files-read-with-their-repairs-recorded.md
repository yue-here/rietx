# WP-2146 — The ISIS iparm files read, with each repair recorded

Milestone: unscheduled · Status: 🔄 2026-11-17 — claimed by ghostshift MacBook-Air-c4aacd
Track: The specimen is not an angle, and the neutron follow-through
Depends on: — (2032 soft, closed: the T-1 readers' last follow-ups; 1927 soft, closed: the T-1 cut)
Priority: P3 2026-11-15 — a reader with a workaround (edit three columns of the file by hand); no TOF fit consumes the profile on main yet, but facility-written HRPD and POLARIS files are what TOF users bring

## Goal

`read_gsas_tof_iparm` reads the ISIS HRPD and POLARIS instrument files that
Mantid and the facility write. Each deviation from the documented layout that
has only one reading is repaired and recorded as a `Diagnostic`. A variance
coefficient is refused only where the variance it gives turns negative inside
the bank's own range. The `.gss` reader keeps Mantid's per-bank header line as
declared metadata.

## Context

**Settled by Claude 2026-11-15 under root CLAUDE.md (WP-1047 reader-repair
rule) and the variance-positivity physics; Yue delegated clear calls that
day.** The rule is "a pattern reader may repair a file only where it can say
that it did". The scope below is that settlement, from the 2026-11-15
rulings file. The reporter asked for it on issue #1447 (comment of
2026-11-09): file now, or hold with T-2. It is filed now, because the readers
shipped in T-1 (WP-1927, WP-2032) and the defects are in shipped code.

**The files** (issue #1447). Both are public.
- ISIS HRPD, `Cyc_182_mantid3.hrpd`: G. W. Howieson's St Andrews thesis
  dataset (2023), doi:10.17630/a7540ced-d4a3-4c89-a93f-6e21dc2b4c01, CC BY 4.0,
  `Diffraction_Data/Powder_Neutron_Diffraction/LaTaO4_Oct18/`. Three banks.
  Its pattern file `hrp72333_01.gss` is in the same directory.
- ISIS POLARIS, `parameter_file.prm`: Collins et al. 2021,
  doi:10.1002/anie.202102073, DataCat record 1047, CC BY 3.0,
  `Powder_diffraction_patterns/Ba10Y6Ti4O27_NPD_data/`. Five banks.
- Both use CRLF line ends. Neither may enter the wheel (root CLAUDE.md,
  licensing: data carries its own fence). A test fixture carries synthetic
  numbers at the files' own column widths, as `tests/test_instrument_tof.py`'s
  `UNNUMBERED_PRCF` does.

**What the tree does, checked at `98d7ba8e3`** with a synthetic HRPD-shaped
bank (type-3 PRCF header `INS  1PRCF      3   14   0.001000`, coefficient
records `INS  1PRCF 1` to `PRCF 4`):
- (a) As published, the bank **reads**, with an all-zero `ProfileTOF` and a
  `GSAS_IPARM_PROFILE_DECLINED` warning. That changed after the issue was
  filed. PR #1503 (merged 2026-11-12, `9d66638f6`) declines a set written
  without its number and keeps the bank. Its stated reason: "the file does
  not say which set it is". The issue's table predates it.
- (b) With set number `1` written in column 11, the header is refused: the
  text `0.001000` in columns 26-33 runs across the boundary of CTOF
  (columns 23-32).
- (c) With CTOF right-aligned, the set is refused: function 3 declares 14
  coefficients and the manual documents 21.
- (d) On POLARIS bank 5, once its set number is written, the reader refuses
  `sig2 = -1.81041` by sign alone (`io/instrument_tof.py`, the loop over
  `sig0`, `sig1`, `sig2`).
- The `.gss` reader skips Mantid's line
  `# Total flight path 95.89m, tth 168.567deg, DIFC 48236.8` as a comment
  (`io/formats/gsas.py:568`). A pattern's metadata hold only `source_file`
  and `format`.

**The scope.**
- **(a) A blank PRCF set number, where the bank has one set**, is read as
  set 1 and recorded. One set per bank has only one reading. This replaces
  PR #1503's decline for that case. Beside a numbered set, the unnumbered one
  stays declined, as #1503 has it, since there it has two readings. Gotcha:
  #1503's GEM-shaped fixture declares profile function 2 with 15
  coefficients. Read as set 1, it meets the later checks for the first time.
  Run that fixture before changing the test that pins the decline
  (`test_a_prcf_set_without_its_number_is_declined_and_the_bank_read`).
- **(b) A trailing zero overflowing CTOF's columns** is read and recorded.
  The repair holds only where the characters past column 32 are zeros, so
  that the column read and the token read give one number (`0.00100` and
  `0.001000`). Any other overrun stays refused by the column-boundary rule.
- **(c) NTERMS below the function's full count** (14 declared for function
  3, where the manual lists 21) is decided inside this WP, after reading the
  GSAS Technical Manual (Larson & Von Dreele, LAUR 86-748). The question is
  whether GSAS-I reads a short block and takes the missing terms as zero. If
  the manual says so, (c) is a recorded repair like (a) and (b). If it says
  nothing, the refusal stays, and it names the fact the user needs. The
  paper corpus held the manual's record but no file on 2026-11-15. Ask the
  maintainer for the PDF rather than working around it.
- **(d) sig-2 passes when σ²(d) > 0 over the bank's own d range**, and is
  refused otherwise. The physics: a variance must be positive where the bank
  has data, and need not be positive outside it. Here σ² = sig0 + sig1·d² +
  sig2·d⁴, the GSAS type-3 Gaussian variance. POLARIS bank 5 has sig0 = 0
  and σ² = 29.2187 d² − 1.81041 d⁴. That is positive for d < 4.02 Å. The
  bank's range (ITYP 0.8-20.4 ms, DIFC 7391.35, DIFA −2.16, ZERO 1.88) ends
  at d ≈ 2.76 Å, where σ² ≈ 118. So the file passes. A bank whose variance
  turns negative inside its range is still refused. Where a bank states no
  range (no `ITYP` record), the WP decides what the range is, or keeps the
  per-coefficient sign test there, and writes the choice here.
- **Mantid's header line** is kept as declared metadata: flight path, 2θ and
  DIFC, each a `METADATA_KEYS` entry (`io/formats/base.py`, which refuses an
  undeclared key). It is recorded and never used as the calibration. The
  header DIFC is the focusing geometry (HRPD bank 1: 48236.8). The iparm's
  `ICONS` holds the silicon-refined value (48275.36). They are different
  numbers on purpose.

**Where the rules live.** `src/rietx/io/CLAUDE.md` is the reader rulebook:
dispatch, repairs, options. `docs/docs/reference/instrument-files.md` is the
manual page that already describes the #1503 decline.

**Tier.** (a) and (b) are file-format rules with one reading each, recorded
as WP-1047 requires. (d) is physics. (c) is named practice if the manual
settles it. Each new diagnostic code needs its `rietx._audit` row (root
CLAUDE.md, every heuristic has a row). A new diagnostic's text is reader
output, so its wording goes to the maintainer before merge.

### Inherited

- **2026-11-17, from the issue triage round (issue #1446).** Decided
  2026-11-16 by the maintainer: reducing raw time-of-flight data to focused
  banks is out of scope. That covers per-pixel event or histogram NeXus,
  empty-can subtraction, vanadium normalisation, per-pixel calibration and
  grouping. rietx starts at the focused bank file. Two follow-ups land here,
  because the files this WP makes readable are what Mantid writes after
  focusing:
  - A how-to: focus the raw run with Mantid, save the banks with `SaveGSS`
    (or FXYE) and the instrument file, then `read_pattern` the `.gss` and
    `read_gsas_tof_iparm` the file. It belongs on
    `reference/instrument-files.md` or a Guides page beside it. Write it after
    tasks (a) to (d), since the HRPD and POLARIS files Mantid writes are
    refused until then.
  - A named refusal when someone opens a raw `.nxs`. Checked against the tree
    at `96f721c26` on a file opening with the HDF5 magic: `read_pattern`
    raises `ValueError` "… is not a powder pattern this build can read (it
    looks binary)" and lists the supported formats (`io/readers.py:352`). It
    names neither HDF5 nor focusing. The new
    message says rietx reads focused banks, and that a raw run is focused with
    Mantid first. The HDF5 magic (`\x89HDF\r\n\x1a\n` at offset 0) identifies
    the file without h5py, so this needs no new dependency. Its text is
    reader output, so its wording goes to the maintainer before merge.
  The same ruling settles issue #113's part (c), a resonance correction at
  raw-TOF level. Only pre-rebinning data could use it, and rietx never sees
  that data.

## Non-goals

- The TOF profile, spectrum and forward model (T-2/T-3) and multi-bank fits
  (T-5): ROADMAP § v2+.
- Using the `.gss` header DIFC as a calibration or a `suggest_instrument`
  hint.
- The LANSCE layout, which `rietx.io.legacy.read_lansce_iparm` reads.

## Tasks

- [x] (a): read a lone unnumbered PRCF set as set 1, with a diagnostic
      naming the assumption. Keep the decline beside a numbered set. Rerun
      #1503's GEM fixture first. *Done 2026-11-17
      (`GSAS_IPARM_SET_NUMBER_ASSUMED`). The GEM fixture declares function
      2, which would meet the default-function refusal as set 1; it stays
      declined with its bank read, the decline now naming the function.
      Whether that case should be refused like a numbered set 1 of
      function 2 is the open question in the handover.*
- [x] (b): read a CTOF whose overrun is trailing zeros, with a diagnostic.
      Every other overrun is still refused. *Done 2026-11-17
      (`GSAS_IPARM_TRAILING_ZEROS_READ`), for the last field of every
      parsed record rather than CTOF alone: the columns after a record's
      last field belong to no field, so the one-reading argument is the
      same on all of them. A spill into the next field's columns stays
      refused.*
- [ ] (c): read the GSAS manual on a declared NTERMS below the full count.
      Write the finding here, then repair with a record or keep the refusal.
- [x] (d): replace the per-coefficient sign test on sig-2 with σ²(d) > 0
      over the bank's d range. Write the no-range case's choice here.
      *Done 2026-11-17. The range is the `I ITYP` window mapped through
      DIFC/DIFA/ZERO; with sig-2 < 0, σ² is concave in d², so its two ends
      decide. **No range (no `I ITYP` record, or a window that maps to no
      positive d): the sign test stays**, since inventing a range the file
      does not state is the guess the reader rule forbids. A passing value
      reaches `ProfileTOF` as a `Parameter` with `min=-inf`, because the
      schema's floor at zero would refuse it (`ProfileTOF.sig2`'s
      validator); the schema default is unchanged.
      `GSAS_IPARM_PROFILE_READ` gains one sentence naming the range and
      where σ² crosses zero. sig-0 and sig-1 keep their sign tests. The
      `.instprm` reader keeps its sign test on all three: it states no
      range.*
- [x] `.gss`: the per-bank Mantid header line into three declared metadata
      keys. *Done 2026-11-17: `total_flight_path_m`, `two_theta_bank_deg`,
      `difc_geometric`, as written, only where exactly one such line sits
      between the bank's record and the previous bank's. The DIFC is
      geometric, measured: 2·95.89·sin(84.2835°)/(h/mₙ) = 48236.6 against
      the 48236.8 written.*
- [ ] Tests on synthetic fixtures at the two files' column widths: each
      repair with its diagnostic, the refusal it replaces, and a bank whose
      σ² turns negative inside its range still refused.
- [ ] `_audit` rows for each new code; the manual page
      `reference/instrument-files.md`; the reader rulebook if a rule moves.
- [ ] Skill: none expected. The diagnostics carry the guidance (root
      CLAUDE.md § skill, the cheapest place). Revisit if an agent needs a row.

## Acceptance

- The HRPD and POLARIS files read on a local copy, with one diagnostic per
  repair, and nothing else changed (`python -m tests.reader_output` exits 0
  for Rietveld output).
- A synthetic bank whose σ²(d) goes negative inside its range is refused.

```sh
.venv/bin/python -m pytest tests/test_instrument_tof.py tests/test_readers.py
.venv/bin/python -m pytest tests/test_audit_table.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Larson & Von Dreele, *General Structure Analysis System (GSAS)*, LAUR
  86-748, the Technical Manual, pp. 221-223 (records) and p. 144, 148
  (profile functions).
- Issue #1447 and its two comments; PR #1503.
- Howieson 2023 (thesis dataset), Collins et al. 2021, *Angew. Chem.*

## Handover log

- **2026-11-15** — created, from the 2026-11-15 issue triage (issue #1447).
  Checked against the tree at `98d7ba8e3`: refusals (b) and (c) reproduce on
  a synthetic HRPD-shaped bank, and (a) no longer refuses since PR #1503
  declines the set. The sig-2 sign test and the skipped `.gss` header line
  were read in the code, not run. No open WP owns the TOF instrument readers:
  1927 and 2032 are closed, and T-2 is fenced at ROADMAP § v2+. Next: (c)
  needs the GSAS manual, so ask for it first.
