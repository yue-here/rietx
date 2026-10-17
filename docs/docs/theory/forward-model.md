(ch-forward)=
# The forward model

This chapter states the equation that turns a structure, an instrument and a source into a calculated powder pattern.

A constant-wavelength powder pattern is modelled as a background plus a
triple sum over phases $p$, source emission lines $l$ and reflections $k$:

```{math}
:label: fm-ycalc

y_{\mathrm{calc}}(2\theta_i) \;=\; y_{\mathrm{bkg}}(2\theta_i)
\;+\; \sum_p \sum_l \sum_k I_{pk}\, w_l\, \Omega_{lk}(2\theta_i)
\qquad [\text{counts}]
```

{source}`rietx.model.forward`

Each emission line (Kα₁/Kα₂, …) diffracts at its own Bragg angle, so the
doublet splitting grows with $\tan\theta$, as in {eq}`pos-doublet`. It is not a
fixed $2\theta$ offset. The line weight $w_l$ is the intensity of line $l$
relative to line 0. Line 0 itself is locked at 1, because its weight is
degenerate with the phase scales.

The three factors carry the units of {ref}`sec-units`.
$\Omega_{lk}$ is a unit-area profile (chapter {ref}`ch-profiles`), so it is a
density on the angle axis, in deg⁻¹. $w_l$ is a ratio. The reflection intensity
$I_{pk}$ is therefore an area, in counts·deg 2θ: what the line integrates to,
and not the height it reaches. That is the conversion a reader coming from
another code needs most often.

## Three intensity models

### Rietveld mode

Intensities come from the structural model {cite}`rietveld1969`:

```{math}
:label: fm-rietveld

I_{pk} \;=\; S_p \cdot m_{pk} \cdot |F_{pk}|^2 \cdot \mathrm{Lp}(2\theta_{lk}),
```

{source}`rietx.model.forward`

with phase scale $S_p$, multiplicity $m_{pk}$ (chapter {ref}`ch-intensities`),
structure factor $|F|^2$ in e² and the Lorentz-polarisation factor Lp (chapter
{ref}`ch-corrections`). Everything but $S_p$ is fixed by the model, so the
scale is what turns e² into the counts·deg 2θ of $I_{pk}$. Its value carries no
meaning on its own. It is meaningful against the other phases' scales, and the
quantitative fractions of {eq}`corr-qpa` are therefore ratios. $|F|^2$ depends
only on $\sin\theta/\lambda = 1/2d$ and is shared across emission lines. Lp is
evaluated per line.

### Le Bail mode

Intensities are empirical per-$hkl$ values {cite}`lebail1988`, updated between
least-squares cycles by observed-intensity partitioning summed over lines:

```{math}
:label: fm-lebail

I_k \;\leftarrow\;
\frac{\sum_l \sum_i \bigl[I_k\, w_l\, \Omega_{lk,i} / y_{\mathrm{bragg},i}\bigr]
      \cdot \max(y_{\mathrm{obs},i} - y_{\mathrm{bkg},i},\, 0)}
     {\sum_l w_l \sum_i \Omega_{lk,i}},
```

{source}`rietx.model.forward.CompiledModel.lebail_update`

Here $y_{\mathrm{bragg},i}$ is the Bragg part of {eq}`fm-ycalc` at point $i$.
It sums over every phase and leaves out the background. The bracket is then
reflection $k$'s share of the calculated Bragg intensity at that point, and the
shares sum to 1 at each point. The update is a fixed point when $y_{\mathrm{obs}} = y_{\mathrm{calc}}$. The
extracted intensities live outside the parameter vector and are path-dependent,
so a history node serialises them beside the parameters it stores.

### Pawley mode

The per-$hkl$ intensities sit inside the least-squares problem
{cite}`pawley1981`, as an off-table parameter block appended to $\theta$.
Equation {eq}`fm-lebail` is then used once, to seed the block before the first
solve. Reflections whose primary-line centres sit within
{{ PAWLEY_OVERLAP_FWHM_FRAC }} × their mean FWHM form an overlapped group and
receive a soft equal-split restraint, scaled so that the split-direction esd is
of order the group intensity itself. An unresolved split is then reported at
≈100 % uncertainty, where a bare pseudo-inverse of a singular $J^\top J$ would
report a spuriously tight one. Such groups come back flagged
`PAWLEY_OVERLAP_UNRESOLVED`.

The reflection list runs 0.5° past each end of the fitted window, so that a
reflection a stage moves onto the data is modelled. A reflection with no
emission line centred on the data reaches it only through a tail, so its column
is nearly zero and its intensity is bounded below only. Each such reflection
gets one more row in the same block, a ridge toward zero,

```{math}
:label: fm-pawley-ridge

r_k \;=\; \frac{\sqrt{\lambda}}{s_p}\, I_k,
\qquad s_p = \max_{j\,\text{on the data}} I_j ,
```

{source}`rietx.model.forward.CompiledModel.build_pawley_restraint`

where $s_p$ is the phase's largest on-data intensity when the stage starts.
An intensity the data do not determine then stays within $s_p$, with an esd of
that order. One the data do reach has a column far more precise than a prior
that wide. Without the ridge, a synthetic series refined one such intensity to
$10^{12}$, and TRF's step test, which is relative to $\lVert x\rVert$, ended
warm refits early (WP-1459). The result names the ridged reflections, one
`PAWLEY_OFF_DATA_RIDGED` diagnostic per phase, because their intensities are
the ridge's and not the data's.

## The residual row layout

The residual carries four blocks of rows, and the data is the first. The
layout,

```{math}
:label: fm-rows

r \;=\; \bigl[\; \text{data} \;\big|\; \text{background penalty}
\;\big|\; \text{Pawley restraint} \;\big|\; \text{soft restraint} \;\bigr],
```

{source}`rietx.model.rows`

is defined once, in `rietx.model.rows`. Every builder consumes it: the numpy
residual, the numpy Jacobian's row offsets, and the traced jax/torch residuals.
The data rows are $\sqrt{w_i}\,(y_{\mathrm{obs},i} - y_{\mathrm{calc},i})$. The
remaining blocks are described with the background models
({ref}`ch-background`) and the restraints ({ref}`ch-parameterisation`).

## Discreteness frozen per stage

Four things are computed when a stage is compiled and never change during a
least-squares run: the reflection list, the per-atom symmetry-operator subsets,
the per-(line, reflection) evaluation windows, and the FCJ quadrature node
counts. A window extends ±(k(η) · estimated FWHM + a floor + the FCJ smear
extent), with k(η) sized so that the discarded pseudo-Voigt area stays at or
below {{ WINDOW_AREA_TOL }} (`rietx.model.forward.window_fwhm_mult`).

Node positions and weights follow the parameters, smoothly. Freezing everything
else keeps the residual smooth for finite-difference and autodiff Jacobians.
Regeneration happens between stages.
