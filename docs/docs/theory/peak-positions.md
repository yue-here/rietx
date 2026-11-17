(ch-positions)=
# Peak positions

This chapter gives where each reflection lands on the 2θ axis, from the lattice metric, the wavelength and each aberration that shifts a peak.

## Lattice metric and Bragg's law

The d-spacing of reflection $(h,k,l)$ follows from the reciprocal metric
tensor $G^*$ {cite}`itc-b`:

```{math}
:label: pos-dspacing

\frac{1}{d^2} \;=\; \mathbf{h} \cdot G^* \cdot \mathbf{h}^\top,
\qquad G^* = G^{-1},
```

{source}`rietx.crystallography.lattice.inv_d_squared`

where $\mathbf{h} = (h, k, l)$ is the row vector of Miller indices. $G$ is the
direct metric tensor, the matrix of dot products of the cell edge vectors. It
turns the six cell parameters into every length and angle the lattice has.

```{math}
:label: pos-metric

G \;=\;
\begin{pmatrix}
\mathbf{a}\cdot\mathbf{a} & \mathbf{a}\cdot\mathbf{b} & \mathbf{a}\cdot\mathbf{c} \\
\mathbf{b}\cdot\mathbf{a} & \mathbf{b}\cdot\mathbf{b} & \mathbf{b}\cdot\mathbf{c} \\
\mathbf{c}\cdot\mathbf{a} & \mathbf{c}\cdot\mathbf{b} & \mathbf{c}\cdot\mathbf{c}
\end{pmatrix}
\;=\;
\begin{pmatrix}
a^2 & ab\cos\gamma & ac\cos\beta \\
ab\cos\gamma & b^2 & bc\cos\alpha \\
ac\cos\beta & bc\cos\alpha & c^2
\end{pmatrix}
\quad [\text{Å}^2].
```

{source}`rietx.crystallography.lattice.direct_metric_tensor`

It is symmetric by construction, and its inverse $G^*$ is in Å⁻². A cubic cell
makes $G = a^2 I$, and an orthogonal one makes it diagonal. Every off-diagonal
element carries a cell angle away from 90°. Written out, with
$(A, B, C, D, E, F) = (G^*_{11}, G^*_{22}, G^*_{33},
2G^*_{23}, 2G^*_{13}, 2G^*_{12})$, {eq}`pos-dspacing` is the familiar
quadratic form

```{math}
:label: pos-dspacing-terms

\frac{1}{d^2} \;=\; A h^2 + B k^2 + C l^2 + D\,kl + E\,hl + F\,hk ,
```

{source}`rietx.crystallography.lattice.inv_d_squared`

For an orthogonal cell ($\alpha = \beta = \gamma = 90°$) this reduces to
$1/d^2 = h^2/a^2 + k^2/b^2 + l^2/c^2$, because the cross terms vanish with the
off-diagonal elements of $G^*$. Peak positions then follow Bragg's law,

```{math}
:label: pos-bragg

2\theta \;=\; 2 \arcsin\!\left(\frac{\lambda}{2d}\right).
```

{source}`rietx.crystallography.lattice.two_theta_deg`

Every emission line diffracts at its own Bragg angle. Differentiating
{eq}`pos-bragg` at fixed $d$ gives the doublet-splitting law

```{math}
:label: pos-doublet

\Delta 2\theta \;=\; 2 \tan\theta \cdot \frac{\Delta\lambda}{\lambda},
```

{source}`rietx.schemas.instrument`

The splitting grows with $\tan\theta$, so a Kα₂ line is not a fixed $2\theta$
offset from Kα₁.

(sec-tof-positions)=
### Time of flight

A time-of-flight neutron bank does not scan an angle at all. It sits at one
fixed scattering angle $2\theta_{\text{bank}}$, sees the whole moderator
spectrum, and separates reflections by the time each neutron takes to fly from
moderator to detector. Bragg's law still holds channel by channel (a neutron
arriving at time $T$ had wavelength $\lambda = 2 d \sin\theta_{\text{bank}}$),
but the *position* of a reflection is a flight time, and the map from $d$ to
$T$ is a calibration of the instrument rather than a consequence of one number
{cite}`larson2004`:

```{math}
:label: pos-tof

T(d) \;=\; \mathrm{DIFC}\, d \;+\; \mathrm{DIFA}\, d^{2}
        \;+\; \mathrm{TZERO} \;+\; \frac{\mathrm{DIFB}}{d}.
```

{source}`rietx.schemas.instrument.TOFSource.tof_from_d`

$\mathrm{DIFC}$ (µs Å⁻¹) is the geometric term, $252.777 \, L \, 2
\sin\theta_{\text{bank}}$ for a total flight path $L$ in metres;
$\mathrm{DIFA}$ (µs Å⁻²) is a small empirical curvature absorbing
sample-position and detector-depth effects; $\mathrm{TZERO}$ (µs) is the
electronic time offset. The fourth term is GSAS-II's `difB` (µs Å), absent
from the GSAS manual's relation and zero in most projects, carried because a
reader built to the three-term form would drop a non-zero one *silently*.

The wavelength–cell degeneracy below reappears here as
$\mathrm{DIFC}$ against the cell: $T \propto \mathrm{DIFC}\, d$ fixes only
the product, so a standard refinement holds the cell at its certified value and
frees $\mathrm{DIFC}$, and a sample refinement does the reverse. Freeing both
on one bank is the same flat direction with different letters.

(sec-harmonics)=
### Monochromator harmonics

A crystal monochromator set to pass $\lambda$ by Bragg reflection from planes of
spacing $d_M$ satisfies $\lambda = 2 d_M \sin\theta_M$. At that same setting

```{math}
:label: pos-harmonic-mono

\frac{\lambda}{n} \;=\; 2\,\frac{d_M}{n}\,\sin\theta_M ,
```

{source}`rietx.schemas.instrument.Harmonic`

and $d_M/n$ is the spacing of the $n$th-order reflection of the same planes. So
the transmitted beam carries $\lambda/n$ for every integer $n \ge 2$ whose
reflection $n\cdot(hkl)$ is allowed. The order belongs to the reflection and not
to the geometry, so no adjustment of $\theta_M$ removes it.

That component diffracts from the specimen too. At detector angle $2\theta$ it
satisfies $\lambda/n = 2 d \sin\theta$, so it is diffracting from planes of
spacing

```{math}
:label: pos-harmonic-d

d \;=\; \frac{\lambda}{2 n \sin\theta}
\qquad\Longleftrightarrow\qquad
\sin\theta_n \;=\; \frac{1}{n}\,\sin\theta_1 ,
```

{source}`rietx.schemas.instrument.Harmonic`

where $\theta_1$ and $\theta_n$ are where the fundamental and the harmonic put
the same reflection. Since $\sin$ increases on $(0°, 90°)$, $\theta_n <
\theta_1$, and the harmonic's peak from a given $hkl$ sits at lower $2\theta$
than the fundamental's. A factor on $\sin\theta$ relates the two, in the same
structure as {eq}`pos-doublet` with a ratio of $n$ in place of a small
$\Delta\lambda$.

Two consequences decide the implementation. First, the harmonic diffracts the
same $hkl$ list with the same $|F|^2$, because $|F|^2$ is evaluated at
$\sin\theta/\lambda = 1/2d$, a property of the reflection alone. A $\lambda/n$
component is therefore an emission line here rather than a second phase. A phase
with a doubled cell reproduces the positions ($2a$ has $d' = 2d$, and $\lambda$
at $d'$ lands where $\lambda/2$ at $d$ does), but it carries the structure
factors of a fictitious cell, so its intensities are wrong. Second, $\lambda/n$
has $n$ times the Ewald radius, so the reflection list is generated for the
shortest wavelength in the source. A list generated for the fundamental leaves
the harmonic's high-angle reflections silently absent.

Whether a harmonic exists at all is arithmetic on the monochromator's own
structure. Copper is face-centred cubic with one atom per lattice point, so
Cu(311) doubles to the fully allowed (622) and the second order passes. A
diamond-structure crystal cut on all-odd indices cancels its own second order:
the doubled indices are all even, and the diamond structure factor $1 +
\exp[2\pi i (h+k+l)/4]$ vanishes unless $h+k+l \equiv 0 \pmod 4$, while doubling
an all-odd triple always gives $h+k+l \equiv 2$.

(sec-satellites)=
### Satellites of a propagation vector

A phase that orders with a commensurate propagation vector $\mathbf{k}$
scatters at $\mathbf{Q} = \mathbf{H} \pm \mathbf{k}$ for every vector
$\mathbf{H}$ of its nuclear reciprocal lattice {cite}`rodriguezcarvajal1993`.
Positions follow from {eq}`pos-dspacing` with $\mathbf{h}$ replaced by

```{math}
:label: sat-position

\mathbf{Q}_{\mathbf{H},m} \;=\; \mathbf{H} + m\,\mathbf{k},
\qquad m \in \{-1,\,0,\,+1\},
```

{source}`rietx.crystallography.satellites`

so $m = 0$ is the nuclear reflection and $m = \pm 1$ its two satellites. The
d-spacing, and hence {eq}`pos-bragg`, is otherwise unchanged: a satellite is a
position, and needs no moment, no magnetic form factor and no magnetic
symmetry to be placed.

Two rules decide which $\mathbf{Q}$ exist, and an implementation can get either wrong.
First, $\mathbf{k}$ and $-\mathbf{k}$ are one vector exactly when

```{math}
:label: sat-plus-minus

2\mathbf{k} \in \Lambda^*,
```

{source}`rietx.crystallography.satellites`

with $\Lambda^*$ the reciprocal lattice, which is a *sublattice* of the
integer $hkl$ grid whenever the direct lattice is centred. On a C lattice
$(\tfrac12, 0, 0)$ and $(-\tfrac12, 0, 0)$ are therefore distinct, because
$(1,0,0)$ violates $h + k = 2n$, while $(0, 0, \tfrac12)$ is a single vector
because $(0,0,1)$ is a lattice point. Second, $\mathbf{H}$ runs over
$\Lambda^*$ itself: the centring conditions decide which $\mathbf{H}$ exist,
but a glide or a screw absence is a condition on the *nuclear structure
factor*, and a satellite has no nuclear structure factor to be absent from:
applying those conditions to a satellite drops reflections that are there.

The multiplicity of a satellite is the number of distinct $\mathbf{Q}$ in its
orbit under the Laue group, Friedel mates merged, with the reciprocal-space
action $R^\top$. It is obtained by enumeration: the plausible closed form
$|{\rm orbit}(\mathbf{H})| \times |{\rm star}(\mathbf{k})|$ is not even a
bound, because $R^\top\mathbf{H}$ and $R^\top\mathbf{k}$ are images under the
*same* $R$ and because reducing an arm of the star back into the first cell
shifts the parent by a lattice vector.

### A child's cell through its parent

A child phase (a superstructure, a distortion, a magnetic supercell) is stated
in a cell whose axes are $P$ applied to its parent's, $(\mathbf{a}', \mathbf{b}',
\mathbf{c}') = (\mathbf{a}, \mathbf{b}, \mathbf{c})\,P$. Its metric is the
parent's carried through $P$, plus the lattice strain the child's lower
symmetry allows {cite}`campbell2006`:

```{math}
:label: pos-child-metric

G' \;=\; P^{\top}\!\left(G_{\mathrm{p}} + 2\,L\,E\,L\right)P,
\qquad E = \sum_j s_j E_j,
\qquad L = \mathrm{diag}(a, b, c)\ \text{of the parent}.
```

{source}`rietx.crystallography.metric.child_metric`

$G_{\mathrm{p}}$ is the parent's metric {eq}`pos-metric`, and the $E_j$ span the
symmetric matrices that the child's point group leaves invariant and the
parent's average removes, so a parent cell and a list of amplitudes $s_j$ name
every metric the child's symmetry allows, once. The $E_j$ are orthonormal in the
parent's Cartesian frame, so each $s_j$ is a dimensionless strain amplitude, and
$E$ is the Green–Lagrange strain of that frame exactly, at any size. The six
child parameters $(a', b', c', \alpha', \beta', \gamma')$ are then read off
$G'$ and are outputs; the parent's cell and the amplitudes are what refines.
With every $s_j = 0$ the child's metric is $P^{\top} G_{\mathrm{p}} P$.

A real lattice needs $G'$ positive definite. Writing $G_{\mathrm{p}} = L\,C\,L$
with $C$ the cosine matrix of the parent's angles, that holds exactly when
$C + 2E$ is positive definite. A sufficient condition for any combination of the
$n$ amplitudes is $|s_j| < \lambda_{\min}(C) / (2 n \lVert E_j \rVert_2)$, since
$\lambda_{\min}(C + 2E) \ge \lambda_{\min}(C) - \lVert 2E \rVert_2$ (Weyl's inequality).
A freed amplitude is bounded a relative {{ PARENT_STRAIN_PD_MARGIN }} inside that box, so the metric
at the bound is still positive definite to working precision. A tighter bound
on a strain is the caller's.

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

{source}`rietx.params.vector.check_wavelength_freedom`

For one histogram that one-parameter family is an exactly flat direction of the
residual, whatever the data quality, so $\lambda$ and the cell cannot both be
free. Differentiating {eq}`pos-bragg` in $\lambda$ gives

```{math}
:label: pos-dlambda

\frac{\partial\, 2\theta}{\partial \lambda}
 \;=\; \frac{2\tan\theta}{\lambda},
```

{source}`rietx.model.forward`

the same $\tan\theta$ signature as {eq}`pos-doublet`, and the signature a
uniform cell scaling has. Across $N$ histograms of one specimen the cell is one
object and the $\lambda_i$ are $N$ separate ones, so the family
{eq}`pos-lambda-cell` collapses to a single scalar $s$. Fixing one $\lambda_i$
fixes $s$, and the other $N-1$ become measurable against the shared lattice. One
wavelength is held, and at most $N-1$ are free.

## Aberration shifts

rietx models additive $2\theta$ shifts that have distinct angular signatures.
The signatures separate them, and only barely (see the decorrelation workflow
below). Which shifts exist depends on the geometry, because each one is derived
for a single specimen shape. The two under the zero-point error are flat-plate
aberrations, and the capillary has its own pair further down.

### Zero-point error

The zero-point error is a constant shift, and the only aberration common to
every geometry.

### Sample displacement

In Bragg-Brentano geometry a flat specimen whose surface sits a distance $s$ off
the goniometer axis shifts every line. Only the ratio of $s$ to the goniometer
radius $R$ enters, and both are in mm {cite}`wilson1963,klug1974`:

```{math}
:label: pos-displacement

\Delta 2\theta \;=\; -\frac{2 s}{R} \cos\theta \quad [\mathrm{rad}].
```

{source}`rietx.model.corrections.displacement_shift_deg`

The $\cos\theta$ dependence separates it from the zero-point error.

### Sample transparency

Finite beam penetration puts the effective diffracting surface below the
physical one (thick-sample limit {cite}`klug1974,wilson1963`):

```{math}
:label: pos-transparency

\Delta 2\theta \;=\; -t \sin 2\theta \quad [\mathrm{rad}],
\qquad t = \frac{1}{2 \mu_{\mathrm{eff}} R},
```

{source}`rietx.model.corrections.transparency_shift_deg`

with $t \ge 0$ dimensionless. For strongly absorbing samples $t \to 0$ and the
correction vanishes.

### Decorrelating the flat-plate trio

These three columns (constant, $\cos\theta$, $\sin 2\theta$) are nearly
collinear over a typical angular range, and all three trade against the cell
parameters. Decorrelate them by calibration. Refine zero and displacement on a
standard whose certified cell is held fixed, save the instrument profile, and
load it frozen for sample work.

### Capillary displacement

The Debye-Scherrer counterpart applies to a capillary whose diffracting volume
sits off the centre of the $2\theta$ circle {cite}`mccusker1999`:

```{math}
:label: pos-capillary

\Delta 2\theta \;=\; \frac{-a \sin 2\theta + b \cos 2\theta}{R}
\quad [\mathrm{rad}].
```

{source}`rietx.model.corrections.capillary_displacement_shift_deg`

Here $a$ is the displacement along the incident beam, positive downstream, and
$b$ the displacement perpendicular to it in the diffraction plane, positive
toward increasing $2\theta$. Both are in mm, like $R$. The paper prints the same
expression as $(x \sin 2\theta - y \cos 2\theta)/R$ and draws no axes. The signs
above are fixed by derivation, and other codes attach the letter $x$ to the
other term, so match the shapes and not the letters. Both terms are zero when
the capillary is centred, and both are held fixed unless the geometry declares
$R$.

The trio for this geometry is (constant, $\sin 2\theta$, $\cos 2\theta$), and it
is separable to the same limited degree. Over $5$–$160°$ the smallest eigenvalue
of the unit-column Gram matrix is $5.2 \times 10^{-2}$, and over $5$–$25°$ it is
$1.1 \times 10^{-5}$.

## Wavelength scales

Kα₁/Kα₂ wavelengths here are peak positions of the measured line shapes, and not
centroids. They are quoted on one consistent scale, the NIST X-ray Transition
Energies Database {cite}`srd128,deslattes2003`. Its 3d-metal values derive from
the Hölzer et al. measurements {cite}`holzer1997` and its Mo/Ag values from
Deslattes & Kessler {cite}`deslattes1985`, so the claim is one column of one
evaluation and not one paper.

Use that column for every anode. Mixing wavelength scales between anodes, or
against an older table, is the classic ~100 ppm cell-parameter error. Bearden's
compilation {cite}`bearden1967` is a different scale, with Mo Kα₂ differing by
24 ppm. Correcting individual rows toward it reintroduces the same error.

{source}`rietx.schemas.instrument`
