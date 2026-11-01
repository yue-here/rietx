"""Time-of-flight instrument-parameter files: one frozen ``Instrument`` per bank.

A calibration, not a model and not a pattern: each reader returns
:class:`~rietx.schemas.instrument.Instrument` objects whose
:class:`~rietx.schemas.instrument.TOFSource` carries DIFC/DIFA/ZERO(/DIFB), the
bank angle, the profile coefficients and the incident spectrum — every
parameter ``vary=False``, because a value read from an instrument file was
refined against a standard.  No writer exists for either format.

GSAS-I ``.iparm`` / ``.prm`` / ``.inst`` — :func:`read_gsas_tof_iparm`
---------------------------------------------------------------------
Larson & Von Dreele (2004), *GSAS — General Structure Analysis System*,
LAUR 86-748, GSAS Technical Manual p. 221-223: 80-character records with a
12-character key, read **by column** from the manual's FORTRAN formats, the
bank number ``bb`` in columns 5-6.

* ``INS   BANK  `` (I5, NBANK) and ``INS   HTYPE `` (2X,A4) are required.  The
  histogram type must begin ``PNT`` — powder, neutron, time-of-flight
  (manual p. 182, 222); anything else is refused by name.
* ``INS bb ICONS`` (3F10.0,10X,F10.0,I5,F10.0) holds DIFC, DIFA, ZERO in µs
  units for a TOF bank and **nothing else**: POLA, IPOLA and KRATIO "are absent
  for neutron data" (p. 222).  Absent means blank or zero, which the record's
  FORTRAN format reads identically: "A field of all blanks is considered to be
  zero" (ANSI X3.9-1978, FORTRAN 77, §13.5.9 item (1)).  So each of the three
  is read in its own columns (53-62, 63-67, 68-77) and refused only when it is
  non-zero or not a number.  A field with blanks between its characters is
  read as the standard reads it under the default ``BLANK='NULL'`` (blanks
  ignored, §12.10.1); ``BLANK='ZERO'`` would make those blanks zero digits,
  which changes a value but never whether it is zero, so the verdict does not
  depend on a mode the file does not state.  There is no DIFB field in GSAS-I;
  ``difb`` is 0.
* ``INS bbBNKPAR`` (5F10.0,2I5) gives DIST and TTHETA; TTHETA is the bank's
  scattering angle 2Θ in degrees and is required (DIFC alone cannot give it
  back), DIST is carried as ``l2_m`` — the field's name is its only
  definition, so that mapping is an inference and is metadata only.
* ``INS   FPATH1`` — not in the manual's list, written by SNS files — is the
  primary flight path L₁ in metres, carried as ``l1_m`` on every bank; read
  as one number, its layout being only observed (:func:`_primary_flight_path`
  holds the evidence that it is L₁).
* ``INS bbI ITYP`` (I5,2F10.4,I10) — ITYP, TMIN, TMAX, CHKSUM.  TMIN/TMAX are
  in **milliseconds** (p. 223) and are carried in µs.  CHKSUM's algorithm is
  not published: it is read and never recomputed or checked, and since the
  schema has no slot for it, it is reported as dropped.
* ``INS bbICOFFc`` (4E15.6, c = 1…3) — the twelve coefficient slots, in
  TOF-in-milliseconds (p. 223); ``INS bbIECOFc`` their esds, carried as each
  coefficient's ``stderr``.  A block that disagrees with its ITYP — a missing
  or out-of-sequence record, a non-zero slot the type does not read, a
  non-zero ITYP 1/2 fifth pair (its exponent is established by conformance,
  not by the documented layout; ``legacy.read_lansce_iparm`` reads it), ITYP 10 (the
  spectrum is in another file), an undefined ITYP — is refused by name
  (:mod:`rietx.model.tof_spectrum`).  ``IECOR`` has no slot and is dropped.
  No ``ITYP`` record at all is read as no spectrum.
* ``INS bbPRCFn `` (2I5,F10.5; PTYP, NCOF, CTOF) and ``INS bbPRCFnc``
  (4E15.6) — the NTYP profile sets; **set n = 1 is the default** whatever its
  PTYP (p. 223) and is the only set read.

**Named assumption — PRCF coefficient order.**  The manual lists each
function's coefficients "respectively" against their GSAS names (function 1,
p. 144: ``alp-0 alp-1 bet-0 bet-1 sig-0 sig-1 sig-2 s1ec s2ec rstr rsta rsca``;
function 2, p. 147: fifteen; function 3, p. 148: ``alp bet-0 bet-1 sig-0 sig-1
sig-2 gam-0 gam-1 gam-2 g1ec g2ec gsf rstr rsta rsca L11 L22 L33 L12 L13 L23``)
but never says that is the order in the record.  It is the only ordering the
documentation offers and it is adopted as such.  A block whose NCOF is not the
documented 12 / 15 / 21 for PTYP 1 / 2 / 3 is refused, never padded or
truncated.  Profile functions 2 (Ikeda-Carpenter), 4 and 5 are documented but
not evaluated by this package: a default set of one of them is refused by
name; a non-default one is reported and skipped.  The anisotropic and
peak-shift coefficients of functions 1 and 3 belong with the microstructure
machinery, so a non-zero one is refused rather than dropped.  ``CTOF`` is "a
cutoff factor" (p. 223) and nothing more in the manual: it is read, reported,
and never used to set a window.

**Column overrun.**  Reading by column, a value written one field too wide
is silently *truncated*: ``61.20`` placed in columns 30-34 leaves ``61.`` in
TTHETA's columns 23-32, which reads as 61.0.  So every parsed record (BANK,
ICONS, BNKPAR, I ITYP, ICOFF/IECOF, the default PRCF set's header and
coefficient records) is tested at each field boundary, a ``10X`` skip and the
columns after the last field (to 80) counting as spans a right-aligned
writer leaves blank.  At a boundary where the left span's last column **and**
the right span's first column are both non-blank, the pair is two packed
full-width fields only if the right span holds no blank at all — a
right-aligned field whose first column is occupied is full.  Any blank in
the right span means a token began on the left and stopped inside the right
span, which no right-aligned field produces, and the record is refused
naming its key, both fields' columns and the raw text.  Blank fields keep
their FORTRAN reading of zero.

What this cannot see, stated rather than hidden:

* **an overrun that ends exactly on a field boundary** — ``       61.`` then
  ``6000000000`` is, character for character, two full-width fields, and the
  two halves read as 46.0 and 6000000000;
* **a whole-field shift** — a value placed entirely inside the wrong field,
  left- or right-aligned, crosses no boundary and reads as a well-formed
  number in the wrong slot (a TTHETA moved into TILT's columns reads TTHETA
  as blank, i.e. zero);
* **mixed alignment is refused though FORTRAN would read it**: a full
  right-aligned field followed by a *left*-aligned one (``      2.5061.20``)
  is legal FORTRAN input (blanks in a numeric field are null by default),
  but on the page it is the overrun's signature, and right-aligning the
  second value costs nothing.

``HTYPE`` is text, not a number, and is not tested; a shifted histogram type
already fails the ``PNT`` test.  The ``.instprm`` reader splits ``key:value``
lines and slices no columns, so none of this applies to it.

GSAS-II ``.instprm`` — a ``Type: PNT`` file of :func:`rietx.read_gsas2_instprm`
------------------------------------------------------------------------------
**One public reader, dispatching on the file's own ``Type``**: ``.instprm`` is
one suffix under one program and the file states which quantity it holds, so
:func:`rietx.io.instrument_profile.read_gsas2_instprm` looks for a ``Type``
line reading ``PNT`` and hands such a file's *path* to :func:`read_tof_instprm`
here.  Both arms return an ``Instrument``; the source union's ``kind`` is what
a caller discriminates on.  The file is handed over whole, not as the
constant-wavelength arm's parsed items, so this reader keeps its own grammar
and nothing on the time-of-flight path was written from another program's
source (``ATTRIBUTION.md``).

The published GSAS-II documentation names the TOF parameters
(``alpha, beta-0, beta-1, beta-q, sig-0, sig-1, sig-2, sig-q, difA, difB,
difC, Zero``, with ``X``/``Y`` for Lorentzian sample broadening) and gives
``TOF = C·d + A·d² + B/d + Z``, but it does **not** publish the file's grammar,
nor the d-laws of ``beta-q``, ``sig-q``, ``Z``, ``X`` or ``Y``.  So the grammar
read here is an *observed* subset, not a specification:

* one bank per file; a line is either blank, a comment starting ``#``, or
  ``key:value`` split at the first colon, both sides stripped; a repeated key
  is refused (it is how a second bank would appear, and multi-bank delimiting
  is not published);
* ``Type`` must be present and begin ``PNT``;
* ``2-theta`` (the bank angle in degrees, the key's own spelling being its
  only definition) and ``difC`` must be present;
* mapped: ``difC``→difc, ``difA``→difa, ``difB``→difb, ``Zero``→tzero,
  ``alpha``→**alpha1** (GSAS profile function 3 has α = α₁/d, manual p. 148;
  alpha0 = 0), ``beta-0``, ``beta-1``, ``sig-0``, ``sig-1``, ``sig-2`` (the
  last three variance coefficients, used as written);
* named but unmappable — ``beta-q``, ``sig-q``, ``Z``, ``X``, ``Y`` and the
  constant-wavelength names ``SH/L``, ``Polariz.``, ``Lam`` — are accepted
  only at exactly 0 (reported as dropped) and refused otherwise;
* observed metadata ``Bank``, ``fltPath``, ``Azimuth`` are reported as
  dropped;
* **any other key is refused, spelled out** — never read as zero.

Every refusal names the file.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from ..model.tof_spectrum import _coefficient_count
from ..schemas.common import Diagnostic, Parameter
from ..schemas.instrument import IncidentSpectrum, Instrument, ProfileTOF, TOFSource
from .projects.gsas import split_records

#: Documented coefficient names, in the manual's "respectively" order (p. 144,
#: 147, 148) — the only ordering the documentation offers (module docstring).
PRCF_COEFFICIENT_NAMES: dict[int, tuple[str, ...]] = {
    1: ("alp-0", "alp-1", "bet-0", "bet-1", "sig-0", "sig-1", "sig-2",
        "s1ec", "s2ec", "rstr", "rsta", "rsca"),
    2: ("alp-0", "alp-1", "beta", "switch", "sig-0", "sig-1", "sig-2",
        "gam-0", "gam-1", "gam-2", "stec", "ptec", "difc", "difa", "zero"),
    3: ("alp", "bet-0", "bet-1", "sig-0", "sig-1", "sig-2", "gam-0", "gam-1",
        "gam-2", "g1ec", "g2ec", "gsf", "rstr", "rsta", "rsca",
        "L11", "L22", "L33", "L12", "L13", "L23"),
}

#: Which documented names land on which :class:`ProfileTOF` field.
_PRCF_TO_PROFILE: dict[int, dict[str, str]] = {
    1: {"alp-0": "alpha0", "alp-1": "alpha1", "bet-0": "beta0", "bet-1": "beta1",
        "sig-0": "sig0", "sig-1": "sig1", "sig-2": "sig2"},
    3: {"alp": "alpha1", "bet-0": "beta0", "bet-1": "beta1", "sig-0": "sig0",
        "sig-1": "sig1", "sig-2": "sig2", "gam-0": "gam0", "gam-1": "gam1",
        "gam-2": "gam2"},
}

#: Documented profile functions this package does not evaluate, and why.
_PRCF_NOT_EVALUATED: dict[int, str] = {
    2: "the Ikeda-Carpenter function (manual p. 145-147), a causal shape with a "
       "different peak origin from the back-to-back pair",
    4: "profile function 4 (manual p. 149)",
    5: "profile function 5 (manual p. 155)",
}

#: Each parsed record's FORTRAN layout as contiguous ``(first, last, name)``
#: column spans (GSAS Technical Manual p. 221-223) — what
#: :meth:`_Record.check_columns` tests for a number crossing a boundary.  A
#: ``10X`` skip is a span too: a right-aligned writer leaves it blank.
_BANK_FIELDS = ((13, 17, "NBANK"),)
_ICONS_FIELDS = ((13, 22, "DIFC"), (23, 32, "DIFA"), (33, 42, "ZERO"),
                 (43, 52, "the 10X skip"), (53, 62, "POLA"), (63, 67, "IPOLA"),
                 (68, 77, "KRATIO"))
_BNKPAR_FIELDS = ((13, 22, "DIST"), (23, 32, "TTHETA"), (33, 42, "TILT"),
                  (43, 52, "SEPN"), (53, 62, "HGHT"), (63, 67, "NTUBE"),
                  (68, 72, "ITUBE"))
_ITYP_FIELDS = ((13, 17, "ITYP"), (18, 27, "TMIN"), (28, 37, "TMAX"),
                (38, 47, "CHKSUM"))
_PRCF_FIELDS = ((13, 17, "PTYP"), (18, 22, "NCOF"), (23, 32, "CTOF"))
_E15_FIELDS = tuple((13 + 15 * k, 27 + 15 * k, f"coefficient field {k + 1}")
                    for k in range(4))

#: The one sentence a strict refusal adds for the legacy LANSCE layout.
_LEGACY_POINTER = (". An 8-coefficient type-1 block is the legacy LANSCE "
                   "layout, read on request by "
                   "rietx.io.legacy.read_lansce_iparm")

#: .instprm keys mapped onto the schema.
_INSTPRM_SOURCE = {"difC": "difc", "difA": "difa", "difB": "difb", "Zero": "tzero"}
_INSTPRM_PROFILE = {"alpha": "alpha1", "beta-0": "beta0", "beta-1": "beta1",
                    "sig-0": "sig0", "sig-1": "sig1", "sig-2": "sig2"}
#: Named in the documentation but with no d-law (or no TOF meaning) published.
_INSTPRM_ZERO_ONLY = ("beta-q", "sig-q", "Z", "X", "Y", "SH/L", "Polariz.", "Lam")
_INSTPRM_METADATA = ("Bank", "fltPath", "Azimuth")


def _note(diagnostics, level, code, message, where=()):
    if diagnostics is not None:
        diagnostics.append(Diagnostic(level=level, code=code, message=message,
                                      where=list(where)))


class _Record:
    """One 80-column record, with 1-based column access and a located error.

    Records are numbered as :func:`_read_records` returns them (blank lines
    are not records), which is the number an error message quotes.
    """

    def __init__(self, path: Path, number: int, text: str):
        self.path = path
        self.number_in_file = number
        self.text = text.rstrip("\r\n").ljust(80)

    def cols(self, a: int, b: int) -> str:
        return self.text[a - 1:b]

    def fail(self, message: str) -> ValueError:
        return ValueError(f"{self.path}: record {self.number_in_file} "
                          f"({self.text[:12].rstrip()!r}): {message}")

    def number(self, a: int, b: int, what: str) -> float:
        s = self.cols(a, b).strip()
        if not s:
            return 0.0          # a blank FORTRAN numeric field reads as zero
        try:
            return float(s.replace("D", "E").replace("d", "e"))
        except ValueError:
            raise self.fail(f"{what} in columns {a}-{b} is {s!r}, which is not "
                            f"a number") from None

    def integer(self, a: int, b: int, what: str) -> int:
        s = self.cols(a, b).strip()
        if not s:
            return 0
        try:
            return int(s)
        except ValueError:
            raise self.fail(f"{what} in columns {a}-{b} is {s!r}, which is not "
                            f"an integer") from None

    def e15_block(self) -> list[str]:
        """The four 4E15.6 fields (columns 13-72), raw."""
        self.check_columns(_E15_FIELDS)
        return [self.cols(13 + 15 * k, 27 + 15 * k) for k in range(4)]

    def check_columns(self, fields: tuple[tuple[int, int, str], ...]) -> None:
        """Refuse a number that runs across a field boundary (module docstring,
        § Column overrun).

        ``fields`` is the record's FORTRAN layout as contiguous ``(first, last,
        name)`` spans from column 13; the columns after the last field, to 80,
        are one more span a right-aligned writer leaves blank.  At each
        boundary, a non-blank last column on the left beside a non-blank first
        column on the right is two full fields only if the right span holds no
        blank at all; any blank in it means a token began on the left and
        stopped short of the right span's end, which no right-aligned field
        produces.
        """
        spans = list(fields)
        if spans[-1][1] < 80:
            spans.append((spans[-1][1] + 1, 80, "the columns after the last field"))
        for (a1, b1, n1), (a2, b2, n2) in zip(spans, spans[1:]):
            left, right = self.cols(a1, b1), self.cols(a2, b2)
            if left[-1] == " " or right[0] == " " or " " not in right:
                continue
            start = b1
            while start > a1 and self.text[start - 2] != " ":
                start -= 1
            end = a2 + right.index(" ") - 1
            raise self.fail(
                f"the text {self.text[start - 1:end]!r} in columns {start}-{end} "
                f"runs across the boundary between {n1} (columns {a1}-{b1}) and "
                f"{n2} (columns {a2}-{b2}). Read by column, {n1} would be "
                f"{left.strip()!r} and {n2} would begin {right.strip()!r} — a "
                f"misaligned field, refused rather than read as a truncated "
                f"number; right-align each value inside its columns")


def _read_records(path: Path) -> list[tuple[str, str]]:
    """The file's ``(12-character key, payload)`` records, in file order.

    The splitting is the package's one GSAS card-index grammar,
    :func:`rietx.io.projects.gsas.split_records` (80-character records, a
    12-character key, the payload from column 13 — GSAS Technical Manual
    p. 221), so a column means the same thing
    here as in the experiment-file and constant-wavelength ``.prm`` readers.
    Only the splitting is shared: every field is read below by this module's
    own column parser, which refuses a non-numeric field rather than reading
    it as blank.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise OSError(f"{path}: cannot be read ({exc})") from exc
    return split_records(raw.decode("latin-1"))


def _read_lines(path: Path) -> list[str]:
    """An ``.instprm``'s lines (the grammar :func:`read_gsas2_instprm` states)."""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1").splitlines()
    except OSError as exc:
        raise OSError(f"{path}: cannot be read ({exc})") from exc


# ---------------------------------------------------------------------------
# GSAS-I
# ---------------------------------------------------------------------------
def _htype_refusal(path: Path, htype: str) -> ValueError:
    kinds = {"P": "powder", "S": "single-crystal"}
    rads = {"N": "neutron", "X": "x-ray"}
    data = {"T": "time-of-flight", "C": "constant-wavelength",
            "E": "energy-dispersive"}
    h = htype.ljust(4)
    if h[0] in kinds and h[1] in rads and h[2] in data:
        extra = (" A constant-wavelength powder .prm is read by "
                 "rietx.read_gsas_prm." if h[2] == "C" and h[0] == "P" else "")
        return ValueError(
            f"{path}: HTYPE {htype!r} is a {kinds[h[0]]} {rads[h[1]]} "
            f"{data[h[2]]} histogram type (GSAS Technical Manual p. 182); this "
            f"reader reads only neutron time-of-flight powder banks, HTYPE "
            f"PNT….{extra}")
    return ValueError(f"{path}: unrecognised GSAS HTYPE {htype!r}; a neutron "
                      f"time-of-flight powder bank is PNTR (GSAS Technical "
                      f"Manual p. 182, 222)")


#: The ICONS fields a neutron bank leaves absent (manual p. 222): POLA and
#: KRATIO are F10.0, IPOLA is I5.
_ICONS_ABSENT = tuple(f[:3] for f in _ICONS_FIELDS if f[2] in ("POLA", "IPOLA", "KRATIO"))
#: FORTRAN 77 input forms, blanks already removed: I editing an optionally
#: signed integer constant (§13.5.9.1); F editing an optional sign, digits
#: optionally containing a decimal point, then an optional exponent written
#: as E or D and an optionally signed integer, or as a signed integer alone
#: (§13.5.9.2.1).  ``mant`` is the part whose digits decide zero.
_FORTRAN_I = re.compile(r"[+-]?(?P<mant>\d+)")
_FORTRAN_F = re.compile(r"[+-]?(?P<mant>\d+\.?\d*|\.\d+)(?:[EeDd][+-]?\d+|[+-]\d+)?")


def _require_absent(rec: _Record, a: int, b: int, field: str) -> None:
    """Refuse an ICONS field a neutron bank must leave absent, unless it is
    blank or zero (module docstring, ``ICONS``).

    Zero is decided on the mantissa's digits, never on ``float()``, which
    reads ``1.0E-999`` as 0.0.
    """
    raw = rec.cols(a, b)
    if not raw.strip():
        return
    integer = field == "IPOLA"
    m = (_FORTRAN_I if integer else _FORTRAN_F).fullmatch(raw.replace(" ", ""))
    if m is None:
        raise rec.fail(
            f"{field} in columns {a}-{b} is {raw.strip()!r}, which is not "
            f"{'an integer' if integer else 'a number'}; POLA, IPOLA and KRATIO "
            f"are absent for neutron data (GSAS Technical Manual p. 222), and "
            f"only a blank or zero field says so")
    if m["mant"].strip("0."):
        raise rec.fail(
            f"{field} in columns {a}-{b} is {raw.strip()!r}, which is not zero. "
            f"POLA, IPOLA and KRATIO are absent for neutron data (GSAS "
            f"Technical Manual p. 222), so an ICONS record carrying a non-zero "
            f"one is not the neutron time-of-flight record this reader was "
            f"told it is. A blank or zero field, which the record's FORTRAN "
            f"format reads identically, is accepted")


def _sequence(path: Path, bank: int, name: str, recs: dict[int, _Record],
              want: int) -> list[str]:
    """The raw E15 fields of records ``name1 … name<want>``, strictly in order."""
    tags = sorted(recs)
    if tags and tags != list(range(1, len(tags) + 1)):
        raise ValueError(
            f"{path}: bank {bank}'s {name} records are tagged {tags}; they must "
            f"be the consecutive run 1…{want} (GSAS Technical Manual p. 223), "
            f"and a gap would shift every later coefficient into the wrong slot")
    fields: list[str] = []
    for c in tags:
        fields.extend(recs[c].e15_block())
    if len(tags) != want:
        held = sum(1 for f in fields if f.strip())
        raise ValueError(
            f"{path}: bank {bank}'s {name} block holds {held} coefficients in "
            f"{len(tags)} records; the manual writes {want} records of four "
            f"(GSAS Technical Manual p. 223), and a short block is refused "
            f"rather than padded")
    return fields


def _e15_values(path: Path, bank: int, name: str, fields: list[str]) -> list[float]:
    out = []
    for k, f in enumerate(fields):
        s = f.strip()
        try:
            out.append(float(s.replace("D", "E")) if s else 0.0)
        except ValueError:
            raise ValueError(f"{path}: bank {bank}'s {name} slot {k + 1} is "
                             f"{s!r}, which is not a number") from None
    return out


def _spectrum(path: Path, bank: int, ityp_rec: _Record | None,
              icoff: dict[int, _Record], iecof: dict[int, _Record],
              dropped: list[str], fifth_pair: bool = False) -> IncidentSpectrum:
    if ityp_rec is None:
        if icoff:
            raise ValueError(f"{path}: bank {bank} has ICOFF records and no "
                             f"'I ITYP' record to say which function they are")
        return IncidentSpectrum()
    ityp_rec.check_columns(_ITYP_FIELDS)
    itype = ityp_rec.integer(13, 17, "ITYP")
    tmin = ityp_rec.number(18, 27, "TMIN")
    tmax = ityp_rec.number(28, 37, "TMAX")
    ityp_rec.integer(38, 47, "CHKSUM")       # read, carried nowhere, never checked
    dropped.append("CHKSUM")
    try:
        want = _coefficient_count(itype)
    except ValueError as exc:
        raise ValueError(f"{path}: bank {bank}: {exc}") from None
    lo = tmin * 1000.0 if tmin > 0.0 else None
    hi = tmax * 1000.0 if tmax > 0.0 else None
    if want == 0:
        if icoff:
            vals = _e15_values(path, bank, "ICOFF",
                               _sequence(path, bank, "ICOFF", icoff, 3))
            if any(v != 0.0 for v in vals):
                raise ValueError(f"{path}: bank {bank} declares ITYP 0 (no "
                                 f"incident spectrum) and carries non-zero "
                                 f"ICOFF coefficients")
        if lo is not None and hi is not None and not lo < hi:
            lo = hi = None
        return IncidentSpectrum(itype=0, tof_min_us=lo, tof_max_us=hi)
    vals = _e15_values(path, bank, "ICOFF", _sequence(path, bank, "ICOFF", icoff, 3))
    for k in range(want, 12):
        if vals[k] != 0.0:
            raise ValueError(
                f"{path}: bank {bank}: ITYP {itype} uses {want} coefficients and "
                f"slot P{k + 1} = {vals[k]!r} is non-zero; a number in a slot the "
                f"declared function does not read is refused")
    if itype in (1, 2) and not fifth_pair:
        # the documented layout stops at the fourth pair, and this reader is
        # the documented layout (module docstring)
        for k in (9, 10):
            if vals[k] != 0.0:
                raise ValueError(
                    f"{path}: bank {bank}: ITYP {itype}: P{k + 1} = {vals[k]!r} "
                    f"is non-zero. The GSAS Technical Manual (p. 128) states "
                    f"eleven coefficients and prints no exponent for the fifth "
                    f"pair (P10, P11), and this reader holds to the documented "
                    f"layout. A file carrying the pair is read by "
                    f"rietx.io.legacy.read_lansce_iparm")
    esds: list[float | None] = [None] * want
    if iecof:
        evals = _e15_values(path, bank, "IECOF",
                            _sequence(path, bank, "IECOF", iecof, 3))
        esds = evals[:want]
    coefficients = [Parameter(value=v, vary=False, stderr=e)
                    for v, e in zip(vals[:want], esds)]
    try:
        return IncidentSpectrum(itype=itype, coefficients=coefficients,
                                tof_min_us=lo, tof_max_us=hi)
    except ValidationError as exc:
        raise ValueError(f"{path}: bank {bank}: {exc}") from None


def _profile(path: Path, bank: int, headers: dict[int, _Record],
             conts: dict[int, dict[int, _Record]], diagnostics) -> ProfileTOF:
    if not headers:
        if conts:
            raise ValueError(f"{path}: bank {bank} has PRCF coefficient records "
                             f"and no PRCF header")
        _note(diagnostics, "warning", "GSAS_IPARM_PROFILE_DECLINED",
              f"Bank {bank} has no PRCF profile set, so the profile "
              f"coefficients are left at zero.",
              where=[f"bank {bank}"])
        return ProfileTOF()
    if 1 not in headers:
        raise ValueError(
            f"{path}: bank {bank}'s PRCF sets are numbered {sorted(headers)}; "
            f"the manual numbers them n = 1 … NTYP and makes set 1 the default "
            f"(GSAS Technical Manual p. 223), so without set 1 the file does not "
            f"say which function is in force")
    for n in sorted(conts):
        if n not in headers:
            raise ValueError(f"{path}: bank {bank} has PRCF{n} coefficient "
                             f"records and no PRCF{n} header")
    chosen: ProfileTOF | None = None
    for n in sorted(headers):
        rec = headers[n]
        rec.check_columns(_PRCF_FIELDS)
        ptyp = rec.integer(13, 17, "PTYP")
        ncof = rec.integer(18, 22, "NCOF")
        ctof = rec.number(23, 32, "CTOF")
        if ptyp not in PRCF_COEFFICIENT_NAMES and ptyp not in _PRCF_NOT_EVALUATED:
            raise rec.fail(f"PRCF set {n} declares profile function {ptyp}, which "
                           f"the GSAS Technical Manual does not define")
        if ptyp in PRCF_COEFFICIENT_NAMES:
            want = len(PRCF_COEFFICIENT_NAMES[ptyp])
            if ncof != want:
                raise rec.fail(
                    f"PRCF set {n} declares profile function {ptyp} with {ncof} "
                    f"coefficients; the manual documents {want} for function "
                    f"{ptyp}, and a block of another length is refused — never "
                    f"zero-padded or truncated — because the order of its "
                    f"slots would be a guess"
                    + (_LEGACY_POINTER if (ptyp, ncof) == (1, 8) else ""))
        if n != 1:
            _note(diagnostics, "info", "GSAS_IPARM_PROFILE_DECLINED",
                  f"Bank {bank}: PRCF set {n} (profile function {ptyp}) was "
                  f"not read, because set 1 is the default whatever its "
                  f"function (GSAS Technical Manual p. 223).",
                  where=[f"bank {bank}", f"PRCF{n}"])
            continue
        if ptyp in _PRCF_NOT_EVALUATED:
            raise rec.fail(
                f"the default PRCF set declares PTYP = {ptyp}, "
                f"{_PRCF_NOT_EVALUATED[ptyp]}, which this package does not "
                f"evaluate; refused rather than mapped onto the back-to-back "
                f"coefficients")
        fields = _sequence(path, bank, f"PRCF{n}", conts.get(n, {}),
                           1 + (ncof - 1) // 4)
        values = _e15_values(path, bank, f"PRCF{n}", fields)
        for k in range(ncof, len(values)):
            if values[k] != 0.0:
                raise rec.fail(f"PRCF set {n} declares {ncof} coefficients and "
                               f"slot {k + 1} beyond them holds {values[k]!r}")
        names = PRCF_COEFFICIENT_NAMES[ptyp]
        mapping = _PRCF_TO_PROFILE[ptyp]
        kwargs: dict[str, float] = {}
        for name, value in zip(names, values[:ncof]):
            if name in mapping:
                kwargs[mapping[name]] = value
            elif value != 0.0:
                raise rec.fail(
                    f"PRCF set {n}, profile function {ptyp}: {name} = {value!r} "
                    f"is non-zero. It is an anisotropic-broadening or peak-shift "
                    f"coefficient (GSAS Technical Manual p. 144, 148) that "
                    f"belongs with the microstructure machinery and has no slot "
                    f"on ProfileTOF; refused rather than dropped")
        for field in ("sig0", "sig1", "sig2"):
            if kwargs.get(field, 0.0) < 0.0:
                raise rec.fail(f"PRCF set {n}: {field} = {kwargs[field]!r} is a "
                               f"variance coefficient and is negative")
        try:
            chosen = ProfileTOF(**kwargs)
        except ValidationError as exc:
            raise rec.fail(str(exc)) from None
        _note(diagnostics, "info", "GSAS_IPARM_PROFILE_READ",
              f"Bank {bank}: PRCF set 1, profile function {ptyp} with {ncof} "
              f"coefficients, was read in the order the GSAS Technical Manual "
              f"lists them ({', '.join(names)}). That order is an assumption. "
              f"CTOF = {ctof!r} was read and not used.",
              where=[f"bank {bank}", "PRCF1"])
    assert chosen is not None
    return chosen


def read_gsas_tof_iparm(path: str | Path, *,
                        diagnostics: list[Diagnostic] | None = None
                        ) -> dict[int, Instrument]:
    """Read a GSAS-I TOF instrument-parameter file: ``{bank number: Instrument}``.

    Every bank the file declares comes back, keyed by the number its records
    carry — several banks are what a TOF instrument *is*, so none is picked.
    Records, columns and refusals are the module docstring's.  ``diagnostics``,
    when given, receives ``GSAS_IPARM_PROFILE_READ`` (the profile set read, the
    order assumption it rests on, CTOF), ``GSAS_IPARM_PROFILE_DECLINED`` (a set
    not read) and ``GSAS_IPARM_FIELD_DROPPED`` (records and fields with no slot
    in the schema); what is *returned* never depends on whether it was given.
    """
    path = Path(path)
    return _banks_from_records(path, _read_records(path), diagnostics)


def _banks_from_records(path: Path, records: list[tuple[str, str]],
                        diagnostics, *, fifth_pair: bool = False
                        ) -> dict[int, Instrument]:
    """:func:`read_gsas_tof_iparm` on records already split from ``path``.

    The one body of the strict reader, and the seam
    :mod:`rietx.io.legacy.lansce_iparm` hands a restated record list to, so
    a legacy layout is checked by exactly the columns and refusals a
    documented file is.  ``path`` is only ever quoted in messages.
    ``fifth_pair=True`` is that module's one switch into this body: it lets
    a non-zero ITYP 1/2 fifth ICOFF pair through to the model, which
    evaluates it; the strict reader never sets it.
    """
    nbank: int | None = None
    htype: str | None = None
    l1_m: float | None = None
    whole_dropped: list[str] = []
    banks: dict[int, dict] = {}

    for number, (key, payload) in enumerate(records, start=1):
        line = key + payload
        if not line.startswith("INS "):
            continue
        rec = _Record(path, number, line)
        bb = rec.cols(5, 6)
        name = rec.cols(7, 12)
        if not bb.strip():
            key = name.strip()
            if key == "BANK":
                rec.check_columns(_BANK_FIELDS)
                nbank = rec.integer(13, 17, "NBANK")
            elif key == "HTYPE":
                htype = rec.cols(15, 18).strip()
            elif key == "FPATH1":
                if l1_m is not None:
                    raise rec.fail("a second FPATH1 record; the primary flight "
                                   "path is one number for the whole file")
                l1_m = _primary_flight_path(rec)
            elif key not in whole_dropped:
                whole_dropped.append(key)
            continue
        if not bb.strip().isdigit():
            raise rec.fail(f"columns 5-6 hold {bb!r}, not a bank number")
        bank = banks.setdefault(int(bb), {
            "icons": None, "bnkpar": None, "ityp": None, "icoff": {},
            "iecof": {}, "prcf": {}, "prcf_c": {}, "dropped": [], "bad_key": None})
        if name == " ICONS":
            bank["icons"] = rec
        elif name == "BNKPAR":
            bank["bnkpar"] = rec
        elif name == "I ITYP":
            bank["ityp"] = rec
        elif name[:5] in ("ICOFF", "IECOF") and name[5].isdigit():
            bank["icoff" if name[:5] == "ICOFF" else "iecof"][int(name[5])] = rec
        elif name.startswith("PRCF"):
            n, c = name[4], name[5]
            if not n.isdigit() or n == "0":
                # refused when this bank is processed, so the file-level
                # refusals (HTYPE, NBANK) and earlier banks speak first
                bank["bad_key"] = bank["bad_key"] or rec.fail(
                    f"the PRCF set number in column 11 is {n!r}; the manual "
                    f"numbers the sets n = 1 … NTYP (GSAS Technical Manual "
                    f"p. 223), and a key spelled otherwise is not a documented "
                    f"record")
            elif c == " ":
                bank["prcf"][int(n)] = rec
            elif c.isdigit():
                bank["prcf_c"].setdefault(int(n), {})[int(c)] = rec
            else:
                bank["bad_key"] = bank["bad_key"] or rec.fail(
                    f"column 12 of a PRCF key is {c!r}; it is blank on a header "
                    f"and a digit on a coefficient record")
        else:
            key = name.strip()
            if key not in bank["dropped"]:
                bank["dropped"].append(key)

    if htype is None:
        raise ValueError(f"{path}: no 'INS   HTYPE ' record; the manual requires "
                         f"one (GSAS Technical Manual p. 221-222)")
    if not htype.startswith("PNT"):
        raise _htype_refusal(path, htype)
    if nbank is None:
        raise ValueError(f"{path}: no 'INS   BANK  ' record; the manual requires "
                         f"one (GSAS Technical Manual p. 221)")
    stray = sorted(b for b in banks if not 1 <= b <= nbank)
    if stray:
        raise ValueError(f"{path}: NBANK is {nbank} and records name bank(s) "
                         f"{stray}")

    out: dict[int, Instrument] = {}
    dropped_all: list[str] = list(whole_dropped)
    for b in range(1, nbank + 1):
        bank = banks.get(b)
        if bank is None or bank["icons"] is None:
            raise ValueError(f"{path}: NBANK is {nbank} and bank {b} has no "
                             f"ICONS record")
        icons = bank["icons"]
        icons.check_columns(_ICONS_FIELDS)
        difc = icons.number(13, 22, "DIFC")
        difa = icons.number(23, 32, "DIFA")
        zero = icons.number(33, 42, "ZERO")
        for a, b_, field in _ICONS_ABSENT:
            _require_absent(icons, a, b_, field)
        if bank["bnkpar"] is None:
            raise ValueError(f"{path}: bank {b} has no BNKPAR record, so its "
                             f"scattering angle is unknown — DIFC alone is one "
                             f"number from two and does not give the angle back")
        bnkpar = bank["bnkpar"]
        bnkpar.check_columns(_BNKPAR_FIELDS)
        dist = bnkpar.number(13, 22, "DIST")
        ttheta = bnkpar.number(23, 32, "TTHETA")
        dropped = list(bank["dropped"])
        spectrum = _spectrum(path, b, bank["ityp"], bank["icoff"], bank["iecof"],
                             dropped, fifth_pair)
        if bank["bad_key"] is not None:
            raise bank["bad_key"]
        profile = _profile(path, b, bank["prcf"], bank["prcf_c"], diagnostics)
        try:
            source = TOFSource(difc=difc, difa=difa, tzero=zero,
                               two_theta_bank_deg=ttheta, l1_m=l1_m,
                               l2_m=dist if dist > 0.0 else None,
                               profile_tof=profile, incident_spectrum=spectrum)
        except ValidationError as exc:
            raise ValueError(f"{path}: bank {b}: {exc}") from None
        out[b] = Instrument(source=source)
        for key in dropped:
            if key not in dropped_all:
                dropped_all.append(key)
    if dropped_all:
        _note(diagnostics, "info", "GSAS_IPARM_FIELD_DROPPED",
              f"{path.name}: {', '.join(dropped_all)} have no slot in the "
              f"schema and were not carried.", where=dropped_all)
    return out


def _primary_flight_path(rec: _Record) -> float:
    """``INS   FPATH1``: the primary flight path L₁ in metres, for every bank.

    **Not a record the manual lists** (GSAS Technical Manual p. 221-223), so
    there is no FORTRAN layout to read it at: the layout is the one observed,
    a single number after the key, and real files place it differently —
    NOMAD writes ``     19.50`` in columns 13-22, POWGEN ``     60.000000``
    across 13-26.  So it is read as one token, and anything else on the
    record is refused rather than guessed between.

    That it is L₁ is established by the files, not by its name alone: SNS
    NOMAD's own data file states "Primary flight path 19.5m" beside an
    ``.prm`` writing ``FPATH1 19.50``, and per bank a "Total flight path"
    equal to 19.5 m plus that bank's ``BNKPAR`` DIST (21.510 m against DIST
    2.010 on bank 1; five of six banks to the written digit, the sixth to
    0.02 m).  Metadata, as :attr:`TOFSource.l1_m` says: DIFC is the refined
    authority on the geometry.
    """
    payload = rec.cols(13, 80).split()
    if len(payload) != 1:
        raise rec.fail(
            f"columns 13-80 hold {rec.cols(13, 80).strip()!r}; FPATH1 is one "
            f"number, the primary flight path in metres")
    try:
        value = float(payload[0].replace("D", "E").replace("d", "e"))
    except ValueError:
        raise rec.fail(f"FPATH1 is {payload[0]!r}, which is not a number") from None
    if not value > 0.0:
        raise rec.fail(f"FPATH1 is {value!r}; a flight path in metres must be "
                       f"positive")
    return value


# ---------------------------------------------------------------------------
# GSAS-II
# ---------------------------------------------------------------------------
def _grammar_refusal(path: Path, lineno: int, line: str, why: str) -> ValueError:
    return ValueError(
        f"{path}: line {lineno} ({line.strip()!r}): {why}. The .instprm grammar "
        f"is not published; this reader accepts only blank lines, '#' comments "
        f"and one 'key:value' per line for a single bank")


def read_tof_instprm(path: str | Path, *,
                     diagnostics: list[Diagnostic] | None = None) -> Instrument:
    """Read a GSAS-II time-of-flight ``.instprm`` as one frozen ``Instrument``.

    Reached through :func:`rietx.read_gsas2_instprm`, which hands over the
    path of a file stating ``Type: PNT``; not a public name of its own.  Only
    the observed grammar and the keys the module docstring lists are read; any
    other key is refused with the key in the message, never read as zero.
    ``diagnostics``, when given, receives one ``GSAS2_INSTPRM_FIELD_DROPPED``
    naming the keys read and not carried.
    """
    path = Path(path)
    items: dict[str, tuple[int, str]] = {}
    for lineno, line in enumerate(_read_lines(path), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            raise _grammar_refusal(path, lineno, line, "no ':' separator")
        key, value = (part.strip() for part in s.split(":", 1))
        if not key:
            raise _grammar_refusal(path, lineno, line, "an empty key")
        if key in items:
            raise _grammar_refusal(
                path, lineno, line,
                f"{key!r} appears twice (first on line {items[key][0]}); how "
                f"several banks are delimited is not published")
        items[key] = (lineno, value)

    def number(key: str) -> float:
        lineno, value = items[key]
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"{path}: line {lineno}: {key} is {value!r}, which "
                             f"is not a number") from None

    known = (set(_INSTPRM_SOURCE) | set(_INSTPRM_PROFILE) | set(_INSTPRM_ZERO_ONLY)
             | set(_INSTPRM_METADATA) | {"Type", "2-theta"})
    for key, (lineno, _value) in items.items():
        if key not in known:
            raise ValueError(
                f"{path}: line {lineno}: key {key!r} is not one this reader can "
                f"name; an unrecognised .instprm key is refused rather than read "
                f"as zero, because a silent zero is a silently wrong profile")

    if "Type" not in items:
        raise ValueError(f"{path}: no 'Type' key, so the file does not say it "
                         f"is a time-of-flight bank")
    htype = items["Type"][1]
    if not htype.startswith("PNT"):
        data = {"PXC": "powder constant-wavelength x-ray",
                "PNC": "powder constant-wavelength neutron"}.get(htype[:3])
        what = f"Type {htype} is {data}" if data else f"Type {htype!r} is unrecognised"
        raise ValueError(f"{path}: {what}; this reader reads only a neutron "
                         f"time-of-flight bank (Type PNT)")
    for key in ("difC", "2-theta"):
        if key not in items:
            raise ValueError(f"{path}: no {key!r} key; a time-of-flight bank "
                             f"needs its DIFC and its scattering angle")

    dropped: list[str] = []
    for key in _INSTPRM_ZERO_ONLY:
        if key in items:
            value = number(key)
            if value != 0.0:
                raise ValueError(
                    f"{path}: {key} is {value!r}: its law is not published "
                    f"(the GSAS-II documentation names it and gives no "
                    f"d-dependence or unit for a TOF bank), so a non-zero value "
                    f"is refused rather than dropped")
            dropped.append(key)
    dropped.extend(k for k in _INSTPRM_METADATA if k in items)

    source_kw = {field: number(key) for key, field in _INSTPRM_SOURCE.items()
                 if key in items}
    profile_kw = {field: number(key) for key, field in _INSTPRM_PROFILE.items()
                  if key in items}
    for field in ("sig0", "sig1", "sig2"):
        if profile_kw.get(field, 0.0) < 0.0:
            raise ValueError(f"{path}: {field.replace('sig', 'sig-')} = "
                             f"{profile_kw[field]!r} is a variance coefficient "
                             f"and is negative")
    try:
        profile = ProfileTOF(**profile_kw)
        source = TOFSource(two_theta_bank_deg=number("2-theta"),
                           profile_tof=profile, **source_kw)
    except ValidationError as exc:
        raise ValueError(f"{path}: {exc}") from None
    if dropped:
        _note(diagnostics, "info", "GSAS2_INSTPRM_FIELD_DROPPED",
              f"{path.name}: {', '.join(dropped)} were read and not carried.",
              where=dropped)
    return Instrument(source=source)
