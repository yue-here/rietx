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

from .._about import PROFILE_FORMAT_KEY
from ..schemas.common import Diagnostic
from ..schemas.instrument import BackgroundChebyshev, Instrument

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

    ``background_peaks`` are stripped on the same grounds and it is the clearer
    case of the two: a diffuse hump belongs to this specimen, this can and this
    cryostat, so carrying one into the next sample would put a free peak at an
    angle nothing measured — and a free peak improves any Rwp.
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
                                     exclude={"background", "background_peaks"}),
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
_PRCF_TYPE_READ = "3"
_PRCF_TYPE_REFUSALS: dict[str, str] = {
    "1": "GSAS profile function 1 (simple Gaussian, no Lorentzian term)",
    "2": "GSAS profile function 2",
    "4": "GSAS profile function 4",
}

#: Inline coefficient labels some real files print beside the numbers on the
#: ``PRCF11``/``PRCF12`` continuation lines (2 of 1500 real files; e.g.
#: ``PRCF11   GU  1.163000     GV -0.126000 ...``).  The count in
#: ``INS nPRCF1 <type> <ncoef> <cutoff>`` counts **numeric** coefficients
#: only, so a label token is skipped rather than counted — it is prose, not a
#: 20th coefficient.  Confirmed against ``.LST`` refinement logs for this
#: instrument, which print the same eight names in the same order:
#: ``GU GV GW GP LX LY S/L H/L`` (§ the module docstring's arithmetic below).
_PRCF_LABELS = frozenset({"GU", "GV", "GW", "GP", "LX", "LY", "S/L", "H/L",
                          "TRNS", "SHFT", "SFEC"})

_ICONS_RE = re.compile(r"^INS\s*(\d+)\s*ICONS\s+(.+?)\s*$", re.MULTILINE)
_BANK_RE = re.compile(r"^INS\s*BANK\s+(\d+)", re.MULTILINE)
_HTYPE_RE = re.compile(r"^INS\s*HTYPE\s+(\S+)", re.MULTILINE)
_PRCF_HEADER_RE = re.compile(
    r"^INS\s*(\d+)PRCF1\s+(\d+)\s+(\d+)\s+([\d.Ee+-]+)", re.MULTILINE)
_PRCF_CONT_RE = re.compile(r"^INS\s*(\d+)PRCF1(\d+)\s+(.+?)\s*$", re.MULTILINE)
#: ``IRAD``/``ITYP`` are ignored by design, but the diagnostic saying so
#: must only fire for a file that actually carried one — see the guard below.
_IRAD_ITYP_RE = re.compile(r"^INS\s*\d+I?\s*(IRAD|ITYP)\b", re.MULTILINE)


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

    ``ICONS``'s six fields are read or refused individually, never guessed:
    the wavelength (field 1) and the polarization (field 4, GSAS's ``POL`` —
    0.990 in every real 11-BM file, matching this package's own
    :meth:`Instrument.debye_scherrer` default) are read.  A second wavelength
    line (field 2), a non-zero zero-point (field 3 — its unit is disputed
    between two GSAS-adjacent conventions 100x apart, see ``io/recipe.py``'s
    ``_read_zero_shift``, and no real file in this corpus has a non-zero
    value to settle it against) and an unidentified reserved field (field 5)
    are each refused **only if non-zero**: every real file in the corpus this
    reader was built against has all three at their identity value (0), so
    refusing only a non-zero occurrence reads every real file while never
    silently discarding a value that would have changed the answer.  Field 6
    (a Kα2/Kα1 intensity-ratio default) is inert whenever field 2 is zero, as
    it is in the whole corpus, and is read but not applied.  ``IRAD`` and
    ``ITYP`` (radiation-table code and angular range) are deliberately
    ignored: the wavelength is read directly from ``ICONS`` rather than
    looked up from ``IRAD``'s table, and an angular range belongs to the
    pattern, not the instrument.

    Similarly for ``PRCF``: only the eight coefficients this package's
    profile has room for (``GU GV GW`` → u/v/w, ``LX LY`` → x/y, ``S/L H/L``
    → axial_sl/axial_hl) are read.  ``GP`` (position 4) and every coefficient
    past position 8 (``trns``, ``shft``, ``sfec`` and further reserved slots)
    are refused if non-zero and dropped only at their identity value (0) —
    every real file in the corpus is 0 there, so this is the same "refuse a
    value at drift, never a value at the model's identity" rule
    ``io/CLAUDE.md``'s ``recipe.py`` section already states, applied to a
    second format's version of it.

    **``diagnostics``** completes that rule's other half: a value dropped at
    the model's identity is dropped *with a diagnostic*, so a caller can learn
    that the file said something the ``Instrument`` does not carry.  Pass a
    list to collect them; the codes are

    * ``GSAS_PRM_FIELD_DROPPED`` — once per record that carried a field this
      reader does not map: ``ICONS`` (a zero second wavelength or zero-point,
      the unidentified field 5, and field 6's Kα2/Kα1 ratio, which is read and
      **not applied**), ``PRCF`` (``GP`` and every coefficient past position 8,
      all at 0), and ``IRAD``/``ITYP``, which are ignored by design.  Each
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
    text = p.read_text(encoding="utf-8", errors="ignore")

    htype_m = _HTYPE_RE.search(text)
    bank_m = _BANK_RE.search(text)
    if htype_m is None or bank_m is None:
        raise ValueError(
            f"{p.name}: not a GSAS-I instrument-parameter file — no "
            f"BANK/HTYPE record found (Larson & Von Dreele, LAUR 86-748)")

    htype = htype_m.group(1).upper()
    _check_htype(htype, p)

    nbank = int(bank_m.group(1))
    if nbank != 1:
        raise ValueError(
            f"{p.name}: declares BANK {nbank} — only a single-bank "
            f"instrument file is read.  No real multi-bank PXCR file was "
            f"found in the corpus this reader was built against (the only "
            f"multi-bank files seen are HTYPE PNTR, refused above); reading "
            f"one bank of several would silently pick a bank rather than "
            f"letting the caller choose")

    wavelength, polarization, ka2_ratio = _read_icons(text, p)
    prof_type, coeffs = _read_prcf(text, p)
    if prof_type != _PRCF_TYPE_READ:
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

    gu, gv, gw, gp, lx, ly, sl, hl, *rest = coeffs
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
                f"S/L/H/L (positions 1-8) onto ProfileTCHZ, and every real "
                f"file this reader was built against carries 0 past "
                f"position 8, so a non-zero one here is unidentified rather "
                f"than dropped")

    if diagnostics is not None:
        # The drop half of io/CLAUDE.md's rule: a field at the model's
        # identity is dropped *with a diagnostic*, one per record, naming the
        # values so the caller can see what was in the file.  Emitted only
        # here, past every refusal above, so a file about to be refused does
        # not leave a half-list behind on the caller's list.
        # Each row is a statement about *this file*, so a row is only built
        # where the file carried the thing it describes.  A drop diagnostic
        # for a record that is absent is the same shape as a defaulted field
        # answering a question nobody asked (WP-1076): it is `info`, and the
        # corpus makes it true often enough that it would not be noticed.
        dropped = [
            ("ICONS", f"field 5 (unidentified) = 0, and field 6's Kα2/Kα1 "
                      f"ratio = {ka2_ratio!r}, read and not applied (it is "
                      f"inert while field 2 is 0, as it is here)"),
        ]
        past_8 = (f", and {len(rest)} coefficient(s) past position 8 = 0"
                  if rest else "")
        dropped.append(
            ("PRCF", f"GP (position 4) = 0{past_8} — this reader maps "
                     f"positions 1-8 onto ProfileTCHZ"))
        if _IRAD_ITYP_RE.search(text):
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

    instrument = Instrument.debye_scherrer(
        wavelength=wavelength, polarization=polarization)
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
                        "different off states (mu_r = 0 against mu_t = inf)")))
    prof = instrument.profile
    prof.u.value = gu / 1e4
    prof.v.value = gv / 1e4
    prof.w.value = gw / 1e4
    prof.x.value = lx / 1e2
    prof.y.value = ly / 1e2
    instrument.geometry.axial_sl.value = sl
    instrument.geometry.axial_hl.value = hl
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


def _read_icons(text: str, p: Path) -> tuple[float, float, float]:
    """Read bank 1's ``ICONS`` record: (wavelength, polarization, ratio).

    The third return value is field 6's Kα2/Kα1 intensity ratio, which this
    reader does **not** apply (it is inert while field 2 is zero, as it is in
    the whole corpus).  It comes back so the caller can be told the file
    carried it — see ``GSAS_PRM_FIELD_DROPPED``.

    Six fields (``ALAM1 ALAM2 ZERO POL <reserved> <ratio>``, in that order —
    the module docstring says which are read, refused-if-nonzero or
    deliberately unused).  Anything other than exactly one match with exactly
    six fields is refused: the one real file that fails this (a stock GSAS
    example with a 7-field ICONS and 3 stacked PRCF profile-type blocks under
    one bank number, none of them real calibration data) is not a shape this
    reader can read any part of safely.
    """
    matches = list(_ICONS_RE.finditer(text))
    bank1 = [m for m in matches if m.group(1) == "1"]
    if len(bank1) != 1:
        raise ValueError(
            f"{p.name}: expected exactly one ICONS record for bank 1, found "
            f"{len(bank1)} — a bank declaring its constants more than once "
            f"(or not at all) is ambiguous, not a single instrument")
    fields = bank1[0].group(2).split()
    if len(fields) != 6:
        raise ValueError(
            f"{p.name}: bank 1's ICONS record has {len(fields)} fields "
            f"({fields!r}), not the 6 (ALAM1 ALAM2 ZERO POL reserved ratio) "
            f"every real calibration file in the corpus this reader was "
            f"built against carries — reading a subset of them would be a "
            f"guess about which is missing")
    try:
        alam1, alam2, zero, pol, reserved, ratio = (float(f) for f in fields)
    except ValueError as exc:
        raise ValueError(
            f"{p.name}: bank 1's ICONS record holds a token that is not a "
            f"number ({fields!r}) — the six fields are ALAM1 ALAM2 ZERO POL "
            f"reserved ratio and every one of them is numeric in the corpus "
            f"this reader was built against, so this is a malformed record "
            f"rather than a convention it has not met") from exc
    if alam2 != 0.0:
        raise ValueError(
            f"{p.name}: ICONS field 2 (a second wavelength line, GSAS "
            f"'ALAM2') is {alam2!r}, not 0 — no real file in this corpus "
            f"has a second line to derive its intensity-weight convention "
            f"from, so adding one here would be a guess about a doublet "
            f"this reader has never seen")
    if zero != 0.0:
        raise ValueError(
            f"{p.name}: ICONS field 3 (GSAS 'ZERO') is {zero!r}, not 0 — "
            f"its unit is disputed between two GSAS-adjacent conventions a "
            f"factor of 100 apart (io/recipe.py's Zero handling) and no "
            f"real file in this corpus has a non-zero value to settle it "
            f"against, so a non-zero one here is refused rather than mapped "
            f"onto instrument.zero_shift on either guess")
    if reserved != 0.0:
        raise ValueError(
            f"{p.name}: ICONS field 5 is {reserved!r}, not 0 — this field "
            f"is unidentified (every real file in the corpus this reader "
            f"was built against carries 0 here), so a non-zero value is "
            f"refused rather than silently dropped")
    return alam1, pol, ratio


def _read_prcf(text: str, p: Path) -> tuple[str, list[float]]:
    """Read bank 1's single ``PRCF1`` block: (profile type, coefficients).

    The block is a **counted** layout: ``INS 1PRCF1 <type> <ncoef> <cutoff>``
    states how many numeric coefficients follow across the ``PRCF11``…
    ``PRCF1n`` continuation lines, and that count — not the number of
    continuation lines present — is what is consumed.  A label token (``GU``,
    ``S/L``, …) printed beside a number on some real files is skipped rather
    than counted as a coefficient.
    """
    headers = [m for m in _PRCF_HEADER_RE.finditer(text) if m.group(1) == "1"]
    if len(headers) != 1:
        raise ValueError(
            f"{p.name}: expected exactly one PRCF1 header for bank 1, found "
            f"{len(headers)} — a bank declaring its profile function more "
            f"than once (the one real example is a stock GSAS file stacking "
            f"types 2, 3 and 4 with placeholder values under one bank) is "
            f"ambiguous about which applies, not a richer instrument")
    header = headers[0]
    prof_type, ncoef = header.group(2), int(header.group(3))

    coeffs: list[float] = []
    for m in _PRCF_CONT_RE.finditer(text, header.end()):
        if m.group(1) != "1":
            break
        for tok in m.group(3).split():
            if tok.upper() in _PRCF_LABELS:
                continue
            try:
                coeffs.append(float(tok))
            except ValueError:
                raise ValueError(
                    f"{p.name}: PRCF11..PRCF1n holds an unrecognised token "
                    f"{tok!r} that is neither a number nor a known label "
                    f"({sorted(_PRCF_LABELS)}) — refusing rather than "
                    f"silently skipping it, since a genuine coefficient "
                    f"dropped this way would shift every one after it") from None
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
