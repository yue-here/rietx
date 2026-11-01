"""The project as text — one parser, on this side of the wire (WP-1009).

``.rxt`` is a line-oriented rendering of everything a session can edit: the
settings, the plan, and every parameter row with its vary flag.  It is a *view*,
not a file format anyone has to keep — the project is the ``.rex/`` directory —
and its purpose is the edit that a form cannot express: change forty vary flags
with a rectangular selection, read the whole model in one screen, diff two
protocols by eye.

    rxt 1
    project "nac"
    pattern "11BM_NAC.fxye"          # fxye · sha256 9f3ac2… · 45001 pts · 3–155° · σ from file
    mode rietveld
    limits 3 60
    excluded 7.5 8  24 25.2

    plan mccusker_default
    guard 0.98
    stage scale_bkg   free phases.*.scale, instrument.background.*
    stage cell        free phases.*.cell.*

    phase 0 "NAC"                    # I 21 3 · No. 199 · cubic · Laue m-3
      cell.a        @ 10.251285      min 10.1  max 10.4  esd 3.1e-05
      cell.b          10.251285      = cell.a
      scale         @ 1.234e-06      min 0
      atoms.0.biso  @ 0.52           min 0  max 25            # Na1 Na
    instrument
      zero_shift    @ 0.0021
      background.c0 @ 118.4

**Why a DSL rather than TOML or YAML.**  Both would lose the aligned columns
that a rectangular selection exists to edit, and neither can say ``@`` — the one
mark this document needs most.  Neither speaks dot-paths in its errors either,
and a parse error that does not name a path is a parse error a user cannot act
on.

**The parser lives only here.**  The editor pane (WP-1013) gets a regex
highlighter and no grammar, so there is no second implementation to drift.

Three rules make the round trip safe:

**A delta is computed against the live project, never against the old text.**
``parse`` is pure syntax; ``changes`` compares the parsed document to the
``Refinement``'s own parameter rows and the ``ProjectDoc``'s own settings, and
emits only what differs.  So a document the user never touched produces *no*
verbs — which is the property that makes an editor pane safe to leave open — and
a field nobody can change is an error only when it actually differs.

**Everything is applied through the same public verbs a form uses**
(``set_values``, ``set_vary``, ``Project.set_excluded_regions``, the plan
setting), so a text apply lands in the history as the same nodes and reads in the
console as the same API calls.  All-or-nothing: ``set_values`` validates every
path before writing any, and it runs first, so a refusal leaves nothing applied.
Refusal *messages* are the verbs' own — a tied path is refused in the words
``set_values`` uses and a held row in the words ``ParameterRow.held_because``
uses, because two surfaces disagreeing about why a parameter cannot move is worse
than either one being terse.

**Values render at 12 significant digits, and an unedited line is not a change.**
A refined parameter carries more digits than that, so the document is lossy by
construction; what must not be lossy is *applying* it.  ``changes`` therefore
compares a typed number against the **rendered** current value rather than
against the stored one, so re-applying an untouched document is a no-op and only
digits a human actually typed reach the model.

What deliberately does not survive a re-render: **the user's own comments.**  The
document is regenerated from state on every read, and the only way to keep a
comment would be to store it — a second authority for something nothing else
needs.  Comments parse and are ignored; the annotations after each value are
rendered afresh each time.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any, get_args

from pydantic import BaseModel, ValidationError

from .._about import TEXTDOC_MAGIC
from ..schemas.common import Mode, Parameter, legacy_transform_bounds
from ..schemas.indexing import PeakFlag
from ..schemas.migrate import migrate_document_text
from ..schemas.plan import (
    PlanSpec,
    StageSpec,
    check_closing_window_tol,
    check_phase_support_sigma,
)
from ..schemas.project import ProjectDoc, check_interval
from ..strategy.staged import PLAN_PRESETS

#: The ``<magic> N`` header, where the magic is :data:`.._about.TEXTDOC_MAGIC`
#: — the token is a format contract and lives with the other name-bearing
#: literals, deliberately free of the brand (WP-1062).
#: Any change a consumer could observe bumps the last component by one, and
#: the comment says what changed — no classification, no digest (WP-1117).
#: WP-1017 injects this into the manual as a fenced constant, so a bump that
#: misses the manual fails the docs build.
FORMAT_VERSION = "1"

#: Significant digits every value renders at.  See the module docstring: the
#: document is a lossy view and ``changes`` is what makes that safe.
VALUE_DIGITS = 12

#: A stage line's trailing ``<key> <number>`` pairs: every :class:`StageSpec`
#: field except the two the line already carries positionally
#: (``stage <name>  free <globs>``).  **Derived, not listed** — the previous
#: spelling was this same tuple written out in the renderer and again in the
#: parser, so WP-1074's ``restraint_weight_scale`` would have rendered nowhere,
#: parsed nowhere, and been dropped on every save, which is the loss
#: ``schemas/plan.py``'s docstring describes one rank up.  Declaration order, so
#: a new field appends and existing documents render byte-for-byte as before.
#:
#: An added key is not a :data:`FORMAT_VERSION` bump, for the reason a new field
#: on an event kind is not an ``EVENT_SCHEMA_VERSION`` bump: no line's *meaning*
#: changed, and every document a previous build wrote still parses here.  The
#: same reading covers a new plan-level *line* (WP-1123's ``tolerance``): the
#: asymmetry it leaves — a document written here is refused by an older build,
#: which does not know the keyword — is the one every added key already had,
#: and a bump would instead refuse every document already stored, since the
#: parser compares this constant for equality.
STAGE_KEYS = tuple(k for k in StageSpec.model_fields
                   if k not in ("name", "turn_on"))
#: The subset that must come back as ``int``.
STAGE_INT_KEYS = ("max_iter", "lebail_cycles")

#: Blocks whose *name* is reserved so a later WP can fill them in without a
#: format bump.  Recognised by the parser and refused with the owner, which is
#: the difference between "not yet" and "you typed nonsense".  Empty since
#: WP-1027 filled in ``peaks``; the mechanism stays for the next reservation.
RESERVED_BLOCKS: dict[str, str] = {}

#: The ``peaks`` block (WP-1027): one row per picked peak, and deliberately
#: **no ``@`` markers** — peaks are not refinable parameters, and that absence
#: is the visual distinction from every other block.  Only two columns are
#: editable on apply, ``2theta`` (a ``move_peak``: reseed + refit the group)
#: and ``flags`` (a ``set_peak_flags``); the count, esd, fwhm and intensity are
#: derived and regenerated on the next render, so an edit to them is refused
#: rather than silently dropped.  A row omitted from the document is "no
#: opinion", exactly as an omitted parameter row is — adding and removing peaks
#: are the panel's verbs, not text edits::
#:
#:     peaks 20                          # session.pick_peaks(shoulders=True)
#:       #        2theta        esd     fwhm            I  flags
#:        0     8.471200   0.000900   0.0812        10420
#:        1    10.774300   0.001100   0.0834         3310  excluded
#:
#: ``origin`` is deliberately not rendered: the panel shows it, and a word in
#: the flags column that is not a flag would make the editable column carry two
#: vocabularies.
_PEAK_FLAG_WORDS: tuple[str, ...] = get_args(PeakFlag)

_KEYWORDS = (TEXTDOC_MAGIC, "project", "pattern", "mode", "limits", "excluded", "plan",
             "guard", "tolerance", "passes", "support", "closing", "stage", "phase",
             "instrument",
             "peaks", *RESERVED_BLOCKS)

_FLAG_WORDS = ("locked", "mode-fixed", "held")
_PAIR_WORDS = ("min", "max", "esd")

#: Flag words a document rendered before schema 0.46 carries, when a row's
#: transform was rendered beside its bounds (WP-1938).  Read, never written:
#: each folds into the row's ``min``/``max`` through the schema's one map
#: (:func:`~rietx.schemas.common.legacy_transform_bounds`), so an old document
#: compares equal to the live rows, whose bounds are that box already.
_LEGACY_TRANSFORM_WORDS = ("softplus", "logit")

#: Order the annotations render in.  One tuple, so the renderer and the
#: read-only check below cannot disagree about what an annotation *is*.
#:
#: ``tie`` is **last**, and that is a grammar decision rather than taste: a tie
#: reads ``= 0.1993 + 1·phases.0.atoms.1.dof.0`` — spaces and all — so ``=``
#: has to run to the end of the line to be unambiguous.  Rendering it in the
#: middle produced a document this module's own parser could not read back, which
#: is what the round-trip test exists to catch.
_ANNOTATION_ORDER = ("min", "max", "locked", "mode-fixed", "held", "esd", "tie")


# ----------------------------------------------------------------------
# the parsed document
# ----------------------------------------------------------------------
@dataclass
class TextError:
    """One failure, addressed the way a text editor needs it addressed."""

    line: int          # 1-based, so it matches what the editor's gutter shows
    message: str
    where: str = ""    # a dot-path, or the keyword at fault
    text: str = ""     # the offending line, for a highlight

    def as_dict(self) -> dict:
        return {"line": self.line, "message": self.message, "where": self.where,
                "text": self.text}


@dataclass
class Row:
    """One parameter line, exactly as written."""

    line: int
    path: str                       # fully qualified (prefix applied)
    local: str                      # as written inside its block
    vary: bool
    value: float | None
    annotations: dict[str, Any]
    text: str

    @property
    def is_glob(self) -> bool:
        return any(ch in self.local for ch in "*?")


@dataclass
class PeakRow:
    """One line of the ``peaks`` block, exactly as written."""

    line: int
    index: int
    two_theta: float
    esd: float
    fwhm: float
    intensity: float
    flags: list[str]
    text: str


@dataclass
class ParsedDocument:
    """Syntax only: what the text says, with no opinion about the project."""

    #: keyword → the line it was read from, so a semantic error found later can
    #: still point at the line a human typed
    lines: dict[str, int] = field(default_factory=dict)
    version: str = ""
    project: str | None = None
    pattern: str | None = None
    mode: str | None = None
    limits: tuple[float, float] | None = None
    has_limits: bool = False
    excluded: list[tuple[float, float]] = field(default_factory=list)
    has_excluded: bool = False
    plan_name: str | None = None
    guard: float | None = None
    #: the ``tolerance`` line's value, and whether it appeared at all — the two
    #: cannot be one field, because ``none`` (converge every stage) is itself a
    #: value here rather than the absence of one
    tolerance: float | None = None
    tolerance_set: bool = False
    #: the ``passes`` line (WP-1323), ``None`` when absent: one pass is the default
    passes: int | None = None
    #: the ``support`` line's value (WP-2002, B1), and whether it appeared at
    #: all, for ``tolerance``'s reason: ``none`` (no absent-phase hold) is a
    #: value rather than the absence of one
    support: float | None = None
    support_set: bool = False
    #: the ``closing`` line's value (WP-2002, the sixth round's Q1 and Q2), and
    #: whether it appeared, for the same reason: ``none`` is a value
    closing: float | None = None
    closing_set: bool = False
    stages: list[StageSpec] = field(default_factory=list)
    stage_lines: list[int] = field(default_factory=list)
    phases: dict[int, tuple[int, str | None]] = field(default_factory=dict)
    rows: list[Row] = field(default_factory=list)
    has_peaks: bool = False
    peaks_count: int | None = None
    peak_rows: list[PeakRow] = field(default_factory=list)
    errors: list[TextError] = field(default_factory=list)


@dataclass
class Delta:
    """What would change, in the shape the verbs take."""

    values: dict[str, float] = field(default_factory=dict)
    vary: dict[str, bool] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] | None = None
    #: peak index (as displayed at render time) → the typed 2θ / flag list;
    #: applied through the same editor the panel's drag and chips call
    peak_moves: dict[int, float] = field(default_factory=dict)
    peak_flags: dict[int, list[str]] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (self.values or self.vary or self.settings or self.plan
                    or self.peak_moves or self.peak_flags)

    def as_dict(self) -> dict:
        return {"values": dict(self.values), "vary": dict(self.vary),
                "settings": dict(self.settings), "plan": self.plan,
                "peak_moves": dict(self.peak_moves),
                "peak_flags": {k: list(v) for k, v in self.peak_flags.items()}}


# ----------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------
def _fmt(value: float) -> str:
    """A number at :data:`VALUE_DIGITS`, without a trailing ``.0``."""
    text = f"{float(value):.{VALUE_DIGITS}g}"
    return text


def _fmt_bound(value: float) -> str:
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    return _fmt(value)


def annotations_of(row) -> dict[str, Any]:
    """Every read-only fact a row carries, keyed the way the text spells it.

    The renderer formats this dict and ``_check_annotations`` compares against
    it, so "what an annotation means" is written once.  Numbers are pre-rounded
    to the rendered precision, which is what makes an unedited document compare
    equal.
    """
    out: dict[str, Any] = {}
    if row.tie is not None:
        out["tie"] = row.tie.describe()      # the schema's own words
    if row.lo != float("-inf"):
        out["min"] = float(_fmt(row.lo))
    if row.hi != float("inf"):
        out["max"] = float(_fmt(row.hi))
    if row.locked:
        out["locked"] = True
    if row.mode_fixed:
        out["mode-fixed"] = True
    if row.held:
        out["held"] = True
    if row.esd is not None:
        out["esd"] = float(_fmt(row.esd))
    return out


def _render_annotations(row) -> str:
    parts = []
    for key in _ANNOTATION_ORDER:
        value = annotations_of(row).get(key)
        if value is None:
            continue
        if value is True:
            parts.append(key)
        elif key == "tie":
            parts.append(f"= {value}")
        else:
            parts.append(f"{key} {_fmt_bound(value)}")
    return "  ".join(parts)


def revision(text: str) -> str:
    """A short digest of a rendered document — the CAS token for ``PUT``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def render(project) -> str:
    """The whole project as text (see the module docstring for the grammar)."""
    doc: ProjectDoc = project.doc
    ref = project.refinement
    data_ref = project.data_ref
    lines: list[str] = [f"{TEXTDOC_MAGIC} {FORMAT_VERSION}",
                        f'project "{project.path.stem}"']

    sigma = "σ from file" if data_ref.has_sigma else "σ = √max(y,1) fallback"
    # every recorded reader keyword, not just ``block``: this is inside a ``#``
    # comment, so widening it is not a grammar change and FORMAT_VERSION holds
    extra = "".join(f" · {k} {v}" for k, v in sorted(data_ref.options.items()))
    lo, hi = data_ref.two_theta_range
    lines.append(
        f'pattern "{data_ref.filename}"'.ljust(34)
        + f"# {data_ref.reader} · sha256 {data_ref.sha256[:6]}… · "
          f"{data_ref.n_points} pts · {_fmt(lo)}–{_fmt(hi)}° · {sigma}{extra}")
    lines.append(f"mode {doc.mode}")
    lines.append("limits none" if doc.two_theta_limits is None
                 else f"limits {_fmt(doc.two_theta_limits[0])} "
                      f"{_fmt(doc.two_theta_limits[1])}")
    lines.append("excluded none" if not doc.excluded_regions else "excluded " +
                 "  ".join(f"{_fmt(a)} {_fmt(b)}" for a, b in doc.excluded_regions))

    lines.extend(["", *_render_plan(doc)])
    rows = project.parameters()
    if not ref.structure.phases:
        # Said rather than left blank (WP-1207): a document with no phase block
        # and no line about it reads as one whose phases went missing, and this
        # is a document a person edits by hand.  A comment, so the grammar and
        # FORMAT_VERSION hold and the round trip is unaffected.
        lines.extend(["", "# no phase yet — index the pattern and adopt a cell "
                          "(a fit is refused until then)"])
    for index, phase in enumerate(ref.structure.phases):
        header = f'phase {index} "{phase.name}"'
        note = _phase_comment(phase)
        lines.extend(["", *_render_block(
            header.ljust(34) + f"# {note}" if note else header,
            f"phases.{index}.", rows, phase)])
    lines.extend(["", *_render_block("instrument", "instrument.", rows, None)])
    peaks = _render_peaks(project)
    if peaks:
        lines.extend(["", *peaks])
    return "\n".join(lines) + "\n"


def _render_peaks(project) -> list[str]:
    """The stored peak list as the ``peaks`` block, or nothing.

    Widths are per block, like every other block.  No ``@`` anywhere: peaks are
    not parameters, and that absence is the block's visual signature.  A store
    that belongs to another pattern renders nothing — its refusal has its own
    surface (``GET /api/peaks``), and a text view must not crash the document.
    """
    from . import peaks as store

    try:
        doc = store.load(project)
    except ValueError:
        return []
    if doc is None or not doc.peaks.peaks:
        return []
    rows = [(str(i), f"{p.two_theta:.6f}", f"{p.two_theta_esd:.6f}",
             f"{p.fwhm:.4f}", f"{p.intensity:.6g}", " ".join(p.flags))
            for i, p in enumerate(doc.peaks.peaks)]
    widths = [max(2, *(len(r[0]) for r in rows))] + [
        max(len(name), *(len(r[k]) for r in rows))
        for k, name in ((1, "2theta"), (2, "esd"), (3, "fwhm"), (4, "I"))]
    shoulders = doc.pick_options.get("shoulders", True)
    provenance = ("σ assumed, not measured" if doc.peaks.source == "positions"
                  else f"session.pick_peaks(shoulders={shoulders})")
    names = ("2theta", "esd", "fwhm", "I")
    lines = [
        f"peaks {len(rows)}".ljust(34) + f"# {provenance}",
        "  # " + " " * widths[0] + "  "
        + "  ".join(n.rjust(w) for n, w in zip(names, widths[1:])) + "  flags",
    ]
    for r in rows:
        line = ("    " + r[0].rjust(widths[0]) + "  "
                + "  ".join(v.rjust(w) for v, w in zip(r[1:5], widths[1:])))
        lines.append(f"{line}  {r[5]}" if r[5] else line)
    return lines


def _render_plan(doc: ProjectDoc) -> list[str]:
    spec = doc.plan
    if spec is None:
        return ["plan none".ljust(34)
                + "# nothing selected; a run would use mccusker_default"]
    name = spec.preset_name()
    lines = [f"plan {name or 'custom'}"]
    if spec.correlation_guard != PlanSpec().correlation_guard:
        lines.append(f"guard {_fmt(spec.correlation_guard)}")
    # rendered always, unlike guard, and the only plan-level line that is: this
    # one decides what the run costs and how far its intermediate stages are
    # taken, and a default nobody can see is a default nobody can decline
    tol = "none" if spec.intermediate_ftol is None else _fmt(spec.intermediate_ftol)
    lines.append(f"tolerance {tol}".ljust(34)
                 + "# intermediate_ftol: every declared stage but the last "
                   "('none' = converge them all)")
    # shown only above its default, like ``guard``: a Le Bail job's cap, which
    # an edit through the document would otherwise reset to one pass
    if spec.lebail_passes != PlanSpec().lebail_passes:
        lines.append(f"passes {spec.lebail_passes}".ljust(34)
                     + "# lebail_passes: Le Bail runs this plan up to N times, "
                       "keeping the best")
    # shown only away from its default, like ``guard`` and ``passes``, so every
    # stored document renders byte for byte as before (WP-2002, B1)
    if spec.phase_support_sigma != PlanSpec().phase_support_sigma:
        sigma = ("none" if spec.phase_support_sigma is None
                 else _fmt(spec.phase_support_sigma))
        lines.append(f"support {sigma}".ljust(34)
                     + "# phase_support_sigma: hold a phase under this many "
                       "esds ('none' = never)")
    # rendered always, for ``tolerance``'s reason: it decides what the run
    # costs and how close its answer is to the converged peak tails
    closing = ("none" if spec.closing_window_tol is None
               else _fmt(spec.closing_window_tol))
    lines.append(f"closing {closing}".ljust(34)
                 + "# closing_window_tol: the closing stage's windows "
                   "('none' = no closing stage)")
    width = max((len(s.name) for s in spec.stages), default=4)
    default = StageSpec(name="_")
    for stage in spec.stages:
        parts = [f"stage {stage.name.ljust(width)}  free "
                 + ", ".join(stage.turn_on)]
        for key in STAGE_KEYS:
            value = getattr(stage, key)
            if value != getattr(default, key):
                parts.append(f"{key} {_fmt(value) if isinstance(value, float) else value}")
        lines.append("   ".join(parts))
    return lines


def _render_block(header: str, prefix: str, all_rows, phase) -> list[str]:
    """One block, in columns wide enough for its own widest row.

    Widths are per block rather than a fixed constant because a fixed constant
    is what let ``polarization`` collide with its own ``min`` annotation — the
    renderer emitted ``0.99min 0``, which the parser then refused as an unknown
    annotation.  Columns exist so a rectangular selection can hit one field, so
    they have to be real.
    """
    rows = [row for row in all_rows if row.path.startswith(prefix)]
    locals_ = [row.path[len(prefix):] for row in rows]
    path_width = max((len(name) for name in locals_), default=8)
    value_width = max((len(_fmt(row.value)) for row in rows), default=8)
    lines = [header]
    for row, local in zip(rows, locals_):
        mark = "@" if row.vary else " "
        body = f"  {local.ljust(path_width)} {mark} {_fmt(row.value).rjust(value_width)}"
        annotations = _render_annotations(row)
        line = f"{body}  {annotations}" if annotations else body
        comment = _atom_comment(phase, local)
        return_width = 12 + path_width + value_width + 44
        lines.append(line.rstrip() if not comment
                     else f"{line.ljust(return_width)}# {comment}")
    return lines


def _phase_comment(phase) -> str:
    """``# I a -3 d · cubic · Laue m-3m`` on a phase header (WP-1035).

    The space group is the one fact about a phase that this document could not
    say, and it is **rendered, never editable**: the ``.rxt`` surface is
    parameters and settings, a symbol change is a whole-model edit
    (``POST /api/structure/symmetry``, which gates on a preview), and a second
    authority on a phase's symmetry is what this module's rules forbid.  It goes
    through the same comment mechanism the atom rows use, so no format bump —
    comments parse and are ignored on the way back in.

    The **setting** is quoted, not the crystal system alone: ``R -3 c:H`` and
    ``R -3 c:R`` tie different cell edges (WP-1036), and a line that showed only
    "trigonal" would not say which document the reader is holding.  An
    unresolvable symbol says so rather than rendering nothing — that is exactly
    when a reader needs the line most.

    What it deliberately leaves out is the tie list: the block *below* it already
    carries ``= cell.a`` on every tied edge and ``locked`` on every held angle,
    and repeating them here would put the same fact in two places and take the
    line past the width the rest of the document holds to.
    """
    from .symmetry import phase_facts

    facts = phase_facts(phase, 0)
    if "error" in facts:
        return f"{phase.space_group} · unresolvable symbol"
    if facts["n_operations"] is not None:
        # an operation list has no number of its own: the one quoted is its
        # closest type's, and the line says so rather than naming it
        return (f"{facts['xhm']} · {facts['n_operations']} operations · closest"
                f" type No. {facts['number']} · {facts['crystal_system']}"
                f" · Laue {facts['laue_class']}")
    return (f"{facts['xhm']} · No. {facts['number']} · {facts['crystal_system']}"
            f" · Laue {facts['laue_class']}")


def _atom_comment(phase, local: str) -> str:
    """``# La1 La`` on an atom row — which atom this dot-path belongs to."""
    if phase is None or not local.startswith("atoms."):
        return ""
    try:
        atom = phase.atoms[int(local.split(".")[1])]
    except (IndexError, ValueError):
        return ""
    return f"{atom.label} {atom.species}".strip()


# ----------------------------------------------------------------------
# parsing
# ----------------------------------------------------------------------
def _strip_comment(line: str) -> str:
    """Drop a trailing ``#`` comment, respecting double-quoted strings."""
    out, quoted = [], False
    for char in line:
        if char == '"':
            quoted = not quoted
        if char == "#" and not quoted:
            break
        out.append(char)
    return "".join(out)


def _quoted(text: str) -> str | None:
    text = text.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return None


def _number(token: str) -> float | None:
    try:
        return float(token)
    except ValueError:
        return None


def parse(text: str) -> ParsedDocument:
    """Syntax only.  Errors collect on ``.errors``; nothing is applied."""
    # a document saved by v1.2 spells the component rows the old way; repaired
    # before the line walk so a row's path is the only spelling below
    # (schemas/migrate.py)
    text, _ = migrate_document_text(text)
    doc = ParsedDocument()
    prefix: str | None = None
    phase_index: int | None = None
    in_peaks = False

    def fail(n: int, message: str, raw: str, where: str = "") -> None:
        doc.errors.append(TextError(line=n, message=message, where=where,
                                    text=raw.rstrip()))

    for n, raw in enumerate(text.splitlines(), start=1):
        body = _strip_comment(raw)
        if not body.strip():
            continue
        if body[0].isspace():
            if in_peaks:
                row = _parse_peak_row(n, body, raw, fail)
                if row is not None:
                    doc.peak_rows.append(row)
                continue
            if prefix is None:
                fail(n, "indented parameter line before any 'phase' or "
                        "'instrument' block", raw)
                continue
            row = _parse_row(n, body, prefix, raw, fail)
            if row is not None:
                doc.rows.append(row)
            continue

        tokens = body.split()
        keyword = tokens[0]
        rest = tokens[1:]
        in_peaks = False
        if keyword in RESERVED_BLOCKS:
            fail(n, f"the {keyword!r} block is reserved for "
                    f"{RESERVED_BLOCKS[keyword]}; this build does not read it yet",
                 raw, keyword)
            prefix = None
            continue
        if keyword == "peaks":
            doc.lines.setdefault("peaks", n)
            doc.has_peaks = True
            in_peaks, prefix = True, None
            if rest and _number(rest[0]) is not None:
                doc.peaks_count = int(float(rest[0]))
            elif rest:
                fail(n, "peaks takes its row count (derived; the rows below "
                        "are the content)", raw, "peaks")
            continue
        if keyword not in _KEYWORDS:
            fail(n, f"unknown keyword {keyword!r}; expected one of "
                    f"{', '.join(sorted(_KEYWORDS))}", raw, keyword)
            continue
        doc.lines.setdefault(keyword, n)

        if keyword == TEXTDOC_MAGIC:
            doc.version = rest[0] if rest else ""
            if doc.version != FORMAT_VERSION:
                fail(n, f"this build reads {TEXTDOC_MAGIC} {FORMAT_VERSION}, the "
                        f"document says {doc.version or '(nothing)'!r}", raw,
                     TEXTDOC_MAGIC)
        elif keyword in ("project", "pattern"):
            value = _quoted(body.partition(keyword)[2])
            if value is None:
                fail(n, f"{keyword} takes a double-quoted name", raw, keyword)
            else:
                setattr(doc, keyword, value)
        elif keyword == "mode":
            doc.mode = rest[0] if rest else ""
        elif keyword == "limits":
            doc.has_limits = True
            if rest[:1] == ["none"]:
                doc.limits = None
            elif len(rest) == 2 and None not in (_number(rest[0]), _number(rest[1])):
                # ordering is the document schema's rule, quoted with a line
                # number rather than restated (WP-1033)
                try:
                    check_interval("limits", float(rest[0]), float(rest[1]))
                except ValueError as exc:
                    fail(n, str(exc), raw, "limits")
                else:
                    doc.limits = (float(rest[0]), float(rest[1]))
            else:
                fail(n, "limits takes two numbers or 'none'", raw, "limits")
        elif keyword == "excluded":
            doc.has_excluded = True
            if rest[:1] == ["none"]:
                doc.excluded = []
            elif len(rest) % 2 or any(_number(t) is None for t in rest):
                fail(n, "excluded takes pairs of numbers (lo hi  lo hi …) "
                        "or 'none'", raw, "excluded")
            else:
                pairs = [(float(a), float(b))
                         for a, b in zip(rest[::2], rest[1::2])]
                try:
                    for a, b in pairs:
                        check_interval("an excluded region", a, b)
                except ValueError as exc:
                    fail(n, str(exc), raw, "excluded")
                else:
                    doc.excluded = pairs
        elif keyword == "plan":
            doc.plan_name = rest[0] if rest else ""
        elif keyword == "guard":
            if not rest or _number(rest[0]) is None:
                fail(n, "guard takes one number (the correlation threshold)",
                     raw, "guard")
            else:
                doc.guard = float(rest[0])
        elif keyword == "tolerance":
            value = rest[0] if rest else ""
            if value != "none" and (_number(value) is None or float(value) <= 0.0):
                fail(n, "tolerance takes one positive number — the ftol every "
                        "stage but the last stops at — or 'none' to converge "
                        "every stage to the solver's own default", raw,
                     "tolerance")
            else:
                doc.tolerance = None if value == "none" else float(value)
                doc.tolerance_set = True
        elif keyword == "passes":
            # ascii only: ``"²".isdigit()`` is true and ``int("²")`` raises
            if (len(rest) != 1 or not (rest[0].isascii() and rest[0].isdigit())
                    or int(rest[0]) < 1):
                fail(n, "passes takes one whole number of at least 1 — how "
                        "many times a Le Bail fit runs the plan", raw, "passes")
            else:
                doc.passes = int(rest[0])
        elif keyword == "support":
            value = rest[0] if len(rest) == 1 else ""
            number = _number(value)
            try:
                # the schema's own check, so the line and a JSON plan refuse
                # the same values; a word that is not a number reaches it as
                # text, which it refuses too
                doc.support = (None if value == "none" else
                               check_phase_support_sigma(
                                   value if number is None else number))
            except ValueError:
                fail(n, "support takes one positive number — the esds a "
                        "phase's scale must sit from zero before its structure "
                        "refines — or 'none' to hold no phase", raw, "support")
            else:
                doc.support_set = True
        elif keyword == "closing":
            value = rest[0] if len(rest) == 1 else ""
            number = _number(value)
            try:
                # the schema's own check, the ``support`` line's rule
                doc.closing = (None if value == "none" else
                               check_closing_window_tol(
                                   value if number is None else number))
            except ValueError:
                fail(n, "closing takes one number between 0 and 1 — the "
                        "fraction of each peak's area the closing stage's "
                        "windows may drop — or 'none' for no closing stage",
                     raw, "closing")
            else:
                doc.closing_set = True
        elif keyword == "stage":
            stage = _parse_stage(n, rest, raw, fail)
            if stage is not None:
                doc.stages.append(stage)
                doc.stage_lines.append(n)
        elif keyword == "phase":
            if not rest or _number(rest[0]) is None:
                fail(n, "phase takes an index, then an optional quoted name",
                     raw, "phase")
                prefix = None
                continue
            phase_index = int(float(rest[0]))
            doc.phases[phase_index] = (n, _quoted(body.partition(rest[0])[2]))
            prefix = f"phases.{phase_index}."
        elif keyword == "instrument":
            prefix, phase_index = "instrument.", None
    return doc


def _parse_row(n: int, body: str, prefix: str, raw: str, fail) -> Row | None:
    tokens = body.split()
    local, rest = tokens[0], tokens[1:]
    vary = False
    if rest[:1] == ["@"]:
        vary, rest = True, rest[1:]
    value = None
    if rest and _number(rest[0]) is not None:
        value, rest = float(rest[0]), rest[1:]

    annotations: dict[str, Any] = {}
    legacy: list[str] = []
    while rest:
        word = rest.pop(0)
        if word in _PAIR_WORDS:
            if not rest:
                fail(n, f"{word!r} needs a number after it", raw, local)
                return None
            token = rest.pop(0)
            number = _number(token)
            if number is None:
                fail(n, f"{word} {token!r} is not a number", raw, local)
                return None
            annotations[word] = number
        elif word == "=":
            annotations["tie"] = " ".join(rest)
            rest = []
        elif word in _FLAG_WORDS:
            annotations[word] = True
        elif word in _LEGACY_TRANSFORM_WORDS:
            legacy.append(word)
        else:
            fail(n, f"unknown annotation {word!r} on {local!r}; expected "
                    f"{', '.join((*_PAIR_WORDS, '=', *_FLAG_WORDS))}", raw, local)
            return None
    for word in legacy:
        lo, hi = legacy_transform_bounds(word, annotations.get("min", float("-inf")),
                                         annotations.get("max", float("inf")))
        annotations["min"] = lo
        if hi != float("inf"):
            annotations["max"] = hi
    return Row(line=n, path=prefix + local, local=local, vary=vary, value=value,
               annotations=annotations, text=raw.rstrip())


def _parse_peak_row(n: int, body: str, raw: str, fail) -> PeakRow | None:
    """``index  2theta  esd  fwhm  I  [flags…]`` — five columns, then words."""
    tokens = body.split()
    if len(tokens) < 5:
        fail(n, "a peaks row is 'index  2theta  esd  fwhm  I  [flags…]'", raw,
             "peaks")
        return None
    numbers = [_number(t) for t in tokens[:5]]
    if any(v is None for v in numbers):
        bad = tokens[[i for i, v in enumerate(numbers) if v is None][0]]
        fail(n, f"{bad!r} is not a number in a peaks row", raw, "peaks")
        return None
    index = numbers[0]
    if index != int(index) or index < 0:
        fail(n, f"peak index {tokens[0]!r} must be a non-negative integer",
             raw, "peaks")
        return None
    return PeakRow(line=n, index=int(index), two_theta=numbers[1],
                   esd=numbers[2], fwhm=numbers[3], intensity=numbers[4],
                   flags=tokens[5:], text=raw.rstrip())


def _parse_stage(n: int, rest: list[str], raw: str, fail) -> StageSpec | None:
    if not rest:
        fail(n, "stage takes a name, then 'free <globs>'", raw, "stage")
        return None
    name, rest = rest[0], rest[1:]
    if rest[:1] != ["free"]:
        fail(n, f"stage {name!r} needs 'free <glob>[, <glob>…]'", raw, name)
        return None
    rest = rest[1:]
    keys = STAGE_KEYS
    cut = next((i for i, token in enumerate(rest) if token in keys), len(rest))
    globs = [g for g in " ".join(rest[:cut]).replace(",", " ").split() if g]
    if not globs:
        fail(n, f"stage {name!r} frees nothing", raw, name)
        return None
    fields: dict[str, Any] = {}
    tail = rest[cut:]
    while tail:
        key = tail.pop(0)
        if key not in keys or not tail or _number(tail[0]) is None:
            fail(n, f"stage {name!r}: expected '<{'|'.join(keys)}> <number>' "
                    f"but found {key!r}", raw, name)
            return None
        fields[key] = float(tail.pop(0))
    for key in STAGE_INT_KEYS:
        if key in fields:
            fields[key] = int(fields[key])
    return StageSpec(name=name, turn_on=globs, **fields)


# ----------------------------------------------------------------------
# the delta
# ----------------------------------------------------------------------
def changes(parsed: ParsedDocument, project) -> tuple[Delta, list[TextError]]:
    """What ``parsed`` would change about ``project``, and what it cannot.

    Compared against the live project rather than against the previous text: an
    unedited document produces an empty delta, and a read-only field is an error
    only when it actually differs (which is what lets the renderer show
    everything without inventing a syntax for "look, don't touch").
    """
    delta = Delta()
    errors: list[TextError] = list(parsed.errors)
    doc: ProjectDoc = project.doc
    rows = {row.path: row for row in project.parameters()}

    def fail(line: int, message: str, where: str = "", text: str = "") -> None:
        errors.append(TextError(line=line, message=message, where=where, text=text))

    if parsed.version != FORMAT_VERSION and not any(
            e.where == TEXTDOC_MAGIC for e in errors):
        fail(1, f"the document must start with '{TEXTDOC_MAGIC} {FORMAT_VERSION}'",
             TEXTDOC_MAGIC)

    if parsed.project is not None and parsed.project != project.path.stem:
        fail(_line_of(parsed, "project"),
             f"a project's name is its directory name ({project.path.name!r}); "
             "rename the directory to change it", "project")
    if parsed.pattern is not None and parsed.pattern != project.data_ref.filename:
        fail(_line_of(parsed, "pattern"),
             f"the pattern is bound to this project by digest "
             f"({project.data_ref.filename!r}); a different file is a new "
             "project, not an edit", "pattern")

    if parsed.mode is not None and parsed.mode != doc.mode:
        if parsed.mode not in get_args(Mode):
            fail(_line_of(parsed, "mode"),
                 f"unknown mode {parsed.mode!r}; expected one of "
                 f"{', '.join(get_args(Mode))}", "mode")
        else:
            delta.settings["mode"] = parsed.mode
    if parsed.has_limits and _limits(parsed.limits) != _limits(doc.two_theta_limits):
        delta.settings["two_theta_limits"] = parsed.limits
    if parsed.has_excluded and _regions(parsed.excluded) != _regions(
            doc.excluded_regions):
        delta.settings["excluded_regions"] = [list(r) for r in parsed.excluded]

    _plan_changes(parsed, doc, delta, fail)

    # Blocks before their rows, and a bad block *suppresses* its rows: a
    # mistyped 'phase 7' otherwise reports itself once and then twenty
    # "unknown parameter 'phases.7.…'" lines, burying the one error that has a
    # fix.  One cause, one message.
    orphaned: list[str] = []
    phases = project.refinement.structure.phases
    for index, (line, name) in parsed.phases.items():
        if not 0 <= index < len(phases):
            fail(line, f"there is no phase {index} (the model has "
                       f"{len(phases)}); adding or removing a phase is a model "
                       "edit, not a text edit", f"phases.{index}")
            orphaned.append(f"phases.{index}.")
        elif name is not None and name != phases[index].name:
            fail(line, f"phase {index} is named {phases[index].name!r}; renaming "
                       "a phase is a model edit (PATCH /api/structure)",
                 f"phases.{index}.name")
    models = {"phases": phases, "instrument": project.refinement.instrument}
    _row_changes(parsed, rows, models, delta, fail, orphaned)
    _peak_changes(parsed, project, delta, fail)
    return delta, errors


def _line_of(parsed: ParsedDocument, keyword: str) -> int:
    """The line a keyword was read from, or 1 if it never appeared."""
    return parsed.lines.get(keyword, 1)


def _limits(limits) -> tuple | None:
    """At rendered precision, so an unedited line compares equal."""
    return None if limits is None else tuple(float(_fmt(v)) for v in limits)


def _regions(regions) -> list[tuple[float, float]]:
    return [(float(_fmt(a)), float(_fmt(b))) for a, b in regions]


def _plan_changes(parsed: ParsedDocument, doc: ProjectDoc, delta: Delta,
                  fail) -> None:
    """The ``plan`` line names a preset; the ``stage`` lines are the plan itself.

    Both can be edited, and they can contradict each other, so the rule is
    explicit rather than resolved by precedence: change one or the other.  A
    preset name that changed wins nothing — it is refused, because silently
    discarding the stage lines the user is looking at is the worse failure.
    """
    current = doc.plan
    current_name = None if current is None else current.preset_name()
    named = parsed.plan_name
    name_changed = named is not None and named not in (
        current_name, "custom", "none")
    if named and named not in PLAN_PRESETS and named not in ("custom", "none"):
        fail(_plan_line(parsed), f"unknown plan preset {named!r}; available: "
                                 f"{', '.join(sorted(PLAN_PRESETS))}", "plan")
        return

    spec: PlanSpec | None = None
    if parsed.stages:
        spec = PlanSpec(stages=parsed.stages,
                        correlation_guard=(parsed.guard if parsed.guard is not None
                                           else PlanSpec().correlation_guard),
                        intermediate_ftol=(parsed.tolerance if parsed.tolerance_set
                                           else PlanSpec().intermediate_ftol),
                        lebail_passes=(parsed.passes if parsed.passes is not None
                                       else PlanSpec().lebail_passes),
                        phase_support_sigma=(parsed.support if parsed.support_set
                                             else PlanSpec().phase_support_sigma),
                        closing_window_tol=(parsed.closing if parsed.closing_set
                                            else PlanSpec().closing_window_tol))
    stages_changed = spec is not None and spec != current

    if name_changed and stages_changed:
        fail(_plan_line(parsed),
             f"the plan line says {named!r} but the stage lines below are "
             "edited too; change the preset or the stages, not both (the next "
             "render will rewrite the stages from whichever you keep)", "plan")
        return
    if name_changed:
        delta.plan = {"preset": named}
    elif stages_changed:
        delta.plan = {"plan": spec.model_dump(mode="json")}


def _plan_line(parsed: ParsedDocument) -> int:
    return parsed.stage_lines[0] - 1 if parsed.stage_lines else 1


def _schema_keeps(models: dict, row: Row) -> dict[str, float]:
    """The row's typed value and bounds as the schema stores them today.

    A validator on the model holding a Parameter may raise a stored bound to a
    floor, and the value with it: W to the Γ_G² clamp (``ProfileTCHZ``), March
    r off its pole (``PreferredOrientation``).  A document written before a
    floor carries the old numbers, as an old file does, and a number the schema
    raises to the live one is no edit (WP-1938).  Re-validating the holding
    model with the typed numbers asks those validators, so no floor is
    restated here.  Empty where the path is no model's Parameter field or the
    schema refuses the numbers.
    """
    *walk, name = row.path.split(".")
    holder: Any = models
    for segment in walk:
        if isinstance(holder, dict):
            holder = holder.get(segment)
        elif isinstance(holder, list):
            index = int(segment) if segment.isdigit() else len(holder)
            holder = holder[index] if index < len(holder) else None
        else:
            holder = getattr(holder, segment, None)
        if holder is None:
            return {}
    if not (isinstance(holder, BaseModel)
            and isinstance(getattr(holder, name, None), Parameter)):
        return {}
    data = holder.model_dump()
    if row.value is not None:
        data[name]["value"] = row.value
    for key in ("min", "max"):
        if key in row.annotations:
            data[name][key] = row.annotations[key]
    try:
        kept = getattr(type(holder).model_validate(data), name)
    except ValidationError:
        return {}
    return {"value": kept.value, "min": kept.min, "max": kept.max}


def _row_changes(parsed: ParsedDocument, rows: dict, models: dict, delta: Delta,
                 fail, orphaned: list[str] = ()) -> None:
    for row in parsed.rows:
        if any(row.path.startswith(prefix) for prefix in orphaned):
            continue  # its block already failed; see the note in ``changes``
        if row.is_glob:
            _glob_row(row, rows, delta, fail)
            continue
        live = rows.get(row.path)
        if live is None:
            fail(row.line, f"unknown parameter {row.path!r}", row.path, row.text)
            continue
        memo: list[dict[str, float]] = []

        def kept(row=row, memo=memo) -> dict[str, float]:
            """:func:`_schema_keeps` for this row, asked at most once."""
            if not memo:
                memo.append(_schema_keeps(models, row))
            return memo[0]

        # An edit sets the number the schema stores.  A value it raises to the
        # live one is no edit, and one it raises past the live one sets the
        # raised number, which ``set_values`` then accepts.
        value = row.value
        differs = value is not None and float(_fmt(live.value)) != value
        if differs:
            value = kept().get("value", value)
            differs = (value == row.value
                       or float(_fmt(value)) != float(_fmt(live.value)))
        if differs:
            # A locked or tied row would be refused by ``set_values`` at apply
            # time, and that refusal would arrive with a line number attached —
            # but ``validate_only`` never applies, and an editor that only
            # reports this on apply is an editor that lets a user type into a
            # dead field.  ``held_because`` is the row's own account of why,
            # which is what keeps the two surfaces from wording it differently.
            if live.locked or live.tie is not None:
                sources = "" if live.tie is None else (
                    f"; set {' / '.join(live.tie.sources)} instead")
                fail(row.line, f"{row.path} cannot be set — "
                               f"{live.held_because}{sources}",
                     row.path, row.text)
            else:
                delta.values[row.path] = value
        if row.vary != live.vary:
            if row.vary and not live.refinable:
                fail(row.line, f"{row.path} cannot be freed: {live.held_because}",
                     row.path, row.text)
            else:
                delta.vary[row.path] = row.vary
        _check_annotations(row, live, fail, kept)


def _glob_row(row: Row, rows: dict, delta: Delta, fail) -> None:
    """A glob line is bulk vary-flag sugar, and nothing else.

    Normalised away on the next render — canonical output is one line per
    parameter — so a glob is an input convenience whose effect is visible
    immediately afterwards.
    """
    if row.value is not None:
        fail(row.line, f"{row.local!r} is a glob, so it sets vary flags only; a "
                       "value needs one line per parameter", row.path, row.text)
        return
    matched = [path for path in rows if fnmatch(path, row.path)]
    if not matched:
        fail(row.line, f"no parameter matches {row.path!r}", row.path, row.text)
        return
    eligible = [path for path in matched if rows[path].refinable]
    if row.vary and not eligible:
        reasons = sorted({rows[path].held_because for path in matched})
        fail(row.line, f"{row.path!r} matches {len(matched)} parameter(s), none "
                       f"of which can be freed: {'; '.join(reasons)}",
             row.path, row.text)
        return
    for path in eligible:
        if rows[path].vary != row.vary:
            delta.vary[path] = row.vary


def _peak_changes(parsed: ParsedDocument, project, delta: Delta, fail) -> None:
    """The peaks block against the stored list: two editable columns, no more.

    Same rules as parameter rows.  A typed number is compared against the
    *rendered* value (the same format :func:`_render_peaks` printed), an
    omitted row is no opinion, and an edit to a derived column (the count, esd,
    fwhm, intensity) is refused rather than silently regenerated away — the
    user is looking at a number that will change under them otherwise.
    """
    if not parsed.has_peaks and not parsed.peak_rows:
        return
    from . import peaks as store

    line = _line_of(parsed, "peaks")
    try:
        doc = store.load(project)
    except ValueError as exc:
        fail(line, str(exc), "peaks")
        return
    if doc is None:
        fail(line, "this project has no stored peak list; pick peaks first "
                   "(POST /api/peaks) — the block cannot create one", "peaks")
        return
    peaks = doc.peaks.peaks
    if parsed.peaks_count is not None and parsed.peaks_count != len(peaks):
        fail(line, f"the peaks count is derived ({len(peaks)} stored); adding "
                   "and removing peaks are the panel's verbs, not text edits",
             "peaks")
    seen: set[int] = set()
    for row in parsed.peak_rows:
        if row.index >= len(peaks):
            fail(row.line, f"no peak {row.index} (the list has {len(peaks)}); "
                           "a new line is added in the panel, not typed here",
                 "peaks", row.text)
            continue
        if row.index in seen:
            fail(row.line, f"peak {row.index} appears twice", "peaks", row.text)
            continue
        seen.add(row.index)
        peak = peaks[row.index]
        for name, typed, rendered in (
                ("esd", row.esd, f"{peak.two_theta_esd:.6f}"),
                ("fwhm", row.fwhm, f"{peak.fwhm:.4f}"),
                ("I", row.intensity, f"{peak.intensity:.6g}")):
            if typed != float(rendered):
                fail(row.line, f"{name} on peak {row.index} is derived from "
                               "the group fit and cannot be edited; only "
                               "2theta and flags apply", "peaks", row.text)
        unknown = [f for f in row.flags if f not in _PEAK_FLAG_WORDS]
        if unknown:
            fail(row.line, f"unknown flag(s) {unknown} on peak {row.index}; "
                           f"expected {', '.join(_PEAK_FLAG_WORDS)}",
                 "peaks", row.text)
            continue
        if row.two_theta != float(f"{peak.two_theta:.6f}"):
            delta.peak_moves[row.index] = row.two_theta
        if set(row.flags) != set(peak.flags):
            delta.peak_flags[row.index] = list(dict.fromkeys(row.flags))


#: Why each annotation cannot be edited — the sentence a user needs instead of
#: "read-only", since each one points at a different place to change it.
_ANNOTATION_REASONS = {
    "tie": "a tie comes from the crystal system or the site symmetry; set the "
           "path it follows instead",
    "min": "bounds come from the schema, not from this document",
    "max": "bounds come from the schema, not from this document",
    "locked": "locked is structural (symmetry, or a representation that owns "
              "this channel)",
    "mode-fixed": "mode-fixed follows the intensity mode; change 'mode' instead",
    "held": "held is a declaration you made with ref.hold(); ref.unhold() "
            "takes it back, and until then no plan's glob frees it",
    "esd": "an esd is a result of a fit, not an input to one",
}


def _check_annotations(row: Row, live, fail, kept) -> None:
    """Annotations are read-only, and only a *differing* one is an error.

    Compared against :func:`annotations_of` — the same dict the renderer printed
    — so there is no second opinion about what an annotation says.  A user who
    *deletes* ``min 0`` is not asking for an unbounded parameter (no verb would
    do that), so omission means "no opinion" while a mismatch means "you edited
    something no API call can change".  A bound the schema raises to the live
    one does not differ: ``kept`` returns the row's :func:`_schema_keeps`.
    """
    current = annotations_of(live)
    for key, typed in row.annotations.items():
        if key not in current:
            fail(row.line, f"{row.path} is not {key!r} — "
                           f"{_ANNOTATION_REASONS.get(key, 'this is read-only')}",
                 row.path, row.text)
        elif current[key] != typed and not (
                key in ("min", "max") and key in kept()
                and float(_fmt(kept()[key])) == current[key]):
            shown = current[key] if current[key] is not True else key
            fail(row.line, f"{key} on {row.path} is {shown}, and cannot be "
                           f"edited here: {_ANNOTATION_REASONS[key]}",
                 row.path, row.text)


# ----------------------------------------------------------------------
# applying
# ----------------------------------------------------------------------
def apply(project, delta: Delta, peak_editor=None) -> list[str]:
    """Apply ``delta`` through the public verbs; returns the calls it made.

    ``set_values`` runs first *because* it is the one that can still refuse
    (locked, tied, out of bounds) and it validates everything before writing
    anything — so a refusal here leaves the project untouched, which is what
    "all-or-nothing" has to mean for a caller.  The returned lines are the same
    API echo the console shows for a form edit.

    Peak edits run last and go through the panel's own editor
    (:class:`~rietx.gui.peaks.PeakEditor` — the session passes its cached one
    so the detection is not rebuilt).  They were fully validated by
    :func:`changes` (indices, vocabulary, editable columns), so what remains is
    solving, which flags a failure on the peak rather than raising.
    """
    calls: list[str] = []
    if delta.values:
        project.refinement.set_values(dict(delta.values))
        calls.append(f"ref.set_values({dict(delta.values)!r})")
    for path, flag in delta.vary.items():
        hits = project.refinement.set_vary(path, flag)
        calls.append(f"ref.set_vary({path!r}, {flag!r})  # {len(hits)} path(s)")
    if delta.plan is not None:
        spec = (PlanSpec.from_plan(PLAN_PRESETS[delta.plan["preset"]]())
                if "preset" in delta.plan
                else PlanSpec.model_validate(delta.plan["plan"]))
        project.doc.plan = spec
        calls.append("project.doc.plan = PlanSpec(…"
                     f"{len(spec.stages)} stage(s))")
    settings = delta.settings
    if "mode" in settings:
        project.doc.mode = settings["mode"]
        calls.append(f"project.doc.mode = {settings['mode']!r}")
    if "two_theta_limits" in settings:
        limits = settings["two_theta_limits"]
        project.doc.two_theta_limits = None if limits is None else tuple(limits)
        calls.append(f"project.doc.two_theta_limits = {limits!r}")
    if "excluded_regions" in settings:
        regions = [tuple(r) for r in settings["excluded_regions"]]
        project.set_excluded_regions(regions)
        calls.append(f"project.set_excluded_regions({regions!r})")
    if settings or delta.plan is not None:
        project.save()  # settings persist on the verb, not on a Save button
    calls.extend(_apply_peaks(project, delta, peak_editor))
    return calls


def _apply_peaks(project, delta: Delta, editor) -> list[str]:
    """Peak moves and flag edits through the panel's editor, one at a time.

    A move refits its group and the list re-sorts by 2θ, so the indices the
    document was written against can shift under a batch.  Each edit therefore
    re-locates its peak by position — the typed target for a peak this batch
    already moved — rather than trusting the original index twice.
    """
    if not (delta.peak_moves or delta.peak_flags):
        return []
    from . import peaks as store

    doc = store.load(project)
    if editor is None:
        limits = (tuple(project.doc.two_theta_limits)
                  if project.doc.two_theta_limits else None)
        editor = store.PeakEditor(project.data, project.refinement.instrument,
                                  two_theta_range=limits)
    where = {i: doc.peaks.peaks[i].two_theta
             for i in set(delta.peak_moves) | set(delta.peak_flags)}

    def locate(tt: float) -> int:
        return min(range(len(doc.peaks.peaks)),
                   key=lambda j: abs(doc.peaks.peaks[j].two_theta - tt))

    calls: list[str] = []
    for i, target in sorted(delta.peak_moves.items()):
        j = locate(where[i])
        doc = editor.move(doc, j, target)
        calls.append(f"session.move_peak({j}, {target:g})")
        where[i] = target
    for i, flag_list in sorted(delta.peak_flags.items()):
        j = locate(where[i])
        doc = editor.flag(doc, j, flags=flag_list)
        calls.append(f"session.set_peak_flags({j}, flags={flag_list!r})")
    store.save(project, doc)
    return calls
