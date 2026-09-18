"""``candidates(..., verify=True)`` flags a failing candidate instead of hiding the rest (Q-21).

Measured (T-A0, ``checks/TA0_SUPERSTRUCTURE_K.md`` "Refusals"; M-1 FYI 1 was one
instance): ``candidates(space_group, k, site, kind="displacive", verify=True)``
used to raise on the **first** candidate of a site whose ``in_allowed_span()``
failed, hiding the passing candidates of that same site.  On Pnma every
y = 1/4 mirror site was affected at k = (1/2, 1/2, 0) and k = (0, 1/2, 1/2): the
S1(rank 2)#3 and S2(rank 1)#2 directions each failed their own span check while
every other direction of the same site passed.

This module tests the aggregation fix: every candidate of a site is returned,
each carrying ``verified`` and ``verification_reason``, and ``candidates()``
raises only when *every* candidate of a site fails (nothing left to fall back
on).  Section A used to pin the two Pnma directions as the *known-bad*
candidates the aggregation was built to surface rather than hide — Q21 left
their *why* diagnosed but not fixed (``checks/Q21_CANDIDATES_VERIFY.md``,
half A).  Q22 fixed the root cause (``allowed_displacement_basis``/
``allowed_moment_basis`` had no way to see a stabiliser element's own
atom-specific return-vector phase, so a displacive check could only ever
demand the +1 eigenspace of R), and both directions now verify ``True`` —
Section A pins that instead.  The aggregation mechanism itself is still
exercised directly, via monkeypatching a synthetic failure, in Section C.
"""

from fractions import Fraction

import numpy as np
import pytest

from rietx.crystallography.magnetic import isotropy
from rietx.crystallography.magnetic.isotropy import MagneticCandidate, candidates
from rietx.crystallography.magnetic.operators import (
    allowed_displacement_basis,
    allowed_moment_basis,
    in_span,
)

PNMA_MIRROR_SITE = (0.1, 0.25, 0.15)   # generic y = 1/4 mirror site, nominal cell
K_HALF_HALF_0 = ("1/2", "1/2", "0")
K_0_HALF_HALF = ("0", "1/2", "1/2")

# one of the twenty published structures test_magnetic_operators.py's
# PUBLISHED_MOMENTS carries (also in test_magnetic_isotropy.py's PUBLISHED):
# a type-IV (k != 0) row whose displacive control is not at stake here, only
# that an ordinary, everything-verifies site is untouched by the aggregation
# change.
NIO_SPACE_GROUP = "F m -3 m"
NIO_SITE = (0.0, 0.0, 0.0)
NIO_K = (Fraction(1, 2), Fraction(1, 2), Fraction(1, 2))


def _old_rule_in_allowed_span(candidate) -> bool:
    """The pre-Q22 ``in_allowed_span``: geometric stabiliser, no return phase.

    Reproduced here (not imported — the whole point is that it no longer
    exists in ``isotropy.py``) so Section A can show the *old* rule really
    did reject these two candidates, not merely that they are unrelated to
    whatever ``candidates()`` happens to return today.
    """
    basis_fn = (allowed_moment_basis if candidate.kind == "magnetic"
                else allowed_displacement_basis)
    for atom in range(candidate.positions.shape[0]):
        basis = basis_fn(candidate.group.site_stabilizer(candidate.positions[atom]))
        for pattern in candidate.configurations:
            if not in_span(basis, pattern[atom]):
                return False
    return True


# --------------------------------------------------------------------------
# A. the two measured Pnma cases: Q21 flagged them, Q22 fixed them
# --------------------------------------------------------------------------

@pytest.mark.parametrize("k,label,bns", [
    (K_HALF_HALF_0, "S1(rank 2)#3", "6.19"),
    (K_0_HALF_HALF, "S2(rank 1)#2", "26.67"),
])
def test_the_two_q21_candidates_now_verify_true_under_q22(k, label, bns):
    cs = candidates("P n m a", PNMA_MIRROR_SITE, k, kind="displacive", verify=True)
    labels = [c.label for c in cs]
    assert label in labels
    by_label = {c.label: c for c in cs}
    candidate = by_label[label]
    assert candidate.bns_number == bns
    # the old rule really did reject this candidate — the fix is not a no-op
    assert _old_rule_in_allowed_span(candidate) is False, (
        f"{label} must fail the pre-Q22 rule, or this is not testing the fix")
    # ... and the new rule (what candidates() actually flags) accepts it
    assert candidate.verified is True, (
        f"{label} still fails its own span check under the Q22 rule")
    assert candidate.verification_reason is None
    for c in cs:
        assert c.verified is True, f"{c.label} unexpectedly failed its own span check"
        assert c.verification_reason is None


@pytest.mark.parametrize("k", [K_HALF_HALF_0, K_0_HALF_HALF])
def test_the_workaround_filter_and_the_new_flag_agree(k):
    """T-A0's own workaround (``verify=False`` + a per-candidate filter) must
    match the new ``verified`` flag exactly — the aggregation change only
    adds bookkeeping, it does not change which candidates pass."""
    unverified = candidates("P n m a", PNMA_MIRROR_SITE, k, kind="displacive", verify=False)
    workaround_passing = {c.label for c in unverified if c.in_allowed_span()}
    flagged = candidates("P n m a", PNMA_MIRROR_SITE, k, kind="displacive", verify=True)
    flagged_passing = {c.label for c in flagged if c.verified}
    assert flagged_passing == workaround_passing


# --------------------------------------------------------------------------
# B. verify=False is unchanged: no flag is set on anybody
# --------------------------------------------------------------------------

@pytest.mark.parametrize("k", [K_HALF_HALF_0, K_0_HALF_HALF])
def test_verify_false_leaves_every_flag_none(k):
    cs = candidates("P n m a", PNMA_MIRROR_SITE, k, kind="displacive", verify=False)
    assert len(cs) >= 2
    for c in cs:
        assert c.verified is None
        assert c.verification_reason is None


# --------------------------------------------------------------------------
# C. an all-failing site still raises — nothing left to fall back on
# --------------------------------------------------------------------------

def test_every_candidate_failing_still_raises(monkeypatch):
    monkeypatch.setattr(MagneticCandidate, "in_allowed_span", lambda self, **kw: False)
    with pytest.raises(RuntimeError, match="every candidate of the site"):
        candidates("P n m a", PNMA_MIRROR_SITE, K_HALF_HALF_0, kind="displacive", verify=True)


def test_a_partial_failure_does_not_raise(monkeypatch):
    """Sanity check on the guard itself: forcing only *one* candidate of a
    multi-candidate site to fail must not trip the all-failing raise."""
    real = MagneticCandidate.in_allowed_span
    calls = {"n": 0}

    def flaky(self, **kw):
        calls["n"] += 1
        return calls["n"] != 1   # the first candidate built fails, the rest pass

    monkeypatch.setattr(MagneticCandidate, "in_allowed_span", flaky)
    cs = candidates("P n m a", PNMA_MIRROR_SITE, K_HALF_HALF_0, kind="displacive", verify=True)
    assert len(cs) >= 2
    assert sum(1 for c in cs if c.verified is False) == 1
    assert sum(1 for c in cs if c.verified is True) == len(cs) - 1
    assert real is MagneticCandidate.in_allowed_span or True  # no-op, keeps `real` referenced


# --------------------------------------------------------------------------
# D. a named-group regression is bit-identical (verify=True vs verify=False)
# --------------------------------------------------------------------------

def test_named_group_candidates_are_bit_identical_to_before():
    """NiO (MAGNDATA #1.6, a type-IV k != 0 published structure) verifies
    cleanly on every candidate; the aggregation change must not perturb a
    single number here, only add the ``verified``/``verification_reason``
    metadata."""
    verified_set = candidates(NIO_SPACE_GROUP, NIO_SITE, NIO_K, kind="magnetic", verify=True)
    bare_set = candidates(NIO_SPACE_GROUP, NIO_SITE, NIO_K, kind="magnetic", verify=False)
    assert len(verified_set) == len(bare_set) > 0
    for v, b in zip(verified_set, bare_set):
        assert v.verified is True
        assert v.verification_reason is None
        assert v.label == b.label
        assert v.bns_number == b.bns_number
        assert v.free_amplitudes == b.free_amplitudes
        assert np.array_equal(v.positions, b.positions)
        assert np.array_equal(v.configurations, b.configurations)
        assert v.group.all_operations() == b.group.all_operations()


# --------------------------------------------------------------------------
# E. CandidateSet.verified_only() — the filter the callers use
# --------------------------------------------------------------------------

@pytest.mark.parametrize("k,label", [
    (K_HALF_HALF_0, "S1(rank 2)#3"),
    (K_0_HALF_HALF, "S2(rank 1)#2"),
])
def test_verified_only_is_a_no_op_on_this_site_under_q22(k, label):
    """Under Q21's rule this site had one candidate ``verified_only()`` dropped
    (``label``); under Q22's fix it verifies too, so the filter now keeps
    everything — pinned here so a regression back to the Q21 behaviour would
    be caught by a *count* changing, not just by a label disappearing."""
    cs = candidates("P n m a", PNMA_MIRROR_SITE, k, kind="displacive", verify=True)
    n_before = len(cs)
    filtered = cs.verified_only()
    assert label in [c.label for c in filtered]
    assert len(filtered) == n_before
    assert all(c.verified is not False for c in filtered)


def test_verified_only_keeps_none_flagged_candidates():
    """``verify=False`` candidates (``verified is None``) are kept: nothing
    has said they fail."""
    cs = candidates("P n m a", PNMA_MIRROR_SITE, K_HALF_HALF_0, kind="displacive", verify=False)
    filtered = cs.verified_only()
    assert len(filtered) == len(cs)


def test_verified_only_clears_derived_fields_rather_than_misaligning_them():
    """classes/determinable/absences are positional against ``candidates``;
    verified_only() must drop them rather than leave them pointing at the
    wrong row once a candidate is removed."""
    cs = candidates("P n m a", PNMA_MIRROR_SITE, K_HALF_HALF_0, kind="displacive", verify=True)
    cs = isotropy.CandidateSet(**{**cs.__dict__, "classes": ((0,), (1,)),
                                  "determinable": (1, 2, 3, 4),
                                  "absences": (0, 0, 0, 0)})
    filtered = cs.verified_only()
    assert filtered.classes == ()
    assert filtered.determinable == ()
    assert filtered.absences == ()
