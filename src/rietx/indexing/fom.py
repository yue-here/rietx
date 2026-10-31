"""Figures of merit — a **panel**, scored in both directions, never one number.

The measured reason this is a panel and not a scalar is in this repo's own prior
art (tag ``guillemot-study``, ``studies/guillemot/out/audit_full.txt`` §D).
Screening a pattern whose answer is known, a wrong phase **ranked first on share
of observed intensity indexed — 83.7 %, with 390 predicted lines of which 9.0 %
are present** — above the truth, which indexed 79.2 % while showing 56.5 % of its
own 23 lines.  A big cell indexes everything and means nothing.  So

* :func:`predicted_seen_fraction` is a **first-class ranking member**, not a
  post-hoc validation field, and
* the ranking is Borda over the whole panel rather than a sort on any member.

That is also Oishi-Tomiyasu's (2013) argument for reversing the asymmetry in the
de Wolff figure of merit, reached independently here on this repo's own data.

**Every FoM carries its blind spot, and the blind spot travels with the number.**
:class:`~rietx.schemas.indexing.FigureOfMerit` has a ``blind_spot`` field and it
is filled from the same string the docstring states, so a consumer cannot see a
value without seeing what it cannot see.  Three of them matter enough to state
here: M₂₀ counts *lattice*-possible lines, so it is blind to space-group
extinctions, and its ⟨ΔQ⟩ is a plain mean, so one impurity line wrecks it; F_N
lives in 2θ, where a refined zero shift can manufacture a large value; and
``indexed_fraction`` is the exact quantity §D above showed ranking a 390-line
impostor first.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from ..schemas.indexing import (
    PEAK_MIN_USABLE_LINES,
    FigureOfMerit,
    q_of_two_theta,
)

#: How many σ_eff an observed and a predicted line may differ by and still count
#: as the same line.  Three, because σ(2θ) is *calibrated* — WP-1018's pull
#: ensemble measured mean +0.03/std 0.97 on a single line and −0.08/0.98 on a lab
#: doublet — so 3σ really is a 99.7 % window rather than a knob.  It is the one
#: number the whole panel shares, and every FoM reports which one it used.
MATCH_SIGMA = 3.0
#: Lines the classical figures of merit are scored on.  De Wolff's M₂₀ is
#: defined on the first twenty and Smith's volume envelope is quoted at N = 20.
#: Smith & Snyder's F_N is *not*: they define it for general N (their eq 1) and
#: recommend N = 30, or the last line where a pattern has fewer.  Their worked
#: example happens to be F₂₀, because that pattern reported twenty lines, and
#: the string "F30" appears nowhere in the paper.  So the twenty here is this
#: package's own choice, aliased to
#: :data:`~rietx.schemas.indexing.PEAK_MIN_USABLE_LINES` — an alias, not a
#: second bar, so the scoring precondition cannot drift from the figures it is
#: about (WP-1043).  The value stays; only the attribution was wrong (WP-1436).
FOM_N = PEAK_MIN_USABLE_LINES


def lattice_group(system: str, centring: str = "P") -> str:
    """The **absence-free** space-group symbol of a lattice: holohedry + centring.

    "Lattice-possible" in de Wolff's and Smith & Snyder's denominators means every
    reflection the *lattice* allows — so centring conditions count (they are
    lattice absences) and space-group conditions do not (they are not known when a
    search runs; ``indexing.extinction.determine_extinction_symbol`` determines
    them afterwards, and this symbol stays its reference model).  Passing this to
    ``generate_reflections`` is what makes ``n_possible`` mean the same thing as
    in the papers.
    """
    holohedry = {
        "triclinic": "P -1", "monoclinic": "P 1 2/m 1", "orthorhombic": "P m m m",
        "tetragonal": "P 4/m m m", "trigonal": "P -3 m 1",
        "hexagonal": "P 6/m m m", "cubic": "P m -3 m",
    }
    if system not in holohedry:
        raise ValueError(f"unknown crystal system {system!r}")
    symbol = holohedry[system]
    if centring in ("", "P"):
        return symbol
    if system == "trigonal" and centring == "R":
        return "R -3 m"
    return centring + symbol[1:]


#: Relative separation below which two calculated reflections are **one line**.
#: 1e-9 is nine orders below any measurement precision, so it merges exact
#: coincidences and nothing else.
LINE_COINCIDENCE_RTOL = 1e-9


def predicted_lines(cell: tuple[float, ...], system: str, centring: str,
                    wavelength: float, two_theta_max: float,
                    two_theta_min: float = 0.0):
    """(hkl, Q) the lattice allows in range — the FoM denominators' population.

    **A line, not an orbit.**  ``generate_reflections`` returns one entry per
    symmetry-unique orbit, and two distinct orbits routinely land at the *same*
    Q — 333 and 511 in a cubic cell both give 27A.  Those are one line: they
    arrive at one 2θ, they are one thing to observe, and a figure of merit whose
    content is "how densely could this lattice produce lines" must count them
    once.  Measured, the difference is not cosmetic: a 17 Å cubic cell has 470
    orbits and **208 distinct lines** to 90° 2θ.  Low-symmetry cells are
    unaffected (orthorhombic, monoclinic and triclinic test cells agree exactly),
    which is what identifies the gap as coincidence rather than as a different
    rule.

    Enumerating directly also removes the cost that made ranking the bottleneck:
    ``generate_reflections`` canonicalises orbits in a python loop over every hkl
    in the box, which is 683 ms for that 17 Å cell against 1.8 ms here — and a
    search ranks tens of candidates.  Correctness and speed point the same way
    because a *lattice* group has no absences beyond its centring
    (:func:`~rietx.indexing.qspace.centring_allows`), so no space-group
    machinery is needed to enumerate one.
    """
    hkl, q, _m = lattice_reflections(cell, system, centring, wavelength,
                                     two_theta_max, two_theta_min)
    if len(q) > 1:
        distinct = np.ones(len(q), dtype=bool)
        distinct[1:] = np.diff(q) > LINE_COINCIDENCE_RTOL * q[1:]
        hkl, q = hkl[distinct], q[distinct]
    return hkl, q


def lattice_reflections(cell: tuple[float, ...], system: str, centring: str,
                        wavelength: float, two_theta_max: float,
                        two_theta_min: float = 0.0, *,
                        multiplicity: bool = False):
    """(hkl, Q, m) the lattice allows in range — **unmerged**, one per Friedel pair.

    :func:`predicted_lines` is this, merged into distinct *lines*.  The merge is
    exactly what the Oishi-Tomiyasu figures must not have: their denominator
    ``N^cal`` counts Laue **orbits** via Σ 1/m, which already gives an exact
    coincidence its own weight, so merging first would double-remove it — and the
    merge is a float comparison at :data:`LINE_COINCIDENCE_RTOL`, which on a
    pseudo-symmetric candidate (what an indexer actually produces) is the
    threshold rather than the symmetry deciding the count.

    ``m`` is ``None`` unless ``multiplicity`` is asked for: it costs an orbit
    expansion over the whole enumeration and only ``N^cal`` needs it.
    """
    from .qspace import af_from_cell, design_matrix, trial_hkl

    lattice_group(system, centring)          # validates the system name
    d_min = wavelength / (2.0 * np.sin(np.radians(max(two_theta_max, 1e-6) / 2.0)))
    # Q(h00) = A·h² and 1/√A = d(100) ≤ a, so h ≤ a/d_min bounds every index
    max_index = int(np.ceil(max(tuple(cell)[:3]) / d_min)) + 1
    hkl = trial_hkl(max_index, centring)
    q = design_matrix(hkl) @ af_from_cell(tuple(cell))
    # the same 0.1 % boundary slack generate_reflections applies to d
    keep = (q > 0.0) & (q <= (1.0 / d_min ** 2) * 1.002)
    if two_theta_min > 0.0:
        d_max = wavelength / (2.0 * np.sin(np.radians(max(two_theta_min, 1e-3)
                                                      / 2.0)))
        keep &= q >= (1.0 / d_max ** 2) * 0.998
    hkl, q = hkl[keep], q[keep]
    order = np.argsort(q)
    hkl, q = hkl[order], q[order]
    m = laue_multiplicity(hkl, system, centring) if multiplicity else None
    return hkl, q, m


def n_cal(q: np.ndarray, m: np.ndarray, lo: float, hi: float) -> float:
    """``N^cal(a, b)`` — Oishi-Tomiyasu's count of Laue orbits in a Q window.

    *Source*: Oishi-Tomiyasu, R. (2013), *J. Appl. Cryst.* **46**, 1277-1282,
    eq. (5).  Defined as Σ 1/m(hkl) over centring-allowed triples with
    ``a ≤ q(hkl) ≤ b``, including 000 exactly when ``a ≤ 0``.

    Two conventions of this package meet here and both would silently halve or
    double the answer if ignored.  ``trial_hkl`` keeps **one hkl per Friedel
    pair**, while ``m`` is the full orbit including −h; a Laue group contains the
    inversion, so each orbit is closed under negation and exactly half its
    members survive the "first non-zero component positive" rule — Σ 1/m over the
    half-sphere is therefore exactly ``N^cal/2``, and the factor of two here is
    that identity rather than a fudge.

    **The result is legitimately fractional and is never rounded.**  Σ 1/m over a
    complete orbit is 1, so an orbit-closed enumeration gives an integer — but the
    enumeration box is a cube in hkl while a hexagonal or trigonal orbit does not
    preserve ``max|h|`` ((110) → (-120)), so an orbit can be cut by the box and
    contribute a fraction.  Rounding would turn that into a silent miscount of the
    denominator both new figures divide by.
    """
    if not len(q):
        return 1.0 if lo <= 0.0 else 0.0
    sel = (q >= lo * (1.0 - _BOUNDARY_RTOL)) & (q <= hi * (1.0 + _BOUNDARY_RTOL))
    total = 2.0 * float(np.sum(1.0 / np.asarray(m, dtype=np.float64)[sel]))
    return total + (1.0 if lo <= 0.0 else 0.0)


@lru_cache(maxsize=32)
def _laue_rotations(symbol: str) -> np.ndarray:
    """The lattice group's reciprocal-space rotations, deduplicated.

    ``Rᵀ`` because the action on *hkl* is the transposed rotation (CLAUDE.md,
    and the comment in ``crystallography.symmetry.generate_reflections``), and
    deduplicated because a centred group's operation list repeats every rotation
    once per centring vector.
    """
    from ..crystallography.symmetry import get_spacegroup, rotation_matrices

    rots = rotation_matrices(get_spacegroup(symbol))
    rot_int = np.rint(np.transpose(rots, (0, 2, 1))).astype(np.int64)
    uniq = {tuple(int(v) for v in r.ravel()) for r in rot_int}
    return np.array(sorted(uniq), dtype=np.int64).reshape(-1, 3, 3)


def laue_multiplicity(hkl: np.ndarray, system: str, centring: str = "P"
                      ) -> np.ndarray:
    """``m(hkl)`` — the **full** Laue orbit size, Friedel mates included.

    ``crystallography.symmetry.reflection_orbits`` answers the same question and
    is the definition this is checked against, but it is a python loop with a set
    of tuples per reflection — the cost profile :func:`predicted_lines` exists to
    escape (683 ms against 1.8 ms on a 17 Å cubic cell), and ``N^cal`` needs one
    multiplicity per reflection over the whole enumeration, per candidate.  So the
    orbit images are formed for every reflection at once and counted by sorting an
    integer encoding of each image, which is exact rather than approximate: the
    encoding is a bijection on the index range in play.
    """
    h = np.atleast_2d(np.asarray(hkl, dtype=np.int64))
    if not len(h):
        return np.zeros(0, dtype=np.int64)
    rot = _laue_rotations(lattice_group(system, centring))
    # (N, R, 3) images, then their Friedel mates — a Laue group contains the
    # inversion, so the mates are usually already present; the stack costs one
    # concatenation and removes the "usually" from that sentence
    images = np.einsum("rij,nj->nri", rot, h)
    images = np.concatenate([images, -images], axis=1)
    base = 2 * int(np.abs(images).max()) + 1
    key = ((images[:, :, 0] * base) + images[:, :, 1]) * base + images[:, :, 2]
    key.sort(axis=1)
    distinct = np.ones_like(key, dtype=bool)
    distinct[:, 1:] = np.diff(key, axis=1) != 0
    return distinct.sum(axis=1).astype(np.int64)


def match_lines(q_obs: np.ndarray, q_esd: np.ndarray, q_pred: np.ndarray, *,
                k_sigma: float = MATCH_SIGMA):
    """(index of the matched prediction per observed line, |ΔQ| of the match).

    ``-1`` where nothing matched.  Matching is **per-line σ**, not one global
    tolerance: that is the whole contract ``schemas/indexing.py`` establishes, and
    it is why a strong sharp line and a weak shoulder are not held to the same
    window.
    """
    obs = np.asarray(q_obs, dtype=np.float64)
    pred = np.asarray(q_pred, dtype=np.float64)
    sig = np.maximum(np.asarray(q_esd, dtype=np.float64), 1e-300)
    if not len(pred):
        return np.full(len(obs), -1, dtype=np.int64), np.full(len(obs), np.inf)
    # Binary search, not an (observed × predicted) distance matrix.  The nearest
    # entry of a sorted array is one of the two straddling it, so this is exact —
    # and it is the difference between O(N·M) and O((N+M)·log M) in the innermost
    # loop of every engine: on a monoclinic search the trial set is ~10 000
    # reflections and this was ~10 ms per candidate.
    order = np.argsort(pred)
    sorted_pred = pred[order]
    right = np.searchsorted(sorted_pred, obs)
    left = np.clip(right - 1, 0, len(sorted_pred) - 1)
    right = np.clip(right, 0, len(sorted_pred) - 1)
    d_left = np.abs(obs - sorted_pred[left])
    d_right = np.abs(obs - sorted_pred[right])
    take_left = d_left <= d_right
    j_sorted = np.where(take_left, left, right)
    best = np.where(take_left, d_left, d_right)
    j = order[j_sorted]
    matched = best <= k_sigma * sig
    return np.where(matched, j, -1), np.where(matched, best, np.inf)


#: Relative tolerance on the "up to the N-th observed line" boundary in every
#: N_poss count.  It is a **tie rule, not a fudge**: the N-th observed line is
#: itself (ideally) a predicted line, so a strictly-less-than comparison makes the
#: count depend on floating-point rounding — measured, the *same lattice* in two
#: unimodular settings gave N_poss 20 and 19 and M₂₀ 76.43 and 80.45, a 5 % swing
#: on a quantity that must be setting-invariant by construction.
_BOUNDARY_RTOL = 1e-9


def _count_possible(pred: np.ndarray, limit: float) -> int:
    """Predictions up to ``limit``, counting the boundary (see _BOUNDARY_RTOL)."""
    return int(np.count_nonzero(np.asarray(pred)
                                <= limit * (1.0 + _BOUNDARY_RTOL)))


def trimmed_mean(discrepancy: np.ndarray, n_unindexed: int) -> float:
    """Mean |Δ| with the ``n_unindexed`` worst lines dropped.

    **A score must tolerate what the search was allowed to tolerate.**  An engine
    run with ``n_unindexed = 2`` may accept a cell that leaves two lines
    unexplained — that option is DICVOL06's own reported gain, and without it one
    impurity line prunes the true cell.  But de Wolff's ⟨ΔQ⟩ is a plain mean, so
    the same unexplained line then wrecks the *score* of the cell the search was
    right to keep: measured on a tetragonal list with one impurity, the truth
    scored M₂₀ = 13.2 against 62.5 for an a√5 supercell whose extra reflections
    happen to cover the impurity — and the supercell won the ranking while showing
    28 % of its own predicted lines against the truth's 100 %.

    Trimming the same number of lines the search was allowed to leave unindexed
    makes the two agree.  It is *not* free: it is the documented M₂₀ blind spot
    (one bad line wrecks the mean) traded against a new one (k bad lines are
    invisible), and which trade is right depends on a number the caller chose.  So
    the trim count travels with the value in ``blind_spot``.
    """
    d = np.sort(np.asarray(discrepancy, dtype=np.float64))
    if n_unindexed > 0 and len(d) > n_unindexed:
        d = d[:len(d) - n_unindexed]
    return float(np.mean(d)) if len(d) else float("inf")


def nearest_discrepancy(obs: np.ndarray, pred: np.ndarray) -> np.ndarray:
    """|Δ| from each observed line to its **nearest** prediction, no window.

    This is what de Wolff's and Smith & Snyder's means are taken over: every
    observed line is assigned to the closest calculated line, and a line that is
    badly missed contributes a *large* discrepancy rather than being excluded.
    Applying a matching window here instead would make both figures blind to the
    lines they are supposed to punish — which is why :func:`match_lines` (the
    windowed version) is used only by the coverage members.
    """
    o = np.asarray(obs, dtype=np.float64)
    p = np.asarray(pred, dtype=np.float64)
    if not len(p) or not len(o):
        return np.full(len(o), np.inf)
    return np.min(np.abs(o[:, None] - p[None, :]), axis=1)


def m20(q_obs: np.ndarray, q_esd: np.ndarray, q_pred: np.ndarray, *,
        n: int = FOM_N, k_sigma: float = MATCH_SIGMA,
        n_unindexed: int = 0) -> FigureOfMerit:
    """de Wolff's M₂₀ = Q_N / (2·⟨ΔQ⟩·N_poss).

    *Source*: de Wolff, P. M. (1968), *J. Appl. Cryst.* **1**, 108-113.  Read it
    as a signal-to-noise ratio on the *density* of possible lines: a lattice that
    explains the observed Q values with small discrepancies while allowing few
    lines up to Q_N scores high.

    **⟨ΔQ⟩ is floored at the median σ(Q)**, and that floor is this package's own
    addition rather than de Wolff's.  It is needed because the figure divides by
    the discrepancy: on synthetic data — or on any candidate that happens to fit
    within fp noise — ⟨ΔQ⟩ → 0 and M₂₀ → ∞, so an unfloored implementation
    returns either infinity or (if it guards with a zero test) **zero**, which
    ranks a perfect cell last.  Both were seen while writing this.  The floor has
    a meaning rather than being an epsilon: a discrepancy smaller than the
    measurement precision is not knowable, and per-line σ is exactly what this
    package has and 1968 did not.

    **Blind spots** (carried in the returned object): it counts *lattice*-possible
    lines, so it is blind to space-group extinctions — a cell that is a supercell
    along one axis is punished only through N_poss; and ⟨ΔQ⟩ is a plain mean, so a
    single impurity line among the first twenty wrecks it.
    """
    order = np.argsort(np.asarray(q_obs, dtype=np.float64))[:n]
    obs = np.asarray(q_obs, dtype=np.float64)[order]
    if len(obs) < 2:
        return FigureOfMerit(name="m20", value=0.0, n_lines=len(obs),
                             n_possible=0, k_sigma=k_sigma,
                             blind_spot=_BLIND["m20"])
    esd = np.asarray(q_esd, dtype=np.float64)[order]
    q_n = float(obs[-1])
    pred = np.asarray(q_pred, dtype=np.float64)
    n_poss = _count_possible(pred, q_n)
    dq = nearest_discrepancy(obs, pred)
    mean_dq = trimmed_mean(dq, n_unindexed)
    floor = float(np.median(esd))
    denom = max(mean_dq, floor)
    value = (q_n / (2.0 * denom * n_poss)
             if denom > 0.0 and n_poss > 0 and np.isfinite(denom) else 0.0)
    return FigureOfMerit(name="m20", value=float(value), n_lines=len(obs),
                         n_possible=n_poss, k_sigma=k_sigma,
                         mean_discrepancy=mean_dq if np.isfinite(mean_dq) else -1.0,
                         blind_spot=_blind("m20", n_unindexed))


def f_n(two_theta_obs: np.ndarray, two_theta_esd: np.ndarray,
        two_theta_pred: np.ndarray, *, n: int = FOM_N,
        k_sigma: float = MATCH_SIGMA, n_unindexed: int = 0) -> FigureOfMerit:
    """Smith & Snyder's F_N = (1/⟨|Δ2θ|⟩)·(N_obs/N_poss).

    *Source*: Smith, G. S. & Snyder, R. L. (1979), *J. Appl. Cryst.* **12**,
    60-65.

    **Blind spot**: it lives in 2θ, so it is sensitive to exactly the systematic
    the shift model exists for — a refined zero shift can manufacture a large F_N
    by absorbing a mismatch that a Q-space figure would have shown.  It is kept in
    the panel *because* of that: its disagreement with M₂₀ is informative, and
    ``tests/test_indexing_core.py`` pins the non-invariance rather than papering
    over it.
    """
    order = np.argsort(np.asarray(two_theta_obs, dtype=np.float64))[:n]
    obs = np.asarray(two_theta_obs, dtype=np.float64)[order]
    if len(obs) < 2:
        return FigureOfMerit(name="f_n", value=0.0, n_lines=len(obs),
                             n_possible=0, k_sigma=k_sigma,
                             blind_spot=_BLIND["f_n"])
    esd = np.asarray(two_theta_esd, dtype=np.float64)[order]
    pred = np.asarray(two_theta_pred, dtype=np.float64)
    n_poss = _count_possible(pred, float(obs[-1]))
    d = nearest_discrepancy(obs, pred)
    mean_d = trimmed_mean(d, n_unindexed)
    # the same precision floor M₂₀ needs, in degrees this time
    denom = max(mean_d, float(np.median(esd)))
    value = (len(obs) / (denom * n_poss)
             if denom > 0.0 and n_poss > 0 and np.isfinite(denom) else 0.0)
    return FigureOfMerit(name="f_n", value=float(value), n_lines=len(obs),
                         n_possible=n_poss, k_sigma=k_sigma,
                         mean_discrepancy=mean_d if np.isfinite(mean_d) else -1.0,
                         blind_spot=_blind("f_n", n_unindexed))


def indexed_fraction(q_obs: np.ndarray, q_esd: np.ndarray, q_pred: np.ndarray, *,
                     intensity: np.ndarray | None = None,
                     k_sigma: float = MATCH_SIGMA) -> FigureOfMerit:
    """Share of the observed lines (or observed *intensity*) a lattice indexes.

    **Blind spot, and it is the measured one this whole module is arranged
    around**: a big enough cell indexes everything.  On the §D data a wrong phase
    scored 83.7 % here against the truth's 79.2 % — so this number must never be
    ranked on alone, and :func:`predicted_seen_fraction` is its other half.
    """
    obs = np.asarray(q_obs, dtype=np.float64)
    idx, _ = match_lines(obs, q_esd, q_pred, k_sigma=k_sigma)
    hit = idx >= 0
    if intensity is None:
        value = float(np.mean(hit)) if len(hit) else 0.0
        name = "indexed_fraction"
    else:
        w = np.asarray(intensity, dtype=np.float64)
        total = float(np.sum(np.abs(w)))
        value = float(np.sum(np.abs(w[hit])) / total) if total > 0 else 0.0
        name = "indexed_intensity_fraction"
    return FigureOfMerit(name=name, value=value, n_lines=len(obs),
                         n_possible=int(len(np.asarray(q_pred))),
                         k_sigma=k_sigma, blind_spot=_BLIND["indexed_fraction"])


def predicted_seen_fraction(q_obs: np.ndarray, q_esd: np.ndarray,
                            q_pred: np.ndarray, *, k_sigma: float = MATCH_SIGMA
                            ) -> FigureOfMerit:
    """Share of the lattice's *predicted* lines that are actually present.

    The reversed direction, and a **first-class** ranking member: it is what
    separates a lattice that explains the pattern from one large enough to have a
    line near everything.  On the §D data the impostor showed 9.0 % of its 390
    predicted lines against the truth's 56.5 % of 23 — the two directions
    disagree by a factor of six where the forward direction disagreed by 4 points
    in the wrong direction.

    **Blind spot**: legitimately absent reflections count against a *correct*
    cell — space-group extinctions (unknown while indexing runs; WP-1025's screen
    determines them from this cell, not before it) and reflections too
    weak to detect.  So a low value is not evidence of a wrong cell on its own;
    it is evidence against a cell that also indexes suspiciously much.
    """
    pred = np.asarray(q_pred, dtype=np.float64)
    if not len(pred):
        return FigureOfMerit(name="predicted_seen_fraction", value=0.0,
                            n_lines=len(np.asarray(q_obs)), n_possible=0,
                            k_sigma=k_sigma,
                            blind_spot=_BLIND["predicted_seen_fraction"])
    # reverse the roles: for each prediction, is there an observed line within
    # that *observed* line's own σ?  The σ belongs to the measurement, so it stays
    # attached to the observation even when the loop runs the other way.
    obs = np.asarray(q_obs, dtype=np.float64)
    sig = np.maximum(np.asarray(q_esd, dtype=np.float64), 1e-300)
    if not len(obs):
        seen = np.zeros(len(pred), dtype=bool)
    else:
        d = np.abs(pred[:, None] - obs[None, :])
        j = np.argmin(d, axis=1)
        seen = d[np.arange(len(pred)), j] <= k_sigma * sig[j]
    return FigureOfMerit(
        name="predicted_seen_fraction", value=float(np.mean(seen)),
        n_lines=len(obs), n_possible=len(pred), k_sigma=k_sigma,
        blind_spot=_BLIND["predicted_seen_fraction"])


#: The resolution multiple for every **reversed** question (predicted line →
#: observed line): two positions closer than this many FWHM are one line as far
#: as a peak list can tell, and a predicted line is *seen* only within this
#: distance of a picked component.  One, not :data:`~rietx.model.forward.PAWLEY_OVERLAP_FWHM_FRAC`'s
#: half: 0.5 is where least squares stops apportioning intensity, while a
#: *picker* separates two equal components only from about one FWHM (the
#: Rayleigh (1879, Phil. Mag. 8, 261) and Sparrow (1916, Astrophys. J. 44, 76)
#: criteria put "two lines or one" at about a width).  Measured
#: on the tetragonal control set: at 0.5 a true cell whose 0.0003 × b split
#: reaches 0.9 FWHM at 60° was refuted as a resolved split; at 1 every control
#: passes.  The forward question — does this cell index that observed line —
#: keeps the **search** window (``engines.match_window``, 3σ_eff with the
#: shift allowance folded in), which on a synchrotron pattern is six FWHM wide:
#: asked in that window, a resolved orthorhombic split scored 0.99 on this
#: member and the hR cell that outranked the truth in issue #916 scored 0.78;
#: at the resolution they read 0.56 and 0.34 against the truth's 0.73.  An
#: allowance bounds a common offset and belongs to the forward match alone;
#: the common shift the forward matches imply (:func:`common_shift`) is what
#: places the reversed question.  Swept from 0.5 to 1.0 on the acceptance
#: corpus's real families (#941's follow-ups, 15 runs from 12 sources: the CPD
#: round robin's seven patterns, NIST SRM 660c, 11-BM NAC, the GSAS-II FAP and
#: Hill's PbSO4 X-ray and neutron histograms, one of which has no truth to
#: rank): one true cell's rank moves, PbSO4 X-ray at 0.7, where the truth
#: ranks 2nd behind a cell within 0.5 % of its metric; every other truth ranks
#: 1st with the same grade at every value, so the synthetic split above sets
#: it.  The sweep stops at 1.0: it shows nothing below 1.0 does better and
#: cannot show that 1.0 beats a larger value.  Floored by
#: ``k_sigma`` × σ(2θ) of the component asked against, so a position-only
#: list keeps a window.
RESOLUTION_FWHM = 1.0


def two_theta_of_q(q: np.ndarray, wavelength: float) -> np.ndarray:
    """°2θ of Q = 1/d², the inverse of :func:`~rietx.schemas.indexing.q_of_two_theta`."""
    return np.degrees(2.0 * np.arcsin(np.clip(
        wavelength * np.sqrt(np.maximum(np.asarray(q, dtype=np.float64), 0.0))
        / 2.0, -1.0, 1.0)))


def resolution_half_width(fwhm_at: np.ndarray, fwhm_comp: np.ndarray,
                          esd_comp: np.ndarray, *, k_sigma: float = MATCH_SIGMA,
                          resolution: float = RESOLUTION_FWHM) -> np.ndarray:
    """Half-width (°2θ) of the reversed window about a component: the resolution
    times the mean of the local width law and the component's own FWHM, floored
    by ``k_sigma`` × that component's σ(2θ)."""
    return np.maximum(resolution * 0.5 * (np.asarray(fwhm_at, dtype=np.float64)
                                          + np.asarray(fwhm_comp, dtype=np.float64)),
                      k_sigma * np.asarray(esd_comp, dtype=np.float64))


def merge_at_resolution(tt_pred: np.ndarray, fwhm_pred: np.ndarray, *,
                        resolution: float = RESOLUTION_FWHM) -> list[np.ndarray]:
    """Group ascending predicted positions closer than the resolution into lines.

    Each group is an index array; a position joins the open group when it sits
    within ``resolution`` × the mean FWHM of the group's last member.  Without
    this a split cell counts a truth's one glide absence once per partner, so a
    tetragonal description of a cubic truth read its three absences eight
    times (F1's first pass).
    """
    tt = np.asarray(tt_pred, dtype=np.float64)
    fw = np.asarray(fwhm_pred, dtype=np.float64)
    if not len(tt):
        return []
    groups: list[list[int]] = [[0]]
    for k in range(1, len(tt)):
        last = groups[-1][-1]
        if tt[k] - tt[last] < resolution * 0.5 * (fw[k] + fw[last]):
            groups[-1].append(k)
        else:
            groups.append([k])
    return [np.asarray(g, dtype=np.int64) for g in groups]


def common_shift(tt_obs: np.ndarray, tt_pred: np.ndarray,
                 idx: np.ndarray) -> float:
    """The common 2θ offset (°) the forward matches imply: the median of
    observed − predicted over the indexed lines, 0 when nothing is indexed.

    An allowance is not a correction (WP-1038); this is the one correction the
    forward matches themselves carry, used only to place the reversed question.
    """
    idx = np.asarray(idx)
    hit = idx >= 0
    if not np.any(hit):
        return 0.0
    return float(np.median(np.asarray(tt_obs, dtype=np.float64)[hit]
                           - np.asarray(tt_pred, dtype=np.float64)[idx[hit]]))


def seen_at_resolution(tt_pred: np.ndarray, fwhm_at: np.ndarray,
                       tt_comp: np.ndarray, fwhm_comp: np.ndarray,
                       esd_comp: np.ndarray, *, k_sigma: float = MATCH_SIGMA,
                       resolution: float = RESOLUTION_FWHM
                       ) -> tuple[np.ndarray, np.ndarray]:
    """``(seen, j)``: whether each predicted position lies within the reversed
    window of its nearest component ``j``.  Nothing is seen on an empty list."""
    pred = np.asarray(tt_pred, dtype=np.float64)
    comp = np.asarray(tt_comp, dtype=np.float64)
    if not len(pred) or not len(comp):
        return np.zeros(len(pred), dtype=bool), np.full(len(pred), -1)
    gap = np.abs(pred[:, None] - comp[None, :])
    j = np.argmin(gap, axis=1)
    half = resolution_half_width(fwhm_at, np.asarray(fwhm_comp)[j],
                                 np.asarray(esd_comp)[j], k_sigma=k_sigma,
                                 resolution=resolution)
    return gap[np.arange(len(pred)), j] <= half, j


def predicted_seen_fraction_at_resolution(
        two_theta_obs: np.ndarray, two_theta_esd: np.ndarray,
        fwhm_obs: np.ndarray, two_theta_pred: np.ndarray, *,
        shift: float = 0.0, k_sigma: float = MATCH_SIGMA,
        resolution: float = RESOLUTION_FWHM) -> FigureOfMerit:
    """:func:`predicted_seen_fraction` asked at the **resolution** (C3, F1 § 3.2).

    The predicted lines are merged at ``resolution`` × the local FWHM, moved by
    the candidate's common ``shift``, and each merged line is *seen* when a
    picked component lies within :func:`resolution_half_width`.  Given the
    screen's positions and common shift it reads the screen's seen fraction
    exactly (``test_the_panel_and_the_screen_share_one_definition_of_seen``);
    the two can still differ by their inputs, since the panel's shift comes from
    the search window and its positions stop at the last observed line, where
    the screen's shift reads the absence window over the pattern's range.
    Same name and blind spot as the windowed member it replaces in the panel: a space-group
    extinction or an undetected weak line still counts against a correct cell,
    which is why it ranks and never refutes.
    """
    obs = np.asarray(two_theta_obs, dtype=np.float64)
    pred = np.sort(np.asarray(two_theta_pred, dtype=np.float64))
    if not len(pred) or not len(obs):
        return FigureOfMerit(name="predicted_seen_fraction", value=0.0,
                            n_lines=len(obs), n_possible=len(pred),
                            k_sigma=k_sigma,
                            blind_spot=_BLIND["predicted_seen_fraction"])
    order = np.argsort(obs)
    fw_at = np.interp(pred, obs[order], np.asarray(fwhm_obs, dtype=np.float64)[order])
    groups = merge_at_resolution(pred, fw_at, resolution=resolution)
    merged = np.array([float(np.mean(pred[g])) for g in groups]) + shift
    # the width law read at the shifted merged line, as the line screen reads
    # it (``screen.screen_candidate``): one definition of seen for both
    fw_m = np.interp(merged, obs[order],
                     np.asarray(fwhm_obs, dtype=np.float64)[order])
    seen, _j = seen_at_resolution(merged, fw_m, obs, fwhm_obs, two_theta_esd,
                                  k_sigma=k_sigma, resolution=resolution)
    return FigureOfMerit(
        name="predicted_seen_fraction", value=float(np.mean(seen)),
        n_lines=len(obs), n_possible=len(merged), k_sigma=k_sigma,
        blind_spot=_BLIND["predicted_seen_fraction"])


def _reversed_pair(q_obs: np.ndarray, q_esd: np.ndarray, q_pred: np.ndarray,
                   m_pred: np.ndarray, *, n: int = FOM_N,
                   k_sigma: float = MATCH_SIGMA,
                   n_unindexed: int = 0) -> tuple[FigureOfMerit, FigureOfMerit]:
    """``M^Rev`` and ``M^Sym`` — the de Wolff figure run backwards, and the product.

    *Source*: Oishi-Tomiyasu, R. (2013), *J. Appl. Cryst.* **46**, 1277-1282,
    eqs. (4), (7), (9)-(11).

    M₂₀ asks how far each *observed* line is from its nearest prediction.  A
    wrong metric that matches a subset tightly is rewarded by that question, and
    the reversed figure asks the other one: how far is each *predicted* line from
    its nearest observation, averaged with weight ``1/m(hkl)`` so an orbit counts
    once however many triples generate it.  ``predicted_seen_fraction`` reaches
    the same failure from the other side and the two are complementary rather than
    redundant — ours is a windowed fraction, this is an unbounded continuous
    ratio, so it separates candidates that both score 1.0 on coverage.

    **The scale is not M₂₀'s and importing a threshold from de Wolff would reject
    nearly every correct cell.**  In the paper's own tables ``M^Rev`` for correct
    solutions runs ~1.7-15.8 where ``M̃₂₀`` reaches 556; its screen is ``M̃ₙ ≥ 3``,
    ``M^Rev ≥ 1``, ``12 ≤ N^cal ≤ 120``.  Nothing here thresholds them — they
    enter the panel as Borda members, where only the ordering matters.

    The vanishing-δ floor is **this package's, not the paper's**, which does not
    address it: on synthetic or fp-exact data ``δ_rev`` vanishes exactly as
    ``δ_fwd`` does in :func:`m20`, and the same median-σ floor is applied for the
    same reason and recorded in ``blind_spot``.
    """
    order = np.argsort(np.asarray(q_obs, dtype=np.float64))[:n]
    obs = np.asarray(q_obs, dtype=np.float64)[order]
    pred = np.asarray(q_pred, dtype=np.float64)
    blind_rev = _blind("m_rev", n_unindexed)
    blind_sym = _blind("m_sym", n_unindexed)
    if len(obs) < 2 or not len(pred):
        empty = dict(n_lines=len(obs), n_possible=0, k_sigma=k_sigma)
        return (FigureOfMerit(name="m_rev", value=0.0, blind_spot=blind_rev,
                              **empty),
                FigureOfMerit(name="m_sym", value=0.0, blind_spot=blind_sym,
                              **empty))
    esd = np.asarray(q_esd, dtype=np.float64)[order]
    floor = float(np.median(esd))

    # the window is the *computed* pair bracketing the observed range, not the
    # observed values themselves — eq. (7)'s qI and qN
    q_i = float(pred[np.argmin(np.abs(pred - obs[0]))])
    q_n = float(pred[np.argmin(np.abs(pred - obs[-1]))])
    lo, hi = (q_i, q_n) if q_i <= q_n else (q_n, q_i)
    count = n_cal(pred, m_pred, lo, hi)

    inside = (pred >= lo * (1.0 - _BOUNDARY_RTOL)) & (pred <= hi *
                                                      (1.0 + _BOUNDARY_RTOL))
    weight = 1.0 / np.asarray(m_pred, dtype=np.float64)[inside]
    gap = nearest_discrepancy(pred[inside], obs)
    delta_rev = (2.0 * float(np.sum(gap * weight)) / count
                 if count > 0.0 and inside.any() else np.inf)
    eps_rev = float(obs[-1] - obs[0]) / (2.0 * len(obs))
    value_rev = (eps_rev / max(delta_rev, floor)
                 if np.isfinite(delta_rev) and max(delta_rev, floor) > 0.0
                 else 0.0)

    # M̃ₙ — the forward figure on the *same* window and denominator, which is what
    # makes the product M^Sym a symmetric statement rather than two scales mixed
    delta_fwd = trimmed_mean(nearest_discrepancy(obs, pred), n_unindexed)
    eps_fwd = (q_n - q_i) / (2.0 * count) if count > 0.0 else 0.0
    value_tilde = (eps_fwd / max(delta_fwd, floor)
                   if np.isfinite(delta_fwd) and max(delta_fwd, floor) > 0.0
                   else 0.0)

    # the float is what both values divided by; ``n_possible`` is an int on the
    # schema, so the reported count is rounded and the computation is not
    n_poss = int(round(count))
    return (
        FigureOfMerit(
            name="m_rev", value=float(value_rev), n_lines=len(obs),
            n_possible=n_poss, k_sigma=k_sigma,
            mean_discrepancy=delta_rev if np.isfinite(delta_rev) else -1.0,
            blind_spot=blind_rev),
        FigureOfMerit(
            name="m_sym", value=float(value_tilde * value_rev),
            n_lines=len(obs), n_possible=n_poss, k_sigma=k_sigma,
            mean_discrepancy=delta_rev if np.isfinite(delta_rev) else -1.0,
            blind_spot=blind_sym),
    )


def panel_undefined(n_usable: int) -> dict[str, str]:
    """Panel members undefined on a list of this length, name → reason.

    The one authority for "can this list be **scored**", which WP-1043 separated
    from "can it be searched" (``MIN_LINES_PER_DOF`` and the per-system
    ``supported`` computation in ``quality.py`` own the second question).
    Whether a figure is computable is a property of the *peak list* — its line
    count — not of any candidate, so below :data:`FOM_N` the panel shrinks by
    the same members for every candidate, uniformly, and Borda still ranks over
    the members that remain.  A figure computed on fewer lines would not be the
    published quantity (an M on 18 lines is not M₂₀ and no published threshold
    transfers), so each is reported **absent with its reason** — recorded on
    ``DataQualityReport.fom_undefined`` — never computed at a different N and
    never silently zero.
    """
    if n_usable >= FOM_N:
        return {}
    return {
        "m20": (f"{n_usable} usable lines, below the {FOM_N} de Wolff's M20 "
                "is defined on (de Wolff 1968)"),
        "f_n": (f"{n_usable} usable lines, below the {FOM_N} this package "
                "scores F_N at (Smith & Snyder 1979 define F_N for general N "
                "and recommend 30)"),
    }


def fom_panel(q_obs: np.ndarray, q_esd: np.ndarray, intensity: np.ndarray,
              two_theta_obs: np.ndarray, two_theta_esd: np.ndarray,
              cell: tuple[float, ...], system: str, centring: str,
              wavelength: float, *, k_sigma: float = MATCH_SIGMA,
              n_unindexed: int = 0,
              q_match: np.ndarray | None = None,
              fwhm_obs: np.ndarray | None = None) -> list[FigureOfMerit]:
    """Every figure of merit for one candidate, in one pass over the predictions.

    ``n_unindexed`` must be the same count the *search* was allowed — see
    :func:`trimmed_mean` for the measurement that makes them one number.

    ``fwhm_obs`` (°2θ per observed line, the peak list's) switches the reversed
    member to the **resolution**: :func:`predicted_seen_fraction_at_resolution`
    at :data:`RESOLUTION_FWHM`, after the common shift the forward matches
    imply.  Without it the member is asked in the matching window, which on a
    synchrotron pattern is six FWHM wide and cannot see a resolved split
    (C3; the numbers are on :data:`RESOLUTION_FWHM`).  Every caller that holds
    a fitted peak list passes it; a position-only list has an assumed width
    and still gets the σ floor.

    **``q_match`` is the matching window and ``q_esd`` is the measurement, and the
    panel needs both** — CLAUDE.md's rule that a fitted σ is the right weight and
    the wrong matching window, one rank up from the engines.  The three coverage
    members ask *is this the same line*, which is a question about the systematic
    a search had to open its window for; M₂₀ and F_N use σ only to **floor** their
    mean discrepancy, which is a question about what the measurement can resolve
    and must never be answered with an assumed allowance.  So a caller widening the
    window widens the coverage members alone.

    Defaulting ``q_match`` to ``q_esd`` is the identity, and that default is what
    every published-figure comparison uses.  Measured on the certified corundum
    pattern, where the two differ by 11× (fitted σ 0.0045° against a 0.05°
    allowance): ``indexed_fraction`` reads **0.11-0.20** on candidates the search's
    own assignment indexed at **0.65-0.89**, so every candidate was refuted by
    ``indexed_fraction_low`` whatever its merit, and the Borda order was decided
    among cells that had all matched almost nothing.
    """
    tt_max = float(np.max(two_theta_obs)) if len(two_theta_obs) else 0.0
    # one enumeration serves both halves of the panel: the classical members want
    # distinct *lines*, N^cal wants unmerged orbits with their multiplicities
    _hkl, q_raw, m_raw = lattice_reflections(cell, system, centring, wavelength,
                                             max(tt_max, 1.0),
                                             multiplicity=True)
    q_pred = q_raw
    if len(q_raw) > 1:
        distinct = np.ones(len(q_raw), dtype=bool)
        distinct[1:] = np.diff(q_raw) > LINE_COINCIDENCE_RTOL * q_raw[1:]
        q_pred = q_raw[distinct]
    tt_pred = np.degrees(2.0 * np.arcsin(np.clip(
        wavelength * np.sqrt(q_pred) / 2.0, -1.0, 1.0)))
    match = q_esd if q_match is None else q_match
    m_rev, m_sym = _reversed_pair(q_obs, q_esd, q_raw, m_raw, k_sigma=k_sigma,
                                  n_unindexed=n_unindexed)
    # the scoring bar (WP-1043): members undefined at this line count are left
    # out of every candidate's panel alike — the same members for all, so Borda
    # still ranks — and their reasons travel on the quality report, never here
    undefined = panel_undefined(len(np.asarray(q_obs)))
    if fwhm_obs is None:
        seen = predicted_seen_fraction(q_obs, match, q_pred, k_sigma=k_sigma)
    else:
        # the forward match decides the common shift; the reversed question
        # is then asked at the resolution, never in the search window
        idx, _ = match_lines(q_obs, match, q_pred, k_sigma=k_sigma)
        seen = predicted_seen_fraction_at_resolution(
            two_theta_obs, two_theta_esd, fwhm_obs, tt_pred,
            shift=common_shift(two_theta_obs, tt_pred, idx), k_sigma=k_sigma)
    members = [
        m20(q_obs, q_esd, q_pred, k_sigma=k_sigma, n_unindexed=n_unindexed),
        f_n(two_theta_obs, two_theta_esd, tt_pred, k_sigma=k_sigma,
            n_unindexed=n_unindexed),
        indexed_fraction(q_obs, match, q_pred, k_sigma=k_sigma),
        indexed_fraction(q_obs, match, q_pred, intensity=intensity,
                         k_sigma=k_sigma),
        seen,
        m_rev,
        m_sym,
    ]
    return [f for f in members if f.name not in undefined]


def borda_scores(panels: list[list[FigureOfMerit]]) -> np.ndarray:
    """Borda count over the panel: sum of each candidate's rank in every member.

    Higher is better, and every member weighs the same.  A weighted sum would
    need weights, and there is no data on which to set them — whereas the *rank*
    aggregation needs none and is invariant to each member's units and scale,
    which matters when the panel mixes a ratio (M₂₀), an inverse-degrees quantity
    (F_N) and two fractions.

    **Ties share their rank, and that is not a nicety.**  Two of the five members
    are fractions that saturate at 1.0, so on any well-explained pattern most
    candidates tie on them.  Ranking ties by array position instead (the
    ``argsort(argsort)`` this function used to do) injects up to N−1 points of
    pure ordering noise *per tied member* — measured on a synthetic tetragonal
    list, that put two derivative lattices above a truth that beat them on every
    single member of the panel.  Averaged ranks are the standard Borda treatment
    of ties and they make the aggregate depend only on the values.

    Non-finite values rank **worst** rather than best: a figure that could not be
    computed is not evidence in a candidate's favour.
    """
    from scipy.stats import rankdata

    if not panels:
        return np.zeros(0)
    names = [f.name for f in panels[0]]
    scores = np.zeros(len(panels))
    for k, name in enumerate(names):
        values = np.array([p[k].value if p[k].name == name else -np.inf
                           for p in panels], dtype=np.float64)
        values = np.where(np.isfinite(values), values, -np.inf)
        scores += rankdata(values, method="average") - 1.0    # 0 = worst
    return scores


#: Panel members the aggregate does not read.  ``m_sym`` is ``M̃ₙ × M^Rev`` by
#: construction (:func:`_reversed_pair`), so on a log scale it is *exactly*
#: ``log M̃ₙ + log M^Rev``: including it counts ``m_rev`` a second time and adds a
#: near-duplicate of the forward figure alongside ``m20``.  A rank aggregation
#: could not see this — Borda is blind to one member being a monotone function of
#: others — which is why the exclusion arrives with the log-sum and not before it.
_AGGREGATE_EXCLUDES: frozenset[str] = frozenset({"m_sym"})

#: How far below the best candidate a member's value is floored before its log is
#: taken.  **Relative** to that best, so the floor rescales with the member and
#: the aggregate stays invariant to its units; six orders down is past anything
#: still in contention, so it only compresses hopeless candidates against each
#: other rather than deciding between them.
_AGGREGATE_FLOOR_RTOL = 1e-6


def _log_sum_scores(panels: list[list[FigureOfMerit]], *,
                   exclude: frozenset[str] = _AGGREGATE_EXCLUDES,
                   floor_rtol: float = _AGGREGATE_FLOOR_RTOL) -> np.ndarray:
    """Sum of ``log`` over the panel: magnitude-aware, still unit-invariant.

    Higher is better, and ranking on this is ranking on the **product** of the
    members — a geometric mean up to a constant.

    **Why not Borda.**  A rank aggregation spends one whole point on a win of any
    size, so a near-tie and a rout are worth the same.  Measured on 11-BM NAC,
    that is not hypothetical: the primitive candidate beat the body-centred truth
    4 members to 3 while *taking* two of those members by 0.4 % and 0.01 % and
    *losing* ``m_rev`` by 516×, and Le Bail agreed with the loser.  A margin the
    panel measured in orders of magnitude was spent as one point, and three
    hairline margins outvoted it.

    **Why logs rather than a weighted sum.**  The panel mixes a ratio (M₂₀), an
    inverse-degrees quantity (F_N) and three fractions, so a plain sum is
    dominated by whichever member happens to carry the largest numbers, and
    fixing that needs weights there is no data to set.  Rescaling a member by
    ``c > 0`` shifts every candidate's log-sum by the same ``log c``, so the
    ordering does not depend on any member's units — the property that made
    ranks attractive — while the *size* of each win survives.

    What is given up is invariance to an arbitrary monotone reparametrisation of
    a member, which ranks do have.  That is the trade, not an oversight: a
    figure's magnitude is evidence, and a transform that changes ratios changes
    what the evidence says.

    Zero, negative and non-finite values floor at ``floor_rtol`` of the best
    candidate on that member, so a figure that could not be computed ranks worst
    rather than aborting the sum.  A member on which *every* candidate scores
    zero is silent and contributes nothing, rather than making every score
    ``-inf``.

    **This is not the ranking in use, and the measurement is why.**
    :func:`~rietx.indexing.engines.rank_candidates` still aggregates with
    :func:`borda_scores`.  Measured across six known-cell datasets (WP-1041), a
    plain log-sum ranks the truth first on **5 of 6** — exactly Borda's score,
    with a different failure: it fixes 11-BM NAC, where the truth wins ``m_rev``
    by 516×, and breaks certified corundum, where it promotes a half-volume
    subcell that indexes 43 of 55 lines against the truth's 51.

    The mechanism is general, so read it before reaching for this again: summing
    raw logs weights each member by its **dynamic range** across the candidate
    set, and the panel's ranges are not comparable — on corundum ``m_rev`` spans
    2.5→356 while the coverage fractions span 0.78→0.99, so one member is worth
    ten of another for no stated reason.  Standardising each member's logs cures
    that and **degenerates exactly where it is needed**: with two candidates every
    z-score is ±1 by construction, so NAC reverts to Borda's answer.  Down-
    weighting ``m_rev`` reaches 6 of 6 and the corpus brackets the weight only to
    ``0.034 < w < 0.294`` — two datasets setting one constant, which is the
    tuning the panel exists to avoid.  Kept, exported and tested because it is
    the instrument that measured all of this, not because it won.
    """
    if not panels:
        return np.zeros(0)
    scores = np.zeros(len(panels))
    by_name = [{f.name: float(f.value) for f in p} for p in panels]
    names = [f.name for f in panels[0] if f.name not in exclude]
    for name in names:
        values = np.array([d.get(name, np.nan) for d in by_name],
                          dtype=np.float64)
        values = np.where(np.isfinite(values) & (values > 0.0), values, 0.0)
        best = float(np.max(values)) if len(values) else 0.0
        if best <= 0.0:
            continue
        scores += np.log(np.maximum(values, best * floor_rtol))
    return scores


def fom_panel_disagrees(panels: list[list[FigureOfMerit]]) -> bool:
    """Do the panel's members put different candidates first?

    A disagreement is not a tie-break problem, it is *information*: the members
    have different blind spots, so when they rank differently at least one blind
    spot is active.  WP-1024 turns this into a confidence statement rather than
    resolving it here.
    """
    if len(panels) < 2:
        return False
    winners = set()
    for k in range(len(panels[0])):
        values = [p[k].value for p in panels]
        winners.add(int(np.argmax(values)))
    return len(winners) > 1


#: Blind spots, stated once and attached to every value the functions return.
_BLIND: dict[str, str] = {
    "m20": ("counts lattice-possible lines, so it is blind to space-group "
            "extinctions; its ⟨ΔQ⟩ is a plain mean, so one impurity line among "
            "the first twenty wrecks it"),
    "f_n": ("lives in 2θ, so a refined zero shift can manufacture a large value "
            "by absorbing a mismatch a Q-space figure would show"),
    "indexed_fraction": ("a big enough cell indexes everything — measured, a "
                         "wrong phase scored 83.7 % against the truth's 79.2 % "
                         "with 390 predicted lines to the truth's 23"),
    "predicted_seen_fraction": ("legitimately absent reflections count against a "
                                "correct cell: space-group extinctions (unknown "
                                "until the extinction symbol is determined) and "
                                "reflections too weak to detect"),
    "m_rev": ("penalises a correct cell for space-group extinctions, the same "
              "blind spot as predicted_seen_fraction and confirmed by the paper "
              "that defines it; its δ is floored at the median σ(Q), which is "
              "this package's addition and not Oishi-Tomiyasu's, because δ_rev "
              "vanishes on fp-exact data exactly as M₂₀'s ⟨ΔQ⟩ does; and its "
              "scale is not M₂₀'s — correct cells score ~1.7-15.8 where M̃₂₀ "
              "reaches 556, so a de Wolff threshold would reject almost all of "
              "them"),
    "m_sym": ("the product of the forward and reversed figures over one window, "
              "so it inherits both their blind spots and is not independent "
              "evidence from m_rev; a candidate can reach it by being mediocre "
              "in both directions rather than good in either"),
}

def _blind(name: str, n_unindexed: int) -> str:
    """The blind spot, with the trim count in it when one was applied."""
    text = _BLIND[name]
    if n_unindexed > 0:
        text += (f"; its mean discrepancy is trimmed by {n_unindexed} line(s) to "
                 "match what the search was allowed to leave unindexed, so that "
                 "many badly-fitting lines are invisible to it")
    return text


__all__ = ["FOM_N",
           "MATCH_SIGMA", "borda_scores", "f_n",
           "fom_panel", "fom_panel_disagrees", "indexed_fraction",
           "lattice_group", "lattice_reflections", "laue_multiplicity",
           "m20",
           "match_lines", "n_cal", "nearest_discrepancy", "panel_undefined",
           "predicted_lines",
           "predicted_seen_fraction", "q_of_two_theta", "trimmed_mean"]
