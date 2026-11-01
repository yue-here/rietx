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
import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from .._about import PROFILE_FORMAT_KEY
from ..model.profiles.caglioti import (
    _MIN_GAMMA_G2,
    GAUSSIAN_VARIANCE_TO_FWHM_SQUARED,
    lorentzian_negative_above,
)
from ..schemas.common import SCHEMA_VERSION, Diagnostic
from ..schemas.instrument import (
    DEBYE_SCHERRER_POLARIZATION,
    PACKING_FRACTION,
    TCHZ_BOUNDS,
    BackgroundChebyshev,
    EmissionLine,
    Geometry,
    Instrument,
    NeutronSource,
    Parameter,
    ProfileTCHZ,
    Source,
)

# The GSAS record grammar, not the .EXP reader's: an instrument-parameter file
# and an experiment file write the same ICONS and PRCF records, so both readers
# in this package take them from one place (WP-1118).  `projects/gsas.py` is
# where the "read by column" doctrine is written down, which is why the grammar
# lives beside it; the registry it stays out of is about dispatch, not parsing.
from ..schemas.migrate import (
    UNSTAMPED_SCHEMA,
    declared_range_repairs,
    newest_declared_since,
    restore_declared_ranges,
    schema_key,
)
from .projects.gsas import (
    CW_PROFILE_COEFFICIENTS,
    KEY_BYTES,
    GsasIcons,
    GsasPrcfHeader,
    _naming_the_file,
    read_icons,
    read_prcf_header,
    split_records,
)

# GSAS-II's own grammar, on the same footing and for the same reason: the
# ``.instprm`` key vocabulary, its centidegree conversion and its bank layout
# belong beside the ``.gpx`` reader that shares them, and the Instrument this
# module builds from them belongs here beside the ``.prm`` pair (WP-1118).
from .projects.gsas2 import (
    CW_TYPES,
    HISTOGRAM_TYPES,
    INSTPRM_CW_DOUBLET,
    INSTPRM_CW_SINGLE,
    INSTPRM_DIFF_TYPES,
    instprm_factor,
    read_instprm,
    write_instprm,
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
    # A bank would be written and could not be read back (the loader's
    # ``_iter_parameters`` is a constant-wavelength list), so it is refused here.
    from ..schemas.pattern import require_two_theta

    require_two_theta(None, "save_instrument_profile()", instrument=instrument)
    ins = instrument.model_copy(deep=True)
    ins.geometry.sample_displacement.value = 0.0
    ins.geometry.sample_transparency.value = 0.0
    ins.geometry.surface_roughness = None
    ins.geometry.mu_r = ins.geometry.capillary_radius_mm = None
    ins.geometry.mu_t = ins.geometry.thickness_mm = None
    doc = {
        FORMAT_KEY: FORMAT_VERSION,
        # what the reader's declared-range repair is gated on (WP-1321)
        "schema_version": SCHEMA_VERSION,
        "created_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "instrument": ins.model_dump(mode="json",
                                     exclude={"background", "extra_components"}),
    }
    Path(path).write_text(json.dumps(doc, indent=1), encoding="utf-8")


def load_instrument_profile(path: str | Path, *,
                            diagnostics: list[Diagnostic] | None = None) -> Instrument:
    """Read a profile file back as a **frozen** instrument.

    Every stored parameter comes back with ``vary=False`` — the calibration
    is data, not a starting guess.  The background is a fresh default
    (attach the model the new measurement needs); displacement and
    transparency are 0 and refinable per the sample plan, and surface roughness
    and specimen absorption are absent (declare them per specimen if the fit
    needs them).

    ``diagnostics``, when a list is passed, collects what the read repaired:
    a profile saved before a class inherited its declared ranges (issue #204)
    stores a caller's own ``Parameter`` at ``(-inf, inf)``, and it gets its
    field's range back as ``DECLARED_RANGE_RESTORED``, or is left as stored
    where its value lies outside that range, as ``DECLARED_RANGE_NOT_RESTORED``
    (:func:`~rietx.schemas.migrate.restore_declared_ranges`).  A profile with
    no ``schema_version`` predates the stamp and is read as the oldest.
    """
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get(FORMAT_KEY) != FORMAT_VERSION:
        raise ValueError(
            f"{path}: not a rietx instrument-profile file "
            f"(missing/unknown {FORMAT_KEY!r} tag)")
    ins = Instrument.model_validate({**doc["instrument"],
                                     "background": BackgroundChebyshev().model_dump(mode="json")})
    written = doc.get("schema_version", UNSTAMPED_SCHEMA)
    if schema_key(written) < newest_declared_since():
        where = f"the profile {Path(path).name}"
        found = {c["path"]: [(where, c)]
                 for c in declared_range_repairs(ins, written, "instrument.")}
        notes = restore_declared_ranges(found, where)
        if diagnostics is not None:
            diagnostics.extend(notes)
    # A profile file holding a bank (written by a version that did not refuse
    # one) is refused by name: ``_iter_parameters`` lists constant-wavelength
    # parameters, and a bank's ``difc`` and ``profile_tof.*`` would stay free.
    # The file leads the message, as every other refusal here does: a reader
    # raises naming the file (CLAUDE.md § Invariants, WP-1047).
    from ..schemas.pattern import require_two_theta

    require_two_theta(None, f"{path}: load_instrument_profile()", instrument=ins)
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

#: ``HTYPE`` values this reader reads, and the radiation each names.  Both are
#: constant-wavelength, so both state a Caglioti/TCH **angular** resolution
#: law, which is what :class:`~rietx.schemas.instrument.ProfileTCHZ` holds —
#: for ``PNCR`` it is where :meth:`Instrument.constant_wavelength_neutron`
#: puts its own.  Whether a file of either reads is then decided by its
#: ``PRCF`` type, never by its ``HTYPE`` (issue #437, WP-1312): the ``INS
#: bbPRCFn`` record (``PTYP, NCOF, CTOF``; Larson & Von Dreele, LAUR 86-748)
#: is defined by profile function, not by radiation, so type 3 reads under
#: either and the other types are refused under either, each refusal naming
#: the type the file in hand carries.  The first real type-3 ``PNCR`` file,
#: ``tests/data/gsas2_hb2a_cr2wo6.prm`` (HFIR HB-2A), is what pins that down.
_HTYPE_PXCR = "PXCR"
_HTYPE_PNCR = "PNCR"
_HTYPES_READ: dict[str, str] = {
    _HTYPE_PXCR: "constant-wavelength X-ray",
    _HTYPE_PNCR: "constant-wavelength neutron",
}

#: ``HTYPE`` values this reader recognises in order to refuse them **by
#: name** rather than approximate them.  ``PNTR`` is the one the corpus this
#: reader was built against actually contains (2 of 1508 files): powder
#: neutron time-of-flight, whose ``BNKPAR``/per-bank ``PRCF`` records
#: parameterise a flight-time peak shape (moderator pulse, L2, DIFC/DIFA) with
#: no 2θ resolution law inside them at all — the *scope, not evidence*
#: argument ``io/formats/gsas.py`` makes for its non-``CONS`` bintypes.
_HTYPE_REFUSALS: dict[str, str] = {
    "PNTR": (
        "powder neutron time-of-flight data.  Its bank records carry BNKPAR "
        "(flight path, 2θ, DIFC/DIFA/DIFB) and per-bank PRCF coefficients "
        "that parameterise a flight-time peak shape (incident-pulse and "
        "moderator terms), not a 2θ Caglioti/TCH resolution function — there "
        "is nowhere in ProfileTCHZ for those numbers to go, and reading them "
        "as if they were GU/GV/GW would be a plausible wrong instrument "
        "rather than a near miss.  A time-of-flight bank is read by "
        "rietx.read_gsas_tof_iparm, which returns one Instrument per bank "
        "with a neutron_tof source."
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


@_naming_the_file(ValueError)
def read_gsas_prm(path: str | Path, *, profile_set: int | None = None,
                  diagnostics: list[Diagnostic] | None = None) -> Instrument:
    """Read a GSAS-I ``.prm`` instrument-parameter file as a **frozen** ``Instrument``.

    Larson & Von Dreele (2004), *GSAS — General Structure Analysis System*,
    LAUR 86-748 (``ATTRIBUTION.md``: manual-as-spec, no code taken).  Reads
    the dominant case this format actually ships — a single ``BANK``,
    ``HTYPE PXCR`` (constant-wavelength X-ray), profile function 3 — and
    its neutron twin, ``HTYPE PNCR`` with profile function 3, which lands on
    :meth:`Instrument.constant_wavelength_neutron` at ``LAM1`` with the same
    coefficient mapping (the ``PRCF`` record is defined by profile function,
    not by radiation; WP-1312, issue #437).  Everything else is refused
    **by name**, following ``read_gsas``'s policy in
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
        Gaussian variance σ² -> FWHM² (Γ² = 8 ln 2 · σ²)
                                              =>  GU, GV, GW      *= 8 ln 2

    ``GU GV GW`` are the coefficients of a Gaussian **variance**, σ² = GU tan²θ
    + GV tanθ + GW (the GSAS manual, "CW profile functions", functions 3 and 4:
    "The Gaussian variance of the peak, σ²"), and ``profile.u/v/w`` those of
    the Gaussian FWHM², so the unit change is followed by the factor 8 ln 2
    (#735; the same factor as the GSAS-II ``.instprm``'s ``U V W``, #705).

    S/L and H/L are already dimensionless ratios and cross unconverted.
    The unit change and the field order are corroborated by a GSAS ``.LST``
    refinement log for this exact instrument, which prints ``GU/GV/GW/S/L/H/L``
    at the same numeric magnitude as the ``.prm``.  The 8 ln 2 is the manual's
    statement that these coefficients are a variance.  Two earlier checks, a
    converted ``W`` landing inside the width an 11-BM LaB6 line shows and
    agreeing to 4 % with a rietx-fitted ``W`` of the same beamline, were read
    as confirming the unit change alone; both are consistent with it and
    neither can tell a factor 2.35 from a specimen contribution, so they are
    not evidence against the variance reading.

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

    **A bank may offer several profile sets**, each its own ``PRCFn`` block
    (``BT1_Cu311.inst`` from GSAS-II's tutorials states types 1, 2 and 3 as
    sets 1, 2 and 3).  ``profile_set`` names the one to read, as ``scan=``
    names a scan in :func:`~rietx.read_pattern`.  Left ``None``, set 1 is
    read, which is what GSAS-II's own importer reads, and a file offering more
    than one says so; a file with no set 1 is refused, naming the sets it
    does state.  A set that is not type 3 is refused, and the refusal names a
    type-3 set when the file offers one.

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
      :meth:`Instrument.debye_scherrer` (``PXCR``) or
      :meth:`Instrument.constant_wavelength_neutron` (``PNCR``), both
      Debye-Scherrer.
    * ``GSAS_PRM_PROFILE_SET_DEFAULTED`` — the bank offers more than one
      profile set and ``profile_set`` named none, so set 1 was read.

    A ``PNCR`` file differs in three places, each because a
    :class:`~rietx.schemas.instrument.NeutronSource` has one wavelength and
    no polarisation: a non-zero ``LAM2`` is refused, and ``POLA`` (which
    such files still write) and ``KRATIO`` are read and not applied, named
    in the ``ICONS`` row of ``GSAS_PRM_FIELD_DROPPED``.

    ``GSAS_PRM_GEOMETRY_ASSUMED`` matters more than a dropped zero.  ``Geometry.kind``
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

    # The profile type is asked before ICONS' values, because it is what
    # decides whether this file can be read at all: a type-1 PNCR file
    # hears about its type, not about a field of a record that would not
    # have been read either way.
    neutron = htype == _HTYPE_PNCR
    sets = _prcf_sets(records)
    # Set 1 by default, as GSAS-II's importer reads it, never "the lowest
    # stated": a file with no PRCF1 is not one GSAS-II reads either.
    chosen = 1 if profile_set is None else profile_set
    if chosen not in sets and (sets or profile_set is not None):
        asked = (f"profile_set={profile_set!r}" if profile_set is not None
                 else "no profile_set was named, so set 1 is the one read")
        raise ValueError(
            f"{p.name}: {asked}, and bank 1 states "
            f"profile set(s) {', '.join(map(str, sorted(sets))) or 'none'}")
    prof_type, coeffs = _read_prcf(records, p, chosen, sets.get(chosen))
    if prof_type != _PRCF_TYPE_3:
        what = _PRCF_TYPE_REFUSALS.get(prof_type)
        # The file may offer a type-3 set beside the one read (BT1_Cu311.inst
        # states types 1, 2 and 3), and a refusal that names it is one the
        # caller can act on.
        offered = [n for n, h in sorted(sets.items())
                   if h.function == _PRCF_TYPE_3 and n != chosen]
        other = (
            f"  This file also states a type-3 profile as set "
            f"{offered[0]}; read_gsas_prm(..., profile_set={offered[0]}) "
            f"reads it" if offered else "")
        if what is None:
            raise ValueError(
                f"{p.name}: unrecognised GSAS PRCF profile type "
                f"{prof_type!r} — only type 3 (pseudo-Voigt with "
                f"microstrain) is read.  Types "
                f"{', '.join(sorted(_PRCF_TYPE_REFUSALS))} are recognised "
                f"and refused, each for lacking a real fixture to derive "
                f"its coefficient layout from; this is not one of those "
                f"either, so what its coefficients mean is not established "
                f"at all.{other}")
        # Worded about *this file's* type and HTYPE, never about a fixture:
        # the PNCR refusal this replaced told a type-3 file that it carried
        # type 1, because it described the repository's one PNCR file rather
        # than the file in hand (issue #437).
        raise ValueError(
            f"{p.name}: HTYPE {htype} ({_HTYPES_READ[htype]}), and this "
            f"bank's profile is {what} (GSAS PRCF type {prof_type}) — only "
            f"type 3 is read, under PXCR and PNCR alike.  Each GSAS profile "
            f"function has its own, independently-defined coefficient "
            f"layout (type 3's 19 are not a superset of type {prof_type}'s "
            f"{len(coeffs)}), and this reader has no verified layout for "
            f"type {prof_type} to read this file's {len(coeffs)} "
            f"coefficient(s) by.  Reading them by position off type 3 would "
            f"be a guess, not a parser.{other}")

    icons = _read_icons(records, p, neutron=neutron)
    if neutron and icons.lam2:
        raise ValueError(
            f"{p.name}: HTYPE PNCR (constant-wavelength neutron) and ICONS "
            f"states a second wavelength, LAM2 = {icons.lam2!r}.  A neutron "
            f"source here is one monochromated wavelength (NeutronSource), "
            f"with no emission-line doublet to put a second one in, and a "
            f"λ/2 contaminant is a harmonic, which the format does not state "
            f"as a LAM2 — so what this field means in this file is not "
            f"established, and it is refused rather than dropped")

    if len(coeffs) < len(_PRCF_MAPPED):
        raise ValueError(
            f"{p.name}: this bank's PRCF{chosen} header declares a type-3 profile "
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

    instrument = _build_instrument(icons, (gu, gv, gw, lx, ly, sl, hl), p,
                                   neutron=neutron)

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
            f"KRATIO = {ratio} is carried as the second emission line's weight."
            if icons.lam2 else
            f"KRATIO = {ratio}, read and not applied (LAM2 states no second "
            f"line).")
        # A neutron file still writes POLA (HB-2A's says 0.990), and the
        # NeutronSource pins the polarisation term at 1, so the value is the
        # file's and is not carried — which is a drop, and says so.
        pola = blank if icons.polarization is None else icons.polarization
        pola_note = (
            f"POLA = {pola}, read and not applied (HTYPE PNCR is a neutron "
            f"source, and NeutronSource pins the polarisation term at 1). "
            if neutron else "")
        dropped = [
            ("ICONS", f"{pola_note}IPOLA (the polarization type) = "
                      f"{blank if icons.polarization_type is None else icons.polarization_type}, "
                      f"the refine flags and IDAMP = "
                      f"{blank if icons.damping is None else icons.damping} "
                      f"were not kept. {ratio_note}"),
        ]
        past_8 = (f" and {len(rest)} coefficient(s) past position "
                  f"{len(_PRCF_MAPPED)} = 0" if rest else "")
        dropped.append(
            ("PRCF", f"GP (position 4) = 0{past_8} were not kept. Positions "
                     f"1-3 and 5-6 map onto ProfileTCHZ and 7-8 "
                     f"(S/L, H/L) onto Geometry."))
        if any(name.endswith(("IRAD", "ITYP")) for name, _ in records):
            dropped.append(
                ("IRAD/ITYP", "read and not kept. The wavelength comes from "
                              "ICONS, and an angular range belongs to the "
                              "pattern."))
        for record, what in dropped:
            diagnostics.append(Diagnostic(
                level="info", code="GSAS_PRM_FIELD_DROPPED",
                message=f"{p.name}, {record}: {what}",
                where=[record]))
        if profile_set is None and len(sets) > 1:
            offered = ", ".join(f"set {n} (type {h.function})"
                                for n, h in sorted(sets.items()))
            diagnostics.append(Diagnostic(
                level="warning", code="GSAS_PRM_PROFILE_SET_DEFAULTED",
                message=(f"{p.name}: bank 1 offers {len(sets)} profile sets "
                         f"({offered}) and none was named, so set {chosen} "
                         f"was read."),
                where=[f"PRCF{chosen}"],
                suggestion=("Name the set with read_gsas_prm(..., "
                            "profile_set=N).")))

    if diagnostics is not None:
        why = (
            "HTYPE PNCR gave debye_scherrer, as "
            "Instrument.constant_wavelength_neutron builds it."
            if neutron else
            "HTYPE PXCR spans Bragg-Brentano and Debye-Scherrer, so "
            f"debye_scherrer was chosen (packing_fraction={PACKING_FRACTION:g}, a capillary "
            "offset pair).")
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS_PRM_GEOMETRY_ASSUMED",
            message=(f"{p.name}: the geometry was not read from the file, "
                     f"because a GSAS .prm states none. {why}"),
            where=["instrument.geometry.kind"],
            suggestion=("For a flat-plate calibration, set the geometry "
                        "yourself. Carry geometry.axial_sl and "
                        "geometry.axial_hl over first, because a fresh "
                        "Geometry has no axial divergence.")))
    return instrument


def _build_instrument(icons: GsasIcons,
                      coefficients: tuple[float, ...], p: Path, *,
                      neutron: bool = False) -> Instrument:
    """The ``Instrument`` this bank states, frozen, or a refusal naming the file.

    ``neutron`` (an ``HTYPE PNCR`` file) starts from
    :meth:`Instrument.constant_wavelength_neutron` at ``LAM1`` — a
    :class:`~rietx.schemas.instrument.NeutronSource`, one wavelength, the
    polarisation term pinned at 1, the profile box every preset builds — and
    maps the same eight ``PRCF`` coefficients onto it as a ``PXCR`` file,
    because the type-3 record is the same record under either radiation.

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
        if neutron:
            instrument = Instrument.constant_wavelength_neutron(
                wavelength=icons.lam1)
        else:
            instrument = Instrument.debye_scherrer(
                wavelength=icons.lam1, polarization=icons.polarization)
        if icons.lam2 and not neutron:
            # A second line's weight is relative to the first, which the
            # parameter table pins at 1 (EmissionLine) — so KRATIO, the
            # Kα2/Kα1 intensity ratio, is exactly the number this slot wants.
            # Reading it is what locating the field by column bought: the old
            # reader could not tell KRATIO from the polarization two fields
            # earlier, both conventionally 0.5, and refused every doublet
            # rather than guess (WP-1118).
            instrument.source.lines.append(EmissionLine(
                wavelength=icons.lam2,
                weight=Parameter(value=icons.ka2_ratio, min=0.0)))
        prof = instrument.profile
        prof.u.value = gu * _PRM_GAUSS_TO_DEG2
        prof.v.value = gv * _PRM_GAUSS_TO_DEG2
        # W's floor is the Γ_G² clamp (ProfileTCHZ): a W in [0, floor) is
        # raised to it, as the schema raises a stored one; a negative W is
        # still refused below
        w = gw * _PRM_GAUSS_TO_DEG2
        prof.w.value = _MIN_GAMMA_G2 if 0.0 <= w < _MIN_GAMMA_G2 else w
        prof.x.value = lx / 1e2
        prof.y.value = ly / 1e2
        _refuse_negative_lorentzian(prof.x.value, prof.y.value, p)
        instrument.geometry.axial_sl.value = sl
        instrument.geometry.axial_hl.value = hl
    except ValidationError as exc:
        raise ValueError(
            f"{p.name}: this bank states a value outside the range this "
            f"package's Instrument holds — ICONS LAM1 {icons.lam1}, LAM2 "
            f"{icons.lam2}, POLA {icons.polarization}, KRATIO "
            f"{icons.ka2_ratio}; PRCF converted to U {gu * _PRM_GAUSS_TO_DEG2}, V "
            f"{gv * _PRM_GAUSS_TO_DEG2}, W {gw * _PRM_GAUSS_TO_DEG2}, X {lx / 1e2}, Y {ly / 1e2}, S/L "
            f"{sl}, H/L {hl}.  Read by column every one of those is the "
            f"file's own number rather than a field landing in the wrong "
            f"slot, so the calibration is refused here, naming the file, "
            f"rather than arriving later as a schema error that names none: "
            f"{exc}") from exc
    for param in _iter_parameters(instrument):
        param.vary = False
    return instrument


def _check_htype(htype: str, p: Path) -> None:
    """Pass ``PXCR`` and ``PNCR``; refuse any other ``HTYPE`` **by name**.

    Passing is not reading: a ``PNCR`` or ``PXCR`` file is read only if its
    ``PRCF`` type is, which ``read_gsas_prm`` asks next.
    """
    if htype in _HTYPES_READ:
        return
    what = _HTYPE_REFUSALS.get(htype)
    if what is not None:
        raise ValueError(f"{p.name}: HTYPE {htype} is {what}")
    raise ValueError(
        f"{p.name}: unrecognised GSAS HTYPE {htype!r} — only "
        f"{' and '.join(f'{h} ({what})' for h, what in _HTYPES_READ.items())}"
        f" are read.  "
        f"{', '.join(sorted(_HTYPE_REFUSALS))} "
        f"{'is' if len(_HTYPE_REFUSALS) == 1 else 'are'} recognised and "
        f"refused by name; this is not one of those either, so what this "
        f"file's HTYPE means is not established at all")


def _read_icons(records: list[tuple[str, str]], p: Path, *,
                neutron: bool = False) -> GsasIcons:
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

    ``neutron`` (``HTYPE PNCR``) waives the two polarisation checks: a
    :class:`~rietx.schemas.instrument.NeutronSource` pins its polarisation
    term at 1, so neither a blank ``POLA`` nor an ``IPOLA`` convention can
    change the instrument, and refusing on one would refuse a file for a
    reason that is not true of it.
    """
    payloads = _payloads(records, "ICONS")
    if len(payloads) != 1:
        raise ValueError(
            f"{p.name}: expected exactly one ICONS record for bank 1, found "
            f"{len(payloads)} — a bank declaring its constants more than once "
            f"(or not at all) is ambiguous, not a single instrument")
    icons = read_icons(payloads[0], required=(
        ("lam1",) if neutron else ("lam1", "polarization")))

    if not icons.lam1:
        raise ValueError(
            f"{p.name}: bank 1's ICONS record states no primary wavelength "
            f"(LAM1, columns 12-22) — the field is blank or zero, and an "
            f"instrument file without a wavelength describes no instrument")
    if icons.polarization is None and not neutron:
        raise ValueError(
            f"{p.name}: bank 1's ICONS record states no polarization (POLA, "
            f"columns 52-62) — the field is blank.  Every "
            f"real file in the corpus states it, and falling back on "
            f"Instrument.debye_scherrer's {DEBYE_SCHERRER_POLARIZATION:g} would put this package's "
            f"number into an instrument the caller will read as the file's")
    if icons.zero:
        raise ValueError(
            f"{p.name}: ICONS field ZERO is {icons.zero!r}, not 0 — "
            f"its unit is disputed between two GSAS-adjacent conventions a "
            f"factor of 100 apart (io/recipe.py's Zero handling) and no "
            f"real file in this corpus has a non-zero value to settle it "
            f"against, so a non-zero one here is refused rather than mapped "
            f"onto instrument.zero_shift on either guess")
    if icons.polarization_type and not neutron:
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


def _prcf_sets(records: list[tuple[str, str]]) -> dict[int, GsasPrcfHeader]:
    """Every profile set bank 1 states, as {set number: its first header}.

    A ``.prm`` may offer several profile functions for one bank, each under its
    own header ``PRCFn`` (``BT1_Cu311.inst`` states types 1, 2 and 3 as sets 1,
    2 and 3, with the same ``GU GV GW`` in each).  GSAS-II's importer reads set
    1 alone (``GSASIIfiles.SetPowderInstParms``).  A type this file leaves blank
    is ``None`` here and refused by :func:`_read_prcf` if that set is read.

    Each header is read **once**, here: an optional field that overflowed is
    reported by :func:`~rietx.io.projects.gsas._naming_the_file` once per read,
    so a second read of the same header would report it twice.
    """
    sets: dict[int, GsasPrcfHeader] = {}
    for name, payload in records:
        if (len(name) == 5 and name.startswith("PRCF")
                and name[4].isdecimal() and int(name[4]) not in sets):
            sets[int(name[4])] = read_prcf_header(payload,
                                                  required=("function",))
    return sets


def _read_prcf(records: list[tuple[str, str]], p: Path, profile_set: int,
               header: GsasPrcfHeader | None
               ) -> tuple[int | None, list[float]]:
    """Read bank 1's ``PRCFn`` block for set ``n``: (profile type, coefficients).

    The **header** is a fixed-format record like every other, read by column
    through :func:`~rietx.io.projects.gsas.read_prcf_header`.  The block is a
    **counted** layout: the header states how many numeric coefficients follow
    across the ``PRCFn1``…``PRCFnm`` continuation records, and that count — not
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
    key = f"PRCF{profile_set}"
    headers = _payloads(records, key)
    if len(headers) != 1:
        raise ValueError(
            f"{p.name}: expected exactly one {key} header for bank 1, found "
            f"{len(headers)} — a bank declaring one profile set more than "
            f"once is ambiguous about which applies, not a richer instrument")
    assert header is not None    # one header under ``key``, so _prcf_sets read it
    prof_type, ncoef = header.function, header.n_coefficients
    if prof_type is None:
        raise ValueError(
            f"{p.name}: this bank's {key} header states no profile function "
            f"type (columns 12-17 are blank) — the coefficients below it "
            f"cannot be named without one, because each GSAS function has its "
            f"own order and type 2's fourth is LX where type 3's is GP")
    labels = _prcf_labels(prof_type)

    coeffs: list[float] = []
    for name, payload in records:
        if not (name.startswith(key) and name[5:].isdigit()):
            continue
        for tok in payload.split():
            if tok.upper() in labels:
                continue
            try:
                coeffs.append(float(tok))
            except ValueError:
                raise ValueError(
                    f"{p.name}: {key}1..{key}n holds an unrecognised token "
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
            f"{p.name}: {key} declares {ncoef} coefficients but only "
            f"{len(coeffs)} were found across its {key}1..{key}n "
            f"continuation lines before the record ended — the count in "
            f"the header, not the number of lines present, is what this "
            f"reader trusts, so a short file is refused rather than padded")
    return prof_type, coeffs[:ncoef]


# ---------------------------------------------------------------------------
# GSAS-I .prm — write_gsas_prm, the inverse of read_gsas_prm
# ---------------------------------------------------------------------------

#: The ``PRCF`` continuation records are ``4E15.6``, so a coefficient gets
#: fifteen columns where a ``.EXP``'s cell edge gets ten.  Both go through
#: :func:`~rietx.io.projects.gsas.write_field`, which takes the width for
#: exactly this reason.
_PRM_COEFFICIENT_COLUMNS = 15
_PRM_PER_RECORD = 4

#: One of those fifteen columns is **reserved as a separator**, so a value is
#: written into fourteen and right-justified into fifteen.  A ``.EXP``'s fields
#: are read back by column and may fill themselves; a ``.prm``'s continuation
#: records are the one place :func:`_read_prcf` splits on whitespace instead
#: (its docstring says why — GSAS's own editor prints labels inside the
#: fields), and :func:`~rietx.io.projects.gsas.write_field` right-justifies, so
#: a value whose shortest exact decimal is fifteen characters long abuts its
#: neighbour and the pair reads as one unparseable token.  Fourteen columns
#: still hold more digits than any esd a calibration reports, and the leading
#: blank is what a real ``4E15.6`` record has anyway.  Un-reserved, a converged
#: ``GU`` of 43.710000000000996 wrote a file this package's own reader refused
#: (WP-1118, the review pass on this writer).
_PRM_COEFFICIENT_DIGITS = _PRM_COEFFICIENT_COLUMNS - 1

#: What this writer states on the two file-wide records.  ``PXCR`` is the one
#: :func:`read_gsas_prm` reads, and type 3 the one profile function it maps, so
#: writing anything else would produce a file this package refuses.
_PRM_BANK = 1
_PRM_CUTOFF = 0.001

#: ``S/L`` and ``H/L`` are dimensionless and cross unconverted; the rest are
#: the inverse of :func:`read_gsas_prm`'s own centidegree division, written
#: here as the multiplication it is so the two cannot drift apart.
_PRM_CENTIDEG_SQUARED = 1e4
_PRM_CENTIDEG = 1e2
#: ``GU GV GW`` are the coefficients of a Gaussian *variance* in centidegrees²;
#: ``profile.u/v/w`` those of the Gaussian FWHM² in degrees² (Γ² = 8 ln 2 · σ²).
#: What a ``GU`` is multiplied by to give a ``u`` (the reader), and what a ``u``
#: is divided by to give a ``GU`` (the writer).
_PRM_GAUSS_TO_DEG2 = GAUSSIAN_VARIANCE_TO_FWHM_SQUARED / _PRM_CENTIDEG_SQUARED


def from_instrument(instrument: Instrument, *, header: str = "",
                    diagnostics: list[Diagnostic] | None = None) -> str:
    """Serialise ``instrument`` as GSAS-I ``.prm`` text — :func:`read_gsas_prm`'s
    inverse, and the fourth of this package's foreign-format writers.

    Named for the shape the three in :mod:`rietx.io.projects` use
    (``from_structure``) rather than for this module's own
    ``save_instrument_profile``: what varies between the four writers is the
    format, not the verb.  A ``.prm`` carries a machine and no model, which is
    why it lives here and stays out of the project registry (``io/CLAUDE.md``
    § Project readers) — but the card grammar is GSAS's, so the fields and
    records are written by :func:`~rietx.io.projects.gsas.write_field` and
    :func:`~rietx.io.projects.gsas.write_record`, the two functions the ``.EXP``
    writer uses.  Two writers spelling one record two ways is how the two
    *readers* came to disagree about ``ICONS``.

    What crosses is exactly what :func:`read_gsas_prm` reads back: the primary
    wavelength and, where the source states a second line, its wavelength and
    its weight as ``KRATIO``; the polarization; ``profile.u/v/w`` as ``GU/GV/GW``
    and ``profile.x/y`` as ``LX/LY``, multiplied back into GSAS's centidegrees;
    and ``geometry.axial_sl``/``axial_hl`` as ``S/L`` and ``H/L``, which are
    dimensionless and cross unconverted.  ``GP`` and the coefficients past
    position 8 are written at 0, the identity the reader requires them at.

    **Every parameter's ``vary`` is dropped, and that is not a loss.**  An
    instrument-parameter file is a beamline calibration rather than a starting
    guess, which is why :func:`read_gsas_prm` and
    :func:`load_instrument_profile` both return everything frozen; the
    ``PRCF`` header's flag columns are left blank for the same reason, which is
    what a real calibration file does.  So unlike the three structure writers,
    the refine flags are deliberately *not* the payload here.

    **A non-zero ``zero_shift`` is refused.**  ``ICONS``' ``ZERO`` field is the
    one number here whose unit this package has not established: GSAS-I's
    constant-wavelength pattern axis is centidegrees (``io/formats/gsas.py``
    measured that on real ``CONS`` banks), which would make ``ZERO``
    centidegrees too, but no file in this corpus states a non-zero one to check
    it against and :func:`read_gsas_prm` refuses one on the way in for exactly
    that reason.  Writing a guess would produce a file this package will not
    read back, and a ``ZERO`` wrong by 100× puts every peak in the wrong place.
    ``io/CLAUDE.md``'s own rule settles which way it goes: magnitude decides
    drop against refuse, so a zero crosses silently and a non-zero raises.  A
    zero shift is per-mount anyway — set it to 0 and let the receiving program
    refine it.

    Three more refusals, each naming what ``ICONS`` cannot state.  A neutron
    source, which would be ``HTYPE PNCR`` — :func:`read_gsas_prm` reads a
    type-3 one, but what its ``POLA`` and ``KRATIO`` should say for a source
    with neither is spelled by one real file only, so it is not written.  More than two emission lines, ``ICONS`` holding ``LAM1`` and
    ``LAM2`` and nothing further.  And a second line whose weight is outside the
    ``0 < w <= 2`` a ``KRATIO`` means, which is the bound the reader checks.

    ``diagnostics`` collects one row, ``GSAS_PRM_FIELD_NOT_WRITTEN``, naming
    what this instrument carries that the format cannot state.  Its first
    clause is always the geometry: a ``.prm`` states none at all, so the kind,
    the sample displacement and transparency, and the specimen absorption stay
    behind and reading the file back gives ``debye_scherrer`` — the mirror of
    the reader's own ``GSAS_PRM_GEOMETRY_ASSUMED``.  A true-Voigt profile is
    named there too rather than refused: GSAS's type 3 is a pseudo-Voigt and
    has no Voigt option, the widths are the content either way, and what
    changes is the target's own shape model.
    """
    from ..schemas.instrument import NeutronSource
    from .projects.gsas import write_field, write_record

    if isinstance(instrument.source, NeutronSource):
        raise ValueError(
            "a GSAS-I .prm written by this package states HTYPE PXCR, "
            "constant-wavelength X-ray.  A constant-wavelength neutron source "
            "would be HTYPE PNCR, which read_gsas_prm reads (profile type 3) "
            "but this writer does not write: what a PNCR file's POLA and "
            "KRATIO fields should hold for a source that has neither is "
            "spelled only by the one real file this package holds, which is "
            "a reading, not a convention to write by")

    source = instrument.source
    if len(source.lines) > 2:
        raise ValueError(
            f"this source states {len(source.lines)} emission lines and an "
            f"ICONS record holds two, LAM1 and LAM2.  Dropping the rest would "
            f"hand back an instrument with a different spectrum under a file "
            f"that looks complete")
    if instrument.zero_shift.value != 0.0:
        raise ValueError(
            f"zero_shift is {instrument.zero_shift.value!r}, and ICONS' ZERO "
            f"field is the one number here whose unit this package has not "
            f"established — GSAS-I's CW pattern axis is centidegrees, which "
            f"would make ZERO centidegrees, but no file in this corpus states "
            f"a non-zero one to check that against and read_gsas_prm refuses "
            f"one on the way in for the same reason.  A ZERO wrong by 100x "
            f"puts every peak in the wrong place.  A zero shift belongs to the "
            f"mount rather than to the goniometer, so set it to 0 and let the "
            f"receiving program refine it")
    second = source.lines[1] if len(source.lines) > 1 else None
    if second is not None and not 0.0 < second.weight.value <= 2.0:
        raise ValueError(
            f"the second emission line's weight is {second.weight.value!r}, "
            f"and it is written as ICONS' KRATIO — the Ka2/Ka1 intensity "
            f"ratio, which read_gsas_prm holds to 0 < w <= 2 (a sealed tube is "
            f"about 0.5).  A value outside that is refused rather than written "
            f"into a field it would not mean")

    # A calibration's numbers are well inside fourteen significant characters,
    # so this list is ordinarily empty — but the channel is what makes
    # `write_field` refuse a non-finite value rather than writing a token GSAS
    # cannot parse, and a value multiplied into centidegrees carries the
    # product's own float noise, which is what spends the columns.
    narrowed: list[tuple[str, float, float]] = []

    def field(value: float, what: str, width: int = _PRM_COEFFICIENT_COLUMNS) -> str:
        return write_field(value, width, what=what, narrowed=narrowed)

    def coefficient(value: float, what: str) -> str:
        """One ``PRCF`` coefficient, in fourteen columns of its fifteen.

        See :data:`_PRM_COEFFICIENT_DIGITS`: the spare column is the separator
        the reader's whitespace split needs.
        """
        return field(value, what, _PRM_COEFFICIENT_DIGITS).rjust(
            _PRM_COEFFICIENT_COLUMNS)

    profile, geometry = instrument.profile, instrument.geometry
    # The inverse of read_gsas_prm's conversion, written as the multiplication
    # it is: GU/GV/GW are a Gaussian variance in centidegrees squared (÷ 8 ln 2
    # from the FWHM² this package holds) and LX/LY centidegrees, while
    # S/L and H/L are ratios.  GP (position 4) and everything past position 8
    # are 0, which is the identity the reader requires them at.
    coefficients = [
        profile.u.value / _PRM_GAUSS_TO_DEG2,
        profile.v.value / _PRM_GAUSS_TO_DEG2,
        profile.w.value / _PRM_GAUSS_TO_DEG2,
        0.0,
        profile.x.value * _PRM_CENTIDEG,
        profile.y.value * _PRM_CENTIDEG,
        geometry.axial_sl.value,
        geometry.axial_hl.value,
    ]
    names = CW_PROFILE_COEFFICIENTS[_PRCF_TYPE_3][:len(coefficients)]

    cards = [
        write_record("INS   BANK  ", f"{_PRM_BANK:5d}"),
        write_record("INS   HTYPE ", f"  {_HTYPE_PXCR}"),
        write_record("INS  1 ICONS",
                     field(source.lines[0].wavelength.value, "source.lines.0.wavelength", 10)
                     + field(second.wavelength.value if second else 0.0,
                             "source.lines.1.wavelength", 10)
                     + field(0.0, "zero_shift", 10)
                     # the three refine flags sit at 32-35 and IDAMP at 39: a
                     # calibration has refined nothing, so both stay blank
                     + " " * 10
                     + field(source.polarization.value, "source.polarization", 10)
                     + f"{0:5d}"
                     + field(second.weight.value if second else 0.0,
                             "source.lines.1.weight", 10)),
    ]
    if header:
        cards.append(write_record("INS  1I HEAD", f"  {header}"))
    cards.append(write_record(
        "INS  1PRCF1 ",
        f"{_PRCF_TYPE_3:5d}{len(coefficients):5d}" + field(_PRM_CUTOFF, "cutoff", 10)))
    for i in range(0, len(coefficients), _PRM_PER_RECORD):
        chunk = coefficients[i:i + _PRM_PER_RECORD]
        cards.append(write_record(
            f"INS  1PRCF1{i // _PRM_PER_RECORD + 1}",
            "".join(coefficient(v, f"PRCF {name}")
                    for v, name in zip(chunk, names[i:i + _PRM_PER_RECORD],
                                       strict=True))))

    if diagnostics is not None:
        if narrowed:
            # The twin of the `.EXP` writer's GSAS_EXP_VALUE_NARROWED, and owed
            # for the same reason: this writer collected `narrowed` from the
            # first and read it nowhere, so a value that did not fit its field
            # crossed in silence while its sibling reported one (WP-1118, the
            # 5th session's review pass).  A PRCF coefficient multiplied into
            # centidegrees carries the product's float noise, so a converged
            # calibration reaches this routinely.
            what, value, written = max(
                narrowed,
                key=lambda row: abs(row[2] - row[1]) / (abs(row[1]) or 1.0))
            diagnostics.append(Diagnostic(
                level="info", code="GSAS_PRM_VALUE_NARROWED",
                message=(
                    f"{len(narrowed)} value(s) need more characters than a "
                    f".prm's fixed columns hold and were written to what fits. "
                    f"The largest change is {what} {value!r} -> {written!r}."),
                where=[row[0] for row in narrowed]))
        clauses = [
            "The geometry, the specimen displacement and transparency and "
            "the specimen absorption were not written, so reading this file "
            "back gives debye_scherrer. S/L and H/L are the two geometry "
            "numbers that do cross."]
        if profile.shape != "tchz_pv":
            clauses.append(
                f"The peak shape is {profile.shape!r}. PRCF type 3 cannot "
                f"state it, so the widths were written and the shape model "
                f"was not.")
        if instrument.extra_components:
            clauses.append(
                f"{len(instrument.extra_components)} extra component(s) were "
                f"not written.")
        if any(p.vary for p in _iter_parameters(instrument)):
            clauses.append(
                "The PRCF header's flag columns are blank, so every refine "
                "flag reads back as vary=False.")
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS_PRM_FIELD_NOT_WRITTEN",
            message="The .prm omits part of the instrument. " + " ".join(clauses),
            where=["instrument.geometry"]))
    return "\r\n".join(cards) + "\r\n"


def write_gsas_prm(instrument: Instrument, path: str | Path, *,
                   header: str = "",
                   diagnostics: list[Diagnostic] | None = None) -> None:
    """Write ``instrument`` to ``path`` as a GSAS-I ``.prm``.

    ``latin-1``, the encoding :func:`read_gsas_prm` decodes one with: the
    ``I HEAD`` record holds whatever the experimenter typed.  See
    :func:`from_instrument` for what carries and what does not.
    """
    from ..schemas.pattern import require_two_theta

    require_two_theta(None, "write_gsas_prm()", instrument=instrument)
    Path(path).write_bytes(
        from_instrument(instrument, header=header,
                        diagnostics=diagnostics).encode("latin-1"))


# ---------------------------------------------------------------------------
# GSAS-II ``.instprm``
# ---------------------------------------------------------------------------
#
# The GSAS-I ``.prm`` pair above and this one are the same kind of object under
# two programs' grammars, so they live together and stay out of the project
# registry for the reason ``io/CLAUDE.md`` § Project readers gives: an
# instrument file carries a machine and no model.  What differs is that an
# ``.instprm`` is a *token* format — ``item:value`` lines, no columns — so none
# of the field-budget rules the ``.EXP``/``.prm`` writers obey apply, and a
# value's own ``repr`` crosses exactly.

#: GSAS-II floors the axial-divergence sum at this when it evaluates a profile
#: (``GSASIIpwd.SetInstParms``: ``max(instDict['SH/L'], 0.002)``), so a smaller
#: one is written faithfully and still read as 0.002 by the program the file is
#: for.  Named here because the writer reports it, which is the only thing this
#: package can do about another program's floor.
INSTPRM_SHL_FLOOR = 0.002

#: What a bank's ``Polariz.`` means, by histogram type.  GSAS-II applies the
#: polarization factor only where the type carries ``XC`` or ``XB``
#: (``GSASIIstrMath.GetIntensityCorr``), so on a ``PNC`` bank the field is inert
#: in GSAS-II exactly as it is here: :class:`NeutronSource` pins K = 1, the bare
#: Lorentz factor.  Both of the corpus's neutron files state ``0.0``.
_INSTPRM_NEUTRON_POLARIZATION = "0.0"


def _instprm_bank(banks: tuple, bank: int | None, p: Path):
    """The one bank to read, or a refusal naming what the file holds.

    A multi-bank file is a **selection**, following ``read_pattern``'s ``scan=``
    (``io/CLAUDE.md`` § Options): reading the first of several would pick a
    detector rather than read one.  GSAS-II's own reader takes the
    lowest-numbered bank silently; here that is a refusal naming the numbers,
    because the caller knows which detector their pattern came from and this
    reader does not.

    Duplicate numbers are refused rather than resolved, and the corpus is why:
    three of its twelve files write ``#Bank 6`` twice, so "bank 6" names two
    different calibrations in one file.
    """
    if not banks:
        raise ValueError(
            f"{p.name}: the header is there and no bank follows it, so this "
            f"file states no instrument")
    if bank is None:
        if len(banks) > 1:
            numbers = ", ".join(str(b.number) for b in banks)
            raise ValueError(
                f"{p.name}: states {len(banks)} banks ({numbers}) and an "
                f"Instrument describes one.  Name the one you measured with, "
                f"read_gsas2_instprm(..., bank=N) — reading the first would "
                f"pick a detector rather than read one")
        return banks[0]
    matched = [b for b in banks if b.number == bank]
    if len(matched) > 1:
        raise ValueError(
            f"{p.name}: states bank {bank} {len(matched)} times, so the number "
            f"names two calibrations here rather than one.  Three of the "
            f"twelve files in GSAS-II's own tutorial corpus write one bank "
            f"twice, so this is the format's normal accident rather than a "
            f"corrupt file")
    if not matched:
        have = ", ".join(str(b.number) for b in banks)
        raise ValueError(
            f"{p.name}: asked for bank {bank} and the file states {have}")
    return matched[0]


def _instprm_float(items: dict[str, str], key: str, p: Path) -> float | None:
    """One item as a number, or ``None`` when the file does not state it."""
    raw = items.get(key)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"{p.name}: {key} is {raw!r}, which is not a number.  GSAS-II "
            f"floats every item it can and leaves the rest as text, so a "
            f"coefficient that does not float is a damaged file rather than a "
            f"convention this reader has not met") from None


def _instprm_width(profile, letter: str, attr: str, value: float,
                   p: Path) -> None:
    """One profile coefficient, converted out of centidegrees and bounded.

    Two rules, both :mod:`~rietx.io.recipe`'s and both earned there rather than
    here (``_refuse_negative_width``, ``_widen``).  A **negative** width (a
    term :data:`TCHZ_BOUNDS` bounds at or above zero, W and X) is refused by
    name, so a fit never answers from a model the file does not describe.  It
    is the ordinary case rather than a corner —
    GSAS-II bounds none of U V W X Y Z, and **two of the four**
    constant-wavelength files in its own tutorial corpus converged to a
    negative ``X``.  A negative U, V or Y is read, those three having no
    floor of their own.  And a value outside this package's default box **widens**
    the box rather than being clipped, because the box is a lab-pattern seed
    and the file is the caller's claim.

    Not shared with :mod:`~rietx.io.recipe`'s pair: they raise that reader's own
    exception type and name a recipe's JSON path, while these name a file and a
    GSAS-II letter.  The rule is one and the message is each format's own.
    """
    param = getattr(profile, attr)
    factor = instprm_factor(letter)
    assert factor is not None  # every letter here is in CW_CENTIDEGREE_POWER
    degrees = value / factor
    if TCHZ_BOUNDS[attr][0] >= 0.0 and degrees < 0.0:
        raise ValueError(
            f"{p.name}: {letter} = {value:g} converts to "
            f"instrument.profile.{attr} = {degrees:g}, and this package's "
            f"{'Gaussian FWHM²' if attr == 'w' else 'Lorentzian FWHM'} term "
            f"is bounded below at zero — a width that is negative is not a "
            f"shape.  GSAS-II bounds none of U V W X Y Z, so a calibration "
            f"saved from a converged fit can carry one.  Refine {attr} from "
            f"this package's own zero instead")
    if attr == "w":
        # W's floor is the Γ_G² clamp (ProfileTCHZ): a W in [0, floor) is
        # raised to it, as the schema raises a stored one
        degrees = max(degrees, _MIN_GAMMA_G2)
    if degrees < param.min:
        # Unreachable while u, v and y are bounded at the ceiling's mirror
        # image and w and x refuse a negative value above; kept for a file
        # stating a value past the 2θ axis.
        param.min = degrees - abs(degrees) - 1.0
    if degrees > param.max:
        param.max = degrees + abs(degrees) + 1.0
    param.value = degrees


def _refuse_negative_lorentzian(x: float, y: float, p: Path) -> None:
    """A calibration whose Lorentzian width goes negative below 2θ = 180°.

    Y has no floor of its own since 2026-10-23 (WP-2002), so a negative Y is
    read where X carries the width X/cosθ + Y·tanθ over it.  A calibration is
    applied to a pattern this reader has not seen, so the check runs to the
    end of the 2θ axis.  Past the crossing GSAS-II clamps the width at a
    floor, this package has no such clamp, and a negative Lorentzian width is
    not a peak shape.  :mod:`~rietx.io.recipe` makes the same check against
    its own fitted range.
    """
    edge = lorentzian_negative_above(x, y)
    if edge >= 180.0:
        return
    raise ValueError(
        f"{p.name}: converts to instrument.profile.x = {x:g} and "
        f"instrument.profile.y = {y:g}, whose Lorentzian FWHM X/cosθ + Y·tanθ "
        f"is negative above 2θ = {edge:.3f}°.  GSAS-II clamps that width at a "
        f"floor and this package has no such clamp, so the calibration is "
        f"refused: refine X and Y from this package's own start instead")


def _instprm_instrument(items: dict[str, str], p: Path,
                        diagnostics: list[Diagnostic] | None) -> Instrument:
    """The ``Instrument`` one bank states, frozen, or a refusal naming the file.

    Every schema object is built inside the one guard below, so a value outside
    this package's ranges is refused **here**, naming the file, rather than
    arriving as a pydantic error naming a ``Parameter`` (``io/CLAUDE.md``
    § Project readers).
    """
    read: list[str] = []

    def number(key: str) -> float | None:
        value = _instprm_float(items, key, p)
        if value is not None:
            read.append(key)
        return value

    kind = (items.get("Type") or "").strip()
    read.append("Type")
    if kind not in CW_TYPES:
        what = HISTOGRAM_TYPES.get(kind)
        raise ValueError(
            f"{p.name}: states Type {kind!r}"
            + (f", {what}" if what else "")
            + f", and this reader takes the constant-wavelength types "
              f"({', '.join(CW_TYPES)}) and the time-of-flight one (PNT).  An "
              f"energy-dispersive bank puts a quantity on the x axis that "
              f"PatternData has no field for")

    for key in ("Z", "Azimuth"):
        value = number(key)
        if value:
            raise ValueError(
                f"{p.name}: states {key} = {value:g}, and this package has no "
                + ("constant Lorentzian term: ProfileTCHZ is u, v, w, x, y "
                   "exactly, so Z has nowhere to land.  Z is zero in all 95 "
                   "constant-wavelength histograms of GSAS-II's own tutorial "
                   "corpus, which is why it is refused here rather than "
                   "carried"
                   if key == "Z" else
                   "azimuth: the polarization factor this package applies is "
                   "the in-plane one, K + (1-K)cos^2(2th), and GSAS-II mixes "
                   "the two polarization components at a non-zero azimuth.  "
                   "Reading Polariz. as K would not then mean what the file "
                   "states"))

    lam, lam1, lam2 = number("Lam"), number("Lam1"), number("Lam2")
    neutron = kind == "PNC"
    if lam is None and lam1 is None:
        raise ValueError(
            f"{p.name}: states neither Lam nor Lam1, and a calibration "
            f"without a wavelength describes no instrument")
    if neutron and (lam1 is not None or lam2 is not None):
        raise ValueError(
            f"{p.name}: is a PNC (constant-wavelength neutron) bank stating "
            f"the Lam1/Lam2 pair a sealed X-ray tube's doublet uses.  A "
            f"monochromator selects one wavelength, so NeutronSource holds "
            f"one, and which of the two this file means is the caller's to "
            f"say rather than this reader's to pick")
    ratio = number("I(L2)/I(L1)")
    if lam2 is not None and ratio is None:
        raise ValueError(
            f"{p.name}: states the Lam2 line and no I(L2)/I(L1), so the "
            f"second line's weight is unstated.  A doublet without its "
            f"intensity ratio is an incomplete emission profile, and the "
            f"conventional 0.5 is this reader's guess rather than the file's "
            f"statement")
    # Read for an X-ray bank and left unread for a neutron one, so the reports
    # below name it: GSAS-II applies the factor only to an XC or XB type.
    polarization = _instprm_float(items, "Polariz.", p)
    if polarization is not None and not neutron:
        read.append("Polariz.")

    diff_type = (items.get("Diff-type") or "").strip()
    if diff_type:
        read.append("Diff-type")
        if diff_type not in INSTPRM_DIFF_TYPES:
            raise ValueError(
                f"{p.name}: states Diff-type {diff_type!r} and GSAS-II names "
                f"two, {' and '.join(INSTPRM_DIFF_TYPES)}")
        geometry_kind = INSTPRM_DIFF_TYPES[diff_type]
    else:
        geometry_kind = "bragg_brentano" if lam2 is not None else "debye_scherrer"

    radius = _instprm_float(items, "Gonio.radius", p)
    if radius is not None:
        read.append("Gonio.radius")

    try:
        source: Source | NeutronSource
        if neutron:
            source = NeutronSource(wavelength=Parameter(value=lam, unit="A"))
        else:
            lines = [EmissionLine(
                wavelength=Parameter(value=lam if lam is not None else lam1,
                                     unit="A"))]
            if lam2 is not None:
                lines.append(EmissionLine(
                    wavelength=Parameter(value=lam2, unit="A"),
                    weight=Parameter(value=ratio, min=0.0)))
            source = Source(
                lines=lines,
                polarization=Parameter(
                    value=(DEBYE_SCHERRER_POLARIZATION if polarization is None
                           else polarization),
                    min=0.0, max=1.0))

        profile = ProfileTCHZ()
        for letter, attr in (("U", "u"), ("V", "v"), ("W", "w"),
                             ("X", "x"), ("Y", "y")):
            value = number(letter)
            if value is not None:
                _instprm_width(profile, letter, attr, value, p)
        _refuse_negative_lorentzian(profile.x.value, profile.y.value, p)

        geometry = Geometry(kind=geometry_kind, goniometer_radius_mm=radius)
        shl = number("SH/L")
        if shl:
            half = 0.5 * shl
            geometry.axial_sl = Parameter(value=half, min=0.0)
            geometry.axial_hl = Parameter(value=half, min=0.0)

        instrument = Instrument(source=source, geometry=geometry,
                                profile=profile)
        zero = number("Zero")
        if zero:
            instrument.zero_shift.value = zero
    except ValidationError as exc:
        raise ValueError(
            f"{p.name}: this bank states a value outside the range this "
            f"package's Instrument holds, so the calibration is refused here, "
            f"naming the file, rather than arriving later as a schema error "
            f"that names none: {exc}") from exc

    for param in _iter_parameters(instrument):
        param.vary = False

    if diagnostics is not None:
        _instprm_reports(items, read, instrument, neutron, bool(diff_type),
                         lam2 is not None, diagnostics)
    return instrument


def _instprm_reports(items: dict[str, str], read: list[str],
                     instrument: Instrument, neutron: bool, stated: bool,
                     doublet: bool, diagnostics: list[Diagnostic]) -> None:
    """What this read assumed, and what of the file it did not carry."""
    geometry = instrument.geometry
    # An item the format declares and this file omits: GSAS-II's own header
    # says "do not add/delete items", so a missing one is the file breaking
    # that rule rather than a convention.  Reported rather than refused, and
    # reported because the alternative is a silence becoming a number — the
    # value used is this package's default, and a writer would spell it out.
    declared = INSTPRM_CW_DOUBLET if doublet else INSTPRM_CW_SINGLE
    skip = {"Bank"} | ({"Polariz."} if neutron else set())
    # ``Lam`` and ``Lam1`` are two spellings of one item, so a file stating
    # either is not a file missing the other.  Un-skipped, a ``Lam1`` with no
    # ``Lam2`` reported "this file states no Lam, so that came back at this
    # package's own default" about a wavelength read from the file.
    if "Lam" in items:
        skip.add("Lam1")
    elif "Lam1" in items:
        skip.add("Lam")
    absent = [k for k in declared if k not in items and k not in skip]
    if absent:
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS2_INSTPRM_VALUE_DEFAULTED",
            message=(
                f"This file states no {', '.join(absent)}, so "
                f"{'those came' if len(absent) > 1 else 'that came'} back at "
                f"this package's own default."),
            where=["instrument.profile"]))
    if geometry.axial_sl.value:
        half = geometry.axial_sl.value
        diagnostics.append(Diagnostic(
            level="info", code="GSAS2_INSTPRM_CONVENTION_ASSUMED",
            message=(
                f"SH/L = {2.0 * half:g} is GSAS-II's combined (S+H)/L. It was "
                f"split evenly into axial_sl = axial_hl = {half:g}."),
            where=["instrument.geometry.axial_sl",
                   "instrument.geometry.axial_hl"],
            value=half))
    if not stated:
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS2_INSTPRM_GEOMETRY_ASSUMED",
            message=(
                f"This file states no Diff-type, so its geometry was not read "
                f"from the file. It came back {geometry.kind}, GSAS-II's own "
                f"fallback."),
            where=["instrument.geometry.kind"],
            suggestion=("Set geometry.kind if you know the diffractometer. "
                        "Carry geometry.axial_sl and axial_hl over first, "
                        "because a fresh Geometry starts at 0 for both.")))
    not_read = [k for k in items if k not in read]
    if not_read:
        why = {
            "Bank": "the bank number",
            "Polariz.": ("inert on a neutron bank, since GSAS-II applies it "
                         "to an XC or XB type only and NeutronSource pins "
                         "K = 1"),
            "InstrName": "a name",
            "Diff-type": "not one of the two sample types GSAS-II names",
        }
        clauses = [f"{k} ({why[k]})" if k in why else k for k in not_read]
        diagnostics.append(Diagnostic(
            level="info", code="GSAS2_INSTPRM_FIELD_NOT_READ",
            message=("This file states items the Instrument has no place "
                     "for: " + ", ".join(clauses)),
            where=["instrument"]))


#: A ``Type`` line stating a time-of-flight histogram — the whole of
#: :func:`read_gsas2_instprm`'s dispatch.  ``Type`` is the file's own
#: statement of which quantity it holds, so it is read rather than inferred.
_TOF_TYPE_LINE = re.compile(r"^\s*Type\s*:\s*PNT", re.M)


def read_gsas2_instprm(path: str | Path, *, bank: int | None = None,
                       diagnostics: list[Diagnostic] | None = None
                       ) -> Instrument:
    """Read a GSAS-II ``.instprm`` file as a **frozen** ``Instrument``.

    The text half of GSAS-II's pair: a project is the binary ``.gpx``
    :func:`~rietx.read_gsas2_gpx` opens, while a calibration travels as this.
    Like :func:`read_gsas_prm` and :func:`load_instrument_profile` every
    parameter comes back ``vary=False``, because an instrument-parameter file is
    a beamline calibration rather than a starting guess (the module docstring's
    calibrate → freeze → refine-sample workflow).

    **The unit conversion** is one function with the writer
    (:func:`~rietx.io.projects.gsas2.instprm_factor`).  GSAS-II's ``U V W`` are
    the coefficients of a Gaussian *variance* in centidegrees² and this
    package's ``profile.u/v/w`` those of the Gaussian FWHM² in degrees², so
    ``u = U × 8 ln 2 × 1e-4`` (Γ² = 8 ln 2 · σ²); ``X`` and ``Y`` are
    centidegrees of Lorentzian FWHM, a factor 1e2.  ``Zero`` is already in
    degrees, and ``SH/L`` and ``Polariz.`` are ratios.  The same constant
    converts a recipe (:data:`~rietx.io.recipe.GAUSS_CENTIDEG2_TO_DEG2`).

    ``Zero`` is a **constant added to the calculated 2θ**, the same sense
    ``instrument.zero_shift`` has: GSAS-II corrects an observed position as
    ``tth = pos - Zero``.

    Read: ``Type``, the wavelengths and the doublet's intensity ratio,
    ``Polariz.``, ``U V W X Y``, ``SH/L``, ``Zero``, ``Diff-type`` and
    ``Gonio. radius``.  A time-of-flight bank (``Type: PNT``) is read too,
    into an ``Instrument`` whose source is ``kind="neutron_tof"``
    (:func:`rietx.io.instrument_tof.read_tof_instprm` lists its keys):
    one reader dispatching on the file's own ``Type``, since the suffix is the
    same either way.  Refused by name: an energy-dispersive or unknown
    ``Type``; a non-zero ``Z``, which ``ProfileTCHZ`` has no term for; a
    non-zero ``Azimuth``, which changes what ``Polariz.`` means; a negative
    width; and a multi-bank file with no ``bank=`` to select one.

    ``bank`` names the bank of a multi-bank file, as ``#Bank n:`` states it.
    ``diagnostics`` collects what the read assumed or could not carry.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"{p.name}: is not text this reader can decode as UTF-8, and "
            f"GSAS-II writes an .instprm as plain text.  A binary GSAS-II "
            f"file is the project itself, which read_gsas2_gpx opens: "
            f"{exc}") from exc
    except OSError:
        raise
    if _TOF_TYPE_LINE.search(text):
        # Handed over by path, before the grammar below: that parser was
        # written from GSAS-II's own modules (ATTRIBUTION.md), and the
        # time-of-flight reader is a literature-only build that keeps its own.
        if bank is not None:
            raise ValueError(
                f"{p.name}: states a time-of-flight bank (Type PNT), which is "
                f"read as the file's one bank; bank={bank} selects among the "
                f"banks of a constant-wavelength file")
        from .instrument_tof import read_tof_instprm

        return read_tof_instprm(p, diagnostics=diagnostics)
    try:
        banks = read_instprm(text)
    except ValueError as exc:
        raise ValueError(f"{p.name}: {exc}") from exc
    return _instprm_instrument(_instprm_bank(banks, bank, p).items, p,
                               diagnostics)


def from_instrument_gsas2(instrument: Instrument, *,
                          diagnostics: list[Diagnostic] | None = None) -> str:
    """Serialise ``instrument`` as GSAS-II ``.instprm`` text.

    :func:`read_gsas2_instprm`'s inverse, and the fifth of this package's
    foreign-format writers.  Named as
    :func:`from_instrument` is, with the format appended because both live here:
    a ``.prm`` and an ``.instprm`` are one kind of object under two programs'
    grammars.

    What crosses is what the reader reads back: the wavelengths and the
    doublet's ratio, the polarization, ``profile.u/v/w`` as ``U/V/W`` (÷ 8 ln 2,
    FWHM² → variance, and × 1e4 into centidegrees²) and ``profile.x/y`` as
    ``X/Y`` multiplied back into centidegrees, the axial
    divergence as ``SH/L``, ``zero_shift`` as ``Zero`` in degrees, and the
    geometry as ``Diff-type``.  ``Z`` is written at 0, the identity the reader
    requires it at.

    **The axial pair is merged and the merge is named.**  GSAS-II models one
    ``(S+H)/L`` where this package holds ``axial_sl`` and ``axial_hl``
    separately, so the sum crosses and an uneven split does not — the
    "a field narrower than the model merges, and the group is named" rule of
    ``io/CLAUDE.md`` § Project writers, met here on a value rather than a refine
    flag.

    **Every ``vary`` is dropped**, as :func:`from_instrument` drops them and for
    the same reason: an ``.instprm`` states no refine flags at all, a
    calibration having refined nothing by the time it ships.

    Refused by name: a ``flat_plate_transmission`` geometry, GSAS-II's
    ``Diff-type`` naming two sample kinds and not that one; more than two
    emission lines; a declared λ/n harmonic, which GSAS-II's constant-wavelength
    model has no term for; and a non-finite value, which ``repr`` spells ``inf``
    and no real program parses.
    """
    import math

    source, profile, geometry = (instrument.source, instrument.profile,
                                 instrument.geometry)
    neutron = isinstance(source, NeutronSource)
    if geometry.kind not in set(INSTPRM_DIFF_TYPES.values()):
        raise ValueError(
            f"this instrument's geometry is {geometry.kind!r}, and GSAS-II's "
            f"Diff-type names two sample kinds: "
            f"{' and '.join(INSTPRM_DIFF_TYPES)}.  Writing one of those would "
            f"hand over a different experiment, and leaving the item out would "
            f"let GSAS-II's own fallback pick one")
    if neutron:
        if source.harmonics:
            raise ValueError(
                f"this source declares {len(source.harmonics)} harmonic "
                f"line(s), and a GSAS-II constant-wavelength bank states one "
                f"wavelength with no lambda/n term.  Dropping them would hand "
                f"back an instrument with a different spectrum under a file "
                f"that looks complete")
        lines = [(source.wavelength, None)]
    else:
        if len(source.lines) > 2:
            raise ValueError(
                f"this source states {len(source.lines)} emission lines and a "
                f"constant-wavelength bank holds two, Lam1 and Lam2.  "
                f"Dropping the rest would hand back an instrument with a "
                f"different spectrum under a file that looks complete")
        lines = [(line.wavelength, line.weight) for line in source.lines]

    def value(number: float, what: str) -> str:
        """One item's value, spelled as the number's own ``repr``.

        A token format has no field to spend, so the shortest string that
        reads back as this double is exactly right and nothing narrows
        (``io/CLAUDE.md`` § Project writers).  Non-finite is refused here
        rather than written: ``repr`` spells it ``inf`` and no real program
        parses that.
        """
        if not math.isfinite(number):
            raise ValueError(
                f"{what} is {number!r}, and a file states numbers a program "
                f"can read: repr spells this 'inf' or 'nan' and GSAS-II's "
                f"reader floats every value it can")
        return repr(float(number))

    def centidegrees(letter: str, param) -> str:
        factor = instprm_factor(letter)
        return value(param.value * factor, f"profile.{letter.lower()}")

    shl = geometry.axial_sl.value + geometry.axial_hl.value
    stated: dict[str, str] = {
        "Type": "PNC" if neutron else "PXC",
        "Zero": value(instrument.zero_shift.value, "zero_shift"),
        "Polariz.": (_INSTPRM_NEUTRON_POLARIZATION if neutron
                     else value(source.polarization.value,
                                "source.polarization")),
        "Z": "0.0",
        "SH/L": value(shl, "geometry.axial_sl + axial_hl"),
        "Azimuth": "0.0",
        "Bank": "1.0",
    }
    if len(lines) == 1:
        stated["Lam"] = value(lines[0][0].value, "source wavelength")
    else:
        stated["Lam1"] = value(lines[0][0].value, "source.lines.0.wavelength")
        stated["Lam2"] = value(lines[1][0].value, "source.lines.1.wavelength")
        stated["I(L2)/I(L1)"] = value(lines[1][1].value,
                                      "source.lines.1.weight")
    for letter, attr in (("U", "u"), ("V", "v"), ("W", "w"),
                         ("X", "x"), ("Y", "y")):
        stated[letter] = centidegrees(letter, getattr(profile, attr))

    # Ordered by the format's own key list rather than by the order this
    # function happened to build them in: the tuples are the specification's,
    # and a second statement of the order here would be a second grammar.
    keys = INSTPRM_CW_DOUBLET if len(lines) == 2 else INSTPRM_CW_SINGLE
    items = {k: stated[k] for k in keys}
    items["Diff-type"] = next(k for k, v in INSTPRM_DIFF_TYPES.items()
                              if v == geometry.kind)
    if geometry.goniometer_radius_mm is not None:
        # GSAS-II writes the space and reads the key with every space stripped,
        # so this item is written `Gonio. radius` and read `Gonio.radius`.
        items["Gonio. radius"] = value(geometry.goniometer_radius_mm,
                                       "geometry.goniometer_radius_mm")

    if diagnostics is not None:
        _instprm_write_reports(instrument, shl, diagnostics)
    return write_instprm(items)


def _instprm_write_reports(instrument: Instrument, shl: float,
                           diagnostics: list[Diagnostic]) -> None:
    """What this instrument carries that an ``.instprm`` cannot state."""
    geometry, profile = instrument.geometry, instrument.profile
    if geometry.axial_sl.value != geometry.axial_hl.value:
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS2_INSTPRM_VALUE_MERGED",
            message=(
                f"axial_sl = {geometry.axial_sl.value:g} and axial_hl = "
                f"{geometry.axial_hl.value:g} were written as one SH/L = "
                f"{shl:g}. Reading this file back gives {0.5 * shl:g} for "
                f"each."),
            where=["instrument.geometry.axial_sl",
                   "instrument.geometry.axial_hl"],
            value=shl))
    if shl < INSTPRM_SHL_FLOOR:
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS2_INSTPRM_VALUE_FLOORED",
            message=(
                f"SH/L = {shl:g} was written as it stands, and GSAS-II floors "
                f"it at {INSTPRM_SHL_FLOOR} when it evaluates a profile."),
            where=["instrument.geometry.axial_sl"],
            value=shl))
    clauses = [
        "An .instprm has no items for the background, the specimen "
        "absorption, the specimen displacement or the transparency.",
    ]
    if profile.shape != "tchz_pv":
        clauses.append(
            f"The peak shape is {profile.shape!r}. An .instprm cannot state "
            f"it, so the widths were written and the shape model was not.")
    if instrument.extra_components:
        clauses.append(
            f"{len(instrument.extra_components)} extra component(s) were not "
            f"written.")
    if any(p.vary for p in _iter_parameters(instrument)):
        clauses.append(
            "An .instprm states no refine flags, so every refine flag reads "
            "back as vary=False.")
    diagnostics.append(Diagnostic(
        level="warning", code="GSAS2_INSTPRM_FIELD_NOT_WRITTEN",
        message="The .instprm omits part of the instrument. " + " ".join(clauses),
        where=["instrument"]))


def write_gsas2_instprm(instrument: Instrument, path: str | Path, *,
                        diagnostics: list[Diagnostic] | None = None) -> None:
    """Write ``instrument`` to ``path`` as a GSAS-II ``.instprm``.

    UTF-8, which is what GSAS-II writes and what :func:`read_gsas2_instprm`
    decodes.  See :func:`from_instrument_gsas2` for what crosses and what does
    not.
    """
    from ..schemas.pattern import require_two_theta

    require_two_theta(None, "write_gsas2_instprm()", instrument=instrument)
    Path(path).write_text(
        from_instrument_gsas2(instrument, diagnostics=diagnostics),
        encoding="utf-8")
