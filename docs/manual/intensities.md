(ch-intensities)=
# Intensities

## The species scattering factor

```{math}
:label: int-species

f(k, \lambda) \;=\; f_0(k) + f'(\lambda) + i\, f''(\lambda),
\qquad k = \frac{\sin\theta}{\lambda}\ [\text{Å}^{-1}].
```

*Source:* `rietx.crystallography.dispersion`

$f_0$ is the angle-dependent, wavelength-independent elastic form factor;
$f'$ and $f''$ are the angle-independent, wavelength-dependent dispersion
corrections. The split is physical: $f_0$ probes the whole electron density
and is therefore keyed by **ion** (`La3+`), while $f'/f''$ are core-level
resonance effects, essentially independent of valence, keyed by **element**
(`La`). $f'' \ge 0$ in this convention.

$f_0$ uses the five-Gaussian parameterisation of Waasmaier & Kirfel
{cite}`waasmaier1995`:

```{math}
:label: int-f0

f_0(k) \;=\; \sum_{i=1}^{5} a_i\, e^{-b_i k^2} + c,
\qquad \text{valid for } k \le 6\ \text{Å}^{-1}.
```

*Source:* `rietx.crystallography.scattering`

$f'/f''$ come from the Cromer-Liberman tabulation
{cite}`cromer1970,cromer1981` — the crystallographic *reference* calculation
(what {cite}`itc-c` §4.2.6 tabulates), chosen so that a disagreement with
another Rietveld code is attributable rather than mysterious — **with the
Kissel & Pratt high-energy-limit correction** {cite}`kissel1990`, which
reaches −1.3 e at uranium. Absorption edges are never interpolated across
($f''$ jumps by nearly an order of magnitude across one grid interval at the
Fe K edge), and within {{ NEAR_EDGE_EV }} eV of an edge the request is
refused outright: there the true $f''$ is the XANES of the *compound*,
which no atomic table knows. Measured overrides can be supplied instead.
Dispersion is applied by default (it was opt-in through v0.6, so every number
recorded in `docs/milestones/` up to and including that milestone was measured
without it). Setting `source.dispersion = None` declines it and reproduces
those numbers bit-identically; `DISPERSION_NEGLECTED` then says so, because
having declined a correction that needs nothing but the species and the
wavelength is a modelling statement rather than a silence.

(int-neutron-b)=
### The neutron scattering length

For neutrons the whole of {eq}`int-species` collapses to one number per
species:

```{math}
:label: int-b

b \;=\; b_{\mathrm{coh}}\ [\text{fm}],
\qquad \frac{\partial b}{\partial k} = 0.
```

*Source:* `rietx.crystallography.neutron`

The derivative is the content of the equation. An X-ray form factor falls off
with $k$ because the electron cloud has spatial extent comparable to $1/k$; a
nucleus is a point scatterer on this scale, so the bound coherent scattering
length carries no angular dependence at all. There is no five-Gaussian
expansion, no $f'/f''$, and $b$ is real for every nuclide this table covers.

Values are the Sears tabulation {cite}`sears1992`, which is what {cite}`itc-c`
§4.4.4 Table 4.4.4.1 reproduces — the same volume this package already relies on
for dispersion, flat-plate absorption and the Lorentz-polarisation factor. Three
properties have no X-ray counterpart, and each breaks an assumption the X-ray
path is entitled to make:

- **$b$ may be negative** — H, Li, Ti, V and Mn among the natural-abundance
  elements. It is a 180° phase shift on scattering, not an error state.
  $|F|^2$ stays positive; individual terms of the sum do not, so anything
  taking an absolute value or a square root of a *single* species' amplitude is
  wrong here.
- **$b$ depends on isotope, not element** — $b(^{1}\mathrm{H}) = -3.741$ fm
  against $b(^{2}\mathrm{H}) = +6.671$ fm is a change of sign, which is why
  deuteration is routine. So an isotope resolves to its own row and a mass
  number is *kept*, while an ionic charge is discarded because the nucleus does
  not care about valence electrons. That is the opposite convention to
  {eq}`int-species`, where an ion resolves to its element because $f'/f''$ is a
  core-level effect: there the element is the identity, here the isotope is.
- **The table is thermal.** For the resonant absorbers — Cd, Sm, Eu, Gd, and
  notably $^{113}$Cd and $^{157}$Gd — $b$ is complex and varies with wavelength
  near a resonance, the neutron analogue of an X-ray edge. At one constant
  wavelength a single thermal value is the right number; an instrument spanning
  a range of wavelengths would need $b(\lambda)$, which this table cannot give.

Everything downstream of the amplitude is unchanged. {eq}`int-F` takes $b$ where
it took $f$, the Debye-Waller factors of {eq}`int-dw-aniso` are properties of
the displacement and not of the probe, and {eq}`int-friedel` is trivially
satisfied because $B \equiv 0$ when the amplitude is real. The
Lorentz-polarisation factor {eq}`corr-lp` reduces to the bare Lorentz factor,
since an unpolarised neutron beam sets $K = 1$.

## The structure factor

```{math}
:label: int-F

F(hkl) \;=\; \sum_j \mathrm{occ}_j\, f_j(k)
\sum_m T_{jm}(\mathbf{h})\,
e^{2\pi i\, \mathbf{h}\cdot(R_m \mathbf{x}_j + \mathbf{t}_m)},
```

*Source:* `rietx.crystallography.structure_factor`

where $j$ runs over the asymmetric-unit sites with occupancy
$\mathrm{occ}_j$, fractional coordinate $\mathbf{x}_j$ and species factor
$f_j$ of {eq}`int-species`; $(R_m, \mathbf{t}_m)$ is the rotation and
translation of symmetry operation $m$, $T_{jm}$ the Debye-Waller factor of
that image, and $\mathbf{h} = (h, k, l)$ as in {eq}`pos-dspacing`. The inner
sum runs over a per-atom *subset* of symmetry operations, chosen once per
stage so special-position images are not double counted
(the subset is frozen — discrete — while the positions it produces remain
smooth functions of the refined coordinates). Intensities use $|F|^2$ with
the reflection multiplicity applied separately {cite}`rietveld1969`;
multiplicities are computed by explicit orbit counting under the **Laue**
group, so $\pm\mathbf{h}$ are always merged into one orbit.

## Debye-Waller factors and ADP representations

Isotropic sites take $T = \exp(-B_j k^2)$ with $B_{\mathrm{iso}} = 8\pi^2
U_{\mathrm{iso}}$ (Å²) {cite}`itc-c`, identical for every image, so it
factors out of the orbit sum. Anisotropic sites do not factor:

```{math}
:label: int-dw-aniso

T_{jm}(\mathbf{h}) \;=\;
\exp\!\bigl(-2\pi^2\, \mathbf{q}^\top U^*_j\, \mathbf{q}\bigr),
\qquad \mathbf{q} = R_m^\top \mathbf{h},
\qquad U^*_{ij} = U^{ij} a^*_i a^*_j.
```

*Source:* `rietx.crystallography.structure_factor`

Three representations of the same tensor appear in the literature, named
explicitly here per the IUCr nomenclature report {cite}`trueblood1996`:

- $U^{ij}$ (Å²) — the CIF `_atom_site_aniso_U_ij` convention, defined by
  $T(\mathbf{h}) = \exp(-2\pi^2 \sum_{ij} U^{ij} h_i h_j a^*_i a^*_j)$; what
  is stored, so what goes into a CIF is what came out of one.
- $U^*$ (dimensionless) — $U^*_{ij} = U^{ij} a^*_i a^*_j$, the mean-square
  displacement tensor in fractional coordinates. $U^*$ is what transforms
  as $U^* \to R\,U^* R^\top$, which makes evaluating the image atom's
  factor at $\mathbf{h}$ *identically* the parent's at $R^\top\mathbf{h}$ —
  the reciprocal-space action again. This is the form the structure factor
  uses; working in $U^*$ makes the identity exact rather than contingent.
- $U_{\mathrm{cart}}$ (Å²) — eigenvalues are the physical mean-square
  displacements along the ellipsoid axes, and $U_{\mathrm{eq}} =
  \operatorname{tr}(U_{\mathrm{cart}})/3$ {cite}`fischer1988`.

Positive-definiteness is a property of $U_{\mathrm{cart}}$, but the three
are congruent, so by Sylvester's law of inertia the *signs* of the
eigenvalues can be tested in any representation. A non-positive-definite
tensor raises an `ADP_NOT_POSITIVE_DEFINITE` diagnostic — the Debye-Waller
factor diverges at high $Q$, so this is not cosmetic — and it is a
diagnostic rather than a bound because the constraint couples all six
components. Component order throughout is $(U_{11}, U_{22}, U_{33}, U_{12},
U_{13}, U_{23})$. Site-symmetry constraints on both coordinates and ADPs
are covered in {ref}`ch-parameterisation`.

## Anomalous scattering and the powder average

With dispersion on, Friedel's law dies in a non-centrosymmetric group:
$|F(\mathbf{h})|^2 \ne |F(-\mathbf{h})|^2$. A powder cannot resolve the pair
— $d(\mathbf{h}) = d(-\mathbf{h})$, both land in one peak — so the model
must return the **orbit average**, not one representative's value. Splitting
the species factor into real and imaginary parts,

```{math}
:label: int-AB

A(\mathbf{h}) = \sum_j \mathrm{occ}_j\, (f_{0,j} + f'_j)
\sum_m T_{jm}\, e^{2\pi i \mathbf{h}\cdot\mathbf{x}_{jm}},
\qquad
B(\mathbf{h}) = \sum_j \mathrm{occ}_j\, f''_j
\sum_m T_{jm}\, e^{2\pi i \mathbf{h}\cdot\mathbf{x}_{jm}},
```

with $\mathbf{x}_{jm} = R_m\mathbf{x}_j + \mathbf{t}_m$ the image position of
{eq}`int-F`, gives $F = A + iB$, and since $T$ is real, $F(-\mathbf{h}) =
\overline{A - iB}$, so

```{math}
:label: int-friedel

\langle |F|^2 \rangle \;=\;
\tfrac{1}{2}\bigl(|F(\mathbf{h})|^2 + |F(-\mathbf{h})|^2\bigr)
\;=\; |A|^2 + |B|^2
```

*Source:* `rietx.crystallography.structure_factor`

*exactly*, over the same orbit sums — no second orbit pass and no
centro/non-centro case split (in a centrosymmetric group $A$ and $B$ share
one common phase, so the cross term vanishes identically). $f'' = 0$ makes
$B \equiv 0$ and recovers $|F|^2$ bit-identically, so a structure without a
dispersion block is unchanged. Merging $\pm\mathbf{h}$ is therefore exact
with or without anomalous scattering — but for two different reasons, and
{eq}`int-friedel` is what keeps one representative per Laue orbit the
*correct* thing to enumerate, not an approximation.
