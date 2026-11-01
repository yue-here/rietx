(ch-corrections)=
# Intensity corrections

Each correction in this chapter multiplies the reflection intensity of
{eq}`fm-rietveld`. None of the corrections in this chapter is well judged by
$\Delta R_{wp}$. One provably cannot move it (capillary absorption, an exact
reparameterisation). One moves it the wrong way when it is right (a declared
flat-plate thickness on a thick specimen). The largest accuracy wins are
invisible in it: dispersion on quantitative fractions, absorption on ADPs. Every
correction therefore reports what it changed through a record field or a
diagnostic, as {ref}`ch-method` describes.

## Lorentz-polarisation

```{math}
:label: corr-lp

\mathrm{Lp}(\theta) \;=\;
\frac{K + (1 - K)\cos^2 2\theta}{\sin^2\theta\, \cos\theta}.
```

{source}`rietx.model.corrections.lorentz_polarization`

The $1/(\sin^2\theta \cos\theta)$ Lorentz part is the standard
constant-wavelength powder factor (single-crystal rotation Lorentz × powder
ring statistics; {cite}`itc-c` §6.2, {cite}`klug1974`). $K$ is the fraction of
the beam polarised perpendicular to the diffraction plane ($\sigma$-polarised).
$K = 0.5$ reproduces the unpolarised $(1 + \cos^2 2\theta)/2$, and a synchrotron
beam diffracting in the vertical plane has $K \approx 0.99$. A diffracted-beam
monochromator sets $K = 1/(1 + \cos^2 2\theta_m)$ {cite}`itc-c,azaroff1955`. The
familiar 26.6° there is a Cu number and not a property of the graphite
crystal.

## Attenuation coefficients

Specimen absorption needs $\mu$, computed from the refined cell contents
and the McMaster total cross sections {cite}`mcmaster1969`:

```{math}
:label: corr-mu

\mu\ [\mathrm{cm}^{-1}] \;=\;
\sum_{\mathrm{atoms}} \mathrm{occ}\cdot m \cdot
\frac{\sigma_{\mathrm{tot}}\ [\mathrm{barn}]}{V\ [\text{Å}^3]}
```

{source}`rietx.crystallography.attenuation.linear_attenuation`

The sum runs over the asymmetric-unit sites. A site has occupancy
$\mathrm{occ}$ and the multiplicity $m$ of {eq}`par-multiplicity`, so
$\mathrm{occ}\cdot m$ counts its atoms per cell. $\sigma_{\mathrm{tot}}$ is the
species' total cross section at the working wavelength, and $V$ is the cell
volume. One barn is 10⁻²⁴ cm² and one Å³ is 10⁻²⁴ cm³, so the exponents cancel.
Attenuation means beam removal, so the total cross section is the one used,
coherent and incoherent scattering included. That is the NIST convention
{cite}`hubbell1995`. The tabulation is a ~2 %-spaced logarithmic grid that
cannot represent an absorption edge, so an interval containing an edge raises an
error instead of being interpolated. A wavelength that close above an edge also
means strong fluorescence, and a refusal is more honest than any number.

On a constant-wavelength neutron source the same sum runs over the Sears
cross-sections {cite}`sears1992` instead, since X-ray and neutron attenuation
are different quantities and not two precisions of one:

```{math}
:label: corr-mu-neutron

\mu\ [\mathrm{cm}^{-1}] \;=\;
\sum_{\mathrm{atoms}} \mathrm{occ}\cdot m \cdot
\frac{\sigma_{\mathrm{abs}}\,\lambda/\lambda_0
      + \sigma_{\mathrm{coh}} + \sigma_{\mathrm{inc}}\ [\mathrm{barn}]}
     {V\ [\text{Å}^3]},
\qquad \lambda_0 = 1.798\ \text{Å}.
```

{source}`rietx.crystallography.neutron.linear_attenuation_neutron`

$\sigma_{\mathrm{abs}}$ is tabulated for 2200 m/s neutrons, $\lambda_0$, and
away from a resonance it follows the $1/v$ law, so it grows linearly in
$\lambda$ where an X-ray $\mu/\rho$ rises roughly as $\lambda^{3}$ (falls as
$E^{-3}$). The scattering terms are the bound (Sears) values, taken as
$\lambda$-independent; for hydrogen the bound value approximates an effective
cross-section that in a real solid depends on $\lambda$ and on the proton's
dynamics. In a polycrystal the coherent part is Bragg scattering, and how much
of the beam that removes depends on $\lambda$ against the largest $d$-spacing,
which is not modelled. Hydrogen is where the two radiations part most: its
incoherent 80.26 barn makes it about 93 % of brucite's neutron $\mu$ and
under 1 % of its X-ray one. A resonant absorber (Cd, Sm, Eu, Gd, Yb) is
refused. Near a resonance the $1/v$ scaling of the thermal value is wrong in
principle. The lowest resonance of each sits at a tabulated energy
(`rietx.crystallography.neutron.resonance_wavelengths`), but how near a given
$\lambda$ must be to matter is not modelled. That is the neutron twin of the edge refusal above.

## Capillary (cylindrical) absorption

The transmission coefficient is the volume average of the attenuation
({cite}`itc-c` equation 6.3.3.1),

```{math}
:label: corr-itc

A \;=\; \frac{1}{V} \int_V e^{-\mu T}\, dV,
```

{source}`rietx.model.absorption`

with $T$ the total (incident + diffracted) path length. For a cylinder it
depends only on $\mu R$ and $\theta$. Rouse et al. {cite}`rouse1970` fit that
integral over $0 \le \mu R \le$ {{ CYLINDER_MU_R_MAX }} to better than 0.0035
with

```{math}
:label: corr-rouse

A(\mu R, \theta) \;=\;
\exp\!\bigl\{ -(a_1 + b_1 \sin^2\theta)\,\mu R
              - (a_2 + b_2 \sin^2\theta)\,\mu R^2 \bigr\},
```

```{math}
:label: corr-rouse-coeff

a_1 = 1.7133, \quad b_1 = -0.0368, \quad a_2 = -0.0927, \quad b_2 = -0.3750.
```

{source}`rietx.model.absorption`

```{warning}
$A$ here is the transmission coefficient, ≤ 1, and the forward model multiplies
it into the intensity. Most tabulations print the absorption correction
$A^* = 1/A \ge 1$ instead, {cite}`itc-c` Table 6.3.3.2 among them. Getting this
backwards inverts the θ-dependence. An identity test cannot detect the mistake,
since $A(0) = A^*(0) = 1$, and the direction of the θ-dependence can: $A$
increases with $2\theta$, because the mean path through a cylinder shortens
toward backscatter. One more digit to watch: $b_2 = -0.3750$, against the
$-0.0375$ a scan of the paper prints. {ref}`ch-method` records how that was
settled.
```

The expression factors exactly into $A = K(\mu R)\cdot\exp(+c(\mu R)
\sin^2\theta)$, a constant times a Debye-Waller shape. Applying it to a model
with free scale and displacement parameters is therefore an exact
reparameterisation, and $R_{wp}$ cannot move. Its whole physical content is the
Biso shift

```{math}
:label: corr-deltab

\Delta B \;=\; \frac{c(\mu R)\, \lambda^2}{2},
```

{source}`rietx.model.absorption.equivalent_delta_biso`

0.13 Å² at $\mu R = 0.5$ and 0.49 Å² at $\mu R = 1.0$ for Cu Kα. Neglecting
capillary absorption biases Biso low by that much. It is also why $\mu R$ is a
plain float and never refinable: a free $\mu R$ is an exactly singular direction
in the normal equations, rather than a merely correlated one.

## Flat-plate absorption

The three flat-specimen cases of {cite}`itc-c` Table 6.3.3.1 follow from the
same volume average {eq}`corr-itc`, each in closed form. Nothing is a fit, so
there are no coefficients to transcribe wrongly. The thick reflection specimen,
case (1a), gives $A = 1/2\mu$ with no θ-dependence, because the $\sin\theta$ of
the beam footprint cancels against the $\sin\theta$ of the penetration depth. It
is identical to the phase scale, and it is what every Bragg-Brentano fit
implicitly assumes. The two implemented cases, both normalised:

```{math}
:label: corr-fp2

\text{reflection, finite thickness } t:\quad
A = 1 - e^{-2\mu t / \sin\theta} \;\longrightarrow\; 1
\text{ as } \mu t \to \infty,
```

{source}`rietx.model.absorption.flat_plate_reflection_absorption`

```{math}
:label: corr-fp3a

\text{symmetric transmission}:\quad
A = \sec\theta\, e^{-\mu t(\sec\theta - 1)}.
```

{source}`rietx.model.absorption.flat_plate_transmission_absorption`

```{warning}
The two cases take opposite answers about what "off" means. For reflection the
identity is an infinitely thick specimen. $\mu t$ absent means thick, and
$\mu t = 0$ is a specimen of no thickness, which diffracts nothing and raises.
Every other correction here has 0 as its identity. For transmission, $\mu t = 0$
leaves $\sec\theta$, and that factor is physics: the beam footprint on the tilted
plate grows as $\sec\theta$.
```

The bias directions differ. Finite-thickness reflection depresses high-angle
intensity, so a Biso refined without it comes back too large, the opposite sign
to the capillary. Transmission flips sign with thickness. Neither expression is
exactly absorbed by {scale, Biso} as the cylinder's is: the fraction
of $\ln A$ they leave over is 0.2–1.3 % for transmission and a few per cent for
finite-thickness reflection, measured at the reflection positions. $\mu t$ is
computed from the specimen and never refined, as $\mu R$ is, for the different
reason that it is ill-conditioned rather than exactly singular. That leftover
fraction is reported, so a caller can disagree.

## Surface roughness

A rough or loosely packed flat specimen has a packing-density deficit in its
top layer. At low θ the beam crosses that layer at grazing incidence over a long
path, and the intensity is depressed. Suortti's form {cite}`suortti1972`:

```{math}
:label: corr-suortti

R(\theta) \;=\;
\frac{a + (1 - a)\, e^{-b/\sin\theta}}{a + (1 - a)\, e^{-b}},
```

{source}`rietx.model.corrections.surface_roughness_suortti`

normalised so $R(90°) = 1$. Read the two parameters by their physics. $a$ is
the intensity fraction surviving at grazing incidence, so $1 - a$ bounds the
depression. $b$ is the depleted layer's dimensionless optical depth, and it sets
where in angle the transition falls rather than how deep it goes. For
$b \ge 0$ the result is bounded, $0 < R \le 1$, so the correction only ever
depresses.

The Pitschke et al. form {cite}`pitschke1993`:

```{math}
:label: corr-pitschke

R(\theta) \;=\; 1 - c\, u (1 - u), \qquad u = \tau / \sin\theta.
```

{source}`rietx.model.corrections.surface_roughness_pitschke`

The paper's angle-independent term is exactly degenerate with the phase scale,
so it is factored out. What remains is the identifiable strength $c$ and the
roughness parameter τ. This model has a validity range and does not police it.
$R$ is monotone in θ only while $\sin\theta \ge 2\tau$, and beyond
$\sin\theta = \tau$ (its equation 18) it would amplify intensity. The
`ROUGHNESS_OUTSIDE_REGIME` diagnostic owns that fence, evaluated at the
reflection positions, while the function itself stays smooth and is never clamped, so
the Jacobian keeps no kink. Uncorrected roughness
biases ADPs severely: Biso refines to −1.9 … −2.5 Å² where the corrected value
is +0.3.

## Primary extinction

Extinction removes intensity from the strongest reflections, because the
diffracted beam re-diffracts inside a coherent domain, a mosaic block. That is
primary extinction, and it is the only extinction a powder has: secondary
extinction is the attenuation of the beam by other, similarly oriented blocks
upstream, and in a powder the corresponding effect is multiple scattering
{cite}`sabine1988b`. Left uncorrected, the
refinement compensates with a spuriously large Biso and a small scale.
Sabine's polycrystalline model {cite}`sabine1985,sabine1988,sabine1988b`
interpolates between the two-beam limits with $\sin^2\theta$ and
$\cos^2\theta$ weights:

```{math}
:label: corr-sabine

E(hkl) \;=\; E_B \sin^2\theta + E_L \cos^2\theta,
\qquad E_B = \frac{1}{\sqrt{1 + x}},
```

```{math}
:label: corr-sabine-x

x \;=\; \mathrm{ext} \cdot |F|^2 \cdot \left(\frac{\lambda}{V}\right)^2
\cdot X_{\mathrm{pol}},
\qquad X_{\mathrm{pol}} = 0.079411\cdot\frac{1 + \cos^2 2\theta}{2},
```

{source}`rietx.model.extinction.sabine_extinction`

with $|F|^2$ entering without multiplicity or Lp. The Laue component is the
Laue-case diffracted fraction $\tfrac12[1 - e^{-2\sigma D}]$ integrated over a
Lorentzian coupling $\sigma(k)$ and divided by the kinematic intensity
{cite}`itc-c`. That integral has a closed form:

```{math}
:label: corr-sabine-laue

E_L \;=\; \frac{1}{\pi x}\int_{-\infty}^{\infty}
\tfrac12\left[1 - e^{-2x/(1+u^2)}\right] du
\;=\; e^{-x}\left[I_0(x) + I_1(x)\right],
\qquad x \ge 0,
```

{source}`rietx.model.extinction._laue_and_deriv`

with $I_0$ and $I_1$ the modified Bessel functions, and $E_L = 1$ at $x < 0$.
The papers print two truncated expansions of $E_L$ instead
{cite}`sabine1988b,itc-c`: the series $1 - x/2 + x^2/4 - 5x^3/48 + 7x^4/192$
for $x \le 1$ and an asymptote above. The closed form is derived from their
stated construction and is printed in neither. It is continuous, with
$E_L(1) = 0.67367$, where the printed pair steps by 2.2 % at $x = 1$ and
GSAS-II's six-term series and two-term asymptote step by 3.6 %.
$\mathrm{ext}$ is the squared mosaic-block size $D^2$ in µm². The constant
0.079411 is $r_e^2$ in Å² times $10^8$ Å² per µm², to four figures, so $x$ is dimensionless
with λ in Å and V in Å³.
$\mathrm{ext} = 0$ gives $E \equiv \sin^2\theta + \cos^2\theta = 1$ exactly.

```{warning}
Documented by physics rather than by letter: the Bragg component weights
$\sin^2\theta$ and the Laue component $\cos^2\theta$. That is the opposite of
the naive reading, because backscattering ($2\theta \to 180°$) is the Bragg-case
limit and forward scattering the Laue-case limit.
```

Real powder data reach $x > 1$. On the [QPA guide](../guides/qpa.md)'s first fit,
CaF₂'s reflections run to $x = 6.5$ at the answer. Until 1.10, rietx used
GSAS-II's stepped pair, and that fit stopped with one reflection on the step.
CaF₂'s esd then depended on whether the solver's last Jacobian straddled it:
0.21 wt % on one platform and 2.24 on another.

## Preferred orientation (March-Dollase)

A non-random crystallite orientation distribution biases intensities. The
March distribution {cite}`march1932` as folded into Rietveld refinement by
Dollase {cite}`dollase1986` is a per-reflection multiplier averaged over
the symmetry orbit (multiplicity $M$):

```{math}
:label: corr-md

P_{hkl} \;=\; \frac{1}{M} \sum_{m \in \mathrm{orbit}}
\left[ r^2 \cos^2\alpha_m + \frac{\sin^2\alpha_m}{r} \right]^{-3/2},
```

{source}`rietx.model.preferred_orientation.march_dollase_factors`

where $\alpha_m$ is the angle between the preferred-orientation axis and
the scattering vector of equivalent $m$. Both are reciprocal-lattice
directions (integer $hkl$), so the angle uses the reciprocal metric:

```{math}
:label: corr-md-angle

\cos\alpha \;=\;
\frac{\mathbf{h}_m \cdot G^* \cdot \mathbf{a}}
     {\sqrt{(\mathbf{h}_m \cdot G^* \cdot \mathbf{h}_m)
            (\mathbf{a} \cdot G^* \cdot \mathbf{a})}}.
```

{source}`rietx.model.preferred_orientation.cos2_alpha`

At $r = 1$ every bracket is 1, so $P \equiv 1$ exactly. Off is the identity,
for every reflection and every cell. Friedel mates give identical brackets, so
orbit merging is unaffected.

```{warning}
Codes disagree on the sign convention of $r$, so the physics is the contract
and the letter is not. For a reflection parallel to the axis, $P = r^{-3}$, so
$r < 1$ enhances axial reflections. In Bragg-Brentano reflection geometry with
axis = plate normal, $r < 1$ means a platy habit and $r > 1$ an acicular one. In
transmission (capillary) geometry the sense reverses for the same axis choice.
The correction is geometry-agnostic. The interpretation of $r$ is not.
```

## Preferred orientation (spherical harmonics)

March-Dollase describes one fibre axis with one number. A texture with no
single axis needs the general description, a series of symmetrised spherical
harmonics {cite}`vondreele1997`. Under cylindrical sample symmetry the
multiplier on a reflection's intensity is

```{math}
:label: corr-sh

\begin{gathered}
P_{h} \;=\; 1 + \sum_{l = 2, 4, \ldots}^{L} \frac{4\pi}{2l+1}
\sum_{n} C_l^{\,n}\, k_l(\psi)\, K_l^{\,n}(\mathbf{h}),
\\
k_l(\psi) = \sqrt{\frac{2l+1}{4\pi}}\, P_l(\cos\psi).
\end{gathered}
```

{source}`rietx.crystallography.spherical_harmonics.texture_basis`

$L$ is the declared order. Only even $l$ appear, because a powder pattern
obeys Friedel's law, and $l = 0$ is the phase scale. Each $K_l^n$ is a real
harmonic of the reflection's direction, orthonormal over the sphere and
invariant under the Laue group. The harmonics follow Bunge {cite}`bunge1982`,
with no Condon-Shortley phase. The crystal frame puts $z$ on the principal
axis and $x$ on the next cell edge {cite}`popa1992`. Which $(l, n)$ the
class allows is read off the operators. Every $C = 0$ gives $P \equiv 1$
exactly.

$\psi$ is the angle between the scattering vector and the specimen's
symmetry axis. In symmetric reflection the scattering vector lies along the
plate normal, so $\psi = 0$. In symmetric transmission and in a spinning
capillary it is perpendicular to the axis, so $\psi = 90°$
{cite}`jarvinen1993`. The size of the texture is the texture index
$J = 1 + \sum C^2/(2l+1)$, which is 1 for a random powder.

```{warning}
GSAS-II puts the Bragg-Brentano $\psi$ at 90°. For the same pattern, this
package's coefficient is GSAS-II's times $P_l(0)$, which is $-1/2$ at
$l = 2$. In the five Laue classes without mirrors ($\bar 1$, $2/m$, $4/m$,
$\bar 3$, $6/m$), GSAS-II's $n \ne 0$ functions also have norm $\sqrt 2$, so
those coefficients take a further factor $\sqrt 2$.

GSAS-II 5.8.4's functions are not invariant under the Laue group in three
places: the $n \ne 0$ terms of $\bar 1$ and $2/m$, every term on rhombohedral
axes, and the $n = 3$ terms of $\bar 3 1m$. Each takes two values on one set of
equivalent reflections, so those coefficients have no counterpart here. GSAS-II
also gives $m\bar 3$ one function fewer at $l = 6$ than the group allows.
```

## Quantitative phase analysis and microabsorption

Weight fractions follow the Hill-Howard scale-factor relation
{cite}`hill1987` (see also {cite}`bish1988`):

```{math}
:label: corr-qpa

W_p \;=\; \frac{S_p\, (Z M V)_p}{\sum_q S_q\, (Z M V)_q},
```

{source}`rietx.optimize.qpa.weight_fractions`

with $Z$ formula units per cell, $M$ the formula mass and $V$ the cell volume,
all derived from the refined model. Occupancies enter the mass, so the
load-bearing quantity is the cell mass $ZM = \sum \mathrm{occ}\cdot m\cdot A$,
and the $Z/M$ split is display-only. Here $m$ is the site multiplicity and $A$
the atomic weight: the IUPAC standard weight for an element, and for a nuclide
(`D`, `2H`, `7Li`) its own mass, 2.0141 for ²H and the mass number otherwise,
within 0.26 % of the nuclide's mass above A = 4. These are fractions of the modelled
crystalline content, so they still sum to 1 when an amorphous fraction is
present.

When phases differ in absorption, coarse particles of an absorbing phase shadow
their own interiors. That is the Brindley microabsorption effect
{cite}`brindley1945`. In the parallel-path approximation for a sphere of radius
$R$:

```{math}
:label: corr-brindley

\tau(x) \;=\; \frac{3\,[\,2 - e^{-u}(u^2 + 2u + 2)\,]}{u^3},
\qquad u = 2x, \quad x = (\mu_p - \bar\mu)\, R,
```

{source}`rietx.optimize.qpa.brindley_tau`

exact at $\tau(0) = 1$, and $\tau > 1$ for a phase less absorbing than the
matrix. Inside the validity domain this agrees to <1 % with Brindley's own
geometry-averaged table, as represented by the two independently published fits
used by FullProf and MAUD {cite}`taylor1991`, which themselves scatter by ~1 %.
The validity fence is $\mu R \le$ {{ BRINDLEY_MU_R_FENCE }}, derived from
Brindley's $\mu D \le 0.1$ with $D = 2R$ the particle diameter. Conflating the
two conventions is a real and recorded mistake. The corrected fractions are
reported alongside the uncorrected Hill-Howard numbers, and never silently
substituted.
