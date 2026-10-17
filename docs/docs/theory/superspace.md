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

The generator counts 775 inequivalent groups over the 230 basic groups and
24 Bravais classes of (3+1)D lattices, the numbers of {cite}`yamamoto1985` and
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
{cite}`stokes2011` § 5.2, and returns the ITC-C spelling for the eleven groups
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
