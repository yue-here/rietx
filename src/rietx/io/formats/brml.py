"""Bruker ``.brml`` — the zip container DIFFRAC.MEASUREMENT writes.

Spec: a zip of XML, read off two real files.  Member paths, element names and
attribute names are interface facts, so they are written down here and the
parser below is this package's own::

    Experiment0/DataContainer.xml       the manifest
      <RawDataReferenceList>
        <string>Experiment0/RawData0.xml</string>   one per scan
    Experiment0/RawData0.xml
      <DataRoutes><DataRoute RouteFlag="Measured">
        <ScanInformation ScanName="TwoThetaOmegaScan">
          <ScanAxes><ScanAxisInfo AxisId="TwoTheta" …
        <Datum>1,1,44,18.028,-0.12937,0,2.63482,3</Datum>   … one per point
        <DataViews>
          <RawDataView xsi:type="FixedRawDataView"    Start="0" Length="1"
                       LogicName="MeasuredTime" />
          <RawDataView xsi:type="FixedRawDataView"    Start="1" Length="1"
                       LogicName="AbsorptionFactor" />
          <RawDataView xsi:type="VaryingRawDataView"  Start="2" Length="2">
            <Varying><FieldDefinitions FieldName="TwoTheta" AxisId="TwoTheta" />
                     <FieldDefinitions FieldName="Theta"    AxisId="Theta" />
          <RawDataView xsi:type="RecordedRawDataView" Start="7" Length="1">
            <Recording><Unit Base="Counts" />

**Every column is located from ``DataViews``, never counted.**  GSAS-II reads a
datum's ``[2]`` and ``[4]``; in the two real files here the 2θ sits at 2 and the
intensity at **7**, so a fixed index is a coincidence of one layout.  ``Start``
and ``Length`` say where each channel is and ``FieldDefinitions`` names the axes
inside a varying one, in order — which is a complete description, so this reader
uses it and asserts nothing about position.

**A ``RecordedRawDataView`` of ``Length > 1`` is a detector frame and is
refused.**  ``EJZ060_13_004_RSM.brml`` records 1280 channels per row from a
position-sensitive detector, with 1281×3 reciprocal-space coordinates beside
them; its ``ScanAxes`` still claims ``AxisId="TwoTheta"``, so the axis check
passes and only the recorded view's own length says what the rows are.  Reading
one channel of it, or the row as a profile, would both be inventions.

**The absorber is *already applied* to the stored intensity, which is the third
answer this WP has got from three vendors.**  ``AbsorptionFactor`` is a per-point
channel and it varies in the real file — 1.0 outside a strong substrate peak,
8.3 across 29 points of it.  Measured there: ``y`` is not integral, ``y × a`` is
not integral, and ``y / a`` **is**, exactly; and the stored series runs
continuously across the transition (120757 → 151306 → 182114 → 213600.5) while
``y / a`` steps by a factor of seven.  So Bruker stores the corrected intensity
and records the factor it used.  Nothing is multiplied here — but σ still has to
go back through it, because the Poisson quantity is ``y / a``: σ = √(y/a)·a,
which is :func:`base.sigma_from_scaled` at that scale.

Compare ``.xrdml``, where the *same* structural test says the opposite (the raw
series dips at the attenuated point, so the factor must be applied), and the two
Rigaku formats, where no obtainable file has a varying factor and the reader
therefore reports rather than decides.  Three formats, three answers, each
measured on a file rather than taken from a convention.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import (
    PatternFormat,
    ScanInfo,
    ascending,
    check_axis,
    decode,
    head,
    multiscan_default,
    pattern_data,
    sigma_from_scaled,
)
from .rasx import MAX_MEMBER_BYTES, ZIP_MAGIC

#: The XML-Schema-instance namespace, whose ``type`` attribute is what
#: distinguishes the four kinds of ``RawDataView``.  Held as a namespace rather
#: than as the literal ``xsi:type``: the prefix is the document's to choose, and
#: ElementTree resolves it away, so matching the string would break on a file
#: that spelled it ``xs:`` — the risk this WP names against this design.
_XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"

_MANIFEST = re.compile(r"(^|/)DataContainer\.xml$")
_RAW_DATA = re.compile(r"(^|/)RawData\d+\.xml$")

#: ``ScanAxisInfo``/``FieldDefinitions`` ``AxisId`` values that step 2θ.  Bruker
#: names the coupled scan by its two axes and a detector scan by one; both step
#: the detector through 2θ, which is all this package needs.
_TWO_THETA_AXES = frozenset({"twotheta"})

#: Axis ids that are recognisably **not** 2θ, with what each one measures.  Every
#: one of these appears as an ``AxisId`` in the real files' alignment records, so
#: the vocabulary is the vendor's rather than this reader's guess.
_OTHER_AXES: dict[str, str] = {
    "theta": "a rocking curve about ω (Bruker's Theta), which measures crystal "
             "misorientation at one fixed 2θ",
    "chi": "a χ tilt — one arc of a pole figure",
    "phi": "a φ rotation — one ring of a pole figure",
    "psi": "a ψ tilt, as measured for residual stress",
    "x": "a specimen translation in x, used to position the sample",
    "y": "a specimen translation in y, used to position the sample",
    "z": "a specimen height scan, used to set the sample surface",
    "recspx": "a reciprocal-space coordinate, not a goniometer angle",
    "recspy": "a reciprocal-space coordinate, not a goniometer angle",
    "recspz": "a reciprocal-space coordinate, not a goniometer angle",
}


@dataclass(frozen=True)
class _Columns:
    """Which datum column holds what, as ``DataViews`` describes it.

    ``two_theta`` is optional here, and deliberately: a file that stepped no 2θ
    is refused by :func:`_axis` first, which can say *what* it stepped instead —
    "a rocking curve about ω" rather than "no diffraction angle".  The generic
    refusal is the fallback for an axis no vocabulary places.
    """

    two_theta: int | None
    intensity: int
    count_time: int | None
    absorption: int | None
    #: the axis ids that actually stepped, in the order the views list them —
    #: the evidence the axis policy is applied to
    stepped: tuple[str, ...]
    #: the recorded channel's declared unit, e.g. ``Counts``
    unit: str


def _archive(path: Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path.name} begins like a zip archive but is not a "
                         f"readable one ({exc}); a .brml that stops early is "
                         "usually a copy that was interrupted") from None


def _member(zip_archive: zipfile.ZipFile, name: str, *, path: Path) -> bytes:
    """One member's bytes, read through :data:`rasx.MAX_MEMBER_BYTES`.

    The cap matters more here than anywhere: a 651 kB ``.brml`` carries a 4.5 MB
    ``MeasurementContainer.xml`` this reader never opens, so "how big is the
    file" says nothing about how big a member is.
    """
    try:
        with zip_archive.open(name) as fh:
            raw = fh.read(MAX_MEMBER_BYTES + 1)
    except KeyError:
        raise ValueError(f"{path.name}: its manifest names {name!r}, which the "
                         "archive does not contain, so the file is internally "
                         "inconsistent") from None
    except (zipfile.BadZipFile, EOFError) as exc:
        raise ValueError(f"{path.name}: member {name!r} could not be "
                         f"decompressed ({exc})") from None
    if len(raw) > MAX_MEMBER_BYTES:
        raise ValueError(f"{path.name}: member {name!r} is larger than the "
                         f"{MAX_MEMBER_BYTES // (1024 * 1024)} MB a pattern "
                         "member may be, so it was not read")
    return raw


def _xml(raw: bytes, *, path: Path, what: str) -> ET.Element:
    try:
        return ET.fromstring(decode(raw)[0])
    except ET.ParseError as exc:
        raise ValueError(f"{path.name}: {what} is not readable as XML "
                         f"({exc})") from None


def _local(tag: str) -> str:
    return tag.rpartition("}")[2]


def _kind(view: ET.Element) -> str:
    """A view's ``xsi:type``, namespace-resolved and without its prefix."""
    return (view.get(_XSI_TYPE) or view.get("type") or "").rpartition(":")[2]


def _scan_members(zip_archive: zipfile.ZipFile, path: Path) -> list[str]:
    """Every ``RawData<N>.xml`` the manifest lists, in its order.

    From ``DataContainer.xml`` rather than the name list, which a real 801-scan
    archive shows is not even in numeric order — its members run …20, 22, 21,
    ``experimentCollection.xml``, 23…
    """
    manifest = next((n for n in zip_archive.namelist() if _MANIFEST.search(n)), None)
    if manifest is None:
        raise ValueError(f"{path.name}: the archive carries no DataContainer.xml, "
                         "which is the manifest naming the scans")
    root = _xml(_member(zip_archive, manifest, path=path), path=path,
                what=manifest)
    out = [(element.text or "").strip()
           for reference in root.iter()
           if _local(reference.tag) == "RawDataReferenceList"
           for element in reference if (element.text or "").strip()]
    if not out:
        raise ValueError(f"{path.name}: {manifest} lists no raw data — a .brml "
                         "names each scan in <RawDataReferenceList>, and this "
                         "archive names none")
    return out


def _route(raw_data: ET.Element, *, path: Path, member: str) -> ET.Element:
    """The ``Measured`` data route, or the only one, or a refusal.

    A file may carry processed routes beside the measured one; refining against
    somebody else's background subtraction without being told is exactly the
    class of silent substitution this package refuses.
    """
    routes = [r for r in raw_data.iter() if _local(r.tag) == "DataRoute"]
    if not routes:
        raise ValueError(f"{path.name}: {member} carries no <DataRoute>, so it "
                         "holds no measured points")
    measured = [r for r in routes if r.get("RouteFlag") == "Measured"]
    if len(measured) == 1:
        return measured[0]
    if len(routes) == 1:
        return routes[0]
    flags = ", ".join(sorted({r.get("RouteFlag") or "(none)" for r in routes}))
    raise ValueError(f"{path.name}: {member} holds {len(routes)} data routes "
                     f"({flags}) and not exactly one marked Measured. Which of "
                     "them is the measurement is the file's to say, not this "
                     "reader's to guess")


def _columns(route: ET.Element, *, path: Path, member: str) -> _Columns:
    """Where each channel lives, read out of ``DataViews``.

    Nothing here is positional: ``Start`` locates a view and ``FieldDefinitions``
    orders the axes inside a varying one, so a file that adds a channel moves
    every index and this still reads it.
    """
    views = [v for v in route.iter() if _local(v.tag) == "RawDataView"]
    fixed: dict[str, int] = {}
    two_theta: int | None = None
    intensity: int | None = None
    unit = ""
    stepped: list[str] = []

    for view in views:
        try:
            start, length = int(view.get("Start", "")), int(view.get("Length", ""))
        except ValueError:
            raise ValueError(f"{path.name}: a <RawDataView> in {member} gives no "
                             "usable Start/Length, which is the only description "
                             "of where its channel sits") from None
        kind = _kind(view)
        if kind == "FixedRawDataView":
            fixed[(view.get("LogicName") or "").lower()] = start
        elif kind == "VaryingRawDataView":
            fields = [f for f in view.iter() if _local(f.tag) == "FieldDefinitions"]
            for offset, field in enumerate(fields):
                axis = (field.get("AxisId") or field.get("FieldName") or "").strip()
                stepped.append(axis)
                if axis.lower() in _TWO_THETA_AXES and two_theta is None:
                    two_theta = start + offset
        elif kind == "RecordedRawDataView":
            if length != 1:
                raise ValueError(
                    f"{path.name}: {member} records {length} channels per point, "
                    "which is a position-sensitive-detector frame rather than a "
                    "profile — each row is a whole detector image, and picking "
                    "one channel of it or reading the row as a scan would both "
                    "be inventions. Export the integrated scan instead")
            if intensity is None:
                intensity = start
                unit = next((u.get("Base") or "" for u in view.iter()
                             if _local(u.tag) == "Unit"), "")

    if intensity is None:
        raise ValueError(f"{path.name}: {member} declares no "
                         "RecordedRawDataView, so nothing in it is the measured "
                         "intensity")
    return _Columns(two_theta=two_theta, intensity=intensity,
                    count_time=fixed.get("measuredtime"),
                    absorption=fixed.get("absorptionfactor"),
                    stepped=tuple(stepped), unit=unit.strip())


def _data(route: ET.Element, columns: _Columns, *, path: Path,
          member: str) -> np.ndarray:
    """The ``Datum`` rows as a float array, wide enough for every named column."""
    rows: list[list[str]] = [(datum.text or "").split(",")
                             for datum in route.iter()
                             if _local(datum.tag) == "Datum"]
    if not rows:
        raise ValueError(f"{path.name}: {member} declares its channels but holds "
                         "no <Datum> rows")
    needed = 1 + max(c for c in (columns.two_theta, columns.intensity,
                                 columns.count_time, columns.absorption)
                     if c is not None)
    width = min(len(r) for r in rows)
    if width < needed:
        raise ValueError(f"{path.name}: {member} declares channels up to column "
                         f"{needed - 1} but a row holds {width}, so the data and "
                         "the description of it disagree")
    try:
        return np.array([r[:needed] for r in rows], dtype=np.float64)
    except ValueError:
        raise ValueError(f"{path.name}: a <Datum> in {member} is not a row of "
                         "comma-separated numbers") from None


def _column(data: np.ndarray, index: int | None) -> np.ndarray | None:
    return None if index is None else data[:, index]


def _scale(columns: _Columns, absorption: np.ndarray | None, *, path: Path,
           diagnostics: list[Diagnostic] | None) -> np.ndarray | float | None:
    """``s`` in ``y = counts·s`` — the absorber, and a counting time if it is one.

    The unit is trusted here on the ``.uxd`` side of that argument: ``Base`` is a
    schema-enumerated attribute of the recorded channel itself.  Verified anyway
    — ``y / a`` is integral to the last of 2001 points on the real file.
    """
    scale: np.ndarray | float = 1.0 if absorption is None else absorption
    if columns.unit.lower() in {"counts", "count", ""}:
        return scale
    if diagnostics is not None:
        diagnostics.append(Diagnostic(
            level="warning", code="PATTERN_INTENSITY_SCALED",
            message=(f"{Path(path).name} declares its recorded channel's unit as "
                     f"{columns.unit!r}, which this reader does not recognise as "
                     "counts. No σ was supplied."),
            where=["sigma"],
            suggestion="Export the file in counts, or supply the esds."))
    return None


def _absorber(absorption: np.ndarray | None, two_theta: np.ndarray, *, path: Path,
              diagnostics: list[Diagnostic] | None) -> None:
    """Say so when the absorber engaged — it did not change y, but it changed σ."""
    if absorption is None or diagnostics is None:
        return
    # a row with no finite value is ``ascending``'s to drop and report (WP-2079)
    off = (absorption != 1.0) & np.isfinite(absorption) & np.isfinite(two_theta)
    if not off.any():
        return
    affected = two_theta[off]
    diagnostics.append(Diagnostic(
        level="info", code="BRML_ABSORBER_ENGAGED",
        message=(f"{Path(path).name} used an automatic absorber over "
                 f"{int(off.sum())} point(s) at 2θ = {affected.min():.4g}–"
                 f"{affected.max():.4g}°, up to {absorption[off].max():.6g}×. The "
                 "stored intensities already include the correction, and σ was "
                 "derived through it."),
        where=["sigma"],
        suggestion=None))


def _axis(columns: _Columns, scan_name: str, *, path: Path,
          diagnostics: list[Diagnostic] | None) -> str | None:
    """The stepped axes classified; :func:`base.check_axis` decides.

    Applied to the axes rather than to ``ScanName`` because the axes are what the
    file *records*: an RSM's ``ScanName`` is ``PsdFixed``, a name no vocabulary
    would place, while its ``ScanAxes`` says plainly which angle moved.
    """
    stated = ", ".join(columns.stepped) or scan_name
    keys = {a.lower() for a in columns.stepped}
    other = next((_OTHER_AXES[k] for k in sorted(keys) if k in _OTHER_AXES), None)
    check_axis(stated, path=path,
               field="the axes ScanInformation/ScanAxes lists",
               two_theta=bool(keys & _TWO_THETA_AXES), other=other,
               remedy="Export the coupled 2θ–ω scan instead.",
               diagnostics=diagnostics)
    # the *name* is what goes in the metadata, because that is what the file
    # calls this scan and what its oracle records — the axes were the evidence
    return scan_name or stated or None


def _text(root: ET.Element, name: str) -> str | None:
    for element in root.iter():
        if _local(element.tag) == name and element.text and element.text.strip():
            return element.text.strip()
    return None


def _value(root: ET.Element, name: str) -> str | None:
    """A Bruker ``<Name Unit="…" Value="…" />``, of which the wavelength is one."""
    for element in root.iter():
        if _local(element.tag) == name and element.get("Value"):
            return element.get("Value")
    return None


def _scan_name(route: ET.Element) -> str:
    for element in route.iter():
        if _local(element.tag) == "ScanInformation":
            return (element.get("ScanName") or "").strip()
    return ""


def read_brml(path: str | Path, *, scan: int | None = None,
              diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    with _archive(p) as zip_archive:
        members = _scan_members(zip_archive, p)
        multiscan_default(len(members), scan, path=p, diagnostics=diagnostics)

        index = 0 if scan is None else scan
        if not 0 <= index < len(members):
            raise ValueError(f"{p.name} holds {len(members)} scan(s), numbered 0 "
                             f"to {len(members) - 1}; scan={index} is not one of "
                             "them")
        member = members[index]
        raw_data = _xml(_member(zip_archive, member, path=p), path=p, what=member)

    route = _route(raw_data, path=p, member=member)
    columns = _columns(route, path=p, member=member)
    data = _data(route, columns, path=p, member=member)

    # the axis policy speaks first, so a recognisable non-2θ scan is refused by
    # what it *is*; only an axis no vocabulary places reaches the generic refusal
    axis = _axis(columns, _scan_name(route), path=p, diagnostics=diagnostics)
    if columns.two_theta is None:
        raise ValueError(
            f"{p.name}: {member} steps {', '.join(columns.stepped) or 'no axis'},"
            " and none of them is TwoTheta — so the file holds no diffraction "
            "angle to read as a pattern")
    x, y = data[:, columns.two_theta], data[:, columns.intensity]
    absorption = _column(data, columns.absorption)
    _absorber(absorption, x, path=p, diagnostics=diagnostics)
    scale = _scale(columns, absorption, path=p, diagnostics=diagnostics)
    # ``s ≡ 1`` is raw counts, for which the Poisson fallback is exactly right
    sigma = (sigma_from_scaled(y, scale)
             if scale is not None and np.any(np.asarray(scale) != 1.0) else None)

    count_time = _column(data, columns.count_time)
    tt, y, sig = ascending(x, y, sigma, path=p, fmt=BRML, diagnostics=diagnostics)
    return pattern_data(
        p, tt, y, sig, source_file=p.name, format="brml", scan=index,
        scan_count=len(members), scan_axis=axis,
        sample=_text(raw_data, "SampleName"),
        anode=_text(raw_data, "TubeMaterial"),
        wavelength=_value(raw_data, "WaveLength"),
        intensity_unit=columns.unit or None,
        count_time_s=(float(count_time[0])
                      if count_time is not None and count_time.size
                      and np.all(count_time == count_time[0]) else None))


def list_brml_scans(path: str | Path) -> list[ScanInfo]:
    out: list[ScanInfo] = []
    p = Path(path)
    with _archive(p) as zip_archive:
        for i, member in enumerate(_scan_members(zip_archive, p)):
            raw_data = _xml(_member(zip_archive, member, path=p), path=p,
                            what=member)
            route = _route(raw_data, path=p, member=member)
            columns = _columns(route, path=p, member=member)
            if columns.two_theta is None:
                raise ValueError(f"{p.name}: {member} steps no TwoTheta axis, so "
                                 "it is not a scan this reader can list")
            x = _data(route, columns, path=p, member=member)[:, columns.two_theta]
            name = _scan_name(route) or ", ".join(columns.stepped)
            out.append(ScanInfo(index=i,
                                label=f"{name} {np.nanmin(x):.4g}–{np.nanmax(x):.4g}°",
                                n_points=int(x.size),
                                two_theta_range=(float(np.nanmin(x)), float(np.nanmax(x)))))
    return out


def looks_brml(p: Path) -> bool:
    """Zip magic, then both members this reader needs to read anything at all."""
    if not head(p, n=len(ZIP_MAGIC)).raw.startswith(ZIP_MAGIC):
        return False
    try:
        with zipfile.ZipFile(p) as zip_archive:
            names = zip_archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return False
    return (any(_MANIFEST.search(n) for n in names)
            and any(_RAW_DATA.search(n) for n in names))


BRML = PatternFormat(
    name="brml",
    title="Bruker DIFFRAC.MEASUREMENT experiment (.brml)",
    extensions=(".brml",),
    sniff="a zip archive holding a DataContainer.xml and a RawData<N>.xml",
    sigma=("derived through the automatic absorber the file records — σ = "
           "√(y/a)·a, because the stored intensity is already corrected for it "
           "and the counted quantity is y/a; the Poisson fallback where the "
           "absorber never engaged, which is exactly right"),
    matches=looks_brml,
    read=read_brml,
    options=("scan",),
    scans=list_brml_scans,
)
