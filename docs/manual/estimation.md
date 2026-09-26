(ch-estimation)=
# Estimation

## Objective and weights

```{math}
:label: est-obj

S(\theta) \;=\; \sum_i w_i \bigl(y_{\mathrm{obs},i}
- y_{\mathrm{calc},i}(\theta)\bigr)^2,
\qquad w_i = 1/\sigma_i^2,
```

{source}`rietx.optimize.least_squares`

minimised over the residual rows of {eq}`fm-rows` {cite}`rietveld1969`.
Weights come from the data file's esd column whenever it is present;
Poisson $\sigma = \sqrt{\max(y, 1)}$ is only the fallback for bare counts.

The Jacobian is assembled column by column, taking exact work wherever it
exists: linear background columns, analytic peak-chain columns (everything
flowing through per-peak position, width, mixing and intensity), analytic
site-DOF columns for coordinates and anisotropic ADPs over the frozen operator
subsets, analytic axial columns for the FCJ apertures, and plain forward
differences as the fallback.
Under a differentiable backend the same residual is traced and columns
come from forward-mode autodiff, whose cost scales with the parameter
count {cite}`nocedal2006`; every backend is held to per-column agreement
with the analytic Jacobian.

## Agreement statistics

Defined per Toby {cite}`toby2006`:

```{math}
:label: est-indices

R_{wp} = \sqrt{\frac{\sum w (y_o - y_c)^2}{\sum w y_o^2}}, \qquad
R_{\exp} = \sqrt{\frac{N - P}{\sum w y_o^2}}, \qquad
\chi^2_{\mathrm{red}} = \frac{\sum w (y_o - y_c)^2}{N - P},
```

{source}`rietx.optimize.statistics`

with $\mathrm{GoF} = \sqrt{\chi^2_{\mathrm{red}}} = R_{wp}/R_{\exp}$, plus
the background-subtracted $R_{wp}$ variant Toby recommends when the
background carries much of the raw intensity. The Durbin-Watson statistic
on weighted residuals {cite}`hillflack1987` flags serial correlation
($d \approx 2$ ⇒ uncorrelated).

Across the shipped corrections, $\Delta R_{wp}$ recurs as a poor judge of a
physical improvement ({ref}`ch-corrections`, {ref}`ch-method`). These indices
measure agreement, and correctness is a separate question.

## Structure agreement indices

Those indices compare profiles. The two that compare the *structure* are
unweighted sums over reflections {cite}`mccusker1999` (their eqs 13 and 14):

```{math}
:label: est-structure-r

R_B = \frac{\sum_{hkl} \bigl| I_o - I_c \bigr|}{\sum_{hkl} I_o},
\qquad
R_F = \frac{\sum_{hkl} \bigl| |F_o| - |F_c| \bigr|}{\sum_{hkl} |F_o|},
\qquad I_{hkl} = m\,|F_{hkl}|^2,
```

{source}`rietx.optimize.statistics.structure_r_factors`

with $m$ the reflection multiplicity, so $|F| = \sqrt{I/m}$ and $R_F$ is the
index a single-crystal $R$ is comparable with. Powder data measure neither sum
directly. $I_o$ is the observed profile partitioned in proportion to $I_c$, the
same partition {ref}`ch-intensities` performs for Le Bail extraction, evaluated
once on the converged structural model. Two consequences follow from the
definition itself.

Both indices are biased towards the model being tested, because a wrong model
receives the intensity it predicted. The paper introduces them for monitoring a
structure's improvement, and not for judging one in isolation. Both are also
unweighted, so a reflection the weighted fit barely constrains counts as much as
one that dominates it. No weighted variant is computed here, and a trace phase's
$R_B$ does not compare with the major phase's.

## The effective observation count

$N$ in {eq}`est-indices` counts profile steps, and the steps across one peak
are repeated measurements of one number. Only the integrated intensities of
individual reflections are unique observations {cite}`mccusker1999`, and
overlap reduces even those: two reflections at one $2\theta$ are one
observation, and two that partly overlap lie between one and two, because the
profile shape still says how to split them. Altomare et al.
{cite}`altomare1995` make that a count,

```{math}
:label: est-mind

M_{\mathrm{ind}} = \sum_k \frac{I'_k}{I_k},
\qquad
I'_k = I_k - \int_{\chi_k} |F_k|^2\, G(\Delta 2\theta_k)\, \mathrm{d}(2\theta),
```

{source}`rietx.optimize.statistics.effective_observations`

where $G$ is the symmetric profile of {ref}`ch-profiles` and $\chi_k$ is the
part of reflection $k$'s own interval ($\pm${{ EFFECTIVE_OBS_ALPHA }} FWHM) on
which some overlapping reflection stands higher. An isolated line contributes 1
and the weaker of an exactly coincident pair contributes 0, so the pair is one
observation. The guideline built on it asks for at least
{{ OBS_PER_PARAMETER_MIN }} and preferably {{ OBS_PER_PARAMETER_PREFERRED }}
effective observations per structural parameter. Those are the atomic ones,
since peak positions rather than intensities pay for the cell, profile and
background terms.

The estimate is not a theorem, and both papers say so: the approach "may not
have a rigorous basis". Its own $\alpha$ is a case in point. The paper's check
at $\alpha = 4$ lands 6.5 % lower on average, so the value tabulated at
$\alpha = 2$, reported here for comparability with it, runs a little
generous.

## Esds and the Bérar-Lelann inflation

```{math}
:label: est-cov

\mathrm{Cov} \;=\; \chi^2_{\mathrm{red}} \cdot (J^\top J)^{-1},
\qquad \mathrm{esd}_i = \sqrt{\mathrm{Cov}_{ii}} \cdot
\sqrt{\chi'^2 / \chi^2},
```

{source}`rietx.optimize.least_squares.covariance_estimates`

where the second factor is the Bérar-Lelann serial-correlation inflation
{cite}`berar1991`. Consecutive same-sign weighted residuals are summed
coherently, $\chi'^2 = \sum_{\mathrm{runs}} (\sum_{i\in\mathrm{run}}
\delta_i)^2 \ge \chi^2$, because serially correlated neighbours do not carry
independent information. The estimator is conservative: even white residuals
land at an expected factor ≈1.51, so read it as an upper bound on the
serial-correlation esd damage. Andreev's serial-correlations figure of merit
{cite}`andreev1994` removes that bias by carrying the correlation into the
minimised quantity itself.

Reported esds carry the inflation. The correlation matrix does not. It is the
true Pearson matrix, so a genuinely degenerate pair reports $|\rho| \approx 1$
and the 0.98 high-correlation guard means what it says. Values are quoted with
two-significant-figure su's per the IUCr convention
{cite}`schwarzenbach1989`.

## Esds of derived quantities

A bond length, an angle or a weight fraction is a function of the refined
parameters rather than one of them, and its esd is the quadratic form

```{math}
:label: est-derived

\sigma_f^2 \;=\; g^\top \mathrm{Cov}\, g,
\qquad g_i = \frac{\partial f}{\partial \theta_i},
```

{source}`rietx.model.geometry`

over the whole covariance of {eq}`est-cov`: "the whole correlation matrix, not
just the diagonal elements, should be included in the calculation"
{cite}`mccusker1999`. Dropping the off-diagonal terms looks conservative and is
not. Measured across the 88 interatomic distances of an 11-BM NAC structural
refinement, the diagonal-only number runs from 0.86 to 1.41 times the full one,
so it is as often too small as too large. Both are reported, so the difference
is visible. It exists only where the coordinates refine,
since a quantity depending on one free parameter has no off-diagonal term to
drop.

A derived esd is absent rather than zero whenever that form cannot be evaluated
honestly. Four cases qualify:

* no covariance at all (an evaluate-only pass, a replayed history node);
* no free parameter the quantity depends on;
* a $g^\top \mathrm{Cov}\, g$ that reaches zero by cancellation, detected as a
  variance below {{ VARIANCE_CANCELLATION_FLOOR }} of its own form's absolute
  terms. A symmetry-fixed 90° angle has exactly zero variance while its partials
  against $x$, $y$ and $z$ do not vanish, so the quadratic form lands on
  roundoff;
* an angle within {{ ANGLE_LINEARISATION_LIMIT_DEG }}° of 0° or 180°, where the
  angle is a stationary point of the coordinates and the linearisation the
  propagation rests on does not hold at all.

The quantity itself is exact in all four cases. Only its uncertainty is
withheld.

The partials are the restraint derivative chain of {eq}`par-restraint`
evaluated at $\sigma = w = 1$. A geometry row is a restraint row, so the two
cannot drift apart, and the weight scale of {eq}`par-restraint-weight` is kept
out of them for the same reason.

## Staged strategy and series

Parameter groups are freed cumulatively in the IUCr-guideline order
{cite}`mccusker1999`: scale and background first, then peak positions, then
profile widths. The discrete model state is regenerated between stages and
frozen within them. A series of related patterns (an in-situ ramp, a parametric
sweep) is chained by warm starts, and the result is a parameter trajectory,
path-dependent by construction. The chain can be run in both directions, and
parameters the two runs disagree on are flagged. That is the one check
separating a measured trajectory from an ordering artefact. True parametric
refinement across patterns {cite}`stinton2007` is out of scope.

## Solvers

The default driver is scipy's Trust Region Reflective. The bounded
Levenberg-Marquardt alternative implements Coelho's adaptive Marquardt
constant {cite}`coelho2018` over the bound-constrained conjugate-gradient
solve of the normal equations {cite}`coelho2005` (conjugate gradients per
{cite}`hestenes1952,polak1971`), with the system diagonally pre-conditioned to
$A_{ii} = 1$. That pre-conditioning makes λ dimensionless and lets the published
constants transfer. Conventions: $A = J^\top J$, $b = -J^\top r$, and the
paper's objective $S = r^\top r$ is $\chi^2$.

The driver earns its place on constraint vocabulary rather than speed. Box
bounds are enforced inside the linear solve, and linear inequalities on
functionals of θ are available as rows $T\theta \ge 0$, the shape of the
Stephens positivity cone ({ref}`ch-microstructure`), which no per-parameter box
can express. An answer that pressed the cone says so. Per-stage truncation
counts are recorded, and a `CONSTRAINT_ACTIVE` diagnostic fires for the
answer-producing stage, which is the one signal that a declared constraint was
active. Speed was measured at 0.74–1.04× against TRF, as expected: the
normal-equation solve is a minority of the runtime, so solver work is
Amdahl-bounded at ≈1.25× here. {ref}`ch-method` works through two places where
the Coelho papers disagree with their own text, and how measurement settled
them.

## Convergence

The Rietveld literature judges convergence by the final cycle's parameter
shifts against their own esds, rather than by a cost decrement
{cite}`mccusker1999` (their §7):

```{math}
:label: est-convergence

\max_i \; \frac{|\Delta \theta_i|}{\mathrm{esd}(\theta_i)}
\;\le\; \epsilon_{\mathrm{conv}},
```

{source}`rietx.optimize.least_squares.run_least_squares`

with the paper's band $\epsilon_{\mathrm{conv}} =$ {{ MAX_SHIFT_CONVERGED }}
quoted, never tuned. Both sides are measured in external parameter units.
$\Delta\theta$ is decoded exactly through the transform chain of
{ref}`ch-parameterisation`, and the esd is the chain-ruled physical one of
{eq}`est-cov`, because at finite step size an internal-space ratio is a
different number.

The measured value is `Statistics.max_shift_over_esd`, computed by the solver
from the final accepted step and copied onto the answer-producing stage's
statistics. Nothing else derives it, and it gates nothing. A converged Trust
Region Reflective solve at `ftol` $10^{-9}$ satisfies the criterion a fortiori
(measured $\sim 3\times 10^{-4}$ on the synthetic LaB₆ round trip), so the
information is on the other branch: a stage stopped on its iteration budget
reports how far it was still moving in esd units, and the same stage starved to
one iteration measures $\approx 14$. The value is withheld wherever it cannot
be measured: with no accepted step, no esds, an evaluate-only replay, or the
joint multi-pattern residual.

## The fp64 floor

The residual used for cost and statistics, and the parameter solve and
covariance, are always fp64 on host. A GPU backend may compute Jacobian columns
in fp32. Three properties set that asymmetry.

- The residual cancels. $\sqrt{w}(y_{\mathrm{obs}} - y_{\mathrm{calc}})$
  subtracts numbers of order 10⁵ counts to leave order 10², and fp32's ~7
  digits put an absolute error of order 10 counts into everything that reads it,
  which is ~10 % of the quantity just formed.
- The solve squares the conditioning {cite}`higham2002`:

```{math}
:label: est-cond

\operatorname{cond}(J^\top J) \;=\; \operatorname{cond}(J)^2,
```

{source}`rietx.backend.linalg64`

  so a routine Rietveld $\operatorname{cond}(J) \sim 10^4$ leaves
  $\operatorname{cond}(J^\top J) \sim 10^8$, which fp32 cannot invert at all.
  The bounded LM forms $J^\top J$ explicitly, and is the direct illustration.
- Columns are relative-accuracy tolerant. A column enters through a descent
  direction and a curvature estimate, and the trust region re-measures every
  step against a fresh fp64 cost. Measured on real hardware, an Apple-GPU
  refinement with every column in fp32 lands 3.5×10⁻⁸ Å from the numpy fp64
  cell.

## From fit to report

The FitReport reads the converged state in three layers. Layer 0 is model-free:
cumulative-χ² breakpoints localise where misfit lives {cite}`david2004`, and
unindexed peaks are flagged against the tick positions of every emission line
(an impurity must clear {{ IMPURITY_SIGMA }}σ). Layer 1 attributes per-region
misfit to profile shape derivatives, under four gates (resolvability on the
scale-normalised Gram, a validity radius, local-χ² significance, global
maturity), so a collinear pair is declared non-separable rather than resolved
into a confident wrong singleton. Layer 2 turns attributions into actions. The
actions are advisory and carry no statistical test of their own. Whether a
freed parameter pays for itself is ΔBIC {cite}`schwarz1978`, predicted before
the fit by `Refinement.suggest` and measured after it by
`report.compare_freed` (next section). The report's thresholds are versioned
(currently {{ THRESHOLDS_VERSION }}).

## Which parameter to free next

`Refinement.suggest()` ranks every held-but-refinable parameter by the χ²
reduction one Gauss-Newton solve would obtain from freeing it, at the cost
of a single Jacobian evaluation and no solve. With $F$ the currently-free
columns, $P_F$ the orthogonal projector onto their span, $r$ the weighted
residual and $J_j$ a held parameter's column,

```{math}
:label: est-suggest

\tilde{\jmath} = (I - P_F)\, J_j, \qquad
\tilde{r} = (I - P_F)\, r, \qquad
\Delta\chi^2_j \;=\; \frac{(\tilde{\jmath}^{\top} \tilde{r})^2}
                          {\tilde{\jmath}^{\top} \tilde{\jmath}},
```

{source}`rietx.optimize.statistics.one_parameter_gains`

which is Rao's score statistic {cite}`rao1948` applied to the linearised model,
computed through the Frisch-Waugh-Lovell projection identity
{cite}`frisch1933,lovell1963`. It is exactly the drop in $\sum w\Delta^2$ that
a least-squares solve of $[F \mid J_j]$ achieves over $F$ alone. It is invariant
under any rescaling of the column, so no per-parameter step heuristics are
needed. At a converged minimum $J^\top r \approx 0$ makes every gain vanish.
GSAS-II answers the same recipe problem {cite}`toby2024` by ±δ finite
differences with per-type δ heuristics and a sign-consistency test, because its
analytic derivatives are locked inside Hessian assembly. Exact columns at the
current state make all three workarounds unnecessary.

Under the null hypothesis a gain is distributed as
$\chi^2_1 \cdot \chi^2_{\mathrm{red}}$, so a candidate is quotable only above
a noise floor of {{ SUGGEST_MIN_GAIN }} · max(χ²_red, 1). That is the 3σ point
of $\chi^2_1$, with the same floor-at-one convention as the covariance scale.
Two gates keep the ranking honest, the Layer-1 discipline one call over. The
free block absorbs some candidates' columns, and those are reported
non-separable and carry no score; the same projection caps the $1/(1-R^2)$
inflation of near-collinear gains. Candidates whose projected columns are
pairwise indistinguishable come back as one unresolved group carrying a joint
gain, which is a tie. As with indexing there is no `.best`, and
`best_or_none()` answers `None` whenever the evidence does not choose one
parameter.

A gain that clears the floor is then read as a model-selection answer, ΔBIC
{cite}`schwarz1978`, and that needs a premise the gain does not: Schwarz's
$N$ counts independent observations. A powder residual is serially
correlated, and at raw channel counts the reward term
$N\ln(\chi^2_r/\chi^2_f)$ outvotes the $\ln N$ penalty for almost any
improvement. The fit already measures the correlation, as the Bérar-Lelann
factor $f$ every esd is inflated by {cite}`berar1991`, and the penalty is
charged at

```{math}
:label: est-effective-n

N_{\mathrm{eff}} = N / f^{2}, \qquad
\Delta\mathrm{BIC} = N_{\mathrm{eff}} \ln\frac{\chi^2_r}{\chi^2_f}
                     - k \ln N_{\mathrm{eff}},
```

{source}`rietx.optimize.statistics.effective_sample_size`

the count at which, for one added parameter, the reward term is that
parameter's $t^2$ at its inflated esd, so ΔBIC is positive exactly when
$t^2 > \ln N_{\mathrm{eff}}$. It is a heuristic and not a theorem, and it is
conservative the way the esds are: white residuals still give $f \approx
1.51$. Hamilton's test {cite}`hamilton1965` takes the same $N_{\mathrm{eff}}$,
so the two verdicts are read off one count. Measured on four ~49 500-channel
synchrotron fits of one occupancy, raw $N$ gave ΔBIC +36 to +211 to a
parameter each fit's own esd put within 0.76-1.89σ of zero, and
$N_{\mathrm{eff}}$ turned all four negative.

After the fit the same count prices the measured gain. `report.compare_freed`
takes the fit without a parameter and the fit with it, and returns
{eq}`est-effective-n` beside each freed parameter's $t$. The two agree for one
parameter, so their disagreement is information: a multi-parameter block whose
joint ΔBIC is positive while no member's $t$ clears 2, or an $f$ that moved
between the fits.
