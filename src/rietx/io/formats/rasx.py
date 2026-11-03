"""Rigaku ``.rasx`` — the zip container SmartLab Studio II writes.

Spec: a zip whose member names and manifest were read off four real files.
Member paths and element names are interface facts, so they are written down
here and the parser below is this package's own::

    root.xml                            the manifest, UTF-8 with a BOM
      <Root Version="1.1.0.0">
        <Data0 Type="Profile">          one group per scan
          <ContentHashList Name="Profile0.txt" ContentHash="…" />
          <ContentHashList Name="MesurementConditions0.xml" ContentHash="…" />
    Data0/Profile0.txt                  2θ ⇥ intensity ⇥ attenuator, per line
    Data0/MesurementConditions0.xml     the header — note the misspelling

**The manifest is the authority on what the file holds**, not the zip's name
list: it gives the groups in order and says which member of each is the profile.
A member path is its group's element name, a slash, and the ``Name`` attribute —
which is how ``MesurementConditions0.xml`` is found without this module having
to be sure Rigaku will keep misspelling it.  A reciprocal-space map is 401
groups (``RSM_111_sdd=350.rasx``, recorded in ``tests/data/README.md``); they
are scans, selected with ``scan=`` and never joined.

**Nothing is extracted to disk and no member is read whole on trust.**
``ZipInfo.file_size`` is a number in the archive's own header — an attacker or a
corrupt writer supplies it — so each member is read through a cap and refused
past it, and ``extract()`` (which writes files, and historically wrote them
outside the destination) is never called.

**σ is the ``.ras`` arithmetic, and that is a correction to this WP's premise.**
The plan recorded cps as *verified by fixture* for this format.  It is not: of
the three real single-scan files, ``TwoTheta_scan_powder.rasx`` and
``Omega-2Theta_scan_high_temperature.rasx`` both declare
``<IntensityUnit>counts</IntensityUnit>`` and store values like 170.55354309082
that **no** scale in 1/400…400 (nor k/60, nor 60/k, nor the file's own 2.4 s
counting time) makes integral, while ``ZnO-ALD-training….rasx`` declares counts
and is integral to the last of 7001 points.  So this is the same free-text
declaration ``.ras`` gets wrong, in the same vendor's own embedded ``RASHeader``,
and it is decided the same way — by :func:`base.sigma_by_arithmetic`.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
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
    sigma_by_arithmetic,
)
from .ras import RIGAKU_OTHER_AXES, RIGAKU_TWO_THETA_AXES, rigaku_attenuator

#: The local ``.zip`` header every member starts with — checked before the
#: archive is opened at all, so a text file never reaches ``zipfile``.
ZIP_MAGIC = b"PK\x03\x04"

#: A profile member, which is what distinguishes this container from a ``.brml``.
_PROFILE_MEMBER = re.compile(r"^Data\d+/Profile\d+\.txt$")
_DATA_GROUP = re.compile(r"^Data\d+$")

#: How much of any one member may be read.  Not protection theatre: a zip states
#: each member's uncompressed size in its own header, so a 40 kB archive can
#: claim — and a naive reader will faithfully materialise — a member of any size
#: at all.  128 MB is far past a real profile (7001 points is 100 kB) and far
#: below what would exhaust a machine.
MAX_MEMBER_BYTES = 128 * 1024 * 1024

#: ``SpeedUnit`` → seconds per unit of the speed's denominator, the same reading
#: ``.ras`` needs: real files say ``deg/min``, and assuming seconds would make
#: every derived counting time 60× short and every σ wrong by √60.
_SPEED_UNIT_SECONDS: dict[str, float] = {
    "deg/min": 60.0, "degree/min": 60.0,
    "deg/sec": 1.0, "deg/s": 1.0, "degree/sec": 1.0,
}


def _archive(path: Path) -> zipfile.ZipFile:
    """The open archive, with ``zipfile``'s exception converted at this boundary."""
    try:
        return zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path.name} begins like a zip archive but is not a "
                         f"readable one ({exc}); a .rasx that stops early is "
                         "usually a copy that was interrupted") from None


def _member(zip_archive: zipfile.ZipFile, name: str, *, path: Path) -> bytes:
    """One member's bytes, read through :data:`MAX_MEMBER_BYTES`.

    ``read(cap + 1)`` and a length test rather than trusting ``ZipInfo``: the
    declared size is metadata in the archive, and the one number a bomb lies
    about.
    """
    try:
        with zip_archive.open(name) as fh:
            raw = fh.read(MAX_MEMBER_BYTES + 1)
    except KeyError:
        raise ValueError(f"{path.name}: its manifest names a member {name!r} "
                         "that the archive does not contain, so the file is "
                         "internally inconsistent") from None
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


def _groups(zip_archive: zipfile.ZipFile, path: Path) -> list[tuple[str, str]]:
    """Every ``(profile member, conditions member)`` pair, in manifest order.

    From ``root.xml`` rather than the name list, because the manifest is what
    orders the scans and what says which member of a group is the profile.  A
    group missing its conditions is legal here and comes back as ``""``: the
    points are the pattern and the header is metadata, so losing the second is a
    thinner answer rather than no answer.
    """
    root = _xml(_member(zip_archive, "root.xml", path=path), path=path,
                what="root.xml")
    out: list[tuple[str, str]] = []
    for group in root:
        tag = group.tag.rpartition("}")[2]
        if not _DATA_GROUP.match(tag):
            continue
        members = [c.get("Name") or "" for c in group
                   if c.tag.rpartition("}")[2] == "ContentHashList"]
        profile = next((m for m in members if m.lower().endswith(".txt")), None)
        # matched on "…conditions….xml", not on the exact spelling: the real
        # files say "MesurementConditions0.xml" and this reader does not want to
        # depend on Rigaku keeping the typo
        conditions = next((m for m in members
                           if "conditions" in m.lower() and
                           m.lower().endswith(".xml")), "")
        if profile is not None:
            out.append((f"{tag}/{profile}",
                        f"{tag}/{conditions}" if conditions else ""))
    if not out:
        raise ValueError(f"{path.name}: root.xml names no profile — a .rasx "
                         "stores each scan as a Data<N> group carrying a "
                         "Profile<N>.txt, and this archive declares none")
    return out


def _points(zip_archive: zipfile.ZipFile, member: str, *, path: Path) -> np.ndarray:
    """One profile's rows: 2θ, intensity, and the attenuator factor when written."""
    text = decode(_member(zip_archive, member, path=path))[0]
    rows: list[list[float]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            values = [float(v) for v in line.split()[:3]]
        except ValueError:
            raise ValueError(f"{path.name}: line {number} of {member} is not a "
                             f"row of numbers: {line.strip()!r}") from None
        if len(values) < 2:
            raise ValueError(f"{path.name}: line {number} of {member} has one "
                             "column; a point is 2θ and an intensity")
        rows.append(values)
    if not rows:
        raise ValueError(f"{path.name}: {member} holds no points")
    # narrowest row wins, so a file that stops writing the attenuator part-way
    # through is two columns rather than a ragged array numpy complains about
    # without naming a file
    width = min(len(r) for r in rows)
    return np.array([r[:width] for r in rows], dtype=np.float64)


def _conditions(zip_archive: zipfile.ZipFile, member: str, *,
                path: Path) -> dict[str, str]:
    """The header, flattened to the leaf names this reader actually reads.

    Flattened rather than walked because the interesting values sit at three
    different depths (``ScanInformation/AxisName``, ``XrayGenerator/TargetName``).
    The keys that are *not* unique — an ``Axis`` element per goniometer axis —
    carry their values in attributes rather than text, so they never enter here.

    ``ScanInformation`` is read **first and wins**, which is not tidiness: names
    like ``Step`` and ``Speed`` are generic enough for an optics or alignment
    block to carry one, and first-wins over the whole document would then derive
    the counting time — and therefore every σ — from somebody else's step.
    """
    if not member:
        return {}
    root = _xml(_member(zip_archive, member, path=path), path=path, what=member)
    scan = next((e for e in root.iter()
                 if e.tag.rpartition("}")[2] == "ScanInformation"), None)
    out: dict[str, str] = {}
    for source in (() if scan is None else scan.iter(), root.iter()):
        for element in source:
            name = element.tag.rpartition("}")[2]
            if element.text and element.text.strip() and name not in out:
                out[name] = element.text.strip()
    return out


def _count_time_s(header: dict[str, str]) -> float | None:
    """Seconds per step, or ``None`` when the header does not settle it.

    ``None`` rather than a default: the unit is what makes the number mean
    anything, and a σ derived from the wrong one is wrong by √60.
    """
    try:
        step, speed = float(header["Step"]), float(header["Speed"])
    except (KeyError, ValueError):
        return None
    seconds = _SPEED_UNIT_SECONDS.get(header.get("SpeedUnit", "").lower())
    if seconds is None or step <= 0 or speed <= 0:
        return None
    return step / speed * seconds


def _axis(header: dict[str, str], *, path: Path,
          diagnostics: list[Diagnostic] | None) -> str | None:
    """``ScanInformation/AxisName``, against the *vendor's* vocabulary.

    Shared with ``.ras`` rather than copied: the axis names are Rigaku's, and
    ``TwoThetaOmega`` means the same thing whichever container it arrives in.
    """
    axis = header.get("AxisName", "").strip()
    key = axis.lower().replace(" ", "").replace("-", "").replace("_", "")
    return check_axis(axis, path=path, field="ScanInformation/AxisName",
                      two_theta=key in RIGAKU_TWO_THETA_AXES,
                      other=RIGAKU_OTHER_AXES.get(key),
                      remedy="Export the θ–2θ scan instead.",
                      diagnostics=diagnostics)


def _label(header: dict[str, str], index: int, x: np.ndarray) -> str:
    """What the file calls this scan, else its own range — never "Scan N"."""
    for key in ("SampleName", "Comment", "Memo"):
        if (value := header.get(key, "").strip()):
            return value
    return f"{header.get('AxisName', '2θ')} {np.nanmin(x):.4g}–{np.nanmax(x):.4g}°"


def read_rasx(path: str | Path, *, scan: int | None = None,
              diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    with _archive(p) as zip_archive:
        groups = _groups(zip_archive, p)
        multiscan_default(len(groups), scan, path=p, diagnostics=diagnostics)

        index = 0 if scan is None else scan
        if not 0 <= index < len(groups):
            raise ValueError(f"{p.name} holds {len(groups)} scan(s), numbered 0 "
                             f"to {len(groups) - 1}; scan={index} is not one of "
                             "them")
        profile, conditions = groups[index]
        rows = _points(zip_archive, profile, path=p)
        header = _conditions(zip_archive, conditions, path=p)

    axis = _axis(header, path=p, diagnostics=diagnostics)
    rigaku_attenuator(rows[:, 0], rows[:, 2] if rows.shape[1] >= 3 else None,
                      path=p, diagnostics=diagnostics)
    count_time = _count_time_s(header)
    sigma = sigma_by_arithmetic(rows[:, 1], count_time,
                                header.get("IntensityUnit", ""), path=p,
                                keep=np.isfinite(rows[:, 0]),
                                diagnostics=diagnostics)
    tt, y, sig = ascending(rows[:, 0], rows[:, 1], sigma, path=p, fmt=RASX,
                           diagnostics=diagnostics)
    return pattern_data(
        p, tt, y, sig, source_file=p.name, format="rasx", scan=index,
        scan_count=len(groups), scan_axis=axis,
        sample=header.get("SampleName") or None,
        title=header.get("Comment") or None,
        anode=header.get("TargetName") or None,
        wavelength=header.get("WavelengthKalpha1") or None,
        wavelength_alpha2=header.get("WavelengthKalpha2") or None,
        intensity_unit=header.get("IntensityUnit") or None,
        count_time_s=count_time)


def list_rasx_scans(path: str | Path) -> list[ScanInfo]:
    out: list[ScanInfo] = []
    p = Path(path)
    with _archive(p) as zip_archive:
        for i, (profile, conditions) in enumerate(_groups(zip_archive, p)):
            x = _points(zip_archive, profile, path=p)[:, 0]
            out.append(ScanInfo(
                index=i, label=_label(_conditions(zip_archive, conditions, path=p),
                                      i, x),
                n_points=int(x.size),
                two_theta_range=(float(np.nanmin(x)), float(np.nanmax(x)))))
    return out


def looks_rasx(p: Path) -> bool:
    """Zip magic first, then the manifest's own member naming.

    Two gates because ``.brml`` is a zip too: the magic says "an archive" and
    only a ``Data<N>/Profile<N>.txt`` member says *whose*.  The archive is opened
    to answer that, which reads its central directory and not its contents.
    """
    if not head(p, n=len(ZIP_MAGIC)).raw.startswith(ZIP_MAGIC):
        return False
    try:
        with zipfile.ZipFile(p) as zip_archive:
            return any(_PROFILE_MEMBER.match(name) for name in zip_archive.namelist())
    except (zipfile.BadZipFile, OSError):
        return False


RASX = PatternFormat(
    name="rasx",
    title="Rigaku SmartLab Studio II measurement (.rasx)",
    extensions=(".rasx",),
    sniff="a zip archive holding a Data<N>/Profile<N>.txt member",
    sigma=("decided by arithmetic, exactly as for .ras — whole numbers are "
           "counts and get the Poisson fallback, an integral y·t is a rate and "
           "gets √(y·t)/t, and anything else withholds σ with "
           "PATTERN_INTENSITY_SCALED. The declared <IntensityUnit> is a claim: "
           "two of three real files say counts and store neither"),
    matches=looks_rasx,
    read=read_rasx,
    options=("scan",),
    scans=list_rasx_scans,
)
