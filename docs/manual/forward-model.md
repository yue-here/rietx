(ch-forward)=
# The forward model

A constant-wavelength powder pattern is modelled as a background plus a
triple sum over phases $p$, source emission lines $l$ and reflections $k$:

```{math}
:label: fm-ycalc

y_{\mathrm{calc}}(2\theta_i) \;=\; y_{\mathrm{bkg}}(2\theta_i)
\;+\; \sum_p \sum_l \sum_k I_{pk}\, w_l\, \Omega_{lk}(2\theta_i).
```

*Source:* `rietx.model.forward`

Each emission line (Kα₁/Kα₂, …) diffracts at its own Bragg angle, so the
doublet splitting grows with $\tan\theta$ — it is never a fixed $2\theta$
offset (see {eq}`pos-doublet`). The line weight $w_l$ is the intensity of
line $l$ relative to line 0, which is structurally locked at 1 because it is
degenerate with the phase scales. $\Omega_{lk}$ is a unit-area profile
(chapter {ref}`ch-profiles`), so the reflection intensity $I_{pk}$ enters
purely as an area.

## Three intensity models

**Rietveld mode** computes intensities from the structural model
{cite}`rietveld1969`:

```{math}
:label: fm-rietveld

I_{pk} \;=\; S_p \cdot m_{pk} \cdot |F_{pk}|^2 \cdot \mathrm{Lp}(2\theta_{lk}),
```

*Source:* `rietx.model.forward`

with phase scale $S_p$, multiplicity $m_{pk}$ (chapter {ref}`ch-intensities`),
structure factor $|F|^2$ and the Lorentz-polarisation factor Lp (chapter
{ref}`ch-corrections`). $|F|^2$ depends only on $\sin\theta/\lambda = 1/2d$
and is therefore shared across emission lines; Lp is evaluated per line.

**Le Bail mode** {cite}`lebail1988` treats the $I_{pk}$ as empirical
per-$hkl$ values, updated *between* least-squares cycles by
observed-intensity partitioning summed over lines:

```{math}
:label: fm-lebail

I_k \;\leftarrow\;
\frac{\sum_l \sum_i \bigl[I_k\, w_l\, \Omega_{lk,i} / y_{\mathrm{bragg},i}\bigr]
      \cdot \max(y_{\mathrm{obs},i} - y_{\mathrm{bkg},i},\, 0)}
     {\sum_l w_l \sum_i \Omega_{lk,i}},
```

*Source:* `rietx.model.forward.CompiledModel.lebail_update`

where $y_{\mathrm{bragg},i}$ is the Bragg part of {eq}`fm-ycalc` at point $i$
— the triple sum over **every** phase, without the background — so the
bracket is reflection $k$'s share of the calculated intensity there and the
shares sum to exactly 1 at each channel. The step is a fixed point when
$y_{\mathrm{obs}} = y_{\mathrm{calc}}$. The
extracted intensities live outside the parameter vector and are
path-dependent, so history nodes serialize them per node rather than
treating them as parameters.

**Pawley mode** {cite}`pawley1981` instead places the per-$hkl$ intensities
*inside* the least-squares problem, as an off-table parameter block appended
to $\theta$. Equation {eq}`fm-lebail` is then used exactly once, to seed the
block before the first solve. Reflections whose primary-line centres sit
within {{ PAWLEY_OVERLAP_FWHM_FRAC }} × their mean FWHM form an overlapped
group and receive a soft equal-split restraint, scaled so that the
split-direction esd is of order the group intensity itself — an unresolved
split is reported at ≈100 % uncertainty rather than with the spuriously
tight esd a bare pseudo-inverse of a singular $J^\top J$ would give. Such
groups come back flagged `PAWLEY_OVERLAP_UNRESOLVED`.

## The residual row layout

The least-squares residual is not just the data block. Its row layout,

```{math}
:label: fm-rows

r \;=\; \bigl[\; \text{data} \;\big|\; \text{background penalty}
\;\big|\; \text{Pawley restraint} \;\big|\; \text{soft restraint} \;\bigr],
```

*Source:* `rietx.model.rows`

is defined once, in `rietx.model.rows`, and every builder — the numpy
residual, the numpy Jacobian's row offsets, and the traced jax/torch
residuals — consumes it. The data rows are
$\sqrt{w_i}\,(y_{\mathrm{obs},i} - y_{\mathrm{calc},i})$; the remaining
blocks are described with the background models ({ref}`ch-background`) and
restraints ({ref}`ch-parameterisation`).

## Discreteness is frozen per stage

Everything discrete about the model — the reflection list, per-atom
symmetry-operator subsets, the per-(line, reflection) evaluation windows
(which extend ±(k(η) · estimated FWHM + a floor + the FCJ smear extent),
where k(η) is sized so the discarded pseudo-Voigt area stays at or below
{{ WINDOW_AREA_TOL }} — `rietx.model.forward.window_fwhm_mult`), and the FCJ
quadrature node counts — is computed when a
stage is compiled and never changes during a least-squares run. Only node
*positions* and weights follow the parameters, smoothly. This is what keeps
the residual smooth for finite-difference and autodiff Jacobians;
regeneration happens between stages only.
