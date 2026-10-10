(ch-parameterisation)=
# Parameterisation and constraints

## From tree to vector

The pydantic model tree compiles to an ordered table of parameters with
stable dot-separated paths (`phases.0.cell.a`, `instrument.profile.w`) and
an affine constraint block

```{math}
:label: par-affine

p_{\mathrm{phys}} \;=\; C\, p_{\mathrm{free}} + d,
```

{source}`rietx.params.vector`

with sparse $C$ rebuilt at every stage boundary and constant during a
least-squares run, so a constant matmul stays exact under the autodiff backends.
Cell ties ($b \leftarrow a$, fixed angles) are the identity-row special case,
and Wyckoff site constraints supply general rows. Three kinds of entry are
structurally locked and can never be freed by a glob: the first emission line's
weight (degenerate with the phase scales), symmetry-fixed cell angles, and fully
fixed special positions.

The cell ties follow the space-group setting rather than the crystal system.
Three settings disagree with the system alone, and in each the number of free
cell parameters is the same either way. The count is right while the subspace is
wrong, so the test is which angle is held and which length follows which:

- a monoclinic symbol may be unique-axis $a$, $b$ or $c$, and the one angle its
  symmetry leaves free is $\alpha$, $\beta$ or $\gamma$ respectively;
- an R lattice on rhombohedral axes needs $a = b = c$ with
  $\alpha = \beta = \gamma$ free, in place of the hexagonal-axes
  $b \leftarrow a$ with $c$ free and all three angles fixed. The file decides
  which description arrives: `read_small_structure` resolves a bare `R -3 c`
  over a rhombohedral cell to the `:R` setting;
- the `:1`/`:2` extensions are origin choices and leave the metric untouched.

A symmetry-fixed angle is checked against the value its symmetry demands, and
the cell is refused if it disagrees by more than {{ SYMMETRY_ANGLE_TOL_DEG }}°.
The angle is held at its stored value, so an orthorhombic symbol over a cell
carrying $\beta = 93.2°$ would otherwise compute every $d$-spacing from that
angle in silence.

{source}`rietx.crystallography.symmetry.cell_constraints`

Strictly positive quantities (widths, scales) refine through the softplus
transform,

```{math}
:label: par-softplus

p \;=\; \log(1 + e^{u}),
```

{source}`rietx.params.transforms`

smooth, monotonic and $p > 0$ for all finite $u$, so the optimiser works in an
unconstrained variable instead of pressing a hard zero bound. Bounded quantities
use a logit.

## Site-symmetry degrees of freedom

Coordinates and anisotropic ADPs refine as site-symmetry DOFs. The constraint
bases are derived from the space-group operators by exact rational linear
algebra, with no floating-point tolerance and no per-site lookup table. (Wyckoff
naming is a separate job, delegated to spglib {cite}`togo2024`.)

A displacement δ of a site fixed by operations $\{(R, \mathbf{t})\}$ must
satisfy $R\,\delta = \delta$, so the coordinate basis spans

```{math}
:label: par-coord

\bigcap_R \ker(R - I)
```

{source}`rietx.crystallography.wyckoff.coordinate_basis`

({cite}`itc-a` sect. 8.3.2). The same intersection taken over every rotation
of the group, not one site's, gives the origin shifts that change no structure
factor,

```{math}
:label: par-origin

\bigcap_{R\in G} \ker(R - I)
```

{source}`rietx.crystallography.wyckoff.floating_origin_basis`

({cite}`itc-a` Part 15): the polar axis of a polar group, nothing for a
non-polar one. A fit freeing a coordinate of every atom along it has a flat
direction; fixing it by holding one atom's coordinate, as
`Refinement.hold_floating_origin` does, leaves the others' esds measured
relative to that atom, where a restraint on the mean coordinate would spread
them {cite}`flack1988`. The $U^{ij}$ tensor transforms as $U \to R\,U
R^\top$ under a rotation acting on fractional coordinates, so the allowed
ADP pattern spans the invariant subspace of that action on symmetric 3×3
matrices {cite}`peterse1966` (cross-checked against the cctbx tables
{cite}`grossekunstleve2002`):

```{math}
:label: par-adp

U \;=\; \sum_k \theta_k\, B_k,
\qquad R\, B_k\, R^\top \in \operatorname{span}\{B_j\} \ \forall R.
```

{source}`rietx.crystallography.wyckoff.adp_basis`

Both bases come back as smallest-integer row vectors in a deterministic
RREF-derived form. An $x,x,z$ site gives $[[1,1,0],[0,0,1]]$, and a hexagonal
three-fold site gives $U_{11} = U_{22} = 2U_{12}$ as $[2,2,0,1,0,0]$. Coordinate
DOFs are affine ties through {eq}`par-affine`. ADP DOFs are absolute
($U = \sum_k \theta_k B_k$), which enforces the site symmetry exactly, and a
tensor outside the allowed subspace raises rather than being symmetrised. The
same construction one rank up yields the Stephens $S_{HKL}$ bases of
{ref}`ch-microstructure`.

The stabiliser also fixes how many atoms the site puts in the cell. The
site multiplicity is the orbit length, and by orbit-stabiliser it is

```{math}
:label: par-multiplicity

m \;=\; \frac{|G|}{|G_{\mathbf{x}}|},
\qquad G_{\mathbf{x}} = \{(R, \mathbf{t}) : R\,\mathbf{x} + \mathbf{t} \equiv
\mathbf{x} \bmod 1\},
```

{source}`rietx.crystallography.symmetry.site_orbit`

so $m$ always divides the group order {cite}`itc-a`, and the orbit is generated
one image per left coset of $G_{\mathbf{x}}$. Counting distinct images by
pairwise comparison instead gives the same answer wherever the comparison is
exact, and no answer at all where it is inexact: proximity within a tolerance is
not transitive, so the partition follows the order the operators arrive in and
its size need not divide $|G|$. A coordinate within the tolerance of a special
position is therefore projected onto it before the images are generated, by the
Reynolds average over $G_{\mathbf{x}}$, which moves the coordinate only along
the directions {eq}`par-coord` forbids. Multiplicities feed $ZMV$ and hence
every quantitative phase fraction of {ref}`ch-estimation`, and none of that
reaches $R_{wp}$.

## Magnetic moment constraints

A site's ordered magnetic moment is symmetry-constrained the way a coordinate
is, by the operators that fix the site. Two things differ. A moment is an axial
vector rather than a polar one, and a magnetic operation carries a time-reversal
sign $\varepsilon = \pm 1$ that an ordinary space-group operation does not. An
operation $(R, \mathbf{t}, \varepsilon)$ acts on a moment as

```{math}
:label: par-moment-action

\mathbf{m} \;\to\; \varepsilon \,\det(R)\, R\, \mathbf{m},
```

{source}`rietx.crystallography.magnetic.operators.MagneticOperator.moment_matrix`

with $R$ untransposed {cite}`halpern1939` and $\varepsilon$ the magnetic
group's own sign {cite}`perezmato2015`. The reciprocal-space $R^\top$ convention
this manual uses elsewhere for an hkl does not apply to a real-space axial
vector. The allowed-moment subspace for a site's stabiliser is then
$\bigcap \ker(\varepsilon\det(R)R - I)$, the same construction as
{eq}`par-coord` with this action in place of $R$.

Moment components are stored on the crystal axes, in a right-handed basis of
unit vectors parallel to the cell edges rather than the edges themselves.
Outside a cubic cell the magnitude is therefore something other than
$\sqrt{\sum_i m_i^2}$:

```{math}
:label: par-moment-magnitude

|\mathbf{m}| \;=\; \sqrt{\mathbf{m}^\top G\, \mathbf{m}},
```

{source}`rietx.crystallography.magnetic.operators.moment_magnitude`

with $G$ the unit-vector metric, ones on the diagonal and the cell's cosines
off it. A hexagonal $(1, 1, 0)$ moment therefore has magnitude 1 $\mu_B$, and
not $\sqrt{2}$. A moment in this crystal-axis form also converts to the
orthonormal Cartesian frame `rietx.crystallography.adp.cartesian_basis` already
builds for the ADP tensor of {eq}`par-adp`. Normalise each direct-lattice basis
vector to unit length before applying it:

```{math}
:label: par-moment-cartesian

\mathbf{m}_{\mathrm{cart}} \;=\; \left(\frac{\mathbf{a}}{a}, \frac{\mathbf{b}}{b},
\frac{\mathbf{c}}{c}\right) \mathbf{m},
```

{source}`rietx.crystallography.magnetic.operators.moment_to_cartesian`

the same Cholesky-derived Cartesian frame the ADP construction uses. The
crystal-axis and fractional components differ by $D = \mathrm{diag}(a, b, c)$,
so on crystal-axis components an operation acts by $D R D^{-1}$, which is $R$
itself exactly when every pair of axes $R$ mixes has equal lengths: a 4-fold's
$a$ and $b$, a hexagonal 3-fold's $a$ and $b$. Every tabulated setting meets
that, so the constraint algebra never has to see a cell. A sheared cell of the
same lattice does not: MnF₂'s group restated in $(a, b, a+c)$ has a 4-fold
that mixes $a+c$ with $a$, whose lengths no cell of that setting can make
equal. A magnetic group carries no cell, so in such a setting its crystal-axis
moment methods refuse by name rather than answer with $R$
(`MagneticGroup.axis_mixing` names the operation).

(sec-moment-dofs)=
## Moment degrees of freedom

A magnetic moment takes the same construction one tensor rank *down*, and then
departs from it in the one way that matters. The allowed subspace at a site is
the simultaneous fixed points of the axial action over the site's magnetic
stabiliser: the rotation untransposed, times its determinant, times the
operation's time-reversal sign:

```{math}
:label: par-moment

\bigcap_{(R,\,\mathbf{t},\,\varepsilon)\, \in\, G_{\mathbf{x}}}
\ker\bigl(\varepsilon \det(R)\, R - I\bigr).
```

{source}`rietx.crystallography.magnetic.operators`

The same exact rational nullspace as {eq}`par-coord` and {eq}`par-adp`, and
the same deterministic smallest-integer basis. The transposed set is a group
too, so a wrong action leaves the *dimension* of this subspace unchanged in
every crystal system; the only test that can fail is whether a known moment
lies in the derived span. Measured over all 1651 magnetic space groups
against a grid of sites, $R$ and $R^{\mathsf T}$ give different spans for 543
(group, site) pairs and every one of them is trigonal or hexagonal, so a test
set built from rutile, perovskite and spinel proves nothing here.

Where the moment departs from the ADP is the parameterisation. A powder
average determines $|m|$ and, for a uniaxial structure, the angle to the
unique axis, and nothing else {cite}`shirane1959`. Those undeterminable
directions have to *be columns* of the least-squares problem for the package's
flat-direction rule to name them, and neither the components nor their
coefficients on {eq}`par-moment` is one: a rotation of the moment is a
combination of all of them, so every coefficient would come back unmeasured
and the magnitude, which the data does determine, would come back with no esd.
So the DOFs are a modulus and angles inside the allowed subspace,

```{math}
:label: par-moment-dof

\mathbf{m} \;=\; \mu \sum_k \hat{u}_k(\phi,\theta)\, \mathbf{e}_k,
\qquad \mathbf{e}_i^{\mathsf T} G\, \mathbf{e}_j = \delta_{ij},
```

{source}`rietx.crystallography.magnetic.moments`

with $\{\mathbf{e}_k\}$ a Gram-Schmidt frame of {eq}`par-moment` in the magCIF
unit-vector metric $G$ (ones on the diagonal, cosines of the cell angles
off it). That metric is what makes $\mu$ equal $|m|$ as the CIF defines it: on
hexagonal axes the moment $(1, 1, 0)$ is $1\ \mu_B$, not $\sqrt 2$. One
dimension gives $(\mu)$ with $\mu$ *signed*, two give $(\mu, \phi)$ and three
$(\mu, \theta, \phi)$; the frame is frozen per stage from the declared cell,
like every other discrete object here.

Nothing bounds these DOFs while a stage solves, so a fit can end at
$\phi + 2\pi k$, at $(-\mu, \phi + \pi)$ or at $(\mu, -\theta, \phi + \pi)$,
which are all the same moment. Every commit therefore moves a block into one
chart: $\mu \ge 0$ for two or three DOFs, $\theta \in [0, \pi]$ and
$\phi \in (-\pi, \pi]$, the chart the stage's seed is already in. Each move is
an identity on the moment and negates whole columns at most, so it changes no
esd, and the solver's correlations are re-signed with it. An entry a tie reads
or the caller holds is left where it is. The chart still has a cut at
$\phi = \pm\pi$, so the series fences compare an angle across patterns
modulo a turn.

## Rigid bodies

A rigid body is a set of a phase's atoms placed by one template. The atoms'
coordinates are not parameters of their own: they are the output of a
nonlinear map applied after the affine block, the *derived block* of the
parameter table,

```{math}
:label: par-body

\mathbf{x}_i \;=\; \mathbf{o} \;+\; M^{-1}(a, b, c, \alpha, \beta, \gamma)\,
\operatorname{Exp}(E\,\boldsymbol{\theta})\, R_0\, \mathbf{T}_i ,
```

{source}`rietx.params.bodies.RigidBodyBlock`

with $\mathbf{T}_i$ the template point in Å, $R_0$ the stored orientation,
$\delta\boldsymbol{\omega} = E\,\boldsymbol{\theta}$ the refined rotation
increment (a rotation vector; Solà et al.'s left-plus increment
{cite}`sola2018`), $\mathbf{o}$ the origin and $M$ the closed-form Cartesian
frame with $\mathbf{a}$ along $x$ and $\mathbf{b}$ in the $xy$ plane. There
are as many rotation parameters $\boldsymbol{\theta}$ as the template's
inertia rank: three, with $E = I$, for any body that is not linear; two for a
linear one, $E$'s columns perpendicular to its axis, since a turn about the
axis moves nothing. Every commit composes the increment into the record,
$R_0 \leftarrow \operatorname{Exp}(\delta\boldsymbol{\omega})\,R_0$ and
$\boldsymbol{\theta} \leftarrow 0$, so each stage starts where the exponential
map's Jacobian is the identity. The cell
is a live input, so a body keeps its geometry in Å while the cell refines.
The origin refines like an atom's coordinates, on its site-symmetry degrees of
freedom. Each body atom's esd comes through the map's exact Jacobian at the
refined parameters, chained through the covariance of the origin, rotation and
cell. A distance between two atoms of one body has no esd, because the template
fixes it.

A named-bond torsion turns a declared set of the body's atoms by an angle
$\varphi$ about the line through two other body atoms, before the pose, in
the right-handed sense from the first axis atom to the second (TOPAS's
`Rotate_about_points` {cite}`coelho2018topas`):

```{math}
:label: par-torsion

\mathbf{T}_i \;\leftarrow\; \mathbf{T}_a + R_{\hat{\mathbf{u}}}(\varphi)\,
(\mathbf{T}_i - \mathbf{T}_a),
\qquad \hat{\mathbf{u}} = \frac{\mathbf{T}_b - \mathbf{T}_a}{|\mathbf{T}_b - \mathbf{T}_a|},
```

{source}`rietx.params.bodies.apply_torsions`

with $R_{\hat{\mathbf u}}(\varphi)$ Rodrigues' rotation. The moved set is
declared, not derived from bonds, so the derivative with respect to
$\varphi$ is exact by construction. A dihedral angle that ends on a moved
atom changes by $\varphi$. Like the body's own rotation, a torsion refines
as an anchored increment, $\varphi = \varphi_0 + \delta\varphi$, and every
commit sets $\varphi_0 \leftarrow \varphi_0 + \delta\varphi$ and
$\delta\varphi \leftarrow 0$. About one axis that composition is addition,
so the chart moves by a translation and the esd of $\delta\varphi$ is the
esd of $\varphi$.

## Soft restraints

A bond-length, angle or value restraint contributes one row to the residual
of {eq}`fm-rows` {cite}`waser1963,watkin1994`:

```{math}
:label: par-restraint

r_{\mathrm{restr}} \;=\; \sqrt{w}\,
\frac{\mathrm{computed}(\theta) - \mathrm{target}}{\sigma},
```

{source}`rietx.model.restraints.restraint_residual`

appended after the data rows, so restraints land in the covariance $J^\top J$
and are excluded from $R_{wp}$, Durbin-Watson and the Bérar-Lelann inflation. A
soft observation carries weight in the solution and none in the agreement
statistics. The geometry is nonlinear in θ,
where the background-penalty and Pawley rows are linear, because a bond length
$d = \sqrt{\Delta x^\top G\, \Delta x}$ depends on coordinates and cell. The
rows and their Jacobian are therefore recomputed per θ. The neighbour atom is
taken at a symmetry image $R\mathbf{x} + \mathbf{t} + \mathbf{n}$ with
$(R, \mathbf{t}, \mathbf{n})$ frozen per stage, the exact analogue of the
frozen reflection list, so positions move smoothly inside a stage while the
discrete image choice stays fixed.

## Weighting the restraints

A stage scales every restraint at once. The minimised quantity is then
eq (7) of the IUCr guidelines {cite}`mccusker1999`,

```{math}
:label: par-restraint-weight

S \;=\; S_y \;+\; c_w S_G,
\qquad S_G \;=\; \sum_k w_k \left(
\frac{\mathrm{computed}_k(\theta) - \mathrm{target}_k}{\sigma_k}\right)^2,
```

{source}`rietx.model.forward.CompiledModel.restraint_residual`

with $S_y$ the data rows of {eq}`est-obj` and $S_G$ the restraint rows of
{eq}`par-restraint` squared. The guidelines set $c_w$ high while the structural
model is incomplete or approximate, and reduce it as the model improves. That
makes it a property of the stage rather than of the restraint. It is frozen onto
the compiled model at stage compile, so a schedule changes it between stages and
never inside one.

Two seams decide where the scalar may act. $\sqrt{c_w}$ multiplies the assembled
rows, so every backend sees it through one row builder. It never reaches the
compiled restraints or their partials, whose second consumer computes the
derived-quantity esds of {eq}`est-derived` at $\sigma = w = 1$; a scale leaking
that far would multiply every reported bond esd by $\sqrt{c_w}$. And $c_w = 0$
silences the rows without deleting them, so the row count the agreement
statistics exclude cannot move part-way through a plan.
