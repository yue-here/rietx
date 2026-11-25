(par-parametric-section)=
# A parameter as a function of each pattern's coordinates

This chapter holds one parameter of a joint fit to a declared function of each pattern's coordinates. It also gives the test of that form against the data.

A joint fit stacks $N$ patterns into one residual {cite}`vondreele1997`, each
pattern with its own parameter table and the shared parameters folded onto one
column each. Parametric refinement {cite}`stinton2007` holds one parameter to a
declared function of where each pattern sits. Pattern $k$ carries coordinates
$z_k$, a temperature down a ramp or a composition across a library, and its
value of the target is

```{math}
:label: par-parametric

p_k \;=\; \sum_{j=1}^{m} \Phi_{kj}\, c_j,
\qquad
\Phi_{kj} \;=\; \prod_{i \in t_j} u_i(z_k),
\qquad
u_i(z) \;=\; \frac{z_i - z_i^{\mathrm{ref}}}{s_i},
```

{source}`rietx.params.parametric.resolve_parametric`

where the term $t_j$ is a list of coordinate names, a repeated name being a
power and the empty term the intercept ($\Phi_{kj} = 1$), and the coefficients
$c_j$ are the refined parameters, shared by every pattern of the declared
subset. That is the polynomial basis. A design basis supplies $\Phi$ as the
caller's own matrix, and a constant basis is the single column of ones.

The function is linear in its coefficients, so it is exactly one affine tie of
{eq}`par-affine` per pattern, with $C_k = \Phi_k$ and $d = 0$. The tie needs no
derivative of its own: what each coefficient's column moves is read off $C$, as
for any tie. A function with a coefficient inside a power or an exponential (an
Arrhenius rate, an order-parameter exponent) is not of this form. It is a
formula equation ({ref}`par-formula-section`). A basis whose columns are collinear over the subset is refused before
any solve: pivoted QR on the column-normalised $\Phi$ names the dependent terms,
with its cut at $\sqrt{\mathrm{rcond}}$ of the leading diagonal, since an
eigenvalue of $\Phi^\top\Phi$ below the covariance's own cut would leave a
declared coefficient with no esd. Mixture fractions summing to one make the
intercept their sum, so the Scheffé form drops it.

The reference $z^{\mathrm{ref}}$ and scale $s$ are part of the declaration.
Left out, they are the mid-range and half-range of the subset's coordinates,
computed once when the declaration is resolved and stored with it, so a pattern
that joins later rebuilds $\Phi$ from the same numbers and never redefines a
coefficient. Centring makes the intercept's coefficient the target at
$z^{\mathrm{ref}}$ rather than an extrapolation to $z = 0$, and removes the intercept-slope correlation an
off-centre coordinate creates. The equilibration of the normal matrix before
{eq}`est-cov` fixes a column's scale and not that correlation, which is why the
declaration centres.

The coefficients are reported per unit of the coordinates themselves, at the
reference:

```{math}
:label: par-parametric-units

\tilde c_j \;=\; \frac{c_j}{\prod_{i \in t_j} s_i},
\qquad
\sigma(\tilde c_j) \;=\; \frac{\sigma(c_j)}{\prod_{i \in t_j} s_i},
```

{source}`rietx.params.parametric.coefficient_rows`

with $\sigma(c_j)$ from the joint covariance {eq}`est-cov`. So the intercept is
the target at the reference and the coefficient of a temperature its slope
there, in the target's unit per kelvin. A design coefficient is reported as
$\Phi$ defines it. A constant basis's one coefficient carries the target's own
bounds, intersected over the subset; a sum of terms has no box that holds every
pattern's target, so the coefficients are unbounded and a target that leaves
its range is reported after the fit.

When the coefficients are the only shared parameters and each pattern's own fit
is linear, profiling out each pattern's private parameters leaves a quadratic in
$p_k$ whose curvature is that pattern's own information. The joint $c$ is then
the generalised least-squares fit of {eq}`par-parametric` to the per-pattern
values, weighted by that information, and the declaration changes no number
that line through the separate fits' values would give. On a synthetic
ten-pattern ramp the joint slope sat a mean 0.0012 esd from that line. The joint form changes the
answer where a pattern's own likelihood is not Gaussian in $p_k$, such as a
minor phase near its detection limit, or where other parameters are shared as
well.

The coefficients' esds assume the declared form is right, so the fit tests
each declaration against the alternative that frees its target in every
pattern of the subset. In pattern $k$ a coefficient's column is
$\Phi_{kj}\,\partial r/\partial p_k$, so each pattern's own column for the
target is read off the coefficients' columns with no further evaluation. The
declaration is rejected when

```{math}
:label: par-parametric-form

\frac{\min_\beta \lVert r - J\beta \rVert^2
      - \min_\beta \lVert r - J_{\mathrm{u}}\beta \rVert^2}
     {\chi^2_{\mathrm{red}}} \;>\; c_k,
\qquad F_k(c_k) = \gamma,
```

{source}`rietx.params.parametric.form_tests`

with $r$ the weighted residual at the answer and $J$ its free columns, less any
the fit left on a bound. $J_{\mathrm{u}}$ is $J$ with the declaration's
coefficient columns replaced by each subset pattern's own target column. A
pattern that cannot see the target is left out of $J_{\mathrm{u}}$, as an
untied fit would hold the target there. $k$ is the number of directions
$J_{\mathrm{u}}$ adds past the covariance's cut, the subset's size less $m$
when nothing is degenerate. $F_k$ is the $\chi^2_k$ distribution function,
and $\gamma$ = {{ PARAMETRIC_FORM_LEVEL }}. Each minimisation is one linear
step, so the numerator is the score statistic of {eq}`est-suggest` for $k$
columns at once {cite}`rao1948`, and the test needs no refit. The denominator
is the answer's own $\chi^2_{\mathrm{red}}$, the restricted estimate the score
test takes. Dividing by the squared Bérar-Lelann factor of
{eq}`est-berar-lelann` as well, as an esd is inflated, made the test far
stricter than $\gamma$. On equations that must hold any smooth truth, over three
real ramps, none of 261 readings rejected with that factor and 12 of 242
(5.0 %) without it.

A fit with several declarations reads each one a second time, with the other
declarations' targets freed too. Let $J_{\mathrm{a}}$ swap every tested
declaration's coefficient columns and $J_{\mathrm{o}}$ every one but this. The
numerator is then the difference
$\min_\beta \lVert r - J_{\mathrm{o}}\beta \rVert^2 - \min_\beta \lVert r - J_{\mathrm{a}}\beta \rVert^2$,
and $k$ is the difference of their directions. That reading does not assume the other
declarations' forms, and the declaration is rejected when it passes its cut.
Two declarations whose target columns are nearly collinear can each pass this
way while both are wrong, because each one's columns absorb the other's
misfit. So the fit is also read once with $J_{\mathrm{a}}$ in place of
$J_{\mathrm{u}}$, every tested declaration swapped at once and $k$ their
directions together. That joint reading rejects the set and names no
declaration in it.

On the 33-pattern ZrMo₂O₈ ramp the numerator was 0.98-1.04 of the $\chi^2$ a
full untied refit removed, for the strong phase's equations and for three equations
together, and the verdict matched the refit's on all five equations tested. At the
three-equation answer, the second reading of the cubic equation's numerator was 575.3,
against the 576.1 a refit of that equation alone removed. A pattern that cannot see
the target adds nothing to the numerator, so the test
cannot check how a form carries through the patterns where the target is
invisible. On synthetic ramps whose minor phase faded out, or was broad and
overlapped, a bent truth was not rejected in 20 seeds of 20, as it did under a
full untied refit, and no straight truth was rejected in 40.

(par-formula-section)=
## A formula equation

A formula equation sets the target in pattern $k$ to a function the caller
writes in the grammar of [Expressions](../reference/expressions.md):

```{math}
:label: par-formula

p_k \;=\; f(v, z_k),
\qquad
\frac{\partial r}{\partial v_i} \;=\; \sum_k
  \frac{\partial r}{\partial p_k}\,\frac{\partial f}{\partial v_i}(v, z_k),
```

{source}`rietx.params.derived.ExpressionBlock`

where $v$ are the variables and $z_k$ the pattern's coordinates. A variable is
one refined column, shared by every formula that names it, so $f$ may be
nonlinear in it. A variable the sharing map makes per-pattern is one column
per pattern instead, Stinton and Evans's temperature offset {cite}`stinton2007`.
In each pattern the target is a derived row, written from the variables at
each evaluation, and $\partial f/\partial v_i$ is exact: the grammar has one
derivative rule per operator, checked against the complex-step derivative over
random trees. A formula that names an earlier formula has that formula's tree
substituted in, so a temperature calibration feeding three cell edges is one function
of the variables per edge.

The equation is evaluated anywhere through its gradient in the variables at the
answer $\hat v$:

```{math}
:label: par-formula-esd

\sigma\bigl(f(\hat v, z)\bigr) \;=\; \sqrt{g\,\Sigma_v\,g^{\top}},
\qquad
g \;=\; \frac{\partial f}{\partial v}\bigg|_{\hat v,\, z},
```

{source}`rietx.schemas.parametric.RefinedParametricEquation.evaluate`

with $\Sigma_v$ the variables' covariance from the joint solve. A held variable
has a zero row and column. At a pattern's own coordinates this is that
pattern's target row, value and esd. On two synthetic twelve-pattern ramps,
an order parameter through $T_c$ and an Avrami fraction against time, the
value ± 2 esd covered every true variable in 96 to 100 of 100 noise seeds.

The form test {eq}`par-parametric-form` needs each pattern's own target column,
which a formula's variables carry only in combination. In pattern $k$ the
variables' columns are $J_{V,k} = T_k G_k$, with $T_k$ the targets' columns and

```{math}
:label: par-formula-form

T_k \;=\; J_{V,k}\, G_k^{+},
\qquad
(G_k)_{ij} \;=\; \frac{\partial f_i}{\partial v_j}(\hat v, z_k),
```

{source}`rietx.params.parametric.expression_target_columns`

where $G_k^{+}$ is the pseudo-inverse. One variable may feed several targets,
so they are recovered together. A pattern where $G_k$ has fewer independent
rows than targets gives none of them, and neither does one where a variable
moves a row no formula writes. The alternative then drops only the variables
no other formula reads. Written as a polynomial and as a formula, one straight
line gave the same statistic to $7 \times 10^{-11}$ relative. A line written
over a cell that followed an Einstein function read 17 222 against a cut of
7.8, and the Einstein formula read 1.2.
