(ch-microstructure)=
# Microstructure

This chapter reads the refined width coefficients as a crystallite size and a microstrain, isotropic or by Stephens' model.

## Isotropic size and strain

Sample broadening rides on the instrument profile through the width laws of
{eq}`prof-caglioti-g` and {eq}`prof-caglioti-l`. Crystallite-size broadening
varies as $1/\cos\theta$ (Scherrer; Lorentzian $X_s$, Gaussian variance
$P/\cos^2\theta$), and microstrain broadening as $\tan\theta$ (Lorentzian $Y_s$,
Gaussian variance $U_s \tan^2\theta$). The
{ref}`instrument ⊕ sample split <sec-width-split>` is a workflow as much as an
equation. Calibrate $U, V, W, X, Y$ on a line-width
standard with its certified cell held fixed, freeze them, and refine only the
sample terms on the specimen.

These laws depend on $hkl$ only through θ. Real strained powders break that:
$(00l)$ and $(hk0)$ can differ threefold at the same $2\theta$.

(sec-width-as-size)=
## Reading a width as a size

A width in degrees does not transfer between instruments. The crystallite size
it implies does. Scherrer's relation {cite}`scherrer1918` reads a single line's
breadth as an apparent size,

```{math}
:label: ms-scherrer

L \;=\; \frac{K\lambda}{2w\,\cos\theta} \qquad [\text{Å}],
```

{source}`rietx.model.profiles.caglioti.apparent_size`

with $2w$ the FWHM in radians of $2\theta$, which is Langford and Wilson's
symbol for it {cite}`langford1978`. Their $\beta$ is the *integral breadth*, the
peak area divided by the peak height, and the table in
{ref}`sec-units` rules that out as a width measure here. The lower-case $2w$ is a
width in radians and has nothing to do with the Caglioti $W$ of
{eq}`prof-caglioti-g`, which is a variance in deg². $K$ depends on the
crystallite shape and on which of the two breadths is used: 0.89 for the FWHM of
a sphere against 1.0747 for its integral breadth. An apparent size
is therefore an order-of-magnitude statement rather than a quotable two-figure
one. It is also a lower bound unless the instrument and strain contributions
have been taken out first, since Scherrer attributes every degree it is handed
to size.

The size transfers and the degrees do not, for the same reason that working in
$Q$ helps. With $Q = 4\pi\sin\theta/\lambda$ the local Jacobian is
$dQ/d(2\theta) = 2\pi\cos\theta/\lambda$, and the $\cos\theta$ of
{eq}`ms-scherrer` cancels against it:

```{math}
:label: ms-delta-q

\Delta Q \;=\; \frac{2\pi\cos\theta}{\lambda}\,(2w) \;=\; \frac{2\pi K}{L}
\qquad [\text{Å}^{-1}],
```

{source}`rietx.model.profiles.caglioti.delta_q_fwhm`

independent of both $\lambda$ and $\theta$, so Scherrer broadening is constant
in Q. The size law of {eq}`prof-caglioti-l` is itself $1/\cos\theta$, so the
same cancellation removes the reference angle entirely, and a size coefficient
maps to one size for the whole pattern,

```{math}
:label: ms-size-coefficient

L \;=\; \frac{180}{\pi}\cdot\frac{K\lambda}{X_s}
\qquad\Longleftrightarrow\qquad
X_s \;=\; \frac{180}{\pi}\cdot\frac{K\lambda}{L},
```

{source}`rietx.model.profiles.caglioti.apparent_size_from_size_coefficient`

reading $\sqrt{P}$ in place of $X_s$ for the Gaussian variance coefficient of
{eq}`prof-caglioti-g`. The right-hand form is the seeding direction. It gives a
width for a specimen whose size is already known from a micrograph, a synthesis
or an earlier refinement, in place of a default calibrated on a synchrotron
linewidth.

```{warning}
Only the $1/\cos\theta$ coefficients have a size to read. $W$ is constant in θ
and $U$ goes as $\tan^2\theta$, so a number of degrees taken off either is a
number at one chosen angle. $U = 1.0\ \deg^2$ alone is 0.268° FWHM at
$2\theta = 30$° and 3.172° at $2\theta = 145$°, a factor of twelve across an
ordinary pattern.

A bound declared in degrees is hard to transfer for the same reason. $X$ carries
$\max = 1.0$°, which is 79.4 Å on Cu Kα against 21.3 Å on 11-BM's 0.4139 Å, so
one cap admits a 3.7× spread in the physics. The sample terms $X_s$ and $P$
carry $\min = 0$ and no maximum. Decide such a limit as a size, and report it in
degrees.
```

(sec-width-as-strain)=
## Reading a width as a strain

Microstrain broadens by a fixed fraction of every d-spacing rather than by a
fixed reciprocal-space width {cite}`stokes1944`. Differentiating Bragg's law
$\lambda = 2d\sin\theta$ at fixed $\lambda$ gives $\Delta d/d = -\cot\theta\,
\Delta\theta$, so a relative spread in $d$ appears as

```{math}
:label: ms-strain-law

\Delta 2\theta \;=\; 2\,\frac{\Delta d}{d}\,\tan\theta
\qquad [\text{radians}],
```

{source}`rietx.model.profiles.caglioti`

which is the $\tan\theta$ term of {eq}`prof-caglioti-l`. Inverting it for the
coefficient $Y_s$ in deg $2\theta$,

```{math}
:label: ms-strain-coefficient

\frac{\Delta d}{d} \;=\; \frac{\pi}{180}\cdot\frac{Y_s}{2}
\qquad\Longleftrightarrow\qquad
Y_s \;=\; \frac{360}{\pi}\cdot\frac{\Delta d}{d},
```

{source}`rietx.model.profiles.caglioti.microstrain_from_strain_coefficient`

reading $\sqrt{U_s}$ in place of $Y_s$ for the Gaussian variance coefficient of
{eq}`prof-caglioti-g`, exactly as {eq}`ms-size-coefficient` reads $\sqrt{P}$.

No wavelength appears in {eq}`ms-strain-coefficient`, and no shape constant
either. The contrast with {eq}`ms-size-coefficient` is the whole of the
asymmetry. Six sample-broadening quantities appear in {eq}`prof-caglioti-g` and
{eq}`prof-caglioti-l`: two sizes, two strains, and the Stephens block of
{eq}`ms-lambda`. The two named "size" are the ones that depend on $\lambda$.
One specimen measured at two wavelengths therefore shows the same number of
degrees of strain broadening, and size coefficients in the ratio
$\lambda_2 / \lambda_1$, with their Gaussian variances in the ratio squared. A
joint refinement shares the size rather than the coefficient.
`rietx.params.multi` normalises it and reports the rescaling as the
`SIZE_NORMALISED_ACROSS_WAVELENGTHS` diagnostic.

$\Delta d/d$ here is the FWHM of the d-spacing distribution, matching what
{eq}`ms-strain-law` relates and what the coefficients of
{eq}`prof-caglioti-g`–{eq}`prof-caglioti-l` are. Other codes publish other
measures of the same width. GSAS-II's `mustrain` is $2\Delta d/d$ in units of
$10^{-6}$, and FullProf's apparent strain is $\tfrac{1}{2}\beta^{*}d$, read off
the integral breadth rather than the FWHM. A microstrain is comparable between
codes only with its convention attached.

(sec-sample-broadening-tof)=
## The same two quantities on a time-of-flight bank

A bank has no angle to vary and no wavelength to state, so neither
{eq}`ms-size-coefficient` nor {eq}`ms-strain-coefficient` can be written down
there. Both quantities survive the move unchanged, because both are statements
about $d$ rather than about $2\theta$. Flight time is proportional to
d-spacing, $T = \mathrm{DIFC}\cdot d$ to the order a width is taken at, so a
fractional spread in $d$ is the same fractional spread in $T$:

```{math}
:label: ms-tof-widths

\Delta T_{\text{size}} = \mathrm{DIFC}\,\frac{K}{L}\,d^{2},
\qquad
\Delta T_{\text{strain}} = \mathrm{DIFC}\,\varepsilon\,d
\qquad [\mu\mathrm{s}]
```

{source}`rietx.model.profiles.tof.tof_sample_gamma`

Microstrain is a constant $\Delta d/d = \varepsilon$, hence linear in $d$;
Scherrer broadening is a constant $\Delta Q = 2\pi K/L$, i.e.
$\Delta d/d = (K/L)\,d$, hence quadratic. The Lorentzian pair add to the
bank's $\gamma(d)$ and the Gaussian pair enter its $\sigma^{2}(d)$ in
quadrature, before the Thompson–Cox–Hastings mixing: a width added to the
mixed $\Gamma$ would be a width of neither shape.

The refinable quantities are the same four `Phase` parameters the angular arm
uses. Their unit differs on a bank, and only
for the size pair, which is the asymmetry of
{eq}`ms-size-coefficient`–{eq}`ms-strain-coefficient` again. A strain
coefficient carries no $\lambda$, so `lor_strain` and `gauss_strain` are the
same numbers of degrees on both arms. A size coefficient is
$(180/\pi)K\lambda/L$, so on a `neutron_tof` histogram `lor_size` holds $K/L$
in Å⁻¹ and `gauss_size` its square. A joint fit sharing one size between a
bank and a scan would convert between the two units, as the multi-histogram
fit already does across two wavelengths; that fit is not written for a bank
yet. The apparent size is then

```{math}
:label: ms-tof-size

L \;=\; K \big/ x_{\text{size}}^{(d)} \qquad [\text{Å}]
```

{source}`rietx.model.profiles.caglioti.apparent_size_from_d_size_coefficient`

with no reference angle and no wavelength at all: the flight-time twin of
{eq}`ms-size-coefficient`, and the reason the microstructure block reports a
crystallite on a bank rather than abstaining.

rietx's defaults are zero on all four, which is the physical statement "an
infinite, strain-free crystal", and no other program's non-zero defaults are
adopted; seed them explicitly to reproduce another program's project.

## Stephens anisotropic strain

Stephens' phenomenological model {cite}`stephens1999` lets every
crystallite carry its own lattice metric. With

```{math}
:label: ms-m

M_{hkl} \;\equiv\; \frac{1}{d^2_{hkl}} \;=\;
\mathbf{h}\cdot G^*\cdot \mathbf{h}^\top \quad [\text{Å}^{-2}],
```

the spread of a quadratic form's coefficients makes the variance of $M$ a
homogeneous quartic in $(h, k, l)$:

```{math}
:label: ms-sigma

\sigma^2(M) \;=\; 10^{-12} \sum_{H+K+L=4} S_{HKL}\; h^H k^K l^L
\quad [\text{Å}^{-4}],
```

{source}`rietx.crystallography.stephens.sigma2_m`

fifteen monomials, hence at most fifteen coefficients. Since $2\theta =
2\arcsin(\lambda\sqrt{M}/2)$ gives $d(2\theta)/dM = \tan\theta / M$, the
contribution in the deg-2θ FWHM units the Lorentzian strain term already
uses is

```{math}
:label: ms-lambda

\Lambda(hkl) \;=\; \frac{180}{\pi}\cdot 10^{-6}\cdot d^2_{hkl}
\cdot \sqrt{\textstyle\sum_{HKL} S_{HKL}\, h^H k^K l^L} \quad [\deg],
```

{source}`rietx.crystallography.stephens.strain_width_deg`

added to the Lorentzian FWHM as $\Lambda(hkl)\cdot\tan\theta$. It is the first
width in the model to depend on $hkl$. Stephens writes this quantity
$\Gamma_A(hkl)$, with the $\tan\theta$ inside it. $\Lambda$ is this manual's
letter for the coefficient alone, because $\Gamma$ is already the FWHM in
{ref}`ch-profiles`. FullProf calls the same thing $D_{ST}$.

The block is opt-in per phase, and no plan frees it until
`phase.microstrain = StephensStrain.isotropic(1000, phase.cell)` declares it.
`lab_sample_refine` then frees it in the sample-broadening stage.
Declare it where the widths depend on direction as well as on 2θ.
Once `lor_strain` has refined, reflections at similar angles stay broader along
some directions than along others, and the difference curve shows a
width-shaped misfit on those reflections alone.
`FitReport.strain` measures that from the observed peak widths and names the broadest and
narrowest directions with their width ratio.
Anisotropic crystallite size and a peak split by too high a symmetry also
broaden some directions more than others, and `FitReport.strain` fits the
tan θ form alone, so rule them out before quoting the coefficients.

```{warning}
Three independent labelling conventions sit behind these $S_{HKL}$, and getting
any one wrong rescales every published number. Transfer a literature value
without them and the width law is wrong while the fit still refines.

1. $\sqrt{\sum S\cdot\text{monomial}}\cdot d^2\cdot 10^{-6}$ is the FWHM of the
   $\Delta M/M = 2\Delta d/d$ distribution, and not its standard deviation. No
   $\sqrt{8\ln 2}$ appears anywhere. That is Stephens' own convention rather
   than a later simplification: the note under his equation (4) says the
   $\sqrt{8\ln 2}$ between the r.m.s. and the FWHM has been folded into the
   definition of $S_{HKL}$. A published set that did not fold it in differs by
   that one constant on every coefficient.
2. The coefficients are carried in 10⁻¹² Å⁻⁴ rather than physical Å⁻⁴. That
   choice is numerical: the shared finite-difference step is absolute below 1,
   so a coefficient at its physical ~10⁻⁸ Å⁻⁴ magnitude would be differenced
   with a step 100× its own value.
3. They multiply the literal monomials $h^H k^K l^L$. Other codes fold symmetry
   multiplicities into their templates, writing the cubic S₂₂₀ term as
   $3(h^2k^2 + h^2l^2 + k^2l^2)$, so their printed values differ by small
   integer factors as well. Check a literature $S_{HKL}$ numerically before
   transferring it.
```

## Symmetry and the allowed coefficients

$\sigma^2(M)$ must be invariant under the Laue group. Miller indices
transform under the reciprocal-space action $\mathbf{h}' =
R^\top\mathbf{h}$, which induces a 15×15 integer action $A(R)$ on the
monomial coefficients. The allowed $S_{HKL}$ span $\bigcap_R \ker(A(R) - I)$,
computed as an exact rational nullspace. It is the rank-4 twin of the rank-2
construction used for ADPs {cite}`peterse1966`, and shares the same kernel.
Degree 4 is inversion-even, so no Laue classification is needed.
The derived dimensions reproduce Stephens' Table 1: $m\bar 3m$ 2, $6/mmm$
and $6/m$ 3, $\bar 3m1$ and $\bar 31m$ 4, $\bar 3$ 5, $4/mmm$ 4, $4/m$ 5,
$mmm$ 6, $2/m$ 9, $\bar 1$ 15.

The coefficients refine as absolute degrees of freedom on that basis, and a set
outside the allowed subspace raises rather than being symmetrised. A Stephens
block replaces the scalar `lor_strain`, whose column is identically the
block's isotropic direction. Declaring a block locks the path, and the width
law then reads zero for it, whatever value it stores. On the isotropic ray
$S = \varepsilon^2\,[M^2]$ the block gives the same width a `lor_strain` of
the same value gives, so the block nests the isotropic model. Free the block in
the sample-broadening stage itself.

$\Lambda$ is purely Lorentzian here. Stephens splits it with a mixing
parameter $\zeta$: $(1-\zeta)\,\Gamma_A$ joins the Gaussian width in
quadrature and $\zeta\,\Gamma_A$ the Lorentzian one (his equation 6). His two
examples refined $\zeta$ to 0.40 and 0.56. TOPAS's Stephens macros carry the
same split as `eta`, and GSAS-II as `Mustrain;mx`. rietx fixes $\zeta = 1$,
so a protocol that refines the split cannot be mirrored here.

## The positivity cone, the seed and the guard

$\sigma^2(M) \ge 0$ for every $hkl$ is a cone coupling all fifteen coefficients,
so it cannot be a box bound. The default bounded-LM driver carries it as a
linear inequality, and the guard (`STEPHENS_STRAIN_NOT_POSITIVE`) falls silent
with nothing left to report ({ref}`ch-estimation`). Under `solver="trf"` the
guard is the only check. A joint fit builds no cone under either driver, so the
guard fires there too. The width law clamps a negative $\sigma^2(M)$ to zero
width, so a fit outside the cone has leaned on the clamp. The reflections past
it lost all strain width, and the solver can use that set as a free hinge. Read
a firing as "these coefficients are not quotable, and the fit leaned on the
clamp". Its χ², cells and phase fractions carry the hinge as well as its
$S_{HKL}$. The finding states the share of the phase's m·|F|² over the reflections
in the fitted range that sits in the clamped ones, with no Lorentz-polarisation,
absorption or texture factor. A firing is
never evidence of anisotropy. The guard's test is one-sided, because zero lies
on the cone itself. An earlier ≤ 0 form that flagged the inert all-zero block
produced a since-withdrawn claim about isotropic specimens.

TOPAS's shipped Stephens macros take `Sqrt(Max(mhkl, 0))`, the same clamp, and
report nothing. `Stephens_tetragonal` takes `Abs()` first, which folds a
negative $\sigma^2(M)$ back into a positive width. A TOPAS Stephens fit
therefore carries no evidence that $\sigma^2(M)$ stayed positive.

The isotropic limit $S = \varepsilon^2\,[M^2]$ lies exactly in the allowed
subspace for every symmetry, and it is both the seed and the only legal start.
At $S \equiv 0$ the square root in {eq}`ms-lambda` has unbounded slope, so strain
stages seed through a dedicated mechanism rather than a generic parameter
seed.

The seed stays at a fixed microstrain (1000 ppm in `lab_sample_refine`) rather
than at the `lor_strain` a phase carried before the block was declared. WP-1467
compared the two starts. On the brucite acceptance pattern under the default LM
driver the χ² agreed to 5 in 10⁵ (7.8943 against 7.8939). On one operando
pattern with two phases the start at the carried strain reached a lower χ² under
LM (1.112 against 1.170) with the two phase fractions swapped, and a higher one
under TRF (1.476 against 1.156). The measurements disagree, so the default is
unchanged.
