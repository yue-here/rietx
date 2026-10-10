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

{source}`rietx.crystallography.representation.irreps.little_group`

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

{source}`rietx.crystallography.representation.irreps.factor_system`

a projective representation with factor system $\omega$ rather than an
ordinary one. $\omega \equiv 1$ away from the zone boundary, where every
$\mathbf{a}_{ij}$ is a lattice vector the phase reduces to $1$. At a
zone-boundary k of a non-symmorphic group, $\omega$ genuinely departs from
$1$, the irreps of $G_{\mathbf{k}}$ have no ordinary counterpart, and their
dimensions are larger than any point-group irrep would give
{cite}`bradleycracknell1972` (§ 3.7 pp. 155–157). Kovalev tabulated exactly this case by hand; the
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

{source}`rietx.crystallography.representation.modes.magnetic_representation`

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

{source}`rietx.crystallography.representation.modes.basis_vectors`

The construction is {cite}`izyumov1991`'s (his eqn (2.12), p. 19, and its
$G_{\mathbf{k}}$ form (9.1), p. 67). The $d_\nu/|P_{\mathbf{k}}|$ prefactor is
the standard Wigner normalisation, written this way by Davies & Wills (2016,
*arXiv*:1610.00472, eq. 6); Izyumov's own two forms carry $1/n(G)$ and $1/N$
with no $d_\nu$. It is the ordinary group-theoretic projection operator carried
over unchanged, because the same factor system $\omega$ multiplies both
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
$D \oplus D^*$ or $D \oplus D$ respectively.

The free real-amplitude count follows from these cases alone, never from
whether the vectors happen to come out real (Bradley & Cracknell, 1972,
Definition 1.3.7 p. 20 and Theorem 4.6.2 p. 204). Where
$2\mathbf{k} \notin L^*$ every irrep carries $2 n_\nu d_\nu$, even when
its vectors are real, because $C$ and $iC$ give different fields (cosine
against sine modulation), and no irrep at $\mathbf{k}$ is the partner of
another, since $D^*$ lives at $-\mathbf{k}$; the counts close on
$2 \cdot 3N$. Where $2\mathbf{k} \in L^*$ the counts close on $3N$: a real
irrep carries $n_\nu d_\nu$; a complex one $2 n_\nu d_\nu$, with the pair
$D, D^*$ counted once; and a pseudoreal one $n_\nu d_\nu$, because its real
irreducible form has dimension $2 d_\nu$ and complexifies to $D \oplus D$,
so the $n_\nu$ complex copies pair up and only $n_\nu/2$ of them are
independent over the reals. P2₁2₁2₁ at $(\tfrac12,\tfrac12,\tfrac12)$ on a
general site is the smallest example: one pseudoreal irrep with
$n_\nu = 6$, $d_\nu = 2$, and $12 = 3N$ real amplitudes.

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

{source}`rietx.crystallography.representation.modes.permutation_representation`

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

For a displacive order parameter the stabiliser is not the candidate's group
in the parent's lattice: time reversal does nothing to a displacement, so the
group is grey, but the coset character $\varepsilon(\Delta)$ of the
anti-translations enters exactly as for a moment, so the child lattice is the
sublattice on which it is $+1$ and an element $\{R \mid \mathbf{v}+\Delta\}$
belongs to the group when $\varepsilon(\Delta)\,D(R)$ fixes the displacement
{cite}`stokeshatch1988`. The perovskite R-point tilt irrep then gives the six
subgroups $I4/mcm$, $R\bar{3}c$, $Imma$, $C2/m$, $C2/c$, $P\bar{1}$
{cite}`howardstokes1998`.

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

{cite}`halpern1939` over the atoms of the magnetic cell, with the moment and
$\hat{\mathbf{h}}$ in one Cartesian frame, the magnetic lattice's own:
$\mathbf{m} = \sum_i m_i \mathbf{a}_i$ for the contravariant components on the
cell vectors, and $\mathbf{h}$ taken through the inverse of the same row-vector
lattice. A $\mathbf{k} \neq 0$ child cell is usually rotated or left-handed
against the parent axes, so rebuilding either vector from the six cell
parameters alone, in a standard orientation, measures the angle between
them in two different frames. That average
destroys some of the information the model carries: two candidate families
are powder-equivalent when each can reproduce the other's powder intensity
at every shell to within a stated tolerance, over the whole range of its
free amplitudes and normalised to the same total moment so a scale can never
be the discriminator {cite}`shirane1959`. `rietx` reports the connected
classes of that relation rather than a ranked list of individually
distinguishable candidates, so a refinement need only try one representative
per class.

"The whole range" is proved where one of two certificates applies, and
sampled everywhere else. A family that lights a shell the other can never
light is distinguishable whatever its amplitudes, and so is one whose shell
intensities span a direction the other's cannot reach: each shell intensity is
linear in the matrix $\mathbf{b}\mathbf{b}^{\mathsf T}$ (the quadratic form
below), so a family's patterns all lie in one linear subspace, and when one
family's subspace is not inside the other's, all but a measure-zero set of its
patterns fall outside the other's reach. "Proved" here means proved on the
intensity matrices as floating point builds them, to the module's
tolerances, for almost every model of the first family. Two families are
proved *equal* in two cases: when neither has any pattern at all to this
$d$ limit, and when their shell matrices are related by one orthogonal
change of amplitude basis, $\mathbf{Q}^{\mathsf T}\mathbf{G}^B_s\mathbf{Q} =
\mathbf{G}^A_s$ on every shell, so that every pattern of one is a pattern of
the other with the amplitudes rotated (an *isometry*; the two rank-1
directions of one irrep are the measured case). Because $\mathbf{Q}$ is
orthogonal the condition is linear in it and is found by one singular value
decomposition, but the proof is the residual of the congruence and of
$\mathbf{Q}^{\mathsf T}\mathbf{Q} = \mathbf{I}$, both checked and both
printed with the verdict, because an equality certificate is the direction
in which a false answer silently drops a distinguishable model. Two families
proved isometric then share every proved verdict: a separation proved
against one of them, or from one of them, is carried to the other exactly
(`propagated`, naming its source), and is not drawn again. Only proofs are
carried; a sampled verdict stays where it was drawn. One family is proved
*inside* another when a matrix $\mathbf{E}$ with
$\mathbf{G}^A_s = c\,\mathbf{E}^{\mathsf T}\mathbf{G}^B_s\mathbf{E}$ on every
shell is found, so that every pattern of the first is a pattern of the
second with the amplitudes mapped and one scale absorbed (`span`; a rank-1
direction inside its irrep's (a,b) plane is the measured case); it is found
from the moment patterns and proved by the congruence residual, printed
with the verdict. A proved separation then travels along the proved
containments, exactly: a draw of $A$ that $B$ cannot reach is a draw of
every family containing $A$, and is out of reach of every family inside
$B$ (`containment`, naming its source). It also travels to a third family
$C$ that reproduces the draw, by a bound that reads no sign: the
certificate's direction $\hat{\mathbf{y}}$ puts the whole of $B$'s image
(where $B$'s stack has a near-kernel, its amplitudes with a kernel component
no larger than the live one) inside the cone $\cos(\hat{\mathbf{y}}, \mathbf{I}) \ge \mu$, and $C$'s
exact image point at the draw, formed from its fitted amplitudes with
their component along $C$'s own kernel projected out, lies below
$\mu - \rho$, $\rho$ a stated rounding allowance (`transfer`, stored with
every number, the cosine and $\mu - \rho$ printed; a margin $\mu$ below $10^{-8}$ is labelled "proved on the
float Gram stack"). A transfer that does not fire is undecided, never
"equal", and nothing sampled is ever read as a containment. Every other
"equivalent", and every
"distinguishable" no certificate gives, is tested on random amplitude draws
(by default 12 per direction between two irreps and 3 inside one), each
fitted from a few random starts, and is statistical.
"Distinguishable" can then be a fit that stopped in a local minimum on every
start, and "equivalent" can be a set of draws that all missed the part of one
family the other cannot reach. The amplitude basis is made canonical before
any draw, so the classes do not depend on which basis of the same family the
linear algebra returned, but the sampled verdicts remain a function of the
seed and the number of draws and starts. Each verdict says which kind it is:
`rietx.crystallography.magnetic.isotropy.powder_relations` returns one record
per ordered pair of candidates, proved with its certificate named, or sampled
with the number of draws actually made. The printed table marks a class P when
every relation bounding it is proved and S when one rests on draws, and lists
each sampled pair with its draw counts.
The docstring of `rietx.crystallography.magnetic.isotropy.powder_equivalent`
states what is measured about each failure and what is still open.

A third certificate turns a failed fit into a proof. When the first fit of
one family does not reproduce a draw of the other, `rietx` looks for a
weighting $\mathbf{y}$ of the shells with $\sum_s y_s \mathbf{G}_s$
positive semi-definite and $\mathbf{y}\cdot\mathbf{t} < 0$ on the drawn
pattern $\mathbf{t}$: every pattern the family can produce then has
$\mathbf{y}\cdot\mathbf{I} \geq 0$, so none of them is $\mathbf{t}$ (the
weak duality of semidefinite programming), and the draw is proved out of
reach. Directions every shell matrix of the fitting family annihilates are
projected out first, so that a family with an undeterminable amplitude can
still be certified, and the certificate is checked in exact rational
arithmetic before it counts. The check is a proof on the projected stack,
with that kernel taken as structural; the record's `kernel_residual` says how
far the floating-point stack departs from it. What that departure leaves
proved on the full stack is stated too. The kernel block of
$\sum_s y_s \mathbf{G}_s$ is not sign-definite, so no bound on the residual
makes the whole matrix positive semi-definite; what does follow is a bound on
the kernel's share of $\mathbf{y}\cdot\mathbf{I}$ under a bound on the
amplitude along the kernel, and the record's `kernel_amplitude_ratio` is that
bound: no amplitude vector whose component along the kernel is at most that
many times its component along the live directions reproduces the draw, on
the full floating-point stack. A certificate is issued only when the ratio is
at least one, which ties the kernel residual the certificate tolerates to the
margin it is quoted at; on the exact stack the residual is zero and the claim
covers every amplitude vector. It also measures the separation: $1/\|\mathbf{y}\|$
is a lower bound on the relative L2 distance from the draw to the other
family's patterns, and the best fit residual an upper one, and the pair
record carries that bracket as `d` with the certificate itself (`witness`)
so it can be re-checked without the random stream. A draw certified this
way is called distinguishable only when the lower bound is large enough that
no fit could have reached the tolerance `rtol`
($d \geq \mathrm{rtol}\,\sqrt{S}\,\max_s t_s/\|\mathbf{t}\|$ over the $S$
shells it uses); a smaller one is kept and printed, and the fits decide.
"Proved" for this certificate is of the stored draw, not of every model of
the family. An optional per-shell `weights` vector (an inverse standard
deviation, say) changes the norm $d$ is measured in, not what is proved. The
printed table lists every such separation with its bracket and names any
class that holds one, which can happen while classes are still joined
through sampled pairs.

Shirane's own example is mechanical here. His criterion is on the
configurational symmetry (the symmetry of the signed moment arrangement, which
he distinguishes from the chemical one; his MnO case is cubic in the chemical
cell and rhombohedral in the configurational symmetry, and there the direction
is measurable). For a collinear structure whose configurational symmetry is
cubic, every direction
of the order-parameter space gives the same powder intensity, and the
[100], [110] and [111] isotropy subgroups of that irrep come out one
equivalence class. Lowering the parent symmetry to tetragonal splits the
same three directions into at least two classes, because the angle a moment
makes with the unique axis is then a measurable quantity a powder pattern
does carry. Neither result is asserted; both are the measured outcome of
fitting one family's amplitudes against the other's intensities. LaMnO₃'s
four Pnma candidates above are the opposite case: each is told apart from
every other by the reflections it does or does not extinguish, so all four
stay in separate classes, proved rather than sampled, and a ranked refinement
has to try them all.
Shirane's MnO case itself, `F m -3 m` site 4a at
$\mathbf{k} = (\tfrac12, \tfrac12, \tfrac12)$, comes out two classes: the
candidate with its moment along [111] on its own, and the three with moments in
the (111) plane together. For the [111] candidate the
$(\tfrac12\,\tfrac12\,\tfrac12)$ reflection is absent, because there the
moment is parallel to $\mathbf{Q}$. This is the reflection that places MnO's
moments in the (111) planes {cite}`roth1958`.

The fit itself never goes back to the reflections. Because $M_\perp$ is
linear in a family's real amplitudes $\mathbf{b}$, the powder intensity of
shell $s$ is a quadratic form,

```{math}
:label: rep-gram

I_s(\mathbf{b}) = \mathbf{b}^{\mathsf T} G_s\, \mathbf{b},
\qquad
(G_s)_{qr} = \operatorname{Re} \sum_{\text{domains}} \sum_{\mathbf{h}\in s}
\overline{M_{\perp,q}(\mathbf{h})}\cdot M_{\perp,r}(\mathbf{h}),
```

{source}`rietx.crystallography.magnetic.isotropy.gram`

with $M_{\perp,q}$ the perpendicular structure factor of amplitude $q$ alone,
so each candidate is reduced once to one small positive semi-definite matrix
per shell and the least-squares fit, and its exact Jacobian
$2G_s\mathbf{b}$, work on those. A shell where $G_s$ vanishes is one the
family can never light: if the other family's intensity is zero there too
the shell carries no information and is left out, and if it is not, the
pair is distinguishable without a fit.
