(ch-engines)=
# Search engines

This chapter describes the search engines that find a cell from a list of line positions.

{ref}`ch-indexing` establishes what a peak list can say about a lattice. The
search is how a cell is found in the first place.

Two engines are implemented. They share the Q form, the tolerance model and the
scoring panel, and nothing else: one exhausts a metric domain, and the other
guesses indices and solves. Both source papers conclude that no single indexing
program wins, and that running several raises the success rate
{cite}`bergmann2004`. That is the device this package uses for confidence
elsewhere. Agreement between independent methods is the evidence, and
disagreement is reported rather than averaged.

## Searching in the metric components

Both published methods this chapter follows work in direct cell parameters. Here
the search coordinates are the metric components of {eq}`idx-qform` instead,
because $Q$ is linear in them. Over an axis-aligned box $[\theta^-, \theta^+]$
the extremes of $Q(hkl)$ are therefore attained exactly at corners and are read
off componentwise,

```{math}
:label: eng-corner

Q^{\pm}(hkl) \;=\; \sum_j \begin{cases}
  m_j \theta_j^{\pm} & m_j > 0\\
  m_j \theta_j^{\mp} & m_j \le 0
\end{cases}
\qquad m = \mathbf{d}(hkl)\,B^{\mathsf T},
```

{source}`rietx.indexing.dichotomy._q_bounds`

with $B$ the metric basis of {eq}`idx-subspace` and $\mathbf{d}(hkl) =
(h^2, k^2, l^2, kl, hl, hk)$ the design row of {eq}`idx-af`. No corner is
enumerated, and there are $2^n$ of them. The bound is tight rather than merely
valid, which matters because a loose bound prunes less while still returning
correct cells, a regression no recovery test would notice.

The direct-space formulation has no such property. Its $Q$ is a ratio of
trigonometric expressions in the parameters, so the 1991 method needs an
eight-case monotonicity analysis for the cross terms when $hl < 0$, and its
authors attribute their own pre-1991 monoclinic cost to having got those
bounds loose {cite}`boultif1991`. In $(A \ldots F)$ that case split does not
exist in any system, triclinic included.

The box lives in the symmetry subspace, so its dimension is the metric degrees
of freedom, 1 for cubic and 6 for triclinic. The coordinates $\theta$ are read
off the basis's pivot structure.

## Successive dichotomy

The method divides a parameter domain into subdomains, discards any that
provably cannot contain a solution, and recurses
{cite}`louer1972,boultif1991,boultif2004`. Its contrapositive is what earns its
cost next to a cheaper engine. When it exhausts a domain and finds nothing, no
cell of that symmetry within those bounds fits the peak list. No other method
here can make that statement, so `search_complete` is reported per system rather
than assumed. An unfinished search has said nothing at all, and the two cases
must not look alike downstream.

The domain is set by the principal $d$-spacings on the diagonal components and
by an obliquity bound on the rest,

```{math}
:label: eng-domain

\frac{1}{d_{\max}^2} \le G^*_{ii} \le \frac{1}{d_{\min}^2},
\qquad
\lvert 2G^*_{ij} \rvert \;\le\; 2\cos\vartheta_{\max}\sqrt{G^*_{ii}G^*_{jj}},
```

{source}`rietx.indexing.dichotomy._initial_box`

the second being Cauchy–Schwarz with the reciprocal angles restricted to
$[\vartheta_{\max}, 180° - \vartheta_{\max}]$. It is reported as a bound of the
search, never as a claim about lattices. A cell more oblique than this is
outside the domain, and its absence from the results means nothing.

Three prunes run per box, cheapest first. Each is monotone under bisection: a
child's intervals are subsets of its parent's. That monotonicity makes the
pruning sound.

### The metric cone and the volume window

A box whose diagonal interval is non-positive is not a lattice, and $\det G^*$
over the box must intersect the band $[V_{\max}^{-2}, V_{\min}^{-2}]$ implied by
the declared volume range. Bounding that determinant by interval arithmetic on
its expanded form is correct and nearly useless: it evaluates $-G^*_{22}(E/2)^2$
with $E$ at the domain's maximum while the diagonals are at this box's, and the
term then swamps $G^*_{11}G^*_{22}G^*_{33}$. Factoring the correlation matrix
out instead keeps the coupling {eq}`eng-domain` already declares,

```{math}
:label: eng-det

\det G^* \;=\; G^*_{11}G^*_{22}G^*_{33} \cdot \det R,
\qquad
R_{ij} = \frac{G^*_{ij}}{\sqrt{G^*_{ii}G^*_{jj}}},
\quad \lvert R_{ij} \rvert \le \cos\vartheta_{\max},
```

{source}`rietx.indexing.dichotomy._det_interval`

so that for a monoclinic box $\det R \in [1 - \cos^2\vartheta_{\max}, 1]$ and
the "this cell is too small" half of the test can fire at all.

The bound on $R_{ij}$ in {eq}`eng-det` holds only at points inside the domain.
A box can lie wholly outside it, and such a box is refused before either
determinant is bounded,

```{math}
:label: eng-oblique

\min_{\text{box}} \frac{\lvert G^*_{ij} \rvert}{\sqrt{G^*_{ii}G^*_{jj}}}
\;>\; \cos\vartheta_{\max}
\quad \text{for some } i \ne j,
```

{source}`rietx.indexing.dichotomy._outside_obliquity`

with the minimum taken at the box's corners: the smallest $\lvert G^*_{ij}
\rvert$ over the largest diagonals. Clipping $R_{ij}$ to the bound instead
gives an inverted interval and refuses nothing. The expanded determinant
cannot refuse such a box either, because it carries $G^*_{22}$ twice and its
interval bound loses the coupling. Near a singular metric the observed lines
then keep finding reflections, and the subtree does not converge.

### Line matching and Hall's condition

For each observed line, some trial $hkl$'s $[Q^-, Q^+]$ must reach it within
$k\sigma_{\text{eff}}$, and past the tolerated number of misses the box is
impossible. That test alone is the weakest necessary condition there is, because
it lets several lines point at the same reflection. An indexing is an injective
map from lines to reflections, since one $hkl$ has one $Q$ and two resolved
lines cannot both be it. The box must therefore admit a matching, and Hall's
theorem requires
$\lvert N(S)\rvert \ge \lvert S \rvert$ for every set $S$ of lines. Two
instances of that are free to check: $S$ = every line, whose neighbourhood is
the count of reflections still reaching anything, and $S$ = the lines with a
single candidate, where two lines forced onto one reflection is a violation at
$\lvert S \rvert = 2$.

{source}`rietx.indexing.dichotomy._assignment_possible`

### One grid pass per system

A centred trial set is a strict subset of the primitive one, so a centred box
has fewer reflections with which to reach the same lines. Its matching test is
strictly harder, and every box surviving it survives the primitive test. The
centred pass can therefore find no metric the primitive pass misses. All it ever
contributed was the scoring, recovered by re-running the assignment under each
admissible centring at the leaves.

The search runs in two phases, and merging them into one loop breaks it. A
merged depth-first stack dives to a leaf through the first grid cell it likes
and explores that cell's entire bisection subtree, which in four dimensions is
effectively unbounded, before it looks at the second cell. So the grid is
completed breadth-first at the literature's steps ({{ AXIS_STEP }} Å in a
principal $d$-spacing and {{ ANGLE_STEP_DEG }}° in a reciprocal angle
{cite}`itc-h-indexing`), with the prunes applied between dimensions, and only
then are the survivors bisected, best first.

Where to stop bisecting is a separate question from the measurement tolerance,
and conflating the two breaks the search outright. Exhaustiveness comes from the
pruning, which is exact however coarse the leaves are. Acceptance only has to
leave a box whose centre the assign-and-refine loop can polish onto the true
cell. The box is small enough when the indexing inside it is unique, with no
observed line carrying two candidate reflections. A width crossing a threshold
is the wrong test, because a high-index reflection has a large $\lVert m \rVert$
and its interval stays wide long after the assignment has stopped being
ambiguous.

Tolerated unindexed lines are the most valuable option here, and the gain the
2004 paper reports for itself {cite}`boultif2004`. Without them one impurity
line prunes the box containing the truth and the engine returns nothing,
confidently, which is the failure this whole subsystem exists to prevent.
Raising the count past a small default manufactures cells instead: each extra
tolerated line is one more coincidence a wrong metric is allowed to have.

## Index-heuristic trial and error

The second engine assumes the indices of a few base lines and solves the metric
exactly {cite}`werner1964,werner1985`. With $n$ metric parameters, $n$ assigned
lines determine them by an exact $n \times n$ solve, so the search runs over
index assignments rather than over a domain. That is a combinatorial space no
volume window prunes, and one where a bad base line poisons the answer exactly
where a wide domain poisons the dichotomy. It is the independence worth having:
the two engines fail on different inputs.

Its base-line index limit is small for an arithmetic reason. A base line of low
$Q$ cannot carry a large index without implying an axis longer than the domain
allows.

{source}`rietx.indexing.trial_error.search_trial_error`

The engine carries no exhaustiveness claim. It can contribute a `found_by` vote
and a Borda rank, and it can never contribute to `search_complete`. A restricted
search is never a verdict about the sample.

## Zone indexing, assessed and declined

A third engine in the ITO lineage {cite}`visser1969` was assessed and left
unimplemented. The attractive half of the argument is real. ITO searches zones:
the continuously searched dimension is never more than one at any stage, in any
system including triclinic, so a monoclinic problem becomes three sequential
one-dimensional coincidence searches rather than a four-dimensional box. It
assumes no indices, only that two of the first few lines are real reflections
whose common zone is populated. That is a genuinely different failure mode from
both landed engines, and it is what would make an agreement vote worth
something.

What refutes the hopeful version is that it buys no immunity to a zero-point
error. With

```{math}
:label: eng-ito

R \;=\; \frac{1}{mn}Q(m,n) \;-\; \frac{m}{n}Q' \;-\; \frac{n}{m}Q'',
```

a constant offset $Q \to Q + \delta$ shifts the four $(m, n)$ branches by
different multiples of $\delta$, so it splits the coincidence peak instead of
translating it. The acceptance test is a count, so splitting is worse than
shifting, and per-line errors amplify. An engine with that property fails on
exactly the uncalibrated laboratory data the systematic-error model of
{ref}`ch-indexing` exists for. It also carries no exhaustiveness claim, and its
reduction is weak above twofold symmetry, so it is an orthorhombic-and-below
specialist.

## The obliquity bound

$\vartheta_{\max}$ is the one domain parameter with no physical answer. Every
monoclinic lattice has a $b$-unique description whose $\beta$ lies in
$[60°, 120°]$, because the $a$–$c$ plane is a two-dimensional lattice and Gauss
reduction gives $\lvert\cos\beta\rvert \le a/2c \le 1/2$. A narrow bound
therefore loses some descriptions of a lattice and no lattice. Against that, the
bound enters the cost twice: directly, through the number of angular slabs the
grid cuts, and again through {eq}`eng-det`, where $1 - \cos^2\vartheta_{\max}$
is the whole strength of the small-cell prune.

The bound is nevertheless kept wide, because the search's setting conventions
are prunes rather than projections, and a box straddling the axis-ordering
constraint is kept. "The reduced description is somewhere in the domain" is then
an argument about lattices that the implementation does not structurally enforce
for every system. A search bound may be loose. The one thing it may not do is
exclude the true cell.

{source}`rietx.indexing.dichotomy.MAX_ANGLE_COSINE`

## The reflection ceiling

Every leaf is checked before any enumeration. The count of reflections a cell
would generate to a given $2\theta$ is arithmetic on the cell, so the guard costs
nothing and never touches memory. That is the point: the cells a search proposes
include ones no physical specimen has, and a refinement free to move produced a
49 Å axis at $\beta = 174°$ in testing.

{source}`rietx.indexing.engines.reflection_ceiling_ok`
