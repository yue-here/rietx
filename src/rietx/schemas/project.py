"""Schemas for the project container — what a saved session *is* on disk.

Two rules shape these models, and both are about avoiding a second authority:

**The model state is not here.**  ``project.json`` carries the data reference
and the settings; the parameter values, the vary flags and the free set live in
``history.jsonl``, whose head is the working state.  Every verb that changes
them (``set_vary``, ``set_values``, ``edit``, a stage) already commits a node, so
a copy in this document could only ever be a second opinion about the same
numbers — and WP-1004 spent its session on what happens when a stage's arguments
exist in three places and one of them silently loses a field.  The consequence
is worth stating plainly: **saving is about settings, not about durability.**  A
refinement is on disk the moment its node is appended, whether or not anyone
called ``Project.save``.

**What is here is what nothing else owns.**  A pattern file does not record the
regions a user excluded, the plan they selected, or their panel layout; a history
node does not record them either (see ``ProjectDoc.excluded_regions``).  Those
are the fields below.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import Field, field_validator

from .common import Base, Mode
from .indexing import IndexingControls
from .plan import PlanSpec

#: Any change a consumer could observe bumps the last component by one, and
#: the comment says what changed — no classification, no digest (WP-1117).
#: ``open`` refuses a newer major than it knows rather than letting pydantic's
#: ``extra="forbid"`` report an unknown field, which is true but unhelpful.
#:
#: ``1.1`` (WP-1047): ``DataRef.options`` gained ``scan``, so the vocabulary a
#: reader call is replayed from grew.  A **minor** bump because nothing already
#: written means anything different — the major gate still opens every 1.x — and
#: an honest one because an older build handed such a project cannot use the key
#: at all.  It would in fact die earlier than the check, on ``read_pattern``'s
#: old signature; that is not fixable retroactively, and recording that the
#: vocabulary grew is the part that is.
#: ``1.2`` (WP-1123): the persisted plan gained ``intermediate_ftol``, so a
#: project written here carries a key an older build's ``extra="forbid"``
#: refuses.  Minor for the same reason 1.1 was: the major gate still opens
#: every 1.x, nothing already written means anything different, and what the
#: bump records is that the vocabulary grew.
#: ``1.3`` (WP-1207): a project may hold **no phase** — ``project.json`` itself
#: is unchanged, and what moved is one rank down, in the ``history.jsonl`` state
#: an older build's ``Structure`` validator refuses to construct.  Minor, and
#: for the same reason 1.1 and 1.2 were: the major gate still opens every 1.x
#: and nothing already written means anything different.  The version is the
#: only field that can say so *before* the log is read, which is the whole
#: reason it moves for a change that added no key here.
#: ``1.4`` (WP-1323): the persisted plan gained ``lebail_passes``, a key an older
#: build's ``extra="forbid"`` refuses.  Minor, as 1.2 was for ``intermediate_ftol``.
#: ``1.5`` (WP-2002, B1): the persisted plan gained ``phase_support_sigma``, the
#: absent-phase hold's threshold.  Minor, as 1.4 was for ``lebail_passes``.
#: Also in 1.5 (WP-2002, the sixth round's Q1 and Q2): ``closing_window_tol``,
#: the closing stage's window area fraction, unreleased beside it.
PROJECT_FORMAT_VERSION = "1.5"


def check_interval(kind: str, lo: float, hi: float) -> None:
    """Refuse an inverted or empty 2θ interval, in one sentence (WP-1033).

    The one place the words exist, because three surfaces refuse with them: the
    GUI's ``POST /api/project``, the ``.rxt`` document's ``limits``/``excluded``
    lines (with a line number attached, never restated), and the field
    validators below — which, because :class:`Base` sets
    ``validate_assignment``, also catch a plain ``doc.two_theta_limits = …`` and
    a hand-edited ``project.json``.

    ``lo == hi`` is refused rather than treated as a point mask: the fit-range
    intersection is inclusive at both ends, so an empty interval and a
    single-channel one are indistinguishable in the arithmetic and a user typing
    one meant neither.
    """
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise ValueError(f"{kind} takes two finite numbers, got ({lo}, {hi})")
    if lo >= hi:
        state = "empty" if lo == hi else "inverted"
        raise ValueError(f"{kind} must run low to high: ({lo}, {hi}) is {state}")


class DataRef(Base):
    """The pattern a project is fitted against, held as a reference you can check.

    The bytes are copied into the project verbatim and *this* is what makes them
    trustworthy again on re-open.  Three quantities, deliberately not one:

    * ``sha256`` — of the file as copied.  Catches an edit in place.
    * ``fingerprint`` — of the parsed float64 2θ/intensity arrays, the same
      digest ``history/store.fingerprint`` computes and ``TreeHeader`` pins.
      Catches a *reader* change: same bytes, different numbers.
    * ``reader`` + ``options`` — which registered format claimed the file
      (``io.readers.PATTERN_FORMATS``) and the keywords it was read with.  A
      pdCIF carrying both a ``_meas`` and a ``_calc`` block is a different
      pattern depending on ``block``, so the reader *call* is part of the
      reference and not just the path.

    The pair (sha256, fingerprint) is more informative than either alone: bytes
    equal with a different fingerprint means this package now parses the file
    differently, which is a thing to be told loudly rather than a corrupted
    project.
    """

    filename: str  # relative to the project directory
    sha256: str
    fingerprint: str
    reader: str
    options: dict[str, str] = Field(default_factory=dict)
    n_points: int
    two_theta_range: tuple[float, float]
    #: whether σ was *measured* — a file esd column, or a σ the reader derived
    #: from the format's own convention (a counting time, an attenuator) —
    #: rather than the Poisson fallback.  σ measured, not σ present in the
    #: file (WP-1003 documents the wider reading): reader-derived σ counts.
    #: Recorded because it is a correctness property of the fit that is
    #: invisible once the data are read (CLAUDE.md, Weights), it is what every
    #: renderer's ``weighted`` flag quotes, and a GUI should be able to say
    #: which it is.
    has_sigma: bool


class ProjectDoc(Base):
    """The settings half of a project, stored as ``project.json`` (see the module docstring)."""

    format_version: str = PROJECT_FORMAT_VERSION
    package_version: str = ""
    created_utc: str = ""
    updated_utc: str = ""

    #: length 1 in v1.0.  The list is the multi-histogram seam (``multi.py``
    #: stacks N patterns into one joint residual); a project holding more than
    #: one pattern is a later milestone's work, and ``Project.open`` refuses it
    #: rather than opening the first and looking like it worked.
    patterns: list[DataRef] = Field(default_factory=list)

    # -- the next run's settings ---------------------------------------
    # These three are what ``fit``/``run_stage`` will be *called* with.  A
    # history node also records mode and limits, and that is not the same fact:
    # the node says what a past run used, this document says what the next one
    # will.  Before any run there is no node to ask, which is why a selected mode
    # has to live somewhere — and why ``Project.run_stage`` passes it explicitly
    # rather than letting the refinement's carried default answer.

    #: the plan currently selected.  Not derivable from the history either: the
    #: tree header records the plan the tree was *created* with.
    plan: PlanSpec | None = None
    mode: Mode = "rietveld"
    two_theta_limits: tuple[float, float] | None = None

    #: 2θ regions masked out of the residual.  These are on ``PatternData``, not
    #: in the pattern file, and — unlike ``two_theta_limits`` — they are *not* in
    #: ``RefinementState`` either, so a history node cannot say what was excluded
    #: when it ran.  Until it can, this document is the only record, which is
    #: why it lives here rather than being recoverable from the head node.
    excluded_regions: list[tuple[float, float]] = Field(default_factory=list)

    #: the next indexing run's controls (WP-1045) — the same
    #: :class:`~rietx.schemas.indexing.SearchSpecSpec` the agent request
    #: carries, plus engines/validation options, so the GUI form and an agent
    #: call are two views of one spec.  A project setting like ``mode``: what
    #: the next ``/api/index`` run will be *called* with, persisted on the
    #: verb.  ``two_theta_limits`` above already governs indexing too, which
    #: is why the controls carry no copy of it.
    indexing: IndexingControls = Field(default_factory=IndexingControls)

    history_file: str = "history.jsonl"

    @field_validator("two_theta_limits")
    @classmethod
    def _check_limits(cls, value):
        if value is not None:
            check_interval("two_theta_limits", *value)
        return value

    @field_validator("excluded_regions")
    @classmethod
    def _check_regions(cls, value):
        for lo, hi in value:
            check_interval("an excluded region", lo, hi)
        return value

    #: Untyped on purpose: the GUI owns these keys (disclosure level, panel
    #: layout, plot ranges) and the container only persists them.  A schema here
    #: would make every frontend change a backend change.
    ui: dict[str, Any] = Field(default_factory=dict)
