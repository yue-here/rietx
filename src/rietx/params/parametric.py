"""Resolving a parametric declaration against its patterns (WP-1325).

:class:`~rietx.schemas.parametric.ParametricEquation` is the declaration;
:func:`resolve_parametric` is the **one authority** that turns it into numbers:
the subset, the design matrix Φ over it, the term labels, and the declaration
with its reference and scale filled in.  Every refusal that can be made from
the declaration and the coordinates alone is made here, before any table is
built or any solve runs; the ones that need a table (the target exists, is not
tied, locked or held) are made by
:class:`~rietx.params.multi.MultiParameterTable`, which owns the tables.

**Why linear, and why it costs no derivative branch.**  The tie machinery is
affine, p = C·θ + d with constant C (WP-0301, WP-1070).  p_k = Σ_j Φ_kj·c_j is
exactly one affine tie per pattern with C_k = Φ_k, so ``_column_extras`` reads
the reach off C and the whole-model FD column covers what a branch does not
claim.  A coefficient inside a power or an exponential is ``Parameter.expr``'s
fence (WP-1119).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from scipy import linalg

from ..optimize import lapack
from ..optimize.blocked import added_columns_gain, held_projection
from ..optimize.statistics import PINV_RCOND
from ..schemas.interval import PARAMETER_INTERVAL_LEVEL
from ..schemas.parametric import (
    CoordinateTable,
    ParametricCoefficient,
    ParametricEquation,
    ParametricFormReading,
    ParametricFormTest,
    RefinedParametricEquation,
)

#: Below this, a pivoted-QR diagonal of the column-normalised Φ is a direction
#: the basis does not have (rank refusal).  **Derived from the covariance's own
#: cut, never tuned**: ``statistics.normal_factors`` hands an equilibrated
#: normal matrix to ``pinv`` with :data:`~rietx.optimize.statistics.PINV_RCOND`,
#: and an R diagonal r against a leading 1 is an eigenvalue r² of ΦᵀΦ, so a
#: basis direction under √rcond would be discarded by the covariance anyway —
#: a coefficient with no esd that the declaration asked to measure.  An exact
#: collinearity (a ternary's x_A + x_B + x_C = 1 beside an intercept) sits at
#: rounding, ~1e-16, eight decades below.
RANK_RTOL = math.sqrt(PINV_RCOND)

#: The confidence level of the form test (:func:`form_tests`): a declaration
#: is rejected when its statistic passes the χ² point at this level for its
#: degrees of freedom.  ``schemas.interval.PARAMETER_INTERVAL_LEVEL``'s value,
#: as the stationary-angle test's is (WP-1929).  Each declaration is tested on
#: its own, so a fit with several sees a false rejection more often than one
#: in twenty.
FORM_TEST_LEVEL = PARAMETER_INTERVAL_LEVEL


@dataclass
class ResolvedParametric:
    """A declaration resolved against its patterns: what the table wires.

    ``equation`` is the declaration with its reference and scale filled in (a
    ``polynomial``'s; the other bases use none), the form to pass back for a
    refit.  ``phi`` is Φ over ``patterns``, row k for ``patterns[k]``;
    ``divisors[j]`` the product of term j's coordinate scales, which turns a
    coefficient in table units into one per unit of the coordinates.
    ``unit`` is the target's, and ``span`` each polynomial coordinate's lowest
    and highest value across the subset.
    """

    equation: ParametricEquation
    patterns: list[int]
    phi: np.ndarray
    labels: list[str]
    divisors: np.ndarray
    units: list[str | None]
    unit: str | None = None
    span: dict[str, tuple[float, float]] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.equation.name

    @property
    def target(self) -> str:
        return self.equation.target

    @property
    def paths(self) -> list[str]:
        return self.equation.coefficient_paths()


def term_label(term: list[str]) -> str:
    """``"1"`` for the intercept, else the monomial: ``"T"``, ``"x*y"``, ``"T^2"``.

    A repeated coordinate is a power, and powers are collected in order of
    first appearance, so ``["x", "y", "x"]`` is ``"x^2*y"``.
    """
    if not term:
        return "1"
    counts = Counter(term)
    return "*".join(name if n == 1 else f"{name}^{n}"
                    for name, n in dict.fromkeys((t, counts[t]) for t in term))


def _term_unit(target_unit: str | None, term: list[str],
               coordinate_units: dict[str, str]) -> str | None:
    """The target's unit over the term's coordinate units.

    ``None`` unless every factor's unit is recorded: a target with no unit, or
    a coordinate the table gives none, would otherwise print a unit that
    claims a dimension nobody declared (``1/K`` for a slope in Å/K).
    """
    if target_unit is None:
        return None
    counts = Counter(term)
    below = []
    for t in dict.fromkeys(term):
        u = coordinate_units.get(t)
        if not u:
            return None
        below.append(u if counts[t] == 1 else f"{u}^{counts[t]}")
    if not below:
        return target_unit
    return (f"{target_unit}/{below[0]}" if len(below) == 1
            else f"{target_unit}/({'*'.join(below)})")


def resolve_parametric(equation: ParametricEquation, coordinates: CoordinateTable | None,
                       n_patterns: int, *, target_unit: str | None = None
                       ) -> ResolvedParametric:
    """Resolve ``equation`` against ``n_patterns`` patterns and their ``coordinates``.

    The reference and scale a polynomial leaves out are filled **once**, from
    the subset's values (mid-range, half-range), and returned in the resolved
    declaration: a refit passing it back reproduces Φ exactly, and a pattern
    that joins later never redefines a coefficient.

    Refusals, each a ``ValueError`` naming its fix: a subset index out of
    range; a polynomial with no coordinate table, a table of the wrong length,
    a term naming a column the table lacks, a subset pattern with no value
    for a coordinate it needs, a coordinate taking one value across the
    subset with no scale given; design rows not matching the subset; fewer
    patterns in the subset than coefficients; and a Φ whose rank is below its
    column count (pivoted QR on the centred, scaled columns, naming the
    collinear terms, and the Scheffé fix when the coordinates used sum to a
    constant).
    """
    name = equation.name
    if coordinates is not None and coordinates.n_patterns != n_patterns:
        raise ValueError(
            f"the coordinate table has {coordinates.n_patterns} rows for "
            f"{n_patterns} patterns: one row per pattern, in the order passed")
    patterns = list(range(n_patterns)) if equation.patterns is None else list(equation.patterns)
    bad = [k for k in patterns if k >= n_patterns]
    if bad:
        raise ValueError(
            f"parametric equation {name!r}: pattern index {bad[0]} is out of range for "
            f"{n_patterns} patterns (indices 0…{n_patterns - 1})")
    n_sub = len(patterns)
    resolved = equation
    divisors: list[float]
    units: list[str | None]
    if equation.basis == "constant":
        phi = np.ones((n_sub, 1), dtype=np.float64)
        labels = ["1"]
        divisors = [1.0]
        units = [target_unit]
        raw: dict[str, np.ndarray] = {}
    elif equation.basis == "design":
        phi = np.asarray(equation.design, dtype=np.float64)
        if phi.shape[0] != n_sub:
            raise ValueError(
                f"parametric equation {name!r}: {phi.shape[0]} design rows for a "
                f"subset of {n_sub} patterns: one row per pattern, in subset order")
        labels = [f"d{j}" for j in range(phi.shape[1])]
        divisors = [1.0] * phi.shape[1]
        # a design column is the caller's, in units only the caller knows
        units = [None] * phi.shape[1]
        raw = {}
    else:
        if coordinates is None:
            raise ValueError(
                f"parametric equation {name!r} is a polynomial over "
                f"{equation.coordinates_used()}, which needs a CoordinateTable "
                "(coordinates=…) giving each pattern's values")
        used = equation.coordinates_used()
        missing = [c for c in used if c not in coordinates.columns]
        if missing:
            raise ValueError(
                f"parametric equation {name!r} uses coordinate(s) {missing} the "
                f"table does not have (it has {sorted(coordinates.columns)})")
        raw = {}
        for c in used:
            column = coordinates.columns[c]
            holes = [k for k in patterns if column[k] is None]
            if holes:
                raise ValueError(
                    f"parametric equation {name!r}: pattern {holes[0]} has no value for "
                    f"coordinate {c!r}, which a term uses; give it one, or leave "
                    "the pattern out of the subset (patterns=…)")
            raw[c] = np.array([column[k] for k in patterns], dtype=np.float64)
        reference = dict(equation.reference or {})
        scale = dict(equation.scale or {})
        _refuse_centred_mixture(equation, used, raw, reference, scale)
        for c in used:
            lo, hi = float(raw[c].min()), float(raw[c].max())
            if c not in reference:
                reference[c] = 0.5 * (lo + hi)
            if c not in scale:
                half = 0.5 * (hi - lo)
                if not half > 0.0:
                    raise ValueError(
                        f"parametric equation {name!r}: coordinate {c!r} takes one value "
                        f"({lo:g}) across the subset, so a term in it is the "
                        "intercept again and it has no range to scale by; drop "
                        "the term, or give scale= if the subset will grow")
                scale[c] = half
        resolved = equation.model_copy(update={"reference": reference, "scale": scale})
        u = {c: (raw[c] - reference[c]) / scale[c] for c in used}
        phi = np.ones((n_sub, len(equation.terms or [])), dtype=np.float64)
        for j, term in enumerate(equation.terms or []):
            for c in term:
                phi[:, j] *= u[c]
        labels = [term_label(t) for t in equation.terms or []]
        divisors = [math.prod(scale[c] for c in t) for t in equation.terms or []]
        units = [_term_unit(target_unit, t, coordinates.units) for t in equation.terms or []]
    m = phi.shape[1]
    if n_sub < m:
        raise ValueError(
            f"parametric equation {name!r} has {m} coefficients ({', '.join(labels)}) "
            f"and its subset {n_sub} pattern{'' if n_sub == 1 else 's'}: a "
            "coefficient needs a pattern to measure it. Drop terms or widen the subset")
    _refuse_rank_deficient(name, phi, labels, raw, equation)
    return ResolvedParametric(equation=resolved, patterns=patterns, phi=phi, labels=labels,
                              divisors=np.asarray(divisors, dtype=np.float64),
                              units=units, unit=target_unit,
                              span={c: (float(v.min()), float(v.max()))
                                    for c, v in raw.items()})


def _refuse_centred_mixture(equation: ParametricEquation, used: list[str],
                            raw: dict[str, np.ndarray], reference: dict[str, float],
                            scale: dict[str, float]) -> None:
    """Refuse default centring of mixture fractions in a basis with no intercept.

    Fractions that sum to a constant span the intercept themselves, so a
    no-intercept basis over them is full rank either way. But centred at
    their own mid-ranges, the coefficients stop being the pure components'
    values (Scheffé's reading) and become combinations of them, with nothing
    to say so. Either reading is a choice, so the caller states the reference
    and scale; the default is never applied silently here.
    """
    if any(not t for t in equation.terms or []) or len(used) < 2:
        return
    total = sum(raw.values())
    if np.ptp(total) > 1e-9 * max(1.0, float(np.max(np.abs(total)))):
        return
    missing = [c for c in used if c not in reference or c not in scale]
    if not missing:
        return
    names = sorted(used)
    raise ValueError(
        f"parametric equation {equation.name!r}: the coordinates {names} sum to a constant "
        "across the subset (mixture fractions), and centring them at their "
        "mid-ranges would make each coefficient a combination of pure-component "
        "values. State the reading: reference="
        f"{{{', '.join(f'{c!r}: 0.0' for c in names)}}} and scale="
        f"{{{', '.join(f'{c!r}: 1.0' for c in names)}}} for the Scheffé form "
        "(each coefficient a pure component's value), or give the reference and "
        "scale you mean")


def _refuse_rank_deficient(name: str, phi: np.ndarray, labels: list[str],
                           raw: dict[str, np.ndarray], equation: ParametricEquation) -> None:
    """Refuse a Φ whose columns are collinear across the subset, naming them.

    Pivoted QR on the column-normalised Φ (a polynomial's columns are already
    centred and scaled; a design's are only normalised, centring being the
    caller's to choose).  The trailing pivots past the rank are the dependent
    terms; each is named with the leading terms it is a combination of.
    """
    norms = np.linalg.norm(phi, axis=0)
    zero = [labels[j] for j in np.flatnonzero(norms == 0.0)]
    if zero:
        raise ValueError(
            f"parametric equation {name!r}: term(s) {zero} are zero in every pattern of "
            "the subset, so no pattern can measure them; drop them")
    q = phi / norms
    _, r, piv = linalg.qr(q, mode="economic", pivoting=True)
    diag = np.abs(np.diag(r))
    rank = int(np.sum(diag > RANK_RTOL * diag[0]))
    if rank == phi.shape[1]:
        return
    keep, dep = list(piv[:rank]), list(piv[rank:])
    coef, *_ = lapack.lstsq(q[:, keep], q[:, dep], rcond=None)
    parts = []
    for i, j in enumerate(dep):
        with_ = [labels[keep[k]] for k in np.flatnonzero(np.abs(coef[:, i]) > 1e-8)]
        parts.append(f"{labels[j]} is a combination of {with_}")
    fix = "drop one of each collinear set, or widen the subset"
    if raw:
        # mixture fractions: with an intercept, the intercept is their sum;
        # without one, centring each at its own mid-range makes the centred
        # columns sum to a constant too, so the Scheffé form is uncentred
        total = sum(raw.values())
        if np.ptp(total) <= 1e-9 * max(1.0, float(np.max(np.abs(total)))):
            names = sorted(raw)
            uncentred = (f"reference={{{', '.join(f'{c!r}: 0.0' for c in names)}}} "
                         f"and scale={{{', '.join(f'{c!r}: 1.0' for c in names)}}}")
            fix = (f"the coordinates {names} sum to a constant across the subset, "
                   + ("so the intercept is their sum: use the Scheffé form — drop "
                      "the intercept and pass " if "1" in labels else
                      "so centred at their mid-ranges they are dependent: a "
                      "mixture (Scheffé) basis is uncentred — pass ")
                   + f"{uncentred}, so each coefficient is a pure component's value")
    raise ValueError(
        f"parametric equation {name!r}: its basis has rank {rank} for {phi.shape[1]} "
        f"terms over the subset ({'; '.join(parts)}), so the coefficients are "
        f"not separately measurable: {fix}")


def least_squares_start(resolved: ResolvedParametric, values: np.ndarray) -> np.ndarray:
    """The coefficients whose Φ·c is closest to the subset's starting values.

    A subset that starts at one value is represented **exactly** where the
    basis can: the intercept takes it and every other term zero, so a
    ``constant`` declaration starts from bit-for-bit the number a plain shared
    parameter would, which the equivalence with ``refine_multi`` rests on.
    """
    values = np.asarray(values, dtype=np.float64)
    m = resolved.phi.shape[1]
    if np.all(values == values[0]) and "1" in resolved.labels:
        c = np.zeros(m, dtype=np.float64)
        c[resolved.labels.index("1")] = values[0]
        return c
    c, *_ = lapack.lstsq(resolved.phi, values, rcond=None)
    return c


def coefficient_rows(resolved: ResolvedParametric, values: dict[str, float],
                     esds: dict[str, float], vary: dict[str, bool]
                     ) -> list[ParametricCoefficient]:
    """One :class:`ParametricCoefficient` per coefficient, in user units.

    ``values``/``esds``/``vary`` are keyed by the coefficients' paths, in the
    table's (centred, scaled) units; each is divided by its term's scale
    product, so the reported number is per unit of the coordinates at the
    reference.  A path absent from ``esds`` is reported ``None``: the
    covariance marked it unmeasured (``ParameterTable.stderr_physical`` omits a
    row drawing on a gradient-free column) or it was never free.
    """
    out = []
    ref = (dict(resolved.equation.reference)
           if resolved.equation.basis == "polynomial" and resolved.equation.reference else None)
    for j, path in enumerate(resolved.paths):
        d = float(resolved.divisors[j])
        esd = esds.get(path) if vary.get(path, False) else None
        out.append(ParametricCoefficient(
            equation=resolved.name, target=resolved.target, term=resolved.labels[j],
            path=path, value=float(values[path]) / d,
            esd=None if esd is None else float(esd) / d,
            vary=bool(vary.get(path, False)), unit=resolved.units[j], reference=ref))
    return out


def parametric_equation(resolved: ResolvedParametric, rows: list[ParametricCoefficient],
                        columns: list[int | None], correlation: np.ndarray | None
                        ) -> RefinedParametricEquation:
    """One declaration as resolved, with its coefficients' covariance.

    ``rows`` are the declaration's :func:`coefficient_rows`, ``columns`` each
    coefficient's index in the joint θ (``None`` where it was not free) and
    ``correlation`` the solve's correlation over θ, which the esds were read
    off with (``ParameterTable._cov_free``).  Each entry is esd_i·esd_j·ρ_ij
    with ρ_ii taken as 1, so the diagonal is each row's ``esd`` squared bit
    for bit, and the correlation carries no unit, so the block is in the
    rows' units already.  ``None`` when a coefficient has no esd, or when a
    equation of several coefficients has no correlation to pair them with.
    """
    esd = [r.esd for r in rows]
    covariance = None
    if all(e is not None for e in esd) and all(c is not None for c in columns):
        m = len(rows)
        if m == 1:
            covariance = [[esd[0] * esd[0]]]
        elif correlation is not None:
            # ρ read off one triangle: the solve's correlation can differ from its
            # transpose in the last bit (measured on Linux, Python 3.14), and a
            # covariance must be symmetric to the bit
            covariance = [[esd[i] * esd[j] * (
                1.0 if i == j else
                float(correlation[columns[min(i, j)], columns[max(i, j)]]))
                for j in range(m)] for i in range(m)]
    return RefinedParametricEquation(equation=resolved.equation, unit=resolved.unit,
                                     span=dict(resolved.span), covariance=covariance)


def target_columns(resolved: ResolvedParametric, bj, free_paths: list[str],
                   skip: frozenset[int] = frozenset()) -> list[np.ndarray | None] | None:
    """Each subset pattern's own column for the target, read off the tie's.

    In pattern k the coefficient columns are Φ_kj·∂r_k/∂p_k, the target's
    column times its row of Φ, so J_coef·Φ_kᵀ/‖Φ_k‖² is ∂r_k/∂p_k itself,
    up to a factor constant in k (a value scale).  No residual is evaluated.
    ``bj`` is the solve's :class:`~rietx.optimize.blocked.BlockJacobian`;
    the result is one entry per block, a column over that block's rows or
    ``None`` outside the subset, in ``skip``, and where Φ_k or the column is
    zero, so a gradient-free pattern is not counted as tested.  ``skip``
    is the patterns where an untied fit would hold the target, because the
    pattern cannot see it (WP-1301).  ``None`` altogether when a coefficient
    is not free, so its column is not in ``bj``.
    """
    index = {p: i for i, p in enumerate(free_paths)}
    cols = [index.get(p) for p in resolved.paths]
    if any(c is None for c in cols):
        return None
    out: list[np.ndarray | None] = [None] * bj.n_blocks
    for row, k in zip(resolved.phi, resolved.patterns, strict=True):
        norm = float(row @ row)
        if norm == 0.0 or k in skip:
            continue
        local = {int(c): i for i, c in enumerate(bj.col_maps[k])}
        col = bj.blocks[k][:, [local[c] for c in cols]] @ (row / norm)
        if np.any(col):
            out[k] = col[:, None]
    return out


def form_tests(resolved: list[ResolvedParametric], bj, resid: np.ndarray, n_data: int,
               free_paths: list[str], skip: dict[str, frozenset[int]], hold
               ) -> tuple[list[ParametricFormTest], ParametricFormReading | None]:
    """Each declaration's lack-of-fit test at the answer (WP-1325).

    A score test, read off the answer alone.  The alternative frees the
    target in each subset pattern (:func:`target_columns`, without ``skip``'s
    patterns) in place of the declaration's coefficients, and
    :func:`~rietx.optimize.blocked.added_columns_gain` says how much χ² one
    linear step toward it removes, every other column refitted.  Columns in
    ``hold`` (θ's indices) leave both sides, as a refit keeps a column on its
    bound.  The gain over χ²_red of the data rows of ``resid`` is ~χ²_k
    while the form holds, k the directions the alternative adds.  The
    denominator is the answer's own, the restricted estimate the textbook
    score test takes (Rao, C. R., 1948, *Proc. Camb. Phil. Soc.* **44**, 50).
    An earlier cut also divided by the Bérar-Lelann factor f², as an esd is
    inflated.  On equations that must hold any smooth truth, over three real
    ramps (f 1.2-3.6), none of 261 readings rejected with it and 12 of 242
    (5.0 %) without it (``docs/wp/1325-parametric-series.md`` § Measured: the
    form test out of sample).

    Measured on the ZrMo₂O₈ ramp (33 patterns), the gain was 0.98-1.04 of the
    χ² a full untied refit removed for the strong phase's equations and for all
    three equations together.  It was 0.89 and 1.36 for the weak phase's two, whose
    refits stop in different minima.  The verdict matched the refit's on all
    five equations.  It costs one Jacobian, 0.7-0.8 s against the refit's 41 s
    (``docs/wp/1325-measure/form_score.py``).  Its power is where, and as
    well as, a pattern measures the target: on synthetic ramps whose minor
    phase fades out or overlaps, a bent truth was rejected in 0 of 20 seeds,
    as by a full refit (``form_synthetic.py``).

    With two or more equations tested, each is read again with every other tested
    equation's targets freed (``ParametricFormTest.others_freed``), the gain with
    all swapped less the gain with the others swapped.  That reading is the
    equation's verdict, since it assumes nothing of the other equations' forms; the tied
    one assumes them right.  At the ZrMo₂O₈ ramp's three-equation answer the cubic
    line's freed gain was 575.3 against the 576.1 its own refit removed
    (``form_freed.py``).  Freed, two equations whose targets move the
    pattern alike can absorb each other's misfit and both pass.  So the gain
    with every equation swapped is read too, one joint reading for the fit, which
    names no equation because the data cannot say which is wrong.  A regression
    tests a term added last beside the overall test of the group the same way.

    Returns the tests in declaration order and the joint reading, ``None``
    unless two or more equations were tested.
    """
    rd = resid[:n_data]
    scale = float(rd @ rd) / max(n_data - len(free_paths), 1)    # χ²_red
    index = {p: i for i, p in enumerate(free_paths)}
    # the held side is one projection for every alternative tested here
    null = None
    readings: list[ParametricFormReading | None] = []
    swaps: list[tuple[list[np.ndarray | None], list[int]] | None] = []
    gains: dict[int, tuple[float, int]] = {}
    counts = []
    for i, r in enumerate(resolved):
        cols = target_columns(r, bj, free_paths, skip.get(r.name, frozenset()))
        counts.append(0 if cols is None else sum(c is not None for c in cols))
        if cols is None:
            readings.append(None)
            swaps.append(None)
            continue
        if null is None:
            null = held_projection(bj, resid, hold)
        drop = [index[p] for p in r.paths]
        swaps.append((cols, drop))
        gains[i] = added_columns_gain(bj, resid, cols, drop, hold, null=null)
        readings.append(_reading(*gains[i], scale))
    # each equation again with every other tested equation's targets freed: the gain
    # with all of them swapped, less the gain with only the others swapped
    freed: list[ParametricFormReading | None] = [None] * len(resolved)
    joint = None
    live = [i for i, s in enumerate(swaps) if s is not None]
    if len(live) >= 2:
        every = added_columns_gain(bj, resid, *_stacked(swaps, live, bj.n_blocks),
                                   hold, null=null)
        joint = _reading(*every, scale)
        for i in live:
            others = [k for k in live if k != i]
            # one other equation swapped alone is that equation's tied alternative,
            # already projected above
            rest = (gains[others[0]] if len(others) == 1 else
                    added_columns_gain(bj, resid, *_stacked(swaps, others, bj.n_blocks),
                                       hold, null=null))
            freed[i] = _reading(every[0] - rest[0], every[1] - rest[1], scale)
    # the verdict assumes nothing of the other equations: freed where there are
    # others, and with none the two readings are one test
    verdicts = [None if v is None else v.rejected
                for v in (o if o is not None else t for t, o in zip(readings, freed,
                                                                    strict=True))]
    rejected = [r.name for r, v in zip(resolved, verdicts, strict=True) if v]
    out = [ParametricFormTest(
        equation=r.name, target=r.target, n_patterns=n_patterns, n_subset=len(r.patterns),
        rejected=verdict, tied=tied, others_freed=other,
        # a rejected equation's misfit has moved the answer every reading steps from
        provisional_on=[] if tied is None else [n for n in rejected if n != r.name])
        for r, n_patterns, tied, other, verdict in zip(resolved, counts, readings, freed,
                                                       verdicts, strict=True)]
    return out, joint


def _stacked(swaps, which: list[int], n_blocks: int
             ) -> tuple[list[np.ndarray | None], list[int]]:
    """The alternative that swaps every equation in ``which``: each block's target
    columns side by side, and every such equation's coefficients dropped."""
    extra: list[list[np.ndarray]] = [[] for _ in range(n_blocks)]
    drop: list[int] = []
    for i in which:
        cols, d = swaps[i]
        for h, c in enumerate(cols):
            if c is not None:
                extra[h].append(c)
        drop += d
    return [np.hstack(e) if e else None for e in extra], drop


def _reading(gain: float, dof: int, scale: float) -> ParametricFormReading:
    """One reading from an alternative's gain and directions.  Fewer directions
    than none is nothing to test, which the schema spells 0, and a gain a
    difference of projections puts a rounding below zero is none."""
    dof = max(int(dof), 0)
    statistic = cut = rejected = p_value = None
    if dof > 0 and np.isfinite(scale) and scale > 0.0:
        from scipy.stats import chi2

        statistic = max(float(gain), 0.0) / scale
        cut = float(chi2.ppf(FORM_TEST_LEVEL, dof))
        rejected = statistic > cut
        p_value = float(chi2.sf(statistic, dof))
    return ParametricFormReading(dof=dof, statistic=statistic, cut=cut,
                                 rejected=rejected, p_value=p_value)
