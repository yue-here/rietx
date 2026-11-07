# Expressions

This page gives the grammar a parametric equation is written in: the numbers and names, the operators and their order, the functions, the conditions, the spellings it refuses, how an expression is evaluated and differentiated, and a conformance table.

An expression is text such as `zero_a + grad / (exp(theta / T) - 1)`.
Its names are refined variables, coordinates from the `CoordinateTable`, or equations declared before it.
The grammar is rietx's own.
It reads no TOPAS or GSAS-II file, and a translation from either program's spelling is in [Switching](../switching/index.md).

The grammar has a version, and this page describes version 1.
A change to what an expression means, or to what is accepted, moves the version.

## Numbers and names

A number is written in decimal, with an optional exponent: `3`, `0.5`, `.5`, `2.`, `1e-5`, `1.5E+3`.
A number never carries a sign.
`-2` is unary minus applied to `2`.
Every value is a 64-bit float.

A name starts with a letter or `_` and continues with letters, digits and `_`, in ASCII.
Names are case-sensitive, so `T` and `t` are two names.
`pi` is π.

These words are reserved, so no variable, coordinate or equation may take them:

- the operators `and`, `or` and `not`;
- the constant `pi`;
- every function name in {ref}`expr-functions`.

(expr-operators)=
## Operators

The operators bind from loosest to tightest in this order.

| Order | Operators | Groups | Takes | Gives |
|---|---|---|---|---|
| 1 | `or` | left to right | conditions | a condition |
| 2 | `and` | left to right | conditions | a condition |
| 3 | `not` | prefix | a condition | a condition |
| 4 | `<` `<=` `>` `>=` `==` `!=` | never chained | numbers | a condition |
| 5 | `+` `-` | left to right | numbers | a number |
| 6 | `*` `/` | left to right | numbers | a number |
| 7 | unary `-` and `+` | prefix | a number | a number |
| 8 | `^`, also written `**` | never chained | numbers | a number |

So `-x^2` is −(x²), and `2^-1` is 0.5.
An exponent is a signed number, name, call or parenthesised expression, so `x^-(a + b)` is allowed.
`8 / 4 / 2` is 1, and `8 - 4 - 2` is 2.

(expr-functions)=
## Functions

Every function is called with parentheses, as in `exp(x)`.
Trigonometric functions take and return radians.
To work in degrees, multiply by `pi / 180`.

| Function | Value | Derivative used |
|---|---|---|
| `exp(x)` | eˣ | eˣ |
| `expm1(x)` | eˣ − 1, accurate near 0 | eˣ |
| `log(x)` | natural logarithm | 1/x |
| `log1p(x)` | ln(1 + x), accurate near 0 | 1/(1 + x) |
| `sqrt(x)` | √x | 1/(2√x), infinite at 0 |
| `sin(x)`, `cos(x)`, `tan(x)` | x in radians | cos x, −sin x, 1 + tan²x |
| `asin(x)`, `acos(x)`, `atan(x)` | in radians | ±1/√(1 − x²), 1/(1 + x²) |
| `abs(x)` | \|x\| | the sign of x, 0 at 0 |
| `min(a, b, …)`, `max(a, b, …)` | two or more arguments | the derivative of the chosen argument; on a tie, the first |
| `if(c, a, b)` | `a` where the condition `c` holds, else `b` | the derivative of the chosen branch |
| `debye(x)` | the first Debye function $D_1(x) = \frac{1}{x}\int_0^x \frac{t}{e^t - 1}\,dt$, with D₁(0) = 1 | 1/(eˣ − 1) − D₁(x)/x, which is −1/4 at 0 |

`debye(x)` follows Abramowitz and Stegun § 27.1.
A Debye temperature $\theta_D$ enters as `debye(theta_D / T)`.
Below |x| = 10 it is a 32-point Gauss-Legendre rule on $\int_0^1 g(xu)\,du$, with $g(s) = s/(e^s - 1)$.
From x = 10 up it is the tail series (π²/6 − Σ e⁻ᵏˣ(x/k + 1/k²))/x.
Both agree with a 50-digit quadrature to 4 × 10⁻¹⁵ or better.

## Conditions

A condition is a comparison, or comparisons joined by `and`, `or` and `not`.
A condition appears only as the first argument of `if`.
An expression whose value is a condition is refused, because an equation's value is a number.

A condition carries no derivative.
`if(T < Tc, a * (1 - T / Tc)^beta, 0)` is therefore differentiable in `a`, `Tc` and `beta` on each side of $T_c$, and its derivative in `Tc` jumps at $T = T_c$.
Nothing is smoothed.
A smoothed step is written out, for example with `atan`.

## Refused spellings

Each refusal names the place in the text with a caret, and gives the error code in the conformance table's last column.

| Written | Code | Why |
|---|---|---|
| `x^y^z`, `2^-x^2` | `power_chain` | TOPAS reads `x^y^z` as `(x^y)^z` and python as `x^(y^z)`. Write the parentheses. |
| `2x`, `x y`, `2(x)` | `implied_multiplication` | `Tc` and `T c` would differ by a space. Write the `*`. |
| `a < b < c` | `comparison_chain` | Write `a < b and b < c`. |
| `ln(x)`, `Exp(x)` | `unknown_function` | The message suggests the nearest function. TOPAS's capitalised names are not aliases. |
| `exp` alone | `reserved` | A function is called. |
| `exp(1, 2)`, `min(1)` | `arity` | Each function takes the arguments in {ref}`expr-functions`. |
| `if(1, 2, 3)`, `x > 1` | `type` | A condition where a number is needed, or the other way round. |
| `x = 1`, `x && y`, `(1 + 2` | `syntax` | `=` is not an operator, and `and`, `or` and `not` are words. |

An expression is at most 4096 characters long, and nests at most 64 levels deep (`too_long`, `too_deep`).
A chain such as `x1 + x2 + … + x65` counts one level per term, so a sum of more than 64 terms is grouped in parentheses or split into intermediate equations.
A name with no value when the expression is evaluated is `unbound`, and the message suggests the nearest bound name.

## Evaluation

An expression is evaluated element by element in 64-bit floating point, with IEEE results.
`1 / 0` is infinite and `log(-1)` is NaN, and neither raises.
A parametric preview reports a non-finite value with the pattern it occurs at.

`if(c, a, b)` evaluates both branches, because a traced backend cannot skip one.
Inside a branch that is not taken, the argument of `log`, `log1p`, `sqrt`, `asin`, `acos`, the base of `^` and the divisor of `/` are replaced by a value inside the function's domain.
The value of the branch taken is unchanged, and no NaN from the other branch reaches a derivative.
So `if(x >= 0, sqrt(x), -1)` at x = −4 is −1, with a finite derivative.

Two rewrites are applied before an expression is evaluated or differentiated.
`exp(u) - 1` becomes `expm1(u)`, and `log(1 + u)` or `log(u + 1)` becomes `log1p(u)`.
Without the first, the Einstein term `grad / (exp(theta / T) - 1)` loses digits as θ/T → 0: at θ/T = 10⁻¹⁰ it is wrong in the eighth significant figure.
The text you wrote is kept and printed unchanged.

## Derivatives

Every derivative is exact.
On the numpy path each operator has one rule, the third column of {ref}`expr-functions` and the rules of the arithmetic operators.
The `jax` and `torch` backends differentiate the same evaluation by forward-mode automatic differentiation.

In `x^y`, the term $x^y \ln x \, \partial y$ enters only where `y` depends on a refined name.
So `x^2` has the derivative 2x for negative x, where ln x is undefined.

## Conformance table

Every evaluator in rietx answers every row of this table, on the `numpy`, `jax` and `torch` backends.
A number matches to a relative 10⁻¹³, and `inf` and NaN match exactly.
An error row expects the code shown.
The expected values were computed with `mpmath` at 50 digits, independently of rietx.

The table is the test: `tests/test_expression.py` reads it from this page.

| Expression | Bindings | Expected |
|---|---|---|
| `1 + 2 * 3` | none | 7.0 |
| `(1 + 2) * 3` | none | 9.0 |
| `2 ^ 3` | none | 8.0 |
| `2 ** 3` | none | 8.0 |
| `-2 ^ 2` | none | -4.0 |
| `2 ^ -1` | none | 0.5 |
| `(2 ^ 3) ^ 2` | none | 64.0 |
| `2 ^ (3 ^ 2)` | none | 512.0 |
| `8 / 4 / 2` | none | 1.0 |
| `8 - 4 - 2` | none | 2.0 |
| `--3` | none | 3.0 |
| `+x` | x=2 | 2.0 |
| `1e-5 * 1E+5` | none | 1.0 |
| `.5 + 1.` | none | 1.5 |
| `pi` | none | 3.141592653589793 |
| `x * y` | x=2, y=3 | 6.0 |
| `1 / 0` | none | inf |
| `0 / 0` | none | NaN |
| `log(-1)` | none | NaN |
| `sqrt(-1)` | none | NaN |
| `x ^ 0.5` | x=-1 | NaN |
| `exp(1)` | none | 2.718281828459045 |
| `expm1(1e-10)` | none | 1.00000000005e-10 |
| `exp(1e-10) - 1` | none | 1.00000000005e-10 |
| `log1p(1e-10)` | none | 9.9999999995e-11 |
| `log(1 + 1e-10)` | none | 9.9999999995e-11 |
| `log(exp(2))` | none | 2.0 |
| `sqrt(2)` | none | 1.4142135623730951 |
| `sin(pi / 6)` | none | 0.5 |
| `cos(pi)` | none | -1.0 |
| `tan(pi / 4)` | none | 1.0 |
| `asin(1)` | none | 1.5707963267948966 |
| `acos(-1)` | none | 3.141592653589793 |
| `atan(1)` | none | 0.7853981633974483 |
| `abs(-3)` | none | 3.0 |
| `min(3, 1, 2)` | none | 1.0 |
| `max(3, 1, 2)` | none | 3.0 |
| `if(x > 0, 1, 2)` | x=1 | 1.0 |
| `if(x > 0, 1, 2)` | x=-1 | 2.0 |
| `if(x > 0 and x < 2, 1, 2)` | x=3 | 2.0 |
| `if(not x > 0 or x == 5, 1, 2)` | x=5 | 1.0 |
| `if(x != 0, 1 / x, 0)` | x=0 | 0.0 |
| `if(x >= 0, sqrt(x), -1)` | x=-4 | -1.0 |
| `if(x <= 1, log(x), 0)` | x=-2 | NaN |
| `debye(0)` | none | 1.0 |
| `debye(1)` | none | 0.7775046341122482 |
| `debye(20)` | none | 0.08224670117820002 |
| `debye(-1)` | none | 1.2775046341122482 |
| `debye(-30)` | none | 15.05483113556151 |
| `zero_a + grad / (exp(theta / T) - 1)` | zero_a=7.29, grad=1e-5, theta=150, T=300 | 7.290015414940825 |
| `a * (1 - T / Tc) ^ beta` | a=2, T=100, Tc=300, beta=0.3 | 1.7709349865911121 |
| `x^y^z` | x=1, y=2, z=3 | error: `power_chain` |
| `2^-x^2` | x=1 | error: `power_chain` |
| `x^(y)^z` | x=1, y=2, z=3 | error: `power_chain` |
| `2x` | x=1 | error: `implied_multiplication` |
| `x y` | x=1, y=2 | error: `implied_multiplication` |
| `2(x)` | x=1 | error: `implied_multiplication` |
| `if(a < b < c, 1, 2)` | a=1, b=2, c=3 | error: `comparison_chain` |
| `ln(x)` | x=1 | error: `unknown_function` |
| `Exp(x)` | x=1 | error: `unknown_function` |
| `exp` | none | error: `reserved` |
| `exp(1, 2)` | none | error: `arity` |
| `min(1)` | none | error: `arity` |
| `if(1, 2, 3)` | none | error: `type` |
| `x > 1` | x=2 | error: `type` |
| `1 + (x > 1)` | x=2 | error: `type` |
| `x and y` | x=1, y=2 | error: `type` |
| `x = 1` | x=1 | error: `syntax` |
| `x & y` | x=1, y=2 | error: `syntax` |
| `(1 + 2` | none | error: `syntax` |
| `1 +` | none | error: `syntax` |
| `1e` | none | error: `syntax` |
| `y + 1` | x=1 | error: `unbound` |
