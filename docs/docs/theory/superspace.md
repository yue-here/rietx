(ch-superspace)=
# Superspace groups for one-dimensional modulations

A crystal whose atoms are displaced, or whose sites are occupied, by a wave of
wave vector $\mathbf{q}$ that is not a reciprocal-lattice vector has no
three-dimensional translation symmetry left. It is periodic in a
four-dimensional superspace instead, and its symmetry is a (3+1)D superspace
group {cite}`dewolff1981`. This chapter is the operator algebra `rietx` builds
those groups with. It is the layer every later part of a modulated model
rests on (the allowed waves at a site, the satellite absences, the structure
factor), and none of those later parts is built yet: what is here is the
groups, how two of them are compared, their one-line symbols, and the
three-dimensional group of a commensurate section.

## The operators

The coordinates are three external ones, $\mathbf{x}$, and one internal one,
$x_4 = \mathbf{q}\cdot\mathbf{x} + t$, the argument of the modulation function
in the section $t$. In this basis the superspace lattice is $\mathbb{Z}^4$
{cite}`stokes2011`, and an operation is the augmented matrix

```{math}
:label: ss-operator

A(g) \;=\; \begin{pmatrix} R & 0 & \mathbf{v} \\ \mathbf{M} & \varepsilon & \delta
\\ 0 & 0 & 1 \end{pmatrix},
\qquad
\mathbf{q}R \;=\; \varepsilon\,\mathbf{q} + \mathbf{M},
```

{source}`rietx.crystallography.superspace.SuperspaceOperator`

with $R$ and $\mathbf{v}$ the operation of the basic space group,
$\varepsilon = \pm 1$ its action on the internal axis, $\mathbf{M}$ an integer
row fixed by $\mathbf{q}$, and $\delta$ the internal translation. The second
equation is the compatibility condition: an incommensurate $\mathbf{q}$ is
mapped to $\pm\mathbf{q}$ up to a reciprocal-lattice vector, which forces its
irrational part onto a subspace on which every point operation acts as a sign.
In the section phase the operation reads $t' = \varepsilon t + \delta -
\mathbf{q}\cdot\mathbf{v}$.

Composition is the matrix product, and its only non-trivial entry is the
internal translation of the product,

```{math}
:label: ss-composition

\delta_{ab} \;=\; \mathbf{M}_a\cdot\mathbf{v}_b + \varepsilon_a\,\delta_b + \delta_a
\pmod 1,
```

{source}`rietx.crystallography.superspace.SuperspaceOperator`

which is the rule $\tau_3 = \tau_1 + \varepsilon_1\tau_2$ of
{cite}`dewolff1981` written in the lattice basis.

## Generating the groups

Given a basic space group and the form of $\mathbf{q}$, everything in
{eq}`ss-operator` is fixed except $\delta$, and closure under
{eq}`ss-composition` is a set of linear congruences modulo 1 in the unknown
$\delta$ of each coset representative. Its real solutions are the shifts of
the internal origin alone, which move every $\varepsilon = -1$ operation by
the same amount and can be fixed by one equation; what is left is a finite
set, solved exactly by integer row reduction. Two solutions describe the same
group when an affine map of superspace that normalises the basic group,
together with $\mathbf{q} \to \pm\mathbf{q} + \mathbf{H}$ for a
reciprocal-lattice vector $\mathbf{H}$, takes one onto the other
{cite}`vansmaalen2013`:

```{math}
:label: ss-equivalence

S \;=\; \begin{pmatrix} P & 0 & \mathbf{p} \\ \mathbf{S}_M & S_\varepsilon &
S_\delta \\ 0 & 0 & 1 \end{pmatrix},
\qquad
g_2 \;=\; S\,g_1\,S^{-1}.
```

{source}`rietx.crystallography.superspace.equivalent`

The generator counts {{ N_SUPERSPACE_GROUPS_D1 }} inequivalent groups over the 230 basic groups and
{{ N_BRAVAIS_CLASSES_D1 }} Bravais classes of (3+1)D lattices, the numbers of {cite}`yamamoto1985` and
{cite}`stokes2011`, and the test suite asserts both. Groups are compared as
operator lists under {eq}`ss-equivalence`, never as symbols: a symbol is
unique only together with $\mathbf{q}$ and the reflection conditions, and
$\mathbf{q} \to \mathbf{c}^* - \mathbf{q}$ turns the bottom line of one group
into the printed bottom line of an inequivalent one {cite}`yamamoto1985`.

## Symbols

A one-line symbol is the basic group's symbol, $\mathbf{q}$, and one letter per
generator of that symbol, the generator's internal intrinsic translation

```{math}
:label: ss-symbol-letter

\tau \;=\; \delta - \mathbf{q}_r\cdot\mathbf{v},
```

{source}`rietx.crystallography.superspace.symbol`

written 0, s, t, q or h for 0, 1/2, 1/3, 1/4 or 1/6, with $\mathbf{q}_r$ the
rational part of $\mathbf{q}$. An $\varepsilon = -1$ generator always prints 0.
When $\mathbf{q}_r \neq 0$, adding a lattice translation to a generator changes
$\tau$, so a convention picks one: the printer follows the four steps of
{cite}`stokes2011` § 5.2, and returns the ITC-C spelling for the {{ N_ITC_C_EXCEPTIONS }} groups
where that convention and ITC-C differ.

## Commensurate sections

At a rational $\mathbf{q}$ the structure is a superstructure, and which
three-dimensional space group it has depends on the section phase $t_0$. An
operation survives in the section when, for some lattice vector
$(\mathbf{l}, l_4)$,

```{math}
:label: ss-section

\delta + l_4 - \mathbf{q}\cdot(\mathbf{v} + \mathbf{l}) + (\varepsilon - 1)\,t_0
\;=\; 0,
```

{source}`rietx.crystallography.superspace.SuperspaceGroup.section`

and becomes the operation $\{R \mid \mathbf{v} + \mathbf{l}\}$ of the
supercell {cite}`orlov2008`. An $\varepsilon = +1$ operation survives at every
$t_0$ or at none; an $\varepsilon = -1$ one only at a discrete set of sections,
so at rational $\mathbf{q}$ the phase $t_0$ is a parameter of the model. The
test suite reproduces every cell of the two worked tables of
{cite}`orlov2008`.

## Magnetic superspace groups

A magnetic structure modulated along one direction has a (3+1)D symmetry group
whose operations may carry time reversal. Each operation then has a sign
$\theta = \pm 1$ beside {eq}`ss-operator`, $-1$ for a primed operation, and the
signs compose as a product {cite}`perezmato2012`:

```{math}
:label: ss-magnetic-composition

(g_a, \theta_a)\,(g_b, \theta_b) \;=\; (g_a g_b,\; \theta_a\theta_b).
```

{source}`rietx.crystallography.superspace.SuperspaceOperator`

$\theta$ moves nothing in superspace. It is a sign on time-odd quantities: a
moment transforms as $\theta \det(R)\,R$, a displacement as $R$. Pure time
reversal $\{1'|0000\}$ and the anti-translations $\{1'|\mathbf{v}\}$ have the
identity point part, and `rietx` carries them among a group's centrings, as the
magCIF centring loop does.

{cite}`stokes2022` sort the groups into four construct types, with $F$ the
group with every prime removed and $D$ an index-2 subgroup: type 1 is $F$
itself, type 2 the grey group $F + F1'$, type 3 is $D + (F - D)1'$ with the
same lattice, and type 4 is $D + D\{1'|\mathbf{v}\}$ with $2\mathbf{v}$ a
lattice vector. The groups over one superspace group are generated in two
ways. Taking it as $F$, its point generators are primed in every way that
forms a group (types 1 and 3). Taking it as $D$, an anti-translation is added
for each of the sixteen classes of $\mathbf{v}$ with $2\mathbf{v}$ a lattice
vector, and the ones that would add translations are dropped (types 2 and 4).
The results are compared under the equivalence of {eq}`ss-equivalence` with
$\theta$ compared on every operation. The test suite asserts the printed
tables of {cite}`stokes2022` over $P222(0,0,\gamma)000$ and $I222(0,0,\gamma)000$,
and, as a slow test, their count of {{ N_MAGNETIC_SUPERSPACE_GROUPS_D1 }} groups
for one modulation vector. Types 1 to 3 come out as printed; type 4 comes out
two short, which the suite keeps visible as an expected failure.

{source}`rietx.crystallography.superspace.magnetic_superspace_groups`

Every single-$\mathbf{k}$ incommensurate magnetic phase has the group

```{math}
:label: ss-time-reversal-shift

\Omega \;=\; G + \{1' \mid 0\,0\,0\,\tfrac12\}\,G
```

{source}`rietx.crystallography.superspace.SuperspaceGroup.with_time_reversal_shift`

with $G$ a non-magnetic superspace group {cite}`perezmato2012`. The operation
$\{1'|000\tfrac12\}$ multiplies the $n$-th harmonic of a moment by
$\theta\,e^{i\pi n} = -(-1)^n$ and of a displacement by $(-1)^n$. So the moment
modulation keeps odd harmonics only, and a structural modulation it induces
keeps even ones. $\{1'|0000\}$ and $\{1|000\tfrac12\}$ are distinct
operations.

{source}`rietx.crystallography.superspace.SuperspaceOperator.harmonic_factor`

A symbol is the unified magnetic symbol {cite}`campbell2022` of the basic
magnetic group merged with the superspace symbol: $P22'2'(0,0,\gamma)000$ for
type 3, and for types 2 and 4 one phase letter per generator plus one for
$1'$, as in $P222.1'(0,0,\gamma)000s$, which is $\{1'|000\tfrac12\}$ over
$P222(0,0,\gamma)000$ and not the grey group $P222.1'(0,0,\gamma)0000$. As for
the non-magnetic groups, the operator list is the primary datum and a symbol is
a label.

## The group of an irrep at an incommensurate k

For $\mathbf{k} = \mathbf{r} + \lambda\mathbf{d}$ on a symmetry line, the little
group is computed exactly from the declared line, never from a float: an
operation belongs to $G_{\mathbf{k}}$ when $\mathbf{d}R = \mathbf{d}$ and
$\mathbf{r}R - \mathbf{r}$ is a reciprocal-lattice vector, and to the extended
group $G_{\mathbf{k},-\mathbf{k}}$ also when $\mathbf{d}R = -\mathbf{d}$ with
$\mathbf{r}R + \mathbf{r}$ in the reciprocal lattice. This is the same rule
{eq}`ss-operator` imposes on a superspace operation, and one function serves
both.

{source}`rietx.crystallography.representation.irreps.little_group_on_line`

A field $\sum_i c_i\psi_i + \mathrm{c.c.}$ built on a small irrep $D$ is
invariant under the superspace operation $(g, \theta, \delta)$ when

```{math}
:label: ss-irrep-invariance

e^{2\pi i(\delta - \mathbf{k}\cdot\mathbf{v})}\,\mathbf{c}
\;=\; \Gamma(g, \theta)\,\mathbf{c},
```

{source}`rietx.crystallography.representation.incommensurate.operation_matrix`

with $\Gamma(g,\theta) = \theta D(g)$ for $\varepsilon = +1$ and an
conjugate-linear map onto the $-\mathbf{k}$ arm for $\varepsilon = -1$
{cite}`perezmato2012`. For a one-dimensional irrep every operation of the
grey extended little group survives, with $e^{2\pi i\delta} =
\theta\,e^{2\pi i\mathbf{k}\cdot\mathbf{v}}D(g)$: an internal translation of
$\tfrac12$ where that product is $-1$, and of $\tfrac13$, $\tfrac14$ or
$\tfrac16$, with its sign, on polar axes. For a larger irrep the order
parameter can point in several directions, and each class of directions with
its own stabiliser gives one group.

{source}`rietx.crystallography.representation.incommensurate.isotropy_superspace_groups`

