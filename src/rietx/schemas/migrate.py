"""Read-side repairs for documents written by an earlier release.

Two repairs, each one authority with its own list of the places it is
applied: a renamed dot-path, repaired on the document *text*
(:func:`migrate_document_text`, :data:`READ_POINTS`), and a declared range a
release dropped from a caller's own ``Parameter``, repaired on the parsed
models (:func:`restore_declared_ranges`, :data:`DECLARED_RANGE_READ_POINTS`).

A vanished *field* is neither: no dot-path names it, so it is folded or
dropped by a ``mode="before"`` validator on the schema that lost it, which
every read point already crosses.  ``Parameter.transform`` (schema 0.46,
``Parameter._fold_transform``) and ``StageResult.floor_unseeded`` are the
current two.

**The rename is textual on purpose.**  A dot-path is not confined to
one schema field: it is a value in a history node's ``free_paths``, a glob in a
saved plan's ``turn_on``, a key in a tie table, a row label in an ``.rxt``.
Enumerating the fields that may hold one is how a migration misses the fifth
place, so the repair is applied to the document *text* at the three points a
stored document is read, and each is named in :data:`READ_POINTS`.

**Why the paths matter more than the field.**  The two halves of the v1.2
``background_peaks`` rename fail differently.  A stored *value* under a name the
schema no longer has fails loudly, under ``extra="forbid"``, naming the field.
A stored *glob* under the old name loads clean and then matches nothing: the
stage runs, frees nothing, and the fit returns a plausible answer with a
declared hump silently unrefined.  This module exists for the second case.
:meth:`rietx.schemas.instrument.Instrument._migrate_v1_2_background_peaks`
handles the first.
"""

from __future__ import annotations

import re

from .common import (
    BARE_PARAMETER_ATTRS,
    Base,
    Diagnostic,
    Parameter,
    _InheritsDeclaredDefaults,
    declared_fills,
)
from .instrument import _LEGACY_COMPONENT_FIELD
from .structure import Atom

#: Where a stored document is read and this repair is applied.  Listed so a
#: fourth read point is an edit here rather than a silent gap; a reader that
#: does not appear in this tuple does not migrate.
#:
#: **Two readers are outside it on purpose**, and both are named here rather
#: than left to be rediscovered:
#:
#: * :func:`rietx.history.events.read_events` — a v1.2 ``live/events.jsonl``
#:   replayed through ``rietx watch`` shows dot-paths in the old spelling.
#:   Nothing raises (an event's ``data`` is an open dict) and the effect is
#:   display-only, on a run that has already finished, so the cost of a
#:   fourth repair point is not paid for.
#: * :class:`rietx.schemas.results.RefinementResult` — its renamed *count*
#:   field is repaired at the schema instead, because ``n_background_peaks``
#:   offers no word boundary before the legacy name for the rule below to
#:   catch, and a result JSON is read by ``rietx html`` rather than by any
#:   reader here.
READ_POINTS: tuple[str, ...] = (
    "rietx.project.Project.open",
    "rietx.history.store.read_records",
    "rietx.gui.textdoc.parse",
)

#: The legacy name as a whole word: not followed by a letter, digit or
#: underscore, so ``background_peaksish`` is left alone while every spelling
#: that actually occurs is caught.
#:
#: **One rule, matching the bare name rather than a prefixed path**, because the
#: name reaches a stored document in four shapes and anchoring on any one of
#: them misses the others:
#:
#: * ``"background_peaks":`` — the JSON key, in a project or a history node;
#: * ``instrument.background_peaks.0.fwhm`` — a dot-path in ``free_paths``;
#: * ``background_peaks.0.fwhm`` — the same row in an ``.rxt``, which renders
#:   each block with its own prefix stripped (``textdoc._render_block``), so the
#:   ``instrument.`` is simply not there;
#: * ``instrument.background_peaks*`` — a glob a caller wrote without the dot,
#:   which fnmatch accepts and a dot-anchored rule would skip.
#:
#: An earlier version of this module anchored on ``instrument.`` and silently
#: missed the third, which is the same class of gap the module exists to close,
#: reintroduced inside it.
#:
#: **What being textual costs, stated rather than discovered.**  The rule cannot
#: see structure, so it also rewrites the legacy word where it is not a path: a
#: ``HumpComponent.label``, a history annotation note, or — the only one with
#: teeth — a ``DataRef`` pointing at a pattern file a user happened to name
#: ``background_peaks.xye``, whose stored path would be rewritten and then not
#: found.  Accepted rather than repaired: making the rule structure-aware means
#: enumerating the fields that may hold a path, which is the failure this module
#: exists to avoid, and the residue **fails loudly** (a missing file, named) in
#: the one case that bites, rather than silently the way a stale glob does.
_LEGACY_NAME = re.compile(rf"\b{_LEGACY_COMPONENT_FIELD}\b")


def migrate_document_text(text: str) -> tuple[str, bool]:
    """Repair a stored document's text; return it with whether anything moved.

    **The one authority.**  There is deliberately no second entry point taking
    already-parsed paths: two functions applying "the same" rules are two
    functions that can disagree, and the disagreement would be silent in
    exactly the way this module was written to prevent.  A caller holding
    parsed paths passes them through this.

    Idempotent, and a no-op on anything written by this release: a document
    holding none of the legacy spellings is returned unchanged and ``False``,
    so a caller can apply it unconditionally on every read without paying for
    it and without a version check that would itself have to be maintained.
    """
    out = _LEGACY_NAME.sub("extra_components", text)
    return out, out != text



# ---------------------------------------------------------------------------
# The declared ranges a release dropped (issue #204, the read half #209)
# ---------------------------------------------------------------------------

#: Where a stored document carrying model ``Parameter`` s is read and
#: :func:`restore_declared_ranges` is applied.  A structural repair, unlike the
#: textual one above, because what it needs is the class a ``Parameter`` sits
#: in and the version its document was written under.  A reader of stored
#: models that does not appear here does not repair.
#:
#: **One reader of stored models is outside it on purpose**:
#: ``RefinementResult``, whose models record a finished fit that nothing
#: refines from, so a range on them bounds nothing.  Its ``parameters`` rows
#: are a copy of the fit's own and read back as they were written.
DECLARED_RANGE_READ_POINTS: tuple[str, ...] = (
    "rietx.history.tree.RefinementTree.load",
    "rietx.io.instrument_profile.load_instrument_profile",
)

#: The version a document that never stamped one is read as: older than every
#: class's ``_declared_since``, which is what such a document is.
UNSTAMPED_SCHEMA = "0.0"


def schema_key(version: str) -> tuple[int, ...]:
    """``"0.9"`` < ``"0.17"``: schema versions compare as integers, never text."""
    return tuple(int(part) for part in version.split("."))


def newest_declared_since() -> tuple[int, ...]:
    """The latest ``_declared_since`` of any class, read off the classes: a
    document written at or after it holds nothing to repair, so it is not
    walked."""
    newest, stack = (0,), list(_InheritsDeclaredDefaults.__subclasses__())
    while stack:
        cls = stack.pop()
        newest = max(newest, schema_key(cls._declared_since))
        stack.extend(cls.__subclasses__())
    return newest


def declared_range_repairs(model: Base, written: str, prefix: str = "") -> list[dict]:
    """What restoring the declared ranges would change in ``model``, read from
    a document written at schema ``written``; ``model`` is not touched.

    **The defect** (issue #204, the read half #209): until a class inherited
    (:class:`~rietx.schemas.common._InheritsDeclaredDefaults`, from its
    ``_declared_since``), a caller's ``Parameter(value=..., vary=...)`` for a
    field that declares a range got ``(-inf, inf)`` and no unit, and
    ``model_dump`` wrote those out explicitly.  So such a document reloads
    with every key present, inherits nothing at construction, and refines
    unbounded again.  Fixed at construction for ``Atom`` by PR #206, for every
    other class by WP-1321; this is what reaches the documents already written.

    **The signature is a bare attribute in a document older than its class's
    inheritance**, per attribute and by :func:`declared_fills` — the same rule
    construction applies, with absence read as "holds the bare value" because
    serialization left no other trace.  Before ``_declared_since`` an explicit
    bare attribute and an omission were the same thing, so reading one as the
    other loses nothing a caller could have meant; from it on, an explicit
    ``min=-inf`` is a choice, and a document written then is left alone.  A
    bound that is merely *wider* than the declared one is never touched:
    WP-1311 made ``max=60`` on a hot specimen's ``biso`` the documented escape.

    **In the reader, with a diagnostic, never in a schema validator** (root
    CLAUDE.md: a silent correction is a reader's to make, because only the read
    path has a channel to say it did).  ``PreferredOrientation``'s silent
    floor repair is not the precedent: its licence is a pole feeding the solver
    NaNs, which a merely loose bound is not.

    One record per parameter the restore would change: its dot-path (under
    ``prefix``), the atom label where there is one, the ``Parameter`` itself,
    the attributes to fill, the stored and the restored attributes, and the
    class's ``_declared_since``.  :func:`restore_declared_ranges` decides which
    to apply.
    """
    written_key = schema_key(written)
    out: list[dict] = []

    def visit(obj: object, at: str, label: str | None) -> None:
        if isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                visit(item, f"{at}{i}.", label)
            return
        if not isinstance(obj, Base) or isinstance(obj, Parameter):
            return
        cls = type(obj)
        if isinstance(obj, Atom):
            label = obj.label  # the name a person knows the site by
        stale = (issubclass(cls, _InheritsDeclaredDefaults)
                 and written_key < schema_key(cls._declared_since))
        for name, info in cls.model_fields.items():
            value = getattr(obj, name)
            if (stale and isinstance(value, Parameter)
                    and info.annotation is Parameter and info.default_factory is not None):
                found = _candidate(value, info.default_factory())
                if found is not None:
                    out.append({"path": f"{at}{name}", "label": label,
                                "since": cls._declared_since, **found})
            else:
                visit(value, f"{at}{name}.", label)

    visit(model, prefix, None)
    return out


def _candidate(param: Parameter, declared: Parameter) -> dict | None:
    present = {attr for attr, bare in BARE_PARAMETER_ATTRS.items()
               if getattr(param, attr) != bare}
    fills = {attr: v for attr, v in declared_fills(declared, present).items()
             if getattr(param, attr) != v}
    # the signature is a bare *range*: a unit rides with a restored range, but
    # alone it is a label a later release declared (extinction's µm², WP-1451)
    # that a document written before it had no way to state
    if not fills.keys() - {"unit"}:
        return None
    before = {attr: getattr(param, attr) for attr in BARE_PARAMETER_ATTRS}
    return {"param": param, "fills": fills, "before": before,
            "after": {**before, **fills}}


def restore_declared_ranges(found: dict[str, list[tuple[str, dict]]],
                            document: str) -> list[Diagnostic]:
    """Apply :func:`declared_range_repairs`' records, per dot-path, and say so.

    ``found`` maps each dot-path to its records, one per place it was stored
    (a history node's id; the one profile), and ``document`` names what was
    read.  **A parameter is restored in every place or in none**: where any
    stored value lies outside the declared range, restoring the others would
    hand a checkout of them a range that value refutes, and restoring that one
    would refuse the record.  The default box is not physics for every
    stored value (a neutron line's Caglioti ``u`` sat outside the X-ray one
    until 2026-10-23), so the parameter is left as stored everywhere and
    reported.
    **No value ever moves.**  One ``DECLARED_RANGE_RESTORED`` or
    ``DECLARED_RANGE_NOT_RESTORED`` per dot-path.
    """
    notes: list[Diagnostic] = []
    for places in found.values():
        ids = [pid for pid, _ in places]
        outside = [(pid, c["param"].value) for pid, c in places
                   if not c["after"]["min"] <= c["param"].value <= c["after"]["max"]]
        first = places[0][1]
        if outside:
            notes.append(_not_restored_note(first, document, ids, outside))
            continue
        for _, c in places:
            # min before max is always legal: the old pair held the value and
            # the new pair does, so [new min, old max] holds it on the way
            for attr in ("min", "max", "unit"):
                if attr in c["fills"]:
                    setattr(c["param"], attr, c["fills"][attr])
        notes.append(_restored_note(first, document, ids))
    return notes


def _describe(attrs: dict) -> str:
    text = f"[{attrs['min']}, {attrs['max']}]"
    text += f" {attrs['unit']}" if attrs["unit"] else ", no unit"
    return text


def _in(document: str, ids: list[str]) -> str:
    if not ids or ids == [document]:
        return document
    if len(ids) == 1:
        return f"{document} ({ids[0]})"
    if len(ids) <= 3:
        return f"{document} ({len(ids)}: {', '.join(ids)})"
    return f"{document} ({len(ids)}, {ids[0]} to {ids[-1]}, not all between)"


def _where(candidate: dict) -> str:
    label = candidate["label"]
    return candidate["path"] + (f" (atom {label})" if label else "")


def _restored_note(candidate: dict, document: str, ids: list[str]) -> Diagnostic:
    before, after = candidate["before"], candidate["after"]
    bound = any(before[a] != after[a] for a in ("min", "max"))
    return Diagnostic(
        level="warning" if bound else "info",
        code="DECLARED_RANGE_RESTORED",
        message=(
            f"{_where(candidate)} was stored as {_describe(before)} before "
            f"schema {candidate['since']} (issue #204) and was restored to the "
            f"declared {_describe(after)} in {_in(document, ids)}. No value "
            f"moved."),
        where=[candidate["path"]],
        suggestion=(
            "Set a range on the Parameter explicitly to keep a different one "
            "(for example max=60 for a hot specimen's biso)."))


def _not_restored_note(candidate: dict, document: str, ids: list[str],
                       outside: list) -> Diagnostic:
    place, value = outside[0]
    more = f" and {len(outside) - 1} more" if len(outside) > 1 else ""
    return Diagnostic(
        level="warning",
        code="DECLARED_RANGE_NOT_RESTORED",
        message=(
            f"{_where(candidate)} was stored as {_describe(candidate['before'])} "
            f"before schema {candidate['since']} (issue #204) and was left so "
            f"in {_in(document, ids)}: {value!r} in {place}{more} lies outside "
            f"the declared {_describe(candidate['after'])}. This parameter "
            "still refines unbounded."),
        where=[candidate["path"]],
        value=float(value),
        suggestion=(
            "If the value is right, give the Parameter a range that holds it "
            "before the next fit."))
