"""A parameter as a declared function of each pattern's coordinates (WP-1325).

A joint fit over many patterns (:func:`rietx.refine_multi`) can refine a
parameter as a function of where each pattern sits: a temperature down a ramp,
an (x, y) composition across a combinatorial library.  Pattern k's value of the
target is p_k = Σ_j Φ_kj · c_j, and the coefficients c_j are the refined
parameters, with esds from the joint covariance (Stinton & Evans, 2007,
*J. Appl. Cryst.* 40, 87, "parametric Rietveld refinement").

**Data, not code.**  Everything here is a pydantic model with a JSON
round-trip, so a self-driving lab can write one and a result can carry it:

* :class:`CoordinateTable` — one row per pattern, named columns with units,
  passed **beside** the patterns because several declarations share one table.
* :class:`ParametricEquation` — one target, a basis from a **closed** vocabulary
  (``constant``, ``polynomial`` over named coordinates, or an explicit
  ``design`` matrix, the escape hatch for splines, Scheffé mixture forms and
  sin²ψ), the pattern subset, and the reference point and scale per
  coordinate.  A form with a coefficient inside a power or an exponential is
  not linear in it, and is written as an ``expression`` (WP-1964): text in
  the grammar of :mod:`rietx.params.expression` over named variables, which
  ``refine_multi(variables=…)`` declares, and the coordinate columns.
* :class:`ParametricCoefficient` — one refined coefficient on
  :attr:`RefinementResult.parametric <rietx.schemas.results.RefinementResult.parametric>`,
  in the caller's units at the reference.
* :class:`ParametricFormTest` — one declaration's lack-of-fit test on
  :attr:`RefinementResult.parametric_form
  <rietx.schemas.results.RefinementResult.parametric_form>`.
* :class:`RefinedParametricEquation` — one declaration as resolved, with its
  coefficients' covariance, on :attr:`RefinementResult.parametric_equations
  <rietx.schemas.results.RefinementResult.parametric_equations>`; and
  :class:`ParametricValue`, the equation evaluated at a coordinate.

**The reference and scale are stored in the declaration** (patsy's lesson).  A
polynomial term is evaluated on u = (z − reference)/scale.  Left out, both are
computed **once**, when the declaration is resolved against a coordinate table
(``params.parametric.resolve_parametric``): the mid-range and half-range of the
subset's values.  The resolved declaration carries them, so a refit or a grown
campaign passing it back gets the same coefficients with the same meaning,
whatever patterns have joined.  Centring is what makes c₀ "the target at the
reference" rather than an extrapolation to z = 0, and it removes the
intercept-slope correlation an off-centre axis creates, which the normal
matrix's own equilibration (van der Sluis, 1969) does not.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import AliasChoices, Field, model_validator

from .common import Base

#: The closed basis vocabulary.  ``constant`` is one coefficient, the same in
#: every pattern of the subset (a shared parameter over a subset);
#: ``polynomial`` is a sum of monomials in named coordinates; ``design`` is a
#: caller's own matrix, one row per pattern of the subset; ``expression`` is
#: the caller's own text over named variables and coordinates (WP-1964), the
#: one basis that may be nonlinear in what it refines.
ParametricBasis = Literal["constant", "polynomial", "design", "expression"]

#: fnmatch's metacharacters: a target names one path, never a family
_GLOB_CHARS = frozenset("*?[")


def _finite(value: float, what: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{what} must be finite, got {value!r}")


class CoordinateTable(Base):
    """Each pattern's coordinates: named columns, one row per pattern.

    ``columns`` maps a coordinate name to its value in every pattern, in the
    order the patterns are passed; ``None`` is a pattern with no value for that
    coordinate (a declaration whose subset needs it there is refused).
    ``units`` names a column's unit, which a coefficient's reported unit is
    built from; a term over a column it leaves out reports no unit at all,
    rather than one claiming the column dimensionless.
    """

    columns: dict[str, list[float | None]]
    units: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> "CoordinateTable":
        if not self.columns:
            raise ValueError("a coordinate table needs at least one column")
        for name, values in self.columns.items():
            if not name.isidentifier():
                raise ValueError(
                    f"coordinate name {name!r} must be a single identifier, so a "
                    "polynomial term can name it and a label can print it")
            for k, v in enumerate(values):
                if v is not None:
                    _finite(v, f"coordinate {name!r} at pattern {k}")
        lengths = {name: len(v) for name, v in self.columns.items()}
        if len(set(lengths.values())) != 1:
            raise ValueError(
                f"every coordinate column needs one value per pattern; the "
                f"lengths differ: {lengths}")
        if min(lengths.values()) < 1:
            raise ValueError("a coordinate column needs at least one pattern")
        extra = sorted(set(self.units) - set(self.columns))
        if extra:
            raise ValueError(f"units name columns the table does not have: {extra}")
        return self

    @property
    def n_patterns(self) -> int:
        """How many patterns the table describes (every column's length)."""
        return len(next(iter(self.columns.values())))


class ParametricEquation(Base):
    """One target refined as a declared function of the coordinates.

    For the three linear bases, its coefficients are named variables
    ``vars.{name}_{j}``, j = 0…m−1, one shared column each in the joint fit,
    and the target in each pattern of the subset is tied onto
    Σ_j Φ_kj·``vars.{name}_{j}``.  A plan frees them when a stage's glob
    reaches the target, so ``mccusker_default``'s cell stage frees a
    parametric cell as it would a plain one.

    For ``basis="expression"`` the target in each pattern of the subset is the
    ``expression`` evaluated at that pattern's coordinates.  Its free names are
    variables, ``vars.{name}`` for each name the caller declares with
    ``refine_multi(variables=…)`` (one shared column, however many equations
    name it), or coordinate columns.  It has no coefficients of its own, and a
    stage's glob reaching the target frees the variables it names.

    An ``expression`` equation's ``name`` may be used in the expression of a
    **later** expression equation, so one equation feeds another: a
    temperature calibration ``T_true = T + c0 + c1*T`` feeding a cell edge
    ``a0 + k*T_true``.  An expression equation with ``target=None`` is such an
    **intermediate** alone.  It drives nothing itself and is evaluated wherever
    a later equation names it, so it takes no ``patterns``.

    * ``target`` — one model parameter's bare dot-path, no glob and no
      ``hist.`` scope (the subset says which patterns): ``phases.0.cell.a``,
      ``instrument.background.c2``.  ``None`` only on an expression equation,
      which is then an intermediate.
    * ``basis`` — ``constant``; ``polynomial``, with ``terms``: each a list of
      coordinate names, a repeat being a power and ``[]`` the intercept
      (``[[], ["T"]]`` is a + b·T, ``[[], ["x"], ["y"], ["x", "y"]]`` a bilinear
      surface); or ``design``, with ``design``: one row per pattern of the
      subset, in subset order.
    * ``patterns`` — the subset, by index into the patterns as passed; ``None``
      is every pattern.
    * ``reference``/``scale`` — per coordinate a polynomial uses: terms are
      evaluated on (z − reference)/scale.  Left out, they are the subset's
      mid-range and half-range, computed once at resolution and stored.
    * ``expression`` — for ``basis="expression"`` alone, and required there:
      the text, parsed at construction, so a malformed one is refused here
      (:class:`~rietx.params.expression.ExpressionError`).
    """

    name: str
    target: str | None = None
    basis: ParametricBasis
    terms: list[list[str]] | None = None
    design: list[list[float]] | None = None
    patterns: list[int] | None = None
    reference: dict[str, float] | None = None
    scale: dict[str, float] | None = None
    expression: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "ParametricEquation":
        if not self.name.isidentifier():
            raise ValueError(
                f"parametric equation name {self.name!r} must be a single identifier: "
                f"its coefficients are the variables vars.{self.name}_0, …, and a "
                "glob must be able to name them")
        t = self.target
        if t is None:
            if self.basis != "expression":
                raise ValueError(
                    f"a {self.basis} basis needs a target: only an expression "
                    "equation can be an intermediate (target=None), named by a "
                    "later expression equation")
            if self.patterns is not None:
                raise ValueError(
                    f"parametric equation {self.name!r} is an intermediate "
                    "(target=None), so it takes no patterns: it is evaluated at the "
                    "patterns of each later equation that names it")
        elif not t or _GLOB_CHARS & set(t):
            raise ValueError(
                f"target {t!r} must be one bare dot-path, not a glob: one "
                "declaration ties one parameter")
        elif not t.startswith(("phases.", "instrument.")):
            raise ValueError(
                f"target {t!r} must be a model parameter, a dot-path under "
                "'phases.' or 'instrument.'; name the patterns it applies to "
                "with patterns=, never with a 'hist.' scope")
        if self.patterns is not None:
            if not self.patterns:
                raise ValueError("patterns=[] selects nothing; pass None for every pattern")
            if any(k < 0 for k in self.patterns):
                raise ValueError(f"pattern indices are non-negative: {self.patterns}")
            if len(set(self.patterns)) != len(self.patterns):
                raise ValueError(f"a pattern appears twice in the subset: {self.patterns}")
        if self.basis != "expression" and self.expression is not None:
            raise ValueError(
                f"a {self.basis} basis takes no expression: an equation written as "
                "text is basis='expression'")
        if self.basis == "constant":
            self._forbid("constant", "terms", "design", "reference", "scale")
        elif self.basis == "polynomial":
            self._forbid("polynomial", "design")
            self._check_terms()
        elif self.basis == "design":
            self._forbid("design", "terms", "reference", "scale")
            self._check_design()
        else:
            self._forbid("expression", "terms", "design", "reference", "scale")
            if self.expression is None:
                raise ValueError(
                    "an expression basis needs expression='…', e.g. "
                    "'zero_a + grad/(exp(theta/T) - 1)'")
            from ..params.expression import Expression

            Expression(self.expression)
        return self

    def _forbid(self, basis: str, *fields: str) -> None:
        given = [f for f in fields if getattr(self, f) is not None]
        if given:
            raise ValueError(
                f"a {basis} basis takes no {', '.join(given)}: "
                + {"constant": "one coefficient, the same in every pattern of the "
                               "subset, uses no coordinate",
                   "polynomial": "its rows are built from terms over the "
                                 "coordinate table",
                   "design": "its rows are the caller's own, already in the units "
                             "the caller wants each coefficient in",
                   "expression": "the expression names its own variables and "
                                 "coordinates"}[basis])

    def _check_terms(self) -> None:
        if not self.terms:
            raise ValueError("a polynomial basis needs terms, e.g. [[], ['T']] for a + b·T")
        seen: set[tuple[str, ...]] = set()
        for term in self.terms:
            for name in term:
                if not name.isidentifier():
                    raise ValueError(f"term {term!r} names {name!r}, not a coordinate name")
            key = tuple(sorted(term))
            if key in seen:
                raise ValueError(
                    f"term {term!r} appears twice (a term is a product, so its "
                    "order does not matter); a repeated column is a rank-deficient "
                    "basis")
            seen.add(key)
        used = set(self.coordinates_used())
        for field in ("reference", "scale"):
            given = getattr(self, field) or {}
            extra = sorted(set(given) - used)
            if extra:
                raise ValueError(
                    f"{field} names coordinates no term uses: {extra} (terms use "
                    f"{sorted(used)})")
            for name, v in given.items():
                _finite(v, f"{field}[{name!r}]")
        for name, v in (self.scale or {}).items():
            if v <= 0.0:
                raise ValueError(f"scale[{name!r}] must be positive, got {v!r}")

    def _check_design(self) -> None:
        if not self.design:
            raise ValueError("a design basis needs design rows, one per pattern of the subset")
        widths = {len(row) for row in self.design}
        if len(widths) != 1 or min(widths) < 1:
            raise ValueError(
                f"every design row needs the same number (≥ 1) of columns; got "
                f"{sorted(widths)}")
        for k, row in enumerate(self.design):
            for j, v in enumerate(row):
                _finite(v, f"design[{k}][{j}]")
        if self.patterns is not None and len(self.design) != len(self.patterns):
            raise ValueError(
                f"{len(self.design)} design rows for a subset of "
                f"{len(self.patterns)} patterns: one row per pattern, in subset order")

    def coordinates_used(self) -> list[str]:
        """The coordinate names the polynomial terms use, first use first."""
        out: dict[str, None] = {}
        for term in self.terms or []:
            for name in term:
                out[name] = None
        return list(out)

    @property
    def n_coefficients(self) -> int:
        """m, the number of coefficients this declaration refines.

        0 for an expression, whose freedom is the variables it names.
        """
        if self.basis == "expression":
            return 0
        if self.basis == "constant":
            return 1
        if self.basis == "polynomial":
            return len(self.terms or [])
        return len((self.design or [[]])[0])

    def coefficient_paths(self) -> list[str]:
        """``vars.{name}_{j}`` for j = 0…m−1, the coefficients' dot-paths.

        Empty for an expression: its variables are ``vars.{variable}``, named
        by the caller rather than by the equation.
        """
        return [f"vars.{self.name}_{j}" for j in range(self.n_coefficients)]


class ParametricCoefficient(Base):
    """One refined coefficient of a :class:`ParametricEquation`, in user units.

    ``value`` and ``esd`` are the coefficient of the term ``term`` per unit of
    the coordinates themselves (not of the scaled u), **at the reference**: for
    a polynomial each is the refined coefficient divided by the product of the
    term's coordinate scales, so ``"1"`` is the target at the reference point
    and ``"T"`` its slope there.  A ``design`` coefficient is reported as the
    design matrix defines it, and a ``constant`` one is the target itself.

    ``esd`` is ``None`` where the joint covariance gives the coefficient none:
    no pattern of the subset carried gradient for it, or it was not free in
    the solve that produced the answer (``vary`` False).  ``unit`` is the target's unit over the term's coordinate
    units, and ``None`` unless the target's and every such coordinate's unit
    is recorded (a ``design`` coefficient's is the caller's, so never).

    An ``expression`` equation has no terms, so its rows are its variables
    (WP-1964).  ``term`` is the variable's name and ``path`` its row,
    ``vars.<name>``.  ``value`` and ``esd`` are the variable's own, in the
    variable's ``unit``, and ``reference`` is ``None``.  A variable two
    formulas read is listed under each, once per equation.  A per-pattern
    variable (one ``SharingMap.per_histogram`` names) has a row per pattern
    of the subset, ``path`` its ``hist.<h>.vars.<name>`` row.  So this table
    does not count free parameters; ``RefinementResult.parameters`` does.

    ``equation`` was ``tie`` in 1.9.0 (schema 0.55), whose results still open:
    the old key is read as ``equation`` and only ``equation`` is written.
    """

    equation: str = Field(validation_alias=AliasChoices("equation", "tie"))
    target: str
    term: str
    path: str
    value: float
    esd: float | None
    vary: bool
    unit: str | None
    reference: dict[str, float] | None


class ParametricFormReading(Base):
    """One reading of a form test (:class:`ParametricFormTest`), or of every
    tested declaration at once (:attr:`RefinementResult.parametric_form_joint
    <rietx.schemas.results.RefinementResult.parametric_form_joint>`).

    The alternative frees the declaration's target in each pattern of the
    subset, in place of its coefficients, and one linear least-squares step
    from the answer with every other free column refitted says how much χ²
    that would remove (``params.parametric.form_tests``).

    * ``dof`` — the directions the alternative adds past the covariance's
      cut, the patterns tested less the free coefficients when nothing is
      degenerate; 0 when there was nothing to test.
    * ``statistic`` — that χ² over χ²_red, the answer's reduced χ², which
      is ~χ² with ``dof`` degrees of freedom while the form holds.
    * ``cut`` — the χ² point at ``params.parametric.FORM_TEST_LEVEL``.
    * ``rejected`` — ``statistic > cut``.
    * ``p_value`` — χ²'s upper tail at ``statistic``, so a near miss reads as
      one on either side of the cut.

    The last four are ``None`` unless ``dof`` is positive and the answer's
    χ²_red is a positive finite number.
    """

    dof: int
    statistic: float | None
    cut: float | None
    rejected: bool | None
    p_value: float | None


class ParametricFormTest(Base):
    """Whether one :class:`ParametricEquation`'s form survives its own data.

    A score test at the answer, read up to twice (:class:`ParametricFormReading`).

    * ``n_patterns`` — the subset patterns whose own target entered the
      alternative.  A pattern that cannot see the target is left out, as an
      untied fit would hold it there (WP-1301), and so is one where Φ is zero.
    * ``n_subset`` — the patterns the declaration's subset names.  Where
      ``n_patterns`` is the smaller, the equation sets the target in the rest and
      the test cannot check it there; ``PARAMETRIC_TARGET_UNSEEN`` names the
      patterns that cannot see it.
    * ``tied`` — the reading with every other equation still tied.  ``None`` when
      the test did not run: a coefficient was not free at the answer.  An
      ``expression`` equation is read through its exact gradient in place of
      Φ, and untested only when none of its variables was free (WP-1964).
    * ``others_freed`` — the reading with every other tested equation's target
      freed too, so its verdict does not assume the other equations' forms: the
      gain with every equation's targets freed less the gain with only the others'
      freed, directions by the same difference.  ``None`` unless two or more
      equations were tested, since with one the two readings are one test.
    * ``rejected`` — the verdict: ``others_freed``'s where there is one,
      else ``tied``'s.  Freed assumes nothing of the other equations' forms, and
      tied an equation can pass behind another equation's misfit.  Two equations whose
      targets move the pattern alike can absorb each other freed, which the
      joint reading of every equation at once sees
      (:attr:`RefinementResult.parametric_form_joint
      <rietx.schemas.results.RefinementResult.parametric_form_joint>`).
      When true, the coefficients' esds assume a form the data refuses.
      ``None`` when the verdict's reading has no statistic.
    * ``provisional_on`` — the other tested declarations whose verdict is a
      rejection.  Every reading is one linear step from the answer, and a
      rejected declaration's misfit has moved that answer, so this verdict
      can differ from a refit's.  On ZrP₂O₇ a right line was rejected beside
      an equation at 3122 for 34 directions, and on WO₃ a bent angle passed beside
      rejected edges (``docs/wp/1325-parametric-series.md`` § Measured: the
      form test out of sample).  Empty when no other declaration is rejected.
    """

    equation: str
    target: str
    n_patterns: int
    n_subset: int
    rejected: bool | None
    tied: ParametricFormReading | None
    others_freed: ParametricFormReading | None
    provisional_on: list[str]


class ParametricValue(Base):
    """One declaration's target evaluated at a coordinate, with its esd.

    :meth:`RefinementResult.parametric_value
    <rietx.schemas.results.RefinementResult.parametric_value>` builds it from
    the stored coefficients and their covariance (:class:`RefinedParametricEquation`).

    * ``coordinates`` — where it was evaluated; empty for a ``constant`` equation
      and for a ``design`` row, which is ``row``.
    * ``value``, ``esd``, ``unit`` — the target there, in its own unit.
      ``esd`` is ``None`` when the equation has no covariance
      (:attr:`RefinedParametricEquation.covariance`), even at a point whose term for the
      coefficient lacking an esd is zero.
    * ``outside`` — the coordinates whose value lies outside the range the
      subset's patterns span, so the value there extrapolates the equation.  Empty
      inside every range.  Over two or more coordinates a point can be inside
      each range and still far from every pattern, which this does not see.
      ``None`` for a ``design`` row, whose coordinates the fit never saw.
    * ``form_rejected`` — the declaration's form test verdict
      (:class:`ParametricFormTest`), because the esd assumes the form.
      ``None`` where the form was not tested.
    * ``provisional_on`` — the other declarations the form test rejected
      (:attr:`ParametricFormTest.provisional_on`).  Their misfit moved the
      answer this verdict steps from, so a verdict beside them is provisional.
      Empty where none was rejected or the form was not tested.
    * ``joint_rejected`` — the verdict of the joint reading of every tested
      declaration at once (:attr:`RefinementResult.parametric_form_joint
      <rietx.schemas.results.RefinementResult.parametric_form_joint>`).  It can
      reject while each declaration's own verdict passes, and then this esd's
      assumption is refused too.  ``None`` where this declaration was not part
      of a joint reading.
    """

    equation: str
    target: str
    coordinates: dict[str, float]
    row: list[float] | None
    value: float
    esd: float | None
    unit: str | None
    outside: list[str] | None
    form_rejected: bool | None
    provisional_on: list[str]
    joint_rejected: bool | None

    def __str__(self) -> str:
        from .._display import _number

        if self.row is not None:
            at = f" at row {self.row}"
        elif self.coordinates:
            at = " at " + ", ".join(f"{k}={v:g}" for k, v in self.coordinates.items())
        else:
            at = ""
        unit = f" {self.unit}" if self.unit else ""
        notes = []
        if self.outside:
            notes.append(f"extrapolating in {', '.join(self.outside)}")
        notes.append({True: "form REJECTED", False: "form not rejected",
                      None: "form not tested"}[self.form_rejected])
        if self.provisional_on:
            notes.append("provisional beside rejected "
                         + ", ".join(repr(n) for n in self.provisional_on))
        if self.joint_rejected:
            notes.append("the joint reading of every equation rejects the set")
        return (f"{self.equation}: {self.target}{at} = {_number(self.value, self.esd)}"
                f"{unit} ({'; '.join(notes)})")


class RefinedParametricEquation(Base):
    """One parametric declaration as the fit resolved it, with what a reader
    needs to evaluate it anywhere (WP-1325).

    * ``equation`` — the declaration with its reference and scale filled in, the
      form to pass back for a refit or a grown campaign.
    * ``unit`` — the target's unit, ``None`` where none is recorded.
    * ``span`` — per coordinate a polynomial uses, the lowest and highest
      value across the subset; empty for the other bases.
    * ``covariance`` — the coefficients' covariance in the caller's units at
      the reference, one row and column per coefficient in
      ``equation.coefficient_paths()`` order.  It is each pair's correlation from
      the joint solve times their esds, so its diagonal is each
      :class:`ParametricCoefficient` ``esd`` squared, bit for bit.  ``None``
      when a coefficient has no esd, or the solve kept no correlation for a
      equation of several coefficients.
    """

    equation: ParametricEquation
    unit: str | None
    span: dict[str, tuple[float, float]]
    covariance: list[list[float]] | None

    def evaluate(self, coefficients: list[ParametricCoefficient],
                 form: ParametricFormTest | None = None,
                 coordinates: dict[str, float] | None = None,
                 row: list[float] | None = None,
                 joint: ParametricFormReading | None = None,
                 definitions: list[RefinedParametricEquation] | None = None
                 ) -> ParametricValue:
        """The target at ``coordinates`` (or a ``design`` equation's ``row``).

        Σ_j x_j·c_j and √(x·Σ·xᵀ), with c the coefficients in the caller's
        units and x_j the term's product of (z − reference) per coordinate, so
        the value at the reference is the intercept.  ``coefficients`` are
        this equation's, in coefficient order, and are refused otherwise, as are a
        coordinate set or a row that does not match the basis.  ``joint`` is the
        joint reading of every tested equation, read only where ``form`` took
        part in it.

        An ``expression`` equation (WP-1964) is the expression at the
        coefficients' values and ``coordinates``, with √(g·Σ·gᵀ) for g its
        exact gradient in the variables.  Its coefficients are the
        variables' rows of ``RefinementResult.parametric``, in that order,
        and ``definitions`` the intermediates it names, as
        ``RefinementResult.parametric_equations`` lists them.  An expression
        reading a per-pattern variable is refused: it has a value at each
        pattern, the target's own row there, and none between them.
        """
        equation = self.equation
        paths = [c.path for c in coefficients]
        if equation.basis == "expression":
            return self._evaluate_expression(coefficients, coordinates or {},
                                             row, definitions or [], form, joint)
        if paths != equation.coefficient_paths():
            raise ValueError(f"equation {equation.name!r} takes its coefficients "
                             f"{equation.coefficient_paths()} in that order, got {paths}")
        coordinates = dict(coordinates or {})
        if equation.basis == "design":
            if row is None or coordinates:
                raise ValueError(
                    f"equation {equation.name!r} is a design basis, so it is evaluated at a "
                    f"design row (row=[…], {equation.n_coefficients} numbers in the "
                    "units of its design matrix), never at coordinates")
            if len(row) != equation.n_coefficients:
                raise ValueError(f"equation {equation.name!r} needs a row of "
                                 f"{equation.n_coefficients} numbers, got {len(row)}")
            x = [float(v) for v in row]
            outside = None
        else:
            if row is not None:
                raise ValueError(f"equation {equation.name!r} is a {equation.basis} basis: pass "
                                 "coordinates, never a design row")
            used = equation.coordinates_used()
            missing = [c for c in used if c not in coordinates]
            extra = sorted(set(coordinates) - set(used))
            if missing or extra:
                raise ValueError(
                    f"equation {equation.name!r} is evaluated at {used or 'no coordinate'}; "
                    f"missing {missing}, not used {extra}")
            for c, v in coordinates.items():
                _finite(v, f"coordinate {c!r}")
            ref = equation.reference or {}
            x = [math.prod(coordinates[c] - ref[c] for c in term)
                 for term in (equation.terms or [[]])]
            outside = [c for c in used
                       if not self.span[c][0] <= coordinates[c] <= self.span[c][1]]
        value = sum(xj * c.value for xj, c in zip(x, coefficients, strict=True))
        esd = None
        if self.covariance is not None:
            var = sum(x[i] * x[j] * self.covariance[i][j]
                      for i in range(len(x)) for j in range(len(x)))
            esd = math.sqrt(max(var, 0.0))
        return ParametricValue(
            equation=equation.name, target=equation.target, coordinates=coordinates,
            row=None if row is None else x, value=value, esd=esd, unit=self.unit,
            outside=outside, form_rejected=None if form is None else form.rejected,
            provisional_on=[] if form is None else list(form.provisional_on),
            # an equation took part in the joint reading iff it has a freed one
            joint_rejected=(None if joint is None or form is None
                            or form.others_freed is None else joint.rejected))

    def _evaluate_expression(self, coefficients: list[ParametricCoefficient],
                             coordinates: dict[str, float], row,
                             definitions: list[RefinedParametricEquation],
                             form: ParametricFormTest | None = None,
                             joint: ParametricFormReading | None = None
                             ) -> ParametricValue:
        """:meth:`evaluate` for an ``expression`` equation; see there."""
        from ..params.expression import Expression, ExpressionError

        equation = self.equation
        if row is not None:
            raise ValueError(f"equation {equation.name!r} is an expression: pass "
                             "coordinates, never a design row")
        wrong = [c.path for c in coefficients if c.equation != equation.name]
        if wrong:
            raise ValueError(f"equation {equation.name!r} takes its own variables' rows; "
                             f"{wrong} belong to another equation")
        local = [c.path for c in coefficients if c.path.startswith("hist.")]
        if local:
            raise ValueError(
                f"equation {equation.name!r} reads a per-pattern variable ({local[0]}), "
                "which has a value at each pattern and none between them, so the "
                f"equation is not evaluated anywhere else; its value at pattern h is "
                f"the result row hist.h.{equation.target}, with its esd")
        if self.covariance is not None and len(self.covariance) != len(coefficients):
            raise ValueError(f"equation {equation.name!r} takes {len(self.covariance)} "
                             f"variables' rows, in result.parametric's order; got "
                             f"{len(coefficients)}")
        defs: dict[str, Expression] = {}
        for d in definitions:
            if d.equation.basis == "expression":
                defs[d.equation.name] = Expression(d.equation.expression).inline(defs)
        tree = Expression(equation.expression).inline(defs)
        for c, v in coordinates.items():
            _finite(v, f"coordinate {c!r}")
        bindings = {c.term: c.value for c in coefficients}
        clash = sorted(set(bindings) & set(coordinates))
        if clash:
            raise ValueError(f"equation {equation.name!r}: {clash} are variables, "
                             "never coordinates")
        try:
            value, grads = tree.gradient({**bindings, **coordinates}, list(bindings))
        except ExpressionError as exc:
            raise ValueError(f"equation {equation.name!r} cannot be evaluated at "
                             f"{coordinates}: {exc}") from exc
        g = [float(d) for d in grads]
        esd = None
        if self.covariance is not None:
            var = sum(g[i] * g[j] * self.covariance[i][j]
                      for i in range(len(g)) for j in range(len(g)))
            esd = math.sqrt(max(var, 0.0))
        outside = [c for c, (lo, hi) in self.span.items()
                   if c in coordinates and not lo <= coordinates[c] <= hi]
        return ParametricValue(
            equation=equation.name, target=equation.target or "",
            coordinates=dict(coordinates), row=None, value=float(value), esd=esd,
            unit=self.unit, outside=outside,
            form_rejected=None if form is None else form.rejected,
            provisional_on=[] if form is None else list(form.provisional_on),
            joint_rejected=(None if joint is None or form is None
                            or form.others_freed is None else joint.rejected))
