(ch-convergence)=
# Convergence

This chapter states when the least-squares fit counts as converged, and the test that stops a plan's last stage.

## The criterion

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
Region Reflective solve at `ftol` $10^{-9}$ satisfies the criterion with a wide margin
(measured $\sim 3\times 10^{-4}$ on the synthetic LaB₆ round trip), so the
information is on the other branch: a stage stopped on its iteration budget
reports how far it was still moving in esd units, and the same stage starved to
one iteration measures $\approx 14$. The value is withheld wherever it cannot
be measured: with no accepted step, no esds, or an evaluate-only replay.

A joint multi-histogram fit has the same quantity over its joint $\theta$. Each
column has one shift, the joint solve's last accepted step. It has one esd,
from the covariance of the weighted stacked residual. The histogram weights
enter both, so they change the number and leave the criterion as it is. A
shared column appears in every histogram's table with the same ratio, because
each table decodes it affinely.

## The stop on the last stage

Since 1.13 the same band also ends the last stage of a plan. At each
iteration the driver solves {eq}`est-lm-step` once more with $\lambda = 0$,
over the same limits and rows. That is the Gauss-Newton step, the shift an
undamped final cycle would make. The stage stops before stepping when no free
parameter's Gauss-Newton shift reaches a fraction $\epsilon_{\mathrm{stop}}$ of
its esd:

```{math}
:label: est-shift-stop

\max_i \; \frac{|\Delta^{\mathrm{GN}}_i|}{\sigma_i} \;<\; \epsilon_{\mathrm{stop}},
\qquad
\sigma_i^2 \;=\; \min\bigl(\chi^2_\nu,\, 1\bigr) \,\bigl(A^{+}\bigr)_{ii},
```

{source}`rietx.optimize.lm._max_shift_over_esd`

with $\epsilon_{\mathrm{stop}} =$ {{ MAX_SHIFT_CONVERGED }} by default, McCusker's
band. Here $\chi^2_\nu$ is $\chi^2$ over the driver's rows less its free
parameters. $A^{+}$ inverts the equilibrated normal matrix as {eq}`est-cov`
does, without the Bérar-Lelann factor. `StageResult.termination` then reads
`shift_over_esd`.

The damped step cannot stand in for the Gauss-Newton one. A large $\lambda$
shrinks every shift, so a solve crawling towards its minimum would pass the
test while far from it.

The esd scales with $\chi^2_\nu$ only up to 1. Scaling an esd by $\chi^2_\nu$
assumes the residual left is noise, which holds only near the minimum. Far
from the data $\chi^2_\nu$ measures the misfit, and every $\sigma_i$ is too
wide by its square root. Tutorial 05's 2 % cell jump, refitted warm, reached
$\chi^2_\nu = 632$ in one step. The next Gauss-Newton step read 0.076 of the
scaled esd and 1.9 at $\chi^2_\nu = 1$. On the scaled esd the stage stopped
there, at $R_{wp}$ 0.966 with the cell 2 % short. With the cap it goes on to $R_{wp}$
0.039. The value $\chi^2_\nu$ alone cannot tell that point from a converged fit
with real model error, so no cap above 1 has a source. At 1, $\sigma_i$ is the
esd of the counting statistics alone. A converged fit at $\chi^2_\nu > 1$ then
stops when every shift is under $\epsilon_{\mathrm{stop}}/\sqrt{\chi^2_\nu}$ of
its reported esd, and otherwise on the $10^{-9}$ test below.

On a Pawley block above 128 parameters the normal
matrix is sparse, and the driver bounds the ratio instead. By the
Cauchy-Schwarz inequality,
$|\Delta_i|/\sigma_i \le \sqrt{\Delta^\top A \Delta / \min(\chi^2_\nu, 1)}$, so the bound
can stop a stage later than the exact ratio would, never earlier. The
$10^{-9}$ relative decrease in $\chi^2$ still ends a stage that never meets
the band. Every intermediate stage, a stage declaring its own `ftol` and a plan
with `shift_over_esd_tol = None` stop on that alone.
