(ch-intensities)=
# Intensities

## The species scattering factor

```{math}
:label: int-species

f(s, \lambda) \;=\; f_0(s) + f'(\lambda) + i\, f''(\lambda),
\qquad s = \frac{\sin\theta}{\lambda} = \frac{1}{2d}\ [\text{Å}^{-1}].
```

{source}`rietx.crystallography.dispersion`

$f_0$ is the angle-dependent, wavelength-independent elastic form factor. $f'$
and $f''$ are the angle-independent, wavelength-dependent dispersion
corrections. The split is physical. $f_0$ probes the whole electron density, so
it is keyed by ion (`La3+`). $f'/f''$ are core-level resonance effects, near
enough independent of valence, so they are keyed by element (`La`).
$f'' \ge 0$ in this convention.

$f_0$ uses the five-Gaussian parameterisation of Waasmaier & Kirfel
{cite}`waasmaier1995`:

```{math}
:label: int-f0

f_0(s) \;=\; \sum_{i=1}^{5} a_i\, e^{-b_i s^2} + c,
\qquad \text{valid for } s \le 6\ \text{Å}^{-1}.
```

{source}`rietx.crystallography.scattering.f0`

An ion's label names its charge. A one-charge ion may leave out the digit, so
`Na+` reads as `Na1+`.

The Waasmaier-Kirfel table lacks one ion of the 111 in {cite}`itc-c` Table
6.1.1.3, Y³⁺. Its $f_0$ comes from Table 6.1.1.4 instead, a fit of four
Gaussians. That is {eq}`int-f0` with $a_5 = b_5 = 0$. The fit holds for
$s \le 2$ Å⁻¹, where the table gives its largest error as 0.005 e. Past that
range *International Tables* recommends the free-atom curve, because the core
electrons dominate high-angle scattering. rietx evaluates the fit at every
$s$. It falls 0.57 e below the free atom at $s = 3$ Å⁻¹ and turns negative
past 3.86 Å⁻¹.

$f'/f''$ come from the Cromer-Liberman tabulation
{cite}`cromer1970,cromer1981`, the crystallographic reference calculation and
what {cite}`itc-c` §4.2.6 tabulates. That choice makes a disagreement with
another Rietveld code attributable. The Kissel & Pratt high-energy-limit
correction {cite}`kissel1990` is applied on top of it, and reaches −1.3 e at
uranium.

Absorption edges are never interpolated across, since $f''$ jumps by nearly an
order of magnitude across one grid interval at the Fe K edge. Within
{{ NEAR_EDGE_EV }} eV of an edge the request is refused outright, because the
true $f''$ there is the XANES of the compound, which no atomic table knows.
Supply measured overrides instead.

Dispersion is applied by default. It was opt-in through v0.6, so every number
recorded in `docs/milestones/` up to and including that milestone was measured
without it. Setting `source.dispersion = None` declines it and reproduces those
numbers bit-identically, and `DISPERSION_NEGLECTED` then says so. Declining a
correction that needs nothing but the species and the wavelength is a modelling
statement, and the diagnostic records it as one.

(int-neutron-b)=
(sec-neutron-b)=
### The neutron scattering length

For neutrons the whole of {eq}`int-species` collapses to one number per
species:

```{math}
:label: int-b

b \;=\; b_{\mathrm{coh}}\ [\text{fm}],
\qquad \frac{\partial b}{\partial s} = 0.
```

{source}`rietx.crystallography.neutron.b_coh`

The derivative is the content of the equation. An X-ray form factor falls off
with $s$ because the electron cloud has spatial extent comparable to $1/s$; a
nucleus is a point scatterer on this scale, so the bound coherent scattering
length carries no angular dependence at all. There is no five-Gaussian
expansion and no $f'/f''$, and every value this table stores is real. For the
resonant absorbers $b$ is complex, and the table carries its real part (see the
thermal-table note below).

Values are the Sears tabulation {cite}`sears1992`, reproduced as {cite}`itc-c`
§4.4.4 Table 4.4.4.1. That is the same volume this package already relies on for
dispersion, flat-plate absorption and the Lorentz-polarisation factor. Three
properties have no X-ray counterpart, and each breaks an assumption the X-ray
path is entitled to make.

- $b$ may be negative: H, Li, Ti, V and Mn among the natural-abundance elements.
  A negative $b$ is a 180° phase shift on scattering, and not an error state.
  $|F|^2$ stays positive while individual terms of the sum do not, so anything
  taking an absolute value or a square root of a single species' amplitude is
  wrong here.
- $b$ depends on the isotope rather than the element. $b(^{1}\mathrm{H}) =
  -3.741$ fm against $b(^{2}\mathrm{H}) = +6.671$ fm is a change of sign, and
  deuteration is routine for that reason. An isotope resolves to its own row and
  a mass number is kept, while an ionic charge is discarded, because the nucleus
  does not care about valence electrons. {eq}`int-species` takes the opposite
  convention, where an ion resolves to its element because $f'/f''$ is a
  core-level effect. There the element is the identity; here the isotope is.
  The X-ray lookups read an isotope label as its element (`2H` and `D` as H,
  `7Li1+` as Li⁺), since the electrons do not see the nucleus's mass, so one
  deuterated structure goes on both histograms of a joint fit.
- The table is thermal. For the resonant absorbers (Cd, Sm, Eu, Gd, and notably
  $^{113}$Cd and $^{157}$Gd) $b$ is complex and varies with wavelength near a
  resonance, the neutron analogue of an X-ray edge. At one constant wavelength a
  single thermal value is the right number. An instrument spanning a range of
  wavelengths would need $b(\lambda)$, which this table cannot give.

Everything downstream of the amplitude is unchanged. {eq}`int-F` takes $b$ where
it took $f$, the Debye-Waller factors of {eq}`int-dw-aniso` are properties of
the displacement and not of the probe, and {eq}`int-friedel` is trivially
satisfied because $B \equiv 0$ when the amplitude is real. The
Lorentz-polarisation factor {eq}`corr-lp` reduces to the bare Lorentz factor.
Neutrons are not polarised by the monochromator the way the Thomson cross
section polarises X-rays, so there is no polarisation term to carry, and
$K = 1$ makes the numerator of {eq}`corr-lp` identically 1. That is not the
unpolarised value. $K$ is the $\sigma$-polarised fraction everywhere in this
manual, and an unpolarised X-ray beam sits at $K = 0.5$.

## The structure factor

```{math}
:label: int-F

F(hkl) \;=\; \sum_j \mathrm{occ}_j\, f_j(s)
\sum_m T_{jm}(\mathbf{h})\,
e^{2\pi i\, \mathbf{h}\cdot(R_m \mathbf{x}_j + \mathbf{t}_m)},
```

{source}`rietx.crystallography.structure_factor.structure_factors_squared`

where the inner sum runs over a per-atom subset of symmetry operations, chosen
once per stage so that special-position images are not double counted. The
subset is frozen and discrete, while the positions it produces stay smooth
functions of the refined coordinates. Intensities use $|F|^2$ with the
reflection multiplicity applied separately {cite}`rietveld1969`. Multiplicities
are computed by explicit orbit counting under the Laue group, so
$\pm\mathbf{h}$ always merge into one orbit.

## Debye-Waller factors and ADP representations

Isotropic sites take $T = \exp(-B_j s^2)$ with $B_{\mathrm{iso}} = 8\pi^2
U_{\mathrm{iso}}$ (Å²) {cite}`itc-c`, identical for every image, so it
factors out of the orbit sum. Anisotropic sites do not factor:

```{math}
:label: int-dw-aniso

T_{jm}(\mathbf{h}) \;=\;
\exp\!\bigl(-2\pi^2\, \mathbf{q}^\top U^*_j\, \mathbf{q}\bigr),
\qquad \mathbf{q} = R_m^\top \mathbf{h},
\qquad U^*_{ij} = U^{ij} a^*_i a^*_j.
```

{source}`rietx.crystallography.structure_factor`

Three representations of the same tensor appear in the literature, named
explicitly here so that "U" cannot mean whichever one the reader had in mind.
The IUCr nomenclature report {cite}`trueblood1996` is the authority for the
definitions. Its own recommendation is to report $U^{ij}$ or $\beta^{ij}$, and
$U^*$ is not one of its symbols:

- $U^{ij}$ (Å²), the CIF `_atom_site_aniso_U_ij` convention, defined by
  $T(\mathbf{h}) = \exp(-2\pi^2 \sum_{ij} U^{ij} h_i h_j a^*_i a^*_j)$. This is
  the stored form, so what goes into a CIF is what came out of one.
- $U^*$ (dimensionless), $U^*_{ij} = U^{ij} a^*_i a^*_j$, the mean-square
  displacement tensor in fractional coordinates. The report's dimensionless
  parameter is $\beta^{ij} = 2\pi^2 U^*_{ij}$, so $U^*$ is the letter of the
  International Tables and of cctbx rather than the report's own. The $2\pi^2$
  is the whole difference. $U^*$ transforms as
  $U^* \to R\,U^* R^\top$, so evaluating the image atom's factor at
  $\mathbf{h}$ is identically the parent's at $R^\top\mathbf{h}$, the
  reciprocal-space action again. The structure factor uses this form, and the
  identity is then exact rather than contingent.
- $U_{\mathrm{cart}}$ (Å²), whose eigenvalues are the physical mean-square
  displacements along the ellipsoid axes, with $U_{\mathrm{eq}} =
  \operatorname{tr}(U_{\mathrm{cart}})/3$ {cite}`fischer1988`.

Positive-definiteness is a property of $U_{\mathrm{cart}}$. The three
representations are congruent, so by Sylvester's law of inertia the signs of the
eigenvalues can be tested in any of them. A non-positive-definite tensor raises
an `ADP_NOT_POSITIVE_DEFINITE` diagnostic. The Debye-Waller factor diverges at
high $Q$, so the finding is not cosmetic. It is a diagnostic rather than a
bound, because the constraint couples all six components. Component order
throughout is $(U_{11}, U_{22}, U_{33}, U_{12}, U_{13}, U_{23})$. Site-symmetry
constraints on both coordinates and ADPs are covered in
{ref}`ch-parameterisation`.

(sec-biso-melting-bound)=
### How large a $B$ can be

$B$ has no upper bound in the least-squares problem, and a wrong model drives
it up rather than down: a spurious atom's displacement parameter "will rise to
a very large value, indicating that it should be removed from the model"
{cite}`watkin2008`. So the magnitude is evidence, and the round robin asks for
it to be reported rather than clamped {cite}`madsen2001`.

The scale it is judged against comes from melting. Reformulating Lindemann's
criterion on the Debye-Waller theory, a solid melts when the root-mean-square
vibration amplitude reaches a critical fraction $\rho$ of the nearest-neighbour
distance $r$, so $\langle u^2\rangle = \rho^2 r^2$ at fusion
{cite}`gilvarry1956`. That paper's $\langle u^2\rangle$ is the amplitude normal
to the reflecting plane, which is $U_{\mathrm{iso}}$ exactly, so no convention
is converted here. Taking $r$ from the volume $v$ per atom by
$v = r^3/\sqrt{2}$:

```{math}
:label: int-biso-melt

B_{\mathrm{melt}} \;=\; 8\pi^2 \rho^2 \bigl(\sqrt{2}\,v\bigr)^{2/3}
\qquad [\text{\AA}^2]
```

{source}`rietx.strategy.staged.biso_melting_bound`

The volume relation is stated for close-packed lattices, with that paper's own
licence to use it more widely: the variation of $v/r^3$ from the close-packed
value for other lattice types is "too small to consider here".

$\rho$ is taken as the loosest of the four ratios that paper quotes, so a
report is past every criterion in it rather than past one reading. On ordinary
inorganic solids the bound is then a few Å²: corundum 4.6, LaB₆ 5.2,
fluorapatite 5.9, Si 8.1, NaCl 8.7, across 8.5–22.4 Å³ per atom.

It is a guard and never a bound, for a reason the source states itself. The
theory is restricted to isotropic monatomic solids and "is not directly
applicable to elements with complex lattices", where $\rho$ may depend on
lattice type. A cap resting on that extrapolation would refuse fits the source
cannot speak about. A genuinely mobile site can also sit above the bound
honestly, a cavity cation or a superionic sublattice being the usual cases. A
fit past it reports `BISO_UNUSUALLY_LARGE`.

## Anomalous scattering and the powder average

With dispersion on, Friedel's law dies in a non-centrosymmetric group:
$|F(\mathbf{h})|^2 \ne |F(-\mathbf{h})|^2$. A powder cannot resolve the pair,
since $d(\mathbf{h}) = d(-\mathbf{h})$ and both land in one peak. The model must
therefore return the orbit average rather than one representative's value.
Splitting the species factor into real and imaginary parts,

```{math}
:label: int-AB

\begin{aligned}
A(\mathbf{h}) &= \sum_j \mathrm{occ}_j\, (f_{0,j} + f'_j)
\sum_m T_{jm}\, e^{2\pi i \mathbf{h}\cdot\mathbf{x}_{jm}}, \\
B(\mathbf{h}) &= \sum_j \mathrm{occ}_j\, f''_j
\sum_m T_{jm}\, e^{2\pi i \mathbf{h}\cdot\mathbf{x}_{jm}},
\end{aligned}
```

gives $F = A + iB$, and since $T$ is real, $F(-\mathbf{h}) =
\overline{A - iB}$, so

```{math}
:label: int-friedel

\langle |F|^2 \rangle \;=\;
\tfrac{1}{2}\bigl(|F(\mathbf{h})|^2 + |F(-\mathbf{h})|^2\bigr)
\;=\; |A|^2 + |B|^2
```

{source}`rietx.crystallography.structure_factor`

exactly, over the same orbit sums, with no second orbit pass and no
centro/non-centro case split. In a centrosymmetric group $A$ and $B$ share one
common phase, so the cross term vanishes identically. $f'' = 0$ makes
$B \equiv 0$ and recovers $|F|^2$ bit-identically, so a structure without a
dispersion block is unchanged. Merging $\pm\mathbf{h}$ is therefore exact
with or without anomalous scattering, but for two different reasons, and
{eq}`int-friedel` is what keeps one representative per Laue orbit the
*correct* thing to enumerate, not an approximation.

## The magnetic structure factor

A neutron carries a moment, so it scatters from the *magnetization density* of
an ordered structure as well as from its nuclei. For a reflection at
$\mathbf{Q}$ under a magnetic space group whose operations carry a
time-reversal sign $\varepsilon_s = \pm 1$,

```{math}
:label: int-Fmag

\mathbf{F}_m(\mathbf{Q}) \;=\; p \sum_j \mathrm{occ}_j\, f_j(s)\, T_j
\sum_s \varepsilon_s \det(R_s)\, R_s\, \mathbf{m}_j\,
e^{2\pi i\, \mathbf{Q}\cdot(R_s \mathbf{x}_j + \mathbf{t}_s)},
\qquad
p = \frac{\gamma r_0}{2} = 2.695\ \mathrm{fm}\ \mu_B^{-1},
```

{source}`rietx.crystallography.magnetic.scattering`

with $\mathbf{m}_j$ the site's moment in $\mu_B$ {cite}`rodriguezcarvajal1993`.
Two things in that expression are not the nuclear ones. A moment is an axial
vector, so an operation acts on it as $\varepsilon_s \det(R_s) R_s$, the
rotation *untransposed*, times the determinant, times the time-reversal sign,
where $\mathbf{h}$ transforms by $R^{\mathsf T}$ and a tensor by $R U
R^{\mathsf T}$. And $p$ is in fm, the unit the bound coherent scattering
lengths of {ref}`sec-neutron-b` are tabulated in, so $p\,\mathbf{m}$ and $b$
are commensurable and one phase scale multiplies both contributions.

Only the component of $\mathbf{F}_m$ perpendicular to $\mathbf{Q}$ scatters
{cite}`halpern1939`:

```{math}
:label: int-Fperp

I_{\mathrm{mag}} \;\propto\;
|\mathbf{F}_m|^2 - |\hat{\mathbf{Q}}\cdot\mathbf{F}_m|^2 .
```

{source}`rietx.crystallography.magnetic.scattering`

$\mathbf{F}_m$ is complex, so the subtracted term is the squared modulus of a
complex projection and not the square of a real dot product. A moment parallel
to $\mathbf{Q}$ contributes exactly nothing, which is why MnF₂'s $(0\,0\,1)$
(a reciprocal-lattice point in range, with the moment along $\mathbf{c}$)
carries no magnetic intensity at all.

The powder average is over the Laue orbit, and that is not the nuclear
case. $|F_\perp|^2$ is *not* constant over the orbit of $\mathbf{Q}$: the
moment direction breaks the Laue symmetry, so "one representative times the
multiplicity" (right for $|F_N|^2$, and exact there for the reason
{eq}`int-friedel` gives) is wrong here. The model returns the average over
the whole orbit, Friedel mates included. After that average a cubic collinear
structure's intensity is independent of the moment direction and a uniaxial
one measures only the angle to its unique axis {cite}`shirane1959`; those are
*results* of the average rather than assumptions, and they are what makes a
moment direction a flat direction of the least-squares problem
({ref}`sec-moment-dofs`).

### The magnetic component's own width

Everything above adds $p^2\langle|F_\perp|^2\rangle$ to
$\langle|F_N|^2\rangle$ and draws the sum once, which is right whenever the
two contributions have the same profile. They need not. A crystallite's
magnetic order need not be coherent across the whole crystallite: antiphase
and domain-wall boundaries, an incompletely grown order parameter near $T_N$,
and chemical disorder that couples to the exchange all cut the magnetic
coherence length below the structural one while leaving the nuclear peaks
untouched. The broadening that follows is Scherrer's, applied to the magnetic
domain ($\approx K\lambda/(L_{\text{mag}}\cos\theta)$, the same
$1/\cos\theta$ law {eq}`ms-scherrer` already reads), and a magnetic
order parameter that varies across the specimen adds the $\tan\theta$ law
instead.

So a phase carries two more coefficients, `magnetic_lor_size` and
`magnetic_lor_strain`, and the intensity is drawn as two components:

```{math}
:label: int-two-component

y(2\theta) \;=\; \sum_k C_k \Big[
  \langle|F_N|^2\rangle_k\,\Omega\big(2\theta - 2\theta_k;\,
  \Gamma_k\big)
  \;+\;
  p^2\langle|F_\perp|^2\rangle_k\,\Omega\big(2\theta - 2\theta_k;\,
  \Gamma^{\text{mag}}_k\big)\Big],
```

with one shared $C_k$ (the phase's single scale, the multiplicity, the
line weight, the Lorentz-polarization factor, the March-Dollase multiplier,
Sabine extinction, specimen absorption and surface roughness, every one of
them a function of $(\text{line}, hkl)$ and of nothing about which
contribution it scales) and one shared position $2\theta_k$. Only the width
differs, and it differs by the composition law the package already uses:
Lorentzian FWHMs add, so

```{math}
:label: int-two-component-width

\Gamma^{\text{mag}}_L \;=\;
\frac{X + \texttt{lor\_size} + \texttt{magnetic\_lor\_size}}
      {\cos\theta}
\;+\;
\big(Y + \texttt{lor\_strain} + \texttt{magnetic\_lor\_strain}\big)
\tan\theta .
```

There is no second scale and no second phase. That is the point: with a single
scale a magnetic peak that is broader than the calculated one has exactly one
way to reduce its residual, and it is to shrink the moment until the narrow
calculated peak's *height* matches the broad observed peak's. Since
$|F_m|^2 \propto m^2$, the moment then comes back low by about the ratio of
the two widths, the fit converges, and nothing in the profile says so.
{eq}`int-two-component` is what stops that; `MAGNETIC_WIDTH_UNMODELLED` is
what says the term is needed while it is still held at zero, read off the
centre-versus-tails sign structure of the residual at the magnetic-only
reflections against the same statistic at the nuclear-only ones.

Both coefficients default to exactly zero, which is the off state: the two
components then have identical widths, the second draw is not built at all,
and the arithmetic is {eq}`int-Fmag`'s single pass. They are only
*identifiable* where the magnetic-to-nuclear intensity ratio differs across
reflections, so a $\mathbf{k} \neq 0$ structure with magnetic-only
satellites measures them and a $\mathbf{k} = 0$ collinear one generally
cannot; the report says which happened rather than quoting a number for both
({ref}`sec-magnetic-width`).

{source}`rietx.model.forward` (`phase_peaks`, `_width_block`)

### The dipole approximation

```{math}
:label: int-ff-dipole

f(s) \;=\; \langle j_0\rangle(s) + \left(\frac{2}{g} - 1\right)
\langle j_2\rangle(s),
\qquad
\langle j_0\rangle(s) = A e^{-a s^2} + B e^{-b s^2} + C e^{-c s^2} + D,
```

{source}`rietx.crystallography.magnetic.form_factor`

with $s = \sin\theta/\lambda = 1/2d$ (the same argument $f_0$ and the
Debye-Waller factor take) and $\langle j_n\rangle$ for $n \ge 2$ carrying an
extra factor $s^2$ {cite}`brown2004`. That factor is why $\langle
j_2\rangle(0) = 0$ and hence $f(0) = 1$ for every ion whatever $g$ is;
dropping it multiplies a rare-earth form factor by roughly $1/s^2$ near the
origin, which the scale absorbs while leaving the *shape* wrong.

For a spin-only 3d ion $g = 2$, the coefficient $2/g - 1$ vanishes identically
and $f = \langle j_0\rangle$. For a rare earth it does not: with
$\langle L\rangle = (2-g)J$ and $\langle S\rangle = (g-1)J$ the normalised
dipole amplitude is $[\langle j_0\rangle\,(L + 2S) + \langle j_2\rangle\,L] /
(L + 2S) = \langle j_0\rangle + ((2-g)/g)\langle j_2\rangle$, which is
{eq}`int-ff-dipole` and not its sign-flipped twin. The two agree only at
$g = 2$, so a spin-only test cannot tell them apart. The output names which
form was used per species, because a fit that does not say is not checkable.

Two rare-earth rows need a note. The row Brown's table labels Ce$^{2+}$ is a
Ce$^{3+}$ calculation: it reproduces Freeman and Desclaux's Dirac-Fock Ce$^{3+}$
values at Brown's own fit error, and they computed no Ce$^{2+}$
{cite}`freeman1979`. So rietx keys it `Ce3+` and refuses `Ce2+` by name. Brown
carries no Pr row of any charge, so Pr$^{3+}$ comes from an older fit with one
exponential fewer {cite}`lisher1971`:

```{math}
:label: int-ff-lisher

\langle j_0\rangle(s) = A e^{-a s^2} + B e^{-b s^2} + C,
\qquad
\langle j_2\rangle(s) = s^2\left[A e^{-a s^2} + B e^{-b s^2} + C\right].
```

{source}`rietx.crystallography.magnetic.form_factor`

That fit is to non-relativistic Hartree-Fock values, while every other
rare-earth row is a fit to Dirac-Fock ones. Its $\langle r^2\rangle$ is about
10 % smaller than a Dirac-Fock Pr$^{3+}$'s would be, so its form factor falls
off a little more slowly with $s$. `approximation_name` names the source
wherever this row is in force.
