(ch-linear-restraint)=
# Restraints on a sum of parameters

A soft restraint can hold a weighted sum of parameters near a target, across phases, and a conserved elemental ratio is one such sum. This page states the row, its partials and the ratio coefficients. The restraints on one atom's geometry are in [Parameterisation and constraints](parameterisation.md).

A linear restraint names a sum of parameters rather than one, and
its terms may belong to different phases, so it lives on the structure rather
than on a phase. Its row is

```{math}
:label: par-linear-restraint

r_{\mathrm{lin}} \;=\; \sqrt{w}\,
\frac{\sum_k c_k\,p_k(\theta) - \mathrm{target}}{\sigma},
```

{source}`rietx.model.restraints.restraint_residual`

with constant partials $\partial r_{\mathrm{lin}}/\partial p_k = \sqrt{w}\,c_k/\sigma$,
chained through the constraint matrix like every other row. A conserved
elemental ratio is one such row. The moles of element $E$ are proportional to
$\sum_p S_p V_p n_{E,p}$, where $n_{E,p}$ is the occupancy-weighted count of $E$
in one cell of phase $p$, since $W_p \propto S_p (ZMV)_p$ {cite}`hill1987` and
$(ZM)_p$ is the cell's mass. A ratio $r$ of the elements in a set $N$ to those
in a set $D$ is then the row

```{math}
:label: par-ratio-restraint

\sum_p a_p S_p = 0, \qquad
a_p = \frac{V_p\,\bigl(n_{N,p} - r\, n_{D,p}\bigr)}{D_0}, \qquad
D_0 = \sum_p S_p^{(0)} V_p\, n_{D,p},
```

{source}`rietx.model.restraints.elemental_ratio_restraint`

where $S_p^{(0)}$ are the scales at declaration. The row equals
$(D/D_0)(\rho - r)$, with $\rho$ the ratio the scales imply and $D$ the
denominator at the current scales, so at the declared scales $\sigma$ is a σ on
the ratio and away from them a σ of $\sigma D_0/D$. The cell volumes and
occupancies are frozen into $a_p$. A fit whose occupancies have moved from the
declared ones reports so, and a refined volume moves a coefficient by its own
relative change.
