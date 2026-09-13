(ch-background)=
# Background

## Additive models, never subtraction

The background is part of the model in {eq}`fm-ycalc`, never subtracted
from the data: an estimated baseline is either held *additively* under the
refined polynomial or co-refined under a smoothness penalty. Refinable
models are Chebyshev polynomials, a fixed estimated baseline plus
Chebyshev, and a P-spline {cite}`eilers1996` — a B-spline basis whose
coefficients $c$ are disciplined by second-difference penalty rows appended
to the residual ({eq}`fm-rows`):

```{math}
:label: bg-penalty

r_{\mathrm{pen}} \;=\; \sqrt{\lambda}\, (D_2\, c),
```

*Source:* `rietx.background.models`

with $D_2$ the $(n-2) \times n$ second-difference matrix. The rows land in
$J^\top J$ (so the covariance is regularised) but are excluded from Rwp and
the serial-correlation statistics — they are soft observations, not data.

(explicit-humps)=
## Localised flexibility: explicit humps

The three models above are all *global* — a Chebyshev term and a spline
coefficient each act over a stretch of the pattern — so a background feature
confined to a few degrees is describable only by making the whole curve
flexible. The alternative is an additive Gaussian on the angle axis, one per
declared feature, summed on top of whichever model is in use:

```{math}
:label: bg-peak

y_{\mathrm{peak}}(2\theta) \;=\; h \,
\exp\!\left[-4\ln 2 \left(\frac{2\theta - 2\theta_0}{\Gamma}\right)^{\!2}\right].
```

*Source:* `rietx.background.models.hump_curve`

This is an **empirical basis function, not a peak shape**, and no physical
derivation is claimed for it: genuinely amorphous scattering is a Debye or
radial-distribution term in $Q$, not a Gaussian in angle. What is cited is the
practice — an explicit broad peak added to the background is what GSAS-II
exposes as a hump {cite}`toby2013` and what TOPAS exposes as a
cell-less "peaks phase" {cite}`coelho2018topas`.

Two consequences follow from the form. It is **nonlinear** in $2\theta_0$ and
$\Gamma$, unlike every term in {eq}`bg-penalty`'s block, so it stays out of the
linear design matrix and its Jacobian columns are finite differences of the
whole model rather than exact design rows. And it is not identifiable on its
own: $h$, $\Gamma$ and the low-order polynomial terms underneath it all raise
the same region of the curve, so what makes the term a *background* term is the
width. With $\Gamma_{\mathrm{inst}}(2\theta)$ the resolution function of
{eq}`prof-caglioti-g`-{eq}`prof-caglioti-l`, the admissible régime is

```{math}
:label: bg-peak-width

\Gamma \;\gtrsim\; m\,\Gamma_{\mathrm{inst}}(2\theta_0),
```

*Source:* `rietx.strategy.staged.HUMP_MIN_WIDTH_MULT`

with $m =$ {{ HUMP_MIN_WIDTH_MULT }}, below which the term is a
reflection with no cell and no structure factor behind it. The condition depends on the refined resolution parameters and on
$2\theta_0$ itself, so it is not a box constraint: like the Stephens strain
cone it is carried as a reported guard rather than enforced, and a firing means
the peak parameters are not quotable.

## Model-free estimation

Baseline estimators serve the fixed-plus-Chebyshev model and the automatic
pipeline. The Whittaker smoother {cite}`eilers2003` solves the banded
(pentadiagonal) system

```{math}
:label: bg-whittaker

(W + \lambda D_2^\top D_2)\, z \;=\; W y,
```

*Source:* `rietx.background.estimators`

for the baseline $z$ against the observed $y$, with $W$ the diagonal matrix
of channel weights and $\lambda$ the smoothing strength — the larger it is,
the more the second-difference term dominates and the stiffer $z$ becomes.
arPLS {cite}`baek2015` iterates it with asymmetric reweighting so
peaks are progressively excluded from the baseline. SNIP {cite}`ryan1988`
is available as an independent alternative.

## Choosing the flexibility

Two knobs — the Chebyshev order (or P-spline λ) and the estimator's λ —
are selected with the same two ingredients:

- **BIC on peak-masked channels** {cite}`schwarz1978`: background
  flexibility must be justified by the background channels only, so
  Bragg-peak channels (net > 3σ above a robust baseline) are masked out of
  $\mathrm{BIC} = m\ln(\mathrm{RSS}/m) + k\ln m$.
- **Durbin-Watson whiteness stopping** {cite}`durbin1950,hillflack1987`:
  $d = \sum(\Delta_i - \Delta_{i-1})^2 / \sum\Delta_i^2$ rises toward 2 as
  the background stops leaving serially correlated structure; past the
  stopping threshold, extra flexibility only chases noise. Masked channels
  are treated as contiguous, which makes the test slightly conservative —
  the safe direction.

*Source:* `rietx.background.select`

## Flexibility is a correctness question

A background able to imitate the peaks biases ADPs up and scales (hence
QPA fractions) down *while Rwp improves*. The right measure is the block
projection of a structural Jacobian column $j_i$ onto the span $B$ of the
background columns:

```{math}
:label: bg-absorption

R^2_i \;=\; 1 - \frac{\lVert j_i - P_B\, j_i \rVert^2}{\lVert j_i \rVert^2},
```

*Source:* `rietx.optimize.statistics.background_absorption`

the fraction of the parameter's effect the background can reproduce.
Pairwise correlation is the wrong statistic here: with ~100 spline
coefficients each individual $|\rho|$ stays small (~0.2) while the block
collectively absorbs ~50 % of the parameter (measured). The projection must
include the penalty rows of {eq}`bg-penalty` — they are what makes a stiff
background unable to imitate a peak, and dropping them overstates the risk
by ~5×.
