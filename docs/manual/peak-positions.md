(ch-positions)=
# Peak positions

## Lattice metric and Bragg's law

The d-spacing of reflection $(h,k,l)$ follows from the reciprocal metric
tensor $G^*$ {cite}`itc-b`:

```{math}
:label: pos-dspacing

\frac{1}{d^2} \;=\; \mathbf{h} \cdot G^* \cdot \mathbf{h}^\top,
\qquad G^* = G^{-1},
```

*Source:* `rietx.crystallography.lattice`

where $\mathbf{h} = (h, k, l)$ is the row vector of Miller indices and $G$ is
the direct metric tensor of the cell $(a, b, c, \alpha, \beta, \gamma)$,

```{math}
:label: pos-metric

G \;=\;
\begin{pmatrix}
a^2 & ab\cos\gamma & ac\cos\beta \\
ab\cos\gamma & b^2 & bc\cos\alpha \\
ac\cos\beta & bc\cos\alpha & c^2
\end{pmatrix}.
```

*Source:* `rietx.crystallography.lattice.direct_metric_tensor`

Written out, with $(A, B, C, D, E, F) = (G^*_{11}, G^*_{22}, G^*_{33},
2G^*_{23}, 2G^*_{13}, 2G^*_{12})$, {eq}`pos-dspacing` is the familiar
quadratic form

```{math}
:label: pos-dspacing-terms

\frac{1}{d^2} \;=\; A h^2 + B k^2 + C l^2 + D\,kl + E\,hl + F\,hk ,
```

*Source:* `rietx.crystallography.lattice.inv_d_squared`

which for an orthogonal cell ($\alpha = \beta = \gamma = 90°$) reduces to
$1/d^2 = h^2/a^2 + k^2/b^2 + l^2/c^2$, the cross terms vanishing with the
off-diagonal elements of $G^*$. Peak positions then follow Bragg's law,

```{math}
:label: pos-bragg

2\theta \;=\; 2 \arcsin\!\left(\frac{\lambda}{2d}\right).
```

*Source:* `rietx.crystallography.lattice`

Every emission line diffracts at its own Bragg angle. Differentiating
{eq}`pos-bragg` at fixed $d$ gives the doublet-splitting law

```{math}
:label: pos-doublet

\Delta 2\theta \;=\; 2 \tan\theta \cdot \frac{\Delta\lambda}{\lambda},
```

*Source:* `rietx.schemas.instrument`

which grows with $\tan\theta$ — a Kα₂ line is never a fixed offset from Kα₁.

(sec-harmonics)=
### Monochromator harmonics

A crystal monochromator set to pass $\lambda$ by Bragg reflection from planes of
spacing $d_M$ satisfies $\lambda = 2 d_M \sin\theta_M$. At that same setting

```{math}
:label: pos-harmonic-mono

\frac{\lambda}{n} \;=\; 2\,\frac{d_M}{n}\,\sin\theta_M ,
```

*Source:* `rietx.schemas.instrument.Harmonic`

and $d_M/n$ is the spacing of the $n$th-order reflection of the same planes. So
the transmitted beam carries $\lambda/n$ for every integer $n \ge 2$ whose
reflection $n\cdot(hkl)$ is not extinct. The order belongs to the reflection
rather than to the geometry, which is why no adjustment of $\theta_M$ removes
it.

That component diffracts from the specimen too. At detector angle $2\theta$ it
satisfies $\lambda/n = 2 d \sin\theta$, so it is diffracting from planes of
spacing

```{math}
:label: pos-harmonic-d

d \;=\; \frac{\lambda}{2 n \sin\theta}
\qquad\Longleftrightarrow\qquad
\sin\theta_n \;=\; \frac{1}{n}\,\sin\theta_1 ,
```

*Source:* `rietx.schemas.instrument.Harmonic`

where $\theta_1$ and $\theta_n$ are where the fundamental and the harmonic put
the *same* reflection. Since $\sin$ increases on $(0°, 90°)$, $\theta_n <
\theta_1$: **the harmonic's peak from a given $hkl$ sits at lower $2\theta$ than
the fundamental's**, and the two are related by a factor on $\sin\theta$ rather
than by an offset in $2\theta$ — the same structure as {eq}`pos-doublet`, taken
to a ratio of $n$ instead of a small $\Delta\lambda$.

Two consequences decide the implementation. First, the harmonic diffracts the
same $hkl$ list with the same $|F|^2$, because $|F|^2$ is evaluated at
$\sin\theta/\lambda = 1/2d$ — a property of the reflection, not of the
wavelength that reaches it. That is what makes a $\lambda/n$ component an
*emission line* here rather than a second phase: a phase with a doubled cell
reproduces the positions ($2a$ has $d' = 2d$, and $\lambda$ at $d'$ lands where
$\lambda/2$ at $d$ does) but carries the structure factors of a fictitious cell,
so its intensities are wrong. Second, $\lambda/n$ has $n$ times the Ewald
radius, so the reflection list must be generated for the *shortest* wavelength
in the source or the harmonic's high-angle reflections are silently absent.

Whether a harmonic exists at all is arithmetic on the monochromator's own
structure. Copper is face-centred cubic with one atom per lattice point, so
Cu(311) doubles to the fully allowed (622) and the second order passes. A
diamond-structure crystal cut on all-odd indices cancels its own second order:
the doubled indices are all even, and the diamond structure factor $1 +
\exp[2\pi i (h+k+l)/4]$ vanishes unless $h+k+l \equiv 0 \pmod 4$, while doubling
an all-odd triple always gives $h+k+l \equiv 2$.

## The wavelength–cell degeneracy

{eq}`pos-bragg` reaches the wavelength only through the ratio $\lambda/2d$, so
scaling $\lambda$ and every reciprocal-lattice length by the same factor leaves
every computed position unchanged:

```{math}
:label: pos-lambda-cell

\lambda \to s\lambda, \quad \mathbf{a}^{*}_i \to s\,\mathbf{a}^{*}_i
\;\;\Longrightarrow\;\;
2\theta_{hkl} \;\text{unchanged for all}\; hkl .
```

*Source:* `rietx.params.vector.check_wavelength_freedom`

For one histogram that one-parameter family is an exactly flat direction of the
residual, whatever the data quality: $\lambda$ and the cell cannot both be free.
Differentiating {eq}`pos-bragg` in $\lambda$ shows what the freedom would buy
instead —

```{math}
:label: pos-dlambda

\frac{\partial\, 2\theta}{\partial \lambda}
 \;=\; \frac{2\tan\theta}{\lambda},
```

*Source:* `rietx.model.forward`

the same $\tan\theta$ signature as {eq}`pos-doublet`, which is exactly the
signature a uniform cell scaling has. Across $N$ histograms of one specimen the
cell is one object and the $\lambda_i$ are $N$ separate ones, so the family
{eq}`pos-lambda-cell` collapses to a single scalar $s$: fixing one $\lambda_i$
fixes $s$, and the other $N-1$ become measurable against the shared lattice.
Hence exactly one wavelength held and at most $N-1$ free.

## Aberration shifts

Additive $2\theta$ shifts with distinct angular signatures are modelled; the
signatures are what makes them separable, and only barely so (the
decorrelation workflow below). **Which shifts exist depends on the geometry**,
because each is derived for one specimen shape: the two below the zero-point
error are flat-plate aberrations, and the capillary has its own pair further
down.

The **zero-point error** is a constant, and is the only one common to every
geometry. **Sample displacement** in
Bragg-Brentano geometry, for a flat specimen whose surface sits a distance
$s$ off the goniometer axis with goniometer radius $R$
{cite}`wilson1963,klug1974`:

```{math}
:label: pos-displacement

\Delta 2\theta \;=\; -\frac{2 s}{R} \cos\theta \quad [\mathrm{rad}].
```

*Source:* `rietx.model.corrections.displacement_shift_deg`

The $\cos\theta$ dependence is what separates it from the zero-point error.
**Sample transparency** — finite beam penetration puts the effective
diffracting surface below the physical one (thick-sample limit
{cite}`klug1974,wilson1963`):

```{math}
:label: pos-transparency

\Delta 2\theta \;=\; -t \sin 2\theta \quad [\mathrm{rad}],
\qquad t = \frac{1}{2 \mu_{\mathrm{eff}} R},
```

*Source:* `rietx.model.corrections.transparency_shift_deg`

with $t \ge 0$ dimensionless; for strongly absorbing samples $t \to 0$ and
the correction vanishes.

These three columns (constant, $\cos\theta$, $\sin 2\theta$) are nearly
collinear over a typical angular range, and all three trade against the cell
parameters. The house workflow decorrelates them by *calibration*: refine
zero and displacement on a standard whose certified cell is held fixed, save
the instrument profile, and load it frozen for sample work.

**Capillary displacement** is the Debye-Scherrer counterpart, for a capillary
whose diffracting volume sits off the centre of the $2\theta$ circle
{cite}`mccusker1999`:

```{math}
:label: pos-capillary

\Delta 2\theta \;=\; \frac{-a \sin 2\theta + b \cos 2\theta}{R}
\quad [\mathrm{rad}].
```

*Source:* `rietx.model.corrections.capillary_displacement_shift_deg`

Here $a$ is the displacement along the incident beam, positive downstream,
and $b$ the displacement perpendicular to it in the diffraction plane,
positive toward increasing $2\theta$. The paper prints the same expression as
$(x \sin 2\theta - y \cos 2\theta)/R$ and draws no axes; the signs above are
fixed by derivation, and other codes attach the letter $x$ to the other term,
so the *shapes* are what carries the meaning. Both are exactly zero when the
capillary is centred, and both are held fixed unless the geometry declares
$R$.

The trio for this geometry is therefore (constant, $\sin 2\theta$,
$\cos 2\theta$), and it is separable for the same reason and to the same
limited degree: over $5$–$160°$ the smallest eigenvalue of the unit-column
Gram matrix is $5.2 \times 10^{-2}$, and over $5$–$25°$ it is
$1.1 \times 10^{-5}$.

## Wavelength scales

Kα₁/Kα₂ wavelengths are **peak** positions of the measured line shapes, not
centroids, quoted on one consistent scale: the NIST X-ray Transition
Energies Database {cite}`srd128,deslattes2003`, whose 3d-metal values derive
from the Hölzer et al. measurements {cite}`holzer1997` and whose Mo/Ag
values from Deslattes & Kessler {cite}`deslattes1985` — one *column* is the
claim, not one paper. One column of one
evaluation for all anodes is the load-bearing choice — mixing wavelength
scales between anodes (or against an older table) is the classic ~100 ppm
cell-parameter error. Bearden's compilation {cite}`bearden1967` is a
*different* scale (Mo Kα₂ differs by 24 ppm); individual rows must not be
"corrected" toward it.

*Source:* `rietx.schemas.instrument`
