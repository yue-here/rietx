"""The package's public call surface, **derived** from the live package (WP-1067).

This is the enumeration the WP-1003 freeze covers, and the denominator the
user manual's coverage partition is asserted against
(`tests/test_manual_api.py`).  It is deliberately not a hand-written list.

**Why derived.** A list nobody regenerates cannot notice a *new* public
method: it never enters the denominator, the coverage partition stays green,
and coverage silently drops.  That is `_SURFACE_FLAGS` one level up —
``features["indexing"]`` was ``False`` for its entire life because a
hand-written name (``index``) and the real export (``index_pattern``) drifted
apart while the meta-test asserted the flag's own expression rather than the
name (WP-1037).  So the names are data read out of the package, and the only
hand-written halves are the exclusions below, each carrying a reason.

**Why not ``rietx.__all__``.** It is the right set of *entry points* and the
wrong denominator for a manual: almost nothing a user calls lives there.
``ref.fit``, ``ref.parameters``, ``result.statistics.rwp``,
``history.branch``/``merge``/``cherry_pick``, ``Project.create``/``open``/
``save`` are members and fields.  A manual naming ``Refinement`` once would
satisfy an ``__all__`` partition and document nothing.

Two derivation rules carry the weight, both measured 2026-08-14:

1. **"Public member" means declared, not inherited.**  34 of the 47 exported
   classes are pydantic models, so a bare ``dir()`` denominator is 1099 names,
   most of them ``model_dump``-class ``BaseModel`` machinery.  A member counts
   iff it is one of the model's own fields, or the class that *defines* it
   lives in a ``rietx`` module.  A member is attributed to its **defining**
   class, so a method a subclass inherits from a rietx base is one entry, not
   two.
2. **The surface closes over reachable unexported types.**  ``Statistics`` is
   not exported, so one level of attributes never reaches
   ``result.statistics.rwp`` — the manual's own motivating example.  The
   closure follows fields and public-method annotations of types already on
   the surface, and the signatures of exported functions: ``capabilities()``
   returns a ``Capabilities``, which is exported nowhere.  Exporting those
   types instead would be new public API, which WP-1067 forbids itself.
3. **A plain class's members are assigned, not declared.**  ``dir()`` on the
   *class* cannot see ``self.history = …`` in ``__init__``, so
   ``Refinement.history``, ``Project.doc`` and 25 others were missing until
   the manual's own guard rejected the first of them as a name that does not
   resolve.  Instance attributes are read off the class's source with ``ast``.

**What the partition does not reach: a keyword.**  The denominator is names —
methods, fields, and the types they close over — so a new *keyword argument* on
an already-documented method adds nothing to it and nothing goes red.  Measured
WP-1431: `label=` landed on `Refinement.fit`, `Refinement.run_stage` and
`refine`, and removing the manual section that documents it left
`test_manual_api.py` at 17 passed, unchanged.  Document a new keyword because an
unannounced knob is WP-1322 again, never because a gate asked.  Closing this
would mean partitioning signatures rather than names, which is a bigger
denominator than the manual's coverage question needs.

**The tier a name is on is data too** (WP-1078).  A documented name is frozen
from the release that documents it, which is the wrong promise for a subsystem
still under development, so ``PROVISIONAL_MODULES`` declares one by **module
prefix** and ``provisional_names()`` resolves it against each name's *defining*
module.  Declared, derived and one edit wide: a new type in a declared module
is provisional the moment it is written, and a rename that empties a
declaration fails rather than leaving a dead promise behind.

Run ``python -m tests.api_surface`` for a summary of the surface, or
``python -m tests.api_surface --write-deferred`` to regenerate
``api_surface_deferred.txt`` (see `tests/test_manual_api.py` for what that
file is and why it is generated rather than typed).
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import textwrap
import types
import typing
from dataclasses import dataclass
from pathlib import Path

import rietx

TESTS_DIR = Path(__file__).resolve().parent
DEFERRED_PATH = TESTS_DIR / "api_surface_deferred.txt"

#: The most names the deferred bucket may hold.  Regenerating the bucket is one
#: command, so without a ceiling a new public name could be deferred as easily
#: as documented and the bucket would only grow.  The test fails on growth
#: alone, so concurrent pull requests that each document a name do not collide
#: on this line.  Each release cut lowers it to the bucket's size then
#: (docs/RELEASING.md step 2), which is where the list is read.  Raising it is
#: a reviewed edit with a reason in its commit (WP-1981, 2026-10-16).
#: 37 on 2026-10-24: `Phase.parent_cell` (WP-1419, #1108) is a technique field kept out
#: of `api.md` and deferred like `Phase.rigid_bodies`, until the technique index lands.
DEFERRED_CEILING = 37


# --- what is off the surface, and why -------------------------------------
#
# Each entry is a *reason*, not a shrug.  A type listed here is removed from
# the surface and is not expanded, so the types reachable only through it drop
# out with it; that is the point of excluding a whole type rather than its
# members one at a time.  `test_manual_api.py` fails on an entry here that
# matches nothing, so a rename cannot leave a dead exclusion behind.

EXCLUDED_TYPES: dict[str, str] = {
    "CompiledModel": (
        "compile-stage internal: the frozen-per-stage state (hkl list, symmetry-op "
        "subsets, quadrature node counts, window ranges) that the invariant in "
        "CLAUDE.md forbids touching during a run. Reachable only as the type of "
        "Refinement.snapshot's model argument; a caller passes one along, never "
        "builds or reads one."
    ),
    "CancelToken": (
        "documented as the cancel= protocol rather than as a type: a caller "
        "constructs one and calls .cancel() from another thread, and the "
        "cooperative-cancellation semantics are the documentable part."
    ),
    "Base": (
        "the pydantic base every rietx schema shares (WP-1302's __getattr__ "
        "hint, extra='forbid'); documented as that shared behaviour in "
        "CLAUDE.md, not as a type a caller constructs or names."
    ),
}

# Individual names, where the *type* is on the surface but one member is not.
EXCLUSIONS: dict[str, str] = {
    "GuardFinding.detail": (
        "a rendering fragment, not a fact about the fit (WP-1434): the "
        "already-formatted clause the BOUND_HIT or FLOOR_HIT diagnostic "
        "appends to its own sentence, written by GuardFinding.at_bound and "
        "read at that one place. The evidence a caller reads programmatically is "
        "Diagnostic.value, which carries the same number, and the sentence a "
        "person reads is Diagnostic.message. Deliberately outside __str__, "
        "which is the pre-v1.0 text byte for byte."
    ),
}


# --- what is documented but not frozen, and why ---------------------------
#
# The third tier (WP-1078).  A name the manual documents is frozen from the
# release that documents it, and for a subsystem still under active
# development that is the wrong promise: `using/indexing.md` froze the whole
# indexing surface the day it landed, and WP-1077 then had to change what one
# of those names *answers* in a patch release.  So a subsystem can be declared
# provisional, which overrides the documented tier for its names and nothing
# else.
#
# Keyed by **module prefix**, and resolved against each name's *defining*
# module, for the reason `_SURFACE_FLAGS` exists (WP-1037): a hand-written
# list of names and the real exports drift apart while the test asserts the
# list.  Defining rather than exporting is what reaches
# `determine_extinction_symbol`, which is re-exported at top level and
# documented under that name.  A new type in one of these modules is
# provisional the moment it is written.
#
# `test_manual_api.py` fails on an entry here that matches nothing, so a
# module rename cannot leave a dead declaration behind, and on a provisional
# name that no chapter documents: provisional is a weaker *promise*, never
# thinner coverage.
#
# What is deliberately NOT here: `rietx.capabilities`.
# `Capabilities.indexing_thresholds_version` and the engine and preset
# capability types are data contracts with their own version strings, and a
# consumer that parses an answer keeps its hard freeze.  The risk is the
# caller's who imports a type, not the reader's of a response.
# (WP-1303: the JSON envelope's module was the second name on that line.)

PROVISIONAL_MODULES: dict[str, str] = {
    "rietx.indexing": (
        "the indexing algorithms and the calls over them (pick_peaks, "
        "index_pattern, determine_extinction_symbol) are under active "
        "development: engines, gates and figures of merit are still being "
        "measured against real data, and WP-1077 had to change what the "
        "extinction screen answers in a patch release."
    ),
    "rietx.schemas.indexing": (
        "the answer types those calls return, which move with them: a "
        "candidate, its figures of merit, the caveats and the evidence "
        "projection are the shape of a search that is still changing."
    ),
    "rietx.strategy.magnetic": (
        "magnetic structure determination (solve_magnetic and the "
        "MagneticSolution it returns): the chain is settled and the ranking "
        "criterion is not, and the rungs still to come change what a trial "
        "refines and add a branch this release abstains on."
    ),
    "rietx.io.projects": (
        "the foreign-refinement readers and the registry over them "
        "(read_project_model, read_topas_inp, read_fullprof_pcr, and the "
        "per-format models they answer with) are under active development: "
        "WP-1118 landed the registry on 2026-09-13 with two formats and three "
        "more queued, each of which is evidence about the shape, and the "
        "write direction landed for all four of them in the three days after "
        "(2026-09-16).  A format's own model mirrors "
        "that format, so its fields move when the reader's coverage does."
    ),
}

# --- the internal sentence, and what WP-1003 filed under it ---------------
#
# **Anything importable outside the derived surface is internal and may
# change without notice.**  That sentence is normative (the compatibility
# page states it to users); this note records the families ruled internal at
# the freeze so a later session exporting one of them knows it is reopening
# a decision, not filling a gap:
#
# - `rietx.backend` (WP-0401): `Backend`, `get_backend`, `set_backend`,
#   `resolve_backend`, `MixedPrecisionPolicy`, the traced twin.  The public
#   route is `fit(backend=...)`; `set_backend` is process-wide mutable state
#   and says so in its docstring.
# - `rietx.model` helpers (1071, 1072): the compiled model's members are
#   dropped with the `CompiledModel` exclusion above; `model.geometry`'s
#   computation (neighbour search, covariance propagation) is internal and
#   its *output* is the surface (`GeometryTable`, reached from the result).
# - `rietx.crystallography` (1018 and before): symmetry/wyckoff/stephens
#   machinery.  Consumed through `ParameterTable` and the schemas; the
#   authorities named in CLAUDE.md (`cell_constraints`, `adp_basis`, …) are
#   authorities over *this package's* behaviour, not exports.
#
# These names are not entries in the tables above because an exclusion must
# be live on the unfiltered surface (`test_exclusions_are_live_and_reasoned`)
# and none of them reaches it — they are internal by the sentence alone.


# --- derivation ------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """One name on the public call surface.

    `module` is the rietx module that **defines** the name — the class's own
    module for a class and for its fields, the defining class's module for an
    inherited member, the function's `__module__` for a function.  It is what
    `PROVISIONAL_MODULES` is resolved against, so a name re-exported at top
    level is attributed where it was written rather than where it is reachable.

    It is `None` for a **constant**, which carries no `__module__` at all: a
    dict is bound in one module and imported into three, and identity says
    nothing about which wrote it.  There are two on the surface today and
    neither is indexing, so the hole is declared rather than guessed at —
    `test_manual_api.py` asserts that constants are the *only* unattributed
    kind, which is what would notice a new kind losing its module quietly.
    """

    name: str  # "refine", "RefinementResult.statistics", "Refinement.fit"
    kind: str  # "function" | "class" | "constant" | "field" | "member" | "module"
    owner: str | None = None  # the type or module the member is declared on
    module: str | None = None  # the rietx module that defines it


def is_rietx(obj: object) -> bool:
    """True for a class or function defined inside the `rietx` package."""
    module = getattr(obj, "__module__", None)
    if not isinstance(module, str):
        return False
    return module == "rietx" or module.startswith("rietx.")


def _public(name: str) -> bool:
    return not name.startswith("_")


def _module_of(obj: object) -> str | None:
    """The rietx module an object was defined in, or None if it carries none."""
    module = getattr(obj, "__module__", None)
    if isinstance(module, str) and (module == "rietx" or module.startswith("rietx.")):
        return module
    return None


def _defining_class(cls: type, name: str) -> type | None:
    for base in cls.__mro__:
        if name in vars(base):
            return base
    return None


# pydantic writes these into the class body of every model, so they are
# "declared in a rietx module" by the letter of rule 1 and machinery by its
# intent.  Filtered structurally rather than listed as exclusions: they are
# not this package's surface at all.
_PYDANTIC_CLASS_ATTRS = frozenset({"model_config", "model_fields", "model_computed_fields"})


def _instance_attributes(cls: type) -> set[str]:
    """Public ``self.x = ...`` attributes assigned in the class's own body.

    `Refinement.history` is one of these: a plain class assigns its attributes
    in `__init__`, so `dir()` on the *class* cannot see them and a surface
    derived from `dir()` alone silently omits a member the manual documents by
    name.  Found by the manual's own guard rejecting `Refinement.history`.
    """
    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError):
        return set()
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:  # pragma: no cover - a class body that parses nowhere else either
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and _public(target.attr)
            ):
                found.add(target.attr)
    return found


def declared_members(cls: type) -> dict[str, Entry]:
    """The class's own public members, keyed by qualified name.

    Rule 1: a member counts iff it is one of the model's fields, or the class
    that defines it lives in a rietx module.  Attribution is to the defining
    class, so an inherited method is one entry.

    Rule 4 (WP-1067, 2026-08-17) is the plain-dataclass half of rule 1, and it
    is rule 3's failure one container over: **a dataclass field without a
    default is not a class attribute at all**, so ``dir()`` cannot see it and
    ``getattr`` returns nothing.  Only the *defaulted* fields were counted,
    which is why ``Stage.max_iter`` was on the surface and ``Stage.name`` and
    ``Stage.turn_on`` — the two a caller actually writes — were not, along with
    every field of ``GuardFinding`` and ``PlanInfo`` and eleven of
    ``ReflectionRow``.  34 names, absent from the denominator with the
    partition green, which is the exact shape of the ``_SURFACE_FLAGS`` bug
    this module exists to prevent.  Found by ``using/refining.md`` naming
    ``PlanInfo.modes`` and the resolver refusing it.
    """
    out: dict[str, Entry] = {}
    fields = set(getattr(cls, "model_fields", None) or {})
    if dataclasses.is_dataclass(cls):
        fields |= {f.name for f in dataclasses.fields(cls)}
    for name in sorted(fields):
        if _public(name):
            qualified = f"{cls.__name__}.{name}"
            out[qualified] = Entry(qualified, "field", cls.__name__, _module_of(cls))
    for name in sorted(dir(cls)):
        if not _public(name) or name in fields or name in _PYDANTIC_CLASS_ATTRS:
            continue
        owner = _defining_class(cls, name)
        if owner is None or not is_rietx(owner):
            continue
        qualified = f"{owner.__name__}.{name}"
        out.setdefault(qualified, Entry(qualified, "member", owner.__name__, _module_of(owner)))
    for name in sorted(_instance_attributes(cls)):
        qualified = f"{cls.__name__}.{name}"
        out.setdefault(qualified, Entry(qualified, "attribute", cls.__name__, _module_of(cls)))
    return out


def _annotated_types(cls: type) -> set[type]:
    """rietx-defined classes reachable from a class's fields and public methods."""
    annotations: list[object] = []
    try:
        annotations.extend(typing.get_type_hints(cls).values())
    except Exception:  # a forward reference that only resolves at runtime
        for field in (getattr(cls, "model_fields", None) or {}).values():
            annotations.append(field.annotation)
    for name in dir(cls):
        if not _public(name):
            continue
        member = inspect.getattr_static(cls, name, None)
        member = member.__func__ if isinstance(member, (classmethod, staticmethod)) else member
        if not inspect.isfunction(member):
            continue
        try:
            annotations.extend(typing.get_type_hints(member).values())
        except Exception:
            continue
    found: set[type] = set()
    stack = list(annotations)
    while stack:
        node = stack.pop()
        if inspect.isclass(node) and is_rietx(node):
            found.add(node)
        stack.extend(arg for arg in typing.get_args(node) if arg is not None)
    return found


def _module_members(module: types.ModuleType) -> list[tuple[str, object]]:
    """A module's own public names — defined there, not imported into it.

    A module that declares no `__all__` has a `dir()` that is mostly the types
    it imported (`rietx.agent`, deleted in WP-1303, was the standing example:
    its request union pulled in half the schemas); `__module__` is what
    separates a module's own surface from its imports.
    """
    return [
        (name, value)
        for name in sorted(dir(module))
        if _public(name)
        and getattr(value := getattr(module, name), "__module__", None) == module.__name__
    ]


def _annotated_types_of(func: object) -> set[type]:
    """rietx classes named in a function's signature — its return type above
    all.  `capabilities()` returns a `Capabilities`, which is exported
    nowhere: seeding only from exported *classes* left a documented type off
    the surface entirely.
    """
    try:
        annotations = list(typing.get_type_hints(func).values())
    except Exception:
        return set()
    found: set[type] = set()
    while annotations:
        node = annotations.pop()
        if inspect.isclass(node) and is_rietx(node):
            found.add(node)
        annotations.extend(arg for arg in typing.get_args(node) if arg is not None)
    return found


def _seed_types() -> list[type]:
    """Exported classes, the types exported functions name in their
    signatures, and the classes an exported module defines itself."""
    seeds: list[type] = []
    for name in rietx.__all__:
        obj = getattr(rietx, name)
        if inspect.isclass(obj):
            seeds.append(obj)
        elif isinstance(obj, types.ModuleType):
            for _, value in _module_members(obj):
                seeds.extend([value] if inspect.isclass(value) else _annotated_types_of(value))
        elif callable(obj):
            seeds.extend(_annotated_types_of(obj))
    return seeds


def reachable_types(*, apply_exclusions: bool = True) -> dict[str, type]:
    """The exported classes plus rietx types reachable through them (rule 2)."""
    blocked = set(EXCLUDED_TYPES) if apply_exclusions else set()
    found: dict[str, type] = {}
    frontier: list[type] = []
    for cls in _seed_types():
        if cls.__name__ not in blocked:
            found[cls.__name__] = cls
            frontier.append(cls)
    while frontier:
        for candidate in _annotated_types(frontier.pop()):
            name = candidate.__name__
            if name in found or name in blocked:
                continue
            found[name] = candidate
            frontier.append(candidate)
    return found


def derive_surface(*, apply_exclusions: bool = True) -> dict[str, Entry]:
    """Every public name a caller of this package can reach, keyed by name.

    `apply_exclusions=False` derives the same surface with the exclusions
    below switched off — the only view in which an excluded name is still
    visible, which is how `test_manual_api.py` checks that an exclusion still
    matches something live rather than a name that was renamed away.
    """
    surface: dict[str, Entry] = {}

    for name in rietx.__all__:
        obj = getattr(rietx, name)
        if inspect.isclass(obj) or isinstance(obj, types.ModuleType):
            continue
        kind = "function" if callable(obj) else "constant"
        surface[name] = Entry(name, kind, "rietx", _module_of(obj))

    for name in rietx.__all__:
        obj = getattr(rietx, name)
        if not isinstance(obj, types.ModuleType):
            continue
        surface[name] = Entry(name, "module", "rietx", obj.__name__)
        for member, value in _module_members(obj):
            if inspect.isclass(value):
                continue  # a seed type; it enters the surface under its own name
            if not callable(value):
                continue
            qualified = f"{name}.{member}"
            surface[qualified] = Entry(qualified, "function", name, _module_of(value))

    for name, cls in sorted(reachable_types(apply_exclusions=apply_exclusions).items()):
        surface[name] = Entry(name, "class", None, _module_of(cls))
        surface.update(declared_members(cls))

    if apply_exclusions:
        for name in EXCLUSIONS:
            surface.pop(name, None)
    return surface


def rietx_class_in(annotation: object) -> type | None:
    """The rietx class inside an annotation, past any Optional/list/dict."""
    stack = [annotation]
    while stack:
        node = stack.pop()
        if isinstance(node, type) and (getattr(node, "__module__", "") or "").startswith("rietx"):
            return node
        stack.extend(arg for arg in typing.get_args(node) if arg is not None)
    return None


def attr_step(obj: object, attr: str) -> tuple[bool, object]:
    """One attribute hop, over classes and pydantic fields alike.

    A pydantic v2 model does not carry its fields as class attributes, so
    ``getattr(Capabilities, "backends")`` raises: a field hop reads
    ``model_fields`` and continues from the annotated type.

    A plain dataclass has the same shape for a different reason: a field with
    no default is never assigned on the class, so ``getattr(PlanInfo, "modes")``
    is ``None`` and ``Stage.name`` and ``GuardFinding.code`` do not resolve
    either.  Read those from ``dataclasses.fields`` and continue from the
    annotation, the same way (WP-1067; :func:`declared_members` rule 4 is the
    half of this that fixes the *denominator*).

    Shared by the manual's name partition and the skill's API index (WP-1304),
    which ask the same question of two documents.
    """
    if isinstance(obj, type):
        fields = getattr(obj, "model_fields", None) or {}
        if attr in fields:
            return True, rietx_class_in(fields[attr].annotation)
        if dataclasses.is_dataclass(obj) and any(
            f.name == attr for f in dataclasses.fields(obj)
        ):
            try:
                hint = typing.get_type_hints(obj).get(attr)
            except Exception:  # a forward reference that only resolves later
                hint = None
            return True, rietx_class_in(hint)
    value = getattr(obj, attr, None)
    return value is not None, value


def resolve_dotted(dotted: str, where: str) -> None:
    """Resolve a fully-spelled ``rietx.…`` name, module path included.

    Walks the longest importable prefix first, because ``rietx.viz`` is not an
    attribute of ``rietx`` until something imports it.
    """
    import importlib

    parts = dotted.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            obj: object = importlib.import_module(".".join(parts[:cut]))
        except ImportError:
            continue
        for attr in parts[cut:]:
            ok, obj = attr_step(obj, attr)
            assert ok, f"{where}: `{dotted}` — no {attr!r}"
            if obj is None:
                return
        return
    raise AssertionError(f"{where}: `{dotted}` — nothing importable in it")


def declares(module: str | None, prefix: str) -> bool:
    """True if `module` is `prefix` or a submodule of it.

    A prefix match on the raw string would make `rietx.indexing` claim a future
    `rietx.indexing_legacy`, which is the sort of thing that goes unnoticed
    because it only ever over-matches.
    """
    return module is not None and (module == prefix or module.startswith(f"{prefix}."))


def provisional_names(*, apply_exclusions: bool = True) -> set[str]:
    """Surface names a `PROVISIONAL_MODULES` declaration covers (WP-1078).

    Documented *and* provisional: these names are in the manual, and the manual
    says they may change in a 1.x release.  That is a third state on top of the
    partition rather than a fourth bucket in it.
    """
    surface = derive_surface(apply_exclusions=apply_exclusions)
    return {
        name
        for name, entry in surface.items()
        if any(declares(entry.module, prefix) for prefix in PROVISIONAL_MODULES)
    }


def load_deferred() -> list[str]:
    """The generated `deferred-1.0.x` bucket; empty file once WP-1067 closes."""
    if not DEFERRED_PATH.exists():
        return []
    return [
        line.strip()
        for line in DEFERRED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


_DEFERRED_HEADER = """\
# Generated — do not hand-edit.  `python -m tests.api_surface --write-deferred`
#
# The `deferred-1.0.x` bucket of the manual's coverage partition (WP-1067):
# public names the floor chapters do not document, which the post-release
# chapters will.  Under the WP-1003 freeze this bucket is the **provisional**
# tier: a name here works as it stands but may change in a 1.0.x release, and
# it leaves this file — frozen — when a chapter documents it
# (docs/docs/reference/compatibility.md).  Generated rather than typed so that a
# NEW public name is not in it, fails the partition, and has to be documented,
# excluded with a reason, or deliberately deferred by regenerating this file —
# which shows up as a diff in review.  WP-1067 closes when this file has no
# names left.
"""


def write_deferred(documented: set[str]) -> int:
    names = sorted(set(derive_surface()) - documented)
    DEFERRED_PATH.write_text(_DEFERRED_HEADER + "\n".join(names) + "\n", encoding="utf-8")
    return len(names)


def _main() -> None:
    import sys

    surface = derive_surface()
    if "--write-deferred" in sys.argv:
        from tests.test_manual_api import documented_names  # noqa: PLC0415 — CLI only

        print(f"{write_deferred(documented_names())} names deferred -> {DEFERRED_PATH}")
        return
    kinds: dict[str, int] = {}
    for entry in surface.values():
        kinds[entry.kind] = kinds.get(entry.kind, 0) + 1
    print(f"{len(surface)} names on the derived public surface")
    for kind, count in sorted(kinds.items()):
        print(f"  {kind:>9}: {count}")
    print(f"  deferred: {len(load_deferred())} (ceiling {DEFERRED_CEILING})")
    provisional = provisional_names()
    print(f"  provisional by declaration: {len(provisional)}")
    for prefix in sorted(PROVISIONAL_MODULES):
        covered = sum(1 for name in provisional if declares(surface[name].module, prefix))
        print(f"    {prefix}: {covered}")


if __name__ == "__main__":
    _main()
