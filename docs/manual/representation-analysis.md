(ch-representation-analysis)=
# Representation analysis of magnetic structures

{ref}`ch-parameterisation` § Magnetic moment constraints takes a magnetic
space group as given and builds the subspace of moments its own site
symmetry allows. This chapter is the layer underneath that: given a nuclear
structure, a propagation vector k, and nothing else, which magnetic
arrangements are symmetry-allowed at all, and which of them a powder pattern
can even tell apart. The construction is Bertaut's representation analysis
{cite}`bertaut1968`, the same method BasIreps, SARAh and ISODISTORT
implement; `rietx` builds its own irreps from the space-group operators
rather than reading a published table, so the worked numbers below are
computed, not transcribed.

## The little group and its small irreps

A magnetic structure at propagation vector k breaks the full space group's
symmetry down to the subgroup that leaves k fixed, up to a reciprocal
lattice vector. That subgroup is the little group,

```{math}
:label: rep-little-group

G_{\mathbf{k}} \;=\; \{\, g = (R, \mathbf{v}) \in G \;:\;
R^\top \mathbf{k} \equiv \mathbf{k} \pmod{L^*} \,\},
```

{source}`rietx.crystallography.magnetic.irreps.little_group`

with $L^*$ the true reciprocal lattice of the cell, which is a proper
sublattice of the integer $hkl$ grid whenever the cell is centred. A moment
arrangement varies only within the small (allowed) irreps of $G_{\mathbf{k}}$,
so the whole problem reduces to finding those irreps and projecting the
site's moments onto them.

$G_{\mathbf{k}}$ is finite, so its irreps could be read off an ordinary
character table, except for one complication that the naive approach misses.
Two coset representatives $g_i, g_j$ of the lattice translations compose to a
third, $g_i g_j = g_l$, but the representative $g_l$ that gemmi lists may
differ from $g_i g_j$ itself by a lattice translation $\mathbf{a}_{ij}$. A
representation must satisfy $D(g_i)D(g_j) = D(g_i g_j)$, and pulling the extra
translation's phase out of $D(g_i g_j)$ leaves

```{math}
:label: rep-projective

D(g_i)\,D(g_j) \;=\; \omega(g_i, g_j)\, D(g_i g_j),
\qquad
\omega(g_i, g_j) \;=\; \exp(-2\pi i\, \mathbf{k}\cdot\mathbf{a}_{ij}),
```

{source}`rietx.crystallography.magnetic.irreps.factor_system`

a projective representation with factor system $\omega$ rather than an
ordinary one. $\omega \equiv 1$ away from the zone boundary, where every
$\mathbf{a}_{ij}$ is a lattice vector the phase reduces to $1$. At a
zone-boundary k of a non-symmorphic group, $\omega$ genuinely departs from
$1$, the irreps of $G_{\mathbf{k}}$ have no ordinary counterpart, and their
dimensions are larger than any point-group irrep would give
{cite}`bradleycracknell1972`. Kovalev tabulated exactly this case by hand; the
package finds it by splitting the $\omega$-twisted regular representation of
the little co-group, verifying $D(g_i)D(g_j) = \omega(g_i, g_j)D(g_i g_j)$
before returning anything.

The Pnma structure of LaMnO₃ is the worked case throughout this chapter.
Mn sits on the 4b site $(0, 0, \tfrac12)$, whose site symmetry contains
inversion. At k = 0 the magnetic representation of that orbit decomposes
into the four inversion-even one-dimensional irreps at multiplicity 3 each
and the four odd ones at multiplicity 0, so $\sum n_\nu d_\nu = 12 = 3N$
{cite}`bertaut1968`: a moment is an axial vector, and 4b's inversion forces
every mode onto the even irreps. The 4c site $(x, \tfrac14, z)$, which has no
inversion in its own site symmetry, is the control: its orbit gives
$(1, 2, 2, 1, 1, 2, 2, 1)$ over the same eight irreps, both even and odd
occupied. At the zone-boundary k = $(0, 0, \tfrac12)$ the little group is the
whole point group, $\omega$ is projective, and the 4b orbit decomposes into
two two-dimensional irreps at multiplicity 3 each, again $\sum n_\nu d_\nu =
12$.

## The projection operator and its basis vectors

The object that actually decomposes is not the little group's abstract
irreps but the magnetic representation of one site orbit: the permutation of
the N atoms of a primitive cell under $G_{\mathbf{k}}$, tensored with the
action on the moment each atom carries,

```{math}
:label: rep-gamma-mag

\Gamma_{\mathrm{mag}} \;=\; \Gamma_{\mathrm{perm}} \otimes \Gamma_{\mathrm{axial}},
```

{source}`rietx.crystallography.magnetic.modes.magnetic_representation`

a $3N$-dimensional representation of $G_{\mathbf{k}}$. Replacing
$\Gamma_{\mathrm{axial}}$ (moment, $\det(R)R$) with $\Gamma_{\mathrm{polar}}$
(displacement, $R$) gives the displacive twin of the same construction
{cite}`campbell2006`, which is why `rietx` builds the two from one function.
$\Gamma_{\mathrm{mag}}$ decomposes into a sum of small irreps by the usual
character inner product, and each irrep that occurs is projected out with

```{math}
:label: rep-projector

W^{\nu}_{lm} \;=\; \frac{d_\nu}{|P_{\mathbf{k}}|}
\sum_{g} \overline{D_\nu(g)_{lm}}\;\Gamma_{\mathrm{mag}}(g)
```

{source}`rietx.crystallography.magnetic.modes.basis_vectors`

{cite}`izyumov1991`, the ordinary group-theoretic projection operator carried
over unchanged because the same factor system $\omega$ multiplies both
$D_\nu$ and $\Gamma_{\mathrm{mag}}$ and cancels between them. $W^{\nu}_{11}$
projects onto the first row of the irrep's subspace, whose rank is the
multiplicity $n_\nu$; taking exactly $n_\nu$ independent columns of it, no
more, is what keeps three trial vectors at one atom from over-generating a
basis larger than the multiplicity actually allows.

Those columns are made orthonormal by Gram-Schmidt, but not in the ordinary
Euclidean product on fractional components: a fractional rotation is an
integer matrix of finite order and is generally not orthogonal, so the
natural inner product is the one the cell metric $G$ defines,
$\langle u, v\rangle = u^\top G v$, under which every rotation in
$G_{\mathbf{k}}$ is orthogonal by construction. Only which orthonormal set
comes out of a degenerate multiplicity depends on this choice; the subspace
itself does not.

Where $2\mathbf{k}$ is a reciprocal lattice vector and the irrep's
Frobenius-Schur indicator is $+1$, a unitary gauge exists that makes the
irrep matrices real, and the projected basis vectors come out real in that
gauge. Two other cases stay complex and need a real combination of a
conjugate pair before they describe an actual moment: when
$2\mathbf{k} \notin L^*$ the conjugate irrep belongs to $-\mathbf{k}$ rather
than to $\mathbf{k}$, and the physically irreducible representation pairs
the two arms of the star, $D_{\mathbf{k}} \oplus D^*_{-\mathbf{k}}$; when
$2\mathbf{k} \in L^*$ but the Frobenius-Schur indicator is $0$ or $-1$ the
irrep is complex or pseudoreal at the same k, and the real combination is
$D \oplus D^*$ or $D \oplus D$ respectively. All three double the count of
free real amplitudes against the real case, because the conjugate partner
carries no information the returned vectors do not already hold.

For the LaMnO₃ 4b orbit the four one-dimensional even irreps each give one
real basis vector per axis, and the twelve vectors, three irreps times three
axes plus the identically-vanishing fourth, reproduce Bertaut's own F, G, C
and A modes exactly.

## The lattice return-vector phase

Building $\Gamma_{\mathrm{perm}}$ needs one further piece of bookkeeping.
An operation $g = (R, \mathbf{v})$ of the little group sends orbit atom
$\mathbf{r}_j$ to $R\mathbf{r}_j + \mathbf{v}$, which is another orbit atom
$\mathbf{r}_{\pi(j)}$ plus a lattice vector $\mathbf{a}_g = R\mathbf{r}_j +
\mathbf{v} - \mathbf{r}_{\pi(j)}$ the image had to be brought back by. The
permutation matrix entry carries that vector as a phase,

```{math}
:label: rep-return-phase

\Gamma_{\mathrm{perm}}(g)_{\pi(j)\,j} \;=\; \exp(-2\pi i\, \mathbf{k}\cdot\mathbf{a}_g),
```

{source}`rietx.crystallography.magnetic.modes.permutation_representation`

with every other entry of column $j$ zero. This is why an atom's own phase
enters rather than one global phase for the operation: two atoms of the same
orbit are generally brought back by different lattice vectors under the
same $g$, so $\Gamma_{\mathrm{perm}}(g)$ carries one phase per atom, not one
phase per operation. Setting $g = \{E \mid \mathbf{a}\}$ recovers
$D(\{E \mid \mathbf{a}\}) = \exp(-2\pi i\, \mathbf{k}\cdot\mathbf{a})$, so
$\Gamma_{\mathrm{perm}} \otimes \Gamma_{\mathrm{axial}}$ carries the same
factor system {eq}`rep-projective` the small irreps were built from, and the
decomposition needs no sign correction between the two. The opposite sign
convention is a representation too, of the conjugate factor system, and
decomposes into the same multiplicities at every k tried; what tells the two
apart is that {eq}`rep-projective` itself must hold for the composed
representation, which the wrong sign breaks.

## Isotropy subgroups and the candidate models

A magnetic structure is a point in one irrep's order-parameter space, real
or a realification of a complex one, and the symmetry of that point rather
than of the whole space is what a candidate model actually has. For an
element $h$ of the order-parameter space's image, its fixed subspace is
$\ker(D(h) - I)$; the pointwise stabiliser of a direction $V$ is

```{math}
:label: rep-stabiliser

S(V) \;=\; \{\, h \;:\; D(h)\,\mathbf{v} = \mathbf{v} \ \ \forall\, \mathbf{v} \in V \,\},
```

{source}`rietx.crystallography.magnetic.isotropy.isotropy_directions`

{cite}`stokeshatch1988`, and the isotropy subgroups of one irrep are the
distinct subgroups this construction returns, one per direction with a
different stabiliser. The whole order-parameter space is itself among them,
whose stabiliser is the kernel of the representation, the subgroup that
fixes every direction rather than only one; every other stabiliser sits
between the kernel and the full little group. Each stabiliser, together
with time reversal, is a magnetic space group in the sense
{ref}`ch-parameterisation` already parameterises: `rietx` returns it as an
operator list carrying the irrep label that produced it and the parent-cell
transform (magCIF's $(P, \mathbf{p})$ pair, the magnetic cell's basis
vectors as columns in the parent's fractional coordinates)
{cite}`campbell2006,perezmato2015`, so a candidate a refinement varies the
amplitudes of is never stated except as that pair.

At k = 0 in Pnma, LaMnO₃'s 4b site gives exactly four maximal candidates,
one per inversion-even irrep. The one matching the published A-type
arrangement, moments antiparallel between nearest pseudo-cubic neighbours
along $c$ and parallel along $a$ and $b$, identifies as magnetic space group
62.448 in the numbering of {cite}`perezmato2015`; the G-type arrangement,
every pseudo-cubic neighbour antiparallel, identifies as the unprimed
62.441. Both come out of the same irrep decomposition that produced the
twelve basis vectors above; the isotropy subgroup, not a separate
calculation, is what picks the moment direction each BNS number belongs to.

A candidate's own group also predicts which reflections it can never show
intensity at, independent of the free amplitudes. For an operation
$(R, \mathbf{t}, \varepsilon)$ the magnetic structure factor obeys

```{math}
:label: rep-magnext

M(\mathbf{h}) \;=\; \varepsilon\,\det(R)\,R\,\exp(2\pi i\,\mathbf{h}\cdot\mathbf{t})\;
M(R^\top\mathbf{h}),
```

{source}`rietx.crystallography.magnetic.isotropy.group_absences`

{cite}`gallego2012`, so an operation fixing $\mathbf{h}$ ($R^\top\mathbf{h} =
\mathbf{h}$) constrains $M(\mathbf{h})$ to an eigenvalue-1 subspace of the
right-hand side's matrix; where that leaves only zero, the reflection is
absent whatever the moment. The MAGNEXT rule for a type IV group, one whose
translations include an anti-translation $\mathbf{t}$ (Q22's construction
gives it $\varepsilon = -1$ with $R = I$), is the special case
$\mathbf{h}\cdot\mathbf{t}$ an integer, since then the two terms of
{eq}`rep-magnext` cancel identically. This absence rule follows from the
group alone, before a single moment amplitude is chosen, and it is at least
as restrictive as the site's own family of allowed patterns, since the
family already obeys its own group's symmetry.

## The powder-equivalence criterion

A powder pattern sums the magnetic intensity of a reflection over every
domain related by the parent operations a candidate's own group does not
contain, and over the whole shell of reflections at one $d$. The intensity
itself is $|M_\perp(\mathbf{h})|^2$, with

```{math}
:label: rep-mperp

M(\mathbf{h}) = \sum_j \mathbf{m}_j\, \exp(2\pi i\, \mathbf{h}\cdot\mathbf{r}_j),
\qquad
M_\perp = M - (M\cdot\hat{\mathbf{h}})\,\hat{\mathbf{h}},
```

{source}`rietx.crystallography.magnetic.isotropy.structure_factors`

{cite}`halpern1939` over the atoms of the magnetic cell. That average
destroys some of the information the model carries: two candidate families
are powder-equivalent when each can reproduce the other's powder intensity
at every shell to within a stated tolerance, over the whole range of its
free amplitudes and normalised to the same total moment so a scale can never
be the discriminator {cite}`shirane1959`. `rietx` reports the connected
classes of that relation rather than a ranked list of individually
distinguishable candidates, so a refinement need only try one representative
per class.

Shirane's own example is mechanical here: for a collinear structure whose
moment sits at a general direction of a cubic little group, every direction
of the order-parameter space gives the same powder intensity, and the
[100], [110] and [111] isotropy subgroups of that irrep come out one
equivalence class. Lowering the parent symmetry to tetragonal splits the
same three directions into at least two classes, because the angle a moment
makes with the unique axis is then a measurable quantity a powder pattern
does carry. Neither result is asserted; both are the measured outcome of
fitting one family's amplitudes against the other's intensities. LaMnO₃'s
four Pnma candidates above are the opposite case: each is told apart from
every other by the reflections it does or does not extinguish, so all four
stay in separate classes and a ranked refinement has to try them all.
