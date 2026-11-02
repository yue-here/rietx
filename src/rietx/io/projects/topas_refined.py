"""What a written TOPAS ``.inp`` refines, how its numbers are tied, and its scale.

:func:`~rietx.io.projects.topas.write_topas_inp` writes each ``Parameter``'s own
``vary``, and a plan-driven fit leaves every stored flag ``False`` (a plan
*replaces* the flags per stage; the free set lives in ``Refinement.parameters()``
and ``RefinementResult.parameters``, not on the models). Issue #722. Ties
(``Refinement.tie``/``tie_equal``, the symmetry ties of a special position, the
anti-translation partners of a supercell) have no written form either, so every
copy of a tied value would refine as its own parameter (#721 item 3).

:class:`RefinedSet` is the one place that answers both questions for a writer:

* **what refines** — the free set of the fit, read from what ``free=`` is given;
* **how a written number depends on it** — every written quantity is resolved,
  through the table's affine ties ``value = Σ c·source + k``, to an
  :class:`Affine` in the *free* sources only (a held source is folded into the
  constant), and written as

  - ``! <value>`` when it depends on no free source;
  - ``<name> <value>`` when it *is* one free source, unchanged (TOPAS
    Technical Reference § 2.1: "a parameter is flagged for refinement by giving
    it a name"; a name written in several places is one parameter, § 2.3's
    ``a lp 5.4031 / b lp 5.4031`` form, which is how an equality tie is spelt);
  - ``= <expression>;`` otherwise (§ 2.3: "equations can be a function of
    parameter names; this provides a mechanism for introducing linear …
    constraints"), with a ``prm <name> <value>`` declaration for any source no
    written quantity carries as itself.

  Names are derived from the rietx path (:meth:`RefinedSet.name`), so a reader
  can map them back. A source's finite bounds are written as ``min``/``max``
  on its first statement, because TOPAS's own default windows are not rietx's
  bounds (§ 2.10, Table 2-1).

**The scale.** rietx's scale multiplies M·|F|²·Lp per cell; TOPAS's multiplies
its own ``I_no_scale_pks`` and its ``LP_Factor``. For neutrons TOPAS's |F|² is
in barn, rietx's in fm², so a TOPAS intensity at the same scale is 0.01 × rietx's
(measured against TOPAS 6 output as a black box, no TOPAS code read:
``I_no_scale_pks`` = 0.01 × rietx M·|F|² for fifteen species and isotopes, to
2e-16, and ``tests/data/topas_export_nacl_neutron_ycalc.txt`` holds the constant
in a test). For X-rays ``LP_Factor(c)`` is, **measured** against TOPAS 6's
zero-cycle Y_calc (the Technical Reference, § 12.2.8, p. 157, gives
``LP_Factor``'s signature and no formula), rietx's
Lp = (K + (1 − K) cos² 2θ)/(sin² θ cos θ) divided by K, with cos² c = (1 − K)/K:
``tests/data/topas_export_nacl_xray_ycalc.txt`` holds it at K = 0.5.
So TOPAS's scale is rietx's × 100 for neutrons and × K for X-rays
(:func:`topas_scale_factor`).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

#: TOPAS's scale over rietx's for a constant-wavelength neutron pattern: TOPAS
#: states |F|² in barn (10² fm²) where rietx states it in fm² (module docstring).
NEUTRON_SCALE_FACTOR = 100.0


def topas_scale_factor(instrument) -> float:
    """TOPAS's ``scale`` over rietx's ``Phase.scale`` for ``instrument``'s source.

    Neutron (constant wavelength): 100. X-ray: the polarisation constant K,
    because TOPAS's ``LP_Factor`` is rietx's Lp divided by K (measured at
    K = 0.5 against TOPAS 6's Y_calc,
    ``tests/data/topas_export_nacl_xray_ycalc.txt``). Refused for a
    source this convention has not been measured for (time of flight).
    """
    source = instrument.source
    kind = getattr(source, "kind", None)
    if kind == "neutron_cw":
        return NEUTRON_SCALE_FACTOR
    if kind == "xray_cw":
        return float(source.polarization.value)
    raise ValueError(
        f"no TOPAS scale convention is measured for a {kind!r} source; write "
        f"the scale in rietx's units (scale='rietx') and say so")


@dataclass
class Affine:
    """``Σ terms[path]·path + const``, in rietx's units, over free sources only."""

    terms: dict[str, float] = field(default_factory=dict)
    const: float = 0.0

    def __add__(self, other: "Affine | float") -> "Affine":
        if not isinstance(other, Affine):
            return Affine(dict(self.terms), self.const + float(other))
        terms = dict(self.terms)
        for p, c in other.terms.items():
            terms[p] = terms.get(p, 0.0) + c
        return Affine({p: c for p, c in terms.items() if c != 0.0},
                      self.const + other.const)

    def __mul__(self, k: float) -> "Affine":
        k = float(k)
        return Affine({p: c * k for p, c in self.terms.items() if c * k != 0.0},
                      self.const * k)

    __rmul__ = __mul__

    def value(self, values: dict[str, float]) -> float:
        return self.const + sum(c * values[p] for p, c in self.terms.items())


@dataclass
class _Row:
    value: float
    vary: bool
    tie: tuple[list[tuple[str, float]], float] | None
    lo: float
    hi: float


def _result_rows(parameters: Any, structure) -> dict[str, _Row]:
    """The rows a ``RefinementResult`` states, with the symmetry ties restored.

    A result lists a row iff the fit could move it — it varied, or is tied to a
    row that did (``RefinedParameter``, WP-1999) — and
    carries no equation, so its ``vary=False`` rows are two things: a **user**
    tie's copy (``Refinement.tie``), whose equation the result does not keep and
    which is written as its own refined parameter, and a **symmetry** tie (a
    cubic cell's ``b`` and ``c``, a special position's coordinates through its
    site DOFs), which TOPAS has no business refining as a parameter of its own:
    the structure rederives those from its own space groups, exactly as every
    ``ParameterTable`` build does, and they are written from their sources.
    """
    from ...params.vector import ParameterTable
    from ...schemas.instrument import Instrument

    table = {e.path: e for e in ParameterTable(
        structure, Instrument.constant_wavelength_neutron(1.0)).entries}
    rows: dict[str, _Row] = {}
    for p in parameters:
        entry = table.get(p.path)
        if not p.vary and entry is not None and entry.tie is not None:
            rows[p.path] = _Row(float(p.value), False,
                                ([(s, float(c)) for s, c in entry.tie.terms],
                                 float(entry.tie.const)), -math.inf, math.inf)
        else:
            rows[p.path] = _Row(float(p.value), True, None, -math.inf, math.inf)
    for r in list(rows.values()):
        if r.tie is None:
            continue
        for src, _ in r.tie[0]:
            if src not in rows:     # a held source: its value, nothing to refine
                held = table.get(src)
                rows[src] = _Row(float(held.value) if held is not None else 0.0,
                                 False, None, -math.inf, math.inf)
    return rows


def _rows_from(free: Any, structure=None
               ) -> tuple[dict[str, _Row] | None, set[str] | None, bool]:
    """``(rows, free_paths, has_ties)`` from whatever ``free=`` was given."""
    if free is None:
        return None, None, False
    parameters = getattr(free, "parameters", None)
    if callable(parameters):          # a Refinement: the whole table, ties included
        free = parameters()
    elif parameters is not None:      # a RefinementResult: free set and tied copies
        if structure is None:
            return None, {p.path for p in parameters}, False
        return _result_rows(parameters, structure), None, False
    items = list(free)
    if items and isinstance(items[0], str):
        return None, set(items), False
    rows: dict[str, _Row] = {}
    for r in items:
        tie = None if r.tie is None else ([(p, float(c)) for p, c in r.tie.terms],
                                          float(r.tie.const))
        lo = -math.inf if r.lo is None else float(r.lo)
        hi = math.inf if r.hi is None else float(r.hi)
        rows[r.path] = _Row(float(r.value), bool(r.vary) and tie is None, tie, lo, hi)
    return rows, None, True


def stored_free_paths(structure) -> set[str]:
    """The paths whose own stored ``Parameter.vary`` is set: what the writer
    states when ``free=`` is not given. A moment's modulus (``moment.dof0``) is
    free when any component's flag is; its angles are not."""
    free: set[str] = set()

    def note(path: str, param) -> None:
        if param is not None and param.vary:
            free.add(path)

    for ip, phase in enumerate(structure.phases):
        note(f"phases.{ip}.scale", phase.scale)
        for attr in ("a", "b", "c", "alpha", "beta", "gamma"):
            note(f"phases.{ip}.cell.{attr}", getattr(phase.cell, attr))
        for ia, atom in enumerate(phase.atoms):
            for key in ("x", "y", "z", "occ", "biso"):
                note(f"phases.{ip}.atoms.{ia}.{key}", getattr(atom, key))
            if atom.aniso is not None:
                for key in ("u11", "u22", "u33", "u12", "u13", "u23"):
                    note(f"phases.{ip}.atoms.{ia}.{key}",
                         getattr(atom.aniso, key))
            if atom.moment is not None and any(
                    q.vary for q in (atom.moment.crystalaxis_x,
                                     atom.moment.crystalaxis_y,
                                     atom.moment.crystalaxis_z)):
                free.add(f"phases.{ip}.atoms.{ia}.moment.dof0")
    return free


_NAME_CHARS = re.compile(r"[^A-Za-z0-9_]")
_ATOM_PATH = re.compile(r"^phases\.(\d+)\.atoms\.(\d+)\.(.+)$")
_PHASE_PATH = re.compile(r"^phases\.(\d+)\.(.+)$")


class RefinedSet:
    """The free set and ties a writer states, and the names it states them by.

    ``free`` is a ``Refinement`` (its ``parameters()``: the free set **and** every
    tie), a list of ``ParameterRow`` (the same), a ``RefinementResult`` (the free
    set and the symmetry ties; a user tie's copy is written free) or an iterable
    of paths (the free set only). Without ties each copy of a tied value is
    written as its own parameter, which :attr:`has_ties` lets a caller report.
    """

    def __init__(self, free: Any, structure=None):
        self.rows, self.free_paths, self.has_ties = _rows_from(free, structure)
        #: True when the rows came from a ``RefinementResult`` (symmetry ties
        #: restored, user ties not kept)
        self.from_result = (self.rows is not None and not callable(
            getattr(free, "parameters", None)) and hasattr(free, "parameters"))
        self.structure = structure
        #: True when the free set is the structure's own stored flags (no ``free=``)
        self.from_stored_flags = False
        self._names: dict[str, str] = {}
        self._taken: set[str] = set()
        self._seen: dict[str, float] = {}
        #: paths always written under their name, held (``prm !name``) or free:
        #: the phase terms a reader can find only by name (``topas_ties``)
        self.named: set[str] = set()
        #: TOPAS value / rietx value of each named source, set by :func:`render_slots`
        self.source_factor: dict[str, float] = {}
        #: ``{TOPAS name: (source path, a, b)}``: the named TOPAS value is
        #: ``a·source + b`` (rietx units on the right), set by :func:`render_slots`
        self.carriers: dict[str, tuple[str, float, float]] = {}

    # ------------------------------------------------------------- the table
    def is_free(self, path: str) -> bool:
        if self.rows is not None:
            row = self.rows.get(path)
            return row is not None and row.vary
        return self.free_paths is not None and path in self.free_paths

    def source_value(self, path: str) -> float:
        if path in self._seen:
            return self._seen[path]
        return self.rows[path].value

    def affine(self, path: str, value: float, _depth: int = 0) -> Affine:
        """The written quantity at ``path`` (now ``value``) over the free sources."""
        if path in self.named and not self.is_free(path):
            self._seen[path] = float(value)
            return Affine({path: 1.0}, 0.0)
        if self.rows is None:
            if self.free_paths is not None and path in self.free_paths:
                self._seen[path] = float(value)
                return Affine({path: 1.0}, 0.0)
            return Affine({}, float(value))
        row = self.rows.get(path)
        if row is None:
            return Affine({}, float(value))
        if row.tie is not None:
            if _depth > 8:
                raise ValueError(f"the tie on {path!r} does not resolve: a cycle")
            terms, const = row.tie
            out = Affine({}, const)
            for src, c in terms:
                src_row = self.rows.get(src)
                src_value = src_row.value if src_row is not None else 0.0
                out = out + self.affine(src, src_value, _depth + 1) * c
            return out
        if row.vary:
            return Affine({path: 1.0}, 0.0)
        return Affine({}, float(value))

    # ------------------------------------------------------------- the names
    def name(self, path: str) -> str:
        """The TOPAS name a free source at ``path`` is written by.

        ``phases.0.atoms.3.biso`` → ``Se2_biso`` (the atom's label), a phase
        quantity → ``p0_scale``, an instrument one → ``zero_shift``, ``u``….
        Characters TOPAS does not take in a name become ``_``; a second phase's
        atoms carry their phase index; a clash gets a numeric suffix.
        """
        if path in self._names:
            return self._names[path]
        raw = path
        if m := _ATOM_PATH.match(path):
            ip, ia, rest = int(m[1]), int(m[2]), m[3]
            label = None
            if self.structure is not None:
                try:
                    label = self.structure.phases[ip].atoms[ia].label
                except (IndexError, AttributeError):
                    label = None
            label = label or f"a{ia}"
            raw = (f"p{ip}_" if ip else "") + f"{label}_{rest}"
        elif m := _PHASE_PATH.match(path):
            raw = f"p{m[1]}_{m[2]}"
        elif path.startswith("instrument."):
            raw = path.split(".", 1)[1]
            for prefix, to in (("profile.", "prof_"), ("geometry.", "geom_"),
                               ("background.", "bkg_"), ("source.", "src_")):
                if raw.startswith(prefix):
                    raw = to + raw[len(prefix):]
        name = _NAME_CHARS.sub("_", raw.replace(".", "_"))
        if not name[:1].isalpha():
            name = "r" + name
        base, k = name, 2
        while name in self._taken:
            name = f"{base}_{k}"
            k += 1
        self._taken.add(name)
        self._names[path] = name
        return name

    def names(self) -> dict[str, str]:
        """``{TOPAS name: rietx path}`` for every source named so far."""
        return {n: p for p, n in self._names.items()}


def number(value: float) -> str:
    """The shortest decimal that reads back to the same double; ``-0.0`` as ``0``.

    A signed zero is a held component the symmetry forces to zero (``mlx ! -0.0``),
    which TOPAS reads as 0 and a person reads as a typo (showcase row M8).
    """
    if not math.isfinite(value):
        raise ValueError(
            f"a parameter's value is {value!r}, which `repr` spells "
            f"'{value}' and TOPAS does not parse — refused here rather "
            f"than written into a file that fails in another program")
    if value == 0.0:
        return "0"
    return repr(float(value))


class Slot:
    """One written number: a quantity's :class:`Affine`, its TOPAS unit factor
    (TOPAS value = ``factor`` × rietx value) and its current rietx value.

    Rendered only once every slot of the file exists, because whether a source
    is written as a name, a ``prm`` or an equation depends on every place it is
    used (:func:`render_slots`).
    """

    __slots__ = ("affine", "factor", "value", "text", "carry", "path")

    def __init__(self, affine: Affine, factor: float, value: float, *,
                 carry: bool = True, path: str | None = None):
        self.affine, self.factor, self.value = affine, float(factor), float(value)
        self.text: str | None = None
        #: the rietx path of the written quantity itself, which names it where
        #: it is the only statement of its source (``x Ba1_x 0.17``)
        self.path = path
        #: False where the source should stay a ``prm`` in rietx's units even if
        #: this slot is exactly it (a moment DOF in μ_B, not μ_B / edge)
        self.carry = carry

    def __str__(self) -> str:  # pragma: no cover - only after render_slots
        if self.text is None:
            raise RuntimeError("a TOPAS slot was written before it was rendered")
        return self.text


class Expr:
    """A written equation that is not affine (``scale_pks``, a moment on a 2- or
    3-dimensional subspace): ``template`` with ``{0}``, ``{1}``… standing for
    the affine sub-expressions in ``parts``, each in rietx units."""

    __slots__ = ("template", "parts", "text")

    def __init__(self, template: str, parts: list[Affine]):
        self.template, self.parts = template, parts
        self.text: str | None = None

    def __str__(self) -> str:  # pragma: no cover - only after render_slots
        if self.text is None:
            raise RuntimeError("a TOPAS expression was written before it was rendered")
        return self.text


def _affine_text(aff: Affine, factor: float, refined: RefinedSet,
                 source_factor: dict[str, float]) -> str:
    """``aff`` × ``factor`` as a TOPAS expression over the sources' names.

    A source's TOPAS value is ``source_factor[path]`` × its rietx value, so its
    rietx value in an expression is ``name / source_factor``.
    """
    parts: list[str] = []
    const = aff.const * factor
    for path, c in aff.terms.items():
        coef = c * factor / source_factor.get(path, 1.0)
        name = refined.name(path)
        if coef == 1.0:
            term = name
        elif coef == -1.0:
            term = f"-{name}"
        else:
            term = f"{number(coef)}*{name}"
        parts.append(term)
    text = " + ".join(parts) if parts else ""
    text = text.replace("+ -", "- ")
    if const != 0.0 or not parts:
        c = number(const)
        if not parts:
            return c
        text = f"{text} - {number(-const)}" if const < 0 else f"{text} + {c}"
    return text


def render_slots(items: Iterable[Any], refined: RefinedSet) -> list[str]:
    """Render every :class:`Slot` and :class:`Expr` in ``items``; return the
    ``prm`` declarations the file needs for sources no slot carries as itself.

    A free source is written **as itself** (``<name> <value>``) at every slot
    whose affine is exactly that source in the slot's own units (the TOPAS
    spelling of an equality tie is one name in several places), and **through
    an equation** everywhere else. A source that no slot carries as itself is
    declared once with ``prm``. Its unit factor is that of the first slot that
    carries it, so a ``prm`` scale is in TOPAS's units like the scale itself.
    """
    items = list(items)
    slots = [s for s in items if isinstance(s, Slot)]
    exprs = [s for s in items if isinstance(s, Expr)]
    uses: dict[str, int] = {}
    for s in slots:
        for path in s.affine.terms:
            uses[path] = uses.get(path, 0) + 1
    for e in exprs:
        for part in e.parts:
            for path in part.terms:
                uses[path] = uses.get(path, 0) + 2   # an equation always needs the name
    # a source stated once, by one slot that depends on it alone: that slot
    # *is* the parameter, named after the quantity it writes (x Ba1_x 0.17)
    owned: dict[int, str] = {}
    for s in slots:
        if s.carry and len(s.affine.terms) == 1:
            (path, c), = s.affine.terms.items()
            if uses.get(path) == 1:
                owned[id(s)] = path
    # a source carried as itself: one term, coefficient 1 in rietx units,
    # no constant, by a slot of one factor
    carried: dict[str, float] = {}
    for s in slots:
        if id(s) in owned:
            continue
        if s.carry and len(s.affine.terms) == 1 and s.affine.const == 0.0:
            (path, c), = s.affine.terms.items()
            if c == 1.0 and path not in carried:
                carried[path] = s.factor
    used: dict[str, float] = {}
    for s in slots:
        if id(s) in owned:
            continue
        for path in s.affine.terms:
            used.setdefault(path, s.factor)
    for e in exprs:
        for part in e.parts:
            for path in part.terms:
                used.setdefault(path, 1.0)
    # a source no slot carries is declared in rietx's own units (a moment DOF
    # in μ_B, a tied scale as rietx's), so its esd reads as rietx's does
    source_factor = {p: carried.get(p, 1.0) for p in used}
    refined.source_factor.update(source_factor)
    first: set[str] = set()

    def bounds(path: str, a: float, b: float = 0.0) -> str:
        if path in first or refined.rows is None:
            return ""
        first.add(path)
        row = refined.rows.get(path)
        if row is None:
            return ""
        lo, hi = row.lo * a + b, row.hi * a + b
        if a < 0:
            lo, hi = hi, lo
        out = ""
        if math.isfinite(lo):
            out += f" min {number(lo)}"
        if math.isfinite(hi):
            out += f" max {number(hi)}"
        return out

    for s in slots:
        aff = s.affine
        if not aff.terms:
            s.text = f"! {number(s.value * s.factor)}"
            continue
        if id(s) in owned:
            path = owned[id(s)]
            (_, c), = aff.terms.items()
            name = refined.name(s.path or path)
            a, b = c * s.factor, aff.const * s.factor
            refined.carriers[name] = (path, a, b)
            s.text = f"{name} {number(s.value * s.factor)}{bounds(path, a, b)}"
            continue
        if len(aff.terms) == 1 and aff.const == 0.0:
            (path, c), = aff.terms.items()
            if s.carry and c == 1.0 and carried.get(path) == s.factor:
                name = refined.name(path)
                refined.carriers[name] = (path, s.factor, 0.0)
                s.text = (f"{name} {number(s.value * s.factor)}"
                          f"{bounds(path, s.factor)}")
                continue
        s.text = f"= {_affine_text(aff, s.factor, refined, source_factor)};"
    for e in exprs:
        e.text = e.template.format(*(
            f"({_affine_text(part, 1.0, refined, source_factor)})" for part in e.parts))
    declarations = []
    for path, f in used.items():
        if path in carried and carried[path] == f:
            continue
        if path in carried:
            continue
        value = refined.source_value(path)
        held = not refined.is_free(path)
        refined.carriers[refined.name(path)] = (path, source_factor[path], 0.0)
        declarations.append(
            f"prm {'!' if held else ''}{refined.name(path)} "
            f"{number(value * source_factor[path])}"
            f"{'' if held else bounds(path, source_factor[path])}")
    return declarations
