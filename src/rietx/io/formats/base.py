"""Shared machinery for the pattern-format readers.

There is one module per format in this package, because a format's spec
citation, its parser, its ``sniff``/``sigma`` prose, its reader options and its
**licence fence** are one fact each and belong adjacent — ten fences in one file
drift.  What lives *here* is what more than one of them needs: the registry
entry they each construct, and the bounded head read every text sniff shares.
"""

from __future__ import annotations

import codecs
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import ValidationError as PydanticValidationError

from ...schemas.common import Diagnostic
from ...schemas.pattern import AxisKind, PatternData


@dataclass(frozen=True)
class ScanInfo:
    """One measurement inside a file that holds several, as a picker sees it.

    Most vendor formats store a *session* rather than a pattern: a low-angle
    scan and a high-angle one, a survey and a slow rescan of one peak, a series
    of temperatures.  Which of them is "the pattern" is the caller's choice, and
    a choice cannot be offered without saying what the alternatives are.

    Deliberately not a ``PatternData``: enumerating is what happens *before* a
    file is read, and materialising every scan to describe them would make
    opening a picker cost what opening the file costs, several times over.
    """

    index: int
    #: what the file itself calls this scan — its comment or sample name, else
    #: its axis and range.  Never invented: a picker showing "Scan 1" for both
    #: entries has told the user nothing they did not already know
    label: str
    n_points: int
    #: the range the scan **stepped through**, which is 2θ only when the scan is
    #: a 2θ scan.  A file may hold ranges that are not (a ``.uxd`` pole figure
    #: steps φ), and a picker has to show those in order for the person to pick
    #: something else — so the number is the stepped one and :attr:`label` is
    #: what says which axis it is on
    two_theta_range: tuple[float, float]
    #: the specimen temperature this scan records, where the format has such a
    #: field and the file filled it (WP-1110 item 17).  It is what distinguishes
    #: the scans of an in-situ reel from each other: without it an 82-range VT
    #: file enumerates as 82 identical labels, which is the thing :attr:`label`
    #: exists not to do.  ``None`` is "the file says nothing", never "ambient"
    temperature_k: float | None = None


@dataclass(frozen=True)
class PatternFormat:
    """One format :func:`rietx.read_pattern` accepts, and how it is recognised.

    A registry rather than a chain of ``if``s inside ``read_pattern`` because
    three consumers need the *same* facts and each would otherwise restate them:
    the dispatch itself, ``capabilities()`` (which must say what this package
    can actually open — WP-1007), and a project's ``DataRef``, which records
    *which reader claimed the file* so re-opening reproduces the reader call and
    not merely the bytes (WP-1005).

    ``options`` names the reader keywords a caller may have supplied, because
    those have to be recorded and replayed too: a pdCIF holding both a ``_meas``
    and a ``_calc`` block (the NIST SRM certification files do) reads as a
    different pattern depending on ``block``.
    """

    name: str
    title: str
    #: conventional suffixes — informational except where ``sniff`` uses them
    extensions: tuple[str, ...]
    #: how the format is recognised, in words a UI can show
    sniff: str
    #: where per-point σ comes from, or how the Poisson fallback is reached
    sigma: str
    matches: Callable[[Path], bool]
    read: Callable[..., PatternData]
    options: tuple[str, ...] = field(default_factory=tuple)
    #: how to list the measurements this file holds, for a format that can hold
    #: several — ``None`` for one that cannot.  Kept in **biconditional** with
    #: ``"scan" in options`` by a meta-test: a format that lets a caller *choose*
    #: a scan must be able to say what there is to choose between, and one that
    #: cannot hold several has nothing to enumerate.  Two halves of one fact,
    #: written twice only because one is a keyword and the other a parser.
    scans: Callable[[Path], list[ScanInfo]] | None = None
    #: why this format is recognised **in order to be refused**, or ``None`` for
    #: one that reads.  One field rather than a side table, so ``capabilities()``
    #: stays honest without ``reader_formats`` meaning two things: an entry says
    #: for itself whether it is a reader or a refusal.
    refuses: str | None = None


@dataclass(frozen=True)
class ReaderOption:
    """One keyword :func:`rietx.read_pattern` accepts, declared as data.

    Two levels exist because an option is rarely one format's — the ``scan`` of
    a multi-scan vendor file will mean the same thing in five of them — and
    because a caller should not have to know which reader will claim a file in
    order to name one.  So the *vocabulary* lives here and each
    :class:`PatternFormat` names the subset it honours.

    That split is what makes a **typo** distinguishable from an option this
    particular file's format does not take.  The first is a caller error and
    raises; the second is normal — a UI carries a value across a file change —
    and is dropped, but *reported* (``READER_OPTION_IGNORED``), because an API
    caller who passed ``scan=2`` against a single-scan format believed they had
    selected something.

    ``kind`` exists because ``DataRef.options`` is ``dict[str, str]``: a scan
    round-trips through a project as ``"2"`` and has to reach the reader as the
    integer 2.
    """

    name: str
    kind: Literal["str", "int"]
    #: what the option does, in words a UI can put beside its control
    help: str

    def coerce(self, value: Any) -> Any:
        """``value`` as this option's type, or a refusal naming the option."""
        if self.kind == "int":
            try:
                return int(value)
            except (TypeError, ValueError):
                raise ValueError(f"reader option {self.name}= takes an integer, "
                                 f"got {value!r}") from None
        return str(value)


#: Every keyword ``read_pattern`` accepts, across all formats — the allowlist.
#: A meta-test pins it equal to the union of every ``PatternFormat.options``, so
#: neither half can grow an entry the other does not know about.
READER_OPTIONS: dict[str, ReaderOption] = {
    "bank": ReaderOption(
        name="bank", kind="int",
        help="which detector bank to read, by the number the file's own BANK "
             "record declares — a GSAS file commonly holds several, and a "
             "time-of-flight diffractometer *is* several (ISIS GEM writes "
             "six). Not a scan: banks are different detectors, each with its "
             "own scattering angle and calibration, so a file holding more "
             "than one is refused until one is named"),
    "block": ReaderOption(
        name="block", kind="str",
        help="the data block to read, by substring match on its name — a pdCIF "
             "carrying both a _meas and a _calc block is a different pattern "
             "depending on it"),
    "scan": ReaderOption(
        name="scan", kind="int",
        help="which measurement to read, counting from 0, in a file that holds "
             "several — a vendor file commonly stores a whole session. The "
             "scans are ranges of one experiment, never one pattern: they are "
             "selected, never concatenated"),
}


#: Every key a reader may put in ``PatternData.metadata``, and what it holds.
#:
#: Data rather than convention because two consumers *match* on these keys —
#: the import wizard's anode pre-selection, and a preview that shows how many
#: scans a file holds — and neither can match on a name each reader spells for
#: itself.  :func:`metadata` refuses an undeclared key, so a new one is a line
#: here rather than a string that works until someone reads it.
METADATA_KEYS: dict[str, str] = {
    "source_file": "the file's own name, as opened",
    "format": "the registered format that claimed it",
    "block": "the pdCIF data block read, when the file held more than one",
    "title": "the file's own title line, verbatim",
    "sample": "the sample name the file records",
    "x_label": "the x-axis label a file states in prose, verbatim and "
               "un-normalised — the only record of what was actually written",
    "scan_axis": "the goniometer axis scanned, as the file names it",
    "scan": "which scan was read, counting from 0",
    "scan_count": "how many scans the file holds. Carried from the single read "
                  "so a preview never parses a 60 MB file twice",
    "anode": "the X-ray target element the file names",
    "wavelength": "the primary wavelength in Å, as the file states it — "
                  "recorded, never used: the anode presets are the authority",
    "wavelength_alpha2": "the Kα2 wavelength in Å, as the file states it — "
                         "**zero included**, because a file recording a zero is "
                         "saying the doublet was not used, and a format that "
                         "records nothing here is saying nothing",
    "intensity_item": "the pdCIF intensity item read, where it is one whose "
                      "definition says more than a count: "
                      "`_pd_proc_intensity_net`, defined as background-"
                      "subtracted. A label, not a measurement — the reader "
                      "says when the numbers disagree with it",
    "intensity_unit": "the intensity unit the file *declares*. A claim, not a "
                      "measurement — see the σ note in the .ras reader",
    "count_time_s": "seconds per step, where the file gives enough to derive it",
    "temperature_k": "the specimen temperature this scan records, as the file "
                     "states it — recorded, never used. On an in-situ reel it "
                     "is the *series coordinate*, which is the point of the "
                     "experiment: without it a caller has no `x=` to give "
                     "`refine_sequential` and no axis to plot a trajectory "
                     "against. A file that records nothing here says nothing, "
                     "and so does one recording zero",
    "goniometer_radius_mm": "the goniometer radius the file records, in mm — one "
                            "of the four bragg_brentano numbers that need not be "
                            "typed when the file already knows it",
    "beam_optics": "the optic elements a file lists in its beam paths "
                   "(xRayMirror, monochromator, filter), comma-joined and "
                   "named only. Recorded, never used, and **absent means "
                   "undeclared**, not that the beam has none: most files say "
                   "nothing",
    "diffracted_beam_optics": "the part of `beam_optics` that sits after the "
                              "sample. A monochromator there removes Kβ, which "
                              "is the one case `Source.kbeta` acts on; the same "
                              "element before the sample is not mapped. Absent "
                              "means undeclared, as for `beam_optics`",
}


def metadata(**entries: object) -> dict[str, str]:
    """A ``PatternData.metadata`` dict, refusing a key no reader declared.

    Values are stringified here rather than at every call site because the field
    is ``dict[str, str]`` and a reader naturally holds floats and ints; ``None``
    is dropped, so a reader may pass a key it merely *might* have found.
    """
    out: dict[str, str] = {}
    for key, value in entries.items():
        if key not in METADATA_KEYS:
            raise ValueError(f"undeclared pattern metadata key {key!r}; add it to "
                             f"METADATA_KEYS with what it holds, or use one of "
                             f"{sorted(METADATA_KEYS)}")
        if value is not None:
            out[key] = str(value)
    return out


def reader_options_for(fmt: PatternFormat, requested: dict[str, Any], *,
                       diagnostics: list[Diagnostic] | None = None) -> dict[str, Any]:
    """The options ``fmt`` will actually be called with — coerced and filtered.

    One authority, because three callers ask the same question and each would
    otherwise answer it slightly differently: :func:`rietx.read_pattern`
    before dispatching, ``Project`` when recording what the parse *used*, and
    the GUI when a staged file is re-read.  ``None`` means "not specified" and
    is dropped, so ``block=None`` still reads the first block that parses.

    A dropped option is **reported, not silent**: a GUI is free to ignore
    ``READER_OPTION_IGNORED`` (carrying a value across a change of file is what
    a form does), and an API caller who passed ``scan=2`` against a single-scan
    format is not, because they believed they had selected something.
    """
    out: dict[str, Any] = {}
    for name, value in requested.items():
        option = READER_OPTIONS.get(name)
        if option is None:
            raise ValueError(f"unknown reader option {name!r}; read_pattern takes "
                             f"{sorted(READER_OPTIONS)}")
        if value is None:
            continue
        if name not in fmt.options:
            if diagnostics is not None:
                diagnostics.append(Diagnostic(
                    level="info", code="READER_OPTION_IGNORED",
                    message=(f"{name}={value!r} was not applied. {fmt.title} takes "
                             f"{list(fmt.options) or 'no reader options'}."),
                    where=[name],
                    suggestion=("Drop the option, or run identify_format to check "
                                "which reader claimed the file.")))
            continue
        out[name] = option.coerce(value)
    return out


def multiscan_default(n_scans: int, requested: int | None, *, path: str | Path,
                      diagnostics: list[Diagnostic] | None = None) -> None:
    """Say so when scan 0 of several was taken because nobody chose.

    Reading one of a file's scans is a *choice*, and a default that only the GUI
    preview reveals leaves the API and the CLI blind.  Same rule as
    ``INDEX_SHIFT_ALLOWANCE`` one seam over: an assumed selection must never
    look like a deliberate one.  Silent when the file holds one scan (there is
    nothing to choose) or when ``scan`` was given (the choice was made).
    """
    if n_scans <= 1 or requested is not None or diagnostics is None:
        return
    diagnostics.append(Diagnostic(
        level="warning", code="PATTERN_MULTISCAN_DEFAULTED",
        message=(f"{Path(path).name} holds {n_scans} scans and none was named, "
                 f"so scan 0 of {n_scans} was read."),
        where=["scan"],
        suggestion=(f"Pass scan=<0…{n_scans - 1}> to choose, or run "
                    "list_scans(path) to see what each one is.")))


#: How much of a file a *sniff* may look at.  Every text dispatch goes through
#: :func:`head`, so the cost of asking "is this yours?" is bounded no matter how
#: many formats are registered or how large the pattern is.
HEAD_BYTES = 4096

#: Byte-order marks worth recognising, longest-first.  ``utf-16`` (rather than
#: an explicit endianness) is the codec on purpose: it reads the mark to pick
#: LE or BE *and* strips it, which is what a caller decoding the whole file
#: wants.  UTF-32 is deliberately absent — no diffractometer writes it, and
#: guessing at one more encoding would buy nothing but a wrong guess.
_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


@dataclass(frozen=True)
class Head:
    """The first :data:`HEAD_BYTES` of a file, read once and decoded once."""

    #: the bytes actually read, byte-order mark included
    raw: bytes
    #: :attr:`raw` decoded with :attr:`encoding`; undecodable bytes are dropped,
    #: so a *sniff* may always search it and a binary file simply matches nothing
    text: str
    #: the codec to decode the whole file with — the one the mark names, else UTF-8
    encoding: str
    #: whether a byte-order mark was actually found.  Load-bearing beyond the
    #: encoding: ASCII-range UTF-16LE is *valid* UTF-8 with interleaved NULs, so
    #: a mark is what separates "Windows vendor export" from "binary".
    bom: bool


def ascending(x: Any, intensity: Any, sigma: Any = None, *,
              path: str | Path, fmt: PatternFormat | None = None,
              axis: AxisKind = "two_theta",
              diagnostics: list[Diagnostic] | None = None,
              ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """``PatternData``'s strictly-increasing abscissa, or a refusal — never a guess.

    Several formats store a scan measured high→low, and the root CLAUDE.md rule
    fixes what to do about it: a silent correction is a reader's to make, and
    only where the deviation is a **report** rather than a **contradiction**.
    Applied case by case, that is the whole of this function:

    ==============================  ==============  ==========================
    deviation                       verdict         action
    ==============================  ==============  ==========================
    strictly descending             report          reverse; the measurement is
                                                    the same one, stored
                                                    backwards, and reversing is
                                                    lossless
    duplicate 2θ, equal intensity   report          drop the repeat — a format
                                                    artefact, no datum lost
    duplicate 2θ, different y       contradiction   raise: averaging invents a
                                                    datum and dropping picks one
    non-monotone (stitched ranges,  contradiction   raise: concatenate, sort or
    restarts)                                       separate is the caller's
                                                    call, not the reader's
    non-constant step               neither         nothing — SRM 660c is 24
                                                    stitched regions and legal
    ==============================  ==============  ==========================

    The non-monotone refusal names the ``scan`` option **only for a format that
    has one**, which is why it takes ``fmt``: telling someone to select a scan
    in a file that cannot hold several is a wrong instruction, not a vague one.

    ``axis`` is the quantity being ordered, and is only ever used to *name* it:
    every rule above is about the order of a column and holds identically for a
    flight time, but a refusal saying "2θ does not run in one direction" about a
    time-of-flight bank would be a wrong statement in the one place a reader
    gets to explain itself.  ``"two_theta"`` is the default, so every CW message
    is the sentence it always was.
    """
    tt = np.asarray(x, dtype=np.float64)
    y = np.asarray(intensity, dtype=np.float64)
    sig = None if sigma is None else np.asarray(sigma, dtype=np.float64)
    name = Path(path).name
    label = "2θ" if axis == "two_theta" else "the flight time"
    unit = "°" if axis == "two_theta" else " µs"
    # the descending-scan and repeated-value notes name the quantity as well
    noun = "2θ" if axis == "two_theta" else "flight-time"

    step = np.diff(tt)
    # ``<= 0`` with at least one strict descent, so that a descending scan which
    # also repeats a point is reversed and *then* meets the duplicate rule below
    # — the mirror of an ascending one, handled by the same code
    if tt.size > 1 and np.all(step <= 0) and np.any(step < 0):
        tt, y = tt[::-1], y[::-1]
        sig = None if sig is None else sig[::-1]
        step = np.diff(tt)
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="info", code="PATTERN_SCAN_REVERSED",
                message=(f"{name} stores its points from high {noun} to low, "
                         "and they were reversed."),
                where=[axis]))

    if tt.size > 1 and not np.all(step > 0):
        repeat = np.flatnonzero(step == 0.0)
        if repeat.size and np.all(step >= 0):
            differing = repeat[y[repeat] != y[repeat + 1]]
            if differing.size:
                i = int(differing[0])
                raise ValueError(
                    f"{name}: {label} = {tt[i]:.6g}{unit} appears twice with "
                    f"different intensities ({y[i]:.6g} and {y[i + 1]:.6g}), and "
                    f"{differing.size} such point(s) in all. Averaging them "
                    "would invent a datum and dropping one would pick a "
                    "measurement arbitrarily, so neither is the reader's to do")
            keep = np.ones(tt.size, dtype=bool)
            keep[repeat + 1] = False
            tt, y = tt[keep], y[keep]
            sig = None if sig is None else sig[keep]
            if diagnostics is not None:
                diagnostics.append(Diagnostic(
                    level="info", code="PATTERN_DUPLICATE_POINTS",
                    message=(f"{name} repeats {int(repeat.size)} {noun} value(s) with "
                             "the same intensity, and the repeats were dropped."),
                    where=[axis]))
        else:
            i = int(np.flatnonzero(step <= 0)[0])
            extra = (" — if these are separate ranges, name one with scan="
                     if fmt is not None and "scan" in fmt.options else "")
            raise ValueError(
                f"{name}: {label} does not run in one direction — it goes "
                f"{tt[i]:.6g}{unit} → {tt[i + 1]:.6g}{unit} at point {i}. Concatenating, "
                "sorting or separating such ranges are three different "
                f"measurements and choosing between them is yours{extra}")

    return tt, y, sig


def check_axis(stated: str, *, path: str | Path, field: str, two_theta: bool,
               other: str | None = None, remedy: str = "", note: str = "",
               diagnostics: list[Diagnostic] | None = None) -> str | None:
    """The three-way scanned-axis policy, in the one place it now lives.

    Most vendor files are **not powder scans** — four of the five real ``.uxd``
    files obtained are pole figures or rocking curves — and a non-2θ scan parses
    perfectly and refines to a confidently wrong cell.  So every format that
    states its axis answers the same three ways: a recognisable 2θ reads
    silently, a recognisable something-else is **refused by name**, and an
    unrecognisable one is read as 2θ **and says so**.

    What is *not* factored is the recognising.  The four formats state their axis
    in inputs of different shapes — a prose label, a quoted header value, a drive
    name, an XML attribute — so each classifies for itself and passes the verdict
    in as ``two_theta`` / ``other``.  That split is the point: the policy is one
    rule and the vocabularies are four, and mixing them would make adding a
    fifth format an edit to a shared table it does not belong in.

    ``other`` is what the axis *is* ("a rocking curve about ω…"), so the refusal
    says what the file holds rather than only what it lacks; ``remedy`` closes it
    with what to export instead; ``note`` is a format-specific sentence carried
    into **both** messages, because a trap worth naming when the axis is refused
    is worth naming when it is merely assumed — ``.uxd``'s block marker being the
    example that earned it.  Returns the axis as stated, for the metadata.
    """
    name = Path(path).name
    if two_theta:
        return stated or None
    if other is not None:
        raise ValueError(
            f"{name}: {field} is {stated!r}, which is {other} — not a powder "
            "pattern in 2θ. Its points parse perfectly and would refine to a "
            f"cell that is confidently wrong, so it is refused rather than "
            f"read.{note}{' ' + remedy if remedy else ''}")
    if diagnostics is not None:
        says = f"gives {field} = {stated!r}" if stated else f"states no {field}"
        diagnostics.append(Diagnostic(
            level="warning", code="PATTERN_X_AXIS_ASSUMED",
            message=(f"{name} {says}, so the axis is not one this reader "
                     f"recognises. The x column was read as 2θ in degrees.{note}"),
            where=["two_theta"],
            suggestion=(f"Check {field} in the file.")))
    return stated or None


def pattern_data(path: str | Path, x: Any, intensity: Any,
            sigma: Any = None, *, axis: AxisKind = "two_theta",
            **meta: object) -> PatternData:
    """The :class:`PatternData` a reader returns — schema refusals included.

    ``axis`` says which abscissa ``x`` is, and is the *only* way a reader
    declares one: the values themselves never decide, because an ascending
    column of flight times is indistinguishable from an ascending column of
    degrees (``io/CLAUDE.md`` § The axis is never trusted).  Defaults to
    ``"two_theta"``, so every existing reader keeps the axis it always had.

    Constructing the model is a **parser boundary like any other**, and the last
    one every reader crosses.  ``PatternData``'s own validators are right to
    refuse a one-point pattern, but they refuse it as a pydantic
    ``ValidationError`` about a field, which reaches a caller as a wall of schema
    prose that does not say which file was being opened.

    That this is the reader's to convert was found the way these things usually
    are: the truncation harness asserted every refusal names the file, and a
    ``.XRA`` cut short enough to lose its ``BANK`` record passed the assertion
    only because pydantic happened to *echo* the metadata dict — which contained
    the filename — in its report.  Adding one more metadata key pushed the name
    past the echo's truncation and the invariant failed, having never held.
    """
    values = np.asarray(x, dtype=np.float64).tolist()
    try:
        return PatternData(
            two_theta=values if axis == "two_theta" else None,
            tof=values if axis == "tof" else None,
            intensity=np.asarray(intensity, dtype=np.float64).tolist(),
            sigma=None if sigma is None else np.asarray(sigma,
                                                        dtype=np.float64).tolist(),
            metadata=metadata(**meta))
    except PydanticValidationError as exc:
        why = "; ".join(str(e.get("msg", "")).removeprefix("Value error, ")
                        for e in exc.errors())
        raise ValueError(f"{Path(path).name} did not parse into a usable "
                         f"pattern: {why}") from None


def sigma_from_scaled(intensity: Any, scale: Any) -> np.ndarray:
    """σ for a Poisson count that has been multiplied by a **known** factor.

    The Weights invariant's Poisson fallback √max(y, 1) is right for raw detector
    counts and wrong for anything scaled since — by √t for a rate, by √a for a
    point measured behind an attenuator of factor ``a``.  Both are the same
    arithmetic: where ``y = counts · s`` with ``s`` known, the counted quantity is
    ``y/s``, its Poisson σ is √max(y/s, 1), and the stored quantity's σ is that
    times ``s``.

    ``scale`` may be per point, because the attenuator case is: a PANalytical
    beam attenuator engages on a single saturating point and leaves the rest of
    the scan at 1.  Written through the counts rather than as √(y·s) so a channel
    that counted **zero** gets the same floor a counts channel gets instead of a
    zero σ and an infinite weight.
    """
    y = np.asarray(intensity, dtype=np.float64)
    s = np.asarray(scale, dtype=np.float64)
    if not np.all(s > 0):
        raise ValueError(f"an intensity scale must be positive, got {scale!r}")
    return np.sqrt(np.maximum(y / s, 1.0)) * s


def sigma_from_cps(intensity: Any, count_time_s: float) -> np.ndarray:
    """σ for a rate, derived from the counts it was a rate *of*.

    The rate is the counted quantity scaled by ``1/t``, so this is
    :func:`sigma_from_scaled` at that scale and the general function holds the
    floor convention for both.
    """
    if not count_time_s > 0:
        raise ValueError(f"a counting time must be positive, got {count_time_s}")
    return sigma_from_scaled(intensity, 1.0 / count_time_s)


#: How close to an integer a value must be to count as one.  Counts are written
#: as ``13.0000``, so the test is exact up to the decimal text; the tolerance is
#: for the ``y·t`` product, where the file's stored decimals are multiplied.
INTEGRAL_TOL = 1e-3


def integral(values: Any) -> bool:
    """Whether every value is a whole number — the counts test."""
    y = np.asarray(values, dtype=np.float64)
    return bool(y.size) and bool(np.all(np.abs(y - np.round(y)) < INTEGRAL_TOL))


def sigma_by_arithmetic(intensity: Any, count_time_s: float | None,
                        declared: str, *, path: str | Path,
                        diagnostics: list[Diagnostic] | None = None,
                        ) -> np.ndarray | None:
    """σ where the file's own word on its intensity unit cannot be trusted.

    The two Rigaku formats declare the unit in a **free-text** header field, and
    real files get it wrong: one `.ras` declares ``counts`` and stores 84.3047,
    which no scale in 1/1000…200 makes integral, and two of the three real
    ``.rasx`` files do the same.  So the declaration is recorded as metadata and
    never decides σ.  What decides is arithmetic, in the order the evidence
    settles it:

    * all-integer intensities **are** counts, whose σ is the Poisson fallback the
      package already applies — so ``None`` here is the *correct* answer and not
      a missing one;
    * an all-integer ``y·t`` says the stored quantity is that count divided by
      the counting time, and its σ is derived;
    * anything else is undecided, and says so (``PATTERN_INTENSITY_SCALED``) —
      the fallback is then being applied to a quantity that may already be a
      rate, in which case the weights are wrong by √t.

    Contrast the ``.uxd`` and ``.xrdml`` side of this: those declare the unit
    *structurally* — in the token that opens the data block, in an attribute on
    the data element — where it cannot disagree with itself, and are trusted.
    """
    y = np.asarray(intensity, dtype=np.float64)
    if integral(y):
        return None
    if count_time_s is not None and count_time_s > 0 and integral(y * count_time_s):
        return sigma_from_cps(y, count_time_s)
    if diagnostics is not None:
        derived = ("the header gives no scan speed with a unit to derive a "
                   "counting time from" if count_time_s is None else
                   f"a counting time of {count_time_s:.6g} s per step does not "
                   "make them whole numbers either")
        diagnostics.append(Diagnostic(
            level="warning", code="PATTERN_INTENSITY_SCALED",
            message=(f"{Path(path).name} declares its intensity unit as "
                     f"{declared or 'nothing'}, but the stored values are not "
                     f"whole numbers and {derived}. No σ was supplied."),
            where=["sigma"],
            suggestion=("Export the scan in counts, or supply the esds.")))
    return None


def looks_binary(h: Head) -> bool:
    """Whether ``h`` came from a file no text reader should try to decode.

    A NUL byte in the first :data:`HEAD_BYTES` — the test every ``file(1)``-like
    heuristic starts from, and enough here because the alternative is not "guess
    better" but "fall through to the ASCII-column reader", which is what turned
    a Bruker binary into a bare ``UnicodeDecodeError``.

    **One carve-out: a byte-order mark means text, never binary.**  ASCII-range
    UTF-16LE decodes as *valid* UTF-8 with interleaved NULs, Windows vendor
    software genuinely exports it, and calling such a file binary would be the
    confidently-wrong-message class this seam exists to remove.
    """
    return b"\x00" in h.raw and not h.bom


def decode(raw: bytes) -> tuple[str, str, bool]:
    """``raw`` as text, the codec that did it, and whether a mark named one.

    Shared with :func:`head` rather than duplicated because the *container*
    formats need it on bytes that never were a file: a ``.rasx`` member is a
    UTF-8-with-BOM text file inside a zip, and decoding it as plain UTF-8 leaves
    a zero-width space on the front of the first number.
    """
    for mark, codec in _BOMS:
        if raw.startswith(mark):
            return raw.decode(codec, errors="ignore"), codec, True
    return raw.decode("utf-8", errors="ignore"), "utf-8", False


def head(path: str | Path, n: int = HEAD_BYTES) -> Head:
    """The first ``n`` bytes of ``path``, decoded for a sniff.

    Bounded on purpose.  The predecessor of this function decoded a whole file
    and then sliced 4 kB off it, which is an O(N) decode per dispatch on a 60 MB
    pattern.  It is deliberately **not** cached either: ``restage`` re-reads the
    same path, so a path-keyed cache would be a correctness hazard for exactly
    the file a user just replaced.
    """
    with open(path, "rb") as fh:
        raw = fh.read(n)
    text, encoding, bom = decode(raw)
    return Head(raw=raw, text=text, encoding=encoding, bom=bom)
