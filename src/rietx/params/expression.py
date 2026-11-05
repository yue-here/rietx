"""The expression grammar a parametric equation is written in (WP-1964).

A user writes an equation as text, ``zero_a + grad/(exp(theta/T) - 1)``, and
this module turns it into rietx's own tree, prints the tree back, evaluates it
on any backend (``xp``) and differentiates it exactly.  The grammar is written
down in the manual (``docs/docs/reference/expressions.md``), with a
conformance table of (expression, bindings, expected value or error) that
``tests/test_expression.py`` runs on every registered backend.  That page is
the specification and this module is its one implementation.

**Why a hand-written parser** (``docs/practice.md`` § A parameter set by an
equation the user writes).  Every system surveyed with exact derivatives owns
a tree with a closed operator list (JuMP, CasADi, TOPAS).  ``ast`` changes with
python and reads ``^`` as XOR; sympy's ``parse_expr`` calls ``eval`` and its
``lambdify`` calls ``exec``.  A Pratt parser over a closed vocabulary adds no
dependency, runs under Pyodide, and makes the spellings below free to choose.

**The traps the grammar refuses** (the survey's list).  ``x^y^z`` is
left-associative in TOPAS and right-associative in python, so an unparenthesised
power chain is refused.  An implied multiplication (``2x``, ``x y``) is refused,
because ``Tc`` and ``T c`` would then differ by a space.  ``^`` and ``**`` are
both the power.

**Evaluation** is element-wise IEEE fp64 on whatever the bindings hold: python
floats, numpy arrays, or a traced backend's values.  ``if(c, a, b)`` evaluates
both branches, as a traced backend must, so each branch's domain-restricted
arguments (a logarithm's, a root's, a power's base, a divisor) are replaced by a
safe value where the branch is dead.  Without that, the dead branch's NaN
reaches an autodiff gradient (the JAX FAQ's "where" trap) and the numpy path
warns about a value nobody uses.

**Derivatives** are forward-mode rules, one per operator, on the numpy path
(:meth:`Expression.gradient`).  A traced backend differentiates
:meth:`Expression.evaluate` itself.  Two rewrites are applied before either:
``exp(u) - 1`` becomes ``expm1(u)`` and ``log(1 + u)`` becomes ``log1p(u)``, so
an Einstein denominator keeps its digits as θ/T → 0.  In ``x^y`` the
``log(x)`` term enters only where ``y`` depends on a name being differentiated,
so ``x^2`` at negative x has a finite derivative.  A comparison carries no
derivative, and nothing is smoothed.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .._nearmiss import did_you_mean

#: the grammar's version, quoted by ``capabilities()``; a change to what any
#: expression means, or to what is accepted, moves it
GRAMMAR_VERSION = "1"

#: the longest expression accepted, in characters
MAX_LENGTH = 4096
#: the deepest nesting accepted (parentheses, calls and operators together)
MAX_DEPTH = 64

#: function → its number of arguments (``None``: two or more)
FUNCTIONS: dict[str, int | None] = {
    "exp": 1, "expm1": 1, "log": 1, "log1p": 1, "sqrt": 1,
    "sin": 1, "cos": 1, "tan": 1, "asin": 1, "acos": 1, "atan": 1,
    "abs": 1, "min": None, "max": None, "if": 3, "debye": 1,
}
#: named constants
CONSTANTS: dict[str, float] = {"pi": math.pi}
#: words that are operators
KEYWORDS = frozenset({"and", "or", "not"})
#: every name an equation, a variable or a coordinate may not take
RESERVED = frozenset(FUNCTIONS) | frozenset(CONSTANTS) | KEYWORDS

#: every error code an :class:`ExpressionError` carries
ERROR_CODES = frozenset({
    "syntax", "implied_multiplication", "power_chain", "comparison_chain",
    "unknown_function", "arity", "type", "reserved", "too_long", "too_deep",
    "unbound",
})


class ExpressionError(ValueError):
    """An expression that does not parse, type-check or bind.

    ``code`` is one of :data:`ERROR_CODES`, the conformance table's error
    column.  ``column`` is the 0-based offset into ``text`` the caret points
    at, or ``None`` where no one place is to blame.
    """

    def __init__(self, code: str, message: str, text: str = "",
                 column: int | None = None):
        self.code = code
        self.text = text
        self.column = column
        self.reason = message
        if text and column is not None:
            shown = text if len(text) <= 120 else text[:117] + "..."
            caret = " " * min(column, len(shown)) + "^"
            message = f"{message}\n  {shown}\n  {caret}"
        super().__init__(message)


# -- the tree ----------------------------------------------------------------

@dataclass(frozen=True)
class Num:
    """A number literal (never negative: a sign is :class:`Neg`)."""
    value: float


@dataclass(frozen=True)
class Name:
    """A name: a variable, a coordinate, an earlier equation, or ``pi``."""
    id: str


@dataclass(frozen=True)
class Neg:
    """Unary minus."""
    arg: Any


@dataclass(frozen=True)
class BinOp:
    """``+ - * / ^`` (``**`` parses to ``^``)."""
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class Call:
    """A function from :data:`FUNCTIONS`."""
    func: str
    args: tuple


@dataclass(frozen=True)
class Compare:
    """``< <= > >= == !=``, a condition."""
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class BoolOp:
    """``and``/``or``, a condition."""
    op: str
    left: Any
    right: Any


@dataclass(frozen=True)
class Not:
    """``not``, a condition."""
    arg: Any


_COMPARE = ("<=", ">=", "==", "!=", "<", ">")
_BOOL_NODES = (Compare, BoolOp, Not)


def _is_condition(node) -> bool:
    return isinstance(node, _BOOL_NODES)


# -- tokens ------------------------------------------------------------------

@dataclass(frozen=True)
class _Tok:
    kind: str           # "num", "name", "op", "end"
    text: str
    col: int
    value: float = 0.0


def _tokenize(text: str) -> list[_Tok]:
    toks: list[_Tok] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit()):
            j = i
            while j < n and text[j].isdigit():
                j += 1
            if j < n and text[j] == ".":
                j += 1
                while j < n and text[j].isdigit():
                    j += 1
            if j < n and text[j] in "eE":
                k = j + 1
                if k < n and text[k] in "+-":
                    k += 1
                if k < n and text[k].isdigit():
                    while k < n and text[k].isdigit():
                        k += 1
                    j = k
                else:
                    raise ExpressionError(
                        "syntax", "a number's exponent needs digits, as in 1e-5",
                        text, j)
            if j < n and (text[j].isalpha() or text[j] == "_"):
                raise ExpressionError(
                    "implied_multiplication",
                    f"a number followed by a name; write {text[i:j]}*{text[j]}… "
                    "with the * (an implied multiplication is refused)", text, j)
            toks.append(_Tok("num", text[i:j], i, float(text[i:j])))
            i = j
            continue
        if c.isascii() and (c.isalpha() or c == "_"):
            j = i + 1
            while j < n and text[j].isascii() and (text[j].isalnum() or text[j] == "_"):
                j += 1
            toks.append(_Tok("name", text[i:j], i))
            i = j
            continue
        two = text[i:i + 2]
        if two in ("**", "<=", ">=", "==", "!="):
            toks.append(_Tok("op", "^" if two == "**" else two, i))
            i += 2
            continue
        if two in ("&&", "||"):
            raise ExpressionError(
                "syntax", f"{two!r} is not an operator; write "
                f"{'and' if two == '&&' else 'or'}", text, i)
        if c in "+-*/^(),<>":
            toks.append(_Tok("op", c, i))
            i += 1
            continue
        if c == "=":
            raise ExpressionError("syntax", "'=' is not an operator; compare with ==",
                                  text, i)
        if c == "!":
            raise ExpressionError("syntax", "'!' is not an operator; write not",
                                  text, i)
        raise ExpressionError("syntax", f"unexpected character {c!r}", text, i)
    toks.append(_Tok("end", "", n))
    return toks


# -- the parser --------------------------------------------------------------

#: binding power of each infix operator, low to high (``^`` is handled apart)
_INFIX = {"or": 1, "and": 2, **{op: 4 for op in _COMPARE},
          "+": 5, "-": 5, "*": 6, "/": 6}
_NOT_POWER = 3
_UNARY_POWER = 7


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.toks = _tokenize(text)
        self.i = 0
        self.depth = 0

    def peek(self) -> _Tok:
        return self.toks[self.i]

    def take(self) -> _Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def err(self, code: str, msg: str, col: int | None) -> ExpressionError:
        return ExpressionError(code, msg, self.text, col)

    def expect(self, op: str) -> _Tok:
        t = self.peek()
        if t.kind != "op" or t.text != op:
            got = "the end" if t.kind == "end" else repr(t.text)
            raise self.err("syntax", f"expected {op!r}, found {got}", t.col)
        return self.take()

    def _op_of(self, t: _Tok) -> str | None:
        if t.kind == "op" and t.text in _INFIX:
            return t.text
        if t.kind == "name" and t.text in ("and", "or"):
            return t.text
        return None

    def parse(self):
        node = self.expr(0)
        t = self.peek()
        if t.kind != "end":
            if (t.kind in ("num", "name") and t.text not in KEYWORDS) or (
                    t.kind == "op" and t.text == "("):
                raise self.err("implied_multiplication",
                               "two operands with no operator between them; write "
                               "the * (an implied multiplication is refused)", t.col)
            raise self.err("syntax", f"unexpected {t.text!r}", t.col)
        return node

    def expr(self, min_power: int):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise self.err("too_deep", f"the expression nests deeper than {MAX_DEPTH}",
                           self.peek().col)
        start = self.peek()
        left = self.prefix()
        left_col = start.col
        while True:
            t = self.peek()
            op = self._op_of(t)
            if op is None:
                if t.kind in ("num", "name") and t.text not in KEYWORDS or (
                        t.kind == "op" and t.text == "("):
                    raise self.err("implied_multiplication",
                                   "two operands with no operator between them; "
                                   "write the * (an implied multiplication is "
                                   "refused)", t.col)
                break
            power = _INFIX[op]
            if power <= min_power:
                break
            self.take()
            right_col = self.peek().col
            right = self.expr(power)
            if op in _COMPARE:
                nxt = self._op_of(self.peek())
                if nxt in _COMPARE:
                    raise self.err(
                        "comparison_chain",
                        "a chained comparison such as a < b < c is refused; "
                        "write (a < b) and (b < c)", self.peek().col)
                self._want_num(left, left_col, f"the left side of {op}")
                self._want_num(right, right_col, f"the right side of {op}")
                left = Compare(op, left, right)
            elif op in ("and", "or"):
                self._want_bool(left, left_col, f"the left side of {op}")
                self._want_bool(right, right_col, f"the right side of {op}")
                left = BoolOp(op, left, right)
            else:
                self._want_num(left, left_col, f"the left side of {op}")
                self._want_num(right, right_col, f"the right side of {op}")
                left = BinOp(op, left, right)
        self.depth -= 1
        return left

    def _want_num(self, node, col: int, where: str) -> None:
        if _is_condition(node):
            raise self.err("type", f"{where} is a condition where a number is "
                           "needed; a condition goes only in if(…) or beside "
                           "and, or, not", col)

    def _want_bool(self, node, col: int, where: str) -> None:
        if not _is_condition(node):
            raise self.err("type", f"{where} is a number where a condition is "
                           "needed, such as T > 300", col)

    def prefix(self):
        t = self.peek()
        if t.kind == "op" and t.text in "+-" and len(t.text) == 1:
            self.take()
            col = self.peek().col
            arg = self.unary_operand()
            self._want_num(arg, col, f"the operand of unary {t.text}")
            return Neg(arg) if t.text == "-" else arg
        if t.kind == "name" and t.text == "not":
            self.take()
            col = self.peek().col
            arg = self.expr(_NOT_POWER)
            self._want_bool(arg, col, "the operand of not")
            return Not(arg)
        return self.power()

    def unary_operand(self):
        """What a unary sign applies to: another sign, or a power."""
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise self.err("too_deep", f"the expression nests deeper than {MAX_DEPTH}",
                           self.peek().col)
        t = self.peek()
        if t.kind == "op" and t.text in ("+", "-"):
            self.take()
            arg = self.unary_operand()
            node = Neg(arg) if t.text == "-" else arg
        else:
            node = self.power()
        self.depth -= 1
        return node

    def power(self):
        """An atom, raised to a signed atom: ``x``, ``x^2``, ``x^-(a + b)``.

        The exponent is a sign or two and one atom, so a second ``^`` after
        it is a chain, refused whichever way it is written.
        """
        base_col = self.peek().col
        base = self.atom()
        t = self.peek()
        if not (t.kind == "op" and t.text == "^"):
            return base
        self.take()
        exp_col = self.peek().col
        exponent = self.exponent()
        self._want_num(base, base_col, "the base of ^")
        self._want_num(exponent, exp_col, "the exponent of ^")
        nxt = self.peek()
        if nxt.kind == "op" and nxt.text == "^":
            raise self.err(
                "power_chain",
                "x^y^z is refused: TOPAS reads it (x^y)^z and python x^(y^z); "
                "write the parentheses", nxt.col)
        return BinOp("^", base, exponent)

    def exponent(self):
        t = self.peek()
        if t.kind == "op" and t.text in ("+", "-"):
            self.take()
            arg = self.exponent()
            return Neg(arg) if t.text == "-" else arg
        return self.atom()

    def atom(self):
        t = self.take()
        if t.kind == "num":
            return Num(t.value)
        if t.kind == "op" and t.text == "(":
            self.depth += 1
            node = self.expr(0)
            self.depth -= 1
            self.expect(")")
            return node
        if t.kind == "name":
            if t.text in KEYWORDS:
                raise self.err("syntax", f"{t.text!r} is an operator here, "
                               "not a name", t.col)
            nxt = self.peek()
            if nxt.kind == "op" and nxt.text == "(":
                return self.call(t)
            if t.text in FUNCTIONS:
                raise self.err("reserved", f"{t.text!r} is a function; call it, "
                               f"as in {t.text}(x)", t.col)
            return Name(t.text)
        if t.kind == "end":
            raise self.err("syntax", "the expression ends where an operand is "
                           "expected", t.col)
        raise self.err("syntax", f"unexpected {t.text!r} where an operand is "
                       "expected", t.col)

    def call(self, name: _Tok):
        func = name.text
        if func not in FUNCTIONS:
            hint = did_you_mean(func, FUNCTIONS)
            raise self.err("unknown_function",
                           f"unknown function {func!r}" + (f"; {hint}" if hint else
                                                           "; the functions are "
                                                           + ", ".join(FUNCTIONS)),
                           name.col)
        self.expect("(")
        args: list = []
        cols: list[int] = []
        if not (self.peek().kind == "op" and self.peek().text == ")"):
            while True:
                cols.append(self.peek().col)
                args.append(self.expr(0))
                if self.peek().kind == "op" and self.peek().text == ",":
                    self.take()
                    continue
                break
        self.expect(")")
        want = FUNCTIONS[func]
        if (want is None and len(args) < 2) or (want is not None and len(args) != want):
            need = "two or more arguments" if want is None else (
                f"{want} argument{'s' if want != 1 else ''}")
            raise self.err("arity", f"{func}() takes {need}, given {len(args)}",
                           name.col)
        for k, (a, col) in enumerate(zip(args, cols, strict=True)):
            if func == "if" and k == 0:
                self._want_bool(a, col, "if()'s first argument")
            else:
                self._want_num(a, col, f"argument {k + 1} of {func}()")
        return Call(func, tuple(args))


def parse(text: str):
    """The tree of ``text``; raises :class:`ExpressionError`.

    The tree is a number: a condition is refused at the top level, since an
    equation's value is a number.
    """
    if not isinstance(text, str):
        raise TypeError(f"an expression is text, got {type(text).__name__}")
    if len(text) > MAX_LENGTH:
        raise ExpressionError("too_long",
                              f"the expression is {len(text)} characters; the limit "
                              f"is {MAX_LENGTH}")
    if not text.strip():
        raise ExpressionError("syntax", "the expression is empty")
    node = _Parser(text).parse()
    if _is_condition(node):
        raise ExpressionError("type", "the expression is a condition; an equation's "
                              "value is a number (a condition goes in if(…))", text, 0)
    return node


# -- the printer -------------------------------------------------------------

def _num_text(v: float) -> str:
    if not math.isfinite(v) or v < 0 or (v == 0 and math.copysign(1.0, v) < 0):
        raise ValueError(f"a literal is a finite non-negative number, got {v!r}")
    r = repr(float(v))
    return r[:-2] if r.endswith(".0") else r


def _prec(node) -> int:
    if isinstance(node, BoolOp):
        return _INFIX[node.op]
    if isinstance(node, Not):
        return _NOT_POWER
    if isinstance(node, Compare):
        return 4
    if isinstance(node, BinOp):
        return 8 if node.op == "^" else _INFIX[node.op]
    if isinstance(node, Neg):
        return _UNARY_POWER
    return 9


def to_text(node) -> str:
    """The tree printed with the fewest parentheses that round-trip it.

    ``parse(to_text(t)) == t`` for every tree :func:`parse` can return.
    """
    if isinstance(node, Num):
        return _num_text(node.value)
    if isinstance(node, Name):
        return node.id
    if isinstance(node, Call):
        return f"{node.func}({', '.join(to_text(a) for a in node.args)})"
    if isinstance(node, Neg):
        arg = node.arg
        inner = to_text(arg)
        # a sign binds tighter than everything but ^ and an atom
        return f"-{inner}" if _prec(arg) >= _UNARY_POWER else f"-({inner})"
    if isinstance(node, Not):
        inner = to_text(node.arg)
        return f"not {inner}" if _prec(node.arg) >= _NOT_POWER else f"not ({inner})"
    if isinstance(node, BinOp) and node.op == "^":
        base = to_text(node.left)
        if not isinstance(node.left, Num | Name | Call):
            base = f"({base})"
        signs, inner = "", node.right
        while isinstance(inner, Neg):
            signs, inner = signs + "-", inner.arg
        if isinstance(inner, Num | Name | Call):
            return f"{base}^{signs}{to_text(inner)}"
        return f"{base}^({to_text(node.right)})"
    if isinstance(node, BinOp | Compare | BoolOp):
        p = _prec(node)
        left, right = to_text(node.left), to_text(node.right)
        if _prec(node.left) < p:
            left = f"({left})"
        if _prec(node.right) <= p:
            right = f"({right})"
        return f"{left} {node.op} {right}"
    raise TypeError(f"not an expression node: {node!r}")


# -- names and rewrites ------------------------------------------------------

def names_in(node) -> list[str]:
    """Free names, first use first, constants left out."""
    out: dict[str, None] = {}

    def walk(n):
        if isinstance(n, Name):
            if n.id not in CONSTANTS:
                out[n.id] = None
        elif isinstance(n, Neg | Not):
            walk(n.arg)
        elif isinstance(n, BinOp | Compare | BoolOp):
            walk(n.left)
            walk(n.right)
        elif isinstance(n, Call):
            for a in n.args:
                walk(a)

    walk(node)
    return list(out)


def rewrite(node):
    """``exp(u) - 1`` → ``expm1(u)``, ``log(1 + u)``/``log(u + 1)`` → ``log1p(u)``.

    Applied before evaluation and differentiation, never to the stored or
    printed tree, so a user reads back what they wrote.
    """
    if isinstance(node, Num | Name):
        return node
    if isinstance(node, Neg):
        return Neg(rewrite(node.arg))
    if isinstance(node, Not):
        return Not(rewrite(node.arg))
    if isinstance(node, Call):
        args = tuple(rewrite(a) for a in node.args)
        if node.func == "log" and isinstance(args[0], BinOp) and args[0].op == "+":
            a = args[0]
            if a.left == Num(1.0):
                return Call("log1p", (a.right,))
            if a.right == Num(1.0):
                return Call("log1p", (a.left,))
        return Call(node.func, args)
    left, right = rewrite(node.left), rewrite(node.right)
    if (isinstance(node, BinOp) and node.op == "-" and right == Num(1.0)
            and isinstance(left, Call) and left.func == "exp"):
        return Call("expm1", left.args)
    return type(node)(node.op, left, right)


# -- evaluation and derivatives ----------------------------------------------

#: the value each domain-restricted argument takes where its if() branch is
#: dead: inside every function's domain, away from every singular derivative
_SAFE = {"log": 1.0, "log1p": 0.0, "sqrt": 1.0, "asin": 0.0, "acos": 0.0,
         "pow_base": 1.0, "divisor": 1.0}

#: Gauss-Legendre nodes and weights on [0, 1] for the Debye function, and the
#: switch to the exponential tail; 32 nodes keep D₁ within 4e-15 of an
#: mpmath quadrature below |x| = 10 (WP-1964's measurement)
_GL_U, _GL_W = np.polynomial.legendre.leggauss(32)
_GL_U, _GL_W = (_GL_U + 1.0) / 2.0, _GL_W / 2.0
_DEBYE_TAIL = 10.0
_DEBYE_TAIL_TERMS = 5


def _is_bool(v) -> bool:
    return isinstance(v, bool | np.bool_)


def _and(xp, a, b):
    if _is_bool(a) and _is_bool(b):
        return bool(a) and bool(b)
    return xp.where(a, b, False)


def _or(xp, a, b):
    if _is_bool(a) and _is_bool(b):
        return bool(a) or bool(b)
    return xp.where(a, True, b)


def _not(xp, a):
    if _is_bool(a):
        return not bool(a)
    return xp.where(a, False, True)


def _guard(xp, live, arg, safe: float):
    """``arg`` where the branch is live, ``safe`` where it is dead."""
    if live is None or live is True:
        return arg
    return xp.where(live, arg, safe)


def _debye_g(xp, s):
    """g(s) = s/(eˢ − 1), g(0) = 1, its Taylor series below |s| = 0.1."""
    small = xp.abs(s) < 0.1
    s_safe = xp.where(small, 1.0, s)
    series = 1.0 - s / 2.0 + s * s / 12.0 - s ** 4 / 720.0 + s ** 6 / 30240.0 \
        - s ** 8 / 1209600.0
    return xp.where(small, series, s_safe / xp.expm1(s_safe))


def _debye_tail(xp, x):
    """D₁(x) for x ≥ 10: (π²/6 − Σₖ e^{−kx}(x/k + 1/k²))/x."""
    acc = 0.0 * x
    for k in range(1, _DEBYE_TAIL_TERMS + 1):
        acc = acc + xp.exp(-k * x) * (x / k + 1.0 / (k * k))
    return (math.pi ** 2 / 6.0 - acc) / x


def debye(x, xp=None):
    """The first Debye function D₁(x) = (1/x)∫₀ˣ t/(eᵗ − 1) dt, D₁(0) = 1.

    Debye (1912), *Ann. Phys.* 39, 789; Abramowitz & Stegun (1964) § 27.1.
    Element-wise on any ``xp``: a 32-node Gauss-Legendre rule on
    D₁(x) = ∫₀¹ g(xu) du with g(s) = s/(eˢ − 1) for |x| < 10, the exponential
    series of the tail for x ≥ 10, and D₁(x) = D₁(−x) − x/2 below −10 (since
    g(−s) = g(s) + s).
    """
    xp = _numpy_xp() if xp is None else xp
    x_mid = xp.where(xp.abs(x) < _DEBYE_TAIL, x, 0.0)
    total = 0.0 * x
    for u, w in zip(_GL_U, _GL_W, strict=True):
        total = total + float(w) * _debye_g(xp, x_mid * float(u))
    x_hi = xp.where(x >= _DEBYE_TAIL, x, _DEBYE_TAIL)
    x_lo = xp.where(x <= -_DEBYE_TAIL, -x, _DEBYE_TAIL)
    return xp.where(x >= _DEBYE_TAIL, _debye_tail(xp, x_hi),
                    xp.where(x <= -_DEBYE_TAIL, _debye_tail(xp, x_lo) - x / 2.0, total))


def debye_derivative(x):
    """dD₁/dx = 1/(eˣ − 1) − D₁(x)/x, numpy; its series −1/4 + x/18 − x³/900 +
    x⁵/35280 − x⁷/1209600 below |x| = 0.1, where the closed form cancels."""
    x = np.asarray(x, dtype=np.result_type(x, np.float64))
    small = np.abs(x) < 0.1
    xs = np.where(small, 1.0, x)
    closed = 1.0 / np.expm1(xs) - debye(xs) / xs
    series = -0.25 + x / 18.0 - x ** 3 / 900.0 + x ** 5 / 35280.0 - x ** 7 / 1209600.0
    return np.where(small, series, closed)


def _numpy_xp():
    from ..backend.api import NumpyBackend
    return NumpyBackend()


class _Eval:
    """One walk computing a value and, on request, its partials.

    ``wrt`` empty: values only, on any ``xp``.  ``wrt`` given: forward-mode
    partials too, on numpy (a traced backend differentiates the values).
    """

    def __init__(self, xp, env: Mapping[str, Any], wrt: Sequence[str]):
        self.xp = xp
        self.env = env
        self.wrt = frozenset(wrt)
        self.numpy = getattr(xp, "name", "") == "numpy"

    def __call__(self, node, live=None):
        if isinstance(node, Num):
            return self.lift(node.value), {}
        if isinstance(node, Name):
            if node.id in CONSTANTS:
                return self.lift(CONSTANTS[node.id]), {}
            if node.id not in self.env:
                hint = did_you_mean(node.id, self.env)
                raise ExpressionError(
                    "unbound", f"{node.id!r} has no value"
                    + (f"; {hint}" if hint else ""))
            v = self.lift(self.env[node.id])
            return v, ({node.id: 1.0} if node.id in self.wrt else {})
        if isinstance(node, Neg):
            v, d = self(node.arg, live)
            return -v, {k: -g for k, g in d.items()}
        if isinstance(node, BinOp):
            return self._binop(node, live)
        if isinstance(node, Call):
            return self._call(node, live)
        raise ExpressionError("type", "a condition where a number is needed")

    def lift(self, v):
        """A python or numpy number as this backend's fp64 value.

        IEEE arithmetic on every leaf: a python ``1.0 / 0.0`` raises where
        numpy's is infinite, and a frozen numpy array on the left of an
        operator against a traced value fails on torch (root CLAUDE.md,
        Conventions).  A value already the backend's own passes through.
        """
        if isinstance(v, float | int | np.floating | np.integer):
            return np.float64(v) if self.numpy else self.xp.asarray(
                float(v), dtype=np.float64)
        if isinstance(v, complex | np.complexfloating):
            return np.complex128(v) if self.numpy else self.xp.asarray(v)
        if isinstance(v, np.ndarray) and not self.numpy:
            return self.xp.asarray(v, dtype=v.dtype if v.dtype.kind == "c"
                                   else np.float64)
        return v

    def cond(self, node, live=None):
        xp = self.xp
        if isinstance(node, Compare):
            a, _ = self(node.left, live)
            b, _ = self(node.right, live)
            op = node.op
            return (a < b if op == "<" else a <= b if op == "<=" else
                    a > b if op == ">" else a >= b if op == ">=" else
                    a == b if op == "==" else a != b)
        if isinstance(node, BoolOp):
            a = self.cond(node.left, live)
            b = self.cond(node.right, live)
            return _and(xp, a, b) if node.op == "and" else _or(xp, a, b)
        if isinstance(node, Not):
            return _not(xp, self.cond(node.arg, live))
        raise ExpressionError("type", "a number where a condition is needed")

    @staticmethod
    def _add(da, db, sa=1.0, sb=1.0):
        out = {k: sa * g for k, g in da.items()}
        for k, g in db.items():
            out[k] = out[k] + sb * g if k in out else sb * g
        return out

    def _binop(self, node, live):
        xp = self.xp
        a, da = self(node.left, live)
        if node.op == "^":
            b, db = self(node.right, live)
            base = _guard(xp, live, a, _SAFE["pow_base"])
            v = xp.power(base, b)
            d: dict = {}
            if da:
                gb = b * xp.power(base, b - 1.0)
                d = {k: gb * g for k, g in da.items()}
            if db:
                lg = v * xp.log(_guard(xp, live, a, _SAFE["log"]))
                d = self._add(d, {k: lg * g for k, g in db.items()})
            return v, d
        b, db = self(node.right, live)
        if node.op == "+":
            return a + b, self._add(da, db)
        if node.op == "-":
            return a - b, self._add(da, db, 1.0, -1.0)
        if node.op == "*":
            return a * b, self._add({k: g * b for k, g in da.items()},
                                    {k: a * g for k, g in db.items()})
        div = _guard(xp, live, b, _SAFE["divisor"])
        v = a / div
        return v, self._add({k: g / div for k, g in da.items()},
                            {k: -v / div * g for k, g in db.items()})

    def _call(self, node, live):
        xp = self.xp
        f = node.func
        if f == "if":
            c = self.cond(node.args[0], live)
            live_a = c if live is None else _and(xp, live, c)
            live_b = _not(xp, c) if live is None else _and(xp, live, _not(xp, c))
            a, da = self(node.args[1], live_a)
            b, db = self(node.args[2], live_b)
            d = {}
            for k in set(da) | set(db):
                d[k] = xp.where(c, da.get(k, 0.0), db.get(k, 0.0))
            return xp.where(c, a, b), d
        if f in ("min", "max"):
            v, d = self(node.args[0], live)
            for arg in node.args[1:]:
                w, dw = self(arg, live)
                keep = (v <= w) if f == "min" else (v >= w)
                nv = xp.where(keep, v, w)
                d = {k: xp.where(keep, d.get(k, 0.0), dw.get(k, 0.0))
                     for k in set(d) | set(dw)}
                v = nv
            return v, d
        x, dx = self(node.args[0], live)
        if f in ("log", "log1p", "sqrt", "asin", "acos"):
            x = _guard(xp, live, x, _SAFE[f])
        if f == "exp":
            v = xp.exp(x)
            g = v
        elif f == "expm1":
            v = xp.expm1(x)
            g = v + 1.0
        elif f == "log":
            v = xp.log(x)
            g = 1.0 / x
        elif f == "log1p":
            v = xp.log1p(x)
            g = 1.0 / (1.0 + x)
        elif f == "sqrt":
            v = xp.sqrt(x)
            g = 0.5 / v if dx else None
        elif f == "sin":
            v = xp.sin(x)
            g = xp.cos(x) if dx else None
        elif f == "cos":
            v = xp.cos(x)
            g = -xp.sin(x) if dx else None
        elif f == "tan":
            v = xp.tan(x)
            g = 1.0 + v * v
        elif f == "asin":
            v = xp.arcsin(x)
            g = 1.0 / xp.sqrt(1.0 - x * x) if dx else None
        elif f == "acos":
            v = xp.arccos(x)
            g = -1.0 / xp.sqrt(1.0 - x * x) if dx else None
        elif f == "atan":
            v = xp.arctan(x)
            g = 1.0 / (1.0 + x * x)
        elif f == "abs":
            v = xp.abs(x)
            g = xp.sign(x) if dx else None
        elif f == "debye":
            v = debye(x, xp)
            g = debye_derivative(x) if dx else None
        else:  # pragma: no cover - FUNCTIONS and this chain are one list
            raise ExpressionError("unknown_function", f"unknown function {f!r}")
        return v, ({k: g * h for k, h in dx.items()} if dx else {})


class Expression:
    """One parsed expression: its text, its tree, its names, and how to run it.

    ``Expression("zero_a + grad/(exp(theta/T) - 1)")`` parses (raising
    :class:`ExpressionError`), and keeps the user's text.  :attr:`tree` is
    what was written; evaluation and derivatives run on the rewritten tree
    (:func:`rewrite`).
    """

    def __init__(self, text: str):
        self.text = text
        self.tree = parse(text)
        self._compiled = rewrite(self.tree)
        #: the free names, first use first, ``pi`` left out
        self.names: tuple[str, ...] = tuple(names_in(self.tree))

    def __repr__(self) -> str:
        return f"Expression({self.text!r})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Expression) and other.tree == self.tree

    def __hash__(self) -> int:
        return hash(self.tree)

    def to_text(self) -> str:
        """The tree printed canonically (:func:`to_text`)."""
        return to_text(self.tree)

    def inline(self, definitions: Mapping[str, Expression]) -> Expression:
        """This expression with each name in ``definitions`` replaced by its tree.

        How one equation feeds another: ``T_true`` defined as
        ``T + c1*T + c2*T^2`` and inlined into ``a0 + k*T_true`` gives one
        tree over ``T``, ``c1``, ``c2``, ``a0`` and ``k``, so its evaluation and
        its derivatives need nothing new.  A definition is inlined as it
        stands, so a caller inlines in declaration order and a definition
        naming a later one stays a free name, which is how a cycle shows up
        (as a name with no value).
        """
        def walk(n):
            if isinstance(n, Name):
                return definitions[n.id].tree if n.id in definitions else n
            if isinstance(n, Num):
                return n
            if isinstance(n, Neg | Not):
                return type(n)(walk(n.arg))
            if isinstance(n, Call):
                return Call(n.func, tuple(walk(x) for x in n.args))
            return type(n)(n.op, walk(n.left), walk(n.right))

        return Expression(to_text(walk(self.tree)))

    def evaluate(self, bindings: Mapping[str, Any], xp=None):
        """The value, element-wise over whatever ``bindings`` hold.

        ``xp`` is a backend namespace (``backend.get_backend()``); ``None``
        is numpy.  A name with no binding raises with code ``unbound``.
        """
        xp = _numpy_xp() if xp is None else xp
        if xp.name == "numpy":
            with np.errstate(all="ignore"):
                v, _ = _Eval(xp, bindings, ())(self._compiled)
            return v
        v, _ = _Eval(xp, bindings, ())(self._compiled)
        return v

    def gradient(self, bindings: Mapping[str, Any], wrt: Sequence[str]
                 ) -> tuple[np.ndarray, list[np.ndarray]]:
        """The value and ∂/∂name for each of ``wrt``, numpy, exact.

        A name the expression does not use has a zero partial.  Each partial
        has the value's shape.
        """
        xp = _numpy_xp()
        with np.errstate(all="ignore"):
            v, d = _Eval(xp, bindings, wrt)(self._compiled)
        v = np.asarray(v)
        out = [np.array(np.broadcast_to(np.asarray(d.get(k, 0.0)), v.shape),
                        dtype=v.dtype) for k in wrt]
        return v, out
