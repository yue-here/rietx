(ch-indexing)=
# Indexing

Refinement starts from a cell. Indexing produces one from a list of line
positions, and that list holds very little information. A powder pattern carries
the length of each reciprocal-lattice vector and nothing about its direction.
Everything below follows from that, including the two places where the honest
answer is a refusal.

## The quadratic form

With $(h,k,l)$ assigned to a line, the measured quantity is

```{math}
:label: idx-qform

Q \;\equiv\; \frac{1}{d^2} \;=\; A h^2 + B k^2 + C l^2 + D k l + E h l
+ F h k
\qquad [\text{Å}^{-2}],
```

{source}`rietx.crystallography.lattice.inv_d_squared`

where the six coefficients are the reciprocal metric tensor's components

```{math}
:label: idx-af

(A, B, C, D, E, F) \;=\; \bigl(G^*_{11},\, G^*_{22},\, G^*_{33},\,
2G^*_{23},\, 2G^*_{13},\, 2G^*_{12}\bigr).
```

{source}`rietx.indexing.qspace.design_matrix`

$Q$ is linear in $(A \ldots F)$ {cite}`itc-h-indexing`, and that is
load-bearing three times over. Fitting a cell to assigned lines is a weighted
linear least-squares problem. A trial-and-error engine solving for $n$ metric
parameters from $n$ base lines is an exact $n \times n$ solve. A dichotomy
engine's bounds on $Q$ over a box of cell parameters are attained at box
corners, so the search runs in $(A \ldots F)$. Neither $d$ nor $2\theta$ is
linear in the metric, so indexing works in $Q$ and reports in $Q$, converting to
a cell at the end.

Positions and their esds enter as $Q$ and $\sigma(Q)$, propagated by the
exact derivative

```{math}
:label: idx-sigma-q

\sigma(Q) \;=\; \frac{\pi}{90}\,
\frac{\lvert \sin 2\theta \rvert}{\lambda^2}\, \sigma(2\theta),
```

{source}`rietx.schemas.indexing.q_esd_of_two_theta`

whose constant is worth reading twice. Differentiating
$Q = 4\sin^2\theta / \lambda^2$ with respect to $2\theta$ in degrees picks up
both the $\theta = (2\theta)/2$ chain and the degree conversion. Applying one of
the two alone gives $\pi/180$, a factor-of-two error that makes every line's
weight four times too confident.

## The symmetry-allowed subspace

A crystal system constrains the metric. The allowed $G^*$ patterns are the
invariants of the lattice point group acting as $A(R)[U] = R\,U\,R^\top$,

```{math}
:label: idx-subspace

\mathcal{M} \;=\; \bigcap_{R \in \mathcal{G}} \ker\bigl(A(R^\top) -
I\bigr),
```

{source}`rietx.indexing.qspace.metric_basis`

which is the exact-rational nullspace the anisotropic-ADP basis uses one rank
down, called with the transposed rotations because the reciprocal-space symmetry
action is $R^\top$. Its dimension is the number of free metric parameters: 1
cubic, 2 tetragonal, 2 hexagonal, 2 trigonal, 3 orthorhombic, 4 monoclinic, 6
triclinic. Deriving it rather than tabulating it keeps a non-standard setting
correct with no case table, rhombohedral axes and a $b$-unique monoclinic cell
included.

## What a peak list supports

A line count is a criterion only against the free metric parameters.
{{ MIN_LINES_PER_DOF }} usable lines per free metric parameter means 20 lines is
20-fold over-determined for a cubic cell and 3.3-fold for a triclinic one, so
the data-quality report names the systems it can support instead of answering
yes or no. Positional precision enters as a resolving power, the median
$\sigma(Q)/Q$. Above {{ MAX_RELATIVE_SIGMA_Q }} two cells differing by 0.1 % in
a lattice parameter are indistinguishable, which is the scale at which
derivative-lattice ambiguity lives.

### Which lines drive the search

A search is driven by {{ DEFAULT_SEARCH_LINES }} lines and scored against every
usable one. Conograph argues for a large driven set, 48 against the 20–30 its
contemporaries used, on the grounds that a missing line costs success while a
false line costs only computation. Its enumeration succeeds by a membership
condition on the observed $q$ set, and adding elements cannot break one
{cite}`oishitomiyasu2014`.

That asymmetry does not transfer here, and the reason lies in the acceptance
rule rather than in the enumeration. A candidate is accepted only if it indexes
all but {{ DEFAULT_N_UNINDEXED }} of the driven lines, which is an absolute
budget and not a membership test. Each foreign line admitted spends that budget,
and past it the true cell is refused rather than out-ranked. Enlarging the driven
set therefore has a failure mode Conograph's lacks, and measurement bears it out:
on a 68-line lab pattern carrying 16 foreign lines, going from 20 driven lines to
32 loses the certified lattice from the candidate list altogether.

Which lines pays, where how many does not. The driven set is taken in order of
integrated intensity, with ties broken by $Q$, so a pattern whose low-angle range
opens on background does not spend its whole budget there. On a synchrotron
pattern beginning at $0.76^\circ\ 2\theta$ the twenty lowest-angle components
contain six of the true cell's lines, where the strongest twenty contain
eighteen. A list of bare positions carries no measured intensities, so every line
ties and the order reduces to ascending $Q$. An assumed intensity may no more
reorder a search than an assumed $\sigma$ may refuse one.

The rank is applied within the lowest {{ SEARCH_POOL_MULTIPLE }}$N$ lines, for
cost. A branch-and-bound search sizes the trial reflection set it tests each box
against by the largest $Q$ among the driven lines, so letting the rank reach a
lab pattern's high-angle tail enlarges that set for every box in the recursion.
The
bound recovers about half of what the rank costs, at a few lines of selection
quality: unbounded, the same synchrotron list scores twenty of twenty.

A systematic $2\theta$ shift is the failure mode both indexing benchmarks single
out {cite}`bergmann2004`. Three physical causes give three angular dependences: a
constant (detector zero point), $\cos\theta$ (specimen displacement) and
$\sin 2\theta$ (specimen transparency). They are fitted one at a time, never
jointly, because a joint fit of collinear templates returns physically absurd
cancelling amplitudes. A cause is named only when the runner-up leaves at least
twice as much variance unexplained; otherwise the magnitude is reported and the
cause is not. One dependence is deliberately outside that basis. A $\tan\theta$
deviation is a cell error, and offering it to a shift screen would let the screen
explain a shift by changing the answer indexing is about to produce.

### Measuring the shift before the cell

Fitting those templates needs reference positions, and before indexing there is
no cell to deviate from. The shift is measurable anyway, so a search can widen
its window by a measurement instead of an assumption.

Two reflections form a reflection pair when their planes are harmonics of one
another, $(h'k'l') = m\,(hkl)$ with $m$ integer, so that
$d_{hkl} = m\,d_{h'k'l'}$ exactly. Bragg's law then relates their angles with no
reference to the cell, the crystal system or the indices. The relation follows
from the lattice being self-consistent, and not from which lattice it is:

```{math}
:label: idx-pair

m \sin\theta_B \;=\; \sin\theta'_B .
```

{source}`rietx.indexing.pairs.pair_shift`

Writing $2\theta_B = 2\theta_\mathrm{obs} + 2\theta_z$ for a constant shift and
solving {cite}`dong1999`:

```{math}
:label: idx-pair-shift

2\theta_z \;=\; 2\arctan\!\left[
  \frac{\sin\theta' - m\sin\theta}{m\cos\theta - \cos\theta'} \right].
```

{source}`rietx.indexing.pairs.pair_shift`

Each pair is thus one equation in the shift and none in the cell. Substituting
a general $2\theta_B = 2\theta_\mathrm{obs} - c\,T(2\theta_\mathrm{obs})$
instead of a constant leaves a scalar equation in the amplitude $c$ of any of
the three templates, solved by Newton.

Two cautions govern how the result may be read. Real harmonic pairs agree on
$c$. Accidental ones, any two lines whose sine ratio falls near an integer,
scatter. A shift is therefore reported only when the agreement is significant
against a structureless null of the same size, and on a bare twenty-line list
the supply of pairs collapses and the honest answer is to decline. The pair
evidence also measures a magnitude rather than a cause. The constant and
$\cos\theta$ templates concentrate equally well on real data, so a pair screen
may refute $\sin 2\theta$ and may not choose between the other two.

## Volume from one line

An estimate of the cell volume follows from the number of distinct
lines a lattice of that volume can show above a given $d$
{cite}`smith1977`:

```{math}
:label: idx-volume

V \;\approx\; \frac{0.6\, d_N^3}{1/N - 0.0052},
```

{source}`rietx.indexing.quality.volume_envelope`

which at $N = 20$ is $V \approx 13.39\, d_{20}^3$ for a primitive triclinic
lattice. Two scalings are needed before it can bound a search in another system,
and both come from the published form counting distinct lines. A high-symmetry
lattice merges reflections into orbits, and a centred one extinguishes them. A
cubic $F$ lattice of a given volume shows some 96 times fewer distinct lines than
a primitive triclinic one, so applying the printed constant to a cubic search
bounds the volume 96-fold too tightly and excludes the true cell. The centring is
part of the answer, so the bound uses the loosest centring each system admits.

The relation is a mean line rather than an envelope, and the distinction is a
live one. Smith fits equation {eq}`idx-volume` by least squares to some forty
well-determined triclinic patterns and reports an average discrepancy of 10.6 %,
with deviations running from 32 % too high to 29 % too low. The low side is the
ordinary case, since it is what missing weak lines produce. Writing $p$ for the
fraction of possible lines actually detected, the bound stands in ratio
$1.40\,p$ to the truth, so it excludes the true cell below $p = 0.71$, and
$1 - 0.71$ is Smith's own worst case. Used as a hard search ceiling the relation
has no margin against the worst pattern in its own calibration set, so the slack
that makes it safe is this package's to supply.

## Volume from a formula

When the formula is known, the volume of one formula unit follows from average
atomic volumes {cite}`hofmann2002`. Hofmann fitted one volume per element to
182 239 structures in the Cambridge Structural Database, and let the sum expand
linearly with temperature:

```{math}
:label: idx-formula-volume

V_{\mathrm{fu}}(T) \;=\; \sum_i n_i\, \bar v_i \,
\frac{1 + \bar\alpha\, T}{1 + \bar\alpha\, T_0},
```

{source}`rietx.crystallography.atomic_volume.formula_unit_volume`

with $n_i$ atoms of element $i$, $\bar v_i$ its average volume at
$T_0 = 298$ K, and $\bar\alpha = 0.95 \times 10^{-4}$ K$^{-1}$. The paper
writes the expansion as $(1 + \bar\alpha T)$ with $T$ absolute and quotes the
volumes at 298 K, and the ratio reconciles the two. The table replaces a single
figure of about 18 Å³ per C, N or O atom {cite}`kempsterlipson1972`. On
Hofmann's set the standard deviation of $V_{\mathrm{obs}}/V_{\mathrm{est}}$ is
4.00 % for the table and 9.04 % for that figure.

Two uncertainties answer two questions. The tabulated mean errors say how well
each average is known, about 0.5 % of an organic formula unit. One crystal
scatters about the average by {{ VOLUME_SCATTER_PCT }} %, and a check on one
candidate cell uses that. A cell of volume $V$ implies $Z = V/V_{\mathrm{fu}}$
formula units. It is reported when the nearest whole number $n$ needs
$\lvert Z/n - 1 \rvert$ above {{ Z_INTEGER_TOLERANCE_PCT }} %, twice the
scatter. Above $Z$ = {{ Z_CHECK_SILENT_ABOVE }} every value lies that close to
a whole number, so the check is silent there. A search window from a formula
takes the paper's wider bounds instead, $V_{\mathrm{obs}}/V_{\mathrm{est}}$
from {{ VOLUME_RATIO_LOW }} to {{ VOLUME_RATIO_HIGH }}, because a window that
excludes the true cell makes the search return a wrong one. The volumes are
fitted to organic and metal-organic crystals, and an ionic compound comes out
too large.

A measured density fixes $Z$ the other way round, through the definition of
the density of a crystal of $Z$ formula units of weight $M$ in a cell of volume
$V$:

```{math}
:label: idx-density-z

Z \;=\; \frac{\rho\, V\, N_A}{M},
```

{source}`rietx.indexing.extinction.declared_z`

with $N_A = 6.022\,140\,76 \times 10^{23}\ \mathrm{mol}^{-1}$, exact in the SI since
2019 {cite}`bipm2019`, so that $\rho$ in g/cm$^3$, $V$ in Å$^3$ and $M$ in
g/mol give $Z = 0.602\,214\,076\,\rho V / M$. The error of $Z$ is the error of
the density, since the cell volume is far better known. *International Tables*
Vol. C asks that measured and calculated density "agree within at least 1.5%"
{cite}`richards2006`; the screen takes {{ DENSITY_Z_TOLERANCE_PCT }} %
and not the 8 % scatter of a volume estimated from atom counts. A density that
fits two whole numbers (above $Z$ = {{ DENSITY_Z_AMBIGUOUS_ABOVE }}) names none.

## Figures of merit, in both directions

The classical figures are de Wolff's {cite}`dewolff1968`

```{math}
:label: idx-m20

M_{20} \;=\; \frac{Q_{20}}{2\,\overline{\lvert \Delta Q \rvert}\,
N_{\mathrm{poss}}},
```

{source}`rietx.indexing.fom.m20`

and Smith & Snyder's {cite}`smithsnyder1979`

```{math}
:label: idx-fn

F_N \;=\; \frac{1}{\overline{\lvert \Delta 2\theta \rvert}} \cdot
\frac{N_{\mathrm{obs}}}{N_{\mathrm{poss}}},
```

{source}`rietx.indexing.fom.f_n`

where $N_{\mathrm{poss}}$ counts the lines the lattice allows up to the $N$-th
observed one, and both means run over every one of those $N$ lines assigned to
its nearest calculated line. Each mean is floored at the measured precision,
which is this package's addition rather than the papers'. The figures divide by a
discrepancy, so on data a lattice fits to within floating-point noise they
diverge, and a naive zero-guard then ranks a perfect cell last. A discrepancy
smaller than $\sigma$ is not knowable, and per-line $\sigma$ is what a fitted
peak list has and 1968 did not.

Both figures share a blind spot with the fraction of observed lines indexed: a
large enough cell has a line near everything. The measured case that fixes the
design is in this project's own prior art. A wrong phase ranked first on share of
observed intensity indexed, 83.7 %, with 390 predicted lines of which 9.0 % were
present, above the truth's 79.2 % with 56.5 % of its own 23 lines seen. Coverage
is therefore scored in both directions, the reverse direction being the fraction
of a candidate's predicted lines that are actually present
{cite}`oishitomiyasu2013`, and the ranking is a Borda count over the whole panel
rather than a sort on any member. Every figure of merit is reported with the
blind spot attached to the number, because a value read without it is one step
from a confident wrong answer.

Two of the panel's inputs are deliberately different quantities that a casual
reading merges. The matching window is how far an observed and a calculated line
may sit and still be the same line, a statement about the systematics the search
had to open its tolerance for. The measurement $\sigma$ that floors the two mean
discrepancies is a statement about what the data resolve. On a laboratory pattern
with an uncorrected specimen displacement the two differ by an order of
magnitude, and scoring coverage at the tighter one makes every candidate look as
though it explains nothing. A candidate that carries a fitted shift is likewise
scored against the corrected positions it claims. Scoring it against the raw ones
marks it down for the correction it declared, which on a certified pattern
demoted the true lattice below cells that had merely been corrected less.

## Lattice ambiguity

Distinct lattices can give identical calculated line positions
{cite}`mighellsantoro1975`. The pattern carries $\lvert \mathbf{h} \rvert$
only, so no counting statistics separate them. The information is absent from
the measurement rather than buried in its noise. Candidate partners are the
derivative lattices, enumerated exactly as the integer matrices in Hermite
normal form of index up to {{ MAX_AMBIGUITY_INDEX }},

```{math}
:label: idx-hnf

H \;=\; \begin{pmatrix} a & b & c \\ 0 & d & e \\ 0 & 0 & f
\end{pmatrix}, \qquad a d f = n, \quad 0 \le b < d, \quad 0 \le c,e < f,
```

{source}`rietx.indexing.ambiguity.hnf_matrices`

whose closed sets have 7, 13 and 35 members at $n = 2, 3, 4$, a count the
implementation is checked against. Each partner's metric follows from
$G' = H\,G\,H^\top$. Partners that Niggli-reduce back to the parent are setting
changes and are dropped, which keeps ambiguity distinct from de-duplication. The
surviving report carries a list of discriminating reflections: the $hkl$, and the
$2\theta$, where the partner and the parent differ. That is the structural twin
of a fit report saying "extend the range", and it is what makes the report
actionable.

De-duplication itself is a $\chi^2$ test on the Niggli-reduced
$(A \ldots F)$ against $\chi^2_6$ at 99 %, using the two candidates' joint
covariance, rather than a fixed percentage: a percentage merges distinct
synchrotron cells and splits noisy laboratory ones.

That test presumes the reduction is canonical, and in floating point it is not
so by default. The Křivý–Gruber algorithm {cite}`krivygruber1976` decides its
normalisation on exact equalities, breaking the tie at $B = C$ on
$\lvert \eta \rvert \le \lvert \zeta \rvert$, and those equalities cannot be
tested with finite precision. Every comparison therefore carries a relative
tolerance $\varepsilon = \varepsilon_{\mathrm{rel}} V^{1/3}$ with
$\varepsilon_{\mathrm{rel}} =$ {{ NIGGLI_EPS_RELATIVE }}, the same value in the
reduction and in the predicate that checks it {cite}`grossekunstleve2004`.
Without it a lattice with two equal reduced axes reduces to $\beta$ and $\gamma$
swapped depending on the setting it arrived in, so two descriptions of one
lattice are declared two lattices.

The tolerance cannot remove the other failure: Niggli reduction has decision
boundaries, and two descriptions of one lattice that fall either side of one
reduce to different vectors, however close they are
{cite}`andrews2019selling`. A pair the $\chi^2$ test calls distinct is
therefore asked again, in Selling's form, which has no boundary of that kind
{cite}`andrews2019selling,andrews2019space`. Each of $b$'s other descriptions
that the Selling scalars place within the pair's error of $a$'s is mapped to
$A \ldots F$ exactly, and the same $\chi^2$, built from the same
pseudo-inverse of the joint covariance, is asked of that image. A pair
joined this way reports the $\chi^2$ of the description that joined it, and a
pair the first test joined is answered exactly as before.

Lattice symmetry is decided by two independent opinions: a Le Page 2-fold search
{cite}`lepage1982` with a tolerance in degrees of obliquity, and a
distance-tolerance standardisation {cite}`togo2024`. Both are swept over their
tolerances, the answer is the symmetry stable across the sweep, and anything
appearing only at the loosest tolerance is reported as ambiguous. Agreement
between independent methods is the confidence. Disagreement is reported rather
than averaged.

## A supercell and the lattice inside it

A superlattice explains every line its sublattice explains and predicts more,
so when the search reports both, the question is whether the pattern shows the
lines the larger cell adds. Asked of every line it adds, the question cannot
separate an oversized cell from a correct one whose space group extinguishes
most of them: the certified corundum cell over its own $c/2$ subcell reads like
a phantom. International Tables classifies the reflection conditions
{cite}`itc-a`. Integral conditions come from centring and act on every
$\mathbf{h}$. Zonal conditions come from glide planes and act on the plane the
glide's mirror fixes. Serial conditions come from screw axes and act on the row
the axis fixes. So a reflection that no point symmetry $W$ of the lattice fixes,
$W\mathbf{k} \ne \mathbf{k}$ for every $W \ne I$ in primitive indices
$\mathbf{k}$, can be extinguished by no space group of that lattice. The count
runs over those alone. The lattice's point symmetries are found from its metric,
as the integer matrices on the reduced basis that preserve it, $WGW^\top = G$.

Of the $n$ such lines the larger cell adds inside the measured range, $k$ fall
inside an observed line's matching window. A position with no line at all falls
inside one with probability $p_0$, the share of the range those windows cover.
The chance of seeing at least $k$, had the added lines not existed, is the
binomial tail

```{math}
:label: idx-supercell-chance

p \;=\; \sum_{j=k}^{n} \binom{n}{j}\, p_0^{\,j}\,(1-p_0)^{\,n-j},
```

{source}`rietx.indexing.ambiguity.supercell_chance`

and at $p \ge \alpha$ = {{ SUPERCELL_CHANCE_ALPHA }} the larger cell is ranked
directly below the smaller. The test cannot refute where it could not have
confirmed. When even $k = n$ gives $p_0^{\,n} \ge \alpha$, too few lines or
too many windows, the verdict is undecided and the order stays as it was.

The other direction asks a narrower count. Of the $k$, let $k'$ fall on an
observed line that no line of the smaller cell's own lattice explains. When the
same tail with $k'$ in place of $k$ is below $\alpha$, the larger cell is ranked
directly above the smaller. Those observed lines exist, and the smaller cell
cannot index them. An added line seen on a line the smaller cell explains is
left out of $k'$. A pseudo-symmetric description places its added lines beside
the smaller cell's own, and those lines say nothing about the larger cell. The
null stays $p_0$. That overstates the chance of landing on an unexplained line.
So this count errs towards leaving the order alone. A larger cell refuted
against any reported cell is never moved up.
