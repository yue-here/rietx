(ch-background)=
# Background

This chapter gives the background models, how flexible each should be, and the bias a background too flexible puts into the structure.

## Additive background models

The background is part of the model in {eq}`fm-ycalc`, and is never subtracted
from the data. An estimated baseline is held additively under the refined
polynomial, or co-refined under a smoothness penalty. Three models refine:
Chebyshev polynomials, a fixed estimated baseline plus Chebyshev, and a P-spline
{cite}`eilers1996`. The P-spline is a B-spline basis whose coefficients $c$ are
disciplined by second-difference penalty rows appended to the residual
{eq}`fm-rows`:

```{math}
:label: bg-penalty

r_{\mathrm{pen}} \;=\; \sqrt{\lambda\, m}\;\frac{D_2\, c}{\bar\sigma},
```

{source}`rietx.background.models.pspline_penalty_scale`

with $D_2$ the $(n-2) \times n$ second-difference matrix, $\bar\sigma$ the median
$\sigma$ over the fitted channels and $m = N/n$ the fitted channels per
coefficient, both frozen at stage compile. The coefficients carry the
intensity's unit and every data row is divided by its $\sigma$, so without
$\bar\sigma$ the penalty's weight would move by $k^2$ when the intensities and
their $\sigma$ are multiplied by $k$. Dividing by $\bar\sigma$ takes the unit
out of $\lambda$, and $m$ takes out the sampling density, because the data's
own weight on one coefficient grows as $m/\bar\sigma^2$. So $\lambda$ is a pure
number, the penalty's weight against the data's. A background feature of width
$W$ then costs about $\lambda (h/W)^4$ of the fit it buys, with $h$ the knot
spacing. That is derived, not measured, and its constant of order one is not
computed. Setting `lambda_units` to `"intensity"` drops both factors, which
gives the rows $\sqrt{\lambda}\, D_2 c$ that every fit used before and keeps
them as the bit-identical way back.

The rows land in $J^\top J$, so the covariance is regularised, and they are
excluded from $R_{wp}$ and the serial-correlation statistics. They are soft
observations rather than data.

(bg-lambda-counts)=
### What the pure number leaves to the counts

A pure λ fixes the penalty's weight against the data's, so it fixes the
*relative* bias a too-stiff spline leaves in a broad feature. The χ² that bias
costs grows with the feature's height in σ, so the same λ is stiffer, in what it
costs, on a better-counted pattern. Measured on the synthetic NAC capillary
pattern of `tests/test_air_scatter_undeclared.py` (0.005° steps,
`auto_background`'s 3° knots, a hump of FWHM about 8° and 900 counts over a
300-count level, no air rise), with every count multiplied by k:

| k | hump height / σ | χ²_red at λ = 1 | at λ = 0.1 | at λ = 0.01 |
|---|---|---|---|---|
| 0.01 | 2.6 | 1.137 | 1.111 | 1.105 |
| 0.1 | 8.2 | 1.301 | 1.079 | 1.039 |
| 1 | 26 | 3.764 | 1.478 | 1.060 |
| 10 | 82 | 28.44 | 5.489 | 1.293 |

The excess over the λ = 0.01 column grows about tenfold per decade of k, as
$(h/\sigma)^2$ would. `FitReport.background.worst_absorption` reads 0.02 in every
cell and `BACKGROUND_ABSORPTION` fires in none, so on this pattern the lower λ
buys the hump without reaching the lines. The rows are invariant to the step:
the k = 1 cell at λ = 1 reads 3.761 at 0.001° steps. The default stays 1. On a
well-counted pattern with a broad hump, the signature of a λ stiffer than the
data supports is the one `increase_background_flexibility` reports: an
off-region χ²_red well above 1 at a Durbin–Watson d well under 2 (here 4.04 and
0.48 at λ = 1, 1.08 and 1.79 at λ = 0.01). Lower `lambda_smooth` a decade at a
time, and read `worst_absorption` and `BACKGROUND_ABSORPTION` at each step before
keeping one.

(a-measured-background)=
## A measured background

The fixed curve can be a measurement rather than an estimate. An empty vanadium
can, a blank capillary, a matrix-only scan and an empty furnace are all scans of
everything the specimen is not. Such a curve enters as $f$, sampled onto the
pattern grid, with one refinable multiplier on it:

```{math}
:label: bg-measured

y_{\mathrm{bkg}}(2\theta) \;=\; \sum_n c_n T_n(x) \;+\; s\, f(2\theta).
```

{source}`rietx.model.forward.CompiledModel.background`

Both forms are TOPAS's `bkg_file` {cite}`coelho2018topas`, which takes the scale
as an argument or leaves it at one.

A blank is never on the specimen's scale. The two scans differ in monitor
normalisation and in counting time, and the specimen attenuates the container's
own scattering. The polynomial on top cannot repair that. It is additive, so it
moves the level and never rescales the shape, while the error in a fixed curve
is multiplicative. Quantitative phase analysis is the workflow least tolerant of
the difference, because what a wrong background level biases is the phase scales
and hence the weight fractions, while $R_{wp}$ improves.

The model is linear in $s$, so its Jacobian column is the sampled curve itself
and it joins the background's linear block. It is also largely parallel to the
constant Chebyshev term wherever the curve is not strongly featured. Large esds
on $s$ and on $c_0$ are then the correct report, and `HIGH_CORRELATION` is where
that surfaces.

The curve's own counting statistics, where it has them, enter the channel
weight:

```{math}
:label: bg-measured-weight

\sigma_i^2 \;=\; \sigma_{y,i}^2 \;+\; s^2\, \sigma_{f,i}^2 .
```

{source}`rietx.model.forward.compile_model`

That is what makes a short blank scan honestly worse than a long one. The $s$ in
it is the value the stage compiled at, frozen for the stage like every other
discrete choice. Two limits stand outside the formula. Interpolating a noisy
curve onto the pattern grid correlates neighbouring channels' errors, so the
propagated $\sigma$ is a lower bound unless the curve is smoothed first, and
smoothing is a modelling choice that belongs in the record. One blank reused
across a series carries error that is fully correlated rather than error that
averages down, so a refined scale that trends along a ramp is partly an artefact
of the single measurement.

A scalar is the leading-order correction rather than the exact one. The
container's scattering reaches the detector through the specimen in the sample
scan and through nothing in the blank scan, so the exact multiplier follows the
specimen transmission of {eq}`corr-rouse`. A single scale is therefore right per
pattern, and not as one constant across a temperature or atmosphere series.

(explicit-humps)=
## Explicit humps

The three models above are global. A Chebyshev term and a spline coefficient
each act over a stretch of the pattern, so describing a feature confined to a
few degrees means making the whole curve flexible. The alternative is an
additive Gaussian on the angle axis, one per declared feature, summed on top of
whichever model is in use:

```{math}
:label: bg-peak

y_{\mathrm{peak}}(2\theta) \;=\; h \,
\exp\!\left[-4\ln 2 \left(\frac{2\theta - 2\theta_0}{\Gamma}\right)^{\!2}\right]
\qquad [\text{counts}],
```

{source}`rietx.background.models.hump_curve`

This is an empirical basis function rather than a peak shape, and no physical
derivation is claimed for it. Genuinely amorphous scattering is a Debye or
radial-distribution term in $Q$. The citation is for the practice: GSAS-II
exposes an explicit broad background peak as a hump {cite}`toby2013`, and TOPAS
exposes one as a cell-less "peaks phase" {cite}`coelho2018topas`.

Two consequences follow from the form. It is nonlinear in $2\theta_0$ and
$\Gamma$, where every term in {eq}`bg-penalty`'s block is linear, so it stays
out of the linear design matrix and its Jacobian columns are finite differences
of the whole model. And it is not identifiable on its own. $h$, $\Gamma$ and the
low-order polynomial terms underneath it all raise the same region of the curve,
so the width is what makes the term a background term. With
$\Gamma_{\mathrm{inst}}(2\theta)$ the resolution function of
{eq}`prof-caglioti-g`-{eq}`prof-caglioti-l`, the admissible régime is

```{math}
:label: bg-peak-width

\Gamma \;\gtrsim\; m\,\Gamma_{\mathrm{inst}}(2\theta_0),
```

{source}`rietx.strategy.staged.HUMP_MIN_WIDTH_MULT`

with $m =$ {{ HUMP_MIN_WIDTH_MULT }}. Below that width the term is a reflection
with no cell and no structure factor behind it. The condition depends on the
refined resolution parameters and on $2\theta_0$ itself, so it cannot be a box
constraint. It is carried as a reported guard, like the Stephens strain cone,
and a firing means the peak parameters are not quotable.

## Model-free estimation

Baseline estimators serve the fixed-plus-Chebyshev model and the automatic
pipeline. The Whittaker smoother {cite}`eilers2003` solves the banded
(pentadiagonal) system

```{math}
:label: bg-whittaker

(W + \lambda D_2^\top D_2)\, z \;=\; W y,
```

{source}`rietx.background.estimators.whittaker_solve`

for the baseline $z$ under the observed counts $y$. $W$ is the diagonal matrix
of channel weights, $D_2$ the second-difference matrix and $\lambda$ the
smoothing strength. A larger $\lambda$ gives the second-difference term more
weight, so $z$ comes out stiffer. arPLS {cite}`baek2015` iterates the solve
with asymmetric reweighting so peaks are progressively excluded from the
baseline. SNIP {cite}`ryan1988`
is available as an independent alternative.

## Choosing the flexibility

Two knobs are selected with the same two ingredients: the Chebyshev order and
the estimator's smoothing strength. (The P-spline's smoothing strength is not
selected: `auto_background` fixes it at 1.0.)

- BIC on peak-masked channels {cite}`schwarz1978`. Background flexibility has to
  be justified by the background channels alone, so Bragg-peak channels (net
  > 3σ above a robust baseline) are masked out of
  $\mathrm{BIC} = m\ln(\mathrm{RSS}/m) + k\ln m$.
- Durbin-Watson whiteness stopping {cite}`durbin1950,hillflack1987`.
  $d = \sum(\Delta_i - \Delta_{i-1})^2 / \sum\Delta_i^2$ rises toward 2 as the
  background stops leaving serially correlated structure. Past the stopping
  threshold, extra flexibility chases noise. Masked channels are treated as
  contiguous, which makes the test slightly conservative, in the safe
  direction.

The two scans combine them differently. The order scan steps from 2 terms to
`max_order` (16 by default) and stops at the first $d \ge 1.8$. It returns the
lowest BIC among the orders it tried, so $d$ only ends the scan and never picks
the order. The arPLS scan steps from stiff to flexible and returns the first
smoothing strength with $d \ge 1.2$; its BIC is reported and decides nothing.

A scan can end at its cap without either ingredient deciding: BIC still
falling at `max_order` and $d$ short of the stop. The order returned is then
the cap and not a choice, and the selection says so with
`BACKGROUND_ORDER_AT_CAP`, naming the cap and the last $d$. On the 11-BM
Si 640c pattern this is the default's outcome, and a higher cap returns the
higher cap: each term gains 50-800 in BIC against a penalty $\ln m \approx 10$,
and the masked residual's serial correlation comes from profile misfit, which
no polynomial removes (issue #833).

{source}`rietx.background.select`

## Background flexibility and bias

A background able to imitate the peaks biases ADPs up, and scales (hence QPA
fractions) down, while $R_{wp}$ improves. The right measure is the block
projection of a structural Jacobian column $j_i$ onto the span $B$ of the
background columns:

```{math}
:label: bg-absorption

R^2_i \;=\; 1 - \frac{\lVert j_i - P_B\, j_i \rVert^2}{\lVert j_i \rVert^2},
```

{source}`rietx.optimize.statistics.background_absorption`

$R^2_i$ is the fraction of the parameter's effect the background can reproduce.
Pairwise correlation is the wrong statistic here. With ~100 spline coefficients
each individual $|\rho|$ stays small (~0.2), while the block collectively
absorbs ~50 % of the parameter (measured). The projection has to include the
penalty rows of {eq}`bg-penalty`: they stiffen the background against imitating
a peak, and dropping them overstates the risk by ~5×.
