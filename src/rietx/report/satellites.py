"""The satellite arm of the unexplained-intensity report (WP-1326).

The package already tells a user that the intensity its model puts nowhere
*might* be magnetic — it is one of the causes ``HARMONIC_FRACTION`` names, and
the manual repeats it in ``reference/refinement.md``.  Until this arm there was no
way to test that.  Here it is, and it costs the user nothing they do not
already have: **a satellite is a position**, so the test needs a cell, a
symmetry and a wavelength, and no moment, no magnetic form factor and no
magnetic symmetry at all.

What it does is score an **enumerated** candidate set — never a search.  For
each candidate k it generates the satellite positions at Q = H ± k
(:mod:`rietx.crystallography.satellites`) and counts how many of Layer 0's
unexplained observed peaks land inside the report's own
:data:`~rietx.report.schemas.VALIDITY_RADIUS_FWHM` of one.  It returns the
whole ranked list and never a singleton, which is the indexing rule one
subject over: the arm tests a fixed candidate set against a cell the user
already has, and it does not index (WP-1018-1027 fence that).

**A good pattern can score nothing, and the arm says why.**  An incommensurate
k is outside the candidate set by construction; so is any commensurate k the
generator does not list.  The generator is a **parameter** (issue #257 A1) —
:func:`~rietx.crystallography.satellites.zone_boundary_candidates` is the
default WP-1326 fixes, and a successor that scans the special points and lines
of the Brillouin zone drops in here without touching the arm.

**Three places a residual peak can be, and the arm sorts them before it
ranks anything.**  It does the split itself, from the positive residual peaks
and the tick list, so that *one* radius — the validity radius — decides both
halves.  Reusing Layer 0's ``unmatched_obs`` list instead would apply its
tighter ``match_tol_deg`` to the tick test and the wider validity radius to the
satellite test, and a peak 0.10° from a nuclear line would be called
unexplained and then "indexed" by a candidate whose satellite sits 0.14° away.

1. **On a calculated line.**  A nuclear misfit, or a k = 0 magnetic structure
   whose intensity coincides with the nuclear lines: a Le Bail extraction
   absorbs the latter into the nuclear intensities, so the two look alike here
   and this route cannot separate them.  What does is a pattern of the same
   specimen above its ordering temperature (WP-1329).
2. **On a reciprocal-lattice point the assumed group forbids.**  A glide or
   screw absence is a condition on the nuclear structure factor *of the space
   group the fit assumed*, so the fit's model cannot put intensity there — but
   four causes can, and the arm has no evidence that separates them: a true
   nuclear group lacking that glide or screw (the assumed group is too high),
   λ/2 contamination from the monochromator, an impurity line that lands on
   the point, and a k = 0 magnetic structure.  The last is possible because a
   magnetic structure factor is an axial vector, transformed by the same
   operation's rotation and any time reversal, so its absence rule for one
   glide or screw can be the *complement* of the nuclear one (Gallego, S. V.,
   Tasci, E. S., de la Flor, G., Perez-Mato, J. M. & Aroyo, M. I. (2012).
   *J. Appl. Cryst.* **45**, 1236, § 4.1.1 on Pn′ma′ and § 4.3.2 on
   P4₂/mnm).  The note names all four and reads none of them as the answer;
   on an X-ray histogram it names the first three only, since X-rays see no
   magnetic order.  What it does settle is that these peaks need no k, so
   they are not handed to the ranking.  It is what the Cr₂WO₆ 4 K pattern
   shows (:func:`~rietx.crystallography.satellites.lattice_two_theta`).
3. **Neither.**  Only these are scored against the candidate k, because only
   these need one.

**One position inside the third is named, and not removed.**  A residual
peak on an integer (h k l) that the lattice's *centring* forbids — mixed
parity on F, h + k + l odd on I — is in neither of the first two lists:
``lattice_two_theta`` applies the centring, so the point is not a
reciprocal-lattice vector at all.  It stays in the third list and is scored
like any other peak, but the note says how many sit there, from how many
such positions in range, and names the strongest with its (h k l) and its
height in σ, because a model of that lattice with no propagation vector
cannot put intensity there.  Measured on the GSAS-II *Magnetic-IV*
(Pr,Sr)MnO₃ pattern (F m m m, issue #795): the strongest residual peak sits
on the forbidden (1 0 0), and the note said nothing about it.

And one sentence about the radiation, which is read off the compiled phase's
own amplitude — a bound coherent scattering length means neutrons — rather than
assumed: **on an X-ray histogram** the positions of a superstructure reflection
and of a magnetic satellite are the same and the inference is not.

References
----------
Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; satellite
generation from a propagation vector, and the ±k rule the enumeration obeys.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from ..crystallography.lattice import d_spacings, two_theta_deg
from ..crystallography.representation.irreps import star
from ..crystallography.satellites import (
    KCandidate,
    check_candidate_denominators,
    lattice_two_theta,
    minus_k_is_k,
    reciprocal_lattice_mask,
    satellite_d_spacings,
    zone_boundary_candidates,
)
from ..crystallography.symmetry import resolve_group
from .schemas import VALIDITY_RADIUS_FWHM, SatelliteCandidate, SatelliteEvidence

#: Fallback peak FWHM in degrees 2θ when the phase put no modelled peak in
#: range to read one from.  Only the *radius* of the position match depends on
#: it, and a phase with no peaks in range scores nothing anyway; it exists so
#: the arm cannot divide by an empty array.
_FWHM_FALLBACK_DEG = 0.2


def _peak_widths(model, values) -> tuple[np.ndarray, np.ndarray]:
    """(positions, FWHM) of every modelled peak of every phase, deg 2θ.

    Read from :meth:`~rietx.model.forward.CompiledModel.phase_peaks`, so the
    radius the arm matches within is **the width the fit actually drew** at
    that angle rather than an instrument estimate that ignores the specimen's
    own broadening.
    """
    pos: list[np.ndarray] = []
    fwhm: list[np.ndarray] = []
    for ip in range(len(model.phases)):
        for p, w1, w2, _i in model.phase_peaks(ip, values):
            p = np.asarray(p, dtype=np.float64)
            good = np.isfinite(p)
            pos.append(p[good])
            fwhm.append(np.asarray(model.peak_fwhm(w1, w2),
                                   dtype=np.float64)[good])
    if not pos:
        return np.zeros(0), np.zeros(0)
    return np.concatenate(pos), np.concatenate(fwhm)


def _radius(tt: np.ndarray, pos: np.ndarray, fwhm: np.ndarray) -> np.ndarray:
    """The validity radius at each 2θ — VALIDITY_RADIUS_FWHM × the local FWHM."""
    if len(pos) == 0:
        local = np.full(len(tt), _FWHM_FALLBACK_DEG)
    else:
        nearest = np.argmin(np.abs(tt[:, None] - pos[None, :]), axis=1)
        local = fwhm[nearest]
    return VALIDITY_RADIUS_FWHM * local


def _satellite_positions(model, values, ip: int, ks) -> list[np.ndarray]:
    """Every emission line's apparent 2θ for the satellites of each k in ``ks``.

    Generated at the *current* cell, over the window ``compile_model``
    generates over (:meth:`~rietx.model.forward.CompiledModel.generation_window`,
    WP-2034), and placed by the
    same ``CompiledModel.apparent_two_theta`` the tick list uses (zero and the
    geometry's own shift, WP-1908), so a position here is comparable with a
    peak found in the residual.  One parent grid serves every candidate
    (:func:`~rietx.crystallography.satellites.satellite_d_spacings`), so the
    arm enumerates the reciprocal lattice once per phase rather than once per
    candidate (review item 4 on #468), and each list is bit-identical to what
    a per-candidate ``satellite_reflections`` call gave.
    """
    cp = model.phases[ip]
    cell = tuple(values[f"phases.{ip}.cell.{key}"]
                 for key in ("a", "b", "c", "alpha", "beta", "gamma"))
    lams = [float(v) for v in model.line_lambdas(values)]
    lo, hi = model.generation_window(values)
    if hi <= lo:
        return [np.zeros(0) for _ in ks]
    ds = satellite_d_spacings(
        resolve_group(cp.reflections.spacegroup, cp.reflections.operations),
        cell, min(lams), hi, ks, two_theta_min=lo)
    positions: list[np.ndarray] = []
    for d in ds:
        out: list[np.ndarray] = []
        for lam in lams:
            tt = model.apparent_two_theta(
                np.asarray(two_theta_deg(d, lam), dtype=np.float64), values)
            tt = tt[np.isfinite(tt)]
            out.append(tt[(tt >= model.tt_min) & (tt <= model.tt_max)])
        positions.append(np.concatenate(out) if out else np.zeros(0))
    return positions


def _score(candidate: KCandidate, positions: np.ndarray, sg,
           peaks: np.ndarray, radius: np.ndarray) -> SatelliteCandidate:
    matched = 0
    worst: float | None = None
    if len(positions) and len(peaks):
        delta = np.min(np.abs(peaks[:, None] - positions[None, :]), axis=1)
        hit = delta <= radius
        matched = int(hit.sum())
        if matched:
            worst = float(delta[hit].max())
    return SatelliteCandidate(
        k=[str(c) for c in candidate.k],
        name=candidate.name, vector=candidate.vector, cdml=candidate.cdml,
        n_satellites=int(len(positions)),
        star_size=len(star(sg, candidate.k)),
        minus_k_distinct=not minus_k_is_k(sg, candidate.k),
        matched=matched,
        matched_fraction=(matched / len(peaks)) if len(peaks) else 0.0,
        worst_offset_deg=worst,
    )


def _num(n: int) -> str:
    return {3: "three", 4: "four"}.get(n, str(n))


class _CentringForbidden(NamedTuple):
    """Unexplained peaks on centring-forbidden integer (h k l), for the note."""

    count: int            # unexplained peaks within the radius of one
    n_positions: int      # such positions in the fitted range
    centring: str         # the lattice letter, "F", "I", "C", …
    two_theta: float      # the named peak
    hkl: tuple[int, int, int]
    height: float | None  # its Δ/σ; None when the caller passed no heights
    half_order: bool      # 2·hkl is allowed by the group (λ/2 can put a line there)


def _centring_sentence(f: _CentringForbidden, radiation: str) -> str:
    h, k, l = f.hkl  # noqa: E741 — Miller indices
    which = (f"the strongest, {f.height:.1f}σ at {f.two_theta:.3f}°"
             if f.height is not None
             else f"the lowest-angle, at {f.two_theta:.3f}°")
    causes = [f"a true lattice less centred than {f.centring} (a "
              "superstructure the centring forbids)"]
    if f.half_order:
        causes.append(f"λ/2 contamination from the ({2 * h} {2 * k} {2 * l}) "
                      "line")
    causes.append("an impurity line that lands on the position")
    if radiation == "neutron":
        causes.append(f"a magnetic structure whose propagation vector is a "
                      f"centring-forbidden integer vector, such as "
                      f"({h} {k} {l}) itself")
    return (f"{f.count} of them sit within the validity radius of an integer "
            f"(h k l) that the {f.centring} centring forbids, from "
            f"{f.n_positions} such position(s) in range; {which}, is at "
            f"({h} {k} {l}), where a model of this lattice with no "
            "propagation vector cannot put intensity, and the arm cannot "
            f"separate {_num(len(causes))} causes that can — "
            + ", ".join(causes[:-1]) + ", or " + causes[-1])


def _note(evidence: SatelliteEvidence,
          forbidden: _CentringForbidden | None = None) -> str:
    parts: list[str] = []
    if evidence.excess_on_absent_lattice_lines:
        causes = [
            "a true nuclear group lacking that glide or screw (the assumed "
            "group is too high)",
            "λ/2 contamination from the monochromator",
            "an impurity line that lands on the point"]
        if evidence.radiation == "neutron":
            causes.append(
                "a k = 0 magnetic structure, whose magnetic structure factor "
                "can obey the complementary absence rule for the same "
                "operation (Gallego et al. 2012, J. Appl. Cryst. 45, 1236)")
        parts.append(
            f"{evidence.excess_on_absent_lattice_lines} residual peak(s) sit "
            "on reciprocal-lattice points that a glide or screw absence of the "
            "assumed space group forbids, so the fitted model cannot put "
            "intensity there; the arm cannot separate "
            f"{_num(len(causes))} causes that can — " + ", ".join(causes[:-1])
            + ", or " + causes[-1])
    if evidence.n_unexplained == 0:
        if evidence.excess_on_nuclear_lines:
            parts.append(
                f"the rest of the excess sits on nuclear lines "
                f"({evidence.excess_on_nuclear_lines} residual peak(s) inside "
                "the validity radius of a calculated reflection, none outside "
                "it); a k = 0 structure and a nuclear misfit look alike here, "
                "and a pattern of the same specimen above its ordering "
                "temperature separates them")
        elif not evidence.excess_on_absent_lattice_lines:
            parts.append("no unexplained peak in the residual — nothing to "
                         "index as a satellite")
        parts.append("no candidate was scored: nothing is left over for a "
                     "satellite to explain")
    else:
        best = evidence.candidates[0] if evidence.candidates else None
        if best is None or best.matched == 0:
            parts.append(
                f"{evidence.n_unexplained} peak(s) sit at neither, and no "
                "candidate in the enumerated set puts a satellite on any of "
                "them")
        else:
            # the comparison that judges the top row rides with it: the count
            # has no chance baseline, so a best named without the positions it
            # had to land on and without the runner-up is a confident singleton
            # (root CLAUDE.md; review item 2 on #468)
            parts.append(
                f"{evidence.n_unexplained} peak(s) sit at neither; the best "
                f"candidate {best.vector} indexes {best.matched} of them "
                f"(worst offset {best.worst_offset_deg:.3f}°) from "
                f"{best.n_satellites} satellite position(s) in range")
            runner = (evidence.candidates[1]
                      if len(evidence.candidates) > 1 else None)
            if runner is None:
                parts.append("there is no runner-up to compare it with")
            elif runner.matched == best.matched:
                parts.append(
                    f"the runner-up {runner.vector} also indexes "
                    f"{runner.matched} (from {runner.n_satellites}), a tie the "
                    "ranking breaks only on the offset and the name, so it "
                    "chooses nothing")
            else:
                parts.append(
                    f"the runner-up {runner.vector} indexes {runner.matched} "
                    f"(from {runner.n_satellites}); the count has no chance "
                    "baseline, so a k with more positions matches more by "
                    "being everywhere")
        if forbidden is not None:
            parts.append(_centring_sentence(forbidden, evidence.radiation))
        if evidence.excess_on_nuclear_lines:
            parts.append(
                f"a further {evidence.excess_on_nuclear_lines} residual "
                "peak(s) sit on nuclear lines, where a k = 0 structure and a "
                "nuclear misfit look alike")
    parts.append(
        "the candidate set is enumerated, not searched: an incommensurate k "
        "is outside it by construction, so a good pattern can score nothing")
    if evidence.radiation != "neutron":
        parts.append(
            "this is an X-ray histogram — intensity at G ± k is a "
            "superstructure reflection, not magnetism; the positions are the "
            "same and the inference is not")
    return "; ".join(parts)


def _lattice_positions(model, values, ip: int) -> np.ndarray:
    """The phase's reciprocal-lattice positions in range, apparent 2θ."""
    cp = model.phases[ip]
    cell = tuple(values[f"phases.{ip}.cell.{key}"]
                 for key in ("a", "b", "c", "alpha", "beta", "gamma"))
    lams = [float(v) for v in model.line_lambdas(values)]
    lo, hi = model.generation_window(values)
    if hi <= lo:
        return np.zeros(0)
    ref = lattice_two_theta(
        resolve_group(cp.reflections.spacegroup, cp.reflections.operations),
        cell, min(lams), hi, two_theta_min=lo)
    if len(ref) == 0:
        return np.zeros(0)
    # ``lattice_two_theta`` works at one λ; re-derive d and place it on each
    # line, exactly as ``_satellite_positions`` does
    d = min(lams) / (2.0 * np.sin(np.radians(ref / 2.0)))
    out = []
    for lam in lams:
        s = lam / (2.0 * d)
        tt = model.apparent_two_theta(
            np.degrees(2.0 * np.arcsin(np.clip(s, -1.0, 1.0))), values)
        out.append(tt[(tt >= model.tt_min) & (tt <= model.tt_max)])
    return np.concatenate(out) if out else np.zeros(0)


def _centring_forbidden_positions(model, values, ip: int, sg
                                  ) -> tuple[np.ndarray, np.ndarray]:
    """(apparent 2θ, hkl) of every integer hkl in range the centring forbids.

    The complement, on the integer grid, of what :func:`_lattice_positions`
    generates: an hkl failing
    :func:`~rietx.crystallography.satellites.reciprocal_lattice_mask`.  Empty
    on a primitive lattice, where every integer hkl is a lattice vector.  The
    grid has :func:`~rietx.crystallography.satellites.lattice_two_theta`'s
    bounds, which that call has already held to its size limit; each row of
    the hkl array pairs with the position at the same index, one row per
    emission line.
    """
    if len(sg.operations().cen_ops) == 1:
        return np.zeros(0), np.zeros((0, 3), dtype=np.int64)
    cell = tuple(values[f"phases.{ip}.cell.{key}"]
                 for key in ("a", "b", "c", "alpha", "beta", "gamma"))
    lams = [float(v) for v in model.line_lambdas(values)]
    lo, hi = model.generation_window(values)
    if hi <= lo:
        return np.zeros(0), np.zeros((0, 3), dtype=np.int64)
    # both bounds in the λ_min frame the window is returned in
    d_min = min(lams) / (2.0 * np.sin(np.radians(hi / 2.0)))
    d_max = min(lams) / (2.0 * np.sin(np.radians(lo / 2.0)))
    bounds = [int(np.floor(cell[i] / d_min)) + 1 for i in range(3)]
    grids = np.meshgrid(*[np.arange(-b, b + 1) for b in bounds], indexing="ij")
    hkl = np.column_stack([g.ravel() for g in grids]).astype(np.int64)
    hkl = hkl[~reciprocal_lattice_mask(sg, hkl)]
    d = d_spacings(hkl, *cell)
    keep = (d >= d_min * 0.999) & (d <= d_max * 1.001)
    hkl, d = hkl[keep], d[keep]
    tts: list[np.ndarray] = []
    rows: list[np.ndarray] = []
    for lam in lams:
        tt = np.asarray(model.apparent_two_theta(
            np.asarray(two_theta_deg(d, lam), dtype=np.float64), values))
        good = np.isfinite(tt) & (tt >= model.tt_min) & (tt <= model.tt_max)
        tts.append(tt[good])
        rows.append(hkl[good])
    return np.concatenate(tts), np.concatenate(rows)


def _centring_finding(model, values, ip: int, sg, peaks: np.ndarray,
                      radius: np.ndarray, heights: np.ndarray | None
                      ) -> _CentringForbidden | None:
    """The unexplained peaks on centring-forbidden positions, or ``None``.

    ``peaks`` and ``radius`` are the arm's own third list and validity radius,
    so the test is the satellite test's: a peak within the radius of one.
    """
    if len(peaks) == 0:
        return None
    tt, hkl = _centring_forbidden_positions(model, values, ip, sg)
    if len(tt) == 0:
        return None
    delta = np.abs(peaks[:, None] - tt[None, :])
    on = np.min(delta, axis=1) <= radius
    if not on.any():
        return None
    idx = np.flatnonzero(on)
    pick = (int(idx[np.argmax(heights[idx])]) if heights is not None
            else int(idx[np.argmin(peaks[idx])]))
    # the nearest position names it; of several at one d (±h, a cubic
    # permutation), the largest tuple, so (1 0 0) rather than (0 0 -1)
    row = delta[pick]
    near = np.flatnonzero(row <= row.min() + 1e-9)
    label = max(tuple(int(v) for v in hkl[j]) for j in near)
    # λ/2 contamination is a nuclear reflection, so the group's whole
    # reflection condition applies (centring, glides, screws), not the
    # centring alone: (2 0 0) is extinct on F d -3 m (International Tables
    # for Crystallography, Vol. A, §2.2.13)
    half = not sg.operations().is_systematically_absent(
        [2 * v for v in label])
    return _CentringForbidden(
        count=int(on.sum()),
        n_positions=int(len(np.unique(np.round(tt, 6)))),
        centring=sg.centring_type(),
        two_theta=float(peaks[pick]), hkl=label,
        height=float(heights[pick]) if heights is not None else None,
        half_order=half)


def analyse_satellites(model, values, *, residual_two_theta, ticks,
                       structure=None,
                       generator=zone_boundary_candidates,
                       residual_height_over_sigma=None,
                       ) -> list[SatelliteEvidence]:
    """Sort the positive residual peaks, then rank the candidate k on the rest.

    ``residual_two_theta`` is **every** positive residual peak
    (:func:`~rietx.report.layer0.residual_peak_indices`, so the arm and Layer 0
    cannot disagree about what a peak is) and ``ticks`` the calculated tick
    positions.  The split into the three places a peak can be, and why the arm
    does it itself rather than reading Layer 0's ``unmatched_obs``, is in the
    module docstring.

    ``generator`` is the candidate set (issue #257 A1): any callable taking a
    space group and returning
    :class:`~rietx.crystallography.satellites.KCandidate`\\ s.  It is validated
    (:func:`~rietx.crystallography.satellites.check_candidate_denominators`)
    rather than trusted, because a caller wrote it.

    ``residual_height_over_sigma``, when given, is Δ/σ at each of
    ``residual_two_theta`` (same order and length).  It changes no count and no
    ranking: it only lets the note name the *strongest* unexplained peak on a
    centring-forbidden position (module docstring) rather than the
    lowest-angle one.
    """
    all_peaks = np.asarray(residual_two_theta, dtype=np.float64)
    all_heights = (None if residual_height_over_sigma is None
                   else np.asarray(residual_height_over_sigma,
                                   dtype=np.float64))
    if all_heights is not None and all_heights.shape != all_peaks.shape:
        raise ValueError(
            f"residual_height_over_sigma has {all_heights.size} value(s) for "
            f"{all_peaks.size} residual peak(s); pass one per peak, in the "
            "same order")
    tick = np.asarray(ticks, dtype=np.float64)
    pos, fwhm = _peak_widths(model, values)
    all_radius = (_radius(all_peaks, pos, fwhm) if len(all_peaks)
                  else np.zeros(0))

    out: list[SatelliteEvidence] = []
    for ip, cp in enumerate(model.phases):
        sg = resolve_group(cp.reflections.spacegroup, cp.reflections.operations)
        if len(all_peaks) == 0:
            on_tick = on_lattice = np.zeros(0, dtype=bool)
        else:
            on_tick = (np.min(np.abs(all_peaks[:, None] - tick[None, :]),
                              axis=1) <= all_radius
                       if len(tick) else np.zeros(len(all_peaks), dtype=bool))
            lattice = _lattice_positions(model, values, ip)
            on_lattice = (~on_tick & (np.min(
                np.abs(all_peaks[:, None] - lattice[None, :]), axis=1)
                <= all_radius) if len(lattice)
                else np.zeros(len(all_peaks), dtype=bool))
        left = ~(on_tick | on_lattice)
        peaks = all_peaks[left]
        radius = all_radius[left]
        candidates = tuple(generator(sg))
        check_candidate_denominators(candidates)
        if len(peaks):
            positions = _satellite_positions(model, values, ip,
                                             [c.k for c in candidates])
            scored = [_score(c, pos_c, sg, peaks, radius)
                      for c, pos_c in zip(candidates, positions, strict=True)]
        else:
            scored = []
        # ranked, and published whole: the top row is a hypothesis worth
        # testing, never an answer (root CLAUDE.md, "never a confident wrong
        # singleton").  Ties break on the tighter fit and then on the name, so
        # the order is deterministic.
        scored.sort(key=lambda c: (-c.matched,
                                   c.worst_offset_deg
                                   if c.worst_offset_deg is not None else 1e9,
                                   c.name))
        declared = None
        if structure is not None and ip < len(structure.phases):
            k = structure.phases[ip].propagation_vector
            declared = list(k) if k is not None else None
        evidence = SatelliteEvidence(
            phase_index=ip,
            radiation="neutron" if cp.sites.b_coh is not None else "xray",
            n_residual_peaks=int(len(all_peaks)),
            n_unexplained=int(len(peaks)),
            excess_on_nuclear_lines=int(on_tick.sum()),
            excess_on_absent_lattice_lines=int(on_lattice.sum()),
            declared_k=declared,
            generator=getattr(generator, "__name__", str(generator)),
            candidates=scored,
        )
        evidence.note = _note(evidence, _centring_finding(
            model, values, ip, sg, peaks, radius,
            None if all_heights is None else all_heights[left]))
        out.append(evidence)
    return out
