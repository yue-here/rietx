"""The line screen: every reversed question asked of inputs a candidate cannot buy.

A candidate cell makes two kinds of claim about a peak list.  The **forward**
one — this observed line is one of mine — is asked in the search window and
scored by the coverage members of the panel.  The **reversed** ones — the lines
I predict are there; the lines I predict and the pattern lacks are a
coincidence; the lines I add over a smaller cell are seen — were, until C3,
asked of the candidate's own Le Bail fit (``predicted_but_absent``) or in the
search window (``predicted_seen_fraction``, ``supercell_chance``).  Both inputs
are the candidate's to buy.  Measured (issue #916, WP-1043): a wrong primitive
description of magnetite needing intensity under 163 reflections drove its
co-refined background negative and read **zero** absent; a search window of
±0.15° on a pattern whose FWHM is 0.023° let a resolved orthorhombic split and
a trigonal description of the cubic truth read *supported* against chance.

This module asks them once per candidate of the **peak list and the detection**
— positions, measured widths and shapes, the picker's background envelope, the
package's own overlap rule — at the measured **resolution**
(:data:`~rietx.indexing.fom.RESOLUTION_FWHM`), after the common shift the
forward matches imply.  No fit.  Three consumers read it:

* the **rank**: ``predicted_seen_fraction`` is the screen's seen fraction
  (:func:`~rietx.indexing.fom.predicted_seen_fraction_at_resolution`, wired in
  ``fom_panel``);
* the **grade**: ``consensus.supercell_checks`` asks child against parent by
  **containment of the indexed observed set** (every line the parent indexes,
  the child indexes) and judges the child's uncancellable extras against
  chance (:func:`containment_evidence`), reaching every cell the index-2-to-4
  sublattice relation could not — cubic I √2·a₀ over cubic F a₀, the hR cell
  that outranked the truth in #916, a resolved split;
* the **validation**: ``LeBailValidation.predicted_but_absent`` is the screen's
  absent count, and the caveat fires on the **windowed uncancellable** count
  (:attr:`LineScreen.n_absent_uncancellable_in_window`) and **caps** rather
  than refutes.

**Why the count is windowed and capping, and the pairwise test is neither.**
On real lab data a true cell carries uncancellable absences over the full
range through general reflections below the picker's detection: corundum 5,
magnetite 2, and more on a neutron pattern read to high angle, most of them
above 70°.  So any absolute full-range count refutes a truth somewhere.
Restricted to de Wolff's window — positions up to the Q of the 20th usable
line, where a truth's lines are strong enough to be detected (de Wolff 1968,
*J. Appl. Cryst.* **1**, 108) — the truths read 0 (Si, the tetragonal set,
corundum) or 2 (magnetite) and the wrong cells 7–79.  The pairwise test keeps
the full range because its discriminating extras can sit above the window
(the resolved split, corundum's index-3 descriptions) and its null, p₀,
already discounts unseen high-angle lines.  And a non-significant result does
not establish the null (Altman & Bland 1995, *BMJ* **311**, 485): *refuted*
means seen **no more often than chance**, k ≤ n·p₀, not merely p ≥ α —
corundum's own cell as a child of its c/2 subcell reads 8 of 18 seen at
p₀ = 0.21 (expected 3.7, p = 0.019), which the two-band rule called refuted
and the three-band one calls undecided.  The measurements are in the C3
record (``planning`` report ``fable-indexing-absent-lines-20261012``).

**Precedent.**  Absent-line penalties in the field are density figures, never
absolute bars: de Wolff's N_poss, Smith & Snyder's (1979) F_N, Oishi-Tomiyasu's
(2013) M^Rev; EXPO's WRIP20 (Altomare *et al.* 2009, *J. Appl. Cryst.* **42**,
768) orders on the present-reflection share under the best extinction symbol
as a ratio to the best candidate.  Le Bail's McMaille (2004, *Powder Diffr.*
**19**, 249) scores candidates on a pseudo-profile built from the observed
lines at a fixed width, the closest precedent for a width-only
candidate-independent screen.  The pairwise question against chance is
rietx's own (WP-1449); this module generalises its reach.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..schemas.indexing import PeakList, q_of_two_theta
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData
from .ambiguity import SupercellEvidence, uncancellable
from .fom import (
    LINE_COINCIDENCE_RTOL,
    MATCH_SIGMA,
    RESOLUTION_FWHM,
    common_shift,
    lattice_reflections,
    match_lines,
    merge_at_resolution,
    resolution_half_width,
    seen_at_resolution,
    two_theta_of_q,
)

#: Lines of de Wolff's window: the capping count takes the predicted positions
#: up to the Q of the N-th usable observed line, N the lesser of this and the
#: list's length.  de Wolff's own twenty (1968, J. Appl. Cryst. 1, 108), the
#: window M₂₀ is defined on, held as its own literal: the panel's
#: :data:`~rietx.indexing.fom.FOM_N` is this package's choice for F_N and a
#: retune of it must not move the absence window.
SCREEN_WINDOW_LINES = 20
_LN2 = float(np.log(2.0))


def _pseudo_voigt(x: np.ndarray, gamma: float, eta: float) -> np.ndarray:
    """Unit-area pseudo-Voigt of FWHM ``gamma``, the peak list's own shape.

    Thompson, Cox & Hastings (1987), J. Appl. Cryst. 20, 79: η·L + (1-η)·G of
    one FWHM.  The same function as ``model.profiles.pseudovoigt.pseudo_voigt``,
    spelled here in plain numpy so the screen never reads the model's global
    backend; ``test_the_screens_pseudo_voigt_is_the_models`` pins them equal.
    """
    g = (2.0 * np.sqrt(_LN2 / np.pi) / gamma
         * np.exp(-4.0 * _LN2 * x ** 2 / gamma ** 2))
    lor = (2.0 / (np.pi * gamma)) / (1.0 + 4.0 * x ** 2 / gamma ** 2)
    return eta * lor + (1.0 - eta) * g


@dataclass
class PatternScreen:
    """One pattern's candidate-independent facts, computed once per run.

    From the peak list alone: the usable lines (position, σ, FWHM, η, area,
    Q), the search window ``q_match`` the forward question is asked in, the
    resolution window per line, the chance rate p₀ at that resolution, and
    de Wolff's window ``q_window``.  With the pattern (``data`` +
    ``instrument``): the grid over the peak list's range, the picker's
    debiased background envelope, σ per channel, every emission-line
    component (Kα2 images included, for testability), and the peak-list
    profile model on the grid — the candidate-free ``y_calc`` that
    :func:`~rietx.indexing.extinction._model_is_quiet` reads.

    ``seen`` is asked against the **primary** components only: a predicted
    line on a Kα2 image of another line has no line of its own there, so it is
    unseen, and it is also untestable (overlapped by the image), so it is never
    *absent* either.  One definition of seen for the panel, which holds no
    instrument, and the screen.
    """

    wavelength: float
    two_theta_min: float
    two_theta_max: float
    k_sigma: float
    resolution: float
    #: usable lines, in ``peaks.usable()`` order
    obs_tt: np.ndarray
    obs_esd: np.ndarray
    obs_fwhm: np.ndarray
    obs_eta: np.ndarray
    obs_intensity: np.ndarray
    obs_q: np.ndarray
    #: the search's σ(Q) per line (``engines.match_window``), the forward window
    q_match: np.ndarray
    #: Q of the N-th usable line: de Wolff's window for the capping count
    q_window: float
    #: the chance rate at the resolution: the share of the range inside some
    #: line's reversed window
    p0: float
    #: the pattern side; ``None`` without a pattern
    grid_tt: np.ndarray | None = None
    grid_y: np.ndarray | None = None
    grid_sigma: np.ndarray | None = None
    envelope: np.ndarray | None = None
    model: np.ndarray | None = None
    comp_tt: np.ndarray | None = None
    comp_fwhm: np.ndarray | None = None
    #: :func:`screen_for`'s answers, keyed by the lattice and the positions it
    #: was scored on: a candidate is screened once per run, however many
    #: consensus calls (streamed snapshots included) and its validation ask
    _memo: dict = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_peaks(cls, peaks: PeakList, *, q_match: np.ndarray | None = None,
                   k_sigma: float = MATCH_SIGMA,
                   resolution: float = RESOLUTION_FWHM,
                   data: PatternData | None = None,
                   instrument: Instrument | None = None,
                   window_lines: int = SCREEN_WINDOW_LINES,
                   two_theta_limits: tuple[float, float] | None = None,
                   p0_floor_deg: float = 0.0,
                   ) -> PatternScreen:
        """Screen the peak list's range, narrowed to ``two_theta_limits`` when
        the fit that follows covers less (``validate_by_lebail``'s own): a line
        the fit never reached is not one the pattern can be said to lack.

        ``p0_floor_deg`` floors the half-width the chance rate p₀ is counted
        in: an absence test reads the assumed bound, never a window the
        unmeasured shift does not justify (#951), so a list at 0.010° FWHM
        with a weak-line filter cannot refute a superstructure through a p₀ of
        0.03.  Default 0 is the resolution alone."""
        usable = peaks.usable()
        tt = np.array([p.two_theta for p in usable], dtype=np.float64)
        esd = np.array([p.two_theta_esd for p in usable], dtype=np.float64)
        fwhm = np.array([p.fwhm for p in usable], dtype=np.float64)
        eta = np.array([p.eta for p in usable], dtype=np.float64)
        area = np.array([p.intensity for p in usable], dtype=np.float64)
        q = np.array([p.q for p in usable], dtype=np.float64)
        match = (np.asarray(q_match, dtype=np.float64) if q_match is not None
                 else np.array([p.q_esd for p in usable], dtype=np.float64))
        lo, hi = float(peaks.two_theta_min), float(peaks.two_theta_max)
        if two_theta_limits is not None:
            lo, hi = max(lo, float(two_theta_limits[0])), min(hi, float(two_theta_limits[1]))
        n = min(window_lines, len(q))
        q_window = float(np.sort(q)[n - 1]) if n else 0.0
        half = np.maximum(np.maximum(resolution * fwhm, k_sigma * esd),
                          p0_floor_deg)
        p0 = _union_fraction(tt, half, lo, hi)
        out = cls(wavelength=float(peaks.wavelength), two_theta_min=lo,
                  two_theta_max=hi, k_sigma=k_sigma, resolution=resolution,
                  obs_tt=tt, obs_esd=esd, obs_fwhm=fwhm, obs_eta=eta,
                  obs_intensity=area, obs_q=q, q_match=match,
                  q_window=q_window, p0=p0)
        if data is not None and instrument is not None:
            out._add_pattern(data, instrument)
        return out

    def _add_pattern(self, data: PatternData, instrument: Instrument) -> None:
        from .peaks import _debiased_envelope

        mask = data.in_range_mask()
        tt_all, y_all, sig_all = data.tt(), data.y(), data.sig()
        mask &= (tt_all >= self.two_theta_min) & (tt_all <= self.two_theta_max)
        tt, y, sig = tt_all[mask], y_all[mask], sig_all[mask]
        if len(tt) < 16:
            return                       # no pattern to screen against
        env = _debiased_envelope(tt, y)
        lines = instrument.source.lines
        w0 = float(lines[0].weight.value)
        comp_tt, comp_fw, comp_eta, comp_area = ([self.obs_tt], [self.obs_fwhm],
                                                 [self.obs_eta], [self.obs_intensity])
        for line in lines[1:]:
            lam_i = float(line.wavelength.value)
            ratio = float(line.weight.value) / w0
            img = np.degrees(2.0 * np.arcsin(np.clip(
                lam_i / self.wavelength * np.sin(np.radians(self.obs_tt / 2.0)),
                -1.0, 1.0)))
            comp_tt.append(img)
            comp_fw.append(self.obs_fwhm)
            comp_eta.append(self.obs_eta)
            comp_area.append(self.obs_intensity * ratio)
        c_tt = np.concatenate(comp_tt)
        c_fw = np.concatenate(comp_fw)
        c_eta = np.concatenate(comp_eta)
        c_area = np.concatenate(comp_area)
        model = np.array(env, dtype=np.float64, copy=True)
        for c, fw, eta, area in zip(c_tt, c_fw, c_eta, c_area):
            if fw <= 0.0 or area <= 0.0:
                continue
            m = np.abs(tt - c) < 25.0 * fw
            if np.any(m):
                model[m] += area * _pseudo_voigt(tt[m] - c, fw, eta)
        self.grid_tt, self.grid_y, self.grid_sigma = tt, y, sig
        self.envelope, self.model = env, model
        self.comp_tt, self.comp_fwhm = c_tt, c_fw

    @property
    def has_pattern(self) -> bool:
        return self.grid_tt is not None

    def fwhm_at(self, two_theta: np.ndarray) -> np.ndarray:
        """The measured width law, interpolated between the usable lines."""
        order = np.argsort(self.obs_tt)
        return np.interp(np.asarray(two_theta, dtype=np.float64),
                         self.obs_tt[order], self.obs_fwhm[order])

    def half_width_at(self, two_theta: np.ndarray) -> np.ndarray:
        """The reversed half-width at these positions against the nearest line."""
        pos = np.asarray(two_theta, dtype=np.float64)
        if not len(pos) or not len(self.obs_tt):
            return np.zeros(len(pos))
        j = np.argmin(np.abs(pos[:, None] - self.obs_tt[None, :]), axis=1)
        return resolution_half_width(self.fwhm_at(pos), self.obs_fwhm[j],
                                     self.obs_esd[j], k_sigma=self.k_sigma,
                                     resolution=self.resolution)


def _union_fraction(centres: np.ndarray, half: np.ndarray, lo: float,
                    hi: float) -> float:
    """The share of ``[lo, hi]`` inside the union of ``centres ± half``."""
    if not hi > lo or not len(centres):
        return 0.0
    a = np.clip(centres - half, lo, hi)
    b = np.clip(centres + half, lo, hi)
    order = np.argsort(a, kind="stable")
    covered, run_lo, run_hi = 0.0, None, None
    for x, y in zip(a[order], b[order]):
        if run_hi is None or x > run_hi:
            if run_hi is not None:
                covered += run_hi - run_lo
            run_lo, run_hi = x, y
        else:
            run_hi = max(run_hi, y)
    if run_hi is not None:
        covered += run_hi - run_lo
    return float(covered / (hi - lo))


@dataclass
class LineScreen:
    """What the screen measured for one candidate.

    Lines are **merged** predicted positions at the resolution, shifted by the
    candidate's common shift; one representative hkl per line.  ``indexed``
    is per usable observed line.  ``testable`` and ``absent`` are ``None``
    without a pattern.
    """

    cell: tuple[float, ...]
    system: str
    centring: str
    two_theta: np.ndarray
    hkl: np.ndarray
    uncancellable: np.ndarray
    seen: np.ndarray
    in_window: np.ndarray
    indexed: np.ndarray
    shift_deg: float
    n_raw: int
    testable: np.ndarray | None = None
    absent: np.ndarray | None = None

    @property
    def n_lines(self) -> int:
        return len(self.two_theta)

    @property
    def n_lines_in_window(self) -> int:
        return int(self.in_window.sum())

    @property
    def seen_fraction(self) -> float:
        return float(np.mean(self.seen)) if len(self.seen) else 0.0

    @property
    def n_absent(self) -> int | None:
        return None if self.absent is None else int(self.absent.sum())

    @property
    def n_absent_uncancellable(self) -> int | None:
        if self.absent is None:
            return None
        return int((self.absent & self.uncancellable).sum())

    @property
    def n_absent_uncancellable_in_window(self) -> int | None:
        if self.absent is None:
            return None
        return int((self.absent & self.uncancellable & self.in_window).sum())

    @property
    def absent_two_theta(self) -> list[float]:
        if self.absent is None:
            return []
        return [float(v) for v in self.two_theta[self.absent]]


def screen_candidate(pattern: PatternScreen, cell: tuple[float, ...],
                     system: str, centring: str, *,
                     q_obs: np.ndarray | None = None,
                     two_theta_obs: np.ndarray | None = None,
                     absence: bool = True) -> LineScreen:
    """Screen one candidate lattice against the pattern's facts.

    ``q_obs``/``two_theta_obs`` are the positions the candidate is scored on
    (``engines.scored_positions``: corrected by its own declared shift), in
    the pattern's line order; the raw positions by default.

    Steps, each candidate-free in its inputs: enumerate the lattice's positions
    in the range (``fom.lattice_reflections``) and flag each as uncancellable
    (:func:`~rietx.indexing.ambiguity.uncancellable`); match the observed
    lines in the **search** window and take the common shift; merge positions
    closer than the resolution; ask *seen* at the resolution; with a pattern,
    ask *testable* (resolved from every component by the Pawley overlap rule
    and quiet in the peak-list model) and *absent* (nothing above the envelope
    at the measured width, :func:`~rietx.indexing.workflow.absent_mask`).
    ``absence=False`` skips that last, grid-wide step and leaves ``testable``
    and ``absent`` ``None``: the containment refuter reads only ``seen``,
    ``indexed`` and ``uncancellable``.
    """
    from .extinction import _model_is_quiet, testable_mask
    from .workflow import ABSENT_SIGMA, absent_mask

    cell = tuple(float(v) for v in cell)
    obs_q = pattern.obs_q if q_obs is None else np.asarray(q_obs, dtype=np.float64)
    obs_tt = (pattern.obs_tt if two_theta_obs is None
              else np.asarray(two_theta_obs, dtype=np.float64))
    hkl, q, _m = lattice_reflections(cell, system, centring, pattern.wavelength,
                                     pattern.two_theta_max,
                                     two_theta_min=pattern.two_theta_min)
    empty = LineScreen(cell=cell, system=system, centring=centring,
                       two_theta=np.zeros(0), hkl=np.zeros((0, 3), dtype=np.int64),
                       uncancellable=np.zeros(0, dtype=bool),
                       seen=np.zeros(0, dtype=bool),
                       in_window=np.zeros(0, dtype=bool),
                       indexed=np.zeros(len(obs_q), dtype=bool),
                       shift_deg=0.0, n_raw=0)
    if not len(q):
        return empty
    # exact coincidences (333/511 in a cubic cell) are one line; keep one hkl
    distinct = np.ones(len(q), dtype=bool)
    distinct[1:] = np.diff(q) > LINE_COINCIDENCE_RTOL * q[1:]
    free_all = uncancellable(cell, centring, hkl)
    # a coincident group is uncancellable if any member is
    group_id = np.cumsum(distinct) - 1
    free = np.zeros(int(group_id[-1]) + 1, dtype=bool)
    np.logical_or.at(free, group_id, free_all)
    hkl, q = hkl[distinct], q[distinct]
    tt = two_theta_of_q(q, pattern.wavelength)
    keep = (tt >= pattern.two_theta_min) & (tt <= pattern.two_theta_max)
    hkl, q, tt, free = hkl[keep], q[keep], tt[keep], free[keep]
    if not len(q):
        return empty
    # forward, in the search window: which observed lines the cell indexes,
    # and the common shift those matches imply
    idx, _gap = match_lines(obs_q, pattern.q_match, q, k_sigma=pattern.k_sigma)
    indexed = idx >= 0
    shift = common_shift(obs_tt, tt, idx)
    # merge at the resolution, then shift
    fw = pattern.fwhm_at(tt)
    groups = merge_at_resolution(tt, fw, resolution=pattern.resolution)
    m_tt = np.array([float(np.mean(tt[g])) for g in groups]) + shift
    m_hkl = np.array([hkl[g[0]] for g in groups], dtype=np.int64)
    m_free = np.array([bool(np.any(free[g])) for g in groups])
    m_q = np.array([float(np.min(q[g])) for g in groups])
    m_fw = pattern.fwhm_at(m_tt)
    seen, _j = seen_at_resolution(m_tt, m_fw, obs_tt, pattern.obs_fwhm,
                                  pattern.obs_esd, k_sigma=pattern.k_sigma,
                                  resolution=pattern.resolution)
    in_window = m_q <= pattern.q_window * (1.0 + 1e-6)
    out = LineScreen(cell=cell, system=system, centring=centring, two_theta=m_tt,
                     hkl=m_hkl, uncancellable=m_free, seen=seen,
                     in_window=in_window, indexed=indexed, shift_deg=shift,
                     n_raw=int(len(tt)))
    if pattern.has_pattern and absence:
        testable = testable_mask(m_tt, pattern.comp_tt, m_fw, pattern.comp_fwhm,
                                 pattern.grid_tt)
        quiet = _model_is_quiet(pattern.grid_tt, pattern.model, pattern.envelope,
                                pattern.grid_sigma, m_tt, m_fw, k_sigma=ABSENT_SIGMA)
        # paired with the merged lines by index, never by position
        nothing, _ratio = absent_mask(pattern.grid_tt, pattern.grid_y,
                                      pattern.envelope, pattern.grid_sigma,
                                      m_tt, m_fw, k_sigma=ABSENT_SIGMA)
        out.testable = testable & quiet
        out.absent = out.testable & nothing
    return out


def screen_for(pattern: PatternScreen, candidate, peaks: PeakList, *,
               absence: bool = True) -> LineScreen:
    """:func:`screen_candidate` on a :class:`~rietx.schemas.indexing.CellCandidate`,
    scored on its own shift-corrected lines (``engines.scored_positions``).

    Answered once per lattice and positions on this ``pattern``: a screen
    with the absence step answers a later request without it, and one
    without is recomputed only when the absences are asked for."""
    from .engines import scored_positions

    q, tt = scored_positions(peaks, candidate)
    q = np.asarray(q, dtype=np.float64)
    tt = np.asarray(tt, dtype=np.float64)
    key = (tuple(float(v) for v in candidate.cell), candidate.system,
           candidate.centring, q.tobytes(), tt.tobytes())
    hit = pattern._memo.get(key)
    if hit is not None and (hit.absent is not None or not absence
                            or not pattern.has_pattern):
        return hit
    out = screen_candidate(pattern, candidate.cell, candidate.system,
                           candidate.centring, q_obs=q, two_theta_obs=tt,
                           absence=absence)
    pattern._memo[key] = out
    return out


def contains(child: LineScreen, parent: LineScreen) -> bool:
    """Does ``child`` index every observed line ``parent`` indexes, and is it
    the denser description?

    Containment of the indexed set is the relation (F1 § 3.3).  The density
    direction is what makes it an order: two descriptions of one lattice
    contain each other, and without a direction a true cell whose weak
    uncancellable lines the picker missed could be refuted against a wrong
    cell that happens to index the same lines.  The denser line set is the
    child, the sparser the parent; at equal density the larger primitive
    volume is the child.  Every pair measured in #941's Acceptance table has the denser
    cell as the one to refute.  The last comparison is **strict**: two cells with
    equal line counts and equal volume contain neither each other nor
    themselves, so the relation stays antisymmetric and
    ``consensus.below_refuting_parents``'s "a parent is strictly smaller than
    its child" holds without a tiebreak.

    The relation chooses which pairs are asked. It does not decide the
    verdict. On a dense low-symmetry pattern the density order can make a true
    cell the child of a wrong one, whose lines merge into fewer resolved
    positions. The verdict never refutes a child seen more often than its
    parent (#1230).
    """
    if len(child.indexed) != len(parent.indexed):
        return False
    if not bool(np.all(child.indexed[parent.indexed])):
        return False
    if child.n_lines != parent.n_lines:
        return child.n_lines > parent.n_lines
    return _primitive_volume(child) > _primitive_volume(parent)


_LATTICE_POINTS = {"P": 1, "A": 2, "B": 2, "C": 2, "I": 2, "F": 4, "R": 3}


def _primitive_volume(screen: LineScreen) -> float:
    from ..crystallography.lattice import cell_volume

    return float(cell_volume(*screen.cell)) / _LATTICE_POINTS.get(screen.centring, 1)


def containment_evidence(pattern: PatternScreen, child: LineScreen,
                         parent: LineScreen) -> SupercellEvidence | None:
    """Are the lines ``child`` adds over ``parent`` seen more often than chance?

    ``None`` unless :func:`contains` holds.  The extras are the child's
    **uncancellable** merged lines farther than the resolution from every
    parent line; *seen* is the screen's; *unexplained* means the observed line
    the extra sits on is one the parent does not index; p₀ is the pattern's
    chance rate at the resolution.  The verdict is
    :meth:`~rietx.indexing.ambiguity.SupercellEvidence.verdict`'s three bands.
    ``index`` is the sublattice index where the parent is a true sublattice
    of the child (index 2–4), else 0 with ``relation="containment"``.
    Both cells' own seen fractions ride along, and a child seen more often
    than its parent is never refuted (#1230).
    """
    from scipy.stats import binom

    from .ambiguity import _parent_coordinates

    if not contains(child, parent):
        return None
    cpos, ppos = child.two_theta, parent.two_theta
    if len(ppos):
        gap = np.min(np.abs(cpos[:, None] - ppos[None, :]), axis=1)
        far = gap > pattern.half_width_at(cpos)
    else:
        far = np.ones(len(cpos), dtype=bool)
    extra = child.uncancellable & far
    seen = child.seen & extra
    # the observed line each seen extra sits on: unexplained if the parent
    # does not index it
    obs_tt = pattern.obs_tt
    if len(obs_tt):
        j = np.argmin(np.abs(cpos[:, None] - obs_tt[None, :]), axis=1)
        alone = seen & ~parent.indexed[j]
    else:
        alone = np.zeros(len(cpos), dtype=bool)
    n = int(extra.sum())
    k, k_un = int(seen.sum()), int(alone.sum())
    p0 = min(max(pattern.p0, 0.0), 1.0)

    def tail(count: int) -> float:
        return 1.0 if n == 0 else float(binom.sf(count - 1, n, p0))

    frame = _parent_coordinates(tuple(parent.cell), parent.centring,
                                tuple(child.cell), child.centring)
    index = 0 if frame is None else int(frame[1])
    q_extra = q_of_two_theta(cpos[extra], pattern.wavelength)
    return SupercellEvidence(
        index=index,
        extra_hkl=tuple(tuple(int(v) for v in row) for row in child.hkl[extra]),
        extra_q=tuple(float(v) for v in q_extra),
        extra_seen=tuple(bool(v) for v in seen[extra]),
        p0=p0, p_value=tail(k),
        extra_seen_unexplained=tuple(bool(v) for v in alone[extra]),
        p_value_unexplained=tail(k_un),
        relation="containment" if index == 0 else "sublattice",
        child_seen_fraction=child.seen_fraction,
        parent_seen_fraction=parent.seen_fraction)


__all__ = ["SCREEN_WINDOW_LINES", "LineScreen", "PatternScreen",
           "containment_evidence", "contains", "screen_candidate", "screen_for"]
