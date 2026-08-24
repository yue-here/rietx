"""Getting data *in*: uploads, content sniffing and validated previews (WP-1014).

Everything before this work package assumed the data was already on the server's
filesystem — ``Project.create`` takes a pattern **path**, ``GuiSession.project_new``
takes server-side paths for all three inputs.  That is the right shape for a
script and useless in a browser, where the file the user is looking at is on
*their* side of the wire.

**Two phases, so a bad file never half-lands.**  An upload is staged and read
first; only what parses becomes an argument to a project verb.  Nothing is
created, no history node is written, and the project directory does not exist
until the commit step, so the failure mode of "wrong file" is a preview that says
what went wrong rather than a half-built ``.rex`` to clean up.  This is the same
shape the text document chose for a different reason (WP-1009: parse, diff, then
apply or apply nothing).

**A token crosses back, not a path.**  The preview returns an opaque token and
the commit verbs resolve it here.  Handing a filesystem path to the browser and
taking it back would make every commit verb a path-traversal surface, and the
staging directory is this session's to name — not the client's to choose.

**What the preview is for is the *decision*, not decoration.**  A pattern comes
back with the reader that claimed it, in that reader's own words, plus a decimated
curve so the file can be looked at before it becomes a project; a CIF comes back
with whether it actually carries an anisotropic-ADP loop, so the opt-in checkbox
that mirrors ``structure_from_cif(aniso=)`` is offered only when there is
something to opt into; an instrument profile comes back frozen, which is what
``load_instrument_profile`` means.

Nothing here knows about HTTP.  ``session.py`` calls it, ``server.py`` reads the
bytes off the socket, and a Tauri host would do neither differently.
"""

from __future__ import annotations

import hashlib
import shutil
import struct
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# the one package import at module level: every other one here is deferred into
# its function, and ``_about`` imports nothing itself, so it cannot cost what
# those defer
from .._about import PROJECT_SUFFIX, SERVER_TOKEN

#: A refusal, not a limit anyone will meet: the largest patterns here are a few
#: MB and a CIF is smaller.  It exists because ``Content-Length`` is a number the
#: client chose, and reading it into memory before checking it is how a localhost
#: server becomes a way to exhaust a machine's RAM.
MAX_UPLOAD_BYTES = 64 * 1024 * 1024

#: The three things a project is made of, and the three upload routes.
UPLOAD_KINDS = ("pattern", "cif", "instrument")

#: Prefix of this session's staging directory.  A named constant so the test
#: asserting a staged path never reaches a client pins *this* string rather
#: than a copy of it — a copy goes quiet, not red, when the prefix changes
#: (WP-1062).
UPLOAD_DIR_PREFIX = f"{SERVER_TOKEN}-upload-"

#: Points in a preview curve.  Enough to see the peaks and the background of a
#: 40 000-point pattern in a wizard step; the real plot fetches its own windows.
PREVIEW_POINTS = 900

#: What a failed read may throw before this route calls it a refusal.
#:
#: The **invariant** is that a reader raises ``ValueError`` or ``OSError`` and
#: names the file — enforced at each parser's own boundary and asserted by
#: ``tests/test_readers_robust.py``, which truncates every real fixture at
#: twenty offsets.  The rest of this tuple is a net, not a licence: the vendor
#: formats are containers, so a parser that forgets to convert would throw
#: ``struct.error``, ``zipfile.BadZipFile`` or ``ET.ParseError`` — and the last
#: subclasses ``SyntaxError``, so it escapes as a **500** on an upload route
#: rather than as "this file could not be read".  A localhost server handed a
#: browser's bytes should degrade to a 400, and the harness is what keeps the
#: net from quietly becoming the mechanism.
READER_FAILURES = (ValueError, OSError, RuntimeError, KeyError, IndexError,
                   struct.error, zipfile.BadZipFile, ET.ParseError)


class UploadRefused(ValueError):
    """An upload could not be accepted, carrying what the transport reports.

    Same grammar as :class:`~rietx.gui.session.GuiError`, which is what wraps
    it — this module raises rather than importing the session (that import runs
    the other way).
    """

    code = "UPLOAD_INVALID"
    status = 400

    def __init__(self, message: str, *, where: list[str] | None = None) -> None:
        super().__init__(message)
        self.where = list(where or [])


class UploadTooLarge(UploadRefused):
    code = "UPLOAD_TOO_LARGE"
    status = 413


class UnknownUpload(UploadRefused):
    code = "NOT_FOUND"
    status = 404


@dataclass(frozen=True)
class Upload:
    """One staged file: what it claims to be, where it landed, and its digest."""

    token: str
    kind: str
    filename: str
    path: Path
    size: int
    sha256: str

    def as_dict(self) -> dict:
        # deliberately no ``path``: see the module docstring
        return {"upload": self.token, "kind": self.kind, "filename": self.filename,
                "bytes": self.size, "sha256": self.sha256}


class UploadStore:
    """Staged uploads for one session, in a directory this process owns.

    Each upload gets its own subdirectory so two files may share a name and so
    the **suffix survives** — ``read_pattern`` dispatches ``.cif`` by suffix and
    everything else by content, so a staged file that lost its extension would
    read as ASCII columns and fail confusingly rather than as the pdCIF it is.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self._root = None if root is None else Path(root)
        self._items: dict[str, Upload] = {}

    @property
    def root(self) -> Path:
        if self._root is None:
            self._root = Path(tempfile.mkdtemp(prefix=UPLOAD_DIR_PREFIX))
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root

    def stage(self, kind: str, filename: str, data: bytes) -> Upload:
        if kind not in UPLOAD_KINDS:
            raise UploadRefused(f"unknown upload kind {kind!r}; "
                                f"expected one of {list(UPLOAD_KINDS)}",
                                where=["kind"])
        if not data:
            raise UploadRefused("the request body is empty; send the file's bytes "
                                "with ?filename=, or ?upload=<token> to re-read "
                                "one already staged", where=["body"])
        if len(data) > MAX_UPLOAD_BYTES:
            raise UploadTooLarge(
                f"{len(data)} bytes is over the {MAX_UPLOAD_BYTES}-byte upload "
                "limit", where=["body"])
        name = _safe_name(filename)
        token = uuid.uuid4().hex[:16]
        target = self.root / token
        target.mkdir(parents=True, exist_ok=True)
        path = target / name
        path.write_bytes(data)
        upload = Upload(token=token, kind=kind, filename=name, path=path,
                        size=len(data), sha256=hashlib.sha256(data).hexdigest())
        self._items[token] = upload
        return upload

    def get(self, token: str, kind: str | None = None) -> Upload:
        upload = self._items.get(token)
        if upload is None:
            raise UnknownUpload(
                f"no staged upload {token!r}; uploads live for the life of this "
                "session, so re-send the file", where=["upload"])
        if kind is not None and upload.kind != kind:
            raise UploadRefused(
                f"upload {token!r} was staged as a {upload.kind}, not a {kind}",
                where=["upload"])
        return upload

    def close(self) -> None:
        if self._root is not None and self._root.is_dir():
            shutil.rmtree(self._root, ignore_errors=True)
        self._items.clear()


def scrub(message: str, upload: Upload) -> str:
    """A reader's complaint with the staging path swapped for the sent filename.

    gemmi and the pattern readers quote the path they were handed, which here is
    a temp directory the client never named and must not learn — the point of a
    token.  The line and column in ``…/a1b2/evil.cif:1:0(0): expected block
    header`` are the useful part and survive.
    """
    return message.replace(str(upload.path), upload.filename)


def _safe_name(filename: str) -> str:
    """The basename of whatever the client sent, or a refusal.

    A filename from a browser is data, not a path: ``../../etc/passwd`` and
    ``C:\\Users\\x\\a.xye`` are both things a real client sends, and both are
    reduced to a leaf here rather than trusted.
    """
    leaf = Path(str(filename).replace("\\", "/").replace("\x00", "")).name.strip()
    if not leaf or leaf in (".", ".."):
        raise UploadRefused(
            f"{filename!r} is not a usable filename; send ?filename=<name.ext> — "
            "the extension is part of how a pattern file is recognised",
            where=["filename"])
    return leaf


# ----------------------------------------------------------------------
# previews
# ----------------------------------------------------------------------
def preview_pattern(upload: Upload, *, reader_options: dict[str, Any] | None = None,
                    suggest_in: Path | None = None) -> dict:
    """Read a staged pattern and describe it — reader included.

    The reader is named because *which reader claimed the file* is part of the
    reference a project records (WP-1005's ``DataRef``), and because the answer
    is not the extension: ``.XRA`` has no parser of its own, GSAS files are
    recognised by their ``BANK`` record in the first 4 kB, and the same bytes
    under two names read the same way.  So the preview quotes
    ``PatternFormat.sniff`` and ``.sigma`` verbatim rather than restating them.

    ``has_sigma`` is the one field here that is a *correctness* property rather
    than a description: it says whether the fit will weight by the file's own
    esd column or fall back to Poisson √max(y,1), which is invisible once the
    file is read.

    ``reader_options`` are :data:`~rietx.io.readers.READER_OPTIONS` keys, and
    the preview echoes back the **effective** ones rather than the requested
    ones — a form carries a ``block`` across a change of file, and what the
    control should then show is what this reader honoured.
    """
    import numpy as np

    from ..io.readers import identify_format, read_pattern, reader_options_for
    from ..viz.compare import decimation_index

    try:
        fmt = identify_format(upload.path)
    except ValueError as exc:
        raise UploadRefused(str(exc)) from None
    notes: list = []
    try:
        options = reader_options_for(fmt, reader_options or {}, diagnostics=notes)
    except ValueError as exc:
        raise UploadRefused(str(exc), where=["reader_options"]) from None
    try:
        data = read_pattern(upload.path, diagnostics=notes, **options)
    except READER_FAILURES as exc:
        raise UploadRefused(
            f"{upload.filename} looks like {fmt.title} but could not be read: "
            f"{type(exc).__name__}: {scrub(str(exc), upload)}") from None

    tt = np.asarray(data.two_theta, dtype=float)
    y = np.asarray(data.intensity, dtype=float)
    if tt.size < 2:
        raise UploadRefused(
            f"{upload.filename} parsed as {fmt.title} but holds {tt.size} "
            "point(s); a pattern needs at least two")
    idx = decimation_index(tt, [y], PREVIEW_POINTS)
    steps = np.diff(tt)
    return {
        **upload.as_dict(),
        "format": {"name": fmt.name, "title": fmt.title, "sniff": fmt.sniff,
                   "sigma": fmt.sigma, "options": list(fmt.options)},
        "reader_options": {k: str(v) for k, v in options.items()},
        # what the reader repaired or assumed.  The wizard is where a human
        # should see a repair — a project records no such field, because these
        # are a deterministic function of bytes + reader + options and all three
        # are already in ``DataRef``
        "diagnostics": [d.model_dump() for d in notes],
        "n_points": int(tt.size),
        "two_theta_range": [float(tt[0]), float(tt[-1])],
        "step": float(np.median(steps)) if steps.size else None,
        "has_sigma": data.sigma is not None,
        "metadata": dict(data.metadata or {}),
        # what the file already knows about its instrument — a *suggestion*, and
        # ``None`` where the header contradicts itself rather than a guess
        "instrument_hint": suggest_instrument(data.metadata),
        "curve": {"two_theta": tt[idx].tolist(), "intensity": y[idx].tolist(),
                  "n_returned": int(len(idx))},
        # a project is a directory on *this* machine and the browser cannot pick
        # one; the server's working directory is where ``rietx gui`` was
        # started, which is the only place a user has already pointed at
        "suggested_project": str(
            (Path(suggest_in) if suggest_in is not None else Path.cwd())
            / f"{Path(upload.filename).stem}{PROJECT_SUFFIX}"),
    }


def preview_cif(upload: Upload, *, aniso: bool = False,
                phase_name: str | None = None) -> dict:
    """Read a staged CIF as a structure, and say what opting into aniso would buy.

    ``aniso_available`` is **measured, not assumed**: the file is read a second
    time with ``aniso=True`` and the answer is whether any site came back with a
    tensor.  A checkbox offered on every CIF would be a control that does nothing
    on most of them, and the invariant it mirrors — reading a file must not
    silently change what a plan frees — is only legible when the UI can say
    whether there is anything to change.
    """
    from ..crystallography.cif import structure_from_cif

    structure = _read_cif(upload, aniso=aniso, phase_name=phase_name)
    aniso_available, aniso_error = False, ""
    if aniso:
        aniso_available = _has_aniso(structure)
    else:
        try:
            aniso_available = _has_aniso(
                structure_from_cif(str(upload.path), aniso=True,
                                   phase_name=phase_name))
        except (ValueError, OSError, RuntimeError) as exc:
            # the isotropic read succeeded, so this is a fact about the aniso
            # loop alone — worth reporting beside a disabled checkbox rather
            # than failing an import that does not need it
            aniso_error = f"{type(exc).__name__}: {scrub(str(exc), upload)}"

    return {
        **upload.as_dict(),
        "structure": structure.model_dump(mode="json"),
        "aniso": bool(aniso),
        "aniso_available": aniso_available,
        "aniso_error": aniso_error,
        "phases": [phase_summary(phase) for phase in structure.phases],
        "unknown_species": unknown_species(structure),
    }


def preview_instrument(upload: Upload) -> dict:
    """Read a staged instrument-profile file — frozen, as the loader returns it."""
    from ..io.instrument_profile import load_instrument_profile

    try:
        instrument = load_instrument_profile(upload.path)
    except (ValueError, OSError, KeyError) as exc:
        raise UploadRefused(
            f"{upload.filename} is not a rietx instrument profile: "
            f"{type(exc).__name__}: {scrub(str(exc), upload)}") from None
    return {**upload.as_dict(),
            "instrument": instrument.model_dump(mode="json"),
            "summary": instrument_summary(instrument),
            # not a caveat, the loader's contract: a calibration is data, and a
            # fresh background is attached because the old one described another
            # measurement (io.instrument_profile)
            "frozen": True}


def _read_cif(upload: Upload, *, aniso: bool, phase_name: str | None):
    from ..crystallography.cif import structure_from_cif

    try:
        return structure_from_cif(str(upload.path), aniso=aniso,
                                  phase_name=phase_name)
    except (ValueError, OSError, RuntimeError) as exc:
        raise UploadRefused(
            f"could not read a structure from {upload.filename}: "
            f"{type(exc).__name__}: {scrub(str(exc), upload)}") from None


def _has_aniso(structure) -> bool:
    return any(atom.aniso is not None
               for phase in structure.phases for atom in phase.atoms)


def phase_summary(phase) -> dict:
    """What an import step shows about a phase before committing to it."""
    return {"name": phase.name, "space_group": phase.space_group,
            "cell": [phase.cell.a.value, phase.cell.b.value, phase.cell.c.value,
                     phase.cell.alpha.value, phase.cell.beta.value,
                     phase.cell.gamma.value],
            "n_atoms": len(phase.atoms),
            "species": sorted({atom.species for atom in phase.atoms}),
            "n_aniso": sum(1 for atom in phase.atoms if atom.aniso is not None)}


def instrument_summary(instrument) -> dict:
    return {"geometry": instrument.geometry.kind,
            "wavelengths": [line.wavelength.value
                            for line in instrument.source.lines],
            "n_lines": len(instrument.source.lines),
            "polarization": instrument.source.polarization.value,
            "dispersion": instrument.source.dispersion is not None,
            "background": instrument.background.kind}


def unknown_species(structure) -> list[dict]:
    """Atoms whose scattering species no form-factor table here knows.

    A :class:`~rietx.schemas.structure.Structure` validates fine with a species
    like ``"D"`` or ``"Xx"`` — nothing looks the symbol up until a stage compiles,
    which is a long way from where it was typed.  This is what lets the import
    flow (and ``PATCH /api/structure``) say so at the point of entry, naming the
    atom, rather than at the point of failure.
    """
    from ..crystallography.scattering import normalize_species

    out = []
    for i, phase in enumerate(structure.phases):
        for j, atom in enumerate(phase.atoms):
            try:
                normalize_species(atom.species)
            except KeyError:
                out.append({"path": f"phases.{i}.atoms.{j}",
                            "label": atom.label, "species": atom.species})
    return out


# ----------------------------------------------------------------------
# building an instrument the wizard can ask for
# ----------------------------------------------------------------------
#: ``preset name → the keyword arguments its constructor takes``.  Declared as
#: data and pinned against ``inspect.signature`` by a meta-test, for the reason
#: every registry here is: an argument added to ``Instrument.bragg_brentano``
#: should either reach the import form or fail a test, never be silently
#: unreachable.  The presets themselves are the authority on *wavelengths* —
#: an anode name resolves against the package's NIST-scale table (WP-0507), so
#: no client ever types a wavelength for a named anode.
INSTRUMENT_PRESETS: dict[str, tuple[str, ...]] = {
    "debye_scherrer": ("wavelength", "polarization", "goniometer_radius_mm",
                       "capillary_radius_mm", "packing_fraction", "mu_r"),
    "bragg_brentano": ("radiation", "goniometer_radius_mm",
                       "monochromator_two_theta", "ka2_ratio", "mu_t",
                       "thickness_mm"),
    "flat_plate_transmission": ("radiation", "mu_t", "thickness_mm",
                                "packing_fraction", "ka2_ratio"),
}


#: How close a file's own wavelength must be to a table value to *be* that
#: anode.  Loose enough to absorb the ~3 ppm spread between vendor headers and
#: the package's NIST-scale table (1.540598 and 1.540593 against 1.5405929),
#: tight enough that no two anodes overlap — the closest pair here differ by 13 %.
WAVELENGTH_RTOL = 5e-4


def _anode_candidates() -> dict[str, tuple[float, float, float]]:
    """Per anode, the **three** wavelengths a file may legitimately quote.

    Kα1, Kα2, and the intensity-weighted mean (2λ₁ + λ₂)/3 — the last because it
    is what ``.uxd`` and older exports actually write (1.5418 for Cu), and 1.5418
    against Kα1 is 7.8e-4 relative, *outside* :data:`WAVELENGTH_RTOL`.  Without
    the mean in the candidate set the most common lab metadata value in existence
    would read as "the name and the wavelength disagree" and suppress the hint.
    """
    from ..schemas.instrument import _KA_DOUBLETS

    return {name: (a1, a2, (2.0 * a1 + a2) / 3.0)
            for name, (a1, a2) in _KA_DOUBLETS.items()}


def _number(metadata: dict, key: str) -> float | None:
    try:
        value = float(metadata[key])
    except (KeyError, TypeError, ValueError):
        return None
    return value if value > 0.0 else None


def _by_wavelength(wavelength: float | None) -> str | None:
    """The one anode whose Kα1, Kα2 or weighted mean ``wavelength`` is."""
    if wavelength is None:
        return None
    hit = [name for name, lines in _anode_candidates().items()
           if any(abs(wavelength - line) <= WAVELENGTH_RTOL * line
                  for line in lines)]
    return hit[0] if len(hit) == 1 else None


def _by_name(anode: str | None) -> str | None:
    """The anode a file *names*, as a radiation key — ``Cu`` → ``CuKa``."""
    if not anode:
        return None
    element = "".join(c for c in str(anode) if c.isalpha())[:2].capitalize()
    return element + "Ka" if element + "Ka" in _anode_candidates() else None


def suggest_instrument(metadata: dict | None) -> dict | None:
    """What the file already knows about its instrument, as a preset spec.

    A vendor header states the anode and the wavelength, and the import wizard
    currently makes a person type both.  Matching them is a *physics* judgement
    against the package's radiation table, so it happens here and not in
    TypeScript — a client-side match would be a second copy of the anode
    vocabulary, kept in a different language.

    **Wavelength first**, because a name is a label and a number is a
    measurement, and the number is checked against three candidates per anode
    (:func:`_anode_candidates`).  Then:

    * name and wavelength agreeing, or only one of them present → that anode's
      **doublet** preset.  The weighted mean resolves to the doublet too: it is
      a way of *writing* a doublet, not a different beam;
    * the file saying it has **no Kα2** — a recorded Kα2 wavelength of zero, as
      a Bruker v4 header writes for an incident-beam monochromator — → the
      ``…Ka1`` radiation, which is a real distinction ``_RADIATIONS`` carries;
    * a wavelength matching **no** anode → ``debye_scherrer`` at that
      wavelength, which is the synchrotron and monochromated case and the one
      where the file does know better than any preset;
    * name and wavelength **disagreeing** → ``None``.  That file is one to look
      at, not to guess from, and a wrong pre-fill is worse than an empty form
      because it looks like it was read.

    ``goniometer_radius_mm`` rides along where the file records one, which is
    the actual win: two of ``bragg_brentano``'s four numbers then come from the
    file instead of from a person.
    """
    metadata = metadata or {}
    wavelength = _number(metadata, "wavelength")
    named = _by_name(metadata.get("anode"))
    matched = _by_wavelength(wavelength)

    # a contradiction, not a default — and "matches no anode at all" is one of
    # them when the file also names one, which is why the test is against
    # ``matched`` rather than against a second anode having been found
    if named is not None and wavelength is not None and matched != named:
        return None
    anode = matched or named
    if anode is None:
        if wavelength is None:
            return None
        return {"preset": "debye_scherrer", "wavelength": wavelength,
                "why": (f"the file gives λ = {wavelength:g} Å, which is no "
                        "characteristic Kα line — a monochromated or "
                        "synchrotron beam, where the file knows better than "
                        "any anode preset")}

    # a *recorded* Kα2 of zero is the file saying there is none; a format that
    # does not record the field at all says nothing, and gets the doublet
    silent = "wavelength_alpha2" not in metadata
    radiation = anode if silent or _number(metadata, "wavelength_alpha2") else anode + "1"
    spec: dict[str, Any] = {"preset": "bragg_brentano", "radiation": radiation}
    radius = _number(metadata, "goniometer_radius_mm")
    if radius is not None:
        spec["goniometer_radius_mm"] = radius
    how = ("its wavelength" if matched and not named else
           "its anode" if named and not matched else
           "its anode and wavelength agreeing")
    spec["why"] = (f"{how} → {radiation}"
                   + (f", and the goniometer radius it records ({radius:g} mm)"
                      if radius is not None else ""))
    return spec


def instrument_from_preset(spec: dict) -> Any:
    """``{"preset": name, ...}`` → an :class:`Instrument` built by the package.

    The wizard sends the *decision* (a geometry and an anode) and the package
    supplies the physics: the emission wavelengths come from ``_RADIATIONS``,
    the polarization constant from the monochromator angle, the doublet from the
    anode.  A form that posted a whole ``Instrument`` would be a second copy of
    all three, kept in TypeScript.

    Refusals are the constructors' own — an unknown anode lists the ones that
    exist, ``bragg_brentano`` without a goniometer radius says so — because they
    are already the right sentences.
    """
    from ..schemas.instrument import Instrument

    name = str(spec.get("preset") or "")
    if name not in INSTRUMENT_PRESETS:
        raise UploadRefused(
            f"unknown instrument preset {name!r}; available: "
            f"{sorted(INSTRUMENT_PRESETS)}", where=["instrument.preset"])
    allowed = INSTRUMENT_PRESETS[name]
    extra = sorted(set(spec) - {"preset", *allowed})
    if extra:
        raise UploadRefused(
            f"{name} takes {list(allowed)}; it does not take {extra}",
            where=[f"instrument.{k}" for k in extra])
    kwargs = {k: spec[k] for k in allowed if spec.get(k) is not None}
    if name == "debye_scherrer" and "wavelength" not in kwargs:
        raise UploadRefused(
            "debye_scherrer needs a wavelength in Å — it is the one geometry "
            "with no anode to read one from", where=["instrument.wavelength"])
    try:
        if name == "debye_scherrer":
            return Instrument.debye_scherrer(**kwargs)
        return getattr(Instrument, name)(**kwargs)
    except (ValueError, TypeError) as exc:
        raise UploadRefused(f"{name}: {exc}", where=["instrument"]) from None
