"""The expression grammar a parametric equation is written in (WP-1964).

The conformance table lives on the manual page that specifies the grammar
(``docs/docs/reference/expressions.md``) and is read from there, so the page
and the implementation cannot disagree without a red row.  Every row runs on
numpy, jax and torch; the two traced backends skip in a ``[dev]`` venv.

The derivative rules are checked against complex-step differentiation (Squire
& Trapp 1998), which is exact to rounding for an analytic expression, where a
forward difference would carry its own truncation error (root CLAUDE.md, "A
branch's oracle must be exact").  Random trees cover the analytic operators;
the kinks (``abs``, ``min``, ``max``, ``if``) are checked at points away from
their switches and against the traced backends' autodiff.
"""

from __future__ import annotations

import math
import pathlib
import random
import re

import numpy as np
import pytest

from rietx.backend.api import BACKEND_REQUIRES, resolve_backend
from rietx.backend.traced import active
from rietx.params.expression import (
    ERROR_CODES,
    FUNCTIONS,
    GRAMMAR_VERSION,
    MAX_DEPTH,
    MAX_LENGTH,
    BinOp,
    Call,
    Expression,
    ExpressionError,
    Name,
    Neg,
    Num,
    debye,
    debye_derivative,
    parse,
    to_text,
)

PAGE = (pathlib.Path(__file__).resolve().parents[1]
        / "docs" / "docs" / "reference" / "expressions.md")

#: the fp64 evaluators the table binds; torch-mps is fp32 by construction
EVALUATORS = ("numpy", "jax", "torch")


def _rows() -> list[tuple[str, dict[str, float], str]]:
    text = PAGE.read_text(encoding="utf-8")
    table = text.split("## Conformance table", 1)[1]
    rows = []
    for line in table.splitlines():
        m = re.match(r"^\| `(.*)` \| (.*) \| (.*) \|$", line)
        if not m:
            continue
        expr, binds, expected = m.groups()
        bindings: dict[str, float] = {}
        if binds != "none":
            for part in binds.split(","):
                k, v = part.split("=")
                bindings[k.strip()] = float(v)
        rows.append((expr, bindings, expected.strip()))
    return rows


ROWS = _rows()


def _xp(name: str):
    package = BACKEND_REQUIRES.get(name)
    if package is not None:
        pytest.importorskip(package)
    return resolve_backend(name)


def _host(v) -> float:
    if hasattr(v, "detach"):
        v = v.detach().cpu().numpy()
    return float(np.asarray(v))


def test_the_table_is_read_and_spans_every_error_code():
    """A table the regex silently stopped reading would pass every row."""
    assert len(ROWS) >= 70
    codes = {e.split("`")[1] for _, _, e in ROWS if e.startswith("error:")}
    # too_long and too_deep cannot sit in a table cell; tested below
    assert codes == ERROR_CODES - {"too_long", "too_deep"}
    assert f"describes version {GRAMMAR_VERSION}." in PAGE.read_text(encoding="utf-8")


def test_every_function_has_a_row_and_a_line_on_the_page():
    text = PAGE.read_text(encoding="utf-8")
    exprs = " ".join(e for e, _, _ in ROWS)
    for f in FUNCTIONS:
        assert f"`{f}(" in text, f
        assert f"{f}(" in exprs, f


@pytest.mark.parametrize("backend", EVALUATORS)
@pytest.mark.parametrize("row", ROWS, ids=[f"{i}" for i in range(len(ROWS))])
def test_conformance_row(backend, row):
    expr, bindings, expected = row
    xp = _xp(backend)
    if expected.startswith("error:"):
        code = expected.split("`")[1]
        with pytest.raises(ExpressionError) as info:
            with active(xp):
                Expression(expr).evaluate(bindings, xp)
        assert info.value.code == code, (expr, info.value)
        return
    with active(xp):
        got = _host(Expression(expr).evaluate(bindings, xp))
    want = float(expected)
    if math.isnan(want):
        assert math.isnan(got), (expr, got)
    elif math.isinf(want):
        assert got == want, (expr, got)
    else:
        assert got == pytest.approx(want, rel=1e-13, abs=1e-300), (expr, got)


def test_print_round_trips_every_table_row():
    for expr, _, expected in ROWS:
        if expected.startswith("error:"):
            continue
        tree = parse(expr)
        assert parse(to_text(tree)) == tree, expr


def test_limits_on_length_and_depth():
    with pytest.raises(ExpressionError) as info:
        parse("x" + " + x" * (MAX_LENGTH // 4))
    assert info.value.code == "too_long"
    with pytest.raises(ExpressionError) as info:
        parse("(" * (MAX_DEPTH + 1) + "x" + ")" * (MAX_DEPTH + 1))
    assert info.value.code == "too_deep"
    parse("(" * (MAX_DEPTH // 2 - 1) + "x" + ")" * (MAX_DEPTH // 2 - 1))
    # a flat chain is parsed in a loop but builds a tree as deep as it is long,
    # and every walk of the tree recurses: 600 terms under MAX_LENGTH once
    # raised RecursionError
    flat = " + ".join(["x"] * 600)
    assert len(flat) < MAX_LENGTH
    with pytest.raises(ExpressionError) as info:
        parse(flat)
    assert info.value.code == "too_deep"
    parse(" + ".join(["x"] * MAX_DEPTH))
    with pytest.raises(ExpressionError) as info:
        parse(" + ".join(["x"] * (MAX_DEPTH + 1)))
    assert info.value.code == "too_deep"
    # an exponent's signs recurse in the parser too: x^----…y
    with pytest.raises(ExpressionError) as info:
        parse("x^" + "-" * 2000 + "y")
    assert info.value.code == "too_deep"


def test_an_error_quotes_the_text_with_a_caret_and_suggests_a_name():
    with pytest.raises(ExpressionError) as info:
        parse("a + Exp(theta / T)")
    message = str(info.value)
    assert "did you mean 'exp'?" in message
    lines = message.splitlines()
    assert lines[1].strip() == "a + Exp(theta / T)"
    assert lines[2].index("^") - lines[1].index("a") == 4
    with pytest.raises(ExpressionError) as info:
        Expression("zero_b + 1").evaluate({"zero_a": 1.0})
    assert "did you mean 'zero_a'?" in str(info.value)


def test_names_are_free_names_in_first_use_order():
    e = Expression("zero_a + grad / (exp(theta / T) - 1) + pi * grad")
    assert e.names == ("zero_a", "grad", "theta", "T")


def test_the_rewrites_keep_the_text_and_buy_the_digits():
    e = Expression("grad / (exp(theta / T) - 1)")
    assert e.to_text() == "grad / (exp(theta / T) - 1)"
    b = {"grad": 1.0, "theta": 1e-10, "T": 1.0}
    assert float(e.evaluate(b)) == pytest.approx(1.0 / math.expm1(1e-10), rel=1e-15)
    naive = 1.0 / (math.exp(1e-10) - 1.0)
    assert abs(naive * math.expm1(1e-10) - 1.0) > 1e-8      # what was bought


# -- random trees against complex step ---------------------------------------

_ANALYTIC = ("exp", "expm1", "log", "log1p", "sqrt", "sin", "cos", "tan",
             "asin", "acos", "atan", "debye")
_NAMES = ("a", "b", "c")


def _tree(rng: random.Random, depth: int):
    if depth == 0 or rng.random() < 0.25:
        if rng.random() < 0.3:
            return Num(round(rng.uniform(0.1, 3.0), 3))
        return Name(rng.choice(_NAMES))
    kind = rng.random()
    if kind < 0.45:
        op = rng.choice("+-*/^")
        right = Num(rng.choice([2.0, 3.0, 0.5])) if op == "^" and rng.random() < 0.5 \
            else _tree(rng, depth - 1)
        return BinOp(op, _tree(rng, depth - 1), right)
    if kind < 0.55:
        return Neg(_tree(rng, depth - 1))
    return Call(rng.choice(_ANALYTIC), (_tree(rng, depth - 1),))


def _complex_step(text: str, point: dict[str, float], name: str) -> float:
    h = 1e-30
    shifted = {k: complex(v, h) if k == name else complex(v) for k, v in point.items()}
    v = Expression(text).evaluate(shifted)
    return float(np.imag(v)) / h


def test_random_trees_round_trip_and_match_complex_step():
    rng = random.Random(1964)
    checked = 0
    for _ in range(600):
        tree = _tree(rng, 4)
        text = to_text(tree)
        assert parse(text) == tree, text
        e = Expression(text)
        point = {k: rng.uniform(0.2, 0.9) for k in _NAMES}
        v, grads = e.gradient(point, list(_NAMES))
        if not np.isfinite(v) or not all(np.isfinite(g) for g in grads):
            continue
        if abs(float(v)) > 1e8:
            continue
        for name, g in zip(_NAMES, grads, strict=True):
            want = _complex_step(text, point, name)
            assert float(g) == pytest.approx(want, rel=1e-9, abs=1e-12), (text, name)
        checked += 1
    assert checked > 300


@pytest.mark.parametrize("x", [0.0, 1e-8, -1e-8, 0.05, 0.0999, 0.1, 0.5, 3.0, 9.99,
                               10.0, 25.0, -12.0])
def test_debye_derivative_matches_complex_step(x):
    h = 1e-30
    want = float(np.imag(debye(np.complex128(complex(x, h))))) / h
    assert float(debye_derivative(x)) == pytest.approx(want, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize("text, point, wrt, want", [
    # the order parameter's derivative in Tc on each side of T = Tc
    ("if(T < Tc, (1 - T/Tc)^beta, 0)", {"T": 300.0, "Tc": 300.0, "beta": 0.3}, "Tc", 0.0),
    ("if(T < Tc, (1 - T/Tc)^beta, 0)", {"T": 400.0, "Tc": 300.0, "beta": 0.3}, "beta", 0.0),
    ("abs(x)", {"x": 0.0}, "x", 0.0),
    ("min(x, y)", {"x": 1.0, "y": 1.0}, "x", 1.0),
    ("max(x, y)", {"x": 1.0, "y": 1.0}, "y", 0.0),
    ("x^2", {"x": -3.0}, "x", -6.0),
    ("if(x >= 0, sqrt(x), -1)", {"x": -4.0}, "x", 0.0),
    ("if(x > 0, log(x), 0)", {"x": -4.0}, "x", 0.0),
    ("if(x > 1, x/(x - 1), 0)", {"x": 1.0}, "x", 0.0),
])
def test_adversarial_points_have_the_stated_derivative(text, point, wrt, want):
    _, (g,) = Expression(text).gradient(point, [wrt])
    assert float(g) == want


@pytest.mark.parametrize("backend", ["jax", "torch"])
@pytest.mark.parametrize("text, point", [
    ("zero_a + grad/(exp(theta/T) - 1)",
     {"zero_a": 7.29, "grad": 1e-5, "theta": 150.0, "T": 300.0}),
    ("if(T < Tc, a*(1 - T/Tc)^beta, 0)", {"T": 100.0, "Tc": 300.0, "a": 2.0, "beta": 0.3}),
    ("if(T < Tc, a*(1 - T/Tc)^beta, 0)", {"T": 400.0, "Tc": 300.0, "a": 2.0, "beta": 0.3}),
    ("b0 + b1*debye(theta_d/T)", {"b0": 0.1, "b1": 0.4, "theta_d": 500.0, "T": 290.0}),
    ("b0 + b1*debye(theta_d/T)", {"b0": 0.1, "b1": 0.4, "theta_d": 5.0, "T": 290.0}),
    ("min(a, b) * max(a, b)^2 + abs(a - 2*b)", {"a": 0.7, "b": 1.3}),
    ("if(x >= 0, sqrt(x), -1) + log(1 + x^2)", {"x": -4.0}),
])
def test_autodiff_matches_the_numpy_rules(backend, text, point):
    """The traced backends differentiate :meth:`Expression.evaluate`; the
    numpy path uses the rules.  One derivation each, one answer."""
    xp = _xp(backend)
    names = list(point)
    e = Expression(text)
    _, want = e.gradient(point, names)
    theta = np.array([point[k] for k in names], dtype=np.float64)
    if backend == "jax":
        import jax

        with active(xp):
            def f(t):
                return e.evaluate({k: t[i] for i, k in enumerate(names)}, xp)

            got = np.asarray(jax.jacfwd(f)(xp.asarray(theta)))
    else:
        import torch

        with active(xp):
            t = torch.tensor(theta, dtype=torch.float64)

            def f(t):
                return e.evaluate({k: t[i] for i, k in enumerate(names)}, xp)

            got = torch.func.jacfwd(f)(t).detach().numpy()
    for k, g, w in zip(names, got, want, strict=True):
        assert np.isfinite(g), (k, g)
        assert float(g) == pytest.approx(float(w), rel=1e-11, abs=1e-14), (text, k)


def test_evaluation_is_element_wise_over_arrays():
    e = Expression("zero_a + grad/(exp(theta/T) - 1)")
    temps = np.array([90.0, 150.0, 300.0])
    v, (d_theta,) = e.gradient({"zero_a": 7.29, "grad": 1e-5, "theta": 150.0,
                                "T": temps}, ["theta"])
    assert v.shape == d_theta.shape == (3,)
    for k, t in enumerate(temps):
        one = float(e.evaluate({"zero_a": 7.29, "grad": 1e-5, "theta": 150.0, "T": t}))
        assert v[k] == one


def test_one_expression_feeds_another_by_inlining():
    calib = Expression("T + c1*T + c2*T^2")
    cell = Expression("a0 + k*T_true").inline({"T_true": calib})
    assert set(cell.names) == {"a0", "k", "T", "c1", "c2"}
    b = {"a0": 5.43, "k": 1e-5, "T": 300.0, "c1": 0.01, "c2": -2e-5}
    t_true = 300.0 + 0.01 * 300.0 - 2e-5 * 300.0 ** 2
    assert float(cell.evaluate(b)) == pytest.approx(5.43 + 1e-5 * t_true, rel=1e-15)
    _, (d_c1,) = cell.gradient(b, ["c1"])
    assert float(d_c1) == pytest.approx(1e-5 * 300.0, rel=1e-13)
    # a power base or a sign keeps its meaning once the definition is a sum
    sq = Expression("-u^2").inline({"u": Expression("x + 1")})
    assert float(sq.evaluate({"x": 1.0})) == -4.0
