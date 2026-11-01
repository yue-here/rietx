"""GSAS raw powder data — the FXYE / ESD / STD bank formats.

Spec: Larson & Von Dreele (2004), *GSAS — General Structure Analysis System*,
LAUR 86-748, §"Powder data file formats".

Recognised by its ``BANK`` record rather than by suffix: the format is written
with a zoo of extensions (``.fxye``, ``.gsas``, ``.gda``, ``.xra``, ``.raw``, …)
and the record is unambiguous.  That is also what keeps it disjoint from the
Bruker binary ``.raw``, which is claimed by magic bytes — a GSAS file named
``.raw`` still reaches this reader, and a Bruker file named ``.gsas`` does not.

**The bank record makes two independent declarations and they are read as two.**
The **bintype** says how the x axis is computed; the **type flag** (``STD``,
``ESD``, ``FXYE``, and also ``ALT`` and ``FXY``) says how one data record is laid
out.  Nothing couples them — an ``ESD`` record holds (intensity, esd) pairs
whichever bintype it sits under — so a reader that lets one decide the other
returns a wrong pattern rather than a refusal.  This one did: a non-``CONS`` bank
was *forced* into the FXYE branch behind a divisible-by-three check on its value
count, which a ``RALF`` bank carrying ESD data passes whenever its pair count is
a multiple of three.

**The bintype decides which quantity the x axis holds, and this reader now has
two places to put one.**  ``CONS``/``CONST`` is 2θ — the two spellings are one
rule, a start angle and a step both in centidegrees, and that rule is what the
centidegree fold below rests on.  ``TIME_MAP``, ``RALF`` and ``SLOG`` are
neutron flight times in microseconds and land on ``PatternData.tof``.  The
manual's remaining five put something this package still has nowhere to keep:
another flight time on a clock whose table this reader cannot build (``LOG6``),
a d-spacing (``COND``), a Q (``CONQ``), a detector position (``LPSD``) or a
photon energy (``EDS``), and each is refused by name saying what its axis
actually holds — the third row of the axis policy (``io/CLAUDE.md`` § The axis
is never trusted) reached through the bintype instead of through an axis label.

**A bank is a detector, so which bank is a choice and it is the caller's.**
``read_gsas(path, bank=n)`` selects the record whose own ``BANK`` line declares
*n* — the number a GSAS instrument-parameter file's per-bank ``INS`` records use
too, never a position in the file — and a file holding **several** banks with no
``bank`` is refused naming them.  Returning the first was harmless only while
every readable bank was one 2θ scan of one specimen; a six-bank Mantid
``SaveGSS`` file, which is the ordinary ISIS GEM export, is six detectors with
six scattering angles and six DIFCs, and answering with bank 1 is the silent
selection ``instrument_profile.read_gsas_prm`` refuses a multi-bank file to
avoid.  Measured: a whole real refinement was worked around by splitting such a
file into six single-bank files by hand.  :func:`gsas_banks` is what makes the
choice offerable, and a single-bank file needs no ``bank`` and is unchanged.

**The bintype also decides the fold, which is the trap this format sets.**  The
manual says an FXYE x column is *"centidegrees for CW data or microseconds for
TOF data"* — one column, two units, and nothing in the numbers to tell them
apart: a TOF range of 1000-10000 µs read as centidegrees is a flawless-looking
10-100° scan.  So the fold is taken off the bintype, once, beside the axis
decision itself (the paragraph below says what that cost before).

The match is **exact and never a prefix**, because ``COND`` and ``CONQ`` share
three characters with ``CONS`` and are two of the axes this refuses.

**A time-of-flight axis is read only where the file states it exactly**, which
is not the same as every TOF bank:

- **``TIME_MAP``** tabulates its steps in a separate record — triples of
  (first channel, flight time, step) in clock units, then a terminator — so the
  axis is a table lookup and is exact.  Read in all three record layouts,
  and the terminator is checked against the bank's declared channel count.
- **``RALF``/``SLOG``** carry *binning constants*, not a table, and are read
  only from an **FXYE** record — the layout that writes its own x column, which
  is what Mantid's ``SaveGSS`` (whose default format is ``RALF``) actually
  writes.  Under ``ESD``/``STD`` the axis would have to be synthesized from the
  four coefficients, and that is refused rather than approximated: the manual
  itself says a ``RALF`` step "varies (irregularly) in pseudoconstant Δt/t
  steps", and reconstructing an ISIS GEM bank's axis from its own coefficients
  (start 35328/32 = 1104 µs, Δt/t = 0.004) reproduces the file's explicit
  column only to ~9 × 10⁻³ µs — a **near miss**, which is the one error shape
  a synthesized axis must not have, since nothing downstream can see it.

Real files are not scarce, which is why none of this is hypothetical: GSAS-II's
own tutorial data ships ``SLOG`` and ``RALF`` banks, and on the code this
replaces several read as plausible wrong 2θ patterns — an ISIS PEARL ``RALF``
bank came back as a flawless-looking 2528-point scan from 15.00° to 194.88°,
which no caller could have told from a real one.  **The reference implementation
has the same bug**: the manual says an FXYE x column is *"centidegrees for CW
data or microseconds for TOF data"*, and GSAS-II's ``G2pwd_fxye`` divides by 100
unconditionally, with no bintype branch anywhere in the module.  So "implement it
the way GSAS-II does" was never available — it would have shipped this exact
wrong answer.

**And only ``STD``/``ESD``/``FXYE`` records are read, with every other flag
refused by name.**  ``STD`` is also what a bank that states *no* flag means —
four obtainable real files write the record that way — and that default is why an
unrecognised flag was silent: an ``ALT`` or ``FXY`` bank fell through to
counts-only with an axis synthesized from ``c1``/``c2``, so its own x column
entered the intensity array and a wrong axis took its place.  The symptom was
visible in the output all along: the pattern came back tagged ``gsas-alt``, the
reader having used the flag as a label rather than as a decision.

Neither layout is *implemented*, and here the reason really is the fixture.
Every ``ALT`` file obtainable is also a ``RALF`` bank, so it is refused one
decision earlier for its bintype and cannot exercise an ``ALT`` reader at all;
and no ``FXY`` file was found anywhere.  A record layout is exactly the kind of
fact a fixture is for, so both are named and declined rather than written against
a description.

**And the three layouts that are read differ in whether a field has a position
or only a separator** — behaviour, not style, because it decides whether a
full-width value can fuse with its neighbour:

- **ESD** is positional, written by a Fortran ``FORMAT``: ten 8-character
  fields to an 80-column record, five (intensity, esd) pairs.  Three
  descriptions agree and so does every real file (§ ``_esd_fields``).
- **FXYE** / **FXY** are free-format, one point to a line, and are read by
  splitting on whitespace.  That is the spec's word (GSAS-II splits them) and
  the fixtures corroborate it: ``mg090.fxye``'s tokens are 9 and 10 characters
  wide and its lines run 31–34 characters, so 8-character slicing would
  destroy it.
- **STD** is positional too, and is read by position.  The manual (Larson &
  Von Dreele 2004, LAUR 86-748, "GSAS raw powder file", p. 217) gives the
  record as ``(10(I2,F6.0))`` holding ``(NCTR(I), YO(I))``: a 2-character
  **counter number** — how many counters collected that step, taken as one
  when zero or blank — then a 6-character count per counter.  The two are
  separate quantities, so a whitespace split is right only while the counter
  field is blank, as it is in ``FAP.XRA``; a bank that writes it (the GSAS-II
  tutorial *Magnetic-IV* pattern, counter numbers 1 to 20) came back with the
  counter numbers interleaved among the counts (issue #1061).  The value is
  read as written; the counter number is checked and not folded into it,
  because the manual states the esd only as σ = √I and does not say how it
  follows when NCTR > 1 — so an STD bank still takes the Poisson fallback on
  the value as written, and any NCTR above one is reported through
  ``PATTERN_INTENSITY_SCALED`` with the range found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import AxisKind, PatternData
from .base import PatternFormat, ascending, head, pattern_data

#: The bintypes read: a start angle and a step, both in centidegrees.  The
#: manual's token is ``CONS`` and real files write both spellings; they are the
#: same rule, so they are one entry's worth of fact rather than two.  Matched
#: **exactly** — ``COND`` and ``CONQ`` below share three characters with these
#: and are different axes, so a prefix test would swallow them.
_ANGLE_BINTYPES = frozenset({"CONS", "CONST"})

#: The bintypes whose x axis is a **neutron flight time in microseconds**, and
#: what each one's binning is.  Each description says how the axis is
#: established, because that is what decides whether it can be read at all:
#: ``TIME_MAP`` tabulates it, the other two state constants a reader would have
#: to integrate.  ``SLOG``'s third coefficient is 4e-4 … 3e-3 across four
#: independent files and the channel ratio matches it, so it really is Δt/t and
#: not Δt.  ``RALF`` is deliberately *not* called log-step: it is constant-width
#: at short flight times and only pseudo-Δt/t beyond a coefficient that says
#: where — the ISIS GEM bank measured here (``BANK 1 797 797 RALF 35328 141
#: 35328 0.00400 FXYE``) puts that coefficient at the *start*, so that bank is
#: log-stepped throughout.  A ``TIME_MAP`` bank carries a map *number* where the
#: others carry coefficients (``BANK 1 6537 1308 TIME_MAP 1 ESD``), so its steps
#: are tabulated elsewhere in the file.
_TOF_BINTYPES = {
    "RALF": "a time-of-flight binning (constant step at short flight times, "
            "pseudo-constant Δt/t beyond), so its x axis is a flight time",
    "SLOG": "a constant-Δt/t (log-step) time-of-flight binning, so its x axis "
            "is a flight time",
    "TIME_MAP": "a time-of-flight binning whose step table is a separate "
                "TIME_MAP record elsewhere in the file",
}

#: Of those, the ones whose steps are **tabulated** rather than merely
#: parameterised, and which can therefore be read in any record layout.  A
#: ``TIME_MAP`` bank is the LANSCE way of writing one; the others are
#: what Mantid writes, and Mantid writes them with their own x column.
_TABULATED_TOF_BINTYPES = frozenset({"TIME_MAP"})

#: The bintypes still refused, and what each one actually puts on the x axis.
#: None is a 2θ and none is a flight time this reader can establish, which is
#: the whole reason they are refused — a matter of **scope** (``LOG6``'s Model 6
#: clock table is not in the manual's data file at all; ``COND``/``CONQ``/
#: ``LPSD``/``EDS`` are quantities ``PatternData`` has no field for) rather than
#: of evidence.  Sources for the descriptions, since a wrong one in a refusal is
#: still a wrong statement: the bintype list and each definition are the GSAS
#: manual's (LAUR 86-748, §"Powder data file formats"), corroborated by real
#: bank records where one was obtainable.  And ``EDS`` is energy-dispersive, not
#: time-of-flight, which is why this is one table of five rather than a "TOF"
#: set.
_NON_ANGLE_BINTYPES = {
    "COND": "a constant-Δd binning, so its x axis is a d-spacing",
    "CONQ": "a constant-ΔQ binning, so its x axis is a Q",
    "EDS": "an energy-dispersive binning, so its x axis is a photon energy",
    "LOG6": "a logarithmic time-of-flight binning for the Los Alamos Model 6 "
            "clock, so its x axis is a flight time on a clock whose step table "
            "this reader cannot build",
    "LPSD": "a linear position-sensitive-detector binning, so its x axis is a "
            "detector position",
}

#: The record layouts read.  A bank that states **no** flag is legal and means
#: ``STD``; that default is the reason an unrecognised flag was silent, since
#: falling through to it looks exactly like a file that declared nothing.
_TYPE_FLAGS = frozenset({"STD", "ESD", "FXYE"})

#: The type flags named and refused, and what each one holds.  Both are a layout
#: this parser does not have, and both were read as *counts only* by the STD
#: branch — an ``ALT`` record's x and error columns entering the intensity array,
#: an ``FXY`` record's x column doing the same while the axis is synthesized from
#: ``c1``/``c2`` in its place.  Neither is implemented, and here the reason is
#: the fixture: every obtainable ``ALT`` file is also a ``RALF`` bank, so it is
#: refused one decision earlier and cannot exercise an ``ALT`` reader at all, and
#: no ``FXY`` file was found anywhere.  The shapes are *known* — the manual gives
#: ALT as four ``(x, intensity, error)`` points to an 80-column record on a
#: 20-character stride, ``NREC = ceil(NCHAN/4)``, and FXY as two free-format
#: values — and knowing a shape is still not having a fixture to test it against.
#: Which matters here more than usual: for ALT the manual's own Fortran format
#: and GSAS-II's scale factors **disagree**, by 100× on x and 10× on y and esd,
#: so there is no reading of the two sources that is safe without a file.
_UNIMPLEMENTED_FLAGS = {
    "ALT": "an x, intensity and error triple on a fixed stride",
    "FXY": "an x and intensity pair with no esd",
}


#: A ``BANK`` record may sit behind a ``#`` (issue #230: two copies of one 2013
#: measurement differed by two bytes, the ``#`` some tool prepended to the title
#: and bank lines).  Missed, the file fell to ``xy`` and its centidegrees were
#: read as degrees, 100× too large and in silence.  The commented form must
#: carry the whole loose header — bank, channel count, record count, bintype —
#: because a comment in an ASCII export may mention a bank in passing, and
#: claiming that file would turn a readable ``.xy`` into a refusal.  Only ``#``:
#: it is the one marker a real file has shown.
_SNIFF_BANK_RE = re.compile(
    r"^BANK\s+\d+|^#[ \t]*BANK[ \t]+\d+[ \t]+\d+[ \t]+\d+[ \t]+[A-Za-z]", re.M)
_BANK_COMMENT_RE = re.compile(r"^#[ \t]*(?=BANK\s)")
_SNIFF_TIME_MAP_RE = re.compile(r"^TIME_MAP", re.M)

#: A ``TIME_MAP`` step table is written *before* the bank it feeds, and a long
#: one pushes the first ``BANK`` record past the 4 kB ``head`` window the sniff
#: reads — a real HIPD@LANSCE file (``vnb5053.dat`` from the GSAS distribution's
#: own examples) carries a 71-row ``(10I8)`` table and its first bank sits at
#: byte 6068, so the sniff missed it and the file fell to the ``xy`` catch-all,
#: which read its fixed-format records as columns and refused with the wrong
#: cause (a 2θ axis the file never had).  The ``TIME_MAP`` token is itself
#: GSAS-shaped evidence and it *does* land in the first 4 kB (it opens the
#: table), so a file showing it is read once more up to this bound to look past
#: the table for the bank.  This is the ``.chi`` count-check discipline
#: (``io/CLAUDE.md`` § Dispatch): an extra read only behind a shape gate a random
#: pattern never trips, never a widened window for every file.  A table larger
#: than this stays unsniffed — the same bounded tradeoff the 4 kB window itself
#: makes, one order of magnitude further out.
_GSAS_TIME_MAP_SCAN_BYTES = 64 * 1024


def looks_gsas(p: Path) -> bool:
    h = head(p)
    if _SNIFF_BANK_RE.search(h.text):
        return True
    # No bank in the first 4 kB, but a TIME_MAP table — which is what pushes the
    # bank past that window — leaves its own token there.  One more bounded read.
    if _SNIFF_TIME_MAP_RE.search(h.text):
        return bool(_SNIFF_BANK_RE.search(head(p, _GSAS_TIME_MAP_SCAN_BYTES).text))
    return False


#: The bank record's own header, matched loosely — bank number, channel count,
#: record count, bintype.  That prefix is common to every bintype while the
#: coefficients that follow are not: a ``CONS`` bank writes a start angle and a
#: step, but a ``TIME_MAP`` bank writes a lone map number.  The strict ``CONS``
#: parse in :func:`read_gsas` needs two coefficients, so matching *first* with
#: it would skip a ``TIME_MAP`` bank entirely and report a missing ``BANK``
#: record — the wrong cause — for a file that plainly has one.  So the axis
#: decision is taken off the header, before the layout.
_BANK_HEAD_RE = re.compile(r"^BANK\s+(\d+)\s+(\d+)\s+(\d+)\s+(\w+)")

#: The strict ``CONS`` record: the same header, then the start angle and step.
#: The flag is a keyword and must begin with a letter — it is the *last* field,
#: after up to four bintype coefficients, so a record writing an odd number of
#: them leaves a coefficient where the flag would be, and ``\w*`` captured that
#: digit as a flag (``BANK 1 4 4 CONST 1000 20 0`` tagged its pattern
#: ``gsas-0``).  A number there is absence, not a flag.
_BANK_RE = re.compile(
    r"^BANK\s+(\d+)\s+(\d+)\s+(\d+)\s+(\w+)\s+([\d.Ee+-]+)\s+([\d.Ee+-]+)"
    r"(?:\s+([\d.Ee+-]+)\s+([\d.Ee+-]+))?\s*([A-Za-z]\w*)?")


@dataclass(frozen=True)
class GSASBank:
    """One ``BANK`` record of a GSAS file, as a picker sees it.

    The bank counterpart of :class:`~rietx.io.formats.base.ScanInfo`, and
    deliberately **not** that class: a vendor file's scans are ranges of one
    experiment on one instrument, while a GSAS file's banks are *different
    detectors* — their own scattering angle, their own DIFC, their own
    resolution — which is why they are selected with ``bank=`` rather than
    ``scan=`` and enumerated by this function rather than by
    :func:`rietx.io.readers.list_scans`.

    :attr:`x_range` is the quantity the bank's own bintype puts on the
    abscissa, and :attr:`axis` is what says which: degrees for a ``CONS``
    bank, microseconds for a flight-time one.  A single number carrying two
    units is what the centidegree fold already made this format's trap, so the
    range is never quoted without the axis beside it.  ``axis`` is ``None``
    for a bank that is neither (``COND``, ``CONQ``, ``LPSD``, ``EDS``, an
    unknown bintype), which this reader cannot open.  ``x_range=None`` means this
    bank could not be read at all, and :attr:`refused` then carries the
    reader's own sentence saying why (a ``RALF`` bank of ``ESD`` records, an
    ``ALT`` layout) — reported rather than raised, because enumerating a file
    must not fail on account of one bank a caller may not have wanted.
    """

    number: int
    bintype: str
    #: the record layout as declared, ``"STD"`` for a bank stating no flag
    type_flag: str
    n_channels: int
    axis: AxisKind | None
    x_range: tuple[float, float] | None
    refused: str | None = None


def _bank_records(lines: list[str]
                  ) -> tuple[list[tuple[int, str, "re.Match[str]"]], bool]:
    """Every ``BANK`` record as ``(line index, the record, its header match)``.

    Live records only, unless the file has none: then every *commented* one
    (issue #230, :data:`_BANK_COMMENT_RE`), with the second value ``True`` so
    the caller can say so.  A commented record beside a live one is never a
    bank, because commenting a bank out is also how a person disables it —
    which is why the two are never pooled into one list to choose from.
    """
    for commented in (False, True):
        out = []
        for i, line in enumerate(lines):
            bare = _BANK_COMMENT_RE.sub("", line, count=1) if commented else line
            if commented and bare == line:
                continue
            m = _BANK_HEAD_RE.match(bare)
            if m:
                out.append((i, bare, m))
        if out:
            return out, commented
    return [], False


def gsas_banks(path: str | Path) -> list[GSASBank]:
    """What there is to choose between in a GSAS file that holds several banks.

    The companion to :func:`read_gsas`'s ``bank=``, and it exists for the
    reason :func:`rietx.io.readers.list_scans` does: a choice cannot honestly
    be offered without saying what the alternatives are.  A six-bank Mantid
    ``SaveGSS`` export — the ordinary ISIS GEM file — is six measurements at
    six scattering angles, and "bank 3" is not a number a caller can guess.

    One :class:`GSASBank` per record, in file order, including the banks this
    reader cannot open: a bank whose axis is not establishable comes back with
    ``x_range=None`` and its own refusal in ``refused`` rather than raising,
    since a file's *listing* must not fail on account of a bank nobody asked
    for.  Every readable bank's range is read through :func:`read_gsas`
    itself, so there is no second spelling of the axis arithmetic to drift
    from the first.
    """
    p = Path(path)
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    records, _ = _bank_records(lines)
    if not records:
        raise ValueError(f"no BANK record found in {p}")
    out: list[GSASBank] = []
    for i, (_, bank_line, head_m) in enumerate(records):
        bintype = head_m.group(4).upper()
        tail = bank_line.split()[5:]
        token = next((t for t in tail if t[:1].isalpha()), None)
        flag = (token or "STD").upper()
        axis: AxisKind | None = ("two_theta" if bintype in _ANGLE_BINTYPES else
                                 "tof" if bintype in _TOF_BINTYPES else None)
        x_range: tuple[float, float] | None = None
        refused: str | None = None
        try:
            data = _read_bank(p, lines, records, i, None)
        except ValueError as exc:
            refused = str(exc)
        else:
            x = data.tof if data.axis == "tof" else data.two_theta
            x_range = (float(x[0]), float(x[-1])) if x else None
        out.append(GSASBank(number=int(head_m.group(1)), bintype=bintype,
                            type_flag=flag, n_channels=int(head_m.group(2)),
                            axis=axis, x_range=x_range, refused=refused))
    return out


def _first_bank_number(path: str | Path) -> int | None:
    """The number the file's *first* BANK record declares, or None.

    For one caller: Project.open re-reading a pattern whose recorded reader
    call predates bank=.  Such a project was created when this reader
    answered a multi-bank file with its first bank, and an old project must
    always open — so the reopen asks for that bank by number rather than
    tripping the "which one?" refusal that exists for a *new* call.
    """
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    records, _ = _bank_records(lines)
    return int(records[0][2].group(1)) if records else None


def read_gsas(path: str | Path, *, bank: int | None = None,
              diagnostics: list[Diagnostic] | None = None) -> PatternData:
    """GSAS raw powder data — a 2θ or a time-of-flight bank, STD/ESD/FXYE.

    The bintype and the type flag are two independent decisions and are taken
    as two: ``_check_bintype`` settles which *quantity* the x axis holds, the
    flag settles how one record is laid out, and only their **combination**
    settles whether the axis can be built (§ the module docstring: a ``RALF``
    bank states its binning where a ``TIME_MAP`` bank tabulates it).

    ``bank`` selects one record **by the number the record itself declares**,
    not by position, because that is the number every other file of the
    experiment uses — a GSAS instrument-parameter file's ``INS  3ICONS`` and
    :func:`rietx.io.instrument_tof.read_gsas_tof_iparm`'s ``{3: Instrument}``
    both mean the bank the data file writes as ``BANK 3``.

    **A file holding several banks and no ``bank=`` is refused**, naming the
    banks it holds.  This reader returned the first one for its whole life,
    which was a harmless simplification only while every readable bank was
    2θ: a six-bank Mantid ``SaveGSS`` file — the ordinary ISIS GEM export — is
    six *different detectors*, and answering with bank 1 is the silent
    selection :func:`rietx.io.instrument_profile.read_gsas_prm` refuses a
    multi-bank file to avoid.  Measured: a whole real refinement was worked
    around by splitting such a file into six single-bank files by hand.  A
    single-bank file needs no ``bank=`` and is unchanged, which is every
    pattern this package ships and every constant-wavelength file it has been
    measured on; :func:`gsas_banks` is what says what a multi-bank file holds.

    Mixed-axis files stay refused whatever ``bank`` says
    (:func:`_one_axis_per_file`): which bank was asked for cannot make a file
    that disagrees with itself about its own abscissa agree.
    """
    p = Path(path)
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    records, commented = _bank_records(lines)
    if not records:
        raise ValueError(f"no BANK record found in {p}")
    # ... refused across the whole file *before* a bank is chosen, because
    # reading one bank of a mixed file would answer a question the caller did
    # not ask (§ ``_one_axis_per_file``).
    _one_axis_per_file(records, p)
    which = _select_bank(p, records, bank)
    if commented and diagnostics is not None:
        line_no = records[which][0] + 1
        diagnostics.append(Diagnostic(
            level="info", code="GSAS_BANK_COMMENTED",
            message=(
                f"{p.name} has no live BANK record, so its commented one "
                f"(line {line_no}: {lines[line_no - 1].strip()!r}) "
                "was read as the bank record."),
            where=[f"line {line_no}"],
            suggestion=(
                "Check that the bank was not commented out on purpose to "
                "disable it."),
        ))
    return _read_bank(p, lines, records, which, diagnostics)


def _select_bank(p: Path, records: list[tuple[int, str, "re.Match[str]"]],
                 bank: int | None) -> int:
    """Which record :func:`read_gsas` reads — the index into ``records``.

    Three answers, and the middle one is the whole point of the argument: one
    bank needs no choice, a named bank is looked up by its **declared**
    number, and several banks with nothing named is refused rather than
    answered by write order.
    """
    numbers = [int(m.group(1)) for _, _, m in records]
    if bank is None:
        if len(records) == 1:
            return 0
        described = ", ".join(str(n) for n in numbers)
        raise ValueError(
            f"{p.name}: this GSAS file holds {len(records)} banks ({described}) "
            f"and none was named. A bank is a detector — its own scattering "
            f"angle, its own calibration, its own resolution — so which one is "
            f"'the pattern' is a choice, and returning the first would make it "
            f"silently. Pass bank=<n> (the number the BANK record declares), "
            f"or call rietx.io.formats.gsas.gsas_banks(path) to see what each "
            f"one is.")
    if bank not in numbers:
        described = ", ".join(str(n) for n in numbers)
        raise ValueError(
            f"{p.name}: no BANK {bank} in this file — it holds bank(s) "
            f"{described}. The number is the one the BANK record declares, "
            f"which is also what a GSAS instrument-parameter file's per-bank "
            f"INS records use, not a position in the file.")
    if numbers.count(bank) > 1:
        raise ValueError(
            f"{p.name}: this file declares BANK {bank} "
            f"{numbers.count(bank)} times. Which of them bank={bank} means is "
            f"not established by the file, and picking the first would decide "
            f"it by write order.")
    return numbers.index(bank)


def _read_bank(p: Path, lines: list[str],
               records: list[tuple[int, str, "re.Match[str]"]], which: int,
               diagnostics: list[Diagnostic] | None) -> PatternData:
    """One selected ``BANK`` record's rows as a :class:`PatternData`.

    Everything :func:`read_gsas` did before it could be asked for a bank
    other than the first: the two independent declarations, the axis decision
    only their pair can take, and the layout parse.  Split out so
    :func:`gsas_banks` reads a bank's range through this one authority rather
    than a second spelling of it.
    """
    start_line, bank_line, head_m = records[which]
    data_start = start_line + 1
    nchan = int(head_m.group(2))
    bintype = head_m.group(4).upper()
    # decision one: which quantity the x axis holds.  Refused before the data is
    # parsed, since a bintype nobody can read is not made readable by its rows —
    # and refused off the header, so a bintype whose coefficient count is not the
    # CONS two (TIME_MAP writes one) is named for what it is rather than lost as
    # an unparseable record.
    _check_bintype(bintype, p)
    axis: AxisKind = "two_theta" if bintype in _ANGLE_BINTYPES else "tof"
    # decision two, and independent of the first: how one record is laid out.
    # Read two ways, because the *coefficients* differ per bintype and the
    # strict CONS regex is a statement about CONS records only: it wants two
    # numeric coefficients, a TIME_MAP bank writes a lone map number, and its
    # ``[\d.Ee+-]+`` coefficient class would happily swallow the ``E`` of an
    # ``ESD`` flag standing where the second coefficient should be.
    c1 = c2 = 0.0
    if axis == "two_theta":
        bank = _BANK_RE.match(bank_line)
        if bank is None:
            raise ValueError(
                f"{p.name}: this is a CONS/CONST bank but its record could not "
                f"be read for a start angle and step — {bank_line.strip()!r}")
        c1, c2 = float(bank.group(5)), float(bank.group(6))
        type_flag = _type_flag(bank.group(9), p)
    else:
        # The flag is the record's last field and the only one that begins with
        # a letter, whatever the coefficient count before it — which is the
        # same rule the CONS regex spells positionally.
        tail = bank_line.split()[5:]
        type_flag = _type_flag(
            next((t for t in tail if t[:1].isalpha()), None), p)
    # decision three, and the one only the *pair* can take: whether the axis is
    # establishable at all.
    if axis == "tof":
        _check_tof_axis_is_establishable(bintype, type_flag, p)

    body: list[str] = []
    for line in lines[data_start:]:
        # the next record header ends this bank, and the manual has two: a
        # BANK record, commented or not, and a TIME_MAP record.  A file's
        # header-plus-records sets "may be repeated in any order", the time
        # map only "usually" heading the file (GSAS Technical Manual p. 219),
        # so a map may follow a bank's rows; read on, it was refused as a
        # malformed data record of this bank.
        if (_BANK_COMMENT_RE.sub("", line, count=1).startswith("BANK")
                or line.startswith("TIME_MAP")):
            break
        # A ``#`` in column 1 is a comment, not a datum, and Mantid's SaveGSS
        # writes one *between* banks — an ISIS GEM file puts "# Total flight
        # path 18.7634m, tth 18.059deg, DIFC 1488.76" and "# Data for spectrum
        # :0" after each bank's last row.  Skipped rather than terminating the
        # body, because the row after it is still this bank's neighbour's, and
        # skipped in column 1 only: every layout read here is either positional
        # (ESD, STD) or free-format numeric (FXYE), so a data record can never
        # begin with one.
        if line.startswith("#"):
            continue
        body.append(line)

    # ESD and STD banks are positional and are read as such (§ ``_esd_fields``,
    # § ``_std_fields``); FXYE is free-format and split on whitespace.  Each flavour tokenises
    # its own body, so the ESD path — the big one — never pays for the ~99 000
    # throwaway tokens a whole-body split would build for a branch it never
    # takes.
    if type_flag == "FXYE":
        # FXYE: explicit x column, then y, esd.  **The bintype decides the
        # unit** — the manual says this column is "centidegrees for CW data or
        # microseconds for TOF data", and nothing in the numbers distinguishes
        # them, so the fold is taken off the axis decision and never off the
        # values.
        values = _floats([t for line in body for t in line.split()], p, type_flag)
        arr = _reshape(values, 3, p, type_flag)
        x = arr[:, 0] / 100.0 if axis == "two_theta" else arr[:, 0]
        y = arr[:, 1]
        sig = arr[:, 2]
    elif type_flag == "ESD":
        arr = _reshape(_esd_fields(body, p), 2, p, type_flag)
        # ``arr`` holds the zero pairs padding the last record to ten fields,
        # so the axis is built for the declared count, as the STD branch does
        x = _synth_axis(axis, bintype, lines, bank_line, c1, c2,
                        min(len(arr), nchan), p)
        y, sig = arr[:, 0], arr[:, 1]
    else:  # STD: counts only, positional (counter number, value); Poisson esd
        values, counters = _std_fields(body, p)
        y = np.array(values, dtype=np.float64)[:nchan]
        x = _synth_axis(axis, bintype, lines, bank_line, c1, c2, len(y), p)
        sig = None
        _std_counter_diagnostic(p, counters[:nchan], diagnostics)

    n = min(len(x), nchan) if type_flag != "FXYE" else len(x)
    x, y = x[:n], y[:n]
    sigma = None
    if sig is not None:
        sig = sig[:n]
        sigma = sig.tolist() if np.any(sig > 0) else None
    # drop zero-esd leading/trailing channels (detector gaps)
    if sigma is not None:
        good = np.asarray(sigma) > 0
        x, y = x[good], y[good]
        sigma = np.asarray(sigma)[good].tolist()
    x, y, sig = ascending(x, y, sigma, path=p, fmt=GSAS, axis=axis,
                          diagnostics=diagnostics)
    return pattern_data(p, x, y, sig, axis=axis,
                   source_file=p.name, format=f"gsas-{type_flag.lower()}")


def _synth_axis(axis: AxisKind, bintype: str, lines: list[str], bank_line: str,
                c1: float, c2: float, n: int, p: Path) -> np.ndarray:
    """The abscissa for a record layout that does not carry its own x column.

    Two arithmetics, one per axis, and both are the bank record's own
    declaration rather than anything read off the data: a ``CONS`` start angle
    and step in centidegrees, or a ``TIME_MAP``'s tabulated step table.  Only
    those two reach here — ``_check_tof_axis_is_establishable`` has already
    refused a ``RALF``/``SLOG`` bank whose axis would have to be integrated
    from four coefficients.
    """
    if axis == "two_theta":
        return (c1 + c2 * np.arange(n)) / 100.0
    return _time_map_axis(lines, bank_line, n, p)


#: A ``TIME_MAP`` record's own header: the map number, how many values the
#: table holds, how many records they occupy, the token again, and the **clock
#: width in nanoseconds**.  Read from the header rather than assumed, because
#: it is the whole conversion to microseconds and it is per file: a header
#: ending ``TIME_MAP 100`` declares a 100 ns clock, on which a first channel
#: of 20000 ticks is 2000 µs.
_TIME_MAP_RE = re.compile(
    r"^TIME_MAP\s+(\d+)\s+(\d+)\s+(\d+)\s+TIME_MAP\s+([\d.Ee+-]+)")

#: Width of one field of a ``TIME_MAP`` table record, in characters.  The table
#: is written ``(10I8)`` — ten 8-character integers to an 80-column record, the
#: same Fortran discipline (and the same field width) as an ESD data record,
#: the last record short when the count is not a multiple of ten.
TIME_MAP_FIELD_CHARS = 8


def _time_map_axis(lines: list[str], bank_line: str, n: int,
                   p: Path) -> np.ndarray:
    """A ``TIME_MAP`` bank's flight times in µs, from its tabulated step table.

    The table is a list of **triples** — (first channel, flight time, step),
    all in clock ticks — followed by one terminating flight time, and it says
    that from ``channel`` onwards each channel's *start* is ``step`` ticks
    after the one before it.  Between triples the step changes; within one it
    does not.  Reading it is therefore a piecewise-linear lookup and the axis
    is **exact**, which is why this bintype is read in every record layout
    while ``RALF``/``SLOG`` are not.

    The terminator is the start the last triple extrapolates for the channel
    after the bank's declared count, and that agreement is asserted below
    rather than assumed: it is the one internal check the format offers, and a
    map read one field out of step would still produce a plausible axis.

    The value returned is the **bin centre**, ``start + step/2``, because that
    is where the counts in a channel are attributed and it is what the
    ``RALF``/``SLOG`` FXYE columns hold (measured: an ISIS GEM bank's first
    channel spans 1104.000-1108.416 µs and its FXYE x is 1106.1995).
    """
    want = _map_number(bank_line, p)
    for i, line in enumerate(lines):
        m = _TIME_MAP_RE.match(line)
        if m and int(m.group(1)) == want:
            nval, nrec = int(m.group(2)), int(m.group(3))
            try:
                clock_ns = float(m.group(4))
            except ValueError:
                raise ValueError(
                    f"{p.name}: the TIME_MAP {want} record's clock width "
                    f"{m.group(4)!r} is not a number of nanoseconds") from None
            break
    else:
        seen = sorted({int(m.group(1)) for m in
                       (_TIME_MAP_RE.match(x) for x in lines) if m})
        held = ("the file holds maps " + ", ".join(map(str, seen)) if seen
                else "the file holds no TIME_MAP record at all")
        raise ValueError(
            f"{p.name}: this bank's record names TIME_MAP {want}, and no "
            f"TIME_MAP record with that number is in the file ({held}). A "
            f"TIME_MAP bank's x axis is the map and nothing else, so there is "
            f"no axis to read.")
    values: list[int] = []
    for raw in lines[i + 1:i + 1 + nrec]:
        line = raw.rstrip()
        for start in range(0, len(line), TIME_MAP_FIELD_CHARS):
            field = line[start:start + TIME_MAP_FIELD_CHARS].strip()
            if field:
                try:
                    values.append(int(field))
                except ValueError:
                    raise ValueError(
                        f"{p.name}: the TIME_MAP {want} table holds {field!r} "
                        f"where a clock tick was expected — the table is not "
                        f"the {TIME_MAP_FIELD_CHARS}-character integer format "
                        f"a TIME_MAP record is written in") from None
    if len(values) != nval or nval % 3 != 1:
        raise ValueError(
            f"{p.name}: the TIME_MAP {want} record declares {nval} values in "
            f"{nrec} records and {len(values)} were read; a map is triples of "
            f"(first channel, flight time, step) plus one terminating flight "
            f"time, so its count is 3k + 1. The table is truncated or its "
            f"header disagrees with it.")
    table = np.asarray(values[:-1], dtype=np.int64).reshape(-1, 3)
    terminator = values[-1]

    start = np.zeros(n, dtype=np.float64)
    step = np.zeros(n, dtype=np.float64)
    for j, (c0, t0, dt) in enumerate(table):
        c1 = int(table[j + 1][0]) if j + 1 < len(table) else n + 1
        idx = np.arange(int(c0), min(c1, n + 1))
        if idx.size:
            start[idx - 1] = t0 + (idx - int(c0)) * dt
            step[idx - 1] = dt
    if start[0] == 0.0 and step[0] == 0.0:
        raise ValueError(
            f"{p.name}: the TIME_MAP {want} table does not cover channel 1 — "
            f"its first triple starts at channel {int(table[0][0])}, so the "
            f"bank's opening channels have no flight time at all")
    last = table[-1]
    extrapolated = int(last[1]) + (n - int(last[0])) * int(last[2])
    if terminator not in (extrapolated, extrapolated + int(last[2])):
        raise ValueError(
            f"{p.name}: the TIME_MAP {want} table terminates at {terminator} "
            f"clock ticks, and its last triple {tuple(int(v) for v in last)} "
            f"puts channel {n} at {extrapolated}. The map and the bank's "
            f"channel count disagree, so the flight time of every channel "
            f"after the last triple would be a guess.")
    return (start + 0.5 * step) * clock_ns / 1000.0


def _map_number(bank_line: str, p: Path) -> int:
    """The TIME_MAP number a bank record points at — its first coefficient.

    Refused by name when the record states none or states something that is not
    an integer: reading such a bank against the file's map 1 would pass the
    terminator check whenever map 1 happened to fit, with no diagnostic, and a
    reader repairs a file only where it can say so.
    """
    fields = bank_line.split()
    try:
        return int(fields[5])
    except (IndexError, ValueError):
        stated = fields[5] if len(fields) > 5 else "nothing"
        raise ValueError(
            f"{p.name}: this TIME_MAP bank's record states {stated!r} where "
            f"the number of its time map belongs — {bank_line.strip()!r}. "
            f"Which map the channels follow is not established by the file, "
            f"and assuming map 1 would read a bank against a table it may not "
            f"own.") from None


def _one_axis_per_file(records: list[tuple[int, str, "re.Match[str]"]],
                       p: Path) -> None:
    """Refuse a file whose banks are not all on the same **kind** of axis.

    A file holding a CONS bank and a TIME_MAP bank would come back with the
    *quantity* on its abscissa decided by whichever was written first, so the
    whole file's bank records are scanned and a mixed file is
    refused naming both axes.

    **Taken before a bank is chosen, and ``bank=`` cannot weaken it.**  The
    two refusals answer different questions and only one of them a caller can
    settle: which bank is *the pattern* is a choice (:func:`_select_bank`), and
    what the pattern's abscissa *means* is not — a file that disagrees with
    itself about that is wrong whichever bank is asked for.
    """
    kinds: dict[str, list[str]] = {}
    for _, _, m in records:
        bintype = m.group(4).upper()
        if bintype in _ANGLE_BINTYPES:
            kinds.setdefault("2θ in degrees", []).append(bintype)
        elif bintype in _TOF_BINTYPES:
            kinds.setdefault("a flight time in microseconds", []).append(bintype)
    if len(kinds) > 1:
        described = "; ".join(
            f"{', '.join(sorted(set(v)))} → {k}" for k, v in sorted(kinds.items()))
        raise ValueError(
            f"{p.name}: this file's banks are not all on the same quantity "
            f"({described}). This reader returns one bank, and which one it "
            f"returned would decide what the x axis of the pattern *means* — "
            f"so the file is refused rather than answered by write order. Split "
            f"it, or export the bank you want on its own.")


#: The bintypes read, for a message that has to list them.
_READ_BINTYPES = sorted(_ANGLE_BINTYPES | set(_TOF_BINTYPES))


def _check_bintype(bintype: str, p: Path) -> None:
    """Pass a bintype whose axis this package can hold; refuse the rest **by name**.

    This is the x-axis decision and nothing else — the type flag is read
    separately, because a bank's binning says nothing about how its records are
    packed.  Conflating the two is what let a ``RALF`` bank holding ESD pairs be
    read as three-column FXYE whenever its pair count divided by three.

    Two quantities now pass: an angle (``CONS``/``CONST``) and a neutron flight
    time (``TIME_MAP``/``RALF``/``SLOG``).  Whether the flight time can actually
    be *built* is a separate question, taken once the record layout is known —
    :func:`_check_tof_axis_is_establishable`.
    """
    if bintype in _ANGLE_BINTYPES or bintype in _TOF_BINTYPES:
        return
    what = _NON_ANGLE_BINTYPES.get(bintype)
    if what is not None:
        raise ValueError(
            f"{p.name}: this is a GSAS {bintype} bank — {what}, so it is "
            f"neither a 2θ nor a TOF.  The bintypes read are "
            f"{', '.join(_READ_BINTYPES)} — an angle in centidegrees or a "
            f"neutron flight time in microseconds, the two quantities "
            f"PatternData can hold.  There is nowhere for this one to go, and "
            f"reading it as either of them anyway is a plausible wrong answer "
            f"rather than a near miss.  Convert the pattern first.")
    raise ValueError(
        f"{p.name}: unrecognised GSAS bintype {bintype!r} in the bank record — "
        f"the bintypes read are {', '.join(_READ_BINTYPES)} (a 2θ in "
        f"centidegrees, or a flight time in microseconds).  The manual's others "
        f"({', '.join(sorted(_NON_ANGLE_BINTYPES))}) are recognised and "
        f"refused, each naming what its x axis holds; this is not one of those "
        f"either, so what this file's x axis means is not established at all.")


def _check_tof_axis_is_establishable(bintype: str, type_flag: str,
                                     p: Path) -> None:
    """Refuse a TOF bank whose axis would have to be *approximated*.

    The decision only the bintype **and** the record layout can take together.
    An FXYE record carries its own x column, so any TOF bintype is exact under
    it.  A ``TIME_MAP`` bank tabulates its steps, so it is exact under any
    layout.  What is left — a ``RALF`` or ``SLOG`` bank of ESD pairs or bare
    counts — would need the axis integrated from the four bank coefficients,
    and neither can be done exactly:

    * ``RALF``'s own manual entry says the step "varies (**irregularly**) in
      pseudoconstant Δt/t steps" beyond its third coefficient, i.e. the
      coefficients describe the binning rather than define it.  Measured: an
      ISIS GEM bank's coefficients (start 35328/32 = 1104 µs, first width
      141/32 = 4.40625 µs, log part from 1104 µs, Δt/t = 0.004) reproduce that
      same bank's explicit FXYE column only to ~9 × 10⁻³ µs — 8 × 10⁻⁶ of the
      flight time, so every peak would land a fraction of a channel off with
      nothing downstream able to see it.
    * ``SLOG``'s Δt/t binning *is* exact arithmetic, and no file writing it
      under ESD or STD was obtainable — the same reason ``ALT`` and ``FXY`` are
      named and declined (§ the module docstring).  A record layout is exactly
      the kind of fact a fixture is for.

    So both are refused *for this layout only*, naming the layout that works,
    which is also the one their writer actually emits: Mantid's ``SaveGSS``
    defaults to ``RALF`` with ``DataFormat=FXYE``.
    """
    if type_flag == "FXYE" or bintype in _TABULATED_TOF_BINTYPES:
        return
    raise ValueError(
        f"{p.name}: this is a GSAS {bintype} bank of {type_flag} records — "
        f"{_TOF_BINTYPES[bintype]}, which is read, but only from a layout that "
        f"states the flight times.  An {type_flag} record carries no x column, "
        f"so the axis would have to be rebuilt from the bank's four binning "
        f"coefficients, and for {bintype} that is an approximation rather than "
        f"a reconstruction — a peak a fraction of a channel out of place, which "
        f"nothing downstream can detect.  Re-export the bank as FXYE (Mantid's "
        f"SaveGSS writes that by default), or as TIME_MAP, whose step table is "
        f"exact.")


def _type_flag(token: str | None, p: Path) -> str:
    """The record layout the bank declares; a flag not implemented **is named**.

    This is the layout decision and nothing else — the bintype is checked
    separately.  Two cases have to stay apart, and only one of them is a
    refusal:

    * **No flag at all** is legal and means ``STD``, counts only.  Real fixtures
      and the inline writers both write the record that way, so the default
      stays.
    * **A flag this parser has no layout for** used to reach that same default
      silently, so an ``ALT`` or ``FXY`` bank was read as counts-only with an
      axis synthesized from ``c1``/``c2`` — a plausible wrong pattern out of a
      file that said, in the record, exactly what it was.  The old code even
      tagged the result ``gsas-alt``: the reader knew the name and used it as a
      label rather than as a decision.
    """
    if not token:
        return "STD"
    flag = token.upper()
    if flag in _TYPE_FLAGS:
        return flag
    needs = _UNIMPLEMENTED_FLAGS.get(flag)
    if needs is not None:
        raise ValueError(
            f"{p.name}: this bank's type flag is {flag} — {needs}, which this "
            f"reader has no layout for.  Only STD, ESD and FXYE records are "
            f"read (a bank stating no flag at all is STD).  {flag} is declined "
            f"rather than guessed at: through the STD branch it would put this "
            f"file's own x column into the intensities and synthesize an axis "
            f"from the bank record in its place, which is a plausible wrong "
            f"pattern and not an error.")
    raise ValueError(
        f"{p.name}: unrecognised GSAS bank type flag {flag!r} — only STD, ESD "
        f"and FXYE records are read, and a bank stating no flag at all is STD.  "
        f"{', '.join(sorted(_UNIMPLEMENTED_FLAGS))} are recognised and refused; "
        f"this is not one of those either, so how its records are laid out is "
        f"not established at all.")


#: Width of one field of an **ESD** (or **STD**) bank's data record, in characters.  A
#: specification fact, and three descriptions state it: the beamline that wrote
#: the files this fixes — APS 11-BM, *Data Formats*
#: (https://11bm.xray.aps.anl.gov/users/filetypes), "*the intensities and their
#: uncertainties (esd) are alternated with five pair of numbers per line (8
#: characters per number), as described in the GSAS manual*"; the manual it
#: points at, Larson & Von Dreele (2004), LAUR 86-748, §"Powder data file
#: formats"; and GSAS-II's own ``G2pwd_fxye.py``, whose ESD reader takes
#: ``S[i:i+8]`` and ``S[i+8:i+16]`` on a 16-character stride — read as a *fact*
#: from a permissively-licensed code, per ``ATTRIBUTION.md`` § Format
#: specifications, with no line of it transcribed.  The files agree
#: independently: every data record of all six real ESD/STD banks obtainable
#: here is exactly 80 characters holding exactly ten non-blank fields.
ESD_FIELD_CHARS = 8


def _esd_fields(body: list[str], p: Path) -> list[float]:
    """An ESD bank's numbers, read **positionally** rather than by separator.

    Splitting on whitespace is right until a value fills its field.  An
    intensity of 100000.0 or more occupies all eight characters, leaves no
    separating space, and fuses with the esd in front of it — real APS 11-BM
    standards patterns do this (``11BM_LaB6.raw`` line 1050 pairs an esd of
    298.5 with an intensity of 101641.3 as ``298.5101641.3``), and the line
    then yields nine numbers instead of ten.  Whichever way that lands — a
    refusal on the two dots, or a plausible wrong number on a bank whose
    values carry no decimal point — the row has lost a value and every channel
    after it is shifted.  So the field's *position* is what is read.

    Blank fields: a data record is padded with explicit zeros in every real
    file (measured on all six), so a blank field is only ever a truncated or
    short final record and is skipped rather than read as a Fortran zero —
    there is no obtainable file in which an interior field is blank, and
    inventing a datum for a hole is the one repair a reader may not make.
    """
    out: list[float] = []
    for lineno, raw in enumerate(body, start=1):
        line = raw.rstrip()
        for start in range(0, len(line), ESD_FIELD_CHARS):
            field = line[start:start + ESD_FIELD_CHARS].strip()
            if not field:
                continue
            try:
                out.append(float(field))
            except ValueError:
                raise ValueError(
                    f"{p.name}: characters {start + 1}-"
                    f"{start + ESD_FIELD_CHARS} of data record {lineno} of the "
                    f"ESD bank hold {field!r}, which is not a number — the "
                    f"record is not the {ESD_FIELD_CHARS}-character fixed "
                    "format an ESD bank is written in") from None
    return out


def _std_fields(body: list[str], p: Path) -> tuple[list[float], list[int]]:
    """An STD bank's values, read **positionally**: ``(I2, F6.0)`` per field.

    Larson & Von Dreele (2004), LAUR 86-748, "GSAS raw powder file", p. 217:
    the profile is ``(NCTR(I), YO(I), I=1,NCHAN)`` in ``(10(I2,F6.0))``, ten
    8-character fields to a record, each a 2-character counter number then a
    6-character value; a counter number of zero or blank is taken as one.  The
    value is what is returned.  The counter number is validated (an integer
    where one is written) and **not** folded into the value or its esd: the
    manual gives the esd of an STD point only as σ = √I, and how σ follows
    when more than one counter collected a step is not stated there, so this
    reader does not decide it (issue #1061).

    A wholly blank field ends a short final record and is skipped, as in
    :func:`_esd_fields`; a field with a counter number and no value, or a
    value that is not a number, is refused naming the record and columns.
    Returns the values and, beside them, each field's counter number with a
    blank or zero read as one, as the manual does.
    """
    out: list[float] = []
    counters: list[int] = []
    for lineno, raw in enumerate(body, start=1):
        line = raw.rstrip()
        for start in range(0, len(line), ESD_FIELD_CHARS):
            field = line[start:start + ESD_FIELD_CHARS]
            if not field.strip():
                continue
            counter, value = field[:2].strip(), field[2:].strip()
            where = (f"{p.name}: characters {start + 1}-"
                     f"{start + ESD_FIELD_CHARS} of data record {lineno} of "
                     f"the STD bank hold {field!r}")
            if counter and not counter.isdigit():
                raise ValueError(
                    f"{where}, whose first two characters are not a counter "
                    "number — the record is not the (I2, F6.0) fixed format "
                    "an STD bank is written in") from None
            try:
                out.append(float(value))
            except ValueError:
                raise ValueError(
                    f"{where}, whose last six characters are not a number — "
                    "the record is not the (I2, F6.0) fixed format an STD "
                    "bank is written in") from None
            counters.append(max(int(counter or 0), 1))
    return out, counters


def _std_counter_diagnostic(p: Path, counters: list[int],
                            diagnostics: list[Diagnostic] | None) -> None:
    """Say so when an STD bank's counter number exceeds one.

    The manual (Larson & Von Dreele 2004, p. 217) does not say whether ``YO``
    is then a total over the counters or a per-counter mean, so the scale the
    intensities are on is not established: σ stays withheld and the value as
    written (``src/rietx/io/CLAUDE.md`` § σ, "Neither settles it").
    """
    if diagnostics is None or not counters or max(counters) <= 1:
        return
    lo, hi = min(counters), max(counters)
    found = f"{lo} to {hi}" if lo != hi else f"{hi}"
    diagnostics.append(Diagnostic(
        level="warning", code="PATTERN_INTENSITY_SCALED",
        message=(f"{p.name}: the STD bank's counter numbers (NCTR) run {found}"
                 ", where more than one counter collected a step. The GSAS "
                 "manual does not say whether the value is then the total "
                 "over the counters or a per-counter mean, so the scale of "
                 "the intensities is not established. The values are read as "
                 "written and no σ was supplied."),
        where=["sigma"],
        suggestion="Export the scan in counts, or supply the esds."))


def _floats(tokens: list[str], p: Path, flag: str) -> list[float]:
    """``tokens`` as floats, or a refusal that names the file.

    ``float()``'s own complaint is ``could not convert string to float:
    '298.5101641.3'`` — true, and it names neither the file nor the format, so
    it reaches ``preview_pattern`` as a refusal a user cannot act on.  The
    general rule (a reader raises ``ValueError`` **naming the file**) applied
    at this parser's free-format boundary.
    """
    out: list[float] = []
    for token in tokens:
        try:
            out.append(float(token))
        except ValueError:
            raise ValueError(
                f"{p.name}: the {flag} bank holds {token!r} where a number "
                "was expected") from None
    return out


def _reshape(values: list[float], width: int, p: Path, flag: str) -> np.ndarray:
    """``values`` as N rows of ``width``, or a refusal that names the file.

    numpy's own complaint is ``cannot reshape array of size 527 into shape
    (3)`` — a true statement about an array, from a user who asked to open a
    diffraction pattern.  Converting here is the general rule (a reader raises
    ``ValueError``/``OSError`` **naming the file**) applied at this parser's own
    boundary; a truncated file is the ordinary way to reach it.
    """
    if width and len(values) % width:
        raise ValueError(
            f"{p.name}: the {flag} bank holds {len(values)} numbers, which is "
            f"not a whole number of {width}-column rows — the file is truncated "
            "or its bank record disagrees with its data")
    return np.array(values, dtype=np.float64).reshape(-1, width)


GSAS = PatternFormat(
    name="gsas",
    title="GSAS raw powder data (FXYE / ESD / STD)",
    extensions=(".fxye", ".gsas", ".gda", ".xra", ".raw"),
    sniff="a BANK record in the first 4 kB — by content, not by suffix — or, "
          "when a TIME_MAP step table (which is what pushes the first bank past "
          "that window) leaves its token there, one more bounded read further "
          "in. A bank record behind a '#' counts when it carries the whole "
          "header, and is read only where the file has no live one "
          "(GSAS_BANK_COMMENTED). A CONS/CONST bank is a 2θ in centidegrees "
          "and a TIME_MAP, RALF or SLOG bank a flight time in microseconds; "
          "the remaining five bintypes (COND, CONQ, EDS, LOG6, LPSD) and every "
          "type flag but STD, ESD and FXYE (ALT, FXY) are named and refused. "
          "A file holding several banks needs bank=<n>",
    sigma=("the third column (FXYE) or second (ESD); an STD bank — which is "
           "also what a bank stating no type flag is — carries counts only and "
           "takes the Poisson fallback"),
    matches=looks_gsas,
    read=read_gsas,
    options=("bank",),
)
