"""The GUI's session model — every verb, and not one line of HTTP (WP-1008).

``server.py`` is transport: it parses a path, calls a method here, and serialises
what comes back.  Everything a client can *do* is a plain method on
:class:`GuiSession`, which is what makes the transport swappable — a Tauri
command handler, a notebook driver or a test calling the verbs directly all get
the same surface, and none of them needs a socket.

Three rules shape it.

**One project per session, and its head is the working state.**  The project
container (WP-1005) already decided that ``project.json`` holds the settings and
``history.jsonl`` holds the model, so this object adds no third store: a verb
that changes a parameter commits a history node, a verb that changes a setting
rewrites ``project.json`` immediately.  A GUI therefore has nothing to warn about
on close — which is a property to preserve, not a coincidence, so every settings
verb here persists rather than deferring to :meth:`Project.save`.

**Mutating verbs refuse while a run is in flight.**  Not politeness:
frozen-per-stage discreteness (CLAUDE.md) says the hkl list, the symmetry-op
subsets and the window ranges are computed at stage compile and never change
during a least-squares run.  A ``PATCH /api/params`` mid-stage would edit the
models the compiled state was derived from.  Enforcing it at the session
boundary makes that structurally impossible rather than a thing to remember, and
:class:`GuiError` carries the 409 the transport reports.

**The run is watched through events, not by polling state.**  One worker thread,
one :class:`~rietx.optimize.cancel.CancelToken`, and a seq-numbered ring
buffer of the engine's own event dicts with a ``Condition`` for followers.  The
buffer is a *transport* of the same stream that lands under
``<project>/live/`` — since WP-1403 in a run directory of its own, written by
the recorder ``Project.fit`` defaults there — so ``rietx watch`` and the GUI
are two views of one log rather than two logs.

The one place this session adds a frame the engine does not emit is the **run
state**: a fit that raises emits no ``fit_end``, so a follower watching only
engine events would wait forever on a failed run.  ``EventKind`` is a closed set
and WP-1006 deliberately declined to add a kind for a guess, so the state frame
is *not* an event — it travels beside them (a separate SSE frame type, a separate
key in the poll fallback) and is never written to the log.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Literal

from .. import _about
from ..capabilities import capabilities as _capabilities
from ..help import help_registry as _help_registry
from ..history.events import EventStream
from ..optimize.cancel import CancelToken, RefinementCancelled
from ..project import Project
from ..refine import (
    _VERSION,
    NoPhasesError,
    _refuse_without_phases,
    mode_fixed_column,
)
from ..report.apply import api_call, describe_action, refusal, stage_for
from ..schemas.instrument import Instrument
from ..schemas.plan import PlanSpec, StageSpec
from ..schemas.structure import Structure
from ..strategy.staged import PLAN_PRESETS, resolve_plan
from ..viz import packed as _packed
from ..viz import theme
from ..viz.compare import decimation_index
from ..viz.packed import Packed
from . import series as series_mod
from . import symmetry
from .imports import (
    UPLOAD_KINDS,
    UploadRefused,
    UploadStore,
    instrument_from_preset,
    preview_cif,
    preview_instrument,
    preview_pattern,
    scrub,
    unknown_species,
)

#: ``idle`` → ``running`` → (``cancelling``) → ``idle``.  There is no ``failed``
#: state: a failure ends the run, and *what* happened is on the run record.
RunState = Literal["idle", "running", "cancelling"]

#: Events kept for replay.  A staged fit on a real pattern emits one ``eval``
#: per residual evaluation — thousands — so the ring is a window, not an
#: archive; ``events_since`` reports its oldest seq so a client that fell behind
#: can tell it missed some instead of silently renumbering.  The log on disk is
#: the archive.
EVENT_RING = 4096

_MAX_RECENT = 12

#: How many predicted positions one candidate overlay carries (WP-1211).
#: A cap rather than a budget, because past it the picture stops being a set of
#: lines: the largest cell ``max_d_axis`` admits — 25 Å triclinic — predicts
#: 92 103 Laue-unique positions over 5-120° at a Cu doublet and 460 649 over
#: 1-60° at a synchrotron λ (measured; ``tests/test_gui_peaks.py`` exercises the
#: first), which is megabytes of JSON drawn as a solid block of ink.  Corundum
#: over the same lab range is 124 and a real lab candidate 426, so this is a
#: guard against the pathological case and not a budget on the ordinary one.
#: Over the cap the answer is thinned **by rank in 2θ**, which
#: is the property it is read for — a dense stretch keeps proportionally more
#: lines than a sparse one, so "this cell predicts lines the pattern lacks"
#: still reads — and ``n_total`` says what was dropped, because a silent cap
#: reads as coverage (CLAUDE.md).
MAX_CANDIDATE_TICKS = 2000

#: Routes whose *shape* is settled here but whose behaviour belongs to a later
#: work package.  Declared rather than omitted so the frontend scaffold can be
#: written against the final path set, and answered with the WP that will fill
#: them in — a 404 saying "not yet, here is who" is a design document a client
#: can read at runtime.  Empty since WP-1027 filled in the peak/index family;
#: the mechanism stays for the next reserved surface.
RESERVED_ROUTES: dict[tuple[str, str], str] = {}

#: ``kind → default filename``.  The route table's export family is built from
#: this, so a kind added here is reachable from the wire with no second list.
EXPORT_DEFAULTS = {
    "cif": "refinement.cif",
    "reflections": "reflections.csv",
    "qpa": "qpa.csv",
    "html": "fit.html",
    "result_json": "result.json",
    "instrument_profile": "instrument_profile.json",
}

#: Exports that describe the **model** rather than a fit, and are therefore
#: gated on a project alone.  Declared as the exception, so the default for a
#: new kind is the stricter gate: an export of a fit written before one has run
#: is an empty file, while an instrument profile is exactly the state a
#: calibration is frozen *from* — the file is written to be loaded into the next
#: sample's project, and the fit that produced it has already been run and its
#: numbers already stand in the model (WP-1214).
_EXPORT_MODEL_ONLY = frozenset({"instrument_profile"})


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class GuiError(Exception):
    """A verb refused, carrying what the transport should report.

    Same grammar as :class:`~rietx.schemas.diagnostics.Diagnostic` and the
    agent envelope (WP-0602): a ``code`` to branch on, a message for a human,
    and ``where`` naming the paths at fault.  The HTTP status lives here rather
    than in the router because the reason is what decides it — a run in flight
    is a 409 wherever it is reported.
    """

    def __init__(self, message: str, *, code: str = "INVALID_REQUEST",
                 status: int = 400, where: list[str] | None = None,
                 details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.where = list(where or [])
        #: per-item failures, as ``AgentError.details`` does it — a text document
        #: apply reports every bad line at once, because fixing them one HTTP
        #: round trip at a time is not an editing experience
        self.details = list(details or [])

    def payload(self) -> dict:
        return {"error": {"code": self.code, "message": self.message,
                          "where": self.where, "details": self.details}}


class GuiSession:
    """One project, one run at a time, and every GUI verb as a method.

    ``project`` may be ``None``: the app opens before a project exists, and the
    verbs that need one raise ``NO_PROJECT`` rather than pretending.
    """

    def __init__(self, project: Project | None = None, *, backend: str = "numpy",
                 solver: str = "trf", state_dir: str | Path | None = None) -> None:
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self.project = project
        self.backend = backend
        self.solver = solver
        # one expression, shared with the two Python pages that *read* the
        # theme this session writes (WP-1429): a reader resolving a different
        # directory is a bug that looks like the choice not sticking
        self.state_dir = theme.state_dir(state_dir)
        #: staged uploads (WP-1014).  Session-scoped on purpose: a token is only
        #: meaningful to the process that issued it, and the directory goes away
        #: with :meth:`close` rather than accumulating in a temp dir.
        self.uploads = UploadStore()
        self.closed = False

        self._state: RunState = "idle"
        self._cancel: CancelToken | None = None
        self._worker: threading.Thread | None = None
        self._events: deque[dict] = deque(maxlen=EVENT_RING)
        self._seq = 0
        self._n_eval = 0
        self._run: dict = _idle_run()
        #: the last completed indexing run's answer.  Session-scoped like
        #: ``refinement.result_``: peaks.json is the durable artifact, an
        #: IndexingResult is a computation over it.
        self._index_result = None
        #: ``{"screen": ExtinctionScreen, "candidate": int}`` — the last
        #: extinction screen, valid only against the ``_index_result`` it was
        #: asked of (a new indexing run renumbers the candidates, so it clears
        #: this).  WP-1025 through WP-1027's surface.
        self._extinction = None
        #: ``(cache key, PeakEditor)`` — the editor holds the lazily built
        #: Detection; the key is everything a detection depends on
        self._peak_ed: tuple[tuple, Any] | None = None
        #: the staged series and its chain settings (WP-1016).  Session-scoped
        #: because its patterns are upload tokens, which die with ``close`` —
        #: a *persisted* series would need a document, which is WP-1003's to
        #: decide rather than this WP's to add.
        self._series = series_mod.SeriesSetup()
        #: the last completed series run: the ``SequentialRefinement`` (which
        #: holds each pattern's full result and its own history tree) beside the
        #: serializable ``SeriesResult``.  One object, so "is there an answer"
        #: cannot be two answers.
        self._series_run: dict | None = None
        if project is not None:
            self._remember(project.path)

    # ------------------------------------------------------------------
    # introspection
    # ------------------------------------------------------------------
    def capabilities(self) -> dict:
        """:func:`rietx.capabilities`, verbatim — the client's one guess-free call."""
        return _capabilities().model_dump(mode="json")

    def help(self) -> dict:
        """The whole help corpus, plus the base its anchors are relative to.

        Static for the life of the build, and needs no project, so it sits
        beside :meth:`capabilities` rather than behind the in-flight 409: a
        person reading what a parameter means while a run works is not editing
        anything.  A parameter row carries only its ``help_key``, which indexes
        the ``parameters`` arm here.

        ``docs_url`` rides beside the arms rather than inside one because it is
        not a name anything is looking up: an entry's ``anchor`` is a manual
        page and heading (``corrections.html#surface-roughness``), so the one
        thing a client needs to turn it into a link is where the manual lives —
        and a frontend that spelled that out would be the second authority on
        it (root CLAUDE.md's ``_about`` rule).
        """
        return {**_help_registry(), "docs_url": _about.DOCS_URL}

    def spacegroup(self, symbol: str) -> dict:
        """What one space-group symbol *is*, and what it costs the cell.

        Project-free, beside :meth:`capabilities` and :meth:`help` for the same
        reason: it is a fact about a symbol, not about a model, and the one
        caller that needs it — the wizard's typed-cell step (WP-1206) — runs
        before any project exists.  The same
        :func:`~rietx.gui.symmetry.symbol_facts` the model panel's phase summary
        rides on, so the two cannot disagree about what a setting constrains.

        ``free_cell`` is why it exists: the form draws the boxes this names, so
        a cell parameter the symmetry determines is never offered and the
        client holds no copy of the constraint rule.

        An unresolvable symbol is a refusal here, not an ``error`` row.  The
        row shape belongs to :func:`~rietx.gui.symmetry.phase_facts`, whose job
        is to keep a panel rendering over a model that cannot resolve its own
        symbol; this route is a lookup, and a symbol with no answer has none.
        """
        text = str(symbol or "").strip()
        if not text:
            raise GuiError("'space_group' is required", where=["space_group"])
        try:
            return symmetry.symbol_facts(text)
        except (ValueError, RuntimeError) as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=["space_group"]) from None

    def version(self) -> dict:
        return {"package_version": _VERSION, "pid": os.getpid(),
                "backend": self.backend, "solver": self.solver,
                "project": None if self.project is None else str(self.project.path)}

    # ------------------------------------------------------------------
    # uploads (WP-1014)
    # ------------------------------------------------------------------
    def upload(self, kind: str, *, data: bytes | None = None, filename: str = "",
               token: str = "", options: dict | None = None) -> dict:
        """Stage a file (or re-read one already staged) and describe it.

        The two argument shapes are the two halves of one flow: **bytes plus a
        filename** stage a new file, **a token** re-reads one with different
        options — which is what the aniso checkbox and the pdCIF block picker
        need, since flipping either must not mean re-uploading a file the server
        already has.

        Not idle-gated.  An upload reads its own staged copy and touches neither
        the models nor the project, so it is one of the few verbs that is safe
        while a fit runs; the *commit* verbs it feeds are all idle-only already.
        """
        opts = dict(options or {})
        try:
            if kind not in UPLOAD_KINDS:
                raise UploadRefused(f"unknown upload kind {kind!r}; expected one "
                                    f"of {list(UPLOAD_KINDS)}", where=["kind"])
            if data:
                staged = self.uploads.stage(kind, filename, data)
            elif token:
                staged = self.uploads.get(token, kind)
            else:
                raise UploadRefused(
                    "send the file's bytes with ?filename=<name>, or "
                    "?upload=<token> to re-read one already staged",
                    where=["upload"])
            if kind == "pattern":
                from ..io.readers import READER_OPTIONS
                return preview_pattern(staged, reader_options={
                    k: v for k, v in opts.items() if k in READER_OPTIONS})
            if kind == "cif":
                return preview_cif(staged, aniso=bool(opts.get("aniso")),
                                   phase_name=opts.get("phase_name"))
            return preview_instrument(staged)
        except UploadRefused as exc:
            raise GuiError(str(exc), code=exc.code, status=exc.status,
                           where=exc.where) from None

    def upload_scans(self, token: str) -> dict:
        """What there is to choose between in a staged multi-scan file.

        A **separate** route from the preview on purpose.  ``scan_count`` travels
        in the pattern's own metadata from the single read the preview already
        did, so showing "3 scans" never costs a second parse of a 60 MB file;
        *labelling* them does, because a label is the file's own comment or the
        range each scan stepped through, and neither is knowable without walking
        the ranges.  So the picker fetches this when a person opens it, and a
        wizard that never touches the control never pays for it.

        Refused rather than answered with a one-element list for a format that
        holds one measurement per file: "this file has one scan" and "this format
        has no scan structure" are different answers.
        """
        from ..io.readers import list_scans

        try:
            staged = self.uploads.get(token, "pattern")
            return {"scans": [
                {"index": s.index, "label": s.label, "n_points": s.n_points,
                 "two_theta_range": list(s.two_theta_range)}
                for s in list_scans(staged.path)]}
        except UploadRefused as exc:
            raise GuiError(str(exc), code=exc.code, status=exc.status,
                           where=exc.where) from None
        except (ValueError, OSError) as exc:
            raise GuiError(str(exc), code="upload_refused", status=400,
                           where=["scan"]) from None

    # ------------------------------------------------------------------
    # project
    # ------------------------------------------------------------------
    def project_new(self, body: dict) -> dict:
        """``Project.create`` from a request body.

        Each of the three inputs takes a server-side path *or* the token of a
        staged upload (WP-1014), which is the whole of the commit step: the file
        was read once already, so a project is only ever created around bytes
        that parsed.  ``structure`` is an inline :class:`Structure` dict,
        ``{"cif": path}`` or ``{"upload": token, "aniso": bool}``; ``instrument``
        is an inline dict, ``{"preset": name, …}`` or ``{"upload": token}``, and
        is **required** because :class:`Instrument` has no default source and
        guessing a diffractometer is exactly the kind of silent assumption this
        package refuses.

        ``structure`` takes a fourth form since WP-1206: ``{"space_group":
        symbol, "cell": {…}}``, the Le Bail scaffold a person types when there
        is no CIF; and a fifth since WP-1207: ``null``, a **pattern-only**
        project with no phase at all, whose phase you find by indexing it.
        The key itself stays required — a client that forgot it is told so
        rather than handed a phase-free project.  ``mode`` is then **refused** at ``"rietveld"`` rather than
        overridden — a Rietveld fit over a dummy carbon is not a thing to offer,
        and a mode the caller chose is not a mode to change behind them.  (Adopt
        does set the mode, because there the caller chose a *candidate*, not a
        mode.)
        """
        self._require_idle()
        path = _need(body, "path")
        pattern = self._as_pattern_path(_need(body, "pattern"))
        if "structure" not in body:
            # Absent is a mistake; `null` is an answer.  `dict.get` cannot tell
            # them apart, and only one of them should create a phase-free
            # project silently (WP-1207).
            raise GuiError(
                "structure is required: pass a CIF, an upload token, an inline "
                "model or a typed cell — or null for a pattern-only project, "
                "whose phase you find by indexing it",
                where=["structure"])
        structure = _as_structure(body.get("structure"), self.uploads)
        if _is_typed_cell(body.get("structure")) and body.get("mode") in (
                None, "rietveld"):
            raise GuiError(
                "a typed cell carries no atoms, so it cannot be refined in "
                "rietveld mode; create the project in 'lebail' or 'pawley' "
                "mode, and add atoms later to switch",
                where=["mode"])
        instrument = _as_instrument(body.get("instrument"), self.uploads)
        kw: dict[str, Any] = {}
        for key in ("mode", "two_theta_limits", "excluded_regions",
                    "reader_options", "ui"):
            if body.get(key) is not None:
                kw[key] = body[key]
        if body.get("plan") is not None:
            kw["plan"] = _as_plan_argument(body["plan"])
        try:
            project = Project.create(path, pattern=pattern, structure=structure,
                                     instrument=instrument, backend=self.backend,
                                     solver=self.solver, **kw)
        except (FileExistsError, FileNotFoundError, ValueError, KeyError) as exc:
            raise GuiError(str(exc), code="PROJECT_ERROR") from None
        self._adopt(project)
        return self.project_doc()

    def _as_pattern_path(self, pattern: Any) -> str:
        """A pattern argument as a path: a server-side one, or a staged upload's.

        The staged file is what ``Project.create`` copies, so the project owns
        its own bytes from the first moment and the staging directory can be
        thrown away with the session — the copy is byte-for-byte either way
        (WP-1005: the bytes are the contract).
        """
        if isinstance(pattern, dict):
            token = _need(pattern, "upload")
            try:
                return str(self.uploads.get(str(token), "pattern").path)
            except UploadRefused as exc:
                raise GuiError(str(exc), code=exc.code, status=exc.status,
                               where=["pattern.upload"]) from None
        return str(pattern)

    def project_open(self, body: dict) -> dict:
        """``Project.open``, with its refusal messages surfaced verbatim.

        ``Project.open`` distinguishes a missing pattern, changed bytes, a
        same-bytes/different-numbers reader change, a tree recorded against
        another pattern, a missing log, a future format major and a
        multi-pattern document — seven causes with seven remedies.  Collapsing
        them into "could not open project" would throw away the only place a
        user will ever read which one happened.
        """
        self._require_idle()
        path = _need(body, "path")
        try:
            project = Project.open(path, backend=self.backend, solver=self.solver)
        except (FileNotFoundError, ValueError) as exc:
            raise GuiError(str(exc), code="PROJECT_ERROR") from None
        self._adopt(project)
        return self.project_doc()

    def project_doc(self) -> dict:
        """The settings document plus what a client needs about the data."""
        p = self._need_project()
        ref = p.data_ref
        return {
            "path": str(p.path),
            "doc": p.doc.model_dump(mode="json"),
            "data": {
                "filename": ref.filename, "reader": ref.reader,
                "options": dict(ref.options), "n_points": ref.n_points,
                "two_theta_range": list(ref.two_theta_range),
                # which weights the fit uses is a correctness property that is
                # invisible once the file is read (CLAUDE.md, Weights)
                "has_sigma": ref.has_sigma,
                # The source's emission lines, primary first — the instrument's
                # own numbers, because the plot's readout says d = λ/(2 sin θ)
                # and names which line a candidate tick belongs to (WP-1213).
                # Here rather than on the window payload: λ is a fact about the
                # instrument, not about a fitted curve, and this is the view a
                # project has before any fit.  The peak document carries a
                # wavelength too and it is *not* this one — it is the λ the
                # picker ran at, which an instrument edit afterwards leaves
                # behind.
                "wavelengths": [float(line.wavelength.value) for line
                                in p.refinement.instrument.source.lines],
                # how many channels survive the limits and the exclusions — the
                # check that a shaded band is telling the truth (WP-1033).  A
                # band drawn over points still in the residual is worse than no
                # band, and this number is what makes the difference readable
                # without re-running anything.
                "n_fitted": int(p.fitted_mask().sum()),
            },
            "head": p.refinement._head_id,
            "n_nodes": len(p.history),
            # A model fact on the settings document, like `head` beside it and
            # for the same reason: a client needs to know a *run* is refused
            # before it offers one (WP-1207), and the alternative is fetching
            # the whole structure to count a list.  Derived on every read, so
            # it is a summary rather than a second authority — the phases live
            # in the history like every other model fact.
            "n_phases": len(p.refinement.structure.phases),
        }

    def project_patch(self, body: dict) -> dict:
        """Change settings, and persist them at once.

        ``ui`` merges at the top level (the frontend owns those keys and pushes
        whole blobs for the panel it touched); a ``null`` value drops a key.
        ``excluded_regions`` goes through ``Project.set_excluded_regions`` so the
        document and the in-memory pattern cannot disagree about what is masked.

        An inverted or empty interval is refused in
        :func:`schemas.project.check_interval`'s words — the same sentence the
        ``.rxt`` document refuses with, because the document's field validators
        are what both routes run into (WP-1033).
        """
        self._require_idle()
        p = self._need_project()
        unknown = set(body) - {"mode", "two_theta_limits", "excluded_regions",
                               "indexing", "ui"}
        if unknown:
            raise GuiError(f"unknown setting(s): {sorted(unknown)}; the plan has "
                           "its own route and the model lives in the history",
                           where=sorted(unknown))
        if "mode" in body:
            p.doc.mode = body["mode"]
        if "indexing" in body:
            # whole-object replace, like the plan: the form pushes the block
            # it edited, and a partial merge would let two half-specs disagree
            from ..schemas.indexing import IndexingControls

            with self._settings_refusal("indexing"):
                p.doc.indexing = IndexingControls.model_validate(
                    body["indexing"] or {})
        if "two_theta_limits" in body:
            limits = body["two_theta_limits"]
            with self._settings_refusal("two_theta_limits"):
                p.doc.two_theta_limits = None if limits is None else tuple(limits)
        if "excluded_regions" in body:
            regions = [tuple(r) for r in (body["excluded_regions"] or [])]
            with self._settings_refusal("excluded_regions"):
                p.set_excluded_regions(regions)
        for key, value in (body.get("ui") or {}).items():
            if value is None:
                p.doc.ui.pop(key, None)
            else:
                p.doc.ui[key] = value
        p.save()
        return self.project_doc()

    @staticmethod
    @contextmanager
    def _settings_refusal(where: str):
        """Turn a document validator's refusal into this verb's 400 (WP-1033).

        The message is passed through with pydantic's ``"Value error, "`` prefix
        removed and nothing else added: the sentence a client shows is the one
        :func:`schemas.project.check_interval` wrote, so the wire route, the
        ``.rxt`` document and a bare ``doc.two_theta_limits = …`` all refuse
        alike.  Without this the assignment raises ``ValidationError`` and the
        transport answers 500 — true, and useless to the person who typed it.
        """
        from pydantic import ValidationError

        try:
            yield
        except ValidationError as exc:
            message = str(exc.errors()[0]["msg"])
            raise GuiError(message.removeprefix("Value error, "),
                           where=[where]) from None

    def project_save(self) -> dict:
        """Rewrite ``project.json``.

        Every settings verb above already saved, and the model was on disk the
        moment its node was appended, so this is a flush a client may call and
        never a thing it must call.  It exists because a "Save" affordance will
        exist, and it should do something honest.
        """
        p = self._need_project()
        p.save()
        return {"saved": str(p.path), "updated_utc": p.doc.updated_utc}

    def settings(self) -> dict:
        """The **app's** own `ui` keys — the ones that belong to the person.

        A second `ui` dict, deliberately, and the line between the two is what
        the key is *about* (WP-1044).  A column width, Simple/Advanced, a stored
        splitter position are facts about a project: it has four phases, so the
        table wants to be wide.  A theme is a fact about the person and the room
        they are in, and `ProjectDoc.ui` gave the wrong answer for it — measured,
        choosing dark and then opening a second project came back `system`,
        because ``readUi`` re-reads the choice off whichever document is open and
        a fresh project has never been told.

        It lives in the state directory beside ``recent.json`` for the same
        reason that list does: it survives the project, the port a client
        happens to be served on, and the browser profile it was chosen in.  The
        dict is **open** exactly as ``ProjectDoc.ui`` is — the frontend owns the
        keys — and an unreadable or hand-mangled file is an empty one, never an
        error, because no setting here is worth refusing to start over.
        """
        try:
            raw = json.loads((self.state_dir / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        ui = raw.get("ui") if isinstance(raw, dict) else None
        return {"ui": ui if isinstance(ui, dict) else {}}

    def settings_patch(self, body: dict) -> dict:
        """Merge `ui` keys into the app settings and persist them at once.

        Same grammar as :meth:`project_patch` one scope up — top-level merge, a
        ``null`` value drops a key, settings persist on the verb rather than on
        a later save — so a client that knows one knows the other.  It takes no
        project and no lock: nothing here can disagree with a run in flight.
        """
        unknown = set(body) - {"ui"}
        if unknown:
            raise GuiError(f"unknown setting(s): {sorted(unknown)}; app settings "
                           "are the frontend's own 'ui' keys",
                           where=sorted(unknown))
        patch = body.get("ui") or {}
        if not isinstance(patch, dict):
            raise GuiError("'ui' maps key → value", where=["ui"])
        ui = self.settings()["ui"]
        for key, value in patch.items():
            if value is None:
                ui.pop(key, None)
            else:
                ui[key] = value
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            (self.state_dir / "settings.json").write_text(
                json.dumps({"ui": ui}, indent=2), encoding="utf-8")
        except OSError:
            # a read-only home costs the *persistence*, not the choice: the
            # client applied it before it asked, exactly as `_remember` treats
            # an unwritable recent list
            pass
        return {"ui": ui}

    # ------------------------------------------------------------------
    # examples (WP-1204)
    # ------------------------------------------------------------------
    def examples(self) -> dict:
        """The example projects this build carries, and whether each is built.

        ``built`` is what makes the empty state honest about cost: the first
        open of the 11-BM example copies 2.5 MB and reads it, and every later
        one is a plain :meth:`project_open`.

        They are built into the **state directory** rather than beside the
        packaged data, for the reason ``recent.json`` lives there: an example
        is a project the person then edits, and package data is read-only,
        shared between virtual environments, and replaced by the next upgrade.
        """
        from ..examples import list_examples

        return {"examples": [
            {"name": e.name, "title": e.title, "description": e.description,
             "bytes": e.bytes, "path": str(self._example_path(e.name)),
             "built": (self._example_path(e.name) / "project.json").is_file()}
            for e in list_examples()]}

    def _example_path(self, name: str) -> Path:
        """Where ``name`` is built, refusing any name this build does not carry.

        The refusal is what makes the path safe to join: ``name`` reaches here
        from a request body, and it is checked against the *list* rather than
        sanitised, so there is no traversal to get wrong.
        """
        from ..examples import list_examples

        known = [e.name for e in list_examples()]
        if name not in known:
            raise GuiError(
                f"unknown example {name!r}; this build carries {known}",
                code="UNKNOWN_EXAMPLE", where=["name"])
        return self.state_dir / "examples" / f"{name}{_about.PROJECT_SUFFIX}"

    def example_open(self, body: dict) -> dict:
        """Open an example, building it first if this is its first open.

        Returns exactly what :meth:`project_open` returns, because that is what
        it ends in — an example is a project like any other from the moment it
        exists, and nothing downstream should be able to tell.
        """
        self._require_idle()
        name = str(_need(body, "name"))
        root = self._example_path(name)
        if not (root / "project.json").is_file():
            self._build_example(name, root)
        return self.project_open({"path": str(root)})

    def example_reset(self, body: dict) -> dict:
        """Throw away this example's copy and build it again.

        The one destructive verb on this surface, and deliberately narrow: it
        removes a directory under ``state_dir/examples`` whose name came from
        the example list, never a path a client chose.  What it discards is the
        person's edits to *the example*, which is the whole request — the
        confirmation belongs in the UI, not in a refusal here.
        """
        self._require_idle()
        name = str(_need(body, "name"))
        root = self._example_path(name)
        if (root / "project.json").is_file():
            import shutil

            # drop it from the session first: between the removal and the open
            # the directory does not exist, and a reader finding NO_PROJECT is
            # better than one finding half a project.  The run frame goes with
            # it — most of what a reader reaches here is in memory and would
            # answer happily about a project that no longer exists, which is
            # WP-1201's "a statistic outlives the thing it describes"
            if self.project is not None and self.project.path == root:
                with self._cond:
                    self.project = None
                    self._run = _idle_run()
                    self._cond.notify_all()
            shutil.rmtree(root)
        self._build_example(name, root)
        return self.project_open({"path": str(root)})

    def _build_example(self, name: str, root: Path) -> None:
        from ..examples import build_example

        try:
            root.parent.mkdir(parents=True, exist_ok=True)
            build_example(name, root.parent)
        except OSError as exc:
            # unlike the recent list, this one cannot be swallowed: there is no
            # project at the end of it, and the person clicked to get one
            raise GuiError(f"could not build the {name} example: {exc}",
                           code="EXAMPLE_BUILD_FAILED") from None

    def recent(self) -> list[dict]:
        """Recently opened projects, newest first (missing ones filtered out)."""
        try:
            raw = json.loads((self.state_dir / "recent.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out = []
        for entry in raw if isinstance(raw, list) else []:
            path = Path(str(entry.get("path", "")))
            if (path / "project.json").is_file():
                out.append({"path": str(path), "name": path.name,
                            "opened_utc": entry.get("opened_utc", "")})
        return out

    def fs(self, path: str | None) -> dict:
        """Directories and projects under one root, for the "Open…" browser.

        Opening a project has no picker to route through — a browser cannot
        hand back a path, only bytes — so this is the one place the GUI reads
        the filesystem for its own sake, and it stays deliberately small: a
        read-only listing confined to the **home directory and the process's
        current working directory** (WP-1205 decision, not the whole machine).
        ``path`` defaults to the home directory; it is resolved — symlinks
        included — before it is checked, so ``..`` and a symlink pointing
        outside a root are refused exactly alike, and a client-typed path is
        never sanitised, only rejected: the gate is containment, not a
        blocklist.  Hidden entries (``.git``, ``.cache``, …) are left off the
        listing, since browsing them serves nobody looking for a project.
        """
        roots = self._fs_roots()
        target = Path(path).expanduser().resolve() if path else roots[0]
        if not any(target.is_relative_to(r) for r in roots):
            raise GuiError(
                f"{target} is outside the browsable roots "
                f"({', '.join(str(r) for r in roots)})", where=["path"])
        if not target.exists():
            raise GuiError(f"{target} does not exist", code="NOT_FOUND",
                           status=404, where=["path"])
        if not target.is_dir():
            raise GuiError(f"{target} is not a directory", where=["path"])
        try:
            children = sorted(target.iterdir(), key=lambda p: p.name.lower())
        except OSError as exc:
            raise GuiError(f"could not list {target}: {exc}",
                           where=["path"]) from None
        entries = []
        for child in children:
            if child.name.startswith("."):
                continue
            try:
                if not child.is_dir():
                    continue
            except OSError:
                continue
            entries.append({"name": child.name, "path": str(child),
                            "is_project": (child / "project.json").is_file()})
        parent = target.parent
        has_parent = parent != target and any(
            parent.is_relative_to(r) for r in roots)
        return {"path": str(target),
                "parent": str(parent) if has_parent else None,
                "roots": [str(r) for r in roots], "entries": entries}

    def _fs_roots(self) -> list[Path]:
        """The two browsable roots, home first — a set, since a GUI launched
        from inside the home tree (the common case) has only one.

        "Inside the home tree" means *under* home, not only *at* it — a GUI
        launched from a project directory (the ordinary case) has a cwd that
        is a strict descendant of home, so containment is what collapses the
        pair, not equality alone.
        """
        home = Path.home().resolve()
        cwd = Path.cwd().resolve()
        return [home] if cwd == home or cwd.is_relative_to(home) else [home, cwd]

    # ------------------------------------------------------------------
    # parameters
    # ------------------------------------------------------------------
    def params(self) -> dict:
        """The whole parameter table as rows, held ones included.

        ``refinable`` and ``held_because`` are :class:`ParameterRow` *properties*
        rather than fields, so ``model_dump`` drops them — and they are the whole
        point of the surface (WP-1004), so they are added here by asking the row
        rather than by a second copy of the rule.

        While a run is in flight the values are read off models a stage is
        writing to, so a row may straddle two iterations; ``live`` says so.  That
        is deliberate — the authoritative live signal is the event stream, and
        the consistent alternative is the head node, which is a completed stage.
        """
        p = self._need_project()
        rows = []
        for row in p.parameters():  # answered for the document's mode
            item = row.model_dump(mode="json")
            item["refinable"] = row.refinable
            item["held_because"] = row.held_because
            rows.append(item)
        return {"parameters": rows,
                "n_free": sum(1 for r in rows if r["vary"]),
                "mode": p.doc.mode,
                "head": p.refinement._head_id,
                "live": self._state != "idle"}

    def params_patch(self, body: dict) -> dict:
        """``set_values`` then ``set_vary``, each committing its own node.

        Values first, then vary flags: the pair reads as "put it here, then let
        it move", which is the order that leaves a freed parameter's node last in
        the log — where a following run continues from.  ``vary`` is applied in
        the order the JSON object gave, since overlapping globs are ordinary
        (``phases.*`` then a single path back off).
        """
        self._require_idle()
        p = self._need_project()
        values = body.get("values") or {}
        vary = body.get("vary") or {}
        if not isinstance(values, dict) or not isinstance(vary, dict):
            raise GuiError("'values' maps dot-path → number and 'vary' maps "
                           "dot-path glob → bool")
        changed: dict[str, Any] = {"values": [], "vary": {}}
        if values:
            try:
                p.refinement.set_values({k: float(v) for k, v in values.items()})
            except (ValueError, TypeError) as exc:
                # a tied path names its sources, a locked one says it is
                # structural, a bound violation prints the interval — each has a
                # different fix, so the message travels intact
                raise GuiError(str(exc), where=sorted(values)) from None
            changed["values"] = sorted(values)
        for glob, flag in vary.items():
            try:
                changed["vary"][glob] = p.refinement.set_vary(glob, bool(flag))
            except ValueError as exc:
                # ``set_vary`` could not refuse anything until WP-1435 gave a
                # caller's hold precedence over a named path, so this branch
                # ran bare and the first refusal would have been a 500.  Same
                # treatment as ``set_values`` above: the sentence names the
                # verb that resolves it, so it travels intact.
                raise GuiError(str(exc), where=[glob]) from None
        return {"changed": changed, **self.params()}

    # ------------------------------------------------------------------
    # plan
    # ------------------------------------------------------------------
    def plan(self) -> dict:
        """The plan the next run will use, expanded into stages.

        A project stores the *expanded* plan, so which preset button was pressed
        is not recoverable from it — ``preset`` is therefore derived by comparing
        the stored stages against every registered preset, and is ``null`` for an
        edited plan.  ``selected`` distinguishes "this project chose a plan" from
        "nothing chose, and ``fit`` would default".
        """
        p = self._need_project()
        effective = PlanSpec.from_plan(self._effective_plan())
        return {"plan": effective.model_dump(mode="json"),
                "selected": p.doc.plan is not None,
                "preset": effective.preset_name(),
                "mode": p.doc.mode}

    def plan_put(self, body: dict) -> dict:
        """Select a preset (``{"preset": name}``) or an explicit plan spec."""
        self._require_idle()
        p = self._need_project()
        if "preset" in body:
            # stored expanded, and expanded *through the mode*: a project's plan
            # is what will run verbatim (``Project.fit`` passes it as-is), so
            # picking "mccusker_default" in Le Bail mode has to store
            # profile_only's stages — the same mapping ``fit`` would apply, made
            # visible in the editor instead of happening at run time
            spec = PlanSpec.from_plan(
                resolve_plan(_as_plan_argument(body["preset"]), p.doc.mode))
        elif "plan" in body:
            spec = _validate(PlanSpec, body["plan"], "plan")
        else:
            raise GuiError("send either {'preset': name} or {'plan': {...}}")
        if not spec.stages:
            raise GuiError("a plan needs at least one stage", where=["plan.stages"])
        p.doc.plan = spec
        p.save()
        return self.plan()

    def plans(self) -> dict:
        """The preset registry, quoted through ``capabilities()``.

        Not read off ``PLAN_INFO`` directly: the capabilities arm is already the
        one answer to "what plans does this build have", and a menu that could
        disagree with it would be a second answer.
        """
        return {"plans": [item.model_dump(mode="json")
                          for item in _capabilities().plans]}

    def plan_resolve(self) -> dict:
        """The plan's stages resolved against the live parameter table (WP-1208).

        ``GET /api/plan`` says what the stages *are*; this says what they will
        **do** — which paths each stage's globs reach, which of those it frees
        that were not free already, which it cannot free and why, and the
        running free count a cumulative plan leaves behind.  A crystallographer
        who has only refined one step at a time reads a plan as a list of
        names; this is the arm that turns it into a list of parameters.

        **The simulation is the real verb, run on the table a fit builds.**
        ``_prepare_table(restore=False)`` is what ``Refinement.fit`` starts
        every plan from, and it holds **everything** first — so a plan does not
        continue from the vary flags a person ticked by hand, it replaces them
        (measured: ``set_vary("phases.*.atoms.*.biso")`` then
        ``fit(plan="profile_only")`` refines no ``biso``).  That is the fact
        this panel exists to make visible, and it is why the table is built
        here rather than taken from ``_working_table``, which is
        ``run_stage``'s starting point and not ``fit``'s.  The paths it strands
        are ``set_aside``.  The table is fresh, so ``set_vary`` on it moves
        nothing a run would see; and calling the real ``set_vary`` — rather
        than a matcher written here — is what keeps the answer honest about the
        rules that live in it (a tied or locked entry never matches however
        broad the glob, and a wavelength does not match while this histogram's
        cell is free).  The one rule that lives in ``_run_stage`` instead is
        the intensity mode's force-fix, so that is applied here the same way it
        is applied there, through :func:`~rietx.refine.mode_fixed_column` —
        which asks what each column moves, so a tie cannot carry a structural
        parameter past it in either place (WP-1342).

        **Every matched path lands in exactly one of three buckets**, decided
        in this order: ``held`` (the stage's globs reach it and the stage will
        not free it), ``already`` (free coming in — which under
        ``restore=False`` can only mean an *earlier stage of this plan* freed
        it, never the caller, whose flags land in ``set_aside``), ``frees``
        (new this stage).  A path can be both mode-fixed and already free, so
        the order matters and ``held`` wins: what the stage will do with it is
        drop it.

        **The reason is never written here.**  ``held_because`` is
        :class:`~rietx.schemas.params.ParameterRow`'s property, and the row for
        the *dynamic* refusal is made by setting the flag that causes it rather
        than by spelling its sentence a second time: when ``set_vary`` declines
        a row that has no static reason to be held, the remaining reason is the
        free-cell one, which is the fourth and last thing ``refinable``
        promises to cover.

        ``rwp`` per stage is read off the **history nodes**, not off a
        ``fit(stage_reports=True)`` trajectory.  The two numbers are the same
        number — a rung and a stage node are both built from the model the
        stage compiled and the θ it landed on, measured bit-identical on the
        synthetic LaB6 fixture — and the node is already on disk, where the
        trajectory costs 7.7× the fit to rebuild (0.076 s → 0.582 s, five
        stages, 4200 channels; WP-1208's handover has the matrix).  A node is
        matched to a ladder rung by **position and identity**: the last run of
        ``stage`` nodes on the head's lineage, aligned from its start, each
        required to carry this stage's name *and* its ``turn_on``.  Anything
        else — a plan edited since the run, a single stage run from a state no
        plan describes, a checkout — leaves ``rwp`` null rather than printing
        the wrong stage's number.  Between the head and that run,
        ``_RWP_TRANSPARENT`` nodes are stepped over, because ticking a
        parameter while reading this panel is the ordinary thing to do and it
        does not change what the stages behind it reached.

        Not behind the 409: this is a read, and it is exposed to a run in
        flight exactly as ``params`` is, for the reason that method's docstring
        gives.  ``live`` says so.
        """
        p = self._need_project()
        plan = self._effective_plan()
        mode = p.doc.mode
        rows = {row.path: row for row in p.parameters()}
        table = p.refinement._prepare_table(restore=False)

        stages: list[dict] = []
        for stage in plan.stages:
            globs = list(stage.turn_on)
            matched = [path for path in rows
                       if any(fnmatchcase(path, glob) for glob in globs)]
            before = set(table.free_paths)
            # exactly what ``_run_stage`` does with a mode-fixed hit, and for
            # its reason: the freed set must describe what is left free.  In
            # one call rather than its per-path loop — a path is a glob that
            # matches itself, and this route is called on every head move,
            # where N calls would be N table rebuilds (a Le Bail phase's every
            # `.atoms.` row is mode-fixed).
            # By what each column *moves*, as ``_run_stage`` does since
            # WP-1342 — a tie can otherwise carry a structural parameter past
            # the name test and this panel would promise a free column the
            # next run drops.  Read after ``set_vary``, while they are columns.
            freed_here = table.set_vary(globs, True)
            reach = table.column_reach() if freed_here else {}
            dropped = [path for path in freed_here
                       if mode_fixed_column(reach.get(path, [path]), mode)]
            if dropped:
                table.set_vary(dropped, False)
            after = set(table.free_paths)

            held, already, frees = [], [], []
            for path in matched:
                if path not in after:
                    row = rows[path]
                    if not row.held_because:
                        row = row.model_copy(update={"needs_held_cell": True})
                    held.append({"path": path, "held_because": row.held_because})
                elif path in before:
                    already.append(path)
                else:
                    frees.append(path)
            stages.append({
                "name": stage.name, "turn_on": globs,
                "frees": frees, "already": already, "held": held,
                "n_matched": len(matched), "n_free": len(after),
            })

        for entry, rwp in zip(stages, self._stage_rwp(p, plan), strict=True):
            entry["rwp"] = rwp
        reached = {path for entry in stages for path in entry["frees"]}
        set_aside = [row.path for row in rows.values()
                     if row.vary and row.refinable and row.path not in reached]
        return {"mode": mode, "n_parameters": len(rows),
                "n_free_final": stages[-1]["n_free"] if stages else 0,
                "set_aside": set_aside, "stages": stages,
                "head": p.refinement._head_id,
                "live": self._state != "idle"}

    #: Node kinds that may sit between the head and the run of stages behind it
    #: without ending it.  These change *which parameters are free*, not the
    #: model the stages' statistics were measured on — and ticking a parameter
    #: to see what the plan makes of it is the ordinary thing to do while
    #: reading this panel, so a ``set_vary`` must not wipe the Rwp column
    #: (it did, found in a browser).  ``edit_model`` is deliberately not here:
    #: it replaces the model, and a number measured on the old one has stopped
    #: describing anything on screen.
    _RWP_TRANSPARENT = frozenset({"set_vary", "set_value", "set_tie",
                                  "set_variable"})

    @classmethod
    def _stage_rwp(cls, p: Project, plan) -> list[float | None]:
        """One Rwp per plan stage, off the history nodes the run recorded.

        The alignment rule is in :meth:`plan_resolve`'s docstring; this is it
        applied.  ``None`` everywhere is the ordinary answer before the first
        run, and the honest one whenever the plan on screen is not the plan
        that ran.
        """
        blank: list[float | None] = [None] * len(plan.stages)
        tree = p.refinement.history
        head = p.refinement._head_id
        if tree is None or head is None or head not in tree:
            return blank
        run: list = []
        for node in reversed(tree.lineage(head)):
            if node.action.kind == "stage":
                run.append(node)
                if len(run) == len(plan.stages):
                    break   # the *last* run: back-to-back runs of one plan
                            # leave 2N contiguous stage nodes, and aligning
                            # from the far end of them would read the first
                            # run's numbers under the second run's ladder
            elif run or node.action.kind not in cls._RWP_TRANSPARENT:
                break   # the run has ended, or something ended it before it
        run.reverse()
        out = list(blank)
        for k, stage in enumerate(plan.stages):
            if k >= len(run):
                break
            node = run[k]
            if (node.action.name != stage.name
                    or list(node.action.turn_on) != list(stage.turn_on)):
                break
            stats = node.metrics.statistics
            out[k] = None if stats is None else float(stats.rwp)
        return out

    # ------------------------------------------------------------------
    # the text document (WP-1009)
    # ------------------------------------------------------------------
    def textdoc(self) -> dict:
        """The project as text, with the CAS token for the matching ``PUT``."""
        from . import textdoc as td

        text = td.render(self._need_project())
        return {"text": text, "revision": td.revision(text),
                "format_version": td.FORMAT_VERSION}

    def textdoc_put(self, body: dict) -> dict:
        """Parse, diff against the live project, and apply — or apply nothing.

        ``base_revision`` is compare-and-set: it is the revision the editor was
        showing, and a mismatch means the project moved underneath it (a stage
        committed, a form edited a value). Rejecting is the whole conflict story
        — a three-way merge of a document that is regenerated from state would be
        inventing an authority. ``validate_only`` runs everything except the
        apply, which is what a continuously-validating editor calls.
        """
        from . import textdoc as td

        self._require_idle()
        project = self._need_project()
        text = body.get("text")
        if not isinstance(text, str):
            raise GuiError("'text' is required and must be a string",
                           where=["text"])
        current = td.render(project)
        base = body.get("base_revision")
        if base and base != td.revision(current):
            raise GuiError(
                "the project changed since this text was rendered "
                f"(revision {td.revision(current)}, you sent {base}); re-read "
                "/api/textdoc and re-apply your edit",
                code="STALE_REVISION", status=409)

        delta, errors = td.changes(td.parse(text), project)
        if errors:
            raise GuiError(
                f"{len(errors)} problem(s) in the document; nothing was applied",
                code="TEXTDOC_INVALID",
                where=sorted({e.where for e in errors if e.where}),
                details=[e.as_dict() for e in errors])
        if body.get("validate_only"):
            return {"valid": True, "applied": [], "delta": delta.as_dict(),
                    "revision": td.revision(current), "would_change":
                    not delta.is_empty()}
        editor = (self._peak_editor()
                  if (delta.peak_moves or delta.peak_flags) else None)
        try:
            applied = td.apply(project, delta, peak_editor=editor)
        except ValueError as exc:
            # the verbs' own refusals (a tied path, a bound); ``set_values``
            # validates before writing, so nothing was applied
            raise GuiError(str(exc), code="TEXTDOC_INVALID",
                           details=[_locate(str(exc), text)]) from None
        rendered = td.render(project)
        return {"valid": True, "applied": applied, "delta": delta.as_dict(),
                "text": rendered, "revision": td.revision(rendered)}

    # ------------------------------------------------------------------
    # the models
    # ------------------------------------------------------------------
    def structure(self) -> dict:
        """The structure, plus what site symmetry allows each atom to do.

        The ``sites`` arm is why an in-GUI structure editor can be safe: a
        coordinate is edited through its ``…dof.k`` parameters, so a site-symmetry
        violation is *unrepresentable* rather than refused after the fact, and a
        fully fixed special position has an empty ``dof_paths`` — which is what
        an editor renders read-only.  Derived through the same two functions
        ``ParameterTable`` uses (``stabilizer_rotations`` → ``coordinate_basis`` /
        ``adp_basis``), never a second rule.

        Two more arms since WP-1035, and both are free — one ``get_spacegroup``
        call per phase, on facts ``ParameterTable._collect`` already looks up.
        ``symmetry`` is the phase's symbol read out (number, **setting**, crystal
        system, Laue class, centring, and the cell ties and held angles it
        causes); ``causes`` names the symmetry responsible for each held row, so
        the parameter table stops showing effects with anonymous causes.

        The Wyckoff *letter* is still deliberately absent: it needs
        ``wyckoff.site_constraints``, which runs spglib per atom (**measured at
        1.8-8.7 ms an atom**, WP-1035), and this route is refetched on every head
        move — including one a ``set_vary`` made.  It rides on
        ``GET /api/structure/symmetry``, the deliberately-opened route this
        docstring already named as the escape.
        """
        structure = self._need_project().refinement.structure
        rows = symmetry.site_rows(structure)
        return {"structure": structure.model_dump(mode="json"),
                "sites": rows,
                "symmetry": symmetry.phase_summary(structure),
                "causes": symmetry.held_causes(structure, rows)}

    def structure_symmetry(self, phase: int = 0) -> dict:
        """One phase's symmetry in full, Wyckoff letters included (WP-1035).

        The tier ``GET /api/structure`` refuses to carry.  A letter is a spglib
        search per atom, so this route is *opened deliberately* — a panel fetches
        it when a user asks to see site symmetry, not on every head move — and
        what it buys beyond the free tier is the **oriented site-symmetry
        symbol** (``.3.``, ``4m.m``), which is the one form of "which element is
        responsible" that names an element rather than counting a stabiliser.
        The ``causes`` here are therefore the same sentences ``/api/structure``
        serves, upgraded wherever a letter was found.

        Not idle-gated: it reads the model, like ``/api/structure``.
        """
        structure = self._need_project().refinement.structure
        try:
            letters = symmetry.site_letters(structure, int(phase))
        except IndexError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=["phase"]) from None
        by_path = {row["path"]: row for row in letters if "error" not in row}
        rows = symmetry.site_rows(structure)
        return {"phase": int(phase),
                "symmetry": symmetry.phase_facts(structure.phases[int(phase)],
                                                 int(phase)),
                "letters": letters,
                "causes": symmetry.held_causes(structure, rows, by_path)}

    def symmetry_preview(self, body: dict) -> dict:
        """What changing a phase's space group would do — and nothing else.

        Built out of the existing rules rather than a second copy of them: the
        candidate model's own ``ParameterTable`` supplies the refusals verbatim
        (nearest-allowed values included, because the raises already compute
        them), the entry diff supplies the tie/lock story, and ``site_rows``
        supplies the per-atom DOF story in the shape the editor already renders.

        Read-only, but **idle-gated anyway**: what it previews is a mutation, and
        an answer computed against a model a running stage is about to move is an
        answer about nothing.
        """
        self._require_idle()
        return self._preview(body)

    def symmetry_patch(self, body: dict) -> dict:
        """Change one phase's space group, gated on :meth:`symmetry_preview`.

        The gate is the whole verb.  ``PATCH /api/structure`` accepted a changed
        symbol before WP-1035 and committed an ``edit_model`` node from a
        snapshot that never builds a ``ParameterTable`` — so an incompatible
        change *succeeded*, recorded a node, and then surfaced as a 500 on the
        panel's next ``GET /api/params``, with the head standing at a state whose
        table cannot build and a history checkout the only way out.  Nothing
        about that was specific to the space group, so the gate went one level
        down into :meth:`_edit`; this verb adds the *complete* refusal list,
        because a table stops at the first bad item and a user fixing four atoms
        one 500 at a time is not being told what is wrong.
        """
        self._require_idle()
        answer = self._preview(body)
        phase = answer["phase"]
        if answer["blocked"]:
            first = (answer["refusals"] or [
                {"message": n["message"]} for n in answer["notes"]
                if n["kind"] == "orbit_collision"])[0]["message"]
            raise GuiError(
                f"{body.get('space_group')!r} is not compatible with this model: "
                f"{first}",
                code="SYMMETRY_REFUSED", where=["space_group"],
                details=[answer])
        if not answer["changed"]:
            return {"node_id": None, "changed": False, "preview": answer,
                    **self.structure()}
        candidate = symmetry.with_symbol(
            self._need_project().refinement.structure, phase,
            str(_need(body, "space_group")))
        node = self._edit(structure=candidate,
                          label=f"phase {phase}: space group "
                                f"{answer['to'].get('xhm', '?')}")
        return {"node_id": node, "changed": True, "preview": answer,
                **self.structure()}

    def _preview(self, body: dict) -> dict:
        p = self._need_project()
        phase = int(body.get("phase", 0) or 0)
        symbol = str(_need(body, "space_group"))
        try:
            free = [row.path for row in p.parameters() if row.vary]
        except ValueError:
            free = []           # the head cannot build a table; that is a state
            # this verb exists to escape, not one it may refuse to answer in
        try:
            return symmetry.preview(p.refinement.structure, p.refinement.instrument,
                                    phase, symbol, free_paths=free)
        except IndexError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=["phase"]) from None
        except (ValueError, RuntimeError) as exc:
            # the same mapping ``index_adopt`` uses for an unresolvable symbol
            raise GuiError(str(exc), where=["space_group"]) from None

    def structure3d(self, phase: int = 0, *, probability: float = 0.5,
                    bond_tolerance: float | None = None) -> dict:
        """The current model as drawable geometry (WP-1015).

        A route beside ``/api/structure`` rather than an arm of it, on WP-1008's
        test for a new one: it returns what the model does **not** already say —
        the symmetry orbit with each image's rotated displacement tensor, bonds
        over the 27 nearest lattice translations, and the cell frame — none of
        which a client could reshape out of a ``Structure`` dump without owning a
        space-group table.  Computed on demand, so it is also where a per-atom
        symmetry search may live that ``/api/structure`` refused (that route
        refetches on every head move; this one is opened deliberately).

        Not idle-gated: it reads the model, like ``/api/structure``, and a fit in
        flight does not move the values the working state holds.
        """
        from . import structure3d as geometry

        structure = self._need_project().refinement.structure
        try:
            return geometry.build(
                structure, int(phase), probability=float(probability),
                bond_tolerance=(geometry.BOND_TOLERANCE if bond_tolerance is None
                                else float(bond_tolerance)))
        except IndexError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=["phase"]) from None
        except ValueError as exc:
            raise GuiError(str(exc), where=["probability"]) from None

    def instrument(self) -> dict:
        return {"instrument": self._need_project().refinement.instrument.model_dump(
            mode="json")}

    def structure_patch(self, body: dict) -> dict:
        """Replace the structure, recording an ``edit_model`` node.

        A whole model, validated, not a field patch: adding a phase or an
        anisotropic ADP block changes what the parameter table *contains*, and a
        partial merge would have to reimplement pydantic's validation to know
        whether the result is a legal structure.

        The typed-cell form (WP-1206) reaches this route too, because
        :func:`_as_structure` is the one boundary every model crosses — and it
        carries the same consequence here as at creation: a scaffold's only atom
        is a dummy, so in ``rietveld`` mode the result is a Rietveld fit over a
        dummy carbon.  It is refused with ``project_new``'s own sentence rather
        than by flipping the mode: ``index_adopt`` flips it because there the
        caller chose a *candidate*, while a caller replacing the whole model has
        said nothing about the mode.  In lebail/pawley the swap is ordinary and
        goes through.
        """
        self._require_idle()  # before validating: a state refusal outranks a
        # body complaint, or a user retyping a structure never learns that the
        # real problem is the fit still running
        if _is_typed_cell(body.get("structure")) and self._need_project(
                ).doc.mode == "rietveld":
            raise GuiError(
                "a typed cell carries no atoms, so it cannot replace the "
                "structure of a project in rietveld mode; set the mode to "
                "'lebail' or 'pawley' first (POST /api/project)",
                where=["mode"])
        node = self._edit(
            structure=_as_structure(_need(body, "structure"), self.uploads),
            label=body.get("label") or "structure edited")
        return {"node_id": node, **self.structure()}

    def instrument_patch(self, body: dict) -> dict:
        self._require_idle()
        node = self._edit(
            instrument=_as_instrument(_need(body, "instrument"), self.uploads),
            label=body.get("label") or "instrument edited")
        return {"node_id": node, **self.instrument()}

    def structure_position(self, body: dict) -> dict:
        """Move one atom to a typed position (WP-1215).

        ``{"atom": "phases.I.atoms.J", "xyz": [x, y, z]}``.  A ``set_value``
        node, not an ``edit_model`` one: the position reaches θ as displacements
        on the site's ``…dof.k`` parameters, so this changes what the table
        *holds* and never what it *contains* — which is the line
        :meth:`structure_aniso` is on the other side of.

        The projection is :func:`symmetry.position_values`, and the refusal is
        its sentence verbatim: it names the directions the site allows and the
        nearest position it can reach, which is what a form needs to offer the
        user the choice rather than make it for them.  Nothing to set is not an
        error and records no node — a coordinate re-typed to the value it
        already had is a no-op, and ``set_values`` would commit a node saying
        nothing.
        """
        self._require_idle()
        p = self._need_project()
        path = str(_need(body, "atom"))
        xyz = _need(body, "xyz")
        if not isinstance(xyz, (list, tuple)):
            raise GuiError("'xyz' is a list of three numbers", where=["xyz"])
        try:
            moved = symmetry.position_values(p.refinement.structure, path,
                                             [float(v) for v in xyz])
        except IndexError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=["atom"]) from None
        except (TypeError, ValueError) as exc:
            raise GuiError(str(exc), code="MODEL_REFUSED",
                           where=[path, "xyz"]) from None
        if not moved["values"]:
            return {"node_id": None, "changed": False,
                    "nearest": moved["nearest"], **self.structure()}
        try:
            p.refinement.set_values(moved["values"])
        except ValueError as exc:
            # a locked DOF, or a bound — the message travels intact, as it does
            # through `params_patch`
            raise GuiError(str(exc), where=sorted(moved["values"])) from None
        return {"node_id": p.refinement._head_id, "changed": True,
                "nearest": moved["nearest"], **self.structure()}

    def structure_aniso(self, body: dict) -> dict:
        """Turn one atom's anisotropic ADP block on or off (WP-1014).

        A verb of its own rather than a field of the structure patch, because
        both directions are **physics the client must not compute**.  On seeds
        ``AnisoU.isotropic`` — U^ij = Uiso·G*ᵢⱼ/(a*ᵢa*ⱼ), which is *not*
        Uiso·δᵢⱼ except for orthogonal reciprocal axes, so a TypeScript version
        would get every hexagonal cell wrong.  Off restores ``biso`` from U_eq,
        which weights by the metric.  Both live in ``crystallography.adp``, and
        this is what reaches them.

        Recorded as one ``edit_model`` node, like every other model change: it
        changes what the parameter table *contains* (six tied components and
        their ``…adp.k`` DOFs appear, ``biso`` becomes locked), which is the
        definition of a shape change here.
        """
        import math

        self._require_idle()
        p = self._need_project()
        path = str(_need(body, "path"))
        on = bool(body.get("on", True))
        match = re.fullmatch(r"phases\.(\d+)\.atoms\.(\d+)", path)
        if match is None:
            raise GuiError(f"{path!r} is not an atom path (phases.I.atoms.J)",
                           where=["path"])
        i, j = int(match.group(1)), int(match.group(2))
        structure = p.refinement.structure.model_copy(deep=True)
        try:
            phase = structure.phases[i]
            atom = phase.atoms[j]
        except IndexError:
            raise GuiError(f"no atom at {path!r}", code="NOT_FOUND",
                           status=404, where=["path"]) from None
        if on and atom.aniso is None:
            from ..schemas.structure import AnisoU

            atom.aniso = AnisoU.isotropic(atom.biso.value / (8.0 * math.pi ** 2),
                                          phase.cell)
        elif not on and atom.aniso is not None:
            from ..crystallography.adp import u_equivalent

            u_eq = u_equivalent(atom.aniso.values(), phase.cell.lengths_angles())
            biso = 8.0 * math.pi ** 2 * float(u_eq)
            atom.biso.value = min(max(biso, atom.biso.min), atom.biso.max)
            atom.aniso = None
        else:
            return {"node_id": None, "changed": False, **self.structure()}
        node = self._edit(structure=structure,
                          label=f"{atom.label}: aniso {'on' if on else 'off'}")
        return {"node_id": node, "changed": True, **self.structure()}

    def _edit(self, *, structure: Structure | None = None,
              instrument: Instrument | None = None, label: str = "") -> str | None:
        """The one funnel every whole-model edit goes through.

        The gate that used to live here is now in ``Refinement.edit`` itself
        (WP-1035), because nothing about it was a GUI concern: pydantic knows no
        crystallography, every symmetry refusal is raised when a
        ``ParameterTable`` is constructed, and the snapshot ``edit`` commits
        never constructs one — so a Python caller was exposed to exactly the
        failure a browser found. All this layer adds is the **address**: a
        ``ValueError`` carries the offending dot-path in its first token, and a
        form needs it to highlight the field.
        """
        self._require_idle()
        p = self._need_project()
        try:
            return p.refinement.edit(structure=structure, instrument=instrument,
                                     label=label)
        except ValueError as exc:
            match = _LEADING_PATH.search(str(exc))
            raise GuiError(str(exc), code="MODEL_REFUSED",
                           where=[match.group(1)] if match else []) from None

    # ------------------------------------------------------------------
    # run control
    # ------------------------------------------------------------------
    def run(self, body: dict) -> dict:
        """Start a fit (``kind="fit"``), one stage (``"stage"``) or an
        indexing run (``"index"``).

        Returns immediately with the run state; everything else about the run
        arrives as events.  The refinement kinds go through ``Project.fit`` /
        ``Project.run_stage`` rather than ``Refinement.fit`` so the document's
        mode and limits are the ones that apply — the project is the authority
        on the settings, and re-deriving them here would be the second copy
        WP-1005 exists to prevent.

        ``"index"`` (WP-1027) runs :func:`rietx.index_pattern` on the stored
        peak list (or lets it pick its own when none is stored) through the
        same machinery: one worker, the same 409 for every mutating verb, the
        engine's own ``index_start``/``stage_start``/``stage_end``/``index_end``
        events on the same stream.  What differs is only how the run record is
        summarised — an ``IndexingResult`` has no Rwp and commits no node, and a
        *cancelled* search returns what it has rather than raising, so its
        status is read off the token.
        """
        p = self._need_project()
        kind = body.get("kind", "fit")
        if kind not in ("fit", "stage", "index", "extinction", "series"):
            raise GuiError(f"unknown run kind {kind!r}; expected 'fit', "
                           "'stage', 'index', 'extinction' or 'series'",
                           where=["kind"])
        if kind in ("fit", "stage", "extinction", "series"):
            # Up here rather than in the worker: the refusal is knowable before
            # anything starts, and a run *started* is a 200 whose failure only
            # ever reaches the event stream — the caller asked a question that
            # has an answer now (WP-1207).
            try:
                _refuse_without_phases(p.refinement.structure, f"a {kind} run")
            except NoPhasesError as exc:
                raise GuiError(str(exc), code=exc.code, where=["kind"]) from None
        summarize = _summarize_refinement
        if kind == "stage":
            stage_spec = _validate(StageSpec, _need(body, "stage"), "stage")
            stage = stage_spec.to_stage()

            def call(stream, token):
                return p.run_stage(stage, events=stream, cancel=token)

            label = stage_spec.name
            n_stages = 1
        elif kind == "index":
            from ..indexing.engines import engine_names

            peak_doc = self._load_peaks(p)  # a wrong-pattern list refuses here
            peak_list = None if peak_doc is None else peak_doc.peaks
            limits = (tuple(p.doc.two_theta_limits)
                      if p.doc.two_theta_limits else None)
            # the document is the authority on the controls (WP-1045), the
            # same way mode and limits reach fit/run_stage through the
            # project rather than through this verb's body
            controls = p.doc.indexing
            run_engines = (tuple(controls.engines)
                           if controls.engines else None)

            def call(stream, token):
                from ..indexing.workflow import index_pattern

                result = index_pattern(
                    peak_list, data=p.data,
                    instrument=p.refinement.instrument,
                    spec=controls.search.to_spec(),
                    preset=controls.search.preset,
                    engines=run_engines,
                    validate=controls.validate_candidates,
                    check_top=controls.check_top,
                    two_theta_limits=limits, events=stream, cancel=token)
                with self._cond:
                    self._index_result = result
                    # candidate indices just changed meaning: a screen kept
                    # from the previous answer would be served against the
                    # wrong cell
                    self._extinction = None
                return result

            summarize = _summarize_index
            label = "index"
            n_stages = len(run_engines or engine_names())
        elif kind == "extinction":
            # WP-1025 served (WP-1027): rank the extinction classes of one
            # candidate.  Deliberately *not* gated on the adopt verdict — on
            # real data with no measured shift ``best_or_none()`` is None by
            # design, and a screen is a read-only measurement ("IF this cell,
            # THEN these classes"); the gate stays on ``index_adopt``, where
            # the model is at stake.  It rides the run machine because it is
            # seconds-long (one profile fit, then one Le Bail per class),
            # takes ``cancel=``, and must hold the same one-worker discipline
            # as every other computation over the project.
            candidate = self._extinction_candidate(body)
            peak_doc = self._load_peaks(p)
            peak_list = None if peak_doc is None else peak_doc.peaks
            limits = (tuple(p.doc.two_theta_limits)
                      if p.doc.two_theta_limits else None)
            index = int(body["candidate"])
            max_classes = body.get("max_classes")
            max_classes = None if max_classes is None else int(max_classes)

            def call(stream, token):
                from ..indexing.extinction import determine_extinction_symbol

                screen = determine_extinction_symbol(
                    p.data, candidate, p.refinement.instrument,
                    peaks=peak_list, two_theta_limits=limits,
                    max_classes=max_classes, cancel=token)
                with self._cond:
                    self._extinction = {"screen": screen, "candidate": index}
                return screen

            summarize = _summarize_extinction
            label = "extinction"
            n_stages = 1
        elif kind == "series":
            # One run on the one machine (WP-1008's charter): a series is N fits,
            # but it is *one* long computation with one cancel token, and
            # ``SequentialRefinement`` already emits per-pattern events — since
            # WP-1016 it does, which is the half that charter assumed and the
            # library did not have.
            from ..sequential import SequentialRefinement

            setup = self._series
            if len(setup.members) < 2:
                raise GuiError(
                    f"a series needs at least two patterns; {len(setup.members)} "
                    "staged. One pattern is a fit — use Run — and the fences a "
                    "series exists for (reseed, discontinuity, path dependence) "
                    "all compare a pattern with its neighbours.",
                    code="NO_SERIES", status=409, where=["patterns"])
            plan = self._effective_plan(body.get("plan"))
            data = series_mod.read_members(setup, p.doc.excluded_regions)
            limits = (tuple(p.doc.two_theta_limits)
                      if p.doc.two_theta_limits else None)
            runner = SequentialRefinement(
                # the working state, not the root: a series warm-starts from
                # whatever the user has already got right in this project
                p.refinement.structure, p.refinement.instrument,
                backend=self.backend, solver=self.solver, carry=setup.carry,
                # in memory: the trees belong to patterns the project does not
                # own, so writing them into it would leave orphans no document
                # can interpret on the next open (see gui/series.py)
                history=True)
            members = [m.as_dict() for m in setup.members]

            def call(stream, token):
                result = runner.fit(
                    data, x=setup.x, x_label=setup.axis_label,
                    labels=setup.labels, mode=p.doc.mode, plan=plan,
                    refit=setup.refit, direction=setup.direction,
                    two_theta_limits=limits, events=stream, cancel=token,
                    # named, because a SequentialRefinement has no project to
                    # derive one from: its trees are in memory and belong to
                    # patterns this project does not own, so the fallback would
                    # put a GUI series' run under the working directory
                    telemetry=p.live_dir)
                with self._cond:
                    self._series_run = {"runner": runner, "result": result,
                                        "backward": runner.backward_,
                                        "members": members, "data": data,
                                        # the limits *this run* used, not the
                                        # document's now: a member's curves
                                        # cannot be re-fitted without replacing
                                        # the whole answer, so its masked band
                                        # must not move when a setting does
                                        "limits": limits}
                return result

            summarize = _summarize_series
            label = "series"
            n_stages = len(setup.members)
        else:
            plan = self._effective_plan(body.get("plan"))

            def call(stream, token):
                return p.fit(plan=plan, events=stream, cancel=token)

            label = ""
            n_stages = len(plan.stages)

        p.live_dir.mkdir(exist_ok=True)  # a project copied without empty dirs
        with self._cond:
            self._require_idle()
            token = CancelToken()
            # Callback only for the kinds that record themselves, since
            # WP-1403.  This used to carry ``path=live_dir/"events.jsonl"`` for
            # every kind, and a recorder chained onto it would then write the
            # whole eval stream **twice** — precisely the weight that WP exists
            # to control.  ``Project.fit``/``run_stage`` default ``telemetry``
            # to this project's ``live/`` and the series names it, so for those
            # three the log still lands there, in a run directory of its own
            # rather than in one log a second writer could interleave.
            #
            # ``index`` and ``extinction`` have no recorder — nothing in
            # ``indexing/`` attaches one — so for them the path *is* the log,
            # and dropping it would have left a GUI indexing run with no
            # on-disk trace at all for ``rietx watch`` to read.
            records_itself = kind in ("fit", "stage", "series")
            stream = EventStream(
                path=None if records_itself else p.live_dir / "events.jsonl",
                callback=self._push)
            self._state = "running"
            self._cancel = token
            self._events.clear()
            self._n_eval = 0
            self._run = {"kind": kind, "name": label, "status": None,
                         "stage": None, "stage_index": None, "n_stages": n_stages,
                         "started_utc": _utcnow(), "finished_utc": None,
                         "elapsed": None, "rwp": None, "gof": None,
                         "node_id": None, "completed_stages": [], "error": None}
            self._worker = threading.Thread(
                target=self._work, args=(call, stream, summarize),
                name=f"{_about.SERVER_TOKEN}-gui-run", daemon=True)
            self._worker.start()
            self._cond.notify_all()
        return self.state_frame()

    def cancel(self) -> dict:
        """Set the token.  Cooperative: read between residual evaluations."""
        with self._cond:
            if self._state == "idle":
                raise GuiError("nothing is running", code="NOT_RUNNING", status=409)
            if self._cancel is not None:
                self._cancel.cancel()
            self._state = "cancelling"
            self._cond.notify_all()
            return self._state_frame_locked()

    def run_state(self) -> dict:
        """The coarse state frame plus the fine progress a poller wants."""
        with self._cond:
            frame = self._state_frame_locked()
            started = self._run.get("started_utc")
            frame["n_eval"] = self._n_eval
            frame["seq"] = self._seq
            frame["last_event"] = self._events[-1] if self._events else None
            frame["run"]["elapsed"] = self._run.get("elapsed")
            if self._state != "idle" and started:
                frame["run"]["elapsed"] = self._elapsed()
            return frame

    def state_frame(self) -> dict:
        with self._cond:
            return self._state_frame_locked()

    def _state_frame_locked(self) -> dict:
        return {"state": self._state, "run": dict(self._run),
                "project": None if self.project is None else str(self.project.path),
                "head": (None if self.project is None
                         else self.project.refinement._head_id)}

    def events_since(self, since: int) -> dict:
        """Buffered events after ``since`` (the ``?poll=1`` fallback's payload).

        ``oldest`` is what tells a client it fell out of the window: if
        ``since + 1 < oldest`` the run emitted more than the ring holds and the
        gap is real, not a renumbering.
        """
        with self._cond:
            events = [e for e in self._events if e["seq"] > since]
            oldest = self._events[0]["seq"] if self._events else self._seq + 1
            return {"events": events, "next": self._seq, "oldest": oldest,
                    **self._state_frame_locked()}

    def follow(self, since: int, last_state: str = "",
               timeout: float = 1.0) -> tuple[list[dict], int, dict | None, str]:
        """Block until something changed, then hand back what did.

        Returns ``(events, next_seq, state_frame_or_None, state_key)``: the
        events after ``since``, the seq to ask for next, the state frame *only
        when it differs* from ``last_state``, and the key to pass back as
        ``last_state``.  The comparison is on the coarse frame, which is why
        ``n_eval`` is not in it — a frame per residual evaluation would make the
        state channel a duplicate of the event channel.
        """
        with self._cond:
            if not self._changed(since, last_state):
                self._cond.wait(timeout)
            events = [e for e in self._events if e["seq"] > since]
            frame = self._state_frame_locked()
            key = json.dumps(frame, sort_keys=True, default=str)
            return events, self._seq, (None if key == last_state else frame), key

    def _changed(self, since: int, last_state: str) -> bool:
        if self.closed or self._seq > since:
            return True
        key = json.dumps(self._state_frame_locked(), sort_keys=True, default=str)
        return key != last_state

    def close(self) -> None:
        """Release followers so a shutdown does not wait on a heartbeat."""
        with self._cond:
            self.closed = True
            self._cond.notify_all()
        self.uploads.close()  # staged bytes outlive nothing

    # -- the worker ----------------------------------------------------
    def _work(self, call, stream: EventStream, summarize) -> None:
        """Run one fit, stage or indexing search and record how it ended.

        Three endings, and the difference between them is the WP-1006 result: a
        cancelled *refinement* **raises** rather than returning a partial
        result, and what it leaves behind is on the exception — the stages that
        did complete and the node the working state now stands at, which is
        what a "resume" button checks out.  (A cancelled indexing search
        returns instead — it has nothing to abandon — which is why
        ``summarize`` reads the token.)
        """
        started = time.monotonic()
        token = self._cancel
        try:
            result = call(stream, token)
            finish = summarize(result, token)
        except RefinementCancelled as exc:
            finish = {"status": "cancelled", "stage": exc.stage,
                      "node_id": exc.node_id,
                      "completed_stages": [s.name for s in exc.completed_stages]}
        except Exception as exc:  # noqa: BLE001 — the run record IS the channel
            finish = {"status": "failed",
                      "error": {"code": "RUN_FAILED",
                                "message": f"{type(exc).__name__}: {exc}"}}
        finally:
            stream.close()
        with self._cond:
            self._run.update(finish)
            self._run["finished_utc"] = _utcnow()
            self._run["elapsed"] = time.monotonic() - started
            self._state = "idle"
            self._cancel = None
            self._worker = None
            self._cond.notify_all()

    def _push(self, event: dict) -> None:
        """``EventStream`` callback — runs on the worker thread, per event.

        Reads the payload with ``.get`` only.  ``data`` is an open dict by
        design (a new field is not a schema bump), so unpacking a fixed shape
        here is exactly the thing the event contract forbids.
        """
        data = event.get("data") or {}
        with self._cond:
            self._seq += 1
            self._events.append({"seq": self._seq, **event})
            kind = event.get("kind")
            series = data.get("series_index")
            if kind == "eval":
                self._n_eval = int(data.get("n_eval") or self._n_eval + 1)
            elif series is not None:
                # A series' progress is "pattern k of N", and the run record says
                # so through the *existing* three fields rather than three new
                # ones — the same reuse an indexing run makes of
                # ``stage_start``.  Its inner stages would otherwise fill them
                # with "warm_refit (1/1)", which is true and says nothing about a
                # forty-pattern chain.
                if kind == "fit_start":
                    self._run["stage"] = _series_stage_name(data, series)
                    self._run["stage_index"] = int(series) + 1
                    self._run["n_stages"] = (data.get("series_n")
                                             or self._run["n_stages"])
                elif kind == "fit_end":
                    completed = self._run["completed_stages"]
                    name = _series_stage_name(data, series)
                    if name not in completed:
                        completed.append(name)
            elif kind == "stage_start":
                self._run["stage"] = data.get("stage") or data.get("name")
                self._run["stage_index"] = data.get("index")
                if data.get("n_stages"):
                    self._run["n_stages"] = data["n_stages"]
            elif kind == "stage_end":
                completed = self._run["completed_stages"]
                name = data.get("stage") or data.get("name") or self._run["stage"]
                if name and name not in completed:
                    completed.append(name)
            self._cond.notify_all()

    def _elapsed(self) -> float:
        return max(0.0, time.time() - _parse_utc(self._run["started_utc"]))

    # ------------------------------------------------------------------
    # peaks (WP-1027)
    # ------------------------------------------------------------------
    def peaks(self) -> dict:
        """The stored peak list — or, before any pick, just the raw pattern.

        The pattern rides on every answer because the peak panel is the one
        surface that must draw *before a fit exists*: an indexing project has
        no fit to plot until a candidate is adopted and Le-Bail-fitted, and
        picking peaks by eye needs the counts on screen.
        Not idle-gated: it reads a project artifact and the pattern.
        """
        p = self._need_project()
        doc = self._load_peaks(p)
        if doc is None:
            return self._peaks_payload(None)
        return self._peaks_payload(doc, editor=self._peak_editor())

    def peaks_pick(self, body: dict) -> dict:
        """Run the picker and store the list — replacing any previous one,
        edits included, which is what "pick" has to mean."""
        self._require_idle()
        p = self._need_project()
        editor = self._peak_editor()
        shoulders = bool(body.get("shoulders", True))
        doc = editor.pick(shoulders=shoulders)
        self._save_peaks(p, doc)
        return self._peaks_payload(
            doc, editor=editor,
            api_call=f"session.pick_peaks(shoulders={shoulders})")

    def peaks_add(self, body: dict) -> dict:
        tt = self._peak_number(body, "two_theta")
        return self._peak_edit(
            lambda ed, doc: ed.add(doc, tt),
            api_call=f"session.add_peak({tt:g})", where=["two_theta"])

    def peaks_move(self, body: dict) -> dict:
        index = self._peak_index(body)
        tt = self._peak_number(body, "two_theta")
        return self._peak_edit(
            lambda ed, doc: ed.move(doc, index, tt),
            api_call=f"session.move_peak({index}, {tt:g})",
            where=["index", "two_theta"])

    def peaks_remove(self, body: dict) -> dict:
        index = self._peak_index(body)
        return self._peak_edit(
            lambda ed, doc: ed.remove(doc, index),
            api_call=f"session.remove_peak({index})", where=["index"])

    def peaks_flag(self, body: dict) -> dict:
        index = self._peak_index(body)
        use = body.get("use_for_indexing")
        flags = body.get("flags")
        if flags is not None and not isinstance(flags, list):
            raise GuiError("'flags' must be a list of flag words",
                           where=["flags"])
        args = (f"use_for_indexing={bool(use)}" if use is not None
                else f"flags={flags!r}")
        return self._peak_edit(
            lambda ed, doc: ed.flag(
                doc, index,
                use_for_indexing=None if use is None else bool(use),
                flags=flags),
            api_call=f"session.set_peak_flags({index}, {args})",
            where=["index", "flags"])

    def peaks_refit(self, body: dict) -> dict:
        group = self._peak_number(body, "group", int)
        n = body.get("n_components")
        n = None if n is None else int(n)
        args = f"{group}" if n is None else f"{group}, n_components={n}"
        return self._peak_edit(
            lambda ed, doc: ed.refit(doc, group, n_components=n),
            api_call=f"session.refit_group({args})",
            where=["group", "n_components"])

    def _peak_edit(self, edit, *, api_call: str, where: list[str]) -> dict:
        """One stored-list edit: load, apply, save, answer — with the echo.

        Every editing verb funnels through here so the rules hold once: idle
        only (an edit refits against the instrument a running stage is
        writing), the stored list is required (there is nothing to edit before
        a pick), a refused edit names its field, and the echo is the verb's own
        equivalent API line — the console transcript stays a script.
        """
        self._require_idle()
        p = self._need_project()
        editor = self._peak_editor()
        doc = self._need_peaks(p)
        try:
            doc = edit(editor, doc)
        except IndexError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404,
                           where=where) from None
        except ValueError as exc:
            raise GuiError(str(exc), where=where) from None
        self._save_peaks(p, doc)
        return self._peaks_payload(doc, editor=editor, api_call=api_call)

    def _peaks_payload(self, doc, *, editor=None, api_call: str = "") -> dict:
        from typing import get_args as _get_args

        from ..schemas.indexing import PEAK_UNUSABLE_FLAGS, PeakFlag

        out: dict[str, Any] = {
            "pattern": self._peaks_pattern(),
            # the split is the server's fact (usable() reads it); a client
            # re-deriving it from a hand-copied list would drift when the
            # vocabulary grows — the held_because rule again
            "flag_vocabulary": list(_get_args(PeakFlag)),
            "unusable_flags": sorted(PEAK_UNUSABLE_FLAGS),
        }
        if api_call:
            out["api_call"] = api_call
        if doc is None:
            out["peaks"] = None
            return out
        rows = []
        for i, peak in enumerate(doc.peaks.peaks):
            row = peak.model_dump(mode="json")
            row["index"] = i
            row["usable"] = peak.usable
            row["d"] = peak.d
            rows.append(row)
        out.update({
            "peaks": rows,
            "n_total": len(rows),
            "n_usable": sum(1 for r in rows if r["usable"]),
            "wavelength": doc.peaks.wavelength,
            "two_theta_min": doc.peaks.two_theta_min,
            "two_theta_max": doc.peaks.two_theta_max,
            "source": doc.peaks.source,
            "diagnostics": [d.model_dump(mode="json")
                            for d in doc.peaks.diagnostics],
            "pick_options": dict(doc.pick_options),
            "created_utc": doc.created_utc,
            "groups": [] if editor is None else editor.curves(doc),
        })
        return out

    def _peaks_pattern(self, max_points: int = 4000) -> dict:
        """The measured pattern, masked and decimated, for the peak plot.

        The masked channels ride along in ``excluded`` for the reason
        :meth:`result_curves` sends ``kept``: this is the view a project has
        *before* any fit, so it is the only place the fit range can be seen at
        all, and it cropped to the limits — a user could not see what they had
        cut.  The
        intersection itself is :meth:`Project.fitted_mask`, so this cannot
        drift from what the residual contains.
        """
        p = self._need_project()
        data = p.data
        keep = p.fitted_mask()
        tt_all, y_all = data.tt(), data.y()
        tt, y = tt_all[keep], y_all[keep]
        out_tt, out_y = tt_all[~keep], y_all[~keep]
        excluded = {"two_theta": [], "y_obs": []}
        if len(out_tt):
            out_idx = decimation_index(out_tt, [out_y], max(2, max_points // 4))
            excluded = {"two_theta": out_tt[out_idx].tolist(),
                        "y_obs": out_y[out_idx].tolist()}
        if not len(tt):
            return {"two_theta": [], "y_obs": [], "n_total": 0,
                    "excluded": excluded, "n_excluded": int(len(out_tt))}
        idx = decimation_index(tt, [y], max_points)
        return {"two_theta": tt[idx].tolist(), "y_obs": y[idx].tolist(),
                "n_total": int(len(tt)), "excluded": excluded,
                "n_excluded": int(len(out_tt))}

    def _peak_editor(self):
        from . import peaks as store

        p = self._need_project()
        instrument = p.refinement.instrument
        key = (instrument.model_dump_json(), str(p.doc.two_theta_limits),
               str(p.doc.excluded_regions))
        if self._peak_ed is not None and self._peak_ed[0] == key:
            return self._peak_ed[1]
        limits = tuple(p.doc.two_theta_limits) if p.doc.two_theta_limits else None
        editor = store.PeakEditor(p.data, instrument, two_theta_range=limits)
        self._peak_ed = (key, editor)
        return editor

    def _load_peaks(self, p):
        from . import peaks as store

        try:
            return store.load(p)
        except ValueError as exc:
            raise GuiError(str(exc), code="PEAKS_WRONG_PATTERN",
                           status=409) from None

    def _need_peaks(self, p):
        doc = self._load_peaks(p)
        if doc is None:
            raise GuiError("no peak list yet; POST /api/peaks to pick one",
                           code="NO_PEAKS", status=409)
        return doc

    def _save_peaks(self, p, doc) -> None:
        from . import peaks as store

        store.save(p, doc)

    @staticmethod
    def _peak_number(body: dict, key: str, cast=float):
        value = _need(body, key)
        try:
            return cast(value)
        except (TypeError, ValueError):
            raise GuiError(f"{key}={value!r} is not a number",
                           where=[key]) from None

    @classmethod
    def _peak_index(cls, body: dict) -> int:
        if body.get("index") is None:
            raise GuiError("'index' is required", where=["index"])
        return cls._peak_number(body, "index", int)

    # ------------------------------------------------------------------
    # indexing (WP-1027)
    # ------------------------------------------------------------------
    def index_result(self) -> dict:
        """The last indexing answer, with the adopt gate answered per row.

        ``adopt`` runs parallel to ``result.candidates`` and is the server
        saying whether :meth:`index_adopt` would act — the button's
        enabled-ness and the route's willingness must not be two answers
        (the ``report.apply`` rule).  ``refuting_caveats`` is served so the
        client colours chips from the constant rather than a hand-written list.
        """
        from ..schemas.indexing import INDEX_REFUTING_CAVEATS

        self._need_project()
        with self._cond:
            result = self._index_result
            busy = self._state != "idle" and self._run.get("kind") == "index"
        if result is None:
            raise GuiError(
                "an indexing run is in flight; follow /api/events" if busy
                else "no indexing run has completed in this session yet; "
                     "POST /api/index", code="NO_INDEX_RESULT", status=409)
        best = result.best_or_none()
        adopt = []
        for cand in result.candidates:
            allowed = best is not None and cand is best
            adopt.append({"allowed": allowed,
                          "why": "" if allowed else _adopt_refusal(cand, best)})
        return {"result": result.model_dump(mode="json"),
                "adopt": adopt,
                "refuting_caveats": sorted(INDEX_REFUTING_CAVEATS),
                "running": busy}

    @staticmethod
    def _candidate_number(result, index: int):
        """The candidate at ``index``, or the 404 that names how many there are.

        Shared by every verb that addresses one, so a client reading past the
        end sees the same sentence whichever it called.  The *no result at all*
        refusal deliberately stays with each verb, because it names what that
        verb was trying to do ("to screen", "to adopt from", "to draw") and one
        shared sentence could not.
        """
        if not 0 <= index < len(result.candidates):
            raise GuiError(
                f"no candidate {index}; the result has "
                f"{len(result.candidates)}", code="NOT_FOUND", status=404,
                where=["candidate"])
        return result.candidates[index]

    def index_ticks(self, index: int) -> dict:
        """Where candidate ``index`` says the lines are, on the pattern's axis.

        The overlay behind ``src/rietx/indexing/CLAUDE.md``'s reading rule for
        ``predicted_but_absent`` — "this cell predicts lines the pattern lacks",
        never "this cell is too big" — which is a claim about *positions* and
        was until now servable only as a count.  One
        :func:`~rietx.crystallography.symmetry.generate_reflections` call per
        emission line over the measured 2θ range: no fit, nothing stored, and
        deliberately not a field on
        :class:`~rietx.schemas.indexing.CellCandidate`, which it would grow by
        hundreds of floats per candidate for one consumer.

        Three decisions, each of which puts the lines off the peaks they exist
        to be compared with if it goes the other way.

        **No instrument zero shift.**  ``RefinementResult.ticks`` adds
        ``instrument.zero_shift`` because a compiled model's Bragg positions
        live in the corrected frame.  A candidate's do not: indexing fits the
        metric to the peak list's *raw* 2θ, so the cell already reproduces
        observed positions and adding the instrument's shift would count it
        twice.

        **The candidate's own shift template, inverted.**
        :func:`~rietx.indexing.qspace.refine_candidate` fits the metric to
        ``2θ_obs − c·T(θ)``, so landing back on the observed axis means adding
        ``c·T`` on.  ``T`` is evaluated at the Bragg position rather than at the
        observed one the fit used, which differ by ``c²·dT/d2θ`` — under 2e-5° at
        the 0.05° scale of
        :data:`~rietx.indexing.engines.DEFAULT_UNKNOWN_SHIFT_DEG`, four orders
        below the narrowest peak this package fits.  Where no template was asked
        for there is nothing to add: ``shift_coefficient`` is 0.0 by
        construction, the search having widened its *tolerance* instead
        (``INDEX_SHIFT_ALLOWANCE``).

        **The lattice group, not a space group.**  The symbol is
        :func:`~rietx.indexing.workflow.structure_from_candidate`'s, quoted
        rather than restated, so what is drawn is what the Le Bail validation
        was scored against: an absence-free group hides nothing, and a group
        carrying reflection conditions would excuse exactly the phantoms an
        oversized cell is caught by.

        One enumeration **per emission line**, unlike ``compile_model``, which
        needs a single shared hkl list because its windows and FCJ node counts
        are indexed by (line, reflection).  Nothing here is indexed that way, so
        each line gets exactly the reflections that reach the range at its own λ
        and that function's min-λ/max-λ frame translation is not restated.

        Not behind the 409: a read, like ``index_result`` beside it.
        """
        import numpy as np

        from ..crystallography.symmetry import generate_reflections
        from ..indexing.engines import (
            MAX_PREDICTED_REFLECTIONS,
            predicted_reflection_count,
        )
        from ..indexing.pairs import shift_template
        from ..indexing.workflow import structure_from_candidate

        p = self._need_project()
        with self._cond:
            result = self._index_result
        if result is None:
            raise GuiError("no indexing result to draw; POST /api/index first",
                           code="NO_INDEX_RESULT", status=409)
        candidate = self._candidate_number(result, index)
        cell = tuple(float(v) for v in candidate.cell)
        try:
            symbol = structure_from_candidate(candidate).phases[0].space_group
        except (ValueError, RuntimeError) as exc:
            # ``index_adopt`` catches the same pair around the same call: a
            # lattice group gemmi will not build is a fact about the candidate,
            # and every refusal on this surface is an envelope rather than a
            # traceback
            raise GuiError(str(exc), where=["candidate"]) from None

        tt_all = np.asarray(p.data.two_theta, dtype=float)
        lo, hi = float(np.min(tt_all)), float(np.max(tt_all))
        lams = [line.wavelength.value
                for line in p.refinement.instrument.source.lines]

        positions: list = []
        hkls: list = []
        lines: list = []
        for il, lam in enumerate(lams):
            # the crash guard, before every reach for the generator (engines.py).
            # A candidate is bounded by the search that found it, but the range
            # here is the *measured* one, which can be wider than the fitted one
            # the search enumerated over.
            if predicted_reflection_count(cell, lam, hi) > MAX_PREDICTED_REFLECTIONS:
                raise GuiError(
                    f"candidate {index} (a={cell[0]:.4g}, b={cell[1]:.4g}, "
                    f"c={cell[2]:.4g} Å) would enumerate more than "
                    f"{MAX_PREDICTED_REFLECTIONS:.0e} reflections at "
                    f"λ={lam:g} Å over {lo:g}-{hi:g}° 2θ",
                    code="INDEX_CELL_TOO_LARGE", status=409, where=["candidate"])
            refl = generate_reflections(symbol, cell, lam,
                                        two_theta_max=hi, two_theta_min=lo)
            tt = refl.two_theta(cell, lam)
            if candidate.shift_template:
                tt = tt + candidate.shift_coefficient * shift_template(
                    candidate.shift_template, tt)
            keep = np.isfinite(tt) & (tt >= lo) & (tt <= hi)
            positions.append(tt[keep])
            hkls.append(np.asarray(refl.hkl)[keep])
            lines.append(np.full(int(keep.sum()), il, dtype=np.int64))

        tt = np.concatenate(positions) if positions else np.zeros(0)
        hkl = (np.concatenate(hkls) if positions
               else np.zeros((0, 3), dtype=np.int64))
        line = (np.concatenate(lines) if positions
                else np.zeros(0, dtype=np.int64))
        order = np.argsort(tt, kind="stable")
        n_total = int(len(order))
        if n_total > MAX_CANDIDATE_TICKS:
            # Thinned by **rank**, so a dense stretch keeps proportionally more
            # lines than a sparse one — density in 2θ is what this picture is
            # read for, and ``n_total`` beside it is the half that keeps the
            # thinning from reading as coverage.
            #
            # Evenly over the ranks rather than every k-th: at 2001 lines the
            # stride is 2 and half the budget goes unspent for one line over.
            # ``unique`` because the rounding can land twice on one rank when
            # the spacing is barely over 1, and a line drawn twice is a lie
            # about the count as surely as a dropped one.
            picks = np.unique(np.linspace(
                0, n_total - 1, MAX_CANDIDATE_TICKS).round().astype(np.int64))
            order = order[picks]
        return {
            "candidate": index,
            "space_group": symbol,
            "two_theta": [round(float(v), 4) for v in tt[order]],
            "hkl": [[int(h) for h in row] for row in hkl[order]],
            "line": [int(v) for v in line[order]],
            "n_total": n_total,
            "n_returned": int(len(order)),
            # what was added to the Bragg positions to land them on the observed
            # axis: a drawn line is the cell's, plus this, and nothing else
            "shift_template": candidate.shift_template,
            "shift_coefficient": float(candidate.shift_coefficient),
        }

    def _extinction_candidate(self, body: dict):
        """Validate and fetch the candidate an extinction screen is asked of."""
        with self._cond:
            result = self._index_result
        if result is None:
            raise GuiError("no indexing result to screen; POST /api/index "
                           "first", code="NO_INDEX_RESULT", status=409)
        if body.get("candidate") is None:
            raise GuiError("'candidate' is required", where=["candidate"])
        return self._candidate_number(
            result, self._peak_number(body, "candidate", int))

    def index_extinction(self) -> dict:
        """The last extinction screen — ranked classes, never one space group.

        ``best`` is the index :meth:`ExtinctionScreen.best_or_none` points at
        (or ``None``), served for the same reason ``adopt`` rides
        ``index_result``: the panel's badge and the package's gate must be one
        answer.  Even the best row lists *every* space group in its class —
        the one place the singleton is unmeasurable rather than merely
        unsupported (WP-1025).
        """
        self._need_project()
        with self._cond:
            entry = self._extinction
            busy = (self._state != "idle"
                    and self._run.get("kind") == "extinction")
        if entry is None:
            raise GuiError(
                "an extinction screen is in flight; follow /api/events"
                if busy else
                "no extinction screen has run; POST /api/index/extinction",
                code="NO_EXTINCTION_RESULT", status=409)
        screen = entry["screen"]
        best = screen.best_or_none()
        return {"result": screen.model_dump(mode="json"),
                "candidate": entry["candidate"],
                "best": None if best is None else screen.candidates.index(best),
                "running": busy}

    def index_adopt(self, body: dict) -> dict:
        """Adopt one candidate cell as the model — through the gate, or not at
        all.

        The gate is re-asked here rather than trusted from the panel: only the
        candidate ``best_or_none()`` would return can be adopted, so no UI path
        can hand back a cell the API itself refuses to single out.  Adoption is
        a model edit (``Refinement.edit`` → one ``edit_model`` node, no new
        NodeKind): the structure becomes WP-1024's single-phase Le Bail scaffold
        (absence-free lattice group unless a ``space_group`` from the extinction
        screen is given, one dummy atom), and the document's mode follows to
        ``lebail`` — a Rietveld fit over a dummy atom is not a thing to offer.
        """
        self._require_idle()
        p = self._need_project()
        with self._cond:
            result = self._index_result
        if result is None:
            raise GuiError("no indexing result to adopt from; POST /api/index",
                           code="NO_INDEX_RESULT", status=409)
        if body.get("candidate") is None:
            raise GuiError("'candidate' is required", where=["candidate"])
        index = self._peak_number(body, "candidate", int)
        candidate = self._candidate_number(result, index)
        best = result.best_or_none()
        if best is None or candidate is not best:
            raise GuiError(
                f"candidate {index} cannot be adopted: "
                f"{_adopt_refusal(candidate, best)}",
                code="ADOPT_GATED", status=409, where=["candidate"])
        from ..indexing.workflow import structure_from_candidate

        space_group = body.get("space_group") or None
        try:
            structure = structure_from_candidate(
                candidate, space_group=space_group,
                name=str(body.get("name") or "indexed"))
        except (ValueError, RuntimeError) as exc:
            raise GuiError(str(exc), where=["space_group"]) from None
        a, b, c = candidate.cell[:3]
        label = (f"adopted indexed cell {a:.4f} {b:.4f} {c:.4f} Å "
                 f"({candidate.system}, {space_group or candidate.lattice_group})")
        node = p.refinement.edit(structure=structure, label=label)
        if p.doc.mode != "lebail":
            p.doc.mode = "lebail"
            p.save()
        sg = f", space_group={space_group!r}" if space_group else ""
        return {"node_id": node, "mode": p.doc.mode,
                "api_call": f"session.adopt_candidate({index}{sg})",
                **self.structure()}

    # ------------------------------------------------------------------
    # series (WP-1016)
    # ------------------------------------------------------------------
    def series(self) -> dict:
        """The staged series, its chain settings, and the protocol it inherits.

        Answers before any file is staged — an empty list plus the defaults *is*
        the empty state, and a client needs the ``choices``/``carry_help`` arms to
        draw the editor at all.  Needs a project, because the protocol it reports
        (mode, plan, limits, exclusions) is the project's.
        """
        p = self._need_project()
        plan = self._effective_plan()
        with self._cond:
            entry = self._series_run
            busy = self._state != "idle" and self._run.get("kind") == "series"
        return series_mod.setup_payload(
            self._series, running=busy, has_result=entry is not None,
            mode=p.doc.mode, plan_preset=self.plan()["preset"],
            n_stages=len(plan.stages))

    def series_put(self, body: dict) -> dict:
        """Replace the staged list and/or the chain settings.

        A whole-list PUT rather than add/remove/reorder verbs: the order *is* the
        series, so every edit a panel makes is "here is the series now", and one
        round trip cannot leave the server holding an order nobody chose.  Every
        file is read here (:func:`series.members_from`), which is WP-1014's
        two-phase property at N files — a file that does not parse is a message
        about that file rather than a chain that dies half way through.

        Idle-gated: the settings are what the next run will be *called* with.
        """
        self._require_idle()
        self._need_project()
        unknown = set(body) - {"patterns", "carry", "refit", "direction", "x_label"}
        if unknown:
            raise GuiError(f"unknown series setting(s): {sorted(unknown)}; the "
                           "mode, plan, limits and excluded regions are the "
                           "project's and are set through its own verbs",
                           where=sorted(unknown))
        setup = self._series
        carry = body.get("carry", setup.carry)
        refit = body.get("refit", setup.refit)
        direction = body.get("direction", setup.direction)
        try:
            series_mod.check_settings(carry, refit, direction)
            members = (series_mod.members_from(body["patterns"], self.uploads,
                                              setup.members)
                       if "patterns" in body else setup.members)
        except UploadRefused as exc:
            raise GuiError(str(exc), code=exc.code, status=exc.status,
                           where=["patterns"]) from None
        except series_mod.SeriesRefused as exc:
            # the field, not the request: a form highlights what to retype
            raise GuiError(str(exc), where=[exc.where]) from None
        self._series = series_mod.SeriesSetup(
            members=list(members), carry=[str(g) for g in carry], refit=refit,
            direction=direction,
            x_label=str(body.get("x_label", setup.x_label) or "index"))
        return self.series()

    def series_result(self) -> dict:
        """The last series answer: entries, trajectories, and the fences.

        Session-scoped like ``Refinement.result_`` and for the same reason — a
        ``SeriesResult`` is a computation over patterns the project does not own,
        so there is nothing on disk for it to be the stale view of.
        """
        self._need_project()
        with self._cond:
            entry = self._series_run
            busy = self._state != "idle" and self._run.get("kind") == "series"
        if entry is None:
            raise GuiError(
                "a series run is in flight; follow /api/events" if busy
                else "no series has completed in this session yet; stage the "
                     "patterns with PUT /api/series, then POST /api/series/run",
                code="NO_SERIES_RESULT", status=409)
        runner = entry["runner"]
        return series_mod.result_payload(
            entry["result"], entry["backward"], running=busy,
            curves=[bool(r.two_theta) for r in runner.results_])

    def _series_member_result(self, index: int):
        """The series entry and member ``index``'s result, which has curves, or a refusal."""
        entry = self._series_entry()
        runner = entry["runner"]
        if not 0 <= index < len(runner.results_):
            raise GuiError(
                f"no series pattern {index}; the run reached "
                f"{len(runner.results_)}", code="NOT_FOUND", status=404,
                where=["index"])
        res = runner.results_[index]
        if not res.two_theta:
            raise GuiError("this series pattern carries no curves",
                           code="NO_RESULT", status=409)
        return entry, res

    def series_curves(self, index: int) -> Packed:
        """One series member's channels and curves, as :meth:`result_curves` serves the project's.

        Built by :func:`curve_arrays`, so the σ policy is the project plot's
        (CLAUDE.md: every weighted residual divides by ``sig()``).

        The masked channels come from this member's own pattern through
        ``project.fitted_mask``, the one authority, under the limits **this
        run** used and the member's own ``excluded_regions`` as it was read. A
        result carries only the channels ``compile_model`` kept, so without
        them the per-pattern plot would range inside the fit range and the
        protocol would be invisible in a picture of its own output (WP-1033).
        There is no stale arm and no need for one: the mask cannot drift from
        the curves beside it, because a series member cannot be refitted under
        a new protocol without re-running the chain, which replaces the whole
        answer.
        """
        from ..project import fitted_mask

        entry, res = self._series_member_result(index)
        data, member = entry["data"][index], entry["members"][index]
        return curve_arrays(
            data.tt(), data.y(), fitted_mask(data, entry["limits"]), res,
            weighted=bool(member["has_sigma"]),
            header={"index": index, "label": member["label"], "x": member["x"]})

    def series_history(self, index: int) -> dict:
        """One series member's own history tree — read-only, and that is the point.

        There is one tree per pattern, never one for the series
        (``TreeHeader.data_fingerprint`` pins a tree to its data), so a node here
        **cannot be checked out** into this project: its state was fitted against
        another pattern, and restoring it would be the silent rebinding
        ``Project.open`` refuses.  What it is for is reading — the warm-start link
        is recorded in the root node's ``notes``
        (``series_warm_start_tree``/``…_node``), so this payload is what makes a
        chain navigable.
        """
        entry = self._series_entry()
        runner = entry["runner"]
        if not 0 <= index < len(runner.trees_):
            raise GuiError(
                f"no series pattern {index}; the run reached "
                f"{len(runner.trees_)}", code="NOT_FOUND", status=404,
                where=["index"])
        tree = runner.trees_[index]
        if tree is None:  # pragma: no cover - the GUI always runs with history
            raise GuiError("this series was run without history",
                           code="NO_HISTORY", status=409)
        member = entry["members"][index]
        return {"index": index, "label": member["label"],
                "checkout": False, **tree_payload(tree)}

    def _series_entry(self) -> dict:
        with self._cond:
            entry = self._series_run
        if entry is None:
            raise GuiError("no series has completed in this session yet",
                           code="NO_SERIES_RESULT", status=409)
        return entry

    # ------------------------------------------------------------------
    # results
    # ------------------------------------------------------------------
    def result(self) -> dict:
        """The last result without its curves (they go through ``result_curves``).

        A 40 000-point pattern is five arrays of 40 000 floats: ~4 MB of JSON,
        whose serialisation alone took the curves route 52-57 ms on NAC where
        float64 binary takes 0.2 ms (WP-1461, D4). So the arrays are excluded
        here and sent once as arrays, and what is left is the whole of the rest:
        statistics, refined values with esds, per-stage outcomes, diagnostics,
        QPA, absorption, provenance.

        ``maturity`` is WP-1029's one honest signal that a fit is hopeless, and
        it is deliberately **not** a new word.  It quotes the FitReport's own
        `MATURITY_MAX_RWP` — the Rwp past which Layer 1 refuses to say anything
        about individual parameters — so a client can stop rendering such a fit
        in the same register as a good one without inventing a judgement, and
        without touching the ``status`` vocabulary (a run that reaches this
        state still reports ``converged``, which is WP-1028's to fix and not
        this route's).  Served here rather than derived in the client for the
        reason ``held_because`` travels on a parameter row: a threshold the
        package owns must not have a second copy in TypeScript.
        """
        from ..report.schemas import MATURITY_MAX_RWP

        res = self._need_result()
        payload = res.model_dump(mode="json", exclude={
            "two_theta", "y_obs", "y_calc", "y_background", "sigma"})
        payload["curves"] = {
            "n_points": len(res.two_theta),
            "two_theta_range": ([res.two_theta[0], res.two_theta[-1]]
                                if res.two_theta else None)}
        rwp = float(res.statistics.rwp)
        payload["maturity"] = {
            "immature": rwp > MATURITY_MAX_RWP,
            "max_rwp": MATURITY_MAX_RWP,
            "message": (
                f"Rwp {rwp:.1%} is past the point where the report will speak "
                f"about individual parameters (Layer 1 abstains above "
                f"{MATURITY_MAX_RWP:.0%}). At this level the usual cause is not "
                f"a parameter but a premise: check that the structure and the "
                f"pattern are of the same specimen, and read Layer 0's "
                f"unmatched peaks before changing anything."
                if rwp > MATURITY_MAX_RWP else ""),
        }
        return {"result": payload}

    def result_curves(self) -> Packed:
        """Every channel of the pattern, and the last fit's curves on the ones it kept.

        The payload behind a chart that zooms in the browser (WP-1461, D4), so
        it is sent once and never per zoom. Before any fit it is the pattern
        alone, which is the raw view. :func:`curve_arrays` builds it, and its
        docstring gives the contract. Three facts on it were each measured
        before they were sent, and each is a defect when it goes missing:

        - **The masked channels travel beside the fitted ones** (WP-1033). A
          result carries only the channels ``compile_model`` kept, so with
          ``two_theta_limits`` set a plot's x axis fitted *inside* the fit
          range and a user could not see what they cut: on the synthetic
          fixture a 3–24° pattern came back as 8.005–18.990°, with zero points
          inside a 3° exclusion. ``kept`` is ``Project.fitted_mask``, so what
          is shaded is what the next run fits.
        - **``stale`` compares the fitted 2θ values, not their count.** Settings
          persist on the verb and curves move only on a run, so between an
          exclusion and the next fit the curves on screen were computed over
          another channel set (measured: 586 points inside a new band still in
          the residual), and two masks can keep the same number of channels.
        - **``weighted`` is whether σ was measured**, ``DataRef.has_sigma``: the
          file's esd column against the Poisson ``√max(y,1)`` estimate. Δ/σ is
          divided by a σ either way, since the fit always weighted by
          something, so the flag changes an axis title and never which curve
          is drawn. It cannot be read off the result, whose ``sigma`` has
          already collapsed the two into one list of floats; ``bool(res.sigma)``
          was a constant until WP-1029 (s), and a Poisson fit's axis said its σ
          had been measured.
        """
        p = self._need_project()
        # read once: the worker swaps the result wholesale (``_need_result``)
        res = p.refinement.result_
        return curve_arrays(p.data.tt(), p.data.y(), p.fitted_mask(), res,
                            weighted=p.data_ref.has_sigma)

    def report(self, plan: str | None = None) -> dict:
        """The three-layer :class:`FitReport` for the last fit, plus what applies.

        Needs the compiled model, so it is idle-only: Layers 1-2 read the
        derivative expansion of the state a stage would be rewriting.

        ``apply`` runs **parallel to** ``report["suggested_actions"]``, one entry
        per action in the same order, and says whether :meth:`report_apply` would
        act on it and what it would run.  Parallel rather than keyed by kind
        because a kind is not unique — two textured phases emit two
        ``refine_preferred_orientation`` actions — and served here rather than
        computed in the client for the reason ``held_because`` travels on a
        parameter row: a button's enabled-ness and the route's willingness to act
        must not be two answers.
        """
        report = self._report_object(plan)
        # both hoisted: ``_held`` rebuilds a ParameterTable and ``_indexing`` probes
        # every optional dependency's import, and a report carries a dozen actions
        held, indexing = self._held(), _indexing()
        return {"report": report.model_dump(mode="json"),
                "apply": [describe_action(a, held=held, indexing=indexing)
                          for a in report.suggested_actions]}

    def _held(self) -> dict[str, str]:
        """Every parameter path → why it is held, ``""`` when it is refinable.

        The reachability half of ``report.apply`` reads this rather than a list of
        refinable paths, so a refusal can quote ``held_because`` verbatim instead
        of guessing which of the three reasons applies.
        """
        return {row.path: row.held_because
                for row in self._need_project().parameters()}

    def _report_object(self, plan: str | None = None):
        self._require_idle()
        p = self._need_project()
        self._need_result()
        try:
            return p.refinement.report(plan=plan or self._effective_plan())
        except RuntimeError as exc:
            raise GuiError(str(exc), code="NO_RESULT", status=409) from None

    def report_apply(self, body: dict) -> dict:
        """Carry out one suggested action — as one stage, through ``run``.

        The action is looked up in a report built **now**, not taken from the
        body: a client-supplied glob would make this a second spelling of
        ``POST /api/run``, and the veto (which the strategy engine holds) is a
        server-side judgement that a stale panel must not be able to skip.
        ``paths`` is only a disambiguator — a kind can appear twice, and guessing
        which of two textured phases was meant is exactly the confident-wrong
        singleton this report is built not to produce.

        Returns before the run finishes, like every other run: what is new is
        ``undo`` (the head to check out to get back — an applied action is a
        history node, so undo needs no inverse verb) and ``chi2_before``, which is
        what lets a panel put the *observed* Δχ² beside the predicted one.
        """
        self._require_idle()
        p = self._need_project()
        kind = _need(body, "kind")
        report = self._report_object(body.get("plan"))
        action = _pick_action(report, kind, body.get("paths"))
        why = refusal(action, held=self._held(), indexing=_indexing())
        if why:
            raise GuiError(
                f"{kind} cannot be applied here: {why}", code="ACTION_NOT_APPLICABLE",
                status=409, where=list(action.parameter_paths))
        stage = stage_for(action)
        undo = p.refinement._head_id
        before = p.refinement.result_.statistics.chi2
        frame = self.run({"kind": "stage", "stage": stage.model_dump(mode="json")})
        return {"applied": {"kind": action.kind,
                            "confidence": action.confidence,
                            "rationale": action.rationale,
                            "expected_delta_chi2": action.expected_delta_chi2,
                            "stage": stage.model_dump(mode="json")},
                "api_call": api_call(stage), "undo": undo,
                "chi2_before": before, **frame}

    # ------------------------------------------------------------------
    # history
    # ------------------------------------------------------------------
    def history(self) -> dict:
        """The DAG as nodes a client can draw, without any node's full state.

        A node is ~10 kB of structure and instrument; a tree of thirty is 300 kB
        of models nobody is looking at.  What a worktree panel needs is the
        shape, the action, the metrics and the diagnostics count — plus
        ``api_call``, which is the node's equivalent public-API line and turns
        the log into a script a user can copy.
        """
        return tree_payload(self._need_project().history)

    def history_diff(self, a: str, b: str) -> dict:
        tree = self._need_project().history
        try:
            diff = tree.diff(a, b)
        except KeyError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None
        return {"a": tree.resolve(a), "b": tree.resolve(b),
                "diff": {path: list(pair) for path, pair in diff.items()}}

    def history_compare(self, node_ids: list[str]) -> dict:
        tree = self._need_project().history
        try:
            return {"rows": tree.compare(node_ids)}
        except KeyError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None

    def history_checkout(self, body: dict) -> dict:
        """Restore a node's state as the working state (``git checkout``)."""
        self._require_idle()
        p = self._need_project()
        node_id = _need(body, "node_id")
        try:
            p.refinement.checkout(node_id)
        except KeyError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None
        return {"head": p.refinement._head_id, **self.params()}

    def history_branch(self, body: dict) -> dict:
        """Check a node out **and name it** — which is what a branch is here.

        Worth being explicit, because the word promises something this DAG does
        not have: there are no moving refs, only ``head``.  A fork appears when
        you run a stage from a node that already has a child, so "branch" is not
        a separate act — the useful half is *naming the fork point* so a history
        panel can label the lane, and that is a tag.  ``Refinement.branch``
        (a second in-process working tree over one tree) has no meaning for a
        one-project session and is not what this route calls.
        """
        p = self._need_project()
        node_id = _need(body, "node_id")
        name = str(body.get("name") or "").strip()
        out = self.history_checkout({"node_id": node_id})
        if name:
            self.history_tag({"node_id": node_id, "name": name})
        return {"branched_from": p.history.resolve(node_id), "name": name, **out}

    def history_tag(self, body: dict) -> dict:
        p = self._need_project()
        try:
            p.history.tag(_need(body, "node_id"), _need(body, "name"))
        except (KeyError, ValueError) as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None
        return {"tags": {k: v for k, v in p.history.refs.items() if k != "head"}}

    def history_annotate(self, body: dict) -> dict:
        p = self._need_project()
        try:
            p.history.annotate(_need(body, "node_id"), label=body.get("label"),
                               notes=body.get("notes") or {},
                               scores=body.get("scores") or {})
        except KeyError as exc:
            raise GuiError(str(exc), code="NOT_FOUND", status=404) from None
        return {"annotated": p.history.resolve(body["node_id"])}

    # ------------------------------------------------------------------
    # exports
    # ------------------------------------------------------------------
    def export(self, kind: str, body: dict) -> dict:
        """Write an export into ``<project>/exports/``.

        Idle-only, and not because it writes: ``write_cif`` and the reflection
        table read the *compiled model*, which a running stage owns.

        Two gates, not one.  Everything here describes a fit and needs a result;
        ``_EXPORT_MODEL_ONLY`` names the kinds that describe the model instead
        and are answered from the project alone.
        """
        self._require_idle()
        p = self._need_project()
        if kind not in EXPORT_DEFAULTS:
            raise GuiError(f"unknown export {kind!r}; "
                           f"available: {sorted(EXPORT_DEFAULTS)}",
                           code="NOT_FOUND", status=404)
        res = None if kind in _EXPORT_MODEL_ONLY else self._need_result()
        target = self._export_target(body.get("filename") or EXPORT_DEFAULTS[kind])
        ref = p.refinement
        try:
            if kind == "instrument_profile":
                from ..io.instrument_profile import save_instrument_profile

                save_instrument_profile(ref.instrument, target)
            elif kind == "cif":
                ref.write_cif(target)
            elif kind == "reflections":
                ref.write_reflection_table(target)
            elif kind == "qpa":
                ref.write_qpa_table(target)
            elif kind == "html":
                from ..viz.html import write_html

                write_html(res, str(target))  # type: ignore[arg-type]
            else:
                target.write_text(res.model_dump_json(indent=2),  # type: ignore[union-attr]
                                  encoding="utf-8")
        except RuntimeError as exc:
            # "no QPA on this result (Rietveld fits only)" is the interesting
            # one: a Le Bail fit has no weight fractions, and saying so beats
            # writing an empty table
            raise GuiError(str(exc), code="EXPORT_UNAVAILABLE", status=409) from None
        return {"kind": kind, "path": str(target), "name": target.name,
                "bytes": target.stat().st_size}

    def _export_target(self, filename: str) -> Path:
        p = self._need_project()
        root = p.exports_dir.resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / filename).resolve()
        if not target.is_relative_to(root):
            raise GuiError(f"{filename!r} escapes the project's exports directory",
                           where=["filename"])
        return target

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _adopt(self, project: Project) -> None:
        with self._cond:
            self.project = project
            self._events.clear()
            self._seq = 0
            self._n_eval = 0
            self._run = _idle_run()
            self._index_result = None
            self._extinction = None
            self._peak_ed = None
            # a series is staged against a project's protocol and warm-started
            # from its models, so another project's series is not this one's
            self._series = series_mod.SeriesSetup()
            self._series_run = None
            self._cond.notify_all()
        self._remember(project.path)

    def _remember(self, path: Path) -> None:
        entry = {"path": str(Path(path).resolve()), "opened_utc": _utcnow()}
        kept = [e for e in self.recent() if e["path"] != entry["path"]]
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            (self.state_dir / "recent.json").write_text(
                json.dumps([entry, *kept][:_MAX_RECENT], indent=2), encoding="utf-8")
        except OSError:
            pass  # a read-only home is not a reason to fail opening a project

    def _need_project(self) -> Project:
        if self.project is None:
            raise GuiError("no project is open; POST /api/project/new or "
                           "/api/project/open first",
                           code="NO_PROJECT", status=409)
        return self.project

    def _need_result(self):
        p = self._need_project()
        result = p.refinement.result_  # read once: the worker swaps it wholesale
        if result is None:
            raise GuiError("no fit has been run in this session yet (a reopened "
                           "project resumes at its head, which carries state and "
                           "metrics but no curves — run a stage to get a result)",
                           code="NO_RESULT", status=409)
        return result

    def _require_idle(self) -> None:
        with self._cond:
            if self._state != "idle":
                raise GuiError(
                    f"a refinement is {self._state}; this verb would change the "
                    "model a compiled stage was built from (frozen-per-stage "
                    "discreteness). Cancel it or wait for it to finish.",
                    code="RUN_IN_FLIGHT", status=409)

    def _effective_plan(self, override: Any = None):
        """The plan a run would use: an override, the document's, or the default."""
        p = self._need_project()
        if override is not None:
            return resolve_plan(_as_plan_argument(override), p.doc.mode)
        if p.doc.plan is not None:
            return p.doc.plan.to_plan()
        return resolve_plan("mccusker_default", p.doc.mode)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def curve_arrays(tt_all, y_all, keep, res, *, weighted: bool,
                 header: dict | None = None) -> Packed:
    """:func:`rietx.viz.packed.curve_arrays`, whose refusal is a 409 here.

    The builder moved to ``viz`` so the file ``write_html`` writes draws the
    payload these routes send (WP-1461, task 10). A result off the pattern's
    channels is a run to repeat, which is what a 409 says.
    """
    try:
        return _packed.curve_arrays(tt_all, y_all, keep, res, weighted=weighted,
                                    header=header)
    except _packed.OffPattern as exc:
        raise GuiError(str(exc), code="RESULT_NOT_ON_PATTERN", status=409) from None


def tree_payload(tree) -> dict:
    """A history tree as nodes a client can draw, without any node's full state.

    ``GuiSession.history``'s body, taking the tree explicitly: a series is N
    trees (one per pattern, each pinned to its own data fingerprint), and the
    panel that walks into one of them needs the same node shape the project's own
    history panel already renders — `lib/history.ts`'s lane layout is reusable
    only if the payload is identical.
    """
    tags: dict[str, list[str]] = {}
    for name, node_id in tree.refs.items():
        if name != "head":
            tags.setdefault(node_id, []).append(name)
    nodes = []
    for node_id in tree.order:
        node = tree.nodes[node_id]
        stats = node.metrics.statistics
        nodes.append({
            "id": node.id, "parents": list(node.parents),
            "label": node.label, "created_utc": node.created_utc,
            "kind": node.action.kind, "name": node.action.name,
            "action": node.action.model_dump(mode="json"),
            "api_call": node.action.api_call(),
            "status": node.metrics.status,
            "n_iterations": node.metrics.n_iterations,
            "rwp": None if stats is None else stats.rwp,
            "gof": None if stats is None else stats.gof,
            "n_free": None if stats is None else stats.n_free_parameters,
            "n_diagnostics": len(node.diagnostics),
            "diagnostics": [d.model_dump(mode="json") for d in node.diagnostics],
            "tags": tags.get(node.id, []),
            "children": [c.id for c in tree.children(node.id)],
            "scores": dict(node.scores), "notes": dict(node.notes),
        })
    return {"tree_id": tree.header.tree_id, "head": tree.head,
            "root": None if tree.root is None else tree.root.id,
            "n_nodes": len(tree), "nodes": nodes}


def _summarize_refinement(result, _token) -> dict:
    """The run-record fields a finished fit or stage supplies."""
    return {"status": result.status, "rwp": result.statistics.rwp,
            "gof": result.statistics.gof, "node_id": result.node_id,
            "completed_stages": [s.name for s in result.stages]}


def _summarize_index(result, token) -> dict:
    """The run-record fields a finished indexing search supplies.

    No Rwp, no node — an ``IndexingResult`` is not a refinement.  The status is
    read off the token because a cancelled search *returns* what it has rather
    than raising (it has no seeded stage to abandon).
    """
    cancelled = token is not None and bool(token)
    return {"status": "cancelled" if cancelled else "completed",
            "completed_stages": [f"engine:{name}"
                                 for name in result.engines_run]}


def _series_stage_name(data: dict, index: Any) -> str:
    """What the progress pill says while a series pattern is being fitted.

    The label alone would be a lie twice over on the same number: a
    ``direction="both"`` run walks every pattern a second time in reverse (so the
    counter goes 1…N and back to 1, which reads as a restart unless the pass is
    named), and a rejected pattern is fitted **up to three times** by design —
    the warm fit, then each rung of the escalation ladder that judges it
    (WP-1051).  Both facts are already on the event's open ``data``; this is the
    two of them made readable.

    The rung is read off ``series_rung``, which the chain stamps on restarts
    only, so a pattern's first attempt is unsuffixed — including the first
    pattern of a chain, which runs the cold rung without being a rescue.
    """
    name = str(data.get("series_label") or index)
    if data.get("series_pass") == "backward":
        name += " (backward)"
    restart = {"warm_staged": " (staged restart)", "cold": " (cold restart)"}
    return name + restart.get(str(data.get("series_rung") or ""), "")


def _summarize_series(result, token) -> dict:
    """The run-record fields a finished series supplies.

    ``rwp``/``gof`` are the **last** entry's, not an average: a series has N of
    each and averaging them would invent a statistic no fit computed.  The status
    is read off the token for the same reason an indexing run's is — a cancelled
    series returns the patterns that completed rather than raising (the module
    docstring of :mod:`rietx.sequential` says why that is WP-1006's rule and
    not an exception to it) — and ``completed_stages`` is the patterns reached, so
    the header's stage list reads as the chain's progress.
    """
    cancelled = token is not None and bool(token)
    last = result.entries[-1].statistics if result.entries else None
    return {"status": "cancelled" if cancelled else "completed",
            "rwp": None if last is None else last.rwp,
            "gof": None if last is None else last.gof,
            "completed_stages": [e.label or str(e.index) for e in result.entries]}


def _summarize_extinction(result, token) -> dict:
    """The run-record fields a finished extinction screen supplies.

    Like an indexing search, a cancelled screen *returns* what it has (the
    unfitted classes stay ``screened=False`` and ``best_or_none`` abstains),
    so the status is read off the token.
    """
    cancelled = token is not None and bool(token)
    return {"status": "cancelled" if cancelled else "completed",
            "completed_stages":
                [f"classes:{result.n_screened}/{result.n_classes}"]}


def _adopt_refusal(candidate, best) -> str:
    """Why ``best_or_none()`` would not return this candidate, in one line."""
    if candidate.confidence != "high":
        caveats = ", ".join(candidate.confidence_caveats)
        return (f"confidence is {candidate.confidence!r}"
                + (f" ({caveats})" if caveats else "")
                + "; only the one candidate best_or_none() returns can be "
                  "adopted")
    if candidate.ambiguity:
        return ("a geometrically indistinguishable lattice exists; the "
                "discriminating reflections are listed on the candidate")
    return ("more than one candidate reached 'high'; the result cannot "
            "single one out")


def _idle_run() -> dict:
    return {"kind": None, "name": "", "status": None, "stage": None,
            "stage_index": None, "n_stages": None, "started_utc": None,
            "finished_utc": None, "elapsed": None, "rwp": None, "gof": None,
            "node_id": None, "completed_stages": [], "error": None}


def _parse_utc(stamp: str) -> float:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=UTC).timestamp()


def _locate(message: str, text: str) -> dict:
    """Attach a line number to a verb's refusal by finding the path it names.

    The verbs raise in their own words — ``'phases.0.cell.b' follows … as an
    affine tie``, ``phases.0.atoms.0.biso=999.0 lies outside its bounds`` — and a
    text editor needs a line, so the **path** is extracted from the message and
    matched against the document instead of the message being rewritten here.

    A row line carries its *local* path (``atoms.0.biso`` inside ``phase 0``), so
    the match is on a trailing dot-component of a full path, and the longest
    candidate wins: a tie message names both the refused path and its source, and
    the refused one is the one to point at.
    """
    candidates = sorted(re.findall(r"[A-Za-z_][\w*?]*(?:\.[\w*?]+)+", message),
                        key=len, reverse=True)
    for path in candidates:
        for n, line in enumerate(text.splitlines(), start=1):
            head = line.split("#", 1)[0].split()
            token = head[0] if head else ""
            if token and (token == path or path.endswith(f".{token}")):
                return {"line": n, "message": message, "where": path,
                        "text": line.rstrip()}
    return {"line": 0, "message": message, "where": "", "text": ""}


def _indexing() -> bool:
    """Whether this build has an indexing engine — a *derived* predicate.

    Read through ``capabilities()`` rather than by importing ``index``, so the one
    action whose availability is a build feature turns on by itself when WP-1024
    lands and nothing here has to be edited (WP-1007's rule).
    """
    return bool(_capabilities().features.get("indexing"))


def _pick_action(report, kind: str, paths: Any = None):
    """The one suggestion ``kind`` (and optionally ``paths``) names.

    ``FitReport.action`` returns the *first* match, which is wrong here: two
    textured phases emit two ``refine_preferred_orientation`` actions with
    different ``parameter_paths``, and applying the wrong one would free the wrong
    phase's March coefficient.  So an ambiguous request is refused and told how to
    disambiguate rather than resolved by position.
    """
    hits = [a for a in report.suggested_actions if a.kind == kind]
    if not hits:
        raise GuiError(
            f"this report suggests no {kind!r}; it suggests "
            f"{[a.kind for a in report.suggested_actions]}",
            code="NOT_FOUND", status=404, where=["kind"])
    if paths is not None:
        wanted = [str(p) for p in paths]
        exact = [a for a in hits if list(a.parameter_paths) == wanted]
        if not exact:
            raise GuiError(
                f"no {kind!r} suggestion carries paths {wanted}; this report has "
                f"{[list(a.parameter_paths) for a in hits]}",
                code="NOT_FOUND", status=404, where=["paths"])
        return exact[0]
    if len(hits) > 1:
        raise GuiError(
            f"{len(hits)} {kind!r} suggestions in this report; send 'paths' to say "
            f"which — {[list(a.parameter_paths) for a in hits]}",
            code="AMBIGUOUS_ACTION", where=["paths"])
    return hits[0]


def _need(body: dict, key: str):
    value = body.get(key)
    if value in (None, ""):
        raise GuiError(f"{key!r} is required", where=[key])
    return value


def _validate(model, payload, where: str):
    """``model.model_validate`` with pydantic's complaint kept addressable."""
    from pydantic import ValidationError

    if not isinstance(payload, dict):
        raise GuiError(f"{where} must be an object", where=[where])
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        # a model-level error has an empty loc; ``"structure."`` would be a
        # dot-path to nothing, and the GUI highlights fields by this string
        paths = [".".join([where, *(str(p) for p in err["loc"])])
                 for err in exc.errors()]
        raise GuiError(f"{where} failed validation: {exc.error_count()} error(s); "
                       f"{exc.errors()[0]['msg']} at {paths[0]}",
                       where=paths) from None


#: The dot-path a ``ParameterTable`` refusal opens with (``phases.0.atoms.3: the
#: anisotropic tensor …``, ``phases.0.atoms.3 sits on a fully fixed special
#: position``).  ``Refinement.edit`` prefixes its own sentence, so this
#: *searches* rather than anchors — it is what lets :meth:`GuiSession._edit`
#: address the field without parsing a sentence it does not own.
_LEADING_PATH = re.compile(r"\b((?:phases|instrument)\.[\w.]*[\w])")


def _is_typed_cell(payload) -> bool:
    """Is this ``structure`` argument the typed-cell form? (WP-1206)

    The four forms are told apart by their keys, and these are disjoint: a whole
    :class:`Structure` has ``phases``, the file forms have ``cif``/``upload``.
    """
    return isinstance(payload, dict) and "space_group" in payload


def _typed_cell_structure(payload: dict) -> Structure:
    """The Le Bail scaffold a person typed: a symbol and the free cell parameters.

    A project without a CIF (WP-1206).  What is supplied is exactly what a
    powder pattern can be indexed to — a lattice and a symmetry — and nothing
    about where the atoms are, so the result is
    :func:`~rietx.schemas.structure.lebail_scaffold`, the same structure the
    indexing panel's Adopt button lands.

    Four refusals, all naming the field they are about, because this is a form:
    an unresolvable symbol in ``get_spacegroup``'s words, a cell parameter the
    symmetry determines or leaves out in ``complete_cell``'s, and a non-numeric
    or unphysical one here.  Nothing is checked twice — ``complete_cell`` fills
    the fixed angles from the setting, so an angle contradicting its symmetry is
    unrepresentable rather than caught later by ``ParameterTable``.

    ``NaN``/``inf`` and a length ``≤ 0`` are refused *here* rather than left to
    the schema: ``Parameter`` has no positivity rule, so a zero or negative edge
    validated fine and died at stage compile, a long way from the box it was
    typed in — the same reason the species check sits at this boundary.
    """
    from ..crystallography.symmetry import CELL_NAMES, complete_cell, get_spacegroup
    from ..schemas.structure import lebail_scaffold

    symbol = str(payload.get("space_group") or "").strip()
    if not symbol:
        raise GuiError("'structure.space_group' is required",
                       where=["structure.space_group"])
    try:
        sg = get_spacegroup(symbol)
    except (ValueError, RuntimeError) as exc:
        raise GuiError(str(exc), where=["structure.space_group"]) from None

    # before the cell is read: a typo'd key is the caller's real mistake, and
    # reporting a cell complaint first would send them to the wrong field
    unknown = set(payload) - {"space_group", "cell", "name"}
    if unknown:
        raise GuiError(
            f"unknown key(s) for a typed cell: {sorted(unknown)}; it takes a "
            "space_group, a cell and an optional phase name",
            where=[f"structure.{k}" for k in sorted(unknown)])

    raw = payload.get("cell")
    if not isinstance(raw, dict):
        raise GuiError(
            "'structure.cell' is an object keyed by cell parameter — the ones "
            f"{symbol!r} leaves free, from GET /api/spacegroup",
            where=["structure.cell"])
    values: dict[str, float] = {}
    for name, value in raw.items():
        key = str(name)
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise GuiError(f"{key} is not a number: {value!r}",
                           where=[f"structure.cell.{key}"]) from None
        if not math.isfinite(number):
            raise GuiError(f"{key} is not a finite number: {value!r}",
                           where=[f"structure.cell.{key}"])
        if number <= 0.0:
            raise GuiError(
                f"{key} must be greater than zero, not {number:g}",
                where=[f"structure.cell.{key}"])
        if key in ("alpha", "beta", "gamma") and number >= 180.0:
            raise GuiError(
                f"{key} must be less than 180°, not {number:g}",
                where=[f"structure.cell.{key}"])
        values[key] = number
    try:
        cell = complete_cell(sg, values)
    except ValueError as exc:
        raise GuiError(str(exc), where=["structure.cell"]) from None

    name = str(payload.get("name") or "").strip()
    return lebail_scaffold(symbol, [cell[k] for k in CELL_NAMES],
                           name=name or "phase")


def _as_structure(payload, uploads=None) -> Structure:
    """A :class:`Structure` from ``None``, an inline dict, a typed cell, a CIF
    or an upload.

    Every route into the model passes through here, which is where the species
    check belongs: a structure carrying a scattering species no form-factor table
    knows validates fine and fails at *stage compile*, a long way from the field
    it was typed in.  Refusing at the boundary is a GUI judgement, not a schema
    change — the Python API still accepts it — and the message names the atom.

    The four dict forms are told apart by their keys — see
    :func:`_is_typed_cell`.  ``None`` is the fifth and is decided **first**
    (WP-1207): it means a pattern-only project, and it has to be caught before
    the inline branch, where it used to fall through to
    ``_validate(Structure, None, …)`` and be refused as a malformed model.

    Callers that want ``structure`` to be *required* must check for the key
    themselves — ``project_new`` does — because the absence of a key and a
    ``null`` value are the same thing to ``dict.get`` and only one of them is a
    deliberate answer.
    """
    if payload is None:
        return Structure(phases=[])
    if _is_typed_cell(payload):
        structure = _typed_cell_structure(payload)
    elif isinstance(payload, dict) and ("cif" in payload or "upload" in payload):
        from ..crystallography.cif import structure_from_cif

        staged = None
        if "upload" in payload:
            if uploads is None:  # pragma: no cover - every caller passes one
                raise GuiError("uploads are not available here",
                               where=["structure.upload"])
            try:
                staged = uploads.get(str(payload["upload"]), "cif")
            except UploadRefused as exc:
                raise GuiError(str(exc), code=exc.code, status=exc.status,
                               where=["structure.upload"]) from None
            path = str(staged.path)
        else:
            path = _need(payload, "cif")
        try:
            # aniso is opt-in on purpose: reading a file must not silently change
            # what a plan frees (CLAUDE.md, anisotropic ADPs)
            structure = structure_from_cif(
                path, aniso=bool(payload.get("aniso", False)),
                phase_name=payload.get("phase_name"))
        except (OSError, ValueError, RuntimeError) as exc:
            name = path if staged is None else staged.filename
            message = str(exc) if staged is None else scrub(str(exc), staged)
            raise GuiError(f"could not read structure from {name}: {message}",
                           where=["structure.cif"]) from None
    else:
        structure = _validate(Structure, payload, "structure")
    unknown = unknown_species(structure)
    if unknown:
        named = ", ".join(f"{u['label']} ({u['species']})" for u in unknown)
        raise GuiError(
            f"{len(unknown)} atom(s) carry a scattering species this build has "
            f"no form factor for: {named}. A fit would fail at stage compile "
            "with the same lookup; edit the species (ions fall back to the "
            "neutral atom, so 'O2-' is fine and 'D' is not).",
            code="UNKNOWN_SPECIES",
            where=[f"{u['path']}.species" for u in unknown])
    return structure


def _as_instrument(payload, uploads=None) -> Instrument:
    """An :class:`Instrument` from an inline dict, a preset spec, or an upload.

    The preset form is what the import wizard sends: a geometry and an anode
    name, with the *wavelengths* supplied by the package's table rather than
    typed by a client (WP-0507's scale, kept in one place).
    """
    if payload is None:
        raise GuiError("'instrument' is required: Instrument has no default "
                       "source, and guessing an anode or a geometry would put a "
                       "wavelength nobody chose into every refined cell",
                       where=["instrument"])
    if isinstance(payload, dict) and "upload" in payload:
        from ..io.instrument_profile import load_instrument_profile

        if uploads is None:  # pragma: no cover - every caller passes one
            raise GuiError("uploads are not available here",
                           where=["instrument.upload"])
        try:
            staged = uploads.get(str(payload["upload"]), "instrument")
            return load_instrument_profile(staged.path)
        except UploadRefused as exc:
            raise GuiError(str(exc), code=exc.code, status=exc.status,
                           where=["instrument.upload"]) from None
        except (ValueError, OSError, KeyError) as exc:
            raise GuiError(str(exc), where=["instrument.upload"]) from None
    if isinstance(payload, dict) and "preset" in payload:
        try:
            return instrument_from_preset(payload)
        except UploadRefused as exc:
            raise GuiError(str(exc), code=exc.code, status=exc.status,
                           where=exc.where) from None
    return _validate(Instrument, payload, "instrument")


def _as_plan_argument(plan: Any):
    """A preset name or a plan spec, as something ``resolve_plan`` accepts."""
    if isinstance(plan, str):
        if plan not in PLAN_PRESETS:
            raise GuiError(f"unknown plan preset {plan!r}; "
                           f"available: {sorted(PLAN_PRESETS)}", where=["plan"])
        return plan
    return _validate(PlanSpec, plan, "plan").to_plan()

