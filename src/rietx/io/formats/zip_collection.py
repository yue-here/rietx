"""A plain ``.zip`` of patterns — N scans, one per member a reader here claims.

No vendor writes this.  It is what a person makes of a beamtime: a folder of
single-pattern files (GSAS ``.fxye``, ``.xye``, …) zipped for transport, which
this build could not open without extracting it first (issue #134, WP-1315).
It is the multi-range ``.raw`` idea with a weaker manifest, and the container
precedents are ``rasx.py`` and ``brml.py``.

**The member-name list is the only membership authority.**  A plain zip has no
manifest, so where a ``.rasx``'s ``root.xml`` says which members are scans and
in what order, here the names are all there is.  A member is a *pattern* when a
reader in :data:`~rietx.io.formats.PATTERN_FORMATS` claims it, by the same
dispatch :func:`~rietx.io.readers.identify_format` runs on a file, and
``scan=k`` reads the k-th pattern in **sorted name order**.  Skipped, and never
counted, so that ``k`` addresses a pattern and not a byte-blob:

- directory entries (a ``\\``-terminated one from Windows too) and empty members;
- dotfiles, which include an office suite's lock file (``.~lock.<name>#``, as
  the real archive carries) and macOS's ``__MACOSX/._<name>`` resource forks;
- a member no reader claims, and a member claimed only by a *refusal*
  (``dif_peaklist``, ``total_scattering``, ``raw_unclaimed``): those are
  recognised in order to be declined, so they are not patterns this build reads;
- a member that is itself a plain zip.  Nested containers are WP-1315's
  non-goal; a ``.rasx`` or ``.brml`` member is a pattern, since a reader here
  claims it by its manifest;
- a member past :data:`MAX_MEMBER_BYTES`, which no reader here would open.

A member that cannot be decompressed (corrupt, encrypted, a method ``zipfile``
cannot undo) is not skipped: whether it is a pattern cannot be known, so the
archive is claimed and its read refused, naming the member.  A member that
holds several scans of its own (a ``.rasx``, an ``.xrdml``) is refused too:
``scan=`` already selects the member, so its second scan could not be reached.

The ASCII reader claims any text that is not binary, so a text member that is
not a pattern (a log, a parameter file) counts as one, and reading it refuses,
naming the member.  That is the claim rule as WP-1315 states it.

**Reading a member is recursion into the normal dispatch, not a new parser.**
The member's bytes are read through the container cap, written to a file of
this module's own naming in a private temporary directory, claimed and read
there by the reader that claims it, and deleted before the call returns.  So a
``.fxye`` member is read by ``gsas``: its centidegree fold, its esd column and
its axis policy are the inner reader's, and this module decides no σ and no
axis.  The other reader options (``axis``, ``bank``, ``block``) are handed on
to that reader and reported there when it does not take them;
``nonpositive_sigma`` is ruled by :func:`~rietx.io.readers.read_pattern` on what
comes back, as for every format.

The temporary file is not ``extract()``, which the container rule in
``io/CLAUDE.md`` forbids.  The archive's name for a member never becomes a path:
only its last component's characters are kept, so a suffix the dispatch reads
(``.cif``, ``.gr``) still reaches it.  The bytes are capped before anything is
written, and one member is on disk at a time.  It exists because every reader
here takes a path, and gemmi reads one too.

**The pattern keeps its reader's metadata**, with ``source_file`` the member's
full name inside the archive and ``scan``/``scan_count`` the archive's own.
``scan_count`` comes from the one pass over the archive that the read makes.

**What a read costs.** That pass decompresses and stages every candidate member
to count the patterns, so one read of a large archive costs a pass over all of
it (measured on synthetic members: ~0.4 ms a small member), and reading every
pattern of an archive in turn is quadratic in its size.  ``list_scans`` reads
every member whole.  Nothing is cached between calls, for the reason
``base.head`` gives.
"""

from __future__ import annotations

import lzma
import re
import struct
import tempfile
import zipfile
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from . import rasx
from .base import PatternFormat, ScanInfo, head, multiscan_default, reader_options_for

#: The local-header magic a zip archive starts with, as for the vendor containers.
ZIP_MAGIC = rasx.ZIP_MAGIC

#: How much of any one member may be read: the cap every container here shares,
#: for the reason ``rasx`` gives.  A member past it is not a pattern this build
#: reads, so it is skipped rather than refused.
MAX_MEMBER_BYTES = rasx.MAX_MEMBER_BYTES

#: The two vendor manifests.  An archive carrying one is a ``.rasx`` or
#: ``.brml`` that its own reader declined, and its members are not this
#: format's to enumerate.
_VENDOR_MANIFEST = re.compile(r"(^|/)(root\.xml|DataContainer\.xml)$")

#: What may stand in a staged file's name; anything else becomes ``_``.
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._+-]")


@dataclass(frozen=True)
class _Member:
    """A member that a reader here claims, by its name inside the archive."""

    info: zipfile.ZipInfo
    reader: PatternFormat

    @property
    def name(self) -> str:
        return self.info.filename


def _archive(path: Path) -> zipfile.ZipFile:
    """The open archive, with ``zipfile``'s exception converted at this boundary."""
    try:
        return zipfile.ZipFile(path)
    except (zipfile.BadZipFile, NotImplementedError) as exc:
        raise ValueError(f"{path.name} begins like a zip archive but is not a "
                         f"readable one ({exc}); a zip that stops early is "
                         "usually a copy that was interrupted") from None


def _skipped(info: zipfile.ZipInfo) -> bool:
    """A directory entry, an empty member or a dotfile, which is never a pattern.

    The empty test reads the archive's declared size, trusted only to skip.
    """
    if info.is_dir() or info.filename.endswith("\\") or info.file_size == 0:
        return True
    return PurePosixPath(info.filename.replace("\\", "/")).name.startswith(".")


def _candidates(zip_archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """The members that may be patterns, in sorted name order.

    ``ZipInfo`` objects, not names: an archive may hold two members of one name,
    and ``open(name)`` would read the last of them twice.
    """
    infos = [i for i in zip_archive.infolist() if not _skipped(i)]
    return sorted(infos, key=lambda i: i.filename)


def _member_bytes(zip_archive: zipfile.ZipFile, info: zipfile.ZipInfo, *,
                  path: Path) -> bytes | None:
    """One member's bytes through :data:`MAX_MEMBER_BYTES`, ``None`` past it.

    The declared size is the archive's own claim, so it is trusted only to
    *skip* a member (a lying archive then hides one) and never to read one.
    """
    if info.file_size > MAX_MEMBER_BYTES:
        return None
    try:
        with zip_archive.open(info) as fh:
            raw = fh.read(MAX_MEMBER_BYTES + 1)
    except (zipfile.BadZipFile, EOFError, OSError, zlib.error, lzma.LZMAError,
            struct.error) as exc:
        raise ValueError(f"{path.name}: member {info.filename!r} could not be "
                         f"decompressed ({exc})") from None
    except (RuntimeError, NotImplementedError) as exc:
        # an encrypted member, or a compression method zipfile cannot undo
        raise ValueError(f"{path.name}: member {info.filename!r} cannot be "
                         f"read ({exc})") from None
    return None if len(raw) > MAX_MEMBER_BYTES else raw


def _staged_name(member: str) -> str:
    """A file name for ``member`` in the staging directory: its last component,
    with anything but letters, digits and ``._+-`` replaced, so the suffix the
    dispatch reads survives and the archive's path never becomes one."""
    last = PurePosixPath(member.replace("\\", "/")).name
    safe = _SAFE_NAME.sub("_", last).lstrip(".") or "member"
    return safe[-120:]


@contextmanager
def _staging() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="rietx-zip-") as directory:
        yield Path(directory)


def _claim(staged: Path, raw: bytes) -> PatternFormat | None:
    """The reader that claims a staged member, or ``None``.

    The registry's own order, without this format: a zip inside is skipped
    rather than enumerated.  A refusal claiming it, or a plain zip that only a
    loose text sniff would claim (a stored one shows its first member's text to
    ``gsas``), is no pattern.
    """
    from . import PATTERN_FORMATS
    from .brml import BRML

    for fmt in PATTERN_FORMATS:
        if fmt is ZIP_COLLECTION:
            continue
        if fmt.matches(staged):
            if fmt.refuses is not None:
                return None
            if raw.startswith(ZIP_MAGIC) and fmt not in (rasx.RASX, BRML):
                return None
            return fmt
    return None


def _stage(directory: Path, zip_archive: zipfile.ZipFile, info: zipfile.ZipInfo,
           *, path: Path) -> tuple[Path, bytes] | None:
    """Write one member to ``directory``, or ``None`` when it is past the cap."""
    raw = _member_bytes(zip_archive, info, path=path)
    if raw is None:
        return None
    staged = directory / _staged_name(info.filename)
    staged.write_bytes(raw)
    return staged, raw


def _patterns(zip_archive: zipfile.ZipFile, directory: Path, *,
              path: Path) -> list[_Member]:
    """Every member a reader here claims, in sorted name order — the one pass."""
    out: list[_Member] = []
    for info in _candidates(zip_archive):
        staged = _stage(directory, zip_archive, info, path=path)
        if staged is None:
            continue
        try:
            reader = _claim(*staged)
        finally:
            staged[0].unlink()
        if reader is not None:
            out.append(_Member(info, reader))
    return out


def _read_member(zip_archive: zipfile.ZipFile, directory: Path, member: _Member,
                 *, path: Path, index: int, count: int,
                 options: dict[str, Any],
                 diagnostics: list[Diagnostic] | None) -> PatternData:
    """Read one claimed member by its own reader, naming the archive on refusal.

    What the reader says names the staged file, a name found neither in the
    archive nor on disk afterwards, so each message is rewritten to name the
    member and the archive instead.
    """
    staged = _stage(directory, zip_archive, member.info, path=path)
    if staged is None:                      # it was under the cap a moment ago
        raise ValueError(f"{path.name}: member {member.name!r} is larger than "
                         f"the {MAX_MEMBER_BYTES // (1024 * 1024)} MB a pattern "
                         "member may be, so it was not read")
    file = staged[0]
    here = f"{member.name} in {path.name}"

    def named(text: str) -> str:
        return text.replace(str(file), here).replace(file.name, here)

    inner: list[Diagnostic] = []
    try:
        kwargs = reader_options_for(member.reader, options, diagnostics=inner)
        data = member.reader.read(file, diagnostics=inner, **kwargs)
    except (ValueError, OSError) as exc:
        raise ValueError(f"{path.name}: member {member.name!r}, pattern "
                         f"{index} of the {count} the archive holds, was claimed "
                         f"by the {member.reader.title} reader and could not be "
                         f"read: {named(str(exc))}") from None
    finally:
        file.unlink()
    held = int(data.metadata.get("scan_count", "1"))
    if held > 1:
        # a member's own scans are a container inside the container, and scan=
        # already selects the member, so none past its first could be reached
        raise ValueError(f"{path.name}: member {member.name!r} is itself a "
                         f"{member.reader.title} holding {held} scans. A zip of "
                         "multi-scan files is not read; extract that member and "
                         "read it with scan=")
    if diagnostics is not None:
        diagnostics.extend(d.model_copy(update={"message": named(d.message)})
                           for d in inner)
    return data


def _out_of_range(path: Path, count: int, index: int) -> ValueError:
    return ValueError(f"{path.name} holds {count} pattern(s) this build can "
                      f"read, numbered 0 to {count - 1} in member-name order; "
                      f"scan={index} is not one of them")


def read_zip_collection(path: str | Path, *, scan: int | None = None,
                        diagnostics: list[Diagnostic] | None = None,
                        **options: Any) -> PatternData:
    p = Path(path)
    with _archive(p) as zip_archive, _staging() as directory:
        members = _patterns(zip_archive, directory, path=p)
        if not members:
            raise ValueError(f"{p.name} holds no member a reader in this build "
                             "claims, so it holds 0 patterns")
        multiscan_default(len(members), scan, path=p, diagnostics=diagnostics)
        index = 0 if scan is None else scan
        if not 0 <= index < len(members):
            raise _out_of_range(p, len(members), index)
        member = members[index]
        data = _read_member(zip_archive, directory, member, path=p, index=index,
                            count=len(members), options=options,
                            diagnostics=diagnostics)
    data.metadata.update(source_file=member.name, scan=str(index),
                         scan_count=str(len(members)))
    return data


def list_zip_collection_scans(path: str | Path) -> list[ScanInfo]:
    """One :class:`ScanInfo` per pattern, labelled with the member's name.

    Never "Scan N": the name is what the archive says about its member.  Each
    member is read whole to count its points, which is why this is the picker's
    route and not the preview's.
    """
    p = Path(path)
    out: list[ScanInfo] = []
    with _archive(p) as zip_archive, _staging() as directory:
        members = _patterns(zip_archive, directory, path=p)
        for i, member in enumerate(members):
            data = _read_member(zip_archive, directory, member, path=p, index=i,
                                count=len(members), options={}, diagnostics=None)
            x = np.asarray(data.x(), dtype=np.float64)
            temperature = data.metadata.get("temperature_k")
            out.append(ScanInfo(
                index=i, label=member.name, n_points=int(x.size),
                two_theta_range=(float(x.min()), float(x.max())),
                temperature_k=None if temperature is None else float(temperature)))
    return out


def looks_zip_collection(p: Path) -> bool:
    """Zip magic; then no vendor manifest, and a member some reader claims.

    An archive that begins with the magic and is not readable is claimed, so
    its refusal names it as a zip: left unclaimed, a stored one reaches
    ``gsas`` through its first member's text and fails on the archive's bytes.
    A member that cannot be decompressed claims it for the same reason.  An
    archive that opens is otherwise claimed only once a member is, and the
    search stops at the first.
    """
    if not head(p, n=len(ZIP_MAGIC)).raw.startswith(ZIP_MAGIC):
        return False
    try:
        zip_archive = zipfile.ZipFile(p)
    except (zipfile.BadZipFile, NotImplementedError):
        return True
    except OSError:
        return False
    with zip_archive, _staging() as directory:
        if any(_VENDOR_MANIFEST.search(n) for n in zip_archive.namelist()):
            return False
        for info in _candidates(zip_archive):
            try:
                staged = _stage(directory, zip_archive, info, path=p)
            except ValueError:
                return True                 # claimed, so the read refuses by name
            if staged is None:
                continue
            try:
                if _claim(*staged) is not None:
                    return True
            finally:
                staged[0].unlink()
    return False


ZIP_COLLECTION = PatternFormat(
    name="zip_collection",
    title="Zip archive of pattern files (.zip)",
    extensions=(".zip",),
    sniff=("a zip archive with no .rasx or .brml manifest, holding at least one "
           "member another reader claims; an archive that begins like a zip "
           "and cannot be opened is claimed in order to refuse it by name"),
    sigma=("the member's own reader's, unchanged — the archive adds no σ and "
           "no axis"),
    matches=looks_zip_collection,
    read=read_zip_collection,
    options=("axis", "bank", "block", "nonpositive_sigma", "scan"),
    scans=list_zip_collection_scans,
)
