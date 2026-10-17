(ch-method)=
# Reading a paper against its own numbers

Three equations in this manual were transcribed from a source that is wrong in
print. Each was caught the same way. Validate an implementation against the
defining quantity, an integral or an identity or a limit, never against a
transcription of the result. Where a paper disagrees with itself, implement the
reading its own numbers pin down. The last two sections are a different case,
where the package's own measurements settled what to ship.

## Rouse b₂: validate against the integral

The capillary-absorption fit {eq}`corr-rouse` has four coefficients
{cite}`rouse1970`. The available scan of the paper prints $b_2$ as "−0·0375", a
digit transposition of the true −0.3750. The error is invisible against the
$\sin^2\theta = 0$ column of the paper's own table, which constrains only $a_1$
and $a_2$, and it is small at low $\mu R$. At $\mu R = 1$ it is 0.0821 wrong.
What settles it is a quadrature of the defining volume-average integral
({cite}`itc-c` equation 6.3.3.4): with −0.3750 the maximum error over the whole
domain is 0.0035, exactly the bound the paper claims for its fit. Never validate
an absorption expression on a constant-θ slice.

{source}`rietx.model.absorption`

The same discipline is structural for the flat-plate cases: they are
closed-form integrals rather than fits, so the tests check them against an
adaptive quadrature of the defining path-length integral, sharing no
constant with the implementation.

## Two Coelho papers vs. their own tables

### Coelho (2005), equation (1)

The paper {cite}`coelho2005` prints the early-iteration damping factor as
$\mathrm{Max}[(k+1)/N_k,\, 1]$ while the surrounding text describes a reduction.
A reduction would be Min. Measured on real refinements, neither reading helps
once parameter removal shrinks $N_k$, and the printed Max form then actively
degrades the step. `bccg.solve` uses a factor of 1 and keeps the two printed
readings selectable, because the choice was measured rather than argued. The LM
driver no longer takes this step. Its bounded step is a projected conjugate
gradient (`bccg.projected_cg`), which stops at a bound instead of clamping a
variable mid-loop.

{source}`rietx.optimize.bccg`

### Coelho (2018), equation (9)

The paper {cite}`coelho2018` defines the predicted cost change as
$\Delta S_t = \Delta p^\top b$. Taken literally with the paper's own
$b = -J^\top r$, that is positive for a descent step while $\Delta S < 0$, so
every good step would report $r_u = \Delta S_t/\Delta S < 0$. That contradicts
the paper's own Table 1 ($r_u \approx 1.003$ on a near-quadratic step), its §1.2
statement and its Fig. 10 distribution. The self-consistent reading is

```{math}
:label: meth-dst

\Delta S_t \;=\; -\Delta\theta^\top b,
```

{source}`rietx.optimize.lm`

pinned by an identity: on an exactly linear model the Gauss-Newton step gives
$r_u \equiv 1$. That is the calibration test, and the only way to know the λ
schedule is being fed the quantity its published constants were tuned for.

## The FCJ corner at $s = h$

The FCJ quadrature {eq}`prof-fcj-weight` is built around $|s - h|$ and
$\min(s, h)$, both non-differentiable at $s = h$, and the default instrument
starts both apertures equal {cite}`finger1994`. Measured on the SRM 660c
protocol, the analytic $S/L$ and $H/L$ Jacobian columns agree with a
residual-vector finite difference to only ~2 %, where every other column is
≤ 1e-5, because the analytic derivative is one-sided while the central
difference straddles the corner. At $s = h$ the two columns are identical. A
Gauss-Newton step moves the pair along the diagonal, and the correlation
guard reports ρ = +1.000. Both drivers leave the diagonal, in opposite
directions. From $S/L = H/L = 0.025$ the bounded LM ends at 0.0367 and 0.0254
($R_{wp}$ 0.08751), and TRF at the mirror point 0.0251 and 0.0376 ($R_{wp}$ 0.08668).
Neither escape is principled. When two drivers "disagree" like
this, the finding is that the parameterisation owns a corner no step can see
across.

{source}`rietx.model.profiles.fcj.fcj_offsets_weights`

## µR, µt, and what $\Delta R_{wp}$ judges

Capillary absorption {eq}`corr-rouse` factors exactly into a scale times a
Debye-Waller shape. Applied to a model with free scale and displacement
parameters, $R_{wp}$ provably cannot move (measured: 3×10⁻⁸ on real 11-BM data),
while every Biso shifts by exactly the predicted {eq}`corr-deltab`. The
correction is real physics with zero fit-quality signature. Flat-plate µt is the
same story with the degeneracy only approximate, since 3–47 % of its signature
survives the projection. It does move $R_{wp}$, and on a genuinely thick
specimen declaring a thickness moves it the wrong way. That movement is the
evidence the specimen was thick.

Of the eight changes shipped in one release, none is well judged by
$\Delta R_{wp}$. Two provably cannot move it, one moves it the wrong way when it
is right, three move it while changing nothing quotable, and the two largest
accuracy wins are invisible in it: dispersion taking round-robin QPA from RMS
2.26 to 0.69 wt %, and absorption removing a bias of up to 1.5 Å² from the ADPs. Every
correction therefore ships with a record field or diagnostic stating what it
changed, and this manual quotes those fields rather than $R_{wp}$ comparisons as
evidence.

{source}`rietx.model.absorption.equivalent_delta_biso_from_transmission`
