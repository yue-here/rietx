"""GSAS-I ``.EXP`` experiment files: someone else's converged refinement.

An ``.EXP`` is GSAS's whole experiment — the phases, the histograms, the
profile and background coefficients, and the refine flag on every one of them.
That last part is the reason this reader exists.  A CIF carries the converged
coordinates and a raw file carries the pattern, but neither says **which
parameters were free**, and that is the protocol: two refinements of one
specimen that free different sets are different experiments.  Before this
module the repo's own ``tests/test_acceptance_fap.py`` carried that protocol as
constants somebody read out of ``FAP.EXP`` by hand.

**The file is a card index, not a text file.**  Each record is exactly 80
characters, terminated by CR LF, and begins with a 12-character key by which
GSAS fetched it; the payload is read in fixed Fortran format from column 12.
Records are in alphabetical order by key because the key *is* the index.  Two
consequences this reader is built on:

* **Every field is read by column, never by splitting on whitespace.**  A
  fixed-format record whose optional numeric fields are blank collapses under
  ``str.split()`` into a shorter list whose entries then mean something else.
  ``ICONS`` is the record where that bites: its layout is
  ``LAM1 LAM2 ZERO [IREF] [IDAMP] POLA IPOLA KRATIO``, and a file that leaves
  ``IREF``/``IDAMP`` blank splits into six tokens that happen to line up, while
  one that writes ``IDAMP`` splits into seven that do not.  ``INST_XRY.PRM``
  and ``11bm_gsas.prm`` in ``tests/data`` are one of each.  **The record is
  GSAS's, not this file kind's**, so :func:`read_icons`,
  :func:`read_prcf_header` and :func:`split_records` are public and
  ``io/instrument_profile.py``'s ``.prm`` reader calls them: two readers
  parsing one record is how they come to disagree about it, which they did
  until WP-1118.
* **A record after the ``ZZZZZZZZZZZZ`` terminator is still a record.**  GSAS
  appends a history line past the end marker, so the terminator bounds nothing
  and is read as a record like any other.

**What "what the file stated" means here.**  Following ``TopasModel`` one
module over, :class:`GsasModel` is what the file says and not yet a
:class:`~rietx.schemas.Structure`: the caller decides which phase to take and
what to do with the histogram facts a ``Structure`` cannot hold.  A value the
file omits arrives as ``None`` rather than as a default, because a default
reads as an answer (WP-1076).

**Profile coefficients are named per function type, and the types disagree.**
CW function 2's fourth coefficient is ``LX`` and function 3's fourth is ``GP``,
so an index-to-name map that did not ask the type would mis-assign every width
in the file.  :data:`CW_PROFILE_COEFFICIENTS` is that map, and a type this
module cannot name is **refused by name** rather than read positionally — the
Bruker ``.raw`` v3 precedent in ``io/CLAUDE.md``, that an uncorroborated layout
is how a reader comes to return a plausible wrong model.

**Two places where the specification contradicts itself, settled by GSAS's own
output.**  Both are recorded here because the next reader of the manual will
meet them:

* The CW function 2 paragraph lists eighteen coefficients twice, once as
  physics symbols (``… Ts, As, P, Ss, Ye …``) and once as GSAS names
  (``… trns, asym, shft, GP, stec …``), and the two are **transposed at
  positions 8 and 9**: ``shft`` is the sample shift Ss and ``GP`` is the
  Gaussian Scherrer term P.  GSAS's own EXPEDT listing prints ``#8(shft)``
  and ``#9(GP)``, and ``FAP.EXP`` puts its converged 4.90166 at index 8 where
  the refinement's sample displacement belongs.  The name tuple is authoritative
  and the physics tuple is the typo.  Function 3's two tuples agree, which is
  what shows this to be a slip rather than a convention.
* The ``ATmmmB`` key template is printed one space short of twelve characters.
  Real files write the full twelve.  Keys are matched by their fixed fields
  here, not by the manual's template string.

**Units are centidegrees** for constant-wavelength data (the manual says so for
the pattern axis, and the sample-shift relation ``s = -πR·Ss/36000`` carries the
factor of 100 for the coefficients).  A term this module can name gets its value
in degrees beside the file's own number; one whose unit is compound — the
Stephens-like ``L11…L23``, which multiply ``d²`` — is carried in the file's
units alone with :attr:`GsasProfileTerm.degrees` ``None``.

Specification: Larson, A. C. & Von Dreele, R. B. (2004), *GSAS — General
Structure Analysis System*, Los Alamos National Laboratory Report LAUR 86-748,
§ "File Structures in GSAS" for the records and § "CW profile functions" for the
coefficient names.  Record keys, column offsets and coefficient names are
specification facts (``io/CLAUDE.md`` § Adding a format); no GSAS or GSAS-II
source was consulted.  See ``ATTRIBUTION.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...schemas.common import Diagnostic

#: One record: 80 characters, of which the first 12 are the fetch key.
RECORD_BYTES = 80
KEY_BYTES = 12

#: The record GSAS writes to mark the end of the index.  It bounds nothing —
#: a history line is appended after it — so this is recognised and then ignored.
TERMINATOR = "ZZZZZZZZZZZZ"

#: Which edition of the format this reader was written against.  Stated rather
#: than implied, so extending it to another is a declared piece of work.
SPEC = "Larson & Von Dreele (2004), GSAS, LAUR 86-748 (rev. 2004-09-26)"

#: The nine characteristic anodes ``IRAD`` selects among, in the manual's order.
#: ``0`` means "not one of these nine", which is a statement and not an absence.
IRAD_ANODES: tuple[str, ...] = ("Cr", "Fe", "Cu", "Mo", "Ag", "Ti", "Co", "Ta", "W")

#: Coefficient names per constant-wavelength profile function, from the
#: manual's own naming sentences.  **The order differs between types** — type 2
#: has ``LX`` fourth and type 3 has ``GP`` fourth — which is why this is keyed
#: by type and why a type absent from here is refused rather than read.
#:
#: Types 4 and upward are deliberately absent.  The manual describes type 4 as
#: "between 14 and 27 coefficients … ``S400``, etc.", which does not enumerate
#: a layout, and there is no file in this repo to corroborate one against.
CW_PROFILE_COEFFICIENTS: dict[int, tuple[str, ...]] = {
    1: ("U", "V", "W", "asym", "F1", "F2"),
    2: ("GU", "GV", "GW", "LX", "LY", "trns", "asym", "shft", "GP",
        "stec", "ptec", "sfec", "L11", "L22", "L33", "L12", "L13", "L23"),
    3: ("GU", "GV", "GW", "GP", "LX", "LY", "S/L", "H/L", "trns", "shft",
        "stec", "ptec", "sfec", "L11", "L22", "L33", "L12", "L13", "L23"),
}

#: Power of centidegrees each named coefficient carries, for the conversion to
#: degrees.  A variance term is 2, a width or a position shift is 1, a ratio is
#: 0.  A name absent from here has a compound unit this module does not convert
#: (``L11``…``L23`` multiply ``d²``), and its ``degrees`` is ``None`` — an
#: absent conversion rather than an identity one, which would read as an answer.
CW_CENTIDEG_POWER: dict[str, int] = {
    "U": 2, "V": 2, "W": 2, "F2": 2,
    "GU": 2, "GV": 2, "GW": 2, "GP": 2,
    "LX": 1, "LY": 1, "trns": 1, "shft": 1, "asym": 1, "F1": 1,
    "stec": 1, "ptec": 1, "sfec": 1,
    "S/L": 0, "H/L": 0, "eta": 0,
}


class GsasExpError(ValueError):
    """A ``.EXP`` this reader will not read, naming the file and the reason.

    A project reader refuses where a pattern reader would repair: its answer is
    a whole model, and a caller cannot see which part of it came from the file
    (``io/CLAUDE.md`` § Project readers).
    """


@dataclass(frozen=True)
class GsasProfileTerm:
    """One profile coefficient: what it is called, what it is, and its flag.

    ``value`` is the file's own number in the file's own units.  ``degrees`` is
    the same quantity in degrees where the unit is a plain power of
    centidegrees, and ``None`` where it is not — never a silent identity.
    """

    name: str
    value: float
    refined: bool
    #: index in the file's coefficient list, 1-based as GSAS numbers them
    index: int
    degrees: float | None = None


@dataclass(frozen=True)
class GsasProfile:
    """A ``PRCF`` block: the profile function, its coefficients and its flags."""

    function: int
    n_coefficients: int
    cutoff: float
    damping: int
    terms: tuple[GsasProfileTerm, ...]

    def by_name(self) -> dict[str, GsasProfileTerm]:
        """The terms keyed by GSAS's own name for them."""
        return {t.name: t for t in self.terms}

    @property
    def refined_names(self) -> tuple[str, ...]:
        """The coefficients this histogram/phase refined, in file order."""
        return tuple(t.name for t in self.terms if t.refined)


@dataclass(frozen=True)
class GsasBackground:
    """A ``BAKGD`` block: which of GSAS's background functions, and its terms.

    ``function`` is GSAS's own numbering, whose members are not all polynomials
    — 5 is a reciprocal-Q expansion for air scatter and 7 is linear
    interpolation — so it is carried as a number and named in
    :data:`BACKGROUND_FUNCTIONS` rather than mapped onto a rietx background,
    which would be inventing a correspondence.
    """

    function: int
    n_coefficients: int
    coefficients: tuple[float, ...]
    refined: bool
    damping: int


#: What each GSAS background function is, in this package's words.  Used to
#: name the function in a diagnostic; 3 and 9 are vacant in the manual.
BACKGROUND_FUNCTIONS: dict[int, str] = {
    1: "shifted Chebyshev polynomial of the first kind",
    2: "cosine Fourier series with a leading constant",
    4: "exponential expansion in Q², for thermal diffuse scattering",
    5: "reciprocal expansion in Q², for low-angle air scatter",
    6: "a mixture of functions 4 and 5",
    7: "linear interpolation between terms equally spaced in 2θ",
    8: "linear interpolation between terms equally spaced in 1/2θ",
}


@dataclass(frozen=True)
class GsasAtom:
    """One ``AT`` pair: the site, and which of its parameters were free.

    GSAS states the refine flags as **letters** on the second record — ``X``
    means the coordinates refined, ``U`` the displacement, ``F`` the occupancy
    — so a blank is the file saying "held" rather than the file saying nothing.
    """

    label: str
    species: str
    x: float
    y: float
    z: float
    occupancy: float
    multiplicity: int
    #: ``Uiso`` in Å², or ``None`` for an anisotropic site
    uiso: float | None
    #: ``U11 U22 U33 U12 U13 U23`` in Å², or ``None`` for an isotropic site
    uij: tuple[float, float, float, float, float, float] | None
    refine_occupancy: bool
    refine_xyz: bool
    refine_u: bool
    #: damping codes for occupancy, coordinates and displacement
    damping: tuple[int, int, int]

    @property
    def anisotropic(self) -> bool:
        return self.uij is not None


@dataclass(frozen=True)
class GsasCell:
    """The ``ABC``/``ANGLES`` pair, their esds, and the one refine flag.

    GSAS refines the cell as reciprocal metric tensor elements under a single
    flag, so there is one ``refined`` for the whole cell rather than six.
    """

    a: float
    b: float
    c: float
    alpha: float
    beta: float
    gamma: float
    refined: bool
    damping: int
    esd_a: float | None = None
    esd_b: float | None = None
    esd_c: float | None = None
    esd_alpha: float | None = None
    esd_beta: float | None = None
    esd_gamma: float | None = None
    volume: float | None = None
    volume_esd: float | None = None


@dataclass(frozen=True)
class GsasPhase:
    """One ``CRS`` block: a phase as the file states it."""

    number: int
    name: str
    space_group: str
    cell: GsasCell
    atoms: tuple[GsasAtom, ...]
    #: GSAS's phase type: 1 nuclear, 2 and 3 magnetic, 4 macromolecular.
    #: ``None`` where the file states no ``EXPR NPHAS`` record, which is the
    #: honest empty state rather than a default of 1 (WP-1076).  Defaulting to
    #: nuclear reads as an *answer* about a file that said nothing, and it is
    #: the one answer that silences the magnetic refusal — whose whole argument
    #: is that the nuclear half would look complete
    kind: int | None = None
    #: the ``CHMF`` unit-cell contents, per species
    formula: tuple[tuple[str, float], ...] = ()

    @property
    def magnetic(self) -> bool:
        return self.kind in (2, 3)


@dataclass(frozen=True)
class GsasIcons:
    """One ``ICONS`` record, read by column: the source and its constants.

    ``ICONS`` is not a ``.EXP`` record — it is a **GSAS** record, written the
    same way into an experiment file's ``HST`` block and into an
    instrument-parameter file's ``INS`` block, so both readers in this package
    get it from here rather than each parsing it (WP-1118).  The layout is
    ``3F10.0`` ``LAM1 LAM2 ZERO``, ``2X``, ``3A1`` refine flags, ``4X``,
    ``I1`` damping, ``F10.0`` ``POLA``, ``I5`` ``IPOLA``, ``F10.0`` ``KRATIO``.

    Reading it by column is the whole point.  A file that leaves ``IREF`` and
    ``IDAMP`` blank splits into six tokens that happen to land on the right
    meanings; one that writes ``IDAMP`` splits into seven that do not, and
    ``tests/data`` holds one of each (``11bm_gsas.prm`` and ``INST_XRY.PRM``).
    Polarization and a Kα2/Kα1 ratio are both conventionally 0.5 and sit two
    fields apart, so a reader that takes the wrong one agrees with the right
    one on some files and disagrees on others.

    Every field is ``None`` where the record leaves it blank, because a field
    GSAS did not write is not a field holding zero (WP-1076).
    """

    lam1: float | None
    lam2: float | None
    zero: float | None
    refine_zero: bool
    damping: int | None
    polarization: float | None
    polarization_type: int | None
    ka2_ratio: float | None

    @property
    def wavelengths(self) -> tuple[float, ...]:
        """The lines this record states, primary first, dropping blanks and zeros.

        ``LAM2 = 0`` *is* "no second line", which is why a zero drops out here
        rather than arriving as a wavelength of zero.
        """
        return tuple(w for w in (self.lam1, self.lam2) if w)


def read_icons(payload: str) -> GsasIcons:
    """Read one ``ICONS`` payload — the record past its 12-byte key."""
    return GsasIcons(
        lam1=_num(payload, 0, 10),
        lam2=_num(payload, 10, 10),
        zero=_num(payload, 20, 10),
        # the three refine flags sit at 32-35; the zero-point's is the third
        refine_zero=_flag(payload, 34),
        damping=_int(payload, 39, 1),
        polarization=_num(payload, 40, 10),
        polarization_type=_int(payload, 50, 5),
        ka2_ratio=_num(payload, 55, 10),
    )


@dataclass(frozen=True)
class GsasHistogram:
    """One ``HST`` block: the machine, the pattern it points at, and the fit.

    Wavelengths, polarization and the Kα2/Kα1 ratio come off ``ICONS`` by
    column, through :func:`read_icons`.  ``ka2_ratio`` is ``None`` where the
    field is blank, which is a file that states no ratio — not one that states
    zero, and not the 0.5 that sits one field earlier in ``FAP.EXP`` as the
    *polarization*.
    """

    number: int
    #: GSAS's four-character ``HTYP``, e.g. ``PXC`` for powder X-ray CW
    kind: str
    data_file: str | None
    instrument_file: str | None
    bank: int | None
    wavelengths: tuple[float, ...]
    zero: float
    refine_zero: bool
    polarization: float | None
    polarization_type: int | None
    ka2_ratio: float | None
    anode: str | None
    excluded_regions: tuple[tuple[float, float], ...]
    two_theta_range: tuple[float, float] | None
    n_channels_total: int | None
    n_channels_used: int | None
    scale: float | None
    refine_scale: bool
    background: GsasBackground | None
    #: the histogram's own default profile sets, from the instrument file
    default_profiles: tuple[GsasProfile, ...] = ()
    rwp: float | None = None
    rp: float | None = None

    @property
    def is_powder(self) -> bool:
        return self.kind[:1] == "P"

    @property
    def is_constant_wavelength(self) -> bool:
        return self.kind[2:3] == "C"


@dataclass(frozen=True)
class GsasHap:
    """One ``HAP`` block: what a phase did in one histogram.

    The profile coefficients that were actually refined live here rather than
    on the histogram, because GSAS refines them per phase-and-histogram pair.
    """

    phase: int
    histogram: int
    phase_fraction: float | None
    refine_phase_fraction: bool
    profile: GsasProfile | None
    #: March-Dollase rows: (coefficient, (h, k, l), refined, kind)
    preferred_orientation: tuple[tuple[float, tuple[float, float, float], bool, int], ...] = ()
    extinction: float | None = None
    refine_extinction: bool = False


@dataclass(frozen=True)
class GsasModel:
    """What a ``.EXP`` states.

    Deliberately not a :class:`~rietx.schemas.Structure` yet — the file states
    a whole experiment, and which phase and which histogram a caller wants is
    the caller's question.  Instrument facts (wavelengths, the profile
    coefficients and their flags, the excluded regions) are read off
    :attr:`histograms` and :attr:`hap`; a ``Structure`` cannot carry them, and
    inventing fields for them here would be the union-with-blanks that
    ``ProjectModel`` exists to avoid.
    """

    title: str = ""
    version: int | None = None
    phases: tuple[GsasPhase, ...] = ()
    histograms: tuple[GsasHistogram, ...] = ()
    #: keyed ``(phase number, histogram number)``
    hap: dict[tuple[int, int], GsasHap] = field(default_factory=dict)
    #: the run's own converged figures
    rwp: float | None = None
    rp: float | None = None
    #: GSAS's ``GDNFT`` figure, which is **reduced χ²** and not its root — the
    #: record states so in words.  GSAS-II is *not* the same convention, which
    #: this field claimed until WP-1118 measured it: its ``Rvals['GOF']`` is the
    #: **square root** of reduced χ²
    reduced_chi2: float | None = None
    n_variables: int | None = None
    n_observations: int | None = None
    path: str | None = None
    #: One line per thing the **read** could not carry across, in this
    #: package's words.  On the model rather than only on the ``diagnostics``
    #: channel for ``TopasModel.skipped_blocks``' reason: a fact about the
    #: answer should not depend on the caller having asked for messages.
    unsupported: tuple[str, ...] = ()

    def histogram(self, number: int | None = None) -> GsasHistogram:
        """The histogram numbered ``number``, or the only one there is.

        Raises rather than picking when a file carries several and the caller
        named none: which histogram's wavelength is "the" wavelength is not a
        question this reader may answer for someone (``io/CLAUDE.md``'s
        ``scan=`` rule, one registry over).
        """
        if number is not None:
            for h in self.histograms:
                if h.number == number:
                    return h
            have = ", ".join(str(h.number) for h in self.histograms) or "none"
            raise GsasExpError(
                f"{self.path or '<model>'}: no histogram {number} — this file "
                f"carries {have}")
        if len(self.histograms) == 1:
            return self.histograms[0]
        if not self.histograms:
            # "pass histogram=N" is no advice about a file that carries none,
            # and this is the shape a .EXP written before any data was loaded
            # really has
            raise GsasExpError(
                f"{self.path or '<model>'}: states no histograms at all — "
                f"there is no wavelength, no range and no profile to read.  "
                f"The phases are on `model.phases`")
        have = ", ".join(f"{h.number} ({h.kind})" for h in self.histograms)
        raise GsasExpError(
            f"{self.path or '<model>'}: {len(self.histograms)} histograms "
            f"({have}) and none named — pass histogram=N.  Which one's "
            f"wavelength is the experiment's is not a question this reader "
            f"can answer for you")

    def profile(self, *, phase: int | None = None,
                histogram: int | None = None) -> GsasProfile:
        """The refined profile for one phase-and-histogram pair.

        This is where the protocol lives: the coefficient values *and* which of
        them GSAS was free to move.
        """
        hist = self.histogram(histogram).number
        if phase is None:
            phases = [p for (p, h) in self.hap if h == hist]
            if len(phases) != 1:
                raise GsasExpError(
                    f"{self.path or '<model>'}: histogram {hist} has "
                    f"{len(phases)} phases and none named — pass phase=N")
            phase = phases[0]
        entry = self.hap.get((phase, hist))
        if entry is None or entry.profile is None:
            raise GsasExpError(
                f"{self.path or '<model>'}: no profile coefficients for phase "
                f"{phase} in histogram {hist}")
        return entry.profile


def _records(path: Path) -> list[tuple[str, str]]:
    """Every ``(key, payload)`` in the file, in file order.

    Decoding is ``latin-1`` because the payload is a byte field — a stray high
    byte in a title must not fail the read of a numeric record.  The splitting
    itself is :func:`split_records`, shared with the ``.prm`` reader.
    """
    raw = path.read_bytes()
    if not raw:
        raise GsasExpError(f"{path.name}: the file is empty")
    return split_records(raw.decode("latin-1"))


def split_records(text: str) -> list[tuple[str, str]]:
    """Split GSAS card-index text into ``(12-byte key, payload)`` pairs.

    The card index is the format, not the file kind: an experiment file and an
    instrument-parameter file are both a list of 80-column records, each a
    12-character key by which GSAS fetched it and a fixed-format payload from
    column 12.  Both readers in this package split here, so a payload offset
    means the same thing in either (WP-1118).

    Real files terminate their records with CR LF and some do not terminate
    them at all, so both are read: the text is split on line breaks where there
    are any, and sliced into 80-character cards where there are none.  Blank
    records are dropped; short ones are not padded, since :func:`_num` reads a
    missing field as the blank it is.

    **The split is on CR and LF by name**, not ``str.splitlines()``, which also
    breaks on ``\\x0b`` and on ``\\x85`` — a byte cp1252 spells ``…``.  One of
    those in a ``DESCR`` title splits that card in two, and the halves are then
    read as records with keys the file never wrote.  ``registry._matches_gsas_exp``
    measures the *bytes* for this reason (``bytes.splitlines`` breaks on CR and
    LF alone), so reading the text more loosely here would let the sniff accept
    a file this function then mis-splits.
    """
    if "\n" in text or "\r" in text:
        flat = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [ln for ln in flat.split("\n") if ln.strip()]
    else:
        lines = [text[i:i + RECORD_BYTES]
                 for i in range(0, len(text), RECORD_BYTES)]
        lines = [ln for ln in lines if ln.strip()]
    return [(ln[:KEY_BYTES], ln[KEY_BYTES:]) for ln in lines]


def _num(payload: str, start: int, width: int) -> float | None:
    """One fixed-width numeric field, or ``None`` when it is blank.

    Blank is the distinction this whole reader rests on: a field GSAS did not
    write is not a field holding zero.
    """
    chunk = payload[start:start + width].strip()
    if not chunk:
        return None
    try:
        return float(chunk)
    except ValueError:
        return None


def _int(payload: str, start: int, width: int) -> int | None:
    value = _num(payload, start, width)
    return None if value is None else int(value)


def _flag(payload: str, index: int) -> bool:
    """A single-character refine flag: ``Y`` refines, anything else holds."""
    return payload[index:index + 1].strip().upper() == "Y"


def _text(payload: str, start: int = 0, width: int | None = None) -> str:
    chunk = payload[start:] if width is None else payload[start:start + width]
    return chunk.strip()


@dataclass(frozen=True)
class GsasPrcfHeader:
    """A ``PRCF`` header record: which profile function, and how many terms.

    Format ``2I5, F10.5, 4X, I1, 20A1`` — the function type, how many
    coefficients follow on the continuation records, the peak cutoff, a damping
    code, then one ``Y``/``N`` per coefficient.  The flags are the protocol:
    they are what says which widths the refinement was free to move.  An
    instrument-parameter file writes the same header with nothing in the flag
    columns, because a calibration has refined nothing yet.

    The count is what a correct reader consumes, never the number of
    continuation records present: a file that skips a record must not silently
    shorten the list it produces.
    """

    function: int | None
    n_coefficients: int
    cutoff: float | None
    damping: int
    flags: str


def read_prcf_header(payload: str) -> GsasPrcfHeader:
    """Read one ``PRCF`` header payload — the record past its 12-byte key."""
    return GsasPrcfHeader(
        function=_int(payload, 0, 5),
        n_coefficients=_int(payload, 5, 5) or 0,
        cutoff=_num(payload, 10, 10),
        damping=_int(payload, 24, 1) or 0,
        flags=payload[25:],
    )


def _profile(payload: str, coefficients: list[float], *, path: str,
             where: str) -> GsasProfile:
    """Build a :class:`GsasProfile` from a ``PRCF`` header and its coefficients."""
    header = read_prcf_header(payload)
    function = header.function
    n_cof = header.n_coefficients
    cutoff = header.cutoff
    damping = header.damping
    flags = header.flags

    if function is None:
        raise GsasExpError(
            f"{path}: {where} states no profile function type — the "
            f"coefficients below it cannot be named without one")
    names = CW_PROFILE_COEFFICIENTS.get(function)
    if names is None:
        known = ", ".join(str(k) for k in sorted(CW_PROFILE_COEFFICIENTS))
        raise GsasExpError(
            f"{path}: {where} uses constant-wavelength profile function "
            f"{function}, whose coefficient order this build does not carry "
            f"(it names functions {known}).  The coefficients differ in order "
            f"between functions — type 2's fourth is LX and type 3's is GP — "
            f"so reading them positionally under another function's names "
            f"would mis-assign every width in the file.  The numbers are on "
            f"the record and readable; what is refused is naming them")

    if len(coefficients) < n_cof:
        raise GsasExpError(
            f"{path}: {where} declares {n_cof} profile coefficients and its "
            f"continuation records carry {len(coefficients)}.  Reading the "
            f"short list would hand back a profile whose `n_coefficients` and "
            f"`terms` disagree, so a lookup of a name the header promised "
            f"raises far from the file instead of here")

    terms = []
    for i in range(n_cof):
        name = names[i] if i < len(names) else f"#{i + 1}"
        power = CW_CENTIDEG_POWER.get(name)
        value = coefficients[i]
        degrees = None if power is None else value * (1e-2 ** power)
        terms.append(GsasProfileTerm(
            name=name, value=value, refined=flags[i:i + 1].strip().upper() == "Y",
            index=i + 1, degrees=degrees))
    return GsasProfile(function=function, n_coefficients=n_cof,
                       cutoff=0.0 if cutoff is None else cutoff,
                       damping=damping, terms=tuple(terms))


def _continuation(block: dict[str, str], stem: str, *, path: str = "<model>",
                  where: str = "") -> list[float]:
    """Every ``4E15.6`` value on the continuation records of ``stem``.

    GSAS splits a coefficient list four to a record and numbers the records
    from 1, so they are collected in key order rather than by counting: a file
    that skips a number must not silently shift the list it produces.

    The suffix must be **digits**, not merely different from the stem: the
    header record's own key differs from its stem only by padding, and
    admitting it prepends the header's own fields to the coefficient list —
    which is silent, because the result is the right length and the wrong
    values shifted by one.

    **Position is the name here**, so a field that cannot be read is refused
    rather than skipped.  Dropping one compacts the list, and every coefficient
    after it then answers to the name of the one before — the profile comes
    back the wrong length with plausible numbers under the wrong labels, which
    is the failure this module exists to prevent.  Two shapes are refused: a
    field that is not a number, and a value that follows a blank, since only
    the tail of the last record is legitimately blank.
    """
    values: list[float] = []
    blank_seen = False
    for suffix in sorted(k for k in block
                         if k.startswith(stem) and k != stem
                         and k[len(stem):].strip().isdigit()):
        payload = block[suffix]
        for i in range(0, 60, 15):
            chunk = payload[i:i + 15].strip()
            if not chunk:
                blank_seen = True
                continue
            if blank_seen:
                raise GsasExpError(
                    f"{path}: {where or stem} record {suffix!r} states a value "
                    f"at column {i + KEY_BYTES} after a blank field — GSAS "
                    f"writes these four to a record and leaves only the last "
                    f"record short, so the list cannot be laid out and every "
                    f"coefficient after the gap would take another's name")
            try:
                values.append(float(chunk))
            except ValueError:
                raise GsasExpError(
                    f"{path}: {where or stem} record {suffix!r} holds "
                    f"{chunk!r} at column {i + KEY_BYTES}, which is not a "
                    f"number.  Skipping it would shift every later coefficient "
                    f"onto the name of the one before it") from None
    return values


def _required(value: float | None, *, path: str, where: str,
              what: str) -> float:
    """``value``, or a refusal naming the record the blank field sits on.

    :func:`_num` answers ``None`` for a field that is blank or unreadable, and
    that is right for an optional one — an absent ``KRATIO`` is a file stating
    no ratio.  A cell edge or a coordinate is not optional: it is declared
    ``float`` on the model, and letting the ``None`` through means the failure
    surfaces two modules away as a schema error naming neither the file nor the
    field (``io/CLAUDE.md``: a reader raises naming the file, never its
    parser's exception).
    """
    if value is None:
        raise GsasExpError(
            f"{path}: {where} states no {what} — the field is blank or is not "
            f"a number, and this one is not optional")
    return value


def _read_phase(number: int, block: dict[str, str], path: str,
                kind: int | None) -> GsasPhase:
    """One ``CRS`` block: cell, symmetry and sites, with their refine flags."""
    abc = block.get("ABC")
    angles = block.get("ANGLES")
    if abc is None or angles is None:
        raise GsasExpError(
            f"{path}: phase {number} states no "
            f"{'ABC' if abc is None else 'ANGLES'} record, so it has no cell")
    sig_abc = block.get("ABCSIG", "")
    sig_ang = block.get("ANGSIG", "")
    volume = block.get("CELVOL", "")
    where = f"phase {number}'s cell"
    cell = GsasCell(
        a=_required(_num(abc, 0, 10), path=path, where=where, what="a"),
        b=_required(_num(abc, 10, 10), path=path, where=where, what="b"),
        c=_required(_num(abc, 20, 10), path=path, where=where, what="c"),
        alpha=_required(_num(angles, 0, 10), path=path, where=where,
                        what="alpha"),
        beta=_required(_num(angles, 10, 10), path=path, where=where,
                       what="beta"),
        gamma=_required(_num(angles, 20, 10), path=path, where=where,
                        what="gamma"),
        refined=_flag(abc, 34), damping=_int(abc, 39, 1) or 0,
        esd_a=_num(sig_abc, 0, 10), esd_b=_num(sig_abc, 10, 10),
        esd_c=_num(sig_abc, 20, 10),
        esd_alpha=_num(sig_ang, 0, 10), esd_beta=_num(sig_ang, 10, 10),
        esd_gamma=_num(sig_ang, 20, 10),
        # CELVOL is 2F15.3 in every file here, against the manual's printed
        # 2F10.3.  Reading it at the printed width truncates 523.755 to 52.0,
        # which is a plausible number and so would not have shown up as an
        # error -- the file is the authority where the two disagree.
        volume=_num(volume, 0, 15), volume_esd=_num(volume, 15, 15))

    atoms = []
    for key in sorted(k for k in block if k.startswith("AT") and k.endswith("A")):
        head = block[key]
        tail = block.get(key[:-1] + "B")
        if tail is None:
            raise GsasExpError(
                f"{path}: phase {number} atom record {key!r} has no matching "
                f"'B' record, so the file states no displacement parameter "
                f"for it")
        # 'A': 2X, A8 type, 4F10.6 x/y/z/frac, A8 name, I4 mult, 1X, 3A1 damping
        species = _text(head, 2, 8)
        # 'B': 6F10.6 Uij, 2X, 4A1 codes -- CODE(1) I/A, then F, X, U flags
        codes = tail[62:66]
        isotropic = codes[0:1].strip().upper() != "A"
        uij = tuple(_num(tail, 10 * i, 10) or 0.0 for i in range(6))
        site = f"phase {number} atom record {key!r}"
        atoms.append(GsasAtom(
            label=_text(head, 50, 8) or species,
            species=species,
            x=_required(_num(head, 10, 10), path=path, where=site, what="x"),
            y=_required(_num(head, 20, 10), path=path, where=site, what="y"),
            z=_required(_num(head, 30, 10), path=path, where=site, what="z"),
            occupancy=_required(_num(head, 40, 10), path=path, where=site,
                                what="occupancy"),
            multiplicity=_int(head, 58, 4) or 0,
            uiso=uij[0] if isotropic else None,
            uij=None if isotropic else uij,
            refine_occupancy="F" in codes.upper(),
            refine_xyz="X" in codes.upper(),
            refine_u="U" in codes.upper(),
            damping=tuple(int(c) if c.isdigit() else 0 for c in head[63:66])))

    formula = tuple(
        (_text(block[k], 0, 8), _num(block[k], 8, 10) or 0.0)
        for k in sorted(k for k in block if k.startswith("CHMF")))

    return GsasPhase(
        number=number, name=_text(block.get("PNAM", "")),
        space_group=_text(block.get("SG SYM", "")),
        cell=cell, atoms=tuple(atoms), kind=kind, formula=formula)


def _names_profile(kind: str) -> bool:
    """Whether this build may name a histogram's profile coefficients.

    One predicate, read by the histogram loop and by the HAP loop, because a
    ``HAP`` block holds the coefficients that were *refined* and the histogram
    block only the instrument file's defaults — so a gate that differed between
    them would decline the defaults and name the refined set anyway.  ``"SXC"``
    is the case: single-crystal data, whose third letter is the ``C`` a
    constant-wavelength test looks for.
    """
    return bool(kind) and kind[:1] != "S" and kind[2:3] == "C"


def _read_histogram(number: int, block: dict[str, str], kind: str,
                    path: str) -> GsasHistogram:
    """One ``HST`` block: the machine, the pattern and the fit's own numbers."""
    icons = read_icons(block.get("ICONS", ""))

    excluded = []
    for key in sorted(k for k in block if k.startswith("EXC")):
        lo, hi = _num(block[key], 0, 10), _num(block[key], 10, 10)
        if lo is None or hi is None or lo == hi:
            continue          # GSAS writes a degenerate 0-0 pair as a spacer
        excluded.append((lo, hi))

    chans = block.get("CHANS", "")
    # Both halves or neither: the field is declared ``tuple[float, float] |
    # None``, and a ``TRNGE`` with one blank field handed back
    # ``(None, 129.98)`` under that annotation — a caller unpacking it into two
    # floats gets a ``None`` far from the record it came off (WP-1076).
    trnge = block.get("TRNGE", "")
    span = (_num(trnge, 0, 10), _num(trnge, 10, 10))
    two_theta_range = None if None in span else span
    rpowd = block.get("RPOWD", "")
    scale = block.get("HSCALE", "")

    background = None
    if (head := block.get("BAKGD")) is not None:
        coefficients = _continuation(
            block, "BAKGD", path=path,
            where=f"histogram {number} background")
        background = GsasBackground(
            function=_int(head, 0, 5) or 0,
            n_coefficients=_int(head, 5, 5) or 0,
            coefficients=tuple(coefficients),
            refined=_flag(head, 14), damping=_int(head, 15, 5) or 0)

    profiles = []
    for key in sorted(k for k in block
                      if k.startswith("PRCF") and len(k.rstrip()) == 5):
        setno = key.rstrip()[-1]
        values = _continuation(
            block, f"PRCF{setno}", path=path,
            where=f"histogram {number} profile set {setno}")
        profiles.append(_profile(block[key], values, path=path,
                                 where=f"histogram {number} profile set {setno}"))

    anode = None
    if (irad := _int(block.get("IRAD", ""), 0, 5)):
        if 1 <= irad <= len(IRAD_ANODES):
            anode = IRAD_ANODES[irad - 1]

    return GsasHistogram(
        number=number, kind=kind,
        data_file=_text(block.get("HFIL", "")) or None,
        instrument_file=_text(block.get("IFIL", "")) or None,
        bank=_int(block.get("BANK", ""), 0, 5),
        wavelengths=icons.wavelengths,
        zero=icons.zero or 0.0,
        refine_zero=icons.refine_zero,
        polarization=icons.polarization,
        polarization_type=icons.polarization_type,
        ka2_ratio=icons.ka2_ratio,
        anode=anode,
        excluded_regions=tuple(excluded),
        two_theta_range=two_theta_range,
        n_channels_total=_int(chans, 40, 10),
        n_channels_used=_int(chans, 20, 10),
        scale=_num(scale, 0, 15),
        refine_scale=_flag(scale, 19),
        background=background,
        default_profiles=tuple(profiles),
        rwp=_num(rpowd, 0, 10), rp=_num(rpowd, 10, 10))


def read_gsas_exp(path: str | Path, *,
                  diagnostics: list[Diagnostic] | None = None) -> GsasModel:
    """Read a GSAS-I ``.EXP`` experiment file.

    Returns what the file states — phases with their refine flags, histograms
    with their wavelengths and excluded regions, and the profile coefficients
    each phase refined in each histogram.  Call :func:`to_structure` for a
    :class:`~rietx.schemas.Structure`; the instrument facts stay on the model,
    because a ``Structure`` cannot hold them and inventing fields for them
    would be the union-with-blanks that ``ProjectModel`` exists to avoid.

    ``diagnostics`` collects what the reader **could not carry across**, by
    name: a background function with no rietx counterpart, a histogram whose
    radiation type this build does not read.  Nothing is dropped in silence.

    Raises :class:`GsasExpError` naming the file and the reason, never a bare
    parser exception.
    """
    p = Path(path)
    try:
        records = _records(p)
    except OSError as exc:
        raise GsasExpError(f"{p.name}: cannot be read ({exc})") from exc

    if not any(key.startswith(("CRS", "HST")) or key.strip() in ("VERSION",)
               or key.strip().startswith("EXPR")
               for key, _ in records):
        raise GsasExpError(
            f"{p.name}: holds no GSAS experiment records — a .EXP is an "
            f"80-character card index whose keys include VERSION, EXPR, CRS "
            f"(phases) and HST (histograms), and none of those is present")

    overall: dict[str, str] = {}
    phase_blocks: dict[int, dict[str, str]] = {}
    hist_blocks: dict[int, dict[str, str]] = {}
    hap_blocks: dict[tuple[int, int], dict[str, str]] = {}

    for key, payload in records:
        if key == TERMINATOR:
            continue
        head, rest = key[:3], key[3:]
        if head == "CRS" and rest[:1].isdigit():
            phase_blocks.setdefault(int(rest[0]), {})[key[4:].strip()] = payload
        elif head == "HST" and key[3:6].strip().isdigit():
            hist_blocks.setdefault(int(key[3:6]), {})[key[6:].strip()] = payload
        elif head == "HAP" and rest[:1].isdigit() and key[4:6].strip().isdigit():
            hap_blocks.setdefault(
                (int(rest[0]), int(key[4:6])), {})[key[6:].strip()] = payload
        else:
            overall[key.strip()] = payload

    # ``EXPR NPHAS`` states a type per phase: 1 nuclear, 2 and 3 magnetic,
    # 4 macromolecular.  Read rather than inferred from the records present,
    # because a magnetic phase's nuclear half parses perfectly.
    kinds: dict[int, int] = {}
    if (nphas := overall.get("EXPR NPHAS")) is not None:
        for i in range(9):
            if (k := _int(nphas, 5 * i, 5)):
                kinds[i + 1] = k

    # ``EXPR  HTYPn`` carries twelve histogram types a record, and **n is which
    # twelve**: record 2 states histograms 13-24.  Reading the record number is
    # what keeps a file with more than twelve histograms honest — mapping every
    # record onto 1-12 gives histogram 13 no type at all while overwriting
    # histogram 1's with it, and a type is what decides whether the profile
    # coefficients are named at all.
    htypes: dict[int, str] = {}
    for key, payload in overall.items():
        if key.startswith("EXPR  HTYP"):
            group = key[len("EXPR  HTYP"):].strip()
            base = (int(group) - 1) * 12 if group.isdigit() else 0
            for i in range(12):
                token = payload[2 + 5 * i:2 + 5 * i + 4].strip()
                if token:
                    htypes[base + i + 1] = token

    phases = tuple(
        _read_phase(n, phase_blocks[n], p.name, kinds.get(n))
        for n in sorted(phase_blocks))

    reported: list[str] = []
    histograms = []
    for n in sorted(hist_blocks):
        kind = htypes.get(n, "")
        block = hist_blocks[n]
        if not _names_profile(kind):
            if not kind:
                # The same rule as the phase type above: an absent HTYP is the
                # file saying nothing, and reading the coefficients under a
                # constant-wavelength function's names would be assuming the
                # one answer that makes them look right.  The numbers stay
                # readable on the record; what is declined is naming them.
                reported.append(
                    f"histogram {n} states no HTYP record, so its radiation "
                    f"type and whether it is constant-wavelength are unknown; "
                    f"its profile coefficients are left unnamed rather than "
                    f"read under a function order nothing establishes")
            elif kind[:1] == "S":
                reported.append(
                    f"histogram {n} is single-crystal data ({kind!r}), which "
                    f"this reader does not carry")
            else:
                reported.append(
                    f"histogram {n} is {kind!r} rather than "
                    f"constant-wavelength, and the time-of-flight profile "
                    f"functions have a different coefficient order from the "
                    f"CW ones this build names, so its profile coefficients "
                    f"are left unnamed")
            block = {k: v for k, v in block.items() if not k.startswith("PRCF")}
        histograms.append(_read_histogram(n, block, kind, p.name))

    hap: dict[tuple[int, int], GsasHap] = {}
    for (ph, hs), block in sorted(hap_blocks.items()):
        profile = None
        head = block.get("PRCF")
        if head is not None and _names_profile(htypes.get(hs, "")):
            where = f"phase {ph} in histogram {hs}"
            profile = _profile(
                head, _continuation(block, "PRCF", path=p.name, where=where),
                path=p.name, where=where)
        prefo = []
        for key in sorted(k for k in block if k.startswith("PREFO")):
            row = block[key]
            prefo.append((
                _num(row, 0, 10) or 1.0,
                (_num(row, 10, 10) or 0.0, _num(row, 20, 10) or 0.0,
                 _num(row, 30, 10) or 0.0),
                _flag(row, 44), _int(row, 50, 5) or 0))
        phsfr = block.get("PHSFR", "")
        extpow = block.get("EXTPOW", "")
        hap[(ph, hs)] = GsasHap(
            phase=ph, histogram=hs,
            phase_fraction=_num(phsfr, 0, 15),
            refine_phase_fraction=_flag(phsfr, 19),
            profile=profile,
            preferred_orientation=tuple(prefo),
            extinction=_num(extpow, 0, 15),
            refine_extinction=_flag(extpow, 19))

    rpowd = overall.get("REFN RPOWD", "")
    gdnft = overall.get("REFN GDNFT", "")
    model = GsasModel(
        title=_text(overall.get("DESCR", "")),
        version=_int(overall.get("VERSION", ""), 0, 5),
        phases=phases, histograms=tuple(histograms), hap=hap,
        rwp=_num(rpowd, 0, 10), rp=_num(rpowd, 10, 10),
        reduced_chi2=_reduced_chi2(gdnft),
        n_variables=_n_variables(gdnft),
        # From ``REFN STATS``' own words rather than from the fields ``RPOWD``
        # carries past its declared ``2F10.4``: those extras are real but
        # undocumented, and reading an undocumented field positionally is how
        # a reader returns a plausible wrong number (``io/CLAUDE.md``).
        n_observations=_n_observations(overall.get("REFN STATS", "")),
        path=str(p),
        unsupported=tuple(reported))

    if diagnostics is not None:
        _report(model, diagnostics)
    return model


def _reduced_chi2(record: str) -> float | None:
    """GSAS's ``GDNFT`` figure, which the record itself calls reduced χ².

    The record is free text ("Reduced CHI**2 =  3.224     for   28 variables")
    rather than a fixed-format numeric, so it is read by its own words.  Worth
    stating plainly because the quantity is **reduced χ² and not its root**, so
    reading it as a goodness-of-fit reports the square of the number meant
    (issue #103).

    **The two GSAS generations disagree here**, which this docstring got wrong
    until WP-1118 measured it while writing the ``.gpx`` reader: GSAS-II's
    ``Rvals['GOF']`` is ``sqrt(chisq / (Nobs - Nvars))`` — its own documentation
    says the root, and it matches to six figures on all six tutorial projects
    stating the four numbers.  So a caller moving between the two formats
    converts rather than copies, and `Gsas2Model.gof` is named for what it is.
    """
    if "=" not in record:
        return None
    try:
        return float(record.split("=", 1)[1].split()[0])
    except (IndexError, ValueError):
        return None


def _n_variables(record: str) -> int | None:
    parts = record.split()
    if "for" in parts:
        try:
            return int(parts[parts.index("for") + 1])
        except (IndexError, ValueError):
            return None
    return None


def _n_observations(record: str) -> int | None:
    """The count out of ``REFN STATS``' sentence, "There were 5750 observations".

    Free text, like ``GDNFT`` above, and read by its words for the same reason:
    the manual declares the record as a sentence rather than as fields.
    """
    parts = record.split()
    if "were" in parts:
        try:
            return int(parts[parts.index("were") + 1])
        except (IndexError, ValueError):
            return None
    return None


def _report(model: GsasModel, diagnostics: list[Diagnostic]) -> None:
    """Append one diagnostic per thing the read could not carry across.

    Every message names the construct rather than describing it generally, so
    a caller learns *what* is missing from their model and not merely that
    something is.
    """
    named = model.path or "<model>"
    for text in model.unsupported:
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS_EXP_HISTOGRAM_NOT_READ",
            message=f"{named}: {text}"))
    for hist in model.histograms:
        bkg = hist.background
        if bkg is None:
            continue
        what = BACKGROUND_FUNCTIONS.get(bkg.function)
        diagnostics.append(Diagnostic(
            level="info", code="GSAS_EXP_BACKGROUND_NOT_CARRIED",
            message=(
                f"{named}: histogram {hist.number} fitted GSAS background "
                f"function {bkg.function}"
                + (f" ({what})" if what else "")
                + f" with {bkg.n_coefficients} terms, which has no rietx "
                f"counterpart — the coefficients are on "
                f"`model.histograms[…].background` and the background to fit "
                f"with is yours to choose"),
            where=[f"histograms.{hist.number}.background"],
            value=float(bkg.function)))
    for phase in model.phases:
        if phase.magnetic:
            diagnostics.append(Diagnostic(
                level="warning", code="GSAS_EXP_PHASE_MAGNETIC",
                message=(
                    f"{named}: phase {phase.number} ({phase.name!r}) is a "
                    f"magnetic phase (GSAS phase type {phase.kind}) and rietx "
                    f"has no magnetic scattering model"),
                where=[f"phases.{phase.number}"]))


#: Uiso (Å²) → Biso (Å²).  GSAS stores U on the ``ATmmmB`` record and rietx's
#: ``Atom.biso`` is B, so this factor is the whole conversion.
EIGHT_PI_SQUARED = 8.0 * 3.141592653589793 ** 2


def to_structure(model: GsasModel, *, phase: int | None = None,
                 diagnostics: list[Diagnostic] | None = None):
    """Build a :class:`~rietx.schemas.Structure` from a parsed ``.EXP``.

    **The refine flags come across**, which is the point: the cell carries
    GSAS's single ``ABC`` flag, and each site's coordinates and displacement
    carry the ``X`` and ``U`` letters from its own ``ATmmmB`` record.  A blank
    letter is the file saying *held*, not the file saying nothing, so it maps
    onto ``vary=False`` rather than onto a schema default.

    ``Uiso`` becomes ``Biso`` through :data:`EIGHT_PI_SQUARED`.  Species are
    title-cased to IUCr spelling (``CA`` → ``Ca``), reported as
    ``GSAS_EXP_SPECIES_NORMALISED`` where ``diagnostics=`` is passed — the channel
    and code shape ``structure_from_cif`` uses.

    ``phase`` picks one of a multi-phase file; with several phases and none
    named this raises rather than taking the first, following ``read_pattern``'s
    ``scan=`` rule that a selection is the caller's.

    Three refusals, each naming what it would otherwise have dropped:

    * **A magnetic phase** (GSAS phase type 2 or 3).  rietx has no magnetic
      scattering model, so the nuclear half is all that could be imported and
      it would look complete — the stance
      :mod:`~rietx.io.projects.coverage` already declares for the sibling
      readers, reached here through the same sentence.
    * **A macromolecular phase** (type 4).  Its sites are on ``ATmmmm`` records
      with a different layout, which this reader does not read at all, so the
      phase would arrive with no atoms rather than with wrong ones.
    * **An anisotropic site.**  The six ``UIJ`` numbers are on the model, but
      which off-diagonal convention they follow is not settled by any file in
      this repo, and a wrong factor of two is a silently wrong Debye-Waller
      factor at high Q.  This is the refusal ``fullprof.to_structure`` makes
      about a ``β`` block, for the same reason and with the same remedy: a
      corroborating file.

    And one the corpus taught rather than the specification: a **negative
    Uiso**, which a real refinement reaches and which no structure can hold.
    It names the phase; a schema refusal that got past it would name a
    ``Parameter`` and never the file, so the final build converts one.
    """
    import gemmi
    import numpy as np

    import rietx as rx

    from ...crystallography.wyckoff import coordinate_basis, stabilizer_rotations
    from .fullprof import normalize_species

    if not model.phases:
        raise GsasExpError(
            f"{model.path or '<model>'}: states no phases — a .EXP written "
            f"before any phase was entered carries histograms alone")

    if phase is None:
        if len(model.phases) != 1:
            named = ", ".join(f"{p.number}:{p.name!r}" for p in model.phases)
            raise GsasExpError(
                f"{model.path or '<model>'}: {len(model.phases)} phases "
                f"({named}) and none named — pass phase=N.  Which of them the "
                f"structure is is the caller's choice, not this reader's")
        chosen = model.phases[0]
    else:
        matches = [p for p in model.phases if p.number == phase]
        if not matches:
            have = ", ".join(str(p.number) for p in model.phases)
            raise GsasExpError(
                f"{model.path or '<model>'}: no phase {phase} — this file "
                f"carries {have}")
        chosen = matches[0]

    if chosen.kind is None:
        raise GsasExpError(
            f"{model.path or '<model>'}: phase {chosen.number} "
            f"({chosen.name!r}) has no phase type — the file states no "
            f"'EXPR NPHAS' record, so nothing says whether it is nuclear, "
            f"magnetic or macromolecular.  Reading it as nuclear is the one "
            f"assumption that would silence the magnetic refusal below, so it "
            f"is refused instead.  The cell and sites are on `model.phases`")
    if chosen.magnetic:
        raise GsasExpError(
            f"{model.path or '<model>'}: phase {chosen.number} "
            f"({chosen.name!r}) is magnetic (GSAS phase type {chosen.kind}) "
            f"and rietx has no magnetic scattering model.  Importing its "
            f"nuclear half would hand back a structure that looks complete "
            f"while the magnetic contribution went unmentioned.  The numbers "
            f"are on `model.phases`")
    if chosen.kind == 4:
        raise GsasExpError(
            f"{model.path or '<model>'}: phase {chosen.number} "
            f"({chosen.name!r}) is macromolecular (GSAS phase type 4), whose "
            f"sites are written on ATmmmm records this reader does not read — "
            f"so the phase would arrive with no atoms rather than with wrong "
            f"ones")
    aniso = [a.label for a in chosen.atoms if a.anisotropic]
    if aniso:
        raise GsasExpError(
            f"{model.path or '<model>'}: phase {chosen.number} has "
            f"{len(aniso)} anisotropic site(s) ({', '.join(aniso)}).  The six "
            f"UIJ values are on `model.phases[…].atoms[…].uij`, but which "
            f"off-diagonal convention GSAS wrote them in is not settled by any "
            f"file in this repo, and a wrong factor of two is a silently wrong "
            f"Debye-Waller factor at high Q")
    negative = [(a.label, a.uiso) for a in chosen.atoms
                if a.uiso is not None and a.uiso < 0.0]
    if negative:
        worst = min(negative, key=lambda row: row[1])
        raise GsasExpError(
            f"{model.path or '<model>'}: phase {chosen.number} states a "
            f"negative Uiso on {len(negative)} site(s), the largest on "
            f"{worst[0]!r} at {worst[1]:.5g} Å².  A refinement really can end "
            f"there and GSAS really does store it, but exp(-B·s²) with B < 0 "
            f"grows without bound at high Q, so the value is carried on "
            f"`model.phases[…].atoms[…].uiso` and not built into a structure.  "
            f"Deciding what it should have been is yours")

    cell = chosen.cell

    # GSAS's own words for the X flag are "XYZ's are to be refined **as
    # permitted by symmetry**", and rietx models exactly that: coordinates
    # enter θ as site-symmetry DOFs, and a site with none of them refuses a
    # vary request outright.  So the flag is carried through the same basis
    # GSAS was speaking about rather than onto x/y/z directly — otherwise
    # fluorapatite's F4, on a zero-freedom special position with its X flag
    # set, makes the whole import raise on a file GSAS refined happily.
    # gemmi's own refusal names neither the file nor the phase, and a partially
    # entered experiment carries no `SG SYM` record at all, so the symbol is
    # crossed here rather than left to raise from two modules away.
    try:
        sg = gemmi.SpaceGroup(chosen.space_group)
    except (ValueError, RuntimeError) as exc:
        raise GsasExpError(
            f"{model.path or '<model>'}: phase {chosen.number} "
            f"({chosen.name!r}) states the space-group symbol "
            f"{chosen.space_group!r}, which is not one this build resolves "
            f"({exc}).  The cell and sites are on `model.phases`") from exc
    frozen: list[str] = []

    rewrites: dict[str, tuple[str, list[str]]] = {}
    sites: list[dict] = []
    for i, atom in enumerate(chosen.atoms):
        species = normalize_species(atom.species)
        if species != atom.species:
            rewrites.setdefault(atom.species, (species, []))[1].append(
                f"phases.0.atoms.{i}.species")
        xyz = np.array([atom.x, atom.y, atom.z])
        movable = len(coordinate_basis(stabilizer_rotations(sg, xyz))) > 0
        if atom.refine_xyz and not movable:
            frozen.append(atom.label)
        sites.append(dict(
            label=atom.label, species=species, xyz=(atom.x, atom.y, atom.z),
            vary_xyz=atom.refine_xyz and movable,
            occupancy=atom.occupancy, vary_occupancy=atom.refine_occupancy,
            biso=(atom.uiso or 0.0) * EIGHT_PI_SQUARED, vary_biso=atom.refine_u))

    # Every schema object the conversion builds is built **here**, inside one
    # try, rather than as it goes — the shape ``gsas2.to_structure`` uses and
    # for the same reason: a schema refusal that reached a caller would name a
    # ``Parameter`` and never the file, which is the one thing
    # ``io/CLAUDE.md`` forbids a reader.  The two shapes the corpus contains
    # (a negative Uiso, an anisotropic site) are refused by name above; this
    # is the class rather than a third instance.
    varies = cell.refined
    try:
        structure = rx.Structure(phases=[rx.Phase(
            name=chosen.name or f"phase {chosen.number}",
            space_group=chosen.space_group,
            cell=rx.Cell(
                a=rx.Parameter(value=cell.a, min=1.0, vary=varies),
                b=rx.Parameter(value=cell.b, min=1.0, vary=varies),
                c=rx.Parameter(value=cell.c, min=1.0, vary=varies),
                alpha=rx.Parameter(value=cell.alpha, vary=varies),
                beta=rx.Parameter(value=cell.beta, vary=varies),
                gamma=rx.Parameter(value=cell.gamma, vary=varies)),
            atoms=[rx.Atom(
                label=site["label"], species=site["species"],
                x=rx.Parameter(value=site["xyz"][0], vary=site["vary_xyz"]),
                y=rx.Parameter(value=site["xyz"][1], vary=site["vary_xyz"]),
                z=rx.Parameter(value=site["xyz"][2], vary=site["vary_xyz"]),
                occ=rx.Parameter(value=site["occupancy"], min=0.0, max=1.5,
                                 vary=site["vary_occupancy"]),
                biso=rx.Parameter(value=site["biso"], min=0.0, max=25.0,
                                  vary=site["vary_biso"]))
                for site in sites],
            scale=rx.Parameter(value=1e-3, min=0.0, transform="softplus"))])
    except ValueError as exc:
        raise GsasExpError(
            f"{model.path or '<model>'}: phase {chosen.number} "
            f"({chosen.name!r}) states values this build's schema refuses "
            f"({exc}).  The file's own numbers are on `model.phases`") from exc

    if diagnostics is not None:
        named = model.path or "<model>"
        for raw, (canonical, wheres) in rewrites.items():
            diagnostics.append(Diagnostic(
                level="info", code="GSAS_EXP_SPECIES_NORMALISED",
                message=(f"species {raw!r} in {named} read as {canonical!r} — "
                         f"GSAS writes the scattering token in upper case; "
                         f"normalised to IUCr spelling"),
                where=wheres))
        if frozen:
            diagnostics.append(Diagnostic(
                level="info", code="GSAS_EXP_COORDINATES_SYMMETRY_FIXED",
                message=(
                    f"{named}: {len(frozen)} site(s) carry GSAS's X refine "
                    f"flag but sit on fully fixed special positions "
                    f"({', '.join(frozen)}), so nothing of them was free in "
                    f"GSAS either — its flag means 'refine as permitted by "
                    f"symmetry', and symmetry permits none"),
                where=[f"phases.0.atoms.{i}.x"
                       for i, a in enumerate(chosen.atoms)
                       if a.label in frozen]))
        diagnostics.append(Diagnostic(
            level="info", code="GSAS_EXP_SCALE_NOT_COMPARABLE",
            message=(
                f"{named}: phase {chosen.number}'s scale is seeded at 1e-3 and "
                f"not taken from the file.  GSAS's histogram scale "
                f"({model.histograms[0].scale if model.histograms else '?'}) "
                f"folds its own normalisation and the phase fraction into one "
                f"number, so it is not a rietx scale — refine it rather than "
                f"trusting a converted value"),
            where=["phases.0.scale"]))
    return structure
