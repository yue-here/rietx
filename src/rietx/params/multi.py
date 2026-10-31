"""Multi-histogram parameter bookkeeping (WP-0308).

A joint refinement fits one **shared** :class:`~rietx.schemas.structure.Structure`
against several patterns, each measured on its **own**
:class:`~rietx.schemas.instrument.Instrument` (different wavelength, geometry,
resolution, background).  Physically the split is instrument-vs-sample: the
crystal (cell, coordinates, occupancies, ADPs, size/strain, extinction, texture)
is one object seen by every histogram, while the instrument and the per-pattern
scale (incident flux × illuminated volume) differ.

:class:`MultiParameterTable` owns one ordinary :class:`ParameterTable` per
histogram — so each keeps its crystal-system cell ties, Wyckoff DOFs and
bounds unchanged — and threads a single combined free vector θ through them
with a column map that folds *shared* columns onto one shared combined column
(fed to every histogram's model) while giving *per-histogram* columns their own.
The stacked residual/Jacobian in
:func:`~rietx.optimize.least_squares.run_multi_least_squares` scatters each
histogram's block through this map.

Per-histogram parameters are named with a ``hist.{h}.`` scope
(``hist.0.instrument.zero_shift``, ``hist.1.phases.0.scale``); shared parameters
keep their bare path (``phases.0.cell.a``).  A turn-on glob frees a parameter
when it matches either form, so every existing single-histogram plan
(``phases.*.scale``, ``instrument.background.*``) frees *all* histograms' copies
unchanged, while a scoped glob (``hist.1.*``) targets one.
"""

from __future__ import annotations

import fnmatch
import math
from dataclasses import dataclass, field

import numpy as np

from ..schemas.instrument import Instrument
from ..schemas.parametric import CoordinateTable, ParametricEquation
from ..schemas.structure import Structure
from .parametric import ResolvedParametric, least_squares_start, resolve_parametric
from .vector import (
    AffineTie,
    ParameterTable,
    _is_wavelength,
    _tie_text,
    check_wavelength_freedom,
    unknown_paths_among,
)


def _unscoped(path: str) -> str:
    """A combined path with any ``hist.{h}.`` scope removed.

    Shared paths arrive bare and come back unchanged, so this is the inverse of
    :meth:`MultiParameterTable._canonical` for exactly the cases that have one.
    """
    if path.startswith("hist."):
        return path.split(".", 2)[2]
    return path


#: Sample **size** terms and the power of λ each carries — the whole of what
#: WP-1131 found wrong with the sharing map, written as data so a new size term
#: joins it in one line.  ``lor_size`` is a FWHM coefficient and goes as λ
#: (Scherrer, ``(180/π)·K·λ/L``); ``gauss_size`` is a *variance* coefficient and
#: goes as λ².  Everything else a phase carries — strain (both), Stephens Λ(hkl),
#: extinction, texture, cell, coordinates, ADPs — is λ-free and stays shared as
#: it always was, which is what makes the strain control of WP-1131 § Finding 2
#: bit-identical across this change.
#: ``magnetic_lor_size`` (WP-1343) joins in that one line and carries λ¹ for
#: exactly the reason ``lor_size`` does: it is the same Scherrer coefficient
#: (180/π)·K·λ/L with the *magnetic coherence length* in place of the
#: crystallite size, so one magnetic domain needs coefficients in the ratio
#: λ₂/λ₁ across two histograms.  Its strain partner is λ-free and is absent
#: here, as both nuclear strain terms are.
SIZE_LAMBDA_POWER = {"lor_size": 1.0, "gauss_size": 2.0,
                     "magnetic_lor_size": 1.0}

#: Size terms that a phase carries only when it declares a magnetic structure:
#: ``ParameterTable`` registers them nowhere else, so a sharing factor for one
#: of these on a non-magnetic phase would be a conversion for a column no
#: table holds.  The guard below reads this rather than the term's spelling.
MAGNETIC_SIZE_TERMS = frozenset({"magnetic_lor_size"})


def _phase_carries(phase, term: str) -> bool:
    """Whether ``phase`` has the size term ``term`` at all (WP-1343)."""
    return term not in MAGNETIC_SIZE_TERMS or phase.magnetic_symmetry is not None


def _longest_wavelength(instrument: Instrument) -> float | None:
    """The source's longest declared line (Å), or ``None`` if it has none.

    A **deliberate second spelling** of
    :func:`~rietx.optimize.least_squares._longest_line_wavelength`, not an
    independent choice of "which λ": that one reads a *compiled* model and this
    one a schema object, and the sharing map has to answer before anything is
    compiled.  The two are held together by
    ``tests/test_multi_histogram.py::test_the_two_wavelength_selectors_agree``
    rather than by this comment — the same idiom the two ``_ZERO_BOUND``
    copies in ``schemas.structure`` and ``schemas.instrument`` use.

    **Longest** for the reason that function gives: every size surface in the
    package attributes a coefficient to the longest line, so a Kα2 offset can
    never move an attribution on its own.
    """
    lams = [line.wavelength.value for line in instrument.source.lines
            if line.wavelength.value > 0.0]
    return max(lams) if lams else None


def size_value_scales(structure: Structure, instruments: list[Instrument],
                      sharing: "SharingMap") -> list[dict[str, float]]:
    """Per-histogram factors that turn a shared size column into one specimen.

    One entry per histogram, each mapping a size path to the factor between
    **that histogram's** coefficient and the shared column's, which is carried
    in histogram 0's wavelength (so histogram 0's map is empty and its numbers
    are unchanged, and a reader of ``phases.0.lor_size`` is reading the
    coefficient at λ₀).

    **The physics, and why the Scherrer constant is not in it** (WP-1131).  A
    size coefficient is (180/π)·K·λ/L, so for one crystallite size L two
    histograms need coefficients in the ratio λ₂/λ₁ — K and the degree
    conversion cancel, which is why sharing a size across wavelengths is
    provably wrong whatever convention K follows, and why the fix needs no
    convention at all.  Microstrain is 2·(Δd/d)·tanθ with no λ in it, so it
    stays one number and is not listed here.

    Empty maps (⇒ the pre-WP-1131 behaviour, bit for bit) in three cases, and
    each is the honest answer rather than a fallback: **one** histogram, where
    there is nothing to normalise; a source with **no declared line**, where
    there is no λ to normalise by; and equal wavelengths, where every factor is
    exactly 1.0 — which is every joint fit that existed before this change.
    """
    lams = [_longest_wavelength(ins) for ins in instruments]
    if len(lams) < 2 or any(lam is None for lam in lams):
        return [{} for _ in instruments]
    ref = lams[0]
    scales: list[dict[str, float]] = []
    for lam in lams:
        ratio = lam / ref
        one: dict[str, float] = {}
        if ratio != 1.0:
            for ip, ph in enumerate(structure.phases):
                for term, power in SIZE_LAMBDA_POWER.items():
                    if not _phase_carries(ph, term):
                        continue
                    path = f"phases.{ip}.{term}"
                    if sharing.is_shared(path):
                        one[path] = ratio ** power
        scales.append(one)
    return scales


@dataclass
class SharingMap:
    """Which parameter paths are shared across histograms vs. per-histogram.

    Default rule: a path is **per-histogram** iff it starts with ``instrument.``
    or ends with ``.scale``; everything else (cell, coordinates, occupancies,
    ADPs, size/strain, extinction, preferred orientation) is **shared** — one
    specimen, one crystal.  ``per_histogram`` / ``shared`` are override glob
    lists (fnmatch on the bare unscoped path, no brackets), checked in that
    order before the default, so a caller can e.g. give each histogram its own
    preferred-orientation axis (``per_histogram=["phases.*.preferred_orientation.*"]``)
    or tie a sample-displacement across mounts.
    """

    per_histogram: list[str] = field(default_factory=list)
    shared: list[str] = field(default_factory=list)

    def is_shared(self, path: str) -> bool:
        if any(fnmatch.fnmatchcase(path, g) for g in self.per_histogram):
            return False
        if any(fnmatch.fnmatchcase(path, g) for g in self.shared):
            return True
        return not (path.startswith("instrument.") or path.endswith(".scale"))


def row_shared(sharing: SharingMap, entry) -> bool:
    """Whether a table entry is one column of the joint fit, or a row per
    histogram.

    An entry is shared when its own path is, and a **tied** one also needs
    every source of its tie shared: ``u11`` of an anisotropic site is a
    follower of the site's ``adp.k`` columns, so under
    ``per_histogram=["phases.*.atoms.*.adp.*"]`` it is each histogram's own
    although no glob names it (WP-2028).  The one rule behind
    :meth:`MultiParameterTable.row_path`, which the joint result's rows,
    ``MultiHistogramRefinement.parameters()`` and :meth:`~MultiParameterTable.known_paths`
    all spell with.
    """
    if not sharing.is_shared(entry.path):
        return False
    return entry.tie is None or all(sharing.is_shared(src)
                                    for src, _ in entry.tie.terms)


def _display_unit(path: str) -> str | None:
    """The unit a reported coefficient's target is quoted in, or ``None``.

    Read off the parameter's family in :mod:`rietx.help`, the one place what
    a name *is* is written, rather than off the table's own unit record, which
    holds only the few units a seed reads (a cell edge has none there, and a
    displacement parameter's is the raw ``A^2``).  ``None`` for a family that
    declares no unit, so a dimensionless target prints none.
    """
    from ..help import help_for

    entry = help_for(path)
    return None if entry is None else entry.unit


def _refuse_clashing_declarations(declared: list[ParametricEquation], n: int) -> None:
    """Two declarations may share no name, nor a target on one pattern (WP-1325).

    A name is its coefficients' paths, so two of one name would be one set of
    columns claimed twice.  A target is one tie per *pattern*, so two
    declarations may drive it on disjoint subsets — one equation per phase field,
    a property varying smoothly inside a field and not across its boundary —
    but a pattern both subsets hold would have its tie silently replaced.
    """
    names: set[str] = set()
    targets: dict[str, list[tuple[str, set[int]]]] = {}
    for equation in declared:
        if equation.name in names:
            raise ValueError(
                f"two parametric equations are named {equation.name!r}: a name is its "
                f"coefficients' paths (vars.{equation.name}_0, …), so each needs its own")
        names.add(equation.name)
        mine = set(range(n)) if equation.patterns is None else set(equation.patterns)
        for other, theirs in targets.get(equation.target, []):
            both = sorted(mine & theirs)
            if both:
                raise ValueError(
                    f"parametric equations {other!r} and {equation.name!r} both drive "
                    f"{equation.target} on pattern{'' if len(both) == 1 else 's'} "
                    f"{', '.join(map(str, both[:5]))}{' …' if len(both) > 5 else ''}: "
                    "a target follows one function per pattern. Give the two "
                    "declarations disjoint subsets (patterns=…), or combine them "
                    "into one")
        targets.setdefault(equation.target, []).append((equation.name, mine))


def _target_refusal(table: ParameterTable, e) -> str | None:
    """Why ``e`` cannot be a parametric target, in ``held_because``'s order.

    The structural reasons first, because no verb lifts them; a hold next.
    Then the two kinds of parameter whose value is not one quantity across
    patterns: a rigid body's increment, which restarts at zero at every commit
    while its record moves (WP-1805), and a moment DOF, read in a frame rebuilt
    from the cell at every stage start (#598).  The intensity modes'
    force-fix does not arise: a joint fit is Rietveld-only.
    """
    if e.locked:
        return ("is structurally fixed by symmetry or by the model (locked), so "
                "no parametric equation can drive it")
    if e.tie is not None:
        sources = ", ".join(src for src, _ in e.tie.terms)
        return (f"is tied: = {_tie_text(e.tie)}. A target must be a parameter "
                f"that moves itself; declare the equation on {sources} instead")
    if e.held:
        return ("is held (Phase.floating_origin fixes it), so no stage frees it; "
                "declare the equation on another coordinate of the phase")
    if table._body_increment_kind(e.path) is not None:
        return ("is a rigid body's increment, which restarts at zero at every "
                "commit while the body's record moves, so it is not one "
                "quantity across patterns")
    if any(e.path.startswith(f"{base}.moment.") for base in table.moment_frames()):
        return ("is a moment DOF, read in a frame rebuilt from the cell at every "
                "stage start, so it is not one quantity across patterns")
    return None


def _starting_structures(structure: Structure | list[Structure],
                         n: int) -> list[Structure]:
    """One starting structure per histogram: the one given, or each its own.

    A list is the per-pattern form (WP-1325): a library's specimens start from
    their own cells, occupancies and widths.  It must describe **one model**,
    so the topology is checked here (phase count, space groups, atoms); the
    shared values are checked by :meth:`MultiParameterTable._check_starts_agree`
    once the tables exist, the table being the authority on which paths a
    model has.
    """
    if isinstance(structure, Structure):
        return [structure] * n
    starts = list(structure)
    if len(starts) != n:
        raise ValueError(
            f"{len(starts)} starting structures for {n} instruments: pass one "
            "Structure for every histogram, or one per histogram")
    ref = starts[0]
    for h, s in enumerate(starts[1:], start=1):
        if len(s.phases) != len(ref.phases):
            raise ValueError(
                f"starting structure {h} has {len(s.phases)} phase(s) and "
                f"structure 0 has {len(ref.phases)}: per-pattern starting "
                "structures are one model with different values, so their "
                "phases must match")
        for ip, (p0, p) in enumerate(zip(ref.phases, s.phases, strict=True)):
            if p.space_group != p0.space_group:
                raise ValueError(
                    f"phase {ip} is {p0.space_group!r} in starting structure 0 "
                    f"and {p.space_group!r} in structure {h}: per-pattern "
                    "starting structures must share each phase's space group")
            a0 = [(a.label, a.species) for a in p0.atoms]
            a1 = [(a.label, a.species) for a in p.atoms]
            if a0 != a1:
                raise ValueError(
                    f"phase {ip}'s atoms differ between starting structure 0 "
                    f"{a0} and structure {h} {a1}: per-pattern starting "
                    "structures must carry the same sites, in the same order")
    return starts


class MultiParameterTable:
    """One :class:`ParameterTable` per histogram + a shared/per-histogram θ map.

    ``structure`` is one :class:`Structure` deep-copied into every histogram,
    or a list of one per histogram (WP-1325): the same model with each
    pattern's own starting values.  A list must agree on every **shared**
    path's value (a shared column has one starting value) and may differ
    anywhere a path is per-histogram — instrument, scales, a
    ``SharingMap.per_histogram`` override, a parametric target.

    ``parametric`` declares targets as functions of ``coordinates``
    (:class:`~rietx.schemas.parametric.ParametricEquation`): each target becomes
    per-histogram, its coefficients ``vars.{name}_{j}`` are added to every
    table and fold onto one shared column each, and the target in each
    pattern of the subset is tied onto Σ_j Φ_kj·``vars.{name}_{j}``.  Every
    refusal is made here, before any solve.  :attr:`parametric` holds the
    declarations as resolved.
    """

    def __init__(self, structure: Structure | list[Structure],
                 instruments: list[Instrument], *,
                 sharing: SharingMap | None = None,
                 parametric: list[ParametricEquation] | None = None,
                 coordinates: CoordinateTable | None = None):
        if len(instruments) < 1:
            raise ValueError("need at least one instrument")
        starts = _starting_structures(structure, len(instruments))
        declared = list(parametric or [])
        self.sharing = sharing or SharingMap()
        if declared:
            _refuse_clashing_declarations(declared, len(instruments))
            # a private copy: the targets (and, below, what follows them)
            # become per-histogram, which is the caller's map plus this fit's
            # declarations and never an edit of the caller's object
            self.sharing = SharingMap(
                per_histogram=[*self.sharing.per_histogram,
                               *(t.target for t in declared)],
                shared=list(self.sharing.shared))
        #: coefficient path → (its target, j + 1): where its column sits in the
        #: combined order (:meth:`_rebuild_columns`), empty without a
        #: parametric declaration
        self._column_anchor: dict[str, tuple[str, int]] = {}
        #: the parametric declarations as resolved (reference and scale frozen)
        self.parametric: list[ResolvedParametric] = []
        # a private structure copy per histogram: shared parameters are written
        # identically into every copy at each commit; only the per-histogram
        # scale (and any per-histogram override) diverges.
        self.structures: list[Structure] = [s.model_copy(deep=True)
                                             for s in starts]
        self.instruments: list[Instrument] = [ins.model_copy(deep=True)
                                              for ins in instruments]
        # ``joint=True``: a sub-table sees one instrument, so it would always
        # read the single-histogram case and refuse a wavelength this fit is
        # entitled to free.  The count is made once, over all of them, in
        # :meth:`_rebuild_columns`.
        # WP-1131: a *size* coefficient is not one number across wavelengths,
        # so before any table is built each copy is put into its own
        # histogram's units and the table is told the factor.  Empty maps
        # everywhere (one histogram, equal wavelengths, or a source with no
        # declared line) leave every table exactly as it was.
        self.value_scales = size_value_scales(starts[0], self.instruments,
                                              self.sharing)
        for struct, scale in zip(self.structures, self.value_scales, strict=True):
            for path, factor in scale.items():
                _, ip, term = path.split(".")
                param = getattr(struct.phases[int(ip)], term)
                # the declared window travels with the value: it is a limit on
                # the *specimen* quantity, so in this histogram's units it is
                # the same factor away.  Scaling the value alone would trip
                # ``Parameter``'s own min<=value<=max validator on any size
                # term carrying a finite bound, with a message that says
                # nothing about wavelengths -- and would leave the histograms
                # disagreeing about a window the caller stated once.
                lo, hi = param.min * factor, param.max * factor
                param.min, param.max = -math.inf, math.inf
                param.value = param.value * factor
                param.min, param.max = lo, hi
        self.tables: list[ParameterTable] = [
            ParameterTable(s, ins, joint=True)
            for s, ins in zip(self.structures, self.instruments, strict=True)]
        for table, scale in zip(self.tables, self.value_scales, strict=True):
            if scale:
                table.apply_value_scale(scale)
        if declared:
            self._install_parametric(declared, coordinates)
        if len({id(s) for s in starts}) > 1:
            self._check_starts_agree(starts)
        self._check_moment_frames_shared()
        self._rebuild_columns()

    # -- per-pattern starting values and parametric equations (WP-1325) -----
    def _check_starts_agree(self, starts: list[Structure]) -> None:
        """Refuse per-pattern starts that disagree on a shared path.

        A shared path is one column, so it has one starting value: the column
        map writes each histogram's into it and keeps the last, which would
        hand every other histogram a value it never declared.  Compared on the
        tables, the authority on which paths a model has, except where WP-1131
        rescaled a shared size term into a histogram's own units, which is
        compared as the caller wrote it.
        """
        scaled = set().union(*(set(s) for s in self.value_scales))
        shared0 = {e.path: e.value for e in self.tables[0].entries
                   if self.sharing.is_shared(e.path)}
        disagree: dict[str, list[int]] = {}
        for h, table in enumerate(self.tables[1:], start=1):
            mine = {e.path: e.value for e in table.entries
                    if self.sharing.is_shared(e.path)}
            if set(mine) != set(shared0):
                odd = sorted(set(mine) ^ set(shared0))
                raise ValueError(
                    f"starting structure {h} and structure 0 do not have the same "
                    f"shared parameters ({odd[0]} is in one only): per-pattern "
                    "starting structures are one model with different values")
            for path, v0 in shared0.items():
                if path in scaled:
                    _, ip, term = path.split(".")
                    v0 = getattr(starts[0].phases[int(ip)], term).value
                    v = getattr(starts[h].phases[int(ip)], term).value
                else:
                    v = mine[path]
                if v != v0:
                    disagree.setdefault(path, []).append(h)
        if disagree:
            path, hs = next(iter(disagree.items()))
            more = (f" (and {len(disagree) - 1} other shared path"
                    f"{'' if len(disagree) == 2 else 's'})" if len(disagree) > 1 else "")
            raise ValueError(
                f"the starting structures disagree on {path}, which is shared: "
                f"histogram{'' if len(hs) == 1 else 's'} {', '.join(map(str, hs))} "
                f"differ from histogram 0{more}. A shared parameter is one column "
                f"with one starting value; start every structure at one value, "
                f"make it per-histogram (SharingMap(per_histogram=['{path}'])), "
                f"or declare it a ParametricEquation target")

    def _install_parametric(self, declared: list[ParametricEquation],
                            coordinates: CoordinateTable | None) -> None:
        """Resolve each declaration, refuse what no table can carry, wire the rest.

        Refusals first, all of them, so a declaration that cannot be built
        leaves no half-wired table behind: the target must exist in every
        subset histogram's model and be a parameter a parametric equation may drive — not
        locked, not already tied (its sources named), not held, not a rigid
        body's increment or a moment DOF, not a coordinate DOF whose
        anchor the subset's starting structures store differently, and not a
        size coefficient over patterns at different wavelengths.  A
        coefficient's path must be new and shared under the caller's map.

        Then, per declaration: what follows the target becomes per-histogram
        with it (a cubic ``b`` and ``c`` follow ``a`` in every histogram, so a
        bare row would report histogram 0's value as everyone's); the
        coefficients are added to **every** table, so they fold onto one
        shared column each (``_rebuild_columns`` asserts the shared free sets
        agree), at the least-squares start (:func:`least_squares_start`); and
        the target in each subset histogram is tied onto Σ_j Φ_kj·c_j.
        """
        n = self.n_histograms
        resolved: list[ResolvedParametric] = []
        for equation in declared:
            resolved.append(resolve_parametric(equation, coordinates, n,
                                               target_unit=_display_unit(equation.target)))
        for r in resolved:
            for h in r.patterns:
                table = self.tables[h]
                i = table._paths.get(r.target)
                if i is None:
                    raise ValueError(
                        f"parametric equation {r.name!r}: target {r.target!r} is not a "
                        f"parameter of histogram {h}'s model; list them with "
                        f"[e.path for e in mtable.tables[{h}].entries]")
                why = _target_refusal(table, table.entries[i])
                if why:
                    raise ValueError(f"parametric equation {r.name!r}: {r.target} in "
                                     f"histogram {h} {why}")
            self._refuse_unanchorable(r)
            self._refuse_size_across_wavelengths(r)
            for path in r.paths:
                if not self.sharing.is_shared(path):
                    raise ValueError(
                        f"parametric equation {r.name!r}: the sharing map makes {path} "
                        "per-histogram (a per_histogram glob matches it), but a "
                        "coefficient is one number across the subset; narrow the "
                        "glob so vars.* stays shared")
                if any(path in t._paths for t in self.tables):
                    raise ValueError(
                        f"parametric equation {r.name!r}: {path} already exists; "
                        "rename the declaration")
        follows: dict[str, None] = {}
        # one transpose of each table's ties, however many declarations ask it
        reach_of: dict[int, dict[str, list[str]]] = {}
        for r in resolved:
            for h in r.patterns:
                if h not in reach_of:
                    reach_of[h] = self.tables[h].entry_reach()
                for q in reach_of[h][r.target]:
                    if q != r.target and self.sharing.is_shared(q):
                        follows[q] = None
        self.sharing.per_histogram.extend(follows)
        touched: set[int] = set()
        for r in resolved:
            targets = [self.tables[h].entries[self.tables[h]._paths[r.target]]
                       for h in r.patterns]
            start = np.array([e.value for e in targets], dtype=np.float64)
            coeffs = least_squares_start(r, start)
            lo, hi, unit = -np.inf, np.inf, None
            if r.equation.basis == "constant":
                # the one coefficient *is* the target in every pattern of the
                # subset, so it carries the target's declared box and unit —
                # WP-1119's renaming rule, which makes the column the target's
                # own to the seed (``seed_floored`` reads the row's bounds) and
                # the FD step.  A sum of terms has no such box, which is what
                # PARAMETRIC_OUT_OF_RANGE reports after the fit.
                lo = max(e.lo for e in targets)
                hi = min(e.hi for e in targets)
                if lo > hi:
                    raise ValueError(
                        f"parametric equation {r.name!r}: the subset's patterns declare "
                        f"{r.target} bounds with no common value ([{lo:g}, {hi:g}] "
                        "intersected), so no one value can be every pattern's")
                coeffs = np.clip(coeffs, lo, hi)
                unit = self.tables[r.patterns[0]]._units.get(r.target)
            for table in self.tables:
                for path, c in zip(r.paths, coeffs, strict=True):
                    table.add_parameter(path, float(c), vary=False, lo=lo, hi=hi,
                                        unit=unit)
            for k, h in enumerate(r.patterns):
                tie = AffineTie(terms=tuple(
                    (path, float(r.phi[k, j])) for j, path in enumerate(r.paths)))
                try:
                    self.tables[h].set_tie(r.target, tie)
                except ValueError as exc:
                    raise ValueError(f"parametric equation {r.name!r}: {exc}") from exc
                touched.add(h)
            for j, path in enumerate(r.paths):
                self._column_anchor[path] = (r.target, j + 1)
        for h in sorted(touched):
            self.tables[h].refresh_ties()
        self.parametric = resolved

    def _refuse_unanchorable(self, r: ResolvedParametric) -> None:
        """A coordinate DOF is a step from each table's stored coordinate.

        The row is x = x_stored + Σ Bₖ·θₖ (WP-1432), so a function of the DOF
        across patterns is a function of the *coordinate* only where every
        pattern of the subset stores the same x.  Per-pattern starting
        structures that differ there would make c₀ a displacement from
        different points; refused, naming the coordinate.
        """
        t0 = self.tables[r.patterns[0]]
        anchored = t0._anchored_dofs.get(r.target)
        if not anchored:
            return
        for coord, _ in anchored:
            values = {h: self.tables[h].entries[self.tables[h]._paths[coord]].value
                      for h in r.patterns}
            if len(set(values.values())) > 1:
                raise ValueError(
                    f"parametric equation {r.name!r}: {r.target} is a displacement from "
                    f"each pattern's own stored {coord}, and the subset's starting "
                    "structures store it differently, so a function of the DOF "
                    f"would not be a function of the coordinate; start every "
                    f"pattern at one {coord}")

    def _refuse_size_across_wavelengths(self, r: ResolvedParametric) -> None:
        """A size coefficient is not one number across wavelengths (WP-1131).

        It is (180/π)·K·λ/L, so a shared size column carries the factor
        λ_h/λ_0 into each histogram (:func:`size_value_scales`).  A parametric
        target is per-histogram, so no factor reaches it, and Σ_j Φ_kj·c_j
        would state one number of *degrees* in every pattern: a different
        specimen size at each wavelength.  Refused where the subset's
        wavelengths differ; where a source declares no line there is no λ to
        normalise by, which is :func:`size_value_scales`' own empty case.
        """
        parts = r.target.split(".")
        if len(parts) != 3 or parts[0] != "phases" or parts[2] not in SIZE_LAMBDA_POWER:
            return
        lams = {h: _longest_wavelength(self.instruments[h]) for h in r.patterns}
        if any(lam is None for lam in lams.values()) or len(set(lams.values())) < 2:
            return
        shown = ", ".join(f"{lam:g}" for lam in sorted(set(lams.values())))
        raise ValueError(
            f"parametric equation {r.name!r}: {r.target} is a crystallite-size "
            f"coefficient, (180/π)·K·λ/L, and the subset's patterns are at "
            f"different wavelengths ({shown} Å), so one function of the "
            "coordinates would state one number of degrees at every λ — a "
            "different size in each pattern (WP-1131). Give the declaration a "
            "subset at one wavelength (patterns=…), or leave the size shared, "
            "which converts it per histogram")

    def parametric_targets(self, h: int) -> set[str]:
        """The bare paths histogram ``h``'s parametric equations drive (WP-1325)."""
        return {r.target for r in self.parametric if h in r.patterns}

    def _parametric_reached(self, path_globs: list[str]) -> set[str]:
        """The coefficient paths of every declaration a glob reaches.

        A glob reaches a declaration when it matches the target in a subset
        histogram, bare or scoped (``hist.{h}.<target>``), under
        :meth:`set_vary`'s matching rule.  The target is a tied row, so the
        glob alone would free nothing; its coefficients are what carry it.
        """
        out: set[str] = set()
        for r in self.parametric:
            names = {r.target, *(f"hist.{h}.{r.target}" for h in r.patterns)}
            if any(fnmatch.fnmatchcase(name, g) for name in names for g in path_globs):
                out.update(r.paths)
        return out

    def _check_moment_frames_shared(self) -> None:
        """Refuse a shared moment DOF over a per-histogram cell or position.

        A moment's DOFs are read in a frame built from the cell angles and the
        atom's position (#598).  One shared column then states one moment only
        if every histogram builds the same frame; with a per-histogram cell
        each table would re-seed it from its own, the column would keep one
        histogram's value, and every other histogram would read a different
        moment at each stage start, silently (review of #615).  Per-histogram
        DOFs over a per-histogram cell are fine: each table re-seeds its own.
        """
        for base in self.tables[0].moment_frames():
            _, ip, _, j = base.split(".")
            frame_paths = [f"phases.{ip}.cell.{t}" for t in
                           ("a", "b", "c", "alpha", "beta", "gamma")]
            frame_paths += [f"{base}.{t}" for t in ("x", "y", "z")]
            dofs = [e.path for e in self.tables[0].entries
                    if e.path.startswith(f"{base}.moment.dof")]
            if (any(self.sharing.is_shared(d) for d in dofs)
                    and not all(self.sharing.is_shared(f) for f in frame_paths)):
                raise ValueError(
                    f"the moment of {base} is shared across histograms but its "
                    f"cell or position is per-histogram "
                    f"(SharingMap.per_histogram): a moment's DOFs are read in a "
                    f"frame built from the cell, so one shared DOF would mean a "
                    f"different moment in each histogram. Make the moment "
                    f"per-histogram too (per_histogram=['{base}.moment.*']) or "
                    f"share the cell.")

    @property
    def n_histograms(self) -> int:
        return len(self.tables)

    # -- vary control --------------------------------------------------
    def _canonical(self, h: int, path: str) -> str:
        """The scoped name of ``path`` in histogram ``h`` (bare if shared)."""
        return path if self.sharing.is_shared(path) else f"hist.{h}.{path}"

    def set_vary(self, path_globs: list[str], vary: bool) -> list[str]:
        """Free/fix by glob across every histogram; returns scoped hits.

        A glob matches an entry when it matches either the scoped canonical name
        or the bare path, so single-histogram plans keep working verbatim.

        A **shared** path is one column however many histograms carry it, so
        it is returned once, at its first histogram's place (WP-1312): every
        histogram's table holds its own copy of the entry and sets it, but the
        record is of what the joint fit freed, and one shared cell listed once
        per histogram claimed twice the parameters a two-histogram fit had.

        A glob reaching a **parametric target** (WP-1325) reaches its
        coefficients too, in every histogram, since they are shared columns
        every table carries: the target is a tied row a glob alone would skip,
        so a plan's ``phases.*.cell.*`` frees a parametric cell as it frees a
        plain one, and the returned list names the coefficients.
        """
        freed: list[str] = []
        seen: set[str] = set()
        coupled = self._parametric_reached(path_globs) if self.parametric else set()
        for h, table in enumerate(self.tables):
            matched = []
            for e in table.entries:
                if e.tie is not None or e.locked:
                    continue
                canon = self._canonical(h, e.path)
                if e.path in coupled or any(
                        fnmatch.fnmatchcase(canon, g)
                        or fnmatch.fnmatchcase(e.path, g) for g in path_globs):
                    matched.append(e.path)
            if matched:
                for p in table.set_vary(matched, vary):
                    canon = self._canonical(h, p)
                    if canon not in seen:
                        seen.add(canon)
                        freed.append(canon)
        self._rebuild_columns()
        return freed

    def blocked_by_hold(self, path_globs: list[str]) -> list[str]:
        """The held rows ``path_globs`` matched, scoped, sorted (WP-1435).

        ``StageResult.blocked_by_hold`` for a joint stage: the rows
        :meth:`set_vary` would have freed but for ``Entry.held``, under its
        matching rule (bare or scoped name), a shared row named once.  A
        joint fit has no hold verb, so every such row is a floating-origin
        hold its tables derive from the structure (WP-1912).
        """
        blocked: dict[str, None] = {}
        for h, table in enumerate(self.tables):
            for e in table.entries:
                if not e.held or e.tie is not None or e.locked:
                    continue
                canon = self._canonical(h, e.path)
                if any(fnmatch.fnmatchcase(canon, g)
                       or fnmatch.fnmatchcase(e.path, g) for g in path_globs):
                    blocked[canon] = None
        return sorted(blocked)

    def row_path(self, h: int, entry) -> str:
        """The name histogram ``h``'s ``entry`` goes by in the joint result.

        Bare when the entry is one column of the joint fit, ``hist.h.``-scoped
        when it is a row per histogram (:func:`row_shared`).  It differs from
        :meth:`_canonical` only for a tied row whose sources are per
        histogram, which ``_canonical`` names bare by its own path.
        """
        return entry.path if row_shared(self.sharing, entry) else f"hist.{h}.{entry.path}"

    def _names(self, h: int) -> set[str]:
        """Every name a glob can match in histogram ``h``: bare and scoped.

        The scoped names include :meth:`row_path`'s, so every path the joint
        result and ``MultiHistogramRefinement.parameters()`` print is a known
        one, and a literal copied from either is never ``STAGE_PATH_UNKNOWN``.
        """
        names: set[str] = set()
        for e in self.tables[h].entries:
            names.add(e.path)
            names.add(self._canonical(h, e.path))
            names.add(self.row_path(h, e))
        return names

    def known_paths(self) -> set[str]:
        """Every name a glob can match in any histogram: bare and scoped."""
        known: set[str] = set()
        for h in range(self.n_histograms):
            known |= self._names(h)
        return known

    def unknown_paths(self, path_globs: list[str]) -> list[str]:
        """The paths naming no entry in any histogram (WP-1414).

        :meth:`ParameterTable.unknown_paths` across the stack, under this
        table's matching rule: a literal is known when it is a bare path of
        some histogram or a scoped one (``hist.1.instrument.zero_shift``), so
        ``hist.7.…`` on a three-histogram fit is unknown however real its tail.
        """
        return unknown_paths_among(path_globs, self.known_paths())

    def unreached_histograms(self, path_globs: list[str]) -> dict[int, list[str]]:
        """Histograms a stage's globs reached elsewhere and not here (WP-1414).

        Maps each such histogram to the globs that did reach another one, in
        plan order.  Histogram ``h`` is unreached when no glob *addressing* it
        matched any of its rows, while one of those same globs matched a row
        of another histogram.  Issue #265's joint fit is the case:
        ``instrument.profile.*`` freed four rows on the one
        constant-wavelength histogram and none on any bank, and the result
        said ``converged``.

        Three things keep this silent where silence is right. **Matched, not
        freed**: a row that exists and is locked, tied or held was reached,
        and the reason it stayed is ``ParameterRow.held_because``'s to give —
        a capillary's force-fixed ``sample_displacement`` is not a miss. A
        glob **scoped** to another histogram does not address this one, so a
        plan that targets one histogram on purpose says nothing about the
        rest. And a glob that matched **nowhere** is the single-histogram
        case, silent for the reason :func:`~rietx.params.vector.is_literal_path`
        gives.

        Scoped means one of two spellings.  A ``hist.<seg>.`` prefix addresses
        the histograms ``<seg>`` admits, so ``hist.*.…`` still means every
        one.  Any other glob addresses every histogram if it matched a **bare**
        path anywhere, which is how a plan written for one histogram is
        spelled, and otherwise only the histograms whose scoped names it
        matched: ``*.1.instrument.zero_shift`` reaches histogram 1 by its
        scope and is aimed there, never a miss on histogram 0.

        What it cannot tell apart, and so reports: a component one histogram
        declares and another does not (a hump, a surface roughness) is
        reached on one side only by construction. That is a true statement
        about the stage, at ``info``.
        """
        n = self.n_histograms
        names = [self._names(h) for h in range(n)]
        bare = [{e.path for e in table.entries} for table in self.tables]
        globs = list(dict.fromkeys(path_globs))
        hit = {g: [any(fnmatch.fnmatchcase(p, g) for p in names[h])
                   for h in range(n)]
               for g in globs}
        written_bare = {g: any(fnmatch.fnmatchcase(p, g)
                               for h in range(n) for p in bare[h])
                        for g in globs}

        def addresses(g: str, h: int) -> bool:
            if g.startswith("hist."):
                return fnmatch.fnmatchcase(str(h), g.split(".", 2)[1])
            return written_bare[g] or hit[g][h]

        out: dict[int, list[str]] = {}
        for h in range(n):
            mine = [g for g in hit if addresses(g, h)]
            if any(hit[g][h] for g in mine):
                continue
            elsewhere = [g for g in mine
                         if any(hit[g][k] for k in range(n) if k != h)]
            if elsewhere:
                out[h] = elsewhere
        return out

    def seed_floored(self, scoped_paths: list[str], value: float) -> list[str]:
        """Lift free rows bounded below at 0 up to ``value`` (per histogram);
        see the single-histogram :meth:`ParameterTable.seed_floored`.

        A shared column is seeded in every histogram or in none.  Each
        histogram's box is its own (WP-1131), so a seed can fit under one
        histogram's upper bound and not another's; written in some, the
        histograms would disagree about one column and the last write would
        win ``x0``.
        """
        wants = []
        for h in range(len(self.tables)):
            want = [self._unscope(h, p) for p in scoped_paths
                    if self._owner(p) in (None, h)]
            wants.append([w for w in want if w is not None])
        declined = {p for h, table in enumerate(self.tables) for p in wants[h]
                    if self.sharing.is_shared(p)
                    and table._floor_seed_target(p, value) is None}
        seeded: list[str] = []
        for h, table in enumerate(self.tables):
            want = [p for p in wants[h] if p not in declined]
            for p in table.seed_floored(want, value):
                # once per shared column, as :meth:`set_vary` returns it
                if self._canonical(h, p) not in seeded:
                    seeded.append(self._canonical(h, p))
        if seeded:
            self._rebuild_columns()
        return seeded

    # -- combined column layout ----------------------------------------
    def _rebuild_columns(self) -> None:
        """Recompute the shared/per-histogram combined column layout.

        Shared free columns come first (in histogram 0's order, and asserted
        identical across histograms — same structure copy, same globs), then
        each histogram's per-histogram free columns in turn.  ``_col_map[h][c]``
        is the combined index of histogram ``h``'s c-th free column.
        """
        shared_order: list[str] = []
        shared_seen: set[str] = set()
        per_hist_paths: list[list[str]] = [[] for _ in self.tables]
        shared_sets: list[set[str]] = []
        for h, table in enumerate(self.tables):
            sset: set[str] = set()
            for p in table.free_paths:
                if self.sharing.is_shared(p):
                    sset.add(p)
                    if p not in shared_seen:
                        shared_seen.add(p)
                        shared_order.append(p)
                else:
                    per_hist_paths[h].append(p)
            shared_sets.append(sset)
        for h, sset in enumerate(shared_sets):
            if sset != shared_seen:
                missing = sorted(shared_seen - sset)
                extra = sorted(sset - shared_seen)
                raise ValueError(
                    f"histogram {h} disagrees on the shared free set "
                    f"(missing {missing[:3]}, extra {extra[:3]}); shared "
                    "parameters must be freed identically in every histogram")
        if self._column_anchor:
            # a parametric coefficient takes the column its target would have
            # had (WP-1325): the order is then the one a plain shared target
            # gives, which is what makes a ``constant`` declaration the same
            # solve as ``refine_multi`` bit for bit (a permuted normal matrix
            # is factorised in another order).  Every other column keeps
            # histogram 0's entry order, which is the order above.
            pos = {e.path: i for i, e in enumerate(self.tables[0].entries)}
            shared_order.sort(key=lambda p: (pos[self._column_anchor.get(p, (p, 0))[0]],
                                             self._column_anchor.get(p, (p, 0))[1]))

        shared_index = {p: k for k, p in enumerate(shared_order)}
        combined_paths = list(shared_order)
        per_hist_index: list[dict[str, int]] = [{} for _ in self.tables]
        for h in range(len(self.tables)):
            for p in per_hist_paths[h]:
                per_hist_index[h][p] = len(combined_paths)
                combined_paths.append(f"hist.{h}.{p}")

        n = len(combined_paths)
        col_map: list[np.ndarray] = []
        x0 = np.zeros(n, dtype=np.float64)
        lo = np.full(n, -np.inf, dtype=np.float64)
        hi = np.full(n, np.inf, dtype=np.float64)
        for h, table in enumerate(self.tables):
            free = table.free_paths
            idx = np.array(
                [shared_index[p] if self.sharing.is_shared(p) else per_hist_index[h][p]
                 for p in free], dtype=np.int64)
            col_map.append(idx)
            xh = table.x0()
            loh, hih = table.bounds()
            # shared columns get identical values from each histogram (harmless
            # overwrite); per-histogram columns are written once.
            x0[idx] = xh
            # bounds are **intersected**, not overwritten.  A shared column has
            # to satisfy every histogram's bound, and since WP-1131 the
            # histograms can genuinely disagree about one: a size cap is a
            # physical limit on each histogram's own coefficient, which the
            # value scale divides by a different factor per histogram.  Identity
            # wherever they agree — which is every bound the three per-stage
            # freezes set, since each is made to agree deliberately — so this is
            # bit-identical on every joint fit that predates the scaling.
            lo[idx] = np.maximum(lo[idx], loh)
            hi[idx] = np.minimum(hi[idx], hih)

        # The wavelength count, made where the whole set is visible.  A
        # wavelength is per-histogram under the default sharing rule (it starts
        # with ``instrument.``), so the scoped ``hist.h.…`` name is what a user
        # reads and what the refusal must name — the check tests the *unscoped*
        # tail and reports the scoped path.  Asked after every column rebuild
        # rather than only at construction, because a staged plan frees its
        # globs one stage at a time and every :meth:`set_vary` ends here.
        n_wavelengths = sum(1 for t in self.tables for e in t.entries
                            if _is_wavelength(e.path))
        # ``SharingMap`` decides sharing per *path*, not per (path, histogram),
        # so "the cell is shared with a held-λ histogram" collapses to "the cell
        # is shared at all" — which is the strongest form this map can express,
        # and it is the right one: with a per-histogram cell *every* histogram
        # has its own, so no free λ has anything to be measured against.
        cell_shared = all(
            self.sharing.is_shared(e.path) for t in self.tables
            for e in t.entries if ".cell." in e.path)
        check_wavelength_freedom(
            [p for p in combined_paths if _is_wavelength(_unscoped(p))],
            n_wavelengths, len(self.tables), cell_shared=cell_shared)

        self.shared_paths = shared_order
        self.per_hist_paths = per_hist_paths
        self._combined_paths = combined_paths
        self._col_map = col_map
        self._x0 = x0
        self._lo = lo
        self._hi = hi
        self.n_shared = len(shared_order)

    def refresh_bounds(self) -> None:
        """Re-read the sub-tables' bounds after a per-stage freeze changed them.

        The constructor's "harmless overwrite" of a shared column holds only
        while every histogram reports the same bound for it, so a caller that
        freezes cell windows must freeze the **same** set on every sub-table —
        see ``optimize.least_squares._freeze_cell_windows_multi``, which decides
        a phase is invisible only when it is invisible in all of them.
        """
        self._lo.fill(-np.inf)
        self._hi.fill(np.inf)
        for h, table in enumerate(self.tables):
            loh, hih = table.bounds()
            idx = self._col_map[h]
            self._lo[idx] = np.maximum(self._lo[idx], loh)
            self._hi[idx] = np.minimum(self._hi[idx], hih)

    # -- optimiser interface -------------------------------------------
    @property
    def free_paths(self) -> list[str]:
        return list(self._combined_paths)

    def x0(self) -> np.ndarray:
        return self._x0.copy()

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        return self._lo.copy(), self._hi.copy()

    def col_map(self, h: int) -> np.ndarray:
        return self._col_map[h]

    def split(self, theta: np.ndarray) -> list[np.ndarray]:
        """Gather the per-histogram internal free vectors from combined θ."""
        return [theta[self._col_map[h]] for h in range(len(self.tables))]

    def decode(self, theta: np.ndarray) -> list[dict[str, float]]:
        thetas = self.split(theta)
        return [self.tables[h].decode(thetas[h]) for h in range(len(self.tables))]

    def free_values(self, theta: np.ndarray) -> list[float]:
        """Physical values of :attr:`free_paths` at ``theta``, in that order.

        :meth:`ParameterTable.free_values` across the stack (WP-1341).  Each
        combined path is read from the histogram that owns it, and a shared
        one from histogram 0, whose value scale is 1 (WP-1131), which is
        where the joint result reads a shared row's value too.
        """
        decoded = self.decode(np.asarray(theta, dtype=np.float64))
        out = []
        for p in self.free_paths:
            h = self._owner(p) or 0
            out.append(float(decoded[h][self._unscope(h, p)]))
        return out

    def commit(self, theta: np.ndarray) -> np.ndarray | None:
        """Each histogram's table commits its slice; the re-charting
        (``ParameterTable.commit``: moment signs, #604, or a body's composed
        rotation, WP-1805) comes back on the combined columns.  A shared
        column is committed from one value by every table that holds it, and
        the chart is a function of the value, so the tables agree on it.  The
        combined form is the widest any table returned: a vector of signs, or
        the square matrix once one table's is.

        One commit, not one per histogram: a table that refuses (a rigid body
        failing the commit-time guard, #801) puts back every table, so the
        histograms never disagree on a shared column, and the error goes on."""
        thetas = self.split(theta)
        before = [table._commit_state() for table in self.tables]
        try:
            parts = [(h, chart) for h, table in enumerate(self.tables)
                     if (chart := table.commit(thetas[h])) is not None]
        except ValueError:
            for table, state in zip(self.tables, before, strict=True):
                table._restore_commit_state(state)
            raise
        if not parts:
            return None
        if all(np.ndim(chart) == 1 for _, chart in parts):
            combined = np.ones(len(theta), dtype=np.float64)
            for h, chart in parts:
                combined[self._col_map[h]] = chart
            return combined
        combined = np.eye(len(theta))
        for h, chart in parts:
            cols = self._col_map[h]
            combined[np.ix_(cols, cols)] = (np.diag(chart) if np.ndim(chart) == 1
                                            else chart)
        return combined

    def apply_to_models(self) -> None:
        for h, table in enumerate(self.tables):
            table.apply_to_models(self.structures[h], self.instruments[h])

    def reframe_moments(self) -> list[str]:
        """:meth:`ParameterTable.reframe_moments` per histogram, at a stage start.

        Each table against its own structure copy, which holds the cell the
        last :meth:`apply_to_models` wrote; a shared cell is one value in every
        copy, so a shared moment DOF is re-seeded to one value in every table
        and the column map stays a map of equal entries (#598).  Returns the
        scoped atom paths reframed.
        """
        moved = [f"hist.{h}.{base}"
                 for h, (table, structure) in enumerate(
                     zip(self.tables, self.structures, strict=True))
                 for base in table.reframe_moments(structure)]
        if moved:
            self._rebuild_columns()
        return moved

    def push_moment_frames(self, models) -> None:
        """:meth:`ParameterTable.push_moment_frames`, histogram by histogram."""
        for table, model in zip(self.tables, models, strict=True):
            table.push_moment_frames(model)

    # -- helpers used by esd assembly ----------------------------------
    def _owner(self, scoped: str) -> int | None:
        """Histogram index of a scoped per-histogram path, or None if shared."""
        if scoped.startswith("hist."):
            return int(scoped.split(".", 2)[1])
        return None

    def _unscope(self, h: int, scoped: str) -> str | None:
        """Bare path of ``scoped`` as seen by histogram ``h`` (None if it
        belongs to another histogram)."""
        owner = self._owner(scoped)
        if owner is None:
            return scoped
        if owner != h:
            return None
        return scoped.split(".", 2)[2]
