"""Instrument-profile files: export a calibrated instrument, import it frozen.

The calibrate → freeze → refine-sample workflow (the reason the profile is
split into instrument ⊕ sample terms — see ``profiles.caglioti``):

1. **Calibrate** — refine a line-profile standard (NIST SRM 660c LaB6) with
   the ``lab_bragg_brentano`` plan; the instrument resolution function
   (U V W X Y), axial ratios, zero and emission-line ratio absorb everything
   the standard cannot broaden.
2. **Freeze** — :func:`save_instrument_profile` writes those values to a JSON
   file, *excluding* what belongs to the measurement rather than the
   instrument: the background model and the specimen displacement /
   transparency (properties of the mounted sample, reset to 0 on load).
3. **Refine the sample** — :func:`load_instrument_profile` returns an
   ``Instrument`` with every stored parameter ``vary=False``; run the
   ``lab_sample_refine`` plan, which frees only the four sample broadening
   terms (lor_size, lor_strain, gauss_size, gauss_strain), displacement,
   cell, scale/background and Biso.

This mirrors the instrument-parameter-file practice of GSAS-II (.instprm)
and FullProf (resolution files), with the whole instrument schema in one
typed JSON document.

:func:`read_gsas_prm` is a second, **foreign** importer living beside the
native JSON one: a GSAS-I ``.prm`` text file (Larson & Von Dreele, *GSAS —
General Structure Analysis System*, LAUR 86-748) is exactly the same kind of
object — a beamline calibration, not a starting guess — so it returns an
``Instrument`` through the same frozen (``vary=False``) contract
:func:`load_instrument_profile` does, rather than a third shape a caller has
to special-case.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from .._about import PROFILE_FORMAT_KEY
from ..schemas.common import Diagnostic
from ..schemas.instrument import (
    BackgroundChebyshev,
    EmissionLine,
    Instrument,
    Parameter,
)

# The GSAS record grammar, not the .EXP reader's: an instrument-parameter file
# and an experiment file write the same ICONS and PRCF records, so both readers
# in this package take them from one place (WP-1118).  `projects/gsas.py` is
# where the "read by column" doctrine is written down, which is why the grammar
# lives beside it; the registry it stays out of is about dispatch, not parsing.
from .projects.gsas import (
    CW_PROFILE_COEFFICIENTS,
    KEY_BYTES,
    GsasIcons,
    read_icons,
    read_prcf_header,
    split_records,
)

#: Tag a profile file is recognised by.  A format contract, so the token lives
#: in :mod:`.._about` free of the brand (WP-1062).
FORMAT_KEY = PROFILE_FORMAT_KEY
FORMAT_VERSION = "1"


def save_instrument_profile(instrument: Instrument, path: str | Path) -> None:
    """Write the instrument's calibrated state to a JSON profile file.

    The background, the specimen displacement/transparency, any surface
    roughness and the **specimen absorption** (µR/µt and the dimensions they
    are computed from) are stripped: they describe one measurement, not the
    goniometer.  Roughness is a property of how *this* specimen was packed and
    pressed, and µt of how thick *this* mount is, so carrying either into the
    next sample's refinement would be worse than useless — it would silently
    pre-bias that sample's ADPs, which is precisely the bias these corrections
    exist to remove (WP-0501, WP-0508).

    ``extra_components`` are stripped on the same grounds and it is the clearer
    case of the two: a diffuse hump belongs to this specimen, this can and this
    cryostat, so carrying one into the next sample would put a free peak at an
    angle nothing measured — and a free peak improves any Rwp.

    The whole list goes, including a
    :class:`~rietx.schemas.instrument.PeakComponent` whose declared cause — a
    holder, a mount, a window — really is the goniometer's and really would
    recur on the next specimen (WP-1103).  Stripped anyway, and stated here
    rather than left to be discovered: the field is one list with two members,
    the profile format has no way to carry half of it, and a component restored
    frozen at the wrong 2θ range would be refused at compile
    (``_compile_extra_peaks``) rather than ignored.  Re-declare the holder line
    on the sample's own instrument; it is three lines and it is where the
    centre bounds belong.
    """
    ins = instrument.model_copy(deep=True)
    ins.geometry.sample_displacement.value = 0.0
    ins.geometry.sample_transparency.value = 0.0
    ins.geometry.surface_roughness = None
    ins.geometry.mu_r = ins.geometry.capillary_radius_mm = None
    ins.geometry.mu_t = ins.geometry.thickness_mm = None
    doc = {
        FORMAT_KEY: FORMAT_VERSION,
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "instrument": ins.model_dump(mode="json",
                                     exclude={"background", "extra_components"}),
    }
    Path(path).write_text(json.dumps(doc, indent=1), encoding="utf-8")


def load_instrument_profile(path: str | Path) -> Instrument:
    """Read a profile file back as a **frozen** instrument.

    Every stored parameter comes back with ``vary=False`` — the calibration
    is data, not a starting guess.  The background is a fresh default
    (attach the model the new measurement needs); displacement and
    transparency are 0 and refinable per the sample plan, and surface roughness
    and specimen absorption are absent (declare them per specimen if the fit
    needs them).
    """
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get(FORMAT_KEY) != FORMAT_VERSION:
        raise ValueError(
            f"{path}: not a rietx instrument-profile file "
            f"(missing/unknown {FORMAT_KEY!r} tag)")
    ins = Instrument.model_validate({**doc["instrument"],
                                     "background": BackgroundChebyshev().model_dump(mode="json")})
    for p in _iter_parameters(ins):
        p.vary = False
    return ins


def _iter_parameters(ins: Instrument):
    yield ins.zero_shift
    yield ins.source.polarization
    for line in ins.source.lines:
        yield line.weight
    g = ins.geometry
    yield from (g.sample_displacement, g.sample_transparency, g.axial_sl, g.axial_hl)
    p = ins.profile
    yield from (p.u, p.v, p.w, p.x, p.y)


# ---------------------------------------------------------------------------
# GSAS-I .prm (Larson & Von Dreele, LAUR 86-748) — read_gsas_prm
# ---------------------------------------------------------------------------

#: ``HTYPE`` values this reader recognises and what each means.  Only
#: ``PXCR`` (constant-wavelength X-ray, Bragg-Brentano/Debye-Scherrer powder)
#: is read, and every other value is refused **by name** rather than
#: approximated.  The reason differs by value and the table says which:
#: a time-of-flight ``HTYPE`` puts something this reader's destination
#: (:class:`~rietx.schemas.instrument.ProfileTCHZ`, a Caglioti/TCH **angular**
#: resolution function) cannot express, which is the *scope, not evidence*
#: argument ``io/formats/gsas.py`` makes for its non-``CONS`` bintypes;
#: a constant-wavelength neutron ``HTYPE`` is the opposite case and is refused
#: for want of a fixture.  Claiming scope for both would be false of the
#: second.  ``PNTR`` is
#: the one this corpus actually contains (2 of 1508 files): powder neutron
#: time-of-flight, whose ``BNKPAR``/per-bank ``PRCF`` records parameterise a
#: flight-time peak shape (moderator pulse, L2, DIFC/DIFA) with no 2θ
#: resolution law inside them at all.
#:
#: ``PNCR`` is the other way round and is refused for a different reason.  A
#: constant-wavelength neutron file states exactly the kind of thing this
#: reader's destination can hold — ``ProfileTCHZ`` is where
#: :meth:`Instrument.constant_wavelength_neutron` puts its own resolution
#: function — so what stops it is not the *meaning* of the record but the
#: absence of a fixture: ``tests/data/mg090.Cu311.inst`` is the one real
#: ``PNCR`` file this repository holds and its ``PRCF`` is **type 1**, whose
#: coefficient layout no real example pins down (see ``_PRCF_TYPE_REFUSALS``).
#: Refusing it by name for the reason that is true keeps the refusal honest
#: and says what a future reader would need.
_HTYPE_PXCR = "PXCR"
_HTYPE_REFUSALS: dict[str, str] = {
    "PNTR": (
        "powder neutron time-of-flight data.  Its bank records carry BNKPAR "
        "(flight path, 2θ, DIFC/DIFA/DIFB) and per-bank PRCF coefficients "
        "that parameterise a flight-time peak shape (incident-pulse and "
        "moderator terms), not a 2θ Caglioti/TCH resolution function — there "
        "is nowhere in ProfileTCHZ for those numbers to go, and reading them "
        "as if they were GU/GV/GW would be a plausible wrong instrument "
        "rather than a near miss.  A time-of-flight profile is a different "
        "correction entirely (see the module docstring's calibrate/freeze "
        "workflow, written for a constant-wavelength source) and is out of "
        "scope here."
    ),
    "PNCR": (
        "powder neutron constant-wavelength data.  Unlike PNTR its "
        "resolution function is the kind ProfileTCHZ can hold — it is what "
        "Instrument.constant_wavelength_neutron builds — so this refusal is "
        "about evidence, not meaning: the one real PNCR file this "
        "repository holds (tests/data/mg090.Cu311.inst, the neutron half of "
        "the ndruo pair) carries a PRCF of type 1, and no real file pins "
        "down type 1's coefficient layout, so reading it by position off "
        "type 3 would be a guess rather than a parser.  A real type-3 PNCR "
        "file, or a type-1 example with numbers to verify against, is what "
        "this needs."
    ),
}

#: ``INS n PRCF1 <type> <ncoef> <cutoff>`` — the profile-function type this
#: reader reads.  Only type 3 (pseudo-Voigt with microstrain, GSAS's
#: ``NPROF=3``) is read: it is the **only** type present in every real,
#: non-template ``.prm`` this reader was built against (1499 of 1500 real
#: ``PXCR`` files; the 1500th is a stock GSAS example carrying dummy type
#: 2/3/4 blocks side by side under one bank — see below).  Each ``NPROF``
#: value has its **own**, independently-defined Fortran coefficient layout —
#: type 2's 6 coefficients and type 4's 12 are not a truncation or extension
#: of type 3's 19, so a real corpus example with real numbers is what a type
#: needs before it can be read at all, not a guess by position.  None was
#: found for 1, 2 or 4 (the only examples are the stock file's placeholder
#: GU=2, GV=-2, GW=5 dummy values), so all three are refused by name.
_PRCF_TYPE_3 = 3
_PRCF_TYPE_REFUSALS: dict[int, str] = {
    1: "GSAS profile function 1 (simple Gaussian, no Lorentzian term)",
    2: "GSAS profile function 2",
    4: "GSAS profile function 4",
}

#: The type-3 coefficients this reader maps, **named from the one table that
#: holds them** (``CW_PROFILE_COEFFICIENTS``, ``io/projects/gsas.py``) rather
#: than restated here: ``GU GV GW`` and ``LX LY`` onto ``ProfileTCHZ``, ``S/L``
#: and ``H/L`` onto ``Geometry``, ``GP`` refused unless it is zero.  Two
#: readers unpacking one coefficient order from two lists is how they come to
#: disagree, so this one is a slice of the other's.
_PRCF_MAPPED = CW_PROFILE_COEFFICIENTS[_PRCF_TYPE_3][:8]

def _prcf_labels(function: int) -> frozenset[str]:
    """Label tokens this profile function may print beside its coefficients.

    Some real files print the coefficient's name beside its number on the
    ``PRCF11``/``PRCF12`` continuation records (2 of 1500; e.g.
    ``PRCF11   GU  1.163000     GV -0.126000 ...``).  The count in the header
    counts **numeric** coefficients only, so a label is skipped rather than
    counted — it is prose, not a coefficient.  Confirmed against ``.LST``
    refinement logs for this instrument, which print the same eight names in
    the same order.

    The names are **this function's own**, from the one table that holds them,
    so a token that names a coefficient of some other profile function is not
    skipped here: it is refused, which is what a file the reader has
    misunderstood should do.
    """
    return frozenset(name.upper()
                     for name in CW_PROFILE_COEFFICIENTS.get(function, ()))


#: A ``.prm`` record's 12-byte key, by column: ``INS``, a three-column bank
#: number, then the record's own name from column 6.  The bank columns are
#: blank on the file-wide records (``BANK``, ``HTYPE``) and carry the bank
#: number on the rest.
_INS = "INS"
_BANK_COLUMNS = slice(3, 6)
_NAME_COLUMNS = slice(6, KEY_BYTES)


def _ins_records(text: str) -> list[tuple[str, str]]:
    """Every bank-1 (or bank-less) ``INS`` record, as ``(name, payload)``.

    A ``.prm`` is the same card index a ``.EXP`` is, so the payload starts at
    column 12 and every field in it is read at the offset
    ``projects/gsas.py`` states.  Records of another bank are dropped here;
    the reader refuses a multi-bank file outright a few lines on, and this
    keeps a bank-2 ``ICONS`` from being counted as a second bank-1 one in the
    meantime.
    """
    records = []
    for key, payload in split_records(text):
        if key[:len(_INS)].upper() != _INS:
            continue
        if key[_BANK_COLUMNS].strip() not in ("", "1"):
            continue
        records.append((key[_NAME_COLUMNS].strip().upper(), payload))
    return records


def _payloads(records: list[tuple[str, str]], name: str) -> list[str]:
    """Every payload under this record name, in file order."""
    return [payload for got, payload in records if got == name]


def read_gsas_prm(path: str | Path, *,
                  diagnostics: list[Diagnostic] | None = None) -> Instrument:
    """Read a GSAS-I ``.prm`` instrument-parameter file as a **frozen** ``Instrument``.

    Larson & Von Dreele (2004), *GSAS — General Structure Analysis System*,
    LAUR 86-748 (``ATTRIBUTION.md``: manual-as-spec, no code taken).  Reads
    the dominant case this format actually ships — a single ``BANK``,
    ``HTYPE PXCR`` (constant-wavelength X-ray), profile function 3 — and
    refuses everything else **by name**, following ``read_gsas``'s policy in
    ``io/formats/gsas.py``: a record this reader cannot map onto
    ``ProfileTCHZ`` is a refusal, not an approximation.

    Like :func:`load_instrument_profile`, every returned parameter comes back
    ``vary=False`` — an instrument-parameter file is a beamline calibration,
    not a starting guess (the module docstring's calibrate → freeze →
    refine-sample workflow).

    **The unit conversion** (GSAS's CW convention, centidegrees/-squared, to
    ``ProfileTCHZ``'s degrees/-squared)::

        1 centidegree  = 1e-2 degree        =>  LX, LY          /= 1e2
        1 centidegree² = (1e-2 degree)²     =>  GU, GV, GW      /= 1e4

    S/L and H/L are already dimensionless ratios and cross unconverted.
    Verified three ways (not merely derived): (1) the converted ``W`` at this
    instrument's own angles sits at FWHM ≈ 0.0035-0.004°, inside the
    ≈0.003-0.01° an 11-BM LaB6 line actually shows, and comfortably *below*
    every measured total peak width in a real pattern from this instrument
    (real specimen broadening can only add to the pure-instrument width, never
    subtract from it — a wrongly-scaled ``÷1e2`` reading predicts an
    "instrument-only" width that *exceeds* the narrowest observed peak, which
    is not physically possible); (2) a GSAS ``.LST`` refinement log for this
    exact instrument prints ``GU/GV/GW/S/L/H/L`` at the same numeric
    magnitude as the ``.prm``, confirming the field order (``GU GV GW GP LX
    LY S/L H/L …``) and that GSAS's own internal units are what the manual
    says; (3) an independent rietx-fitted profile of the same beamline gives
    ``W`` = 6.58e-6 deg² against this conversion's 6.30e-6 — a 4% agreement
    between two different LaB6 fits taken years apart.

    **Every record is read by column**, through the grammar
    ``io/projects/gsas.py`` holds: a ``.prm``'s ``INS`` records and a
    ``.EXP``'s ``HST`` records are the same GSAS records under different
    four-character keys, so both readers here call
    :func:`~rietx.io.projects.gsas.read_icons` and
    :func:`~rietx.io.projects.gsas.read_prcf_header` rather than each parsing
    one (WP-1118).  ``ICONS``'s fields are ``LAM1 LAM2 ZERO [IREF] [IDAMP]
    POLA IPOLA KRATIO``, and the optional ones are why a whitespace split
    cannot do this: a file leaving ``IREF`` and ``IDAMP`` blank splits into
    six tokens that happen to land on the right meanings, and one writing
    ``IDAMP`` splits into seven that do not.

    Its fields are then read or refused individually, never guessed.
    ``LAM1`` and ``POLA`` (0.990 in every real 11-BM file, matching this
    package's own :meth:`Instrument.debye_scherrer` default) are read.  A
    **doublet is read too**: ``LAM2`` becomes a second
    :class:`~rietx.schemas.instrument.EmissionLine` weighted by ``KRATIO``,
    which is the Kα2/Kα1 intensity ratio and so is exactly what
    ``EmissionLine.weight`` holds — a line's intensity relative to the first,
    which the parameter table pins at 1.  A ``LAM2`` with no ``KRATIO`` to
    weight it by is refused, because supplying the conventional 0.5 would be
    this reader's number rather than the file's, and the polarization two
    fields earlier is conventionally 0.5 as well.

    A non-zero ``ZERO`` (its unit is disputed between two GSAS-adjacent
    conventions 100x apart, see ``io/recipe.py``'s ``_read_zero_shift``, and
    no real file in this corpus has a non-zero value to settle it against) and
    a non-zero ``IPOLA`` (the polarization *type*, which says which convention
    ``POLA`` is stated in) are each refused: every real file in the corpus has
    both at 0, so refusing only a non-zero occurrence reads every real file
    while never silently discarding a value that would have changed the
    answer.  The refine flags and ``IDAMP`` are refinement controls, which a
    frozen calibration has no use for, and are dropped with a diagnostic.
    ``IRAD`` and ``ITYP`` (radiation-table code and angular range) are
    deliberately ignored: the wavelength is read directly from ``ICONS``
    rather than looked up from ``IRAD``'s table, and an angular range belongs
    to the pattern, not the instrument.

    Similarly for ``PRCF``: only the eight coefficients this package has room
    for are read, **named from the one table that names them**
    (``CW_PROFILE_COEFFICIENTS``, keyed by profile function because type 2's
    fourth coefficient is ``LX`` and type 3's is ``GP``), and they land on
    **two** objects — ``GU GV GW`` →
    ``profile.u/v/w`` and ``LX LY`` → ``profile.x/y``, but ``S/L H/L`` →
    ``geometry.axial_sl``/``geometry.axial_hl``.  That split is why
    ``GSAS_PRM_GEOMETRY_ASSUMED`` says to carry those two over: replacing the
    geometry wholesale discards two coefficients the file *did* state.
    ``GP`` (position 4) and every coefficient past position 8 (``trns``,
    ``shft``, ``sfec`` and further reserved slots) are refused if non-zero
    and dropped only at their identity value (0) — every real file in the
    corpus is 0 there, so this is the same "refuse a value at drift, never a
    value at the model's identity" rule ``io/CLAUDE.md``'s ``recipe.py``
    section already states, applied to a second format's version of it.

    A value the file states that lies outside the range the ``Instrument``
    schema holds — a negative ``GW``, a ``POLA`` on some other convention's
    0-100 scale — is refused **naming the file**, by ``_build_instrument``,
    rather than escaping as pydantic's own report on a field.

    **``diagnostics``** completes that rule's other half: a value dropped at
    the model's identity is dropped *with a diagnostic*, so a caller can learn
    that the file said something the ``Instrument`` does not carry.  Pass a
    list to collect them; the codes are

    * ``GSAS_PRM_FIELD_DROPPED`` — once per record that carried a field this
      reader does not map: ``ICONS``, ``PRCF`` (``GP`` and every coefficient
      past position 8, all at 0), and ``IRAD``/``ITYP``, which are ignored by
      design.  The ``ICONS`` row names ``IPOLA``, the refine flags and
      ``IDAMP``, and says what became of ``KRATIO`` — carried as the second
      line's weight where the file states a doublet, read and **not applied**
      where it does not.  A zero ``LAM2`` and a zero ``ZERO`` are dropped at
      their identity without being named, because "LAM2 = 0" *is* "no second
      line" and naming it would add nothing.  Each
      row describes a record **this file carried**: the ``IRAD``/``ITYP`` row
      is absent for a file holding neither, and the "past position 8" clause
      is absent for a ``PRCF`` declaring exactly eight.
    * ``GSAS_PRM_GEOMETRY_ASSUMED`` — always, because a ``.prm`` states no
      geometry at all and this reader returns
      :meth:`Instrument.debye_scherrer`.

    That second one matters more than a dropped zero.  ``Geometry.kind``
    selects the position correction and its suggested action
    (``report/layer1.POSITION_TEMPLATES``,
    ``layer2._POSITION_ACTIONS_BY_GEOMETRY``), and the two geometries'
    absorption corrections have different *off* states (``mu_r = 0`` against
    ``mu_t = ∞``).  ``PXCR`` spans Bragg-Brentano and Debye-Scherrer, and the
    format gives nothing to tell them apart, so this reader does not infer:
    it picks the one the corpus it was built against is (11-BM capillary) and
    **says so**.  A caller reading a flat-plate ``PXCR`` calibration must set
    the geometry itself.
    """
    p = Path(path)
    # latin-1, never utf-8 with errors ignored.  A ``.prm``'s ``I HEAD`` record
    # holds whatever the experimenter typed, and a decode that *drops* an
    # undecodable byte shortens that record — which no longer matters for a
    # record read as prose, but does the moment every other record is read at a
    # column (the same trap the .EXP sniff was moved onto bytes for).
    raw = p.read_bytes()
    records = _ins_records(raw.decode("latin-1"))

    htypes = _payloads(records, "HTYPE")
    banks = _payloads(records, "BANK")
    # HTYPE is the only field on its record, so stripping the whole payload
    # cannot re-assign anything — and it reports what the file states rather
    # than the four columns the layout allows, which is what a refusal by name
    # owes a reader whose file says something longer.
    htype = htypes[0].strip().upper() if htypes else ""
    # BANK's count is ``I5``, so it is read at its column like every other
    # field here.  Testing the *whole* payload for digits reads a record that
    # carries anything after the number as an absent record, and the refusal
    # then says "no BANK/HTYPE record found" about a file that has one.
    bank_field = banks[0][:5].strip() if banks else ""
    if not htype or not bank_field.isdigit():
        raise ValueError(
            f"{p.name}: not a GSAS-I instrument-parameter file — no "
            f"BANK/HTYPE record found (Larson & Von Dreele, LAUR 86-748)")

    _check_htype(htype, p)

    nbank = int(bank_field)
    if nbank != 1:
        raise ValueError(
            f"{p.name}: declares BANK {nbank} — only a single-bank "
            f"instrument file is read.  No real multi-bank PXCR file was "
            f"found in the corpus this reader was built against (the only "
            f"multi-bank files seen are HTYPE PNTR, refused above); reading "
            f"one bank of several would silently pick a bank rather than "
            f"letting the caller choose")

    icons = _read_icons(records, p)
    prof_type, coeffs = _read_prcf(records, p)
    if prof_type != _PRCF_TYPE_3:
        what = _PRCF_TYPE_REFUSALS.get(prof_type)
        if what is None:
            raise ValueError(
                f"{p.name}: unrecognised GSAS PRCF profile type "
                f"{prof_type!r} — only type 3 (pseudo-Voigt with "
                f"microstrain) is read.  Types "
                f"{', '.join(sorted(_PRCF_TYPE_REFUSALS))} are recognised "
                f"and refused, each for lacking a real fixture to derive "
                f"its coefficient layout from; this is not one of those "
                f"either, so what its coefficients mean is not established "
                f"at all")
        raise ValueError(
            f"{p.name}: this bank's profile is {what} (GSAS PRCF type "
            f"{prof_type}) — only type 3 is read.  Each GSAS profile "
            f"function has its own, independently-defined coefficient "
            f"layout (type 3's 19 are not a superset of type {prof_type}'s "
            f"{len(coeffs)}), and no real instrument file of this type was "
            f"found to derive or verify one against — only a stock example "
            f"carrying placeholder zero-broadening values.  Reading it by "
            f"position off type 3 would be a guess, not a parser")

    if len(coeffs) < len(_PRCF_MAPPED):
        raise ValueError(
            f"{p.name}: this bank's PRCF1 header declares a type-3 profile "
            f"with {len(coeffs)} coefficient(s), but positions "
            f"1-{len(_PRCF_MAPPED)} ({' '.join(_PRCF_MAPPED)}) are what this "
            f"reader maps onto ProfileTCHZ and Geometry — a type-3 record "
            f"shorter than that is refused rather than read as a subset, "
            f"because nothing in the file says which of the eight is the "
            f"missing one.  The count in the header is what this reader "
            f"trusts (see _read_prcf), so this is a header declaring fewer "
            f"than the mapping needs, not a truncated file")
    named = dict(zip(_PRCF_MAPPED, coeffs, strict=False))
    gu, gv, gw = named["GU"], named["GV"], named["GW"]
    gp, lx, ly = named["GP"], named["LX"], named["LY"]
    sl, hl = named["S/L"], named["H/L"]
    rest = coeffs[len(_PRCF_MAPPED):]
    if gp != 0.0:
        raise ValueError(
            f"{p.name}: PRCF coefficient 4 (GSAS 'GP') is {gp!r}, not 0 — "
            f"this reader has no mapping for it (every real file in the "
            f"corpus this was built against carries 0 here, so it was never "
            f"identified), and dropping a non-zero value silently is what "
            f"this refusal exists to prevent")
    for i, v in enumerate(rest, start=9):
        if v != 0.0:
            raise ValueError(
                f"{p.name}: PRCF coefficient {i} of {len(coeffs)} "
                f"(GSAS 'trns'/'shft'/'sfec' or a further reserved slot) is "
                f"{v!r}, not 0 — this reader maps only GU/GV/GW/GP/LX/LY/"
                f"S/L/H/L (positions 1-8) onto ProfileTCHZ and Geometry, and "
                f"every real "
                f"file this reader was built against carries 0 past "
                f"position 8, so a non-zero one here is unidentified rather "
                f"than dropped")

    instrument = _build_instrument(icons, (gu, gv, gw, lx, ly, sl, hl), p)

    if diagnostics is not None:
        # The drop half of io/CLAUDE.md's rule: a field at the model's
        # identity is dropped *with a diagnostic*, one per record, naming the
        # values so the caller can see what was in the file.  Emitted only
        # here, past every refusal above — the build on the line above is the
        # last thing that can refuse — so a file about to be refused does
        # not leave a half-list behind on the caller's list.
        # Each row is a statement about *this file*, so a row is only built
        # where the file carried the thing it describes.  A drop diagnostic
        # for a record that is absent is the same shape as a defaulted field
        # answering a question nobody asked (WP-1076): it is `info`, and the
        # corpus makes it true often enough that it would not be noticed.
        blank = "blank"
        ratio = blank if icons.ka2_ratio is None else icons.ka2_ratio
        ratio_note = (
            f"KRATIO = {ratio}, carried as the second emission line's weight"
            if icons.lam2 else
            f"KRATIO = {ratio}, read and not applied (it weights a second "
            f"line, and LAM2 states none here)")
        dropped = [
            ("ICONS", f"IPOLA (the polarization type) = "
                      f"{blank if icons.polarization_type is None else 0}, "
                      f"the refine flags and IDAMP = "
                      f"{blank if icons.damping is None else icons.damping} "
                      f"(refinement controls, which a frozen calibration has "
                      f"no use for), and {ratio_note}"),
        ]
        past_8 = (f", and {len(rest)} coefficient(s) past position "
                  f"{len(_PRCF_MAPPED)} = 0" if rest else "")
        dropped.append(
            ("PRCF", f"GP (position 4) = 0{past_8} — this reader maps "
                     f"positions 1-3 and 5-6 onto ProfileTCHZ and 7-8 "
                     f"(S/L, H/L) onto Geometry"))
        if any(name.endswith(("IRAD", "ITYP")) for name, _ in records):
            dropped.append(
                ("IRAD/ITYP", "ignored by design: the wavelength is read from "
                              "ICONS rather than looked up from IRAD's table, "
                              "and an angular range belongs to the pattern, "
                              "not the instrument"))
        for record, what in dropped:
            diagnostics.append(Diagnostic(
                level="info", code="GSAS_PRM_FIELD_DROPPED",
                message=f"{p.name}: {record} — {what}",
                where=[record]))

    if diagnostics is not None:
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS_PRM_GEOMETRY_ASSUMED",
            message=(f"{p.name}: a GSAS .prm states no geometry, and HTYPE "
                     f"PXCR spans Bragg-Brentano and Debye-Scherrer, so this "
                     f"instrument came back debye_scherrer "
                     f"(packing_fraction=0.6, a capillary offset pair) "
                     f"because that is what the corpus this reader was built "
                     f"against is — it was not read from the file"),
            where=["instrument.geometry.kind"],
            suggestion=("if this calibration is from a flat-plate "
                        "diffractometer, set the geometry yourself: "
                        "Geometry.kind selects the position correction and "
                        "the two geometries' absorption corrections have "
                        "different off states (mu_r = 0 against mu_t = inf).  "
                        "Carry geometry.axial_sl and geometry.axial_hl over "
                        "to the replacement first: PRCF positions 7-8 "
                        "(S/L, H/L) were read from THIS file and land on the "
                        "geometry, so a fresh Geometry starts at 0 for both "
                        "and models an instrument with no axial divergence "
                        "at all")))
    return instrument


def _build_instrument(icons: GsasIcons,
                      coefficients: tuple[float, ...], p: Path) -> Instrument:
    """The ``Instrument`` this bank states, frozen, or a refusal naming the file.

    Every value here is the file's own, and the schema holds each to a range
    (``ProfileTCHZ.w`` is non-negative, ``Source.polarization`` sits in [0, 1],
    a wavelength is at least 1e-3 Å).  ``Base`` validates on assignment, so a
    value outside one of those raises **here** rather than at stage compile.
    Measured 2026-09-15: assigning a negative ``GW`` raises a
    ``ValidationError`` naming ``Parameter``, with no file in it.  How often a
    real GSAS refinement writes one is **not** measured, and the conversion is
    refused on its own terms either way.

    Reading by column is what makes it worth converting.  A whitespace split
    could put any number in any slot, so an out-of-range value was evidence of
    a misaligned read; located by column it is the file's own statement, and
    the refusal is the reader's to make **naming the file** rather than
    pydantic's to make naming a field (``io/CLAUDE.md`` § Refusals).
    """
    gu, gv, gw, lx, ly, sl, hl = coefficients
    try:
        instrument = Instrument.debye_scherrer(
            wavelength=icons.lam1, polarization=icons.polarization)
        if icons.lam2:
            # A second line's weight is relative to the first, which the
            # parameter table pins at 1 (EmissionLine) — so KRATIO, the
            # Kα2/Kα1 intensity ratio, is exactly the number this slot wants.
            # Reading it is what locating the field by column bought: the old
            # reader could not tell KRATIO from the polarization two fields
            # earlier, both conventionally 0.5, and refused every doublet
            # rather than guess (WP-1118).
            instrument.source.lines.append(EmissionLine(
                wavelength=icons.lam2,
                weight=Parameter(value=icons.ka2_ratio, min=0.0, max=2.0)))
        prof = instrument.profile
        prof.u.value = gu / 1e4
        prof.v.value = gv / 1e4
        prof.w.value = gw / 1e4
        prof.x.value = lx / 1e2
        prof.y.value = ly / 1e2
        instrument.geometry.axial_sl.value = sl
        instrument.geometry.axial_hl.value = hl
    except ValidationError as exc:
        raise ValueError(
            f"{p.name}: this bank states a value outside the range this "
            f"package's Instrument holds — ICONS LAM1 {icons.lam1}, LAM2 "
            f"{icons.lam2}, POLA {icons.polarization}, KRATIO "
            f"{icons.ka2_ratio}; PRCF converted to U {gu / 1e4}, V "
            f"{gv / 1e4}, W {gw / 1e4}, X {lx / 1e2}, Y {ly / 1e2}, S/L "
            f"{sl}, H/L {hl}.  Read by column every one of those is the "
            f"file's own number rather than a field landing in the wrong "
            f"slot, so the calibration is refused here, naming the file, "
            f"rather than arriving later as a schema error that names none: "
            f"{exc}") from exc
    for param in _iter_parameters(instrument):
        param.vary = False
    return instrument


def _check_htype(htype: str, p: Path) -> None:
    """Pass ``PXCR``; refuse any other ``HTYPE`` **by name**."""
    if htype == _HTYPE_PXCR:
        return
    what = _HTYPE_REFUSALS.get(htype)
    if what is not None:
        raise ValueError(f"{p.name}: HTYPE {htype} is {what}")
    raise ValueError(
        f"{p.name}: unrecognised GSAS HTYPE {htype!r} — only PXCR "
        f"(constant-wavelength X-ray) is read.  "
        f"{', '.join(sorted(_HTYPE_REFUSALS))} "
        f"{'is' if len(_HTYPE_REFUSALS) == 1 else 'are'} recognised and "
        f"refused by name; this is not one of those either, so what this "
        f"file's HTYPE means is not established at all")


def _read_icons(records: list[tuple[str, str]], p: Path) -> GsasIcons:
    """Read bank 1's ``ICONS`` record, **by column**, and refuse what it states
    that this reader cannot carry.

    The fields are ``LAM1 LAM2 ZERO [IREF] [IDAMP] POLA IPOLA KRATIO``, read
    through :func:`~rietx.io.projects.gsas.read_icons` — the same call the
    ``.EXP`` reader makes, because it is the same GSAS record.  **Reading it
    by column is the correction this function exists for** (WP-1118): it used
    to split on whitespace and require exactly six tokens, which is right only
    for a file that leaves ``IREF`` and ``IDAMP`` blank.  Every 11-BM file in
    ``tests/data`` does, so the six lined up and the reader looked correct;
    ``INST_XRY.PRM`` writes ``IDAMP`` and was refused for having seven.  The
    failure was safe rather than silent, but only by luck of the corpus, and
    the two GSAS readers here disagreed about one record.

    What the *values* must be is unchanged, with one exception.  A non-zero
    ``ZERO`` is still refused (its unit is disputed between two GSAS-adjacent
    conventions a factor of 100 apart), and so is a polarization type this
    reader does not carry.  A **doublet is now read** rather than refused:
    the reason for refusing it was that no file here stated the intensity
    weight, and that reason was an artefact of not knowing which field
    ``KRATIO`` was.
    """
    payloads = _payloads(records, "ICONS")
    if len(payloads) != 1:
        raise ValueError(
            f"{p.name}: expected exactly one ICONS record for bank 1, found "
            f"{len(payloads)} — a bank declaring its constants more than once "
            f"(or not at all) is ambiguous, not a single instrument")
    icons = read_icons(payloads[0])

    if not icons.lam1:
        raise ValueError(
            f"{p.name}: bank 1's ICONS record states no primary wavelength "
            f"(LAM1, columns 12-22) — the field is blank or is not a number, "
            f"and an instrument file without a wavelength describes no "
            f"instrument")
    if icons.polarization is None:
        raise ValueError(
            f"{p.name}: bank 1's ICONS record states no polarization (POLA, "
            f"columns 52-62) — the field is blank or is not a number.  Every "
            f"real file in the corpus states it, and falling back on "
            f"Instrument.debye_scherrer's 0.99 would put this package's "
            f"number into an instrument the caller will read as the file's")
    if icons.zero:
        raise ValueError(
            f"{p.name}: ICONS field ZERO is {icons.zero!r}, not 0 — "
            f"its unit is disputed between two GSAS-adjacent conventions a "
            f"factor of 100 apart (io/recipe.py's Zero handling) and no "
            f"real file in this corpus has a non-zero value to settle it "
            f"against, so a non-zero one here is refused rather than mapped "
            f"onto instrument.zero_shift on either guess")
    if icons.polarization_type:
        raise ValueError(
            f"{p.name}: ICONS field IPOLA (the polarization type) is "
            f"{icons.polarization_type!r}, not 0 — every real file in the "
            f"corpus this reader was built against carries 0, which is the "
            f"convention Instrument.debye_scherrer's POLA follows, so what "
            f"another code means is not established here.  Reading POLA "
            f"under a type this reader cannot name would apply the right "
            f"number under the wrong convention")
    if icons.lam2 and not icons.ka2_ratio:
        raise ValueError(
            f"{p.name}: ICONS states a second wavelength line (LAM2 = "
            f"{icons.lam2!r}) and no KRATIO to weight it by — the field is "
            f"blank or zero.  A line's weight is relative to the first "
            f"(EmissionLine), so a doublet needs the ratio the file did not "
            f"state, and supplying the conventional 0.5 would be this "
            f"reader's number rather than the file's")
    if icons.lam2 and not 0.0 < icons.ka2_ratio <= 2.0:
        raise ValueError(
            f"{p.name}: ICONS field KRATIO is {icons.ka2_ratio!r}, which is "
            f"not a Kα2/Kα1 intensity ratio (EmissionLine.weight holds "
            f"0 < w <= 2; a sealed tube is ≈0.5) — refused rather than "
            f"clamped, since a value this far from the convention says the "
            f"field means something else in this file")
    return icons


def _read_prcf(records: list[tuple[str, str]],
               p: Path) -> tuple[int | None, list[float]]:
    """Read bank 1's single ``PRCF1`` block: (profile type, coefficients).

    The **header** is a fixed-format record like every other, read by column
    through :func:`~rietx.io.projects.gsas.read_prcf_header`.  The block is a
    **counted** layout: the header states how many numeric coefficients follow
    across the ``PRCF11``…``PRCF1n`` continuation records, and that count — not
    the number of records present — is what is consumed.

    **The continuation records are the one place a whitespace split is right**,
    and this is the exception rather than an oversight.  GSAS's own
    instrument-file editor prints coefficient labels *inside* the 15-column
    fields on some files, which pushes every later field off its column:
    ``11BM_LaB6_cBN_mg2044.prm`` in ``tests/data`` is 61 characters where
    ``4E15.6`` is 60, and reading its second field by column returns
    ``'     GV -0.1260'``.  A token read survives that; a column read does not,
    and the ``.EXP`` reader can use a column read on its own continuations
    only because no ``.EXP`` carries labels.  What the token read must not do
    is *skip* a field it cannot parse, which compacts the list and renames
    every coefficient after it — so an unreadable token is refused by name,
    which is the half of the hazard the ``.EXP`` review found the other end of.
    """
    headers = _payloads(records, "PRCF1")
    if len(headers) != 1:
        raise ValueError(
            f"{p.name}: expected exactly one PRCF1 header for bank 1, found "
            f"{len(headers)} — a bank declaring its profile function more "
            f"than once (the one real example is a stock GSAS file stacking "
            f"types 2, 3 and 4 with placeholder values under one bank) is "
            f"ambiguous about which applies, not a richer instrument")
    header = read_prcf_header(headers[0])
    prof_type, ncoef = header.function, header.n_coefficients
    if prof_type is None:
        raise ValueError(
            f"{p.name}: this bank's PRCF1 header states no profile function "
            f"type (columns 12-17 are blank) — the coefficients below it "
            f"cannot be named without one, because each GSAS function has its "
            f"own order and type 2's fourth is LX where type 3's is GP")
    labels = _prcf_labels(prof_type)

    coeffs: list[float] = []
    for name, payload in records:
        if not (name.startswith("PRCF1") and name[5:].isdigit()):
            continue
        for tok in payload.split():
            if tok.upper() in labels:
                continue
            try:
                coeffs.append(float(tok))
            except ValueError:
                raise ValueError(
                    f"{p.name}: PRCF11..PRCF1n holds an unrecognised token "
                    f"{tok!r} that is neither a number nor a label of profile "
                    f"function {prof_type} ({sorted(labels)}) — refusing "
                    f"rather than silently skipping it, since a genuine "
                    f"coefficient dropped this way would shift every one "
                    f"after it") from None
            if len(coeffs) >= ncoef:
                break
        if len(coeffs) >= ncoef:
            break

    if len(coeffs) < ncoef:
        raise ValueError(
            f"{p.name}: PRCF1 declares {ncoef} coefficients but only "
            f"{len(coeffs)} were found across its PRCF11..PRCF1n "
            f"continuation lines before the record ended — the count in "
            f"the header, not the number of lines present, is what this "
            f"reader trusts, so a short file is refused rather than padded")
    return prof_type, coeffs[:ncoef]
