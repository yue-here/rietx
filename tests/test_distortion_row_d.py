"""Milestone row D on main's fallback route: one stored list is the group (WP-1419 C3a).

The fork's displacive children declared the sign-consistent stabiliser of
their mode field, a strict subgroup of the child group, and every consumer
(reflections, multiplicities, the metric) read that reduced list.  On main,
``magnetic_supercell(..., nuclear_group="magnetic")`` still builds a
displacive candidate's colourless group and then reduces it with
``_sign_consistent_operations`` before writing it into the child.  Measured
2026-10-21 over the fifteen Q-17 sweep rows of WP-1419 C2 × two sites, every
displacive candidate (215): **none is reduced**.  The candidate group is
already the stabiliser of its signed field (#679 builds it with the coset
character), so the reduction is a safety net that does not fire, and the
reflections the child generates are the full child group's.

The test replays the lines of ``magnetic_supercell`` that build the child
group, so it covers every candidate, including those a later refusal stops.
Positive arm: the same reduction fed the parent's group carried into the
child cell (a supergroup) removes operations, and keeps exactly the
colourless set.  Three rows here; all fifteen under ``slow``.
"""

from __future__ import annotations

import itertools
from fractions import Fraction

import numpy as np
import pytest

from rietx.crystallography.adp import cartesian_basis
from rietx.crystallography.magnetic import isotropy as _isotropy
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.magnetic.operators import LatticeNotPreserved, format_transform

#: C2's sweep rows (setting, k, nominal cell)
SWEEP_ROWS = (
    ("P c c 2", ("1/2", "1/2", "0"), (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("C m m 2", ("0", "0", "1/2"), (6.0, 7.0, 9.0, 90.0, 90.0, 90.0)),
    ("P c c a", ("1/2", "1/2", "0"), (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("P c c n", ("1/2", "1/2", "0"), (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("P 42 c m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42 c m", ("1/2", "1/2", "0"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42 n m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 4 c c", ("1/2", "1/2", "0"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P -4 c 2", ("1/2", "1/2", "0"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/m c m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/n n m:1", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/m n m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/n c m:1", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P n -3 m:1", ("0", "0", "1/2"), (6.0, 6.0, 6.0, 90.0, 90.0, 90.0)),
    ("P 6 m m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 120.0)),
)
SITES = ((Fraction(0), Fraction(0), Fraction(0)),
         (Fraction(11, 100), Fraction(13, 100), Fraction(17, 100)))
FAST = ("P c c n", "P 42/m c m", "P 6 m m")


def _reductions(setting, k, values):
    """(colourless, kept, parent-group, parent-kept) per displacive candidate."""
    kk = tuple(Fraction(c) for c in k)
    lattice = np.asarray(cartesian_basis(*values)).T
    parent_group = sc.resolve_group(setting, None)
    out = []
    for site in SITES:
        for cand in _isotropy.candidates(setting, site, kk, kind="displacive",
                                         cell=lattice, verify=True):
            # magnetic_supercell's own lines: the child basis, the candidate's
            # group carried into it, its colourless part, then the reduction
            basis = sc.child_basis(parent_group, cand.cell.k)
            p_candidate = [[Fraction(v) for v in row] for row in cand.cell.basis]
            step = sc._mat_mul(_isotropy._exact_inverse(p_candidate),
                               [[Fraction(v) for v in row] for row in basis])
            group = cand.group.transformed(format_transform(
                _isotropy._exact_inverse(step), (Fraction(0),) * 3))
            ops = sc._nuclear_operations(sc._colourless(group))
            m_matrix = _isotropy._fraction_inverse(basis) @ sc._matrix_of(cand.cell.basis)
            kept = sc._sign_consistent_operations(cand, m_matrix, ops)
            try:
                parent_ops = sc._nuclear_operations(sc._nuclear_group_of(setting).transformed(
                    format_transform(_isotropy._exact_inverse(
                        [[Fraction(v) for v in r] for r in basis]), (Fraction(0),) * 3)))
            except LatticeNotPreserved:
                # the parent's group does not survive into this child cell (a
                # cubic parent in a,b,2c), so this candidate has no positive arm
                out.append((ops, kept, None, None))
                continue
            parent_kept = sc._sign_consistent_operations(cand, m_matrix, parent_ops)
            out.append((ops, kept, parent_ops, parent_kept))
    return out


@pytest.mark.parametrize("row", [
    pytest.param(row, marks=[] if row[0] in FAST else [pytest.mark.slow], id=f"{row[0]} {row[1]}")
    for row in SWEEP_ROWS])
def test_no_displacive_child_loses_an_operation_to_the_sign_check(row):
    """Kept = colourless for every candidate; the parent's group is pruned to it."""
    found = _reductions(*row)
    assert found
    for ops, kept, parent_ops, parent_kept in found:
        assert kept == ops
        if parent_ops is not None:
            assert len(parent_kept) < len(parent_ops)
            assert parent_kept == ops
    if row[0] in FAST:
        assert all(parent is not None for *_, parent, _kept in found)


@pytest.mark.slow
def test_the_sweep_counts_215_displacive_candidates():
    """The enumeration the measurement rests on (C2's rows, both sites)."""
    n = sum(1 for (setting, k, values), site in itertools.product(SWEEP_ROWS, SITES)
            for _ in _isotropy.candidates(setting, site, tuple(Fraction(c) for c in k),
                                          kind="displacive"))
    assert n == 215
