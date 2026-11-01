"""The constraints a TOPAS file states, read back as rietx ties (#721 item 4).

A ``.inp`` states a constraint two ways (Technical Reference § 2.3): one
parameter **name** written at several values (``beq b_Fe 0.5`` on eight sites
is one B), and an **equation** over names (``mly = -mFe / 9.10;``). Reading
only the numbers returns every copy as an independent literal, which is the
model with its constraints dropped: a moment tied across eight sites comes back
as eight held numbers and a shared B as eight free ones (showcase row M6).

:func:`derive_ties` recovers the forms
:func:`~rietx.io.projects.topas.write_topas_inp` writes, and any file stating
the same forms: a value that is exactly a name, and an equation **affine** in
names (sums of ``c*name`` and a constant). Each name is carried by the first
value that is that name alone (``c·name + k``); every other value over it is an
affine tie on the carrier's path, ``Σ (c/c₀)·carrier + k'``, which is the shape
``Refinement.tie`` takes. A moment is the one non-affine case: its freedom in
rietx is a modulus and up to two angles (``crystallography.magnetic.moments``),
so a moment that is ``s`` times a carrier moment is tied as the modulus
``|s|·μ`` and, for ``s < 0``, the antipode (θ → π − θ, φ → φ + π). An equation
outside these forms keeps its value and is reported, never guessed at.

:func:`apply_ties` declares them on a ``Refinement``.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field, replace

import numpy as np

#: The writer's names for phase terms TOPAS has no keyword for, read back by name
#: (``topas_input``): ``p<i>_extinction`` (a ``scale_pks`` equation) and the two
#: magnetic-only widths (the Lorentzian terms of the ``mag_only`` part).
RESERVED_PHASE_TERMS = ("extinction", "magnetic_lor_size", "magnetic_lor_strain")
#: The suffix of the ``phase_name`` of the writer's magnetic part.
MAGNETIC_PART_SUFFIX = " magnetic part"


@dataclass
class TopasTie:
    """``path = Σ c·source + const`` — ``Refinement.tie``'s arguments."""

    path: str
    terms: list[tuple[str, float]]
    const: float = 0.0
    #: the file's names the tie came from, for the message that reports it
    names: tuple[str, ...] = ()


@dataclass
class TopasConstraints:
    """What :func:`derive_ties` read: the ties, the free set the file's names
    state, and the values it could not read as a tie (with why)."""

    ties: list[TopasTie] = field(default_factory=list)
    free: dict[str, bool] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)


# ------------------------------------------------------------- magnetic part

def _close(a, b, rel=1e-9, floor=1.0) -> bool:
    """Equal to within ``rel`` of the larger magnitude, which is at least
    ``floor``. The default floor of 1 makes the test absolute below 1, right for
    a coordinate or a cell length; a *scale* or a shared name needs ``floor=0``,
    because a TOPAS scale of 1e-6 against one of 1.5e-6 is a 50 % disagreement
    that a floor of 1 would call equal."""
    if a is None or b is None:
        return a is b
    return abs(a - b) <= rel * max(floor, abs(a), abs(b))


def _element(species: str) -> str:
    m = re.match(r"[A-Z][a-z]?", species or "")
    return m.group(0) if m else species


def _check_part_equals_nuclear(nuclear, part, path) -> None:
    """Refuse a magnetic part that states anything the merge would discard
    differently from the nuclear ``str``'s: its scale, cell, space group, and
    each site's position, element and occupancy (``io/CLAUDE.md``: a project
    reader refuses where a caller cannot see which part of the model is the
    file's). Only the moments, flags, species charge and magnetic group are
    the part's own, and they are what the merge takes."""
    from .topas import TopasInpError

    def refuse(what, a, b):
        raise TopasInpError(
            f"{path}: {part.name!r} is read as the magnetic half of "
            f"{nuclear.name!r}, but they state {what} differently ({b!r} against "
            f"{a!r}), and the merged phase has one. Make the two agree, or read "
            f"`model.phases` for what each states.")

    if not _close(nuclear.scale, part.scale, floor=0.0):
        refuse("scale", nuclear.scale, part.scale)
    for key in sorted(set(nuclear.cell) | set(part.cell)):
        if not _close(nuclear.cell.get(key), part.cell.get(key)):
            refuse(f"cell {key!r}", nuclear.cell.get(key), part.cell.get(key))
    if part.space_group and part.space_group != nuclear.space_group:
        refuse("space_group", nuclear.space_group, part.space_group)
    sites = {s.label: s for s in nuclear.sites}
    for m in part.sites:
        s = sites.get(m.label)
        if s is None:
            raise TopasInpError(
                f"{path}: site {m.label!r} of {part.name!r} has no site of that "
                f"label in {nuclear.name!r}, so its moment has nowhere to go. "
                f"Merging would drop it; read `model.phases` for what the file "
                f"states.")
        for key in ("x", "y", "z", "occupancy"):
            if not _close(getattr(s, key), getattr(m, key)):
                refuse(f"{key} of site {m.label!r}", getattr(s, key), getattr(m, key))
        if _element(s.species) != _element(m.species):
            refuse(f"species of site {m.label!r}", s.species, m.species)


def magnetic_part_names(phases_in) -> set[str]:
    """Names of the ``"<name> magnetic part"`` str's that
    :func:`split_magnetic_parts` merges: the partner ``<name>`` is present and
    every site of the part is ``mag_only`` and carries a moment. The one
    predicate, so the reader's coverage and the merge cannot disagree."""
    names = {ph.name for ph in phases_in}
    return {ph.name for ph in phases_in
            if ph.name.endswith(MAGNETIC_PART_SUFFIX) and ph.sites
            and ph.name[: -len(MAGNETIC_PART_SUFFIX)] in names
            and all(s.mag_only and s.moment is not None for s in ph.sites)}


def lift_magnetic_parts(coverage, phases_in):
    """``coverage`` with the ``mag_only`` of each mergeable magnetic part no
    longer a refusal: the file states it in the one form this reader builds, so
    ``read_topas_inp`` must not warn that ``to_structure`` refuses it. Any other
    use (``mag_only_for_mag_sites``, a ``mag_only`` str that is no part, or one
    the equality check then refuses) stays refused."""
    parts = magnetic_part_names(phases_in)
    if not parts:
        return coverage
    refused = []
    for h in coverage.refused:
        if (h.feature.name == "magnetic-only phase" and h.keywords == ("mag_only",)
                and h.phases):
            rest = tuple(p for p in h.phases if p not in parts)
            if not rest:
                continue
            h = replace(h, phases=rest)
        refused.append(h)
    return replace(coverage, refused=tuple(refused))


def split_magnetic_parts(phases_in, path="<model>"):
    """``(phases, parts)``: each ``"<name> magnetic part"`` str whose every site
    is ``mag_only`` and carries a moment, merged into ``<name>``.

    The merged phase takes the part's ``mag_space_group`` and its sites' moments
    (matched by label), which is the model the writer split: TOPAS has one
    peak shape per ``str``, so a magnetic-only width needs a second ``str``
    (``topas_input``). ``parts`` maps the merged phase's name to its part.

    The merge is **equal or refuse**: the part's scale, cell, space group and
    each matched site's position, element and occupancy must equal the nuclear
    ``str``'s, and every part site must have a nuclear counterpart
    (:func:`_check_part_equals_nuclear`).
    """
    by_name = {ph.name: ph for ph in phases_in}
    mergeable = magnetic_part_names(phases_in)
    parts = {}
    for ph in phases_in:
        if ph.name not in mergeable:
            continue
        partner = ph.name[: -len(MAGNETIC_PART_SUFFIX)]
        _check_part_equals_nuclear(by_name[partner], ph, path)
        parts[partner] = ph
    if not parts:
        return list(phases_in), {}
    out = []
    for ph in phases_in:
        if ph.name.endswith(MAGNETIC_PART_SUFFIX) and ph.name[: -len(MAGNETIC_PART_SUFFIX)] in parts:
            continue
        part = parts.get(ph.name)
        if part is None:
            out.append(ph)
            continue
        moments = {s.label: s for s in part.sites}
        sites = []
        for s in ph.sites:
            m = moments.get(s.label)
            if m is None:
                sites.append(s)
                continue
            vary = dict(s.vary)
            vary.update({k: v for k, v in m.vary.items() if k in ("mlx", "mly", "mlz")})
            stated = dict(s.stated)
            stated.update({k: v for k, v in m.stated.items() if k in ("mlx", "mly", "mlz")})
            sites.append(replace(s, moment=dict(m.moment), vary=vary, stated=stated,
                                 species=m.species))
        out.append(replace(ph, sites=sites, mag_space_group=part.mag_space_group))
    return out, parts


# ------------------------------------------------------------- equations

class _NotAffine(ValueError):
    pass


def affine_of(expr: str) -> tuple[dict[str, float], float]:
    """``(terms, const)`` for an equation affine in names, or :class:`_NotAffine`."""
    try:
        tree = ast.parse(expr.strip().rstrip(";"), mode="eval").body
    except SyntaxError as exc:
        raise _NotAffine(expr) from exc

    def walk(node) -> tuple[dict[str, float], float]:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return {}, float(node.value)
        if isinstance(node, ast.Name):
            return {node.id: 1.0}, 0.0
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            t, c = walk(node.operand)
            k = -1.0 if isinstance(node.op, ast.USub) else 1.0
            return {n: k * v for n, v in t.items()}, k * c
        if isinstance(node, ast.BinOp):
            lt, lc = walk(node.left)
            rt, rc = walk(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                k = 1.0 if isinstance(node.op, ast.Add) else -1.0
                t = dict(lt)
                for n, v in rt.items():
                    t[n] = t.get(n, 0.0) + k * v
                return t, lc + k * rc
            if isinstance(node.op, ast.Mult):
                if not lt:
                    return {n: lc * v for n, v in rt.items()}, lc * rc
                if not rt:
                    return {n: rc * v for n, v in lt.items()}, lc * rc
            if isinstance(node.op, ast.Div) and not rt and rc != 0.0:
                return {n: v / rc for n, v in lt.items()}, lc / rc
        raise _NotAffine(expr)

    terms, const = walk(tree)
    return {n: v for n, v in terms.items() if v != 0.0}, const


@dataclass
class _Stated:
    path: str
    terms: dict[str, float]
    const: float
    value: float


def _through(expr: str, symbols, chain: tuple[str, ...] = ()) -> str:
    """``expr`` with every **dependent** parameter written out as its equation.

    ``u11 = uA;`` under ``prm uA = 0.006*k;`` is ``u11 = 0.006*k``: ``uA`` is a
    dependent parameter (Technical Reference §2.6), so the name that carries a
    refine state, and that a tie has to be written over, is ``k``. Left as
    ``uA``, the tie would be over a name nothing refines, and a ``beq = k;``
    elsewhere would come back as a second independent parameter. A declaration
    whose equation names nothing (``prm third = 1/3;``) is an *independent*
    parameter by the same section and stays a name. A name already being
    written out is left standing, so a cycle of tail-evaluated declarations
    ends rather than recursing. The names are found with the reader's own
    pattern (``topas._EQUATION_NAME``), so the two cannot disagree about what
    in an equation is a name.
    """
    from .topas import _EQUATION_NAME

    def sub(m):
        name = m.group(0)
        read = symbols.get(name)
        if read is None or read.expr is None or not read.refs or name in chain:
            return name
        return f"({_through(read.expr, symbols, chain + (name,))})"
    return _EQUATION_NAME.sub(sub, expr)


def _stated_value(read, path, symbols, skipped) -> _Stated | None:
    """A value's affine form over declared names, from how the file stated it,
    with every dependent parameter it names written out (:func:`_through`)."""
    if read is None:
        return None
    if read.expr is not None:
        expr = _through(read.expr, symbols)
        try:
            terms, const = affine_of(expr)
        except _NotAffine:
            through = "" if expr == read.expr else f", which is '= {expr};',"
            skipped.append(f"{path}: '= {read.expr};'{through} is not affine in "
                           f"parameter names; read as its value {read.value!r}")
            return None
        terms = {n: c for n, c in terms.items() if n in symbols}
        if not terms:
            return None
        return _Stated(path, terms, const, read.value)
    if read.name:
        return _Stated(path, {read.name: 1.0}, 0.0, read.value)
    return None


def derive_ties(model, phases_in, structure) -> TopasConstraints:
    """Every name and affine equation of the built phases, as rietx ties.

    ``phases_in`` are the :class:`~.topas.TopasPhase` the ``structure`` was built
    from, in its order (after :func:`split_magnetic_parts`).
    """
    out = TopasConstraints()
    symbols = model.symbols
    stated: list[_Stated] = []
    moments: dict[str, tuple[str, dict]] = {}   # atom path → (phase base, comps)
    for ip, (tp, phase) in enumerate(zip(phases_in, structure.phases)):
        base = f"phases.{ip}"
        if (st := _stated_value(tp.stated.get("scale"), f"{base}.scale", symbols, out.skipped)):
            stated.append(st)
        for key, attr in (("a", "a"), ("b", "b"), ("c", "c"), ("al", "alpha"),
                          ("be", "beta"), ("ga", "gamma")):
            if (st := _stated_value(tp.stated.get(key), f"{base}.cell.{attr}", symbols,
                                    out.skipped)):
                stated.append(st)
        for ia, site in enumerate(tp.sites):
            apath = f"{base}.atoms.{ia}"
            for key, attr in (("x", "x"), ("y", "y"), ("z", "z"), ("occ", "occ"),
                              ("beq", "biso"), ("u11", "u11"), ("u22", "u22"),
                              ("u33", "u33"), ("u12", "u12"), ("u13", "u13"),
                              ("u23", "u23")):
                if (st := _stated_value(site.stated.get(key), f"{apath}.{attr}",
                                        symbols, out.skipped)):
                    stated.append(st)
            comps = {}
            for key in ("mlx", "mly", "mlz"):
                read = site.stated.get(key)
                if read is None:
                    continue
                st = _stated_value(read, f"{apath}.{key}", symbols, out.skipped)
                comps[key] = st if st is not None else _Stated(f"{apath}.{key}", {}, read.value,
                                                               read.value)
            if comps and phase.atoms[ia].moment is not None:
                moments[apath] = (base, comps)

    # carriers: the first value that is one name alone
    carrier: dict[str, _Stated] = {}
    for st in stated:
        if len(st.terms) == 1:
            (name, c), = st.terms.items()
            if name not in carrier and c != 0.0:
                carrier[name] = st
    # A name stated at two values is two statements of one parameter: refused,
    # not chosen between (the root rulebook's "a row the format states two
    # ways"); a tie would otherwise move the later value onto the carrier's.
    # The moment components are statements too: ``mlx mA 2`` and ``mlx mA 3`` are
    # one name at two values. Compared relative to the larger value with no
    # floor (a TOPAS scale of 1e-6 is real), at 1e-6: three decades looser than
    # the merge's 1e-9 because a value is recovered through a division and an
    # offset, and far tighter than the six or seven figures a .inp prints (sized
    # against that print precision, not measured on a file).
    from .topas import TopasInpError

    seen: dict[str, tuple[float, str]] = {}
    moment_stated = [st for _, comps in moments.values() for st in comps.values()]
    for st in stated + moment_stated:
        if len(st.terms) != 1 or st.value is None:
            continue
        (name, c), = st.terms.items()
        if c == 0.0:
            continue
        v = (st.value - st.const) / c
        if name not in seen:
            seen[name] = (v, st.path)
            continue
        v0, where0 = seen[name]
        if not _close(v, v0, 1e-6, floor=0.0):
            raise TopasInpError(
                f"{getattr(model, 'path', None) or '<model>'}: the name {name!r} "
                f"is stated at two values, {v0!r} at {where0} and {v!r} at "
                f"{st.path}. A shared name is one parameter, so the file states "
                f"it two ways; reading either would choose for the caller. "
                f"Make them agree, or read `model.phases` for what each site "
                f"states.")
    for st in stated:
        if any(n not in carrier for n in st.terms):
            out.skipped.append(f"{st.path}: depends on "
                               f"{sorted(n for n in st.terms if n not in carrier)}, "
                               f"which no value carries alone; read as its value")
            continue
        if len(st.terms) == 1 and carrier[next(iter(st.terms))] is st:
            name = next(iter(st.terms))
            read = symbols.get(name)
            if read is not None and read.vary is not None:
                out.free[st.path] = bool(read.vary)
            continue
        terms, const = [], st.const
        for name, c in st.terms.items():
            car = carrier[name]
            c0 = car.terms[name]
            terms.append((car.path, c / c0))
            const -= c * car.const / c0
        out.ties.append(TopasTie(st.path, terms, const, tuple(st.terms)))

    _moment_ties(structure, moments, symbols, out)
    return out


def _moment_ties(structure, moments, symbols, out: TopasConstraints) -> None:
    """Moments stated as one name times a vector: ties on the moment DOFs."""
    from ...crystallography.magnetic.moments import dofs_from_moment, moment_frame

    groups: dict[str, list] = {}
    for apath, (base, comps) in moments.items():
        names = set()
        for st in comps.values():
            names.update(st.terms)
        if len(names) != 1:
            if names:
                out.skipped.append(f"{apath}.moment: stated over {sorted(names)}; "
                                   f"only a moment over one name is read as a tie")
            continue
        name = names.pop()
        if any(st.terms and st.const != 0.0 for st in comps.values()):
            out.skipped.append(f"{apath}.moment: an offset beside {name}; read as values")
            continue
        groups.setdefault(name, []).append(apath)
    for name, paths in groups.items():
        first = paths[0]
        ip = int(first.split(".")[1])
        phase = structure.phases[ip]
        cell = phase.cell.lengths_angles()
        group = phase.magnetic_symmetry.group()

        def frame_of(apath):
            atom = phase.atoms[int(apath.split(".")[3])]
            return atom, moment_frame(group.allowed_moment_basis(
                (atom.x.value, atom.y.value, atom.z.value)), cell)

        atom0, f0 = frame_of(first)
        m0 = np.asarray(atom0.moment.values())
        d0 = dofs_from_moment(f0, cell, m0)
        read = symbols.get(name)
        if read is not None and read.vary is not None:
            out.free[f"{first}.moment.dof0"] = bool(read.vary)
            for k in range(1, len(f0)):
                out.free[f"{first}.moment.dof{k}"] = False
        for apath in paths[1:]:
            atom, f = frame_of(apath)
            m = np.asarray(atom.moment.values())
            denom = float(m0 @ m0)
            if denom == 0.0:
                continue
            s = float(m @ m0) / denom
            if not np.allclose(m, s * m0, atol=1e-9 * max(1.0, abs(s)) * math.sqrt(denom)):
                out.skipped.append(f"{apath}.moment: not parallel to {first}'s; read as values")
                continue
            if len(f) != len(f0) or not np.allclose(f, f0, atol=1e-12):
                if len(f) == len(f0) == 1:
                    g = float(f[0] @ f0[0])   # ±1 for parallel unit frames
                    out.ties.append(TopasTie(f"{apath}.moment.dof0",
                                             [(f"{first}.moment.dof0", s / g)], 0.0, (name,)))
                else:
                    out.skipped.append(f"{apath}.moment: a different moment frame from "
                                       f"{first}'s; read as values")
                continue
            d = dofs_from_moment(f, cell, m)
            n = len(f)
            if n == 1:
                out.ties.append(TopasTie(f"{apath}.moment.dof0",
                                         [(f"{first}.moment.dof0", s)], 0.0, (name,)))
                continue
            out.ties.append(TopasTie(f"{apath}.moment.dof0",
                                     [(f"{first}.moment.dof0", abs(s))], 0.0, (name,)))
            if n == 2:
                out.ties.append(TopasTie(f"{apath}.moment.dof1",
                                         [(f"{first}.moment.dof1", 1.0)],
                                         float(d[1] - d0[1]), (name,)))
            else:
                k = -1.0 if s < 0 else 1.0
                out.ties.append(TopasTie(f"{apath}.moment.dof1",
                                         [(f"{first}.moment.dof1", k)],
                                         float(d[1] - k * d0[1]), (name,)))
                out.ties.append(TopasTie(f"{apath}.moment.dof2",
                                         [(f"{first}.moment.dof2", 1.0)],
                                         float(d[2] - d0[2]), (name,)))


def apply_ties(refinement, constraints: TopasConstraints) -> list[str]:
    """Declare ``constraints`` on ``refinement``: the free set, then each tie.

    Returns the paths tied. Everything not applied is appended to
    ``constraints.skipped`` with its reason: a path with no row, one already
    tied (a symmetry tie, say), one the table holds locked, one the
    caller holds (never freed over a hold), a path
    ``set_vary`` declined, and a tie the table refuses.
    """
    rows = {r.path: r for r in refinement.parameters()}

    def usable(path, freeing=False):
        row = rows.get(path)
        if row is None:
            constraints.skipped.append(f"{path}: not applied, the model has no such parameter")
        elif row.tie is not None:
            constraints.skipped.append(f"{path}: not applied, already tied (symmetry or an "
                                       f"earlier tie)")
        elif row.locked:
            constraints.skipped.append(f"{path}: not applied, the parameter is locked")
        elif freeing and row.held:
            # `set_vary` raises on a literal held path, which would abort the
            # call before any tie is declared: a hold is the caller's own
            # declaration, so it is named and left standing.
            constraints.skipped.append(f"{path}: not freed, the refinement holds it "
                                       f"(`unhold` it first if the file's flag should win)")
        else:
            return True
        return False

    for vary in (True, False):
        want = [p for p, v in constraints.free.items()
                if bool(v) is vary and usable(p, freeing=vary)]
        if want:
            changed = set(refinement.set_vary(want, vary))
            for p in want:
                row = rows[p]
                if p not in changed and bool(row.vary) is not vary:
                    constraints.skipped.append(
                        f"{p}: set_vary({'free' if vary else 'hold'}) declined it")
    tied = []
    for t in constraints.ties:
        if not usable(t.path):
            continue
        try:
            refinement.tie(t.path, dict(t.terms), offset=t.const)
            tied.append(t.path)
        except ValueError as exc:
            constraints.skipped.append(f"{t.path}: not tied ({exc})")
    return tied
