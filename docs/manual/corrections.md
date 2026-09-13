(ch-corrections)=
# Intensity corrections

Each correction in this chapter multiplies the reflection intensity of
{eq}`fm-rietveld`. A method result from shipping all of them, recorded once
here rather than per section: **not one is well judged by ΔRwp** — one
provably cannot move it (capillary absorption, an exact reparameterisation),
one moves it the wrong way when it is right (a declared flat-plate
thickness on a thick specimen), and the largest accuracy wins (dispersion
on quantitative fractions, absorption on ADPs) are invisible in it. Every
correction therefore reports *what it changed* through a record field or a
diagnostic; see {ref}`ch-method`.

## Lorentz-polarisation

```{math}
:label: corr-lp

\mathrm{Lp}(\theta) \;=\;
\frac{K + (1 - K)\cos^2 2\theta}{\sin^2\theta\, \cos\theta}.
```

*Source:* `rietx.model.corrections.lorentz_polarization`

The $1/(\sin^2\theta \cos\theta)$ Lorentz part is the standard
constant-wavelength powder factor (single-crystal rotation Lorentz × powder
ring statistics; {cite}`itc-c` §6.2, {cite}`klug1974`). $K$ is the fraction
of the beam polarised perpendicular to the diffraction plane
($\sigma$-polarised): $K = 0.5$ reproduces the unpolarised
$(1 + \cos^2 2\theta)/2$; a synchrotron beam diffracting in the vertical
plane has $K \approx 0.99$. A diffracted-beam monochromator sets
$K = 1/(1 + \cos^2 2\theta_m)$ {cite}`itc-c,azaroff1955` — and the familiar
26.6° there is a *Cu* number, not a property of the graphite crystal.

## Attenuation coefficients

Specimen absorption needs $\mu$, computed from the refined cell contents
and the McMaster total cross sections {cite}`mcmaster1969`:

```{math}
:label: corr-mu

\mu\ [\mathrm{cm}^{-1}] \;=\;
\sum_{\mathrm{atoms}} \mathrm{occ}\cdot m \cdot
\frac{\sigma_{\mathrm{tot}}\ [\mathrm{barn}]}{V\ [\text{Å}^3]}
```

*Source:* `rietx.crystallography.attenuation`

summed over the asymmetric-unit sites, with $\mathrm{occ}$ the site
occupancy, $m$ its multiplicity ({eq}`par-multiplicity`) — so
$\mathrm{occ}\cdot m$ is the atom count per cell — $\sigma_{\mathrm{tot}}$
the species' total cross section at the working wavelength and $V$ the cell
volume. (1 barn = 10⁻²⁴ cm² and 1 Å³ = 10⁻²⁴ cm³, so the exponents cancel.)
Attenuation means beam *removal*, so the total cross section including
coherent and incoherent scattering is used — the NIST convention
{cite}`hubbell1995`. The tabulation is a ~2 %-spaced logarithmic grid that
cannot represent an absorption edge, so an interval containing an edge is
refused with an error rather than interpolated: a wavelength that close
above an edge also means strong fluorescence, and a refusal is more honest
than any number.

## Capillary (cylindrical) absorption

The transmission coefficient is the volume average of the attenuation
({cite}`itc-c` eq. 6.3.3.1),

```{math}
:label: corr-itc

A \;=\; \frac{1}{V} \int_V e^{-\mu T}\, dV,
```

*Source:* `rietx.model.absorption`

with $T$ the total (incident + diffracted) path length. For a cylinder it
depends only on $\mu R$ and $\theta$; Rouse et al. {cite}`rouse1970` fit
that integral over $0 \le \mu R \le$ {{ CYLINDER_MU_R_MAX }} to better than
0.0035 with

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

*Source:* `rietx.model.absorption`

```{warning}
$A$ here is the **transmission** coefficient, ≤ 1, which the forward model
*multiplies* into the intensity. Most tabulations — including
{cite}`itc-c` Table 6.3.3.2 — print the *absorption correction*
$A^* = 1/A \ge 1$ instead. Getting this backwards inverts the
θ-dependence, and $A(0) = A^*(0) = 1$ means an identity test cannot detect
it: the direction of the θ-dependence is what does ($A$ *increases* with
$2\theta$, because the mean path through a cylinder shortens toward
backscatter). And $b_2 = -0.3750$, not the $-0.0375$ a scan of the paper
prints — see {ref}`ch-method` for how that was settled.
```

The expression factors *exactly* into $A = K(\mu R)\cdot\exp(+c(\mu R)
\sin^2\theta)$ — a constant times a Debye-Waller shape. Applying it to a
model with free scale and displacement parameters is therefore an **exact
reparameterisation**: Rwp cannot move. Its entire physical content is the
Biso shift

```{math}
:label: corr-deltab

\Delta B \;=\; \frac{c(\mu R)\, \lambda^2}{2},
```

*Source:* `rietx.model.absorption.equivalent_delta_biso`

0.13 Å² at $\mu R = 0.5$ and 0.49 Å² at $\mu R = 1.0$ for Cu Kα —
neglecting capillary absorption biases Biso *low* by that much. This is
also why $\mu R$ is a plain float and never refinable: a free $\mu R$ is an
exactly singular direction in the normal equations, not merely a
correlated one.

## Flat-plate absorption

The three flat-specimen cases of {cite}`itc-c` Table 6.3.3.1 follow from
the same volume average {eq}`corr-itc`, each in closed form — nothing is a
fit, so there are no coefficients to transcribe wrongly. The thick
reflection specimen, case (1a), gives $A = 1/2\mu$ with **no θ-dependence
at all** (the $\sin\theta$ of the beam footprint cancels against the
$\sin\theta$ of the penetration depth); it is identical to the phase scale
and is what every Bragg-Brentano fit implicitly assumes. The two
implemented cases, both normalised:

```{math}
:label: corr-fp2

\text{reflection, finite thickness } t:\quad
A = 1 - e^{-2\mu t / \sin\theta} \;\longrightarrow\; 1
\text{ as } \mu t \to \infty,
```

*Source:* `rietx.model.absorption.flat_plate_reflection_absorption`

```{math}
:label: corr-fp3a

\text{symmetric transmission}:\quad
A = \sec\theta\, e^{-\mu t(\sec\theta - 1)}.
```

*Source:* `rietx.model.absorption.flat_plate_transmission_absorption`

```{warning}
The two cases take **opposite** answers about what "off" means. For
reflection the identity is an *infinitely thick* specimen — $\mu t$ absent
means thick, and $\mu t = 0$ is a specimen of no thickness, which
diffracts nothing and raises. This is the reverse of every other
correction here, where 0 is the identity. For transmission, $\mu t = 0$
leaves $\sec\theta$ — physics, not a leftover: the beam footprint on the
tilted plate grows as $\sec\theta$.
```

Bias directions: finite-thickness reflection depresses *high*-angle
intensity, so a Biso refined without it comes back too **large** — the
opposite sign to the capillary. Transmission flips sign with thickness.
Unlike the cylinder, neither expression is exactly absorbed by
{scale, Biso}: the unabsorbed fraction of $\ln A$ is 0.2–1.3 % for
transmission and a few per cent for finite-thickness reflection, measured
at the *reflection* positions. $\mu t$, like $\mu R$, is computed from the
specimen and never refined — but for a different reason (ill-conditioned,
not exactly singular), and the unabsorbed fraction is reported so a caller
can disagree.

## Surface roughness

A rough or loosely packed flat specimen has a packing-density deficit in
its top layer; at low θ the beam crosses it at grazing incidence over a
long path, depressing intensity. Suortti's form {cite}`suortti1972`:

```{math}
:label: corr-suortti

R(\theta) \;=\;
\frac{a + (1 - a)\, e^{-b/\sin\theta}}{a + (1 - a)\, e^{-b}},
```

*Source:* `rietx.model.corrections.surface_roughness_suortti`

normalised so $R(90°) = 1$. Physics, not letters: $a$ is the intensity
fraction surviving at grazing incidence, so $1 - a$ *bounds the
depression*; $b$ is the depleted layer's dimensionless optical depth,
which sets *where in angle* the transition falls — not how deep it goes.
For $b \ge 0$ the result is bounded $0 < R \le 1$: the correction only
ever depresses.

The Pitschke et al. form {cite}`pitschke1993`:

```{math}
:label: corr-pitschke

R(\theta) \;=\; 1 - c\, u (1 - u), \qquad u = \tau / \sin\theta.
```

*Source:* `rietx.model.corrections.surface_roughness_pitschke`

The paper's angle-independent term is factored out because it is exactly
degenerate with the phase scale, leaving the identifiable strength $c$ and
roughness parameter τ. This model has a validity range and does not police
it: $R$ is monotone in θ only while $\sin\theta \ge 2\tau$, and beyond
$\sin\theta = \tau$ (its Eq 18) it would *amplify* intensity. The
`ROUGHNESS_OUTSIDE_REGIME` diagnostic owns the fence — evaluated at the
reflection positions, not over the 2θ grid — while the function itself
stays smooth and unclamped so the Jacobian keeps no kink. Left
uncorrected, roughness biases ADPs severely (the classic result:
Biso refining to −1.9 … −2.5 Å² where the corrected value is +0.3).

## Secondary extinction

Extinction removes intensity from the strongest reflections because the
diffracted beam re-diffracts inside a coherent domain; uncorrected, the
refinement compensates with a spuriously large Biso and small scale.
Sabine's polycrystalline model {cite}`sabine1985,sabine1988,sabine1988b`
blends the two-beam limits by the fraction of a random powder in each
geometry:

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

*Source:* `rietx.model.extinction`

with $E_L$ a six-term series in $x$ for $0 < x \le 1$ and a two-term
asymptote above, $E_L = 1$ at $x \le 0$, and $|F|^2$ entering *without*
multiplicity or Lp. $\mathrm{ext} = 0$ gives $E \equiv \sin^2\theta +
\cos^2\theta = 1$ exactly.

```{warning}
Documented by physics, not letter: the **Bragg** component weights
$\sin^2\theta$ and the **Laue** component $\cos^2\theta$ — the opposite of
the naive reading, because backscattering ($2\theta \to 180°$) is the
Bragg-case limit and forward scattering the Laue-case limit. The two Laue
branches deliberately do not join continuously at $x = 1$ (a ~2 % step,
inherited verbatim from the cross-code reference and out of reach for
real powder data, where $x \ll 1$); smoothing it would break the
cross-code golden.
```

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

*Source:* `rietx.model.preferred_orientation`

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

*Source:* `rietx.model.preferred_orientation`

At $r = 1$ every bracket is 1, so $P \equiv 1$ exactly — the identity when
off, for every reflection and cell. Friedel mates give identical brackets,
so orbit merging is unaffected.

```{warning}
Codes disagree on the sign convention of $r$, so the physics — not the
letter — is the contract. For a reflection parallel to the axis, $P =
r^{-3}$: $r < 1$ *enhances* axial reflections. In Bragg-Brentano
reflection geometry with axis = plate normal, $r < 1$ ⇒ platy habit and
$r > 1$ ⇒ acicular; in transmission (capillary) geometry the sense
reverses for the same axis choice. The correction itself is
geometry-agnostic; the *interpretation of r* is not.
```

Spherical-harmonics texture {cite}`vondreele1997` is not implemented; it is
planned for v2.

## Quantitative phase analysis and microabsorption

Weight fractions follow the Hill-Howard scale-factor relation
{cite}`hill1987` (see also {cite}`bish1988`):

```{math}
:label: corr-qpa

W_p \;=\; \frac{S_p\, (Z M V)_p}{\sum_q S_q\, (Z M V)_q},
```

*Source:* `rietx.optimize.qpa`

with $Z$ formula units per cell, $M$ the formula mass and $V$ the cell
volume — all derived from the refined model. Occupancies enter the mass, so
the load-bearing quantity is the **cell mass** $ZM = \sum \mathrm{occ}\cdot
m\cdot A$, summed over sites as in {eq}`corr-mu` with $A$ the species' atomic
weight; the $Z/M$ split is display-only. These are fractions of the
*modelled crystalline* content: an amorphous fraction still makes them sum
to 1.

When phases differ in absorption, coarse particles of an absorbing phase
shadow their own interiors — the Brindley microabsorption effect
{cite}`brindley1945`. In the parallel-path approximation for a sphere of
radius $R$:

```{math}
:label: corr-brindley

\tau(x) \;=\; \frac{3\,[\,2 - e^{-u}(u^2 + 2u + 2)\,]}{u^3},
\qquad u = 2x, \quad x = (\mu_p - \bar\mu)\, R,
```

*Source:* `rietx.optimize.qpa.brindley_tau`

exact at $\tau(0) = 1$ and $\tau > 1$ for a phase less absorbing than the
matrix. Inside the validity domain this agrees to <1 % with Brindley's own
geometry-averaged table (as represented by the two independently published
fits used by FullProf and MAUD {cite}`taylor1991`, which themselves scatter
by ~1 %). The validity fence is $\mu R \le$ {{ BRINDLEY_MU_R_FENCE }} —
derived from Brindley's $\mu D \le 0.1$ with $D = 2R$ the particle
*diameter*; conflating the two conventions is a real, recorded mistake.
The corrected fractions are reported *alongside* the uncorrected
Hill-Howard numbers, never silently substituted.
