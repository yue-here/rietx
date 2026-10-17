(ch-profiles)=
# Peak profiles

This chapter gives the shape and width of one peak, and how the instrument's width and the sample's combine.

(sec-width-split)=
## The instrument ⊕ sample width split

⊗ is convolution. A measured line is the specimen's line convolved with the
instrument's, so the shape to approximate is a Voigt, a Gaussian ⊗ Lorentzian.
That convolution is never evaluated as an integral. The default profile
approximates it by the linear blend of {eq}`prof-pv`. The opt-in exact shape is
the closed form of {eq}`prof-voigt`. The one convolution this chapter does
integrate is the axial divergence of {eq}`prof-fcj-integral`.

⊕ is shorthand for the rule convolution imposes on the widths. The Gaussian and
Lorentzian component widths each carry an instrument part and a sample part.
Gaussian variances add, and Lorentzian FWHMs add. So "instrument ⊕ sample"
means a specimen contribution combined with an instrument contribution by that
rule, and never two numbers of degrees added together.

The two widths below are full widths at half maximum, in deg 2θ. The Gaussian
one is written as a law for its square, because the variance is what adds, and
that is where its deg² come from.

```{math}
:label: prof-caglioti-g

\Gamma_G^2(\theta) \;=\; (U + U_s)\tan^2\theta + V\tan\theta + W
+ \frac{P}{\cos^2\theta}
\qquad [\deg^2 2\theta]
```

{source}`rietx.model.profiles.caglioti.gaussian_fwhm`

$U, V, W$ are the instrument resolution function {cite}`caglioti1958`. The
sample adds a Gaussian microstrain term $U_s\tan^2\theta$ and a Gaussian size
term $P/\cos^2\theta$ {cite}`larson2004,thompson1987`.

$\Gamma_G^2$ is a variance, so the physical constraint is on the sum and not on
its coefficients:

```{math}
:label: prof-caglioti-positive

\Gamma_G^2(\theta) \;>\; 0
\qquad \text{for every } \theta \text{ in the fitted range}
```

{source}`rietx.strategy.staged.check_resolution_positive`

Each coefficient separately may be negative. A negative $V$ is the ordinary
sign of a focusing geometry, and the schema bounds allow it. What the sum
cannot do is go below zero where a peak is being fitted, because the width
there would be the square root of a negative variance.

Nothing raises when it does. `gaussian_fwhm` clamps $\Gamma_G^2$ to a small
floor to keep the root real, so the model reports a resolution some four orders
finer than any goniometer and the fit goes on converging. The condition above
is therefore checked as a guard rather than enforced as a bound, and a fit that
trips it reports `RESOLUTION_NOT_POSITIVE`. Read that as "these resolution
parameters are not quotable", the same reading
`STEPHENS_STRAIN_NOT_POSITIVE` has and for the same reason: a variance left its
physical set, and the widths built on it are not measurements.

$W$ has a floor of its own. Its lower bound is the clamp itself, $\varepsilon$ =
{{ MIN_GAMMA_G2 }} deg², and not 0. Under the clamp every Gaussian width column
is exactly zero. The default Levenberg-Marquardt driver puts a parameter
exactly on its bound when the data push it there ({ref}`ch-estimation`,
§ Solvers). With a floor of 0, a stage freeing $W$ while $U$ and $V$ were near
0 put $\Gamma_G^2$ under the clamp at every point, and the stage stopped there.
With $U$ and $V$ at 0, $W$ on its floor holds $\Gamma_G^2$ at $\varepsilon$,
and a step up in $W$ still widens every peak. A stored or passed
lower bound under the floor is raised to it when the profile is built, and a
value under it is raised with it. GSAS-II clamps the same way, but its solver
takes no bounds, so no step lands on a floor there. The floor holds $W$ and
not the sum. A negative $U$ or $V$ can still take $\Gamma_G^2$ under the
clamp.

So the driver also holds the sum on a single-histogram fit. Each reflection on
the data adds one row to its linear inequalities ({ref}`ch-estimation`,
§ Solvers):

```{math}
:label: prof-caglioti-floor

\Gamma_G^2(\theta_{hkl}) \;\ge\; \varepsilon
\qquad \text{for every reflection } hkl \text{ on the data}
```

{source}`rietx.optimize.least_squares.gaussian_width_inequalities`

$\Gamma_G^2$ here includes the phase's Gaussian size and strain terms, and the
angles are those of the cell at the start of the stage. TRF and a joint fit
build no rows, and neither does a reflection that starts under the clamp. The
guard above stays the check for those.

```{math}
:label: prof-caglioti-l

\Gamma_L(\theta) \;=\; \frac{X + X_s}{\cos\theta} + (Y + Y_s)\tan\theta
\qquad [\deg 2\theta]
```

{source}`rietx.model.profiles.caglioti.lorentzian_fwhm`

```{warning}
Conventions here are documented by physics and not by letters. The
$1/\cos\theta$ terms (and the $1/\cos^2\theta$ variance term) carry Scherrer
crystallite-size broadening, and the $\tan\theta$ terms (and $\tan^2\theta$)
carry microstrain. The letter assignments differ between codes. GSAS uses
X = size and Y = strain, and FullProf swaps them. Transfer a value by matching
the $\theta$-law, never the letter.
```

{ref}`sec-width-as-size` reads either $1/\cos\theta$ coefficient back as a
crystallite size, and says why $U$ and $W$ have no size to read. Anisotropic
(hkl-dependent) sample broadening is in {ref}`ch-microstructure`.

(sec-resolution-determined)=
### When $U$, $V$ and $W$ are determined at all

The two laws above are fitted together, so how well each is determined depends
on how much of the peak it carries. On high-resolution data the peaks are
predominantly Lorentzian, and there the Gaussian parameters are poorly
constrained: "unconstrained refinement of the Gaussian parameters $U$, $V$ and
$W$ may lead to nonphysical results, or at worst, complete failure of the
refinement" {cite}`mccusker1999`. The same source gives the remedy, and it is
not a limit on the width. Apply a constraint, or hold the parameters at the
instrumental values.

The converse holds for constant-wavelength neutron data, where the instrument
dominates the profile and the same paper finds the same three parameters
well determined by refinement. So the question is about the character
of the pattern rather than the size of the widths, and any single bound on
width would have to be wrong for one technique or the other.

rietx therefore reports rather than bounds. A fit that frees $U$, $V$ or $W$ on
a pattern where $\Gamma_L$ exceeds $\Gamma_G$ at more than half the fitted
points gets a `RESOLUTION_UNCONSTRAINED` diagnostic. "Predominantly" is a
comparison between two computed widths, so no calibrated constant enters. The
workflow that implements the paper's remedy is in Part 1: calibrate on a
standard with its certified cell held fixed, save the profile, and load it
before the sample fit.

(sec-strain-cap)=
## The strain width bound

Nothing in $Y_s\tan\theta$ stops at a physical strain. Past some width the
phase's lines are flat across the whole scan. They are then degenerate with the
background, they starve whatever they overlap, and the covariance loses
conditioning. Measured on a 248-pattern in-situ reduction series, $Y_s$ reached
$1.1\times10^{5}$ where the reference protocol for the same data used 0.3.

$Y_s$ therefore carries a default upper bound derived from the pattern itself
rather than from any material, and so does $U_s$, the same width squared:

```{math}
:label: prof-strain-cap

Y_s \;\le\; Y_{\max}, \qquad U_s \;\le\; Y_{\max}^2,
\qquad
Y_{\max} \;=\; \frac{f\,(2\theta_{\max} - 2\theta_{\min})}{\tan\theta_{\max}}
\quad [\deg 2\theta]
```

{source}`rietx.params.vector.strain_cap`

with $2\theta_{\min}, 2\theta_{\max}$ the ends of the fitted range (excluded
regions removed, since an excluded interval was not measured). $f$ is the
fraction of that range one term is allowed to spend, and rietx sets it to
{{ STRAIN_CAP_RANGE_FRACTION }}. $U_s$ takes the square because it is a
variance. At $f = 1$ the strain term alone would contribute one whole range's
worth of FWHM at the pattern's highest $\theta$, so the bound says that a line
wider than the interval it was measured over is not a line. The rule is
dimensional and self-scaling. A 15–80° lab scan and a 0.5–50° low-angle scan get
different bounds out of it, and no calibrated constant enters.

```{warning}
This bounds the numerics and not the strain. It sits two orders of magnitude
above anything a specimen produces (≈ 83 deg on a 10–80° scan), so it makes no
judgement about whether a width is believable. That judgement is the
`STRAIN_UNUSUALLY_LARGE` diagnostic, which fires above
{{ STRAIN_FLAG_WIDTH }} deg, the top of a corpus of 606 solved refinements, and
bounds nothing. Nanocrystalline and heavily defective specimens refine into that
tail legitimately. Treat a flag there as a number to check.
```

The bound is applied at the optimiser interface for one stage, and never on the
stored parameter. Two properties follow.

* It is armed only on a term that has already reached it. A finite bound changes
  the trust-region step in a coordinate even where nothing approaches it, so a
  fit whose strain stays inside {eq}`prof-strain-cap` gets no bound at all and
  is bit-identical to an unbounded build.
* A finite stored `max` is the caller's claim and outranks it, by the rule the
  per-stage cell window follows. Declaring any ceiling switches the default off,
  a deliberately enormous one included.

Enforcement is per stage rather than per iteration. A stage that starts below
the bound may cross it, and the next stage pulls it back and reports `BOUND_HIT`
on the path (`RefinedParameter.at_bound` carries the same finding on the row).

(sec-size-cap)=
## The size coefficient bound

The size terms $X_s/\cos\theta$ and $P/\cos^2\theta$ have the same runaway
geometry as the strain terms and take the same fix. The intent differs, and so
does the number. A large $X_s$ is a small crystallite (via Scherrer,
{eq}`ms-size-coefficient` in {ref}`sec-width-as-size`), and real specimens are
genuinely nanocrystalline, so this bound is set to catch a runaway and not to
legislate a size:

```{math}
:label: prof-size-cap

X_s \;\le\; \min\!\left(
\frac{(180/\pi)\,K\lambda}{L_{\min}},\;\;
f\,(2\theta_{\max}-2\theta_{\min})\cos\theta_{\max}
\right)
\quad [\deg 2\theta]
```

{source}`rietx.params.vector.size_cap`

with $L_{\min}$ the smallest crystallite the bound admits,
{{ SIZE_CAP_MIN_SIZE_NM }} nm, and $f$ the range fraction of
{eq}`prof-strain-cap`.

The first term is a floor on the crystallite ($L \ge L_{\min}$), read as a
ceiling on the coefficient with no reference angle, {eq}`ms-size-coefficient`
in {ref}`sec-width-as-size`, per wavelength: ≈ 4°/cos θ at Cu Kα for 2 nm. The
second is the strain rule's range backstop, with $1/\cos\theta$ in place of
$\tan\theta$, evaluated where $1/\cos\theta$ is largest. On any real scan the
floor is far the tighter (Cu 10–80°: ≈ 4 deg against ≈ 54 deg), so the floor
governs, and the backstop catches only the $1/\cos\theta$ pathology near
2θ = 180°. $P$ is a variance and takes the square of whichever width binds.

```{warning}
$L_{\min}$ makes no claim about how small a crystallite may be. It is a runaway
fence two unit cells below the archive. The smallest well-determined size in a
corpus of 606 solved refinements is ≈ 33 nm, and every refined size below ~2 nm
there is an exploratory or placeholder fit. A genuinely nano specimen refines
freely above the fence. For one truly smaller than 2 nm, declare the bound you
mean: a finite `Parameter.max` outranks the default. The
surprising-but-possible band is the `SIZE_UNUSUALLY_SMALL` diagnostic, which
fires below {{ SIZE_FLAG_SIZE_NM }} nm and bounds nothing.
```

The bound behaves as the {ref}`strain cap <sec-strain-cap>` does. It is armed only on a term that
has already reached it, a finite stored `max` outranks it, and it reports
`BOUND_HIT` when the next stage pulls a crossing back. Any fit that stays off
the floor is bit-identical to an unbounded build.

## Thompson-Cox-Hastings pseudo-Voigt

TCH is Thompson, Cox and Hastings, whose 1987 paper {cite}`thompson1987`
supplies the two polynomials below. The trailing Z of the class name
`ProfileTCHZ` is not theirs. That paper's own width model is one parameter per
component, $\Gamma_G = V\tan\theta$ and $\Gamma_L = X/\cos\theta$, with no $U$,
$W$ or $Y$ and nothing called $Z$. Every further letter came from the codes that
adopted the profile afterwards, the label included, and those codes disagree on
which term wears which. rietx's class holds the five coefficients
$U, V, W, X, Y$ of {eq}`prof-caglioti-g` and {eq}`prof-caglioti-l`, so read the
$\theta$-law and not the label, as the chapter's first warning already says for
X and Y. TCH's own two letters do survive it. Their $V$ is this chapter's
Gaussian $\tan\theta$ term, and their $X$ this chapter's Lorentzian
$1/\cos\theta$ one.

The default profile approximates the Voigt (Gaussian ⊗ Lorentzian) as a
linear blend with a single FWHM $\Gamma$ [deg 2θ] and a mixing fraction
$\eta$. Its argument is the offset $x = 2\theta - 2\theta_k$ from reflection
$k$'s Bragg position:

```{math}
:label: prof-pv

\mathrm{pV}(x) \;=\; \eta\, L(x; \Gamma) + (1 - \eta)\, G(x; \Gamma),
```

```{math}
:label: prof-tch-gamma

\begin{aligned}
\Gamma^5 = \Gamma_G^5
&+ 2.69269\, \Gamma_G^4 \Gamma_L + 2.42843\, \Gamma_G^3 \Gamma_L^2 \\
&+ 4.47163\, \Gamma_G^2 \Gamma_L^3 + 0.07842\, \Gamma_G \Gamma_L^4
+ \Gamma_L^5,
\end{aligned}
```

```{math}
:label: prof-tch-eta

\eta = 1.36603\, q - 0.47719\, q^2 + 0.11116\, q^3,
\qquad q = \Gamma_L / \Gamma.
```

{source}`rietx.model.profiles.pseudovoigt.tch_gamma_eta`

### Origin and accuracy of the coefficients

The coefficients are fitted rather than derived, because a Voigt has no
closed-form width and no exact pseudo-Voigt equivalent. The two equations do not
have the same author.

{eq}`prof-tch-gamma` is TCH's, and the paper gives its origin in one clause:
"another simple series expansion derived from a set of computer-generated
convolutions" {cite}`thompson1987`. {eq}`prof-tch-eta` is older. The
pseudo-Voigt as a way of reading a line's Gaussian and Lorentzian content is
Wertheim, Butler, West and Buchanan's {cite}`wertheim1974`, and the mixing
expansion is Hastings, Thomlinson and Cox's {cite}`hastings1984`. TCH
renormalised that expansion's coefficients for the unit-area form of
{eq}`prof-pv`, and say so in the paper. The digits are transcribed from two
papers. None of them carries physics on its own, and none is a rietx constant
to tune.

Neither paper quotes an accuracy for its expansion, so the accuracy of the pair
is measured here against the exact convolution rietx ships as {eq}`prof-voigt`.
Across the whole range $0 \le q \le 1$, with the true FWHM found by bisecting
the Faddeeva Voigt (`tests/test_voigt.py`):

* {eq}`prof-tch-gamma` reproduces the true Voigt FWHM to within 0.43 %, worst
  near $\Gamma_L \approx \Gamma_G/2$, and is exact in both pure limits;
* the pseudo-Voigt built from the pair departs from the exact Voigt by at most
  1.3 % of the peak height, worst at $q \approx 0.56$.

Where that 1.3 % sits matters more than its size. At the peak centre the
departure stays under 0.25 % across the whole range. The worst of it is on the
flanks, at $x \approx \pm0.28\,\Gamma$, where a peak's position and width
derivatives live. The choice between `"tchz_pv"` and `"voigt"` is therefore not
a choice about peak heights. The exact shape has something to offer on a pattern
whose lines are neither nearly Gaussian nor nearly Lorentzian.

Both component shapes are unit-area normalised, so $\int \mathrm{pV}\,dx =
1$ and the reflection intensity of {eq}`fm-rietveld` enters purely through
the prefactor:

```{math}
:label: prof-components

G(x) = \frac{2}{\Gamma}\sqrt{\frac{\ln 2}{\pi}}
\exp\!\left(-\frac{4 \ln 2\, x^2}{\Gamma^2}\right),
\qquad
L(x) = \frac{2/(\pi\Gamma)}{1 + 4x^2/\Gamma^2}.
```

{source}`rietx.model.profiles.pseudovoigt.pseudo_voigt`

## Declared extra peaks

A sample holder, a mount or an unidentified impurity may diffract the same
source as the specimen and put a sharp line where no phase in the model has one.
Such a line has no cell behind it, so it is declared rather than derived. It is
evaluated as a single unit-area pseudo-Voigt of {eq}`prof-pv`, one image per
emission line:

```{math}
:label: prof-extra-peak

y_{\mathrm{peak}}(2\theta) = A \sum_{l} g_l\,
\mathrm{pV}\!\left(2\theta - 2\theta_l;\ \Gamma,\ \eta\right),
\qquad
g_l = w_l\, \frac{\mathrm{Lp}(2\theta_l)}{\mathrm{Lp}(2\theta_0)},
```

with $2\theta_l$ the Bragg image of the declared apparent centre $2\theta_0$,

```{math}
:label: prof-extra-peak-image

\sin\theta_l = \frac{\lambda_l}{\lambda_0}\,\sin\theta_0 .
```

{source}`rietx.model.forward.CompiledModel.extra_peak_curve`

The intensity enters as an area $A$, in counts·deg. That is what a reflection
intensity is, and what the unit-area normalisation of {eq}`prof-components`
makes the prefactor mean. The line gain $g_l$ carries the line's weight and the
two lines' Lorentz-polarisation ratio. Each image diffracts at its own Bragg
angle and so carries its own Lp, and holding the bare weight instead biases the
fitted primary position by a measured amount. Line 0 is the primary, with
$w_0 \equiv 1$ and $g_0 = 1$, so $A$ is the primary line's area.

The profile deliberately carries three things less than a reflection does.

* No position correction of the specimen's reaches $2\theta_0$. Zero shift,
  displacement and transparency all describe where the specimen sits, and a
  holder at its own distance has aberrations of its own. The free centre absorbs
  them.
* No axial asymmetry. The Finger-Cox-Jephcoat convolution
  {eq}`prof-fcj-integral` describes the specimen's axial geometry, so a
  symmetric pseudo-Voigt is the honest model for an intruder.
* No structure factor, multiplicity or Lorentz factor beyond the line ratio,
  because there is no cell to compute them from.

{eq}`prof-extra-peak` therefore describes a feature and does not predict one.

The evaluation window is frozen per stage, as every window in {ref}`ch-method`
is, and it is sized from the declared bounds rather than from the current
values. Its half-width is $k(\eta_{\max})\,\Gamma_{\max} + \Delta$, with $k$
the area-tolerance multiplier of {ref}`ch-forward` and $\Delta$ the same
absolute movement slack a reflection window carries. A centre free anywhere
inside its bounds is therefore inside its frozen window by construction.


## The true Voigt, via the Faddeeva function

An opt-in shape (`Instrument.profile.shape = "voigt"`; TCHZ stays the
default) evaluates the exact convolution {cite}`armstrong1967`:

```{math}
:label: prof-voigt

V(x; \sigma, \gamma) \;=\; \frac{\operatorname{Re}[w(z)]}{\sigma\sqrt{2\pi}},
\qquad z = \frac{x + i\gamma}{\sigma\sqrt{2}},
```

{source}`rietx.model.profiles.voigt.voigt`

where $\sigma$ is the Gaussian standard deviation and $\gamma$ the Lorentzian
half-width at half maximum, both in deg 2θ. Both are recovered from the
component FWHMs of {eq}`prof-caglioti-g`-{eq}`prof-caglioti-l`. This is the one
place in the manual where a width is something other than an FWHM, and the
conversion is the equation:

```{math}
:label: prof-voigt-widths

\sigma = \frac{\Gamma_G}{2\sqrt{2\ln 2}}, \qquad \gamma = \frac{\Gamma_L}{2}.
```

{source}`rietx.model.profiles.voigt.fwhm_to_voigt_params`

Both limits are exact and recovered without a branch: $\gamma \to 0$ makes $z$
real and $\operatorname{Re}[w] = e^{-z^2}$ (the unit Gaussian); $\sigma \to
0$ sends $|z| \to \infty$ where $w(z) \to i/(\sqrt{\pi} z)$ (the unit
Lorentzian).

The Faddeeva function $w(z) = e^{-z^2}\operatorname{erfc}(-iz)$
($\operatorname{Im} z \ge 0$) is computed by the Weideman rational
approximation {cite}`weideman1994`: the conformal map of the upper
half-plane onto the unit disc,

```{math}
:label: prof-weideman

Z = \frac{L + iz}{L - iz}, \qquad L = \sqrt[4]{1/2}\cdot\sqrt{N},
\qquad
w(z) = \frac{2\, p(Z)}{(L - iz)^2} + \frac{1/\sqrt{\pi}}{L - iz},
```

{source}`rietx.model.profiles.faddeeva.faddeeva_w`

with $p$ an $N$-term polynomial whose real coefficients come from a single FFT
at import time. $N = 32$ reaches ≈1e-13. The algorithm is branchless over the
whole upper half-plane, with no region partition (Humlíček's w4
{cite}`humlicek1982`) and no series switching {cite}`zaghloul2011`. A
branchless form keeps the residual smooth for finite-difference and autodiff
Jacobians, and that is what this one was chosen for. The Voigt argument always
has $\operatorname{Im} z = \gamma_L/(\sigma\sqrt{2}) \ge 0$, so the reflection
formula for the lower half-plane never arises. Derivatives reuse the same
$w$ call through the identity $w'(z) = -2z\,w(z) + 2i/\sqrt{\pi}$
{cite}`abramowitz1964`.

## Finger-Cox-Jephcoat axial divergence

With a sample of axial half-length $S$ and a receiving slit of axial
half-length $H$ at goniometer radius $L$, rays leaving the diffraction plane
are detected at an *apparent* angle $2\varphi$ related to the true Bragg
angle by {cite}`finger1994`

```{math}
:label: prof-fcj-apparent

\cos 2\varphi \;=\; \cos 2\theta \cdot \sqrt{1 + \xi^2},
\qquad \xi = u/L,
```

{source}`rietx.model.profiles.fcj.fcj_offsets_weights`

where $u$ is the signed axial offset of the ray. For $2\theta < 90°$ intensity
smears from $2\theta$ down to $2\varphi_{\min}$, the classic low-angle tail of
laboratory data. Above 90° the smear is toward high angle. The weight of a given
offset is the axial overlap of sample and slit, a trapezoid in $\xi$ (with
$s = S/L$, $h = H/L$):

```{math}
:label: prof-fcj-weight

W(\xi) \;=\; \operatorname{clip}\bigl(s + h - \xi,\; 0,\; 2\min(s, h)\bigr),
\qquad \xi \ge 0.
```

{source}`rietx.model.profiles.fcj`

As a density in $2\varphi$, the aberration diverges like
$1/\sqrt{2\theta - 2\varphi}$ at the Bragg position. Naive sampling fails on
that divergence. Substituting $\xi$ as the integration variable removes the
singularity exactly:

```{math}
:label: prof-fcj-integral

y(2\theta_i) \;=\;
\frac{\int_0^{\xi_{\max}} W(\xi)\, \Omega\bigl(2\theta_i - 2\varphi(\xi)\bigr)\, d\xi}
     {\int_0^{\xi_{\max}} W(\xi)\, d\xi},
\qquad
\xi_{\max} = \min\bigl(s + h,\; |\tan 2\theta|\bigr),
```

{source}`rietx.model.profiles.fcj`

The integrand is smooth, and fixed-node Gauss-Legendre quadrature in
$\tau = \xi/\xi_{\max}$ evaluates it. The $|\tan 2\theta|$ cap removes the
unphysical $\cos 2\varphi > 1$ branch at very low angle. The weights are
renormalised to $\sum\omega = 1$, so the composite peak keeps unit area and
reflection intensities stay areas. Node counts are frozen per stage
({{ NODES_PER_FWHM }} nodes per FWHM of smear where the map moves fastest,
clamped to [8, 64]), and node positions follow $s$, $h$ and $2\theta$ smoothly.
When the asymmetric extent falls below {{ SKIP_EXTENT_FWHM_RATIO }} of the peak
FWHM the aberration is invisible, and the peak is treated as symmetric.

With one aperture at zero the trapezoid {eq}`prof-fcj-weight` has no height,
and {eq}`prof-fcj-integral` is a ratio of two zeros. Its limit as $h \to 0^+$
with $s > 0$ is a uniform weight over $[0, \xi_{\max}]$, because $W/2h \to 1$
there and the falling edge shrinks to nothing. rietx evaluates that limit, so
the profile is continuous over the whole range of apertures. Only
$s = h = 0$ gives the symmetric peak. A refinement can therefore land an
aperture exactly on its lower bound of zero.

The quadrature is split at the kink of the trapezoid {eq}`prof-fcj-weight`,
which keeps the response $C^1$ everywhere but the inherent FCJ corner at
$s = h$. That corner is a genuine non-differentiability, and it has measured
consequences for refinement when both apertures are equal. {ref}`ch-method`
works them through.
