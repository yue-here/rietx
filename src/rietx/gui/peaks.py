"""``peaks.json`` and the editing engine behind the GUI's peak verbs (WP-1027).

Peak picking is the one step where a human eye genuinely beats the algorithm: a
shoulder the fitter missed is obvious on screen and invisible in a number.  This
module is what makes that correction *cheap* — every verb refits exactly one
group, through the same solver the picker used, and splices the result into the
stored list.

**The stored list is the authority.**  A peak list is a project artifact
(WP-1005's ``.rex/`` container, ``peaks.json``), keyed by ``data_fingerprint``
so it can never be displayed against the wrong pattern — the device
``TreeHeader.data_fingerprint`` already uses for history trees.  It is *not* a
history node: peaks are measurements about the pattern, not model state, and
they survive a ``checkout`` unchanged.

**An edit is surgical, and what it may touch is the rule.**  Refitting group
``g`` recomputes that group's components, their fitter-owned flags
(:func:`~rietx.indexing.pick.peaks_of_group` — the same translation the
picker used, never a second reading) and their ghost marks
(:func:`~rietx.indexing.pick.flag_ghosts` with ``only=`` the new indices, so
recomputing cannot resurrect a mark a user cleared on an untouched peak).
Everything a *human* decided — an ``excluded`` flag, an ``origin`` — is carried
across the refit by component identity, because a fitter must not overrule the
person correcting it.  Peaks in other groups are not touched at all.

**What ``peaks.json`` stores beyond the list** is exactly what re-editing
needs and the flattened list has lost: per group, the fitted width pair
(``gamma_g``/``gamma_l`` — the combined ``fwhm``/``eta`` on each peak cannot be
inverted back to them), the frozen window bounds in 2θ, and ``from_reseed``
(which components were a residual's proposal rather than a detection — the
provenance :func:`~rietx.indexing.pick._not_separable` needs, known only at
fit time).  The :class:`~rietx.indexing.peaks.Detection` itself is *not*
stored: it is deterministic in (data, instrument, range) and rebuilt lazily.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args

import numpy as np

from ..indexing.diagnostics import peak_diagnostics
from ..indexing.peakfit import GroupFit, fit_group, fit_group_at, group_profile
from ..indexing.peaks import Detection, PeakGroup, detect_peaks, predicted_fwhm
from ..indexing.pick import (
    flag_ghosts,
    flag_kalpha2_residuals,
    peaks_of_group,
    pick_peaks_with_state,
)
from ..model.profiles.fcj import fcj_extent_deg
from ..schemas.indexing import (
    PEAK_UNUSABLE_FLAGS,
    PEAK_WINDOW_FWHM_MULT,
    ObservedPeak,
    PeakFlag,
    PeakList,
)
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData

PEAKS_FILE = "peaks.json"
PEAKS_FORMAT_VERSION = "1"

#: A manually created group must land on enough channels to fit two widths and
#: one component; below this the click was on a gap or an excluded region.
_MIN_GROUP_POINTS = 8


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class GroupMeta:
    """The per-group state an editor needs and the flattened list has lost."""

    lo: float                    # window bounds, ° 2θ (values of det channels)
    hi: float
    seed_fwhm: float             # ° 2θ, the frozen width the solve is bounded by
    gamma_g: float               # fitted component FWHMs — fwhm/eta on a peak
    gamma_l: float               # cannot be inverted back to this pair
    from_reseed: list[bool]      # per component, ascending 2θ

    def as_dict(self) -> dict:
        return {"lo": self.lo, "hi": self.hi, "seed_fwhm": self.seed_fwhm,
                "gamma_g": self.gamma_g, "gamma_l": self.gamma_l,
                "from_reseed": list(self.from_reseed)}


@dataclass
class PeakDoc:
    """What ``peaks.json`` holds: the list, the group state, the pick call."""

    peaks: PeakList
    groups: dict[int, GroupMeta] = field(default_factory=dict)
    pick_options: dict = field(default_factory=dict)
    created_utc: str = ""


# ----------------------------------------------------------------------
# the store
# ----------------------------------------------------------------------
def peaks_path(project) -> Path:
    return Path(project.path) / PEAKS_FILE


def load(project) -> PeakDoc | None:
    """The project's stored peak list, or ``None`` when none was ever picked.

    Raises ``ValueError`` when the stored ``data_fingerprint`` disagrees with
    the project's pattern: a peak list must never be displayed against — or
    worse, indexed against — data it was not measured on.  The mismatch is a
    refusal, not a silent re-pick, because the list may carry human edits.
    """
    path = peaks_path(project)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    actual = project.data_ref.fingerprint
    stored = raw.get("data_fingerprint", "")
    if stored != actual:
        raise ValueError(
            f"{path}: this peak list was picked from a different pattern "
            f"(fingerprint {stored[:8] or '(none)'}, the project's data reads "
            f"{actual[:8]}); re-pick rather than trusting positions measured "
            "on other data")
    return PeakDoc(
        peaks=PeakList.model_validate(raw["peaks"]),
        groups={int(k): GroupMeta(**v) for k, v in raw.get("groups", {}).items()},
        pick_options=dict(raw.get("pick_options", {})),
        created_utc=raw.get("created_utc", ""))


def save(project, doc: PeakDoc) -> None:
    payload = {
        "format_version": PEAKS_FORMAT_VERSION,
        "data_fingerprint": project.data_ref.fingerprint,
        "created_utc": doc.created_utc or _utcnow(),
        "pick_options": dict(doc.pick_options),
        "peaks": json.loads(doc.peaks.model_dump_json()),
        "groups": {str(k): v.as_dict() for k, v in sorted(doc.groups.items())},
    }
    target = peaks_path(project)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    os.replace(tmp, target)  # a crash leaves the previous list, not half of one


def delete(project) -> bool:
    path = peaks_path(project)
    if path.is_file():
        path.unlink()
        return True
    return False


# ----------------------------------------------------------------------
# flags — pure list surgery, no refit
# ----------------------------------------------------------------------
def set_flags(doc: PeakDoc, index: int, *, use_for_indexing: bool | None = None,
              flags: list[str] | None = None) -> PeakDoc:
    """One peak's flags, edited as the user's own decision.

    ``use_for_indexing=False`` adds ``excluded`` — the existing route for a
    caller's decision.  ``use_for_indexing=True`` removes every flag in
    :data:`~rietx.schemas.indexing.PEAK_UNUSABLE_FLAGS` from this peak: that
    is the overrule act (most often of ``not_separable``, a judgement about a
    real component), and it is deliberately *lossy* about the fitter's marks —
    a human who says "this is a line" is not asking for a debate.  ``flags``
    replaces the list wholesale for surgical edits; the vocabulary is closed.
    """
    peak = _peak_at(doc, index)
    if (use_for_indexing is None) == (flags is None):
        raise ValueError("send exactly one of use_for_indexing or flags")
    if flags is not None:
        vocabulary = set(get_args(PeakFlag))
        unknown = [f for f in flags if f not in vocabulary]
        if unknown:
            raise ValueError(f"unknown flag(s) {unknown}; the vocabulary is "
                             f"{sorted(vocabulary)}")
        peak.flags = list(dict.fromkeys(flags))  # de-dup, order kept
    elif use_for_indexing:
        peak.flags = [f for f in peak.flags if f not in PEAK_UNUSABLE_FLAGS]
    elif "excluded" not in peak.flags:
        peak.flags = [*peak.flags, "excluded"]
    return doc


def _peak_at(doc: PeakDoc, index: int) -> ObservedPeak:
    if not 0 <= index < len(doc.peaks.peaks):
        raise IndexError(f"no peak {index}; the list has "
                         f"{len(doc.peaks.peaks)}")
    return doc.peaks.peaks[index]


# ----------------------------------------------------------------------
# the editor
# ----------------------------------------------------------------------
@dataclass
class _Carry:
    """What survives a refit because a human owns it, per component."""

    origin: Literal["fitted", "manual", "edited"] = "fitted"
    excluded: bool = False
    from_reseed: bool = False


class PeakEditor:
    """The verbs, over one (data, instrument, range) triple.

    Holds the lazily built :class:`Detection` — the masked pattern, the frozen
    background envelope and the measured width scale — which every refit and
    every drawn curve reads.  The session caches the editor keyed on what the
    detection depends on, so an instrument edit or a changed exclusion rebuilds
    it and a run of peak edits does not.
    """

    def __init__(self, data: PatternData, instrument: Instrument, *,
                 two_theta_range: tuple[float, float] | None = None):
        self.data = data
        self.instrument = instrument
        self.two_theta_range = two_theta_range
        self._det: Detection | None = None

    @property
    def det(self) -> Detection:
        if self._det is None:
            self._det = detect_peaks(self.data, self.instrument,
                                     two_theta_range=self.two_theta_range)
        return self._det

    @property
    def wavelength(self) -> float:
        return self.instrument.source.lines[0].wavelength.value

    # -- picking -------------------------------------------------------
    def pick(self, *, shoulders: bool = True) -> PeakDoc:
        """A fresh list — and a fresh detection, since the fits come from one."""
        peaks, det, fits = pick_peaks_with_state(
            self.data, self.instrument, two_theta_range=self.two_theta_range,
            shoulders=shoulders)
        self._det = det
        groups: dict[int, GroupMeta] = {}
        for gi, (group, fit) in enumerate(zip(det.groups, fits)):
            if fit.n == 0:
                continue  # every component was pruned; nothing to edit or draw
            groups[gi] = GroupMeta(
                lo=float(det.two_theta[group.i0]),
                hi=float(det.two_theta[group.i1 - 1]),
                seed_fwhm=float(group.seed_fwhm),
                gamma_g=float(fit.gamma_g), gamma_l=float(fit.gamma_l),
                from_reseed=[bool(b) for b in fit.reseeded()])
        return PeakDoc(peaks=peaks, groups=groups, created_utc=_utcnow(),
                       pick_options={"shoulders": shoulders,
                                     "two_theta_range": self.two_theta_range})

    # -- editing -------------------------------------------------------
    def add(self, doc: PeakDoc, two_theta: float, *,
            origin: Literal["manual", "edited"] = "manual") -> PeakDoc:
        """Seed a component at ``two_theta`` and refit the group it lands in.

        A click inside an existing group's window adds a component to that
        group's simultaneous fit; a click anywhere else opens a fresh window
        around the position, mirroring detection's own sizing.
        """
        tt = float(two_theta)
        g = self._group_containing(doc, tt)
        if g is None:
            g, meta = self._new_group(doc, tt)
            doc.groups[g] = meta
            comps: list[tuple[ObservedPeak, _Carry]] = []
        else:
            comps = self._components(doc, g)
        seeds = [p.two_theta for p, _ in comps] + [tt]
        carries = [c for _, c in comps] + [_Carry(origin=origin)]
        return self._refit_with(doc, g, seeds, carries)

    def move(self, doc: PeakDoc, index: int, two_theta: float) -> PeakDoc:
        """Reseed one component at the dragged position and refit its group.

        A drag beyond the group's own window is a removal from that group plus
        an :meth:`add` at the target — the component's identity (its ``origin``
        and any ``excluded`` mark) does not survive the crossing, because the
        window it was fitted in no longer contains it.
        """
        peak = _peak_at(doc, index)
        tt = float(two_theta)
        g = peak.group
        meta = self._meta(doc, g)
        if not meta.lo <= tt <= meta.hi:
            doc = self.remove(doc, index)
            return self.add(doc, tt, origin="edited")
        comps = self._components(doc, g)
        seeds, carries = [], []
        for p, carry in comps:
            if p is peak:
                seeds.append(tt)
                carries.append(_Carry(origin="edited", excluded=carry.excluded,
                                      from_reseed=False))
            else:
                seeds.append(p.two_theta)
                carries.append(carry)
        return self._refit_with(doc, g, seeds, carries)

    def remove(self, doc: PeakDoc, index: int) -> PeakDoc:
        """Drop one component and refit what its group still holds."""
        peak = _peak_at(doc, index)
        g = peak.group
        comps = [(p, c) for p, c in self._components(doc, g) if p is not peak]
        if not comps:
            doc.peaks = _spliced(doc.peaks, g, [], self.det)
            doc.groups.pop(g, None)
            return doc
        return self._refit_with(doc, g, [p.two_theta for p, _ in comps],
                                [c for _, c in comps])

    def refit(self, doc: PeakDoc, group: int, *,
              n_components: int | None = None) -> PeakDoc:
        """Refit one group — at a component count the user chose, or freshly.

        With ``n_components`` the count is the user's: extra components are
        seeded one at a time at the fitter's own residual proposal
        (``reseed_at``) and surplus ones dropped weakest-first by |I|/σ(I).
        Without it the group is refitted under the picker's full judgement
        (:func:`~rietx.indexing.peakfit.fit_group`: shoulder pruning and
        ΔBIC-gated re-seeding), which is "start this group over".
        """
        meta = self._meta(doc, group)
        comps = self._components(doc, group)
        if not comps:
            raise IndexError(f"group {group} holds no peaks")
        seeds = [p.two_theta for p, _ in comps]
        carries = [c for _, c in comps]
        if n_components is None:
            return self._refit_fresh(doc, group, seeds, carries)
        n = int(n_components)
        if n < 1:
            raise ValueError("n_components must be at least 1")
        while n < len(seeds):
            weakest = min(
                range(len(comps)),
                key=lambda j: abs(comps[j][0].intensity)
                / (comps[j][0].intensity_esd or float("inf")))
            comps.pop(weakest)
            seeds.pop(weakest)
            carries.pop(weakest)
        while n > len(seeds):
            fit = self._solve(meta, seeds)
            if fit.reseed_at is None:
                raise ValueError(
                    f"the residual proposes no position for component "
                    f"{len(seeds) + 1}; add one by clicking where you see it")
            k = int(np.searchsorted(np.sort(np.asarray(seeds)), fit.reseed_at))
            seeds.insert(k, float(fit.reseed_at))
            carries.insert(k, _Carry(origin="fitted", from_reseed=True))
        return self._refit_with(doc, group, seeds, carries)

    def flag(self, doc: PeakDoc, index: int, *,
             use_for_indexing: bool | None = None,
             flags: list[str] | None = None) -> PeakDoc:
        """:func:`set_flags`, then the list's diagnostics recomputed — a flags
        edit changes what ``usable()`` returns, and the diagnostics speak about
        the usable lines."""
        set_flags(doc, index, use_for_indexing=use_for_indexing, flags=flags)
        doc.peaks = doc.peaks.model_copy(update={
            "diagnostics": peak_diagnostics(doc.peaks, self.det)})
        return doc

    # -- drawing -------------------------------------------------------
    def curves(self, doc: PeakDoc) -> list[dict]:
        """Per group: the fitted profile over its window, and the residual strip.

        Evaluation only — the profile is reconstructed from the stored width
        pair and the stored component positions/areas
        (:func:`~rietx.indexing.peakfit.group_profile`), so drawing costs no
        solve.  ``y_fit`` includes the frozen envelope because the panel draws
        it over the measured counts; ``delta`` is (y − env − model)/σ, the same
        weighting the group was fitted under.
        """
        det = self.det
        out = []
        for g, meta in sorted(doc.groups.items()):
            members = [p for p in doc.peaks.peaks if p.group == g]
            if not members:
                continue
            pg, fit = self._as_fit(meta, members)
            model = group_profile(det, pg, self.instrument, fit)
            sl = slice(pg.i0, pg.i1)
            y_fit = det.envelope[sl] + model
            out.append({
                "group": g,
                "two_theta": det.two_theta[sl].tolist(),
                "y_fit": y_fit.tolist(),
                "y_env": det.envelope[sl].tolist(),
                "delta": ((det.intensity[sl] - y_fit) / det.sigma[sl]).tolist(),
                "chi2_red": members[0].chi2_red,
                "n_components": len(members),
            })
        return out

    # -- internals -----------------------------------------------------
    def _meta(self, doc: PeakDoc, g: int) -> GroupMeta:
        try:
            return doc.groups[g]
        except KeyError:
            raise IndexError(f"no group {g}; the list has groups "
                             f"{sorted(doc.groups)}") from None

    def _components(self, doc: PeakDoc, g: int
                    ) -> list[tuple[ObservedPeak, _Carry]]:
        """Group ``g``'s peaks in ascending 2θ, each with what a refit carries."""
        meta = doc.groups.get(g)
        reseed = list(meta.from_reseed) if meta is not None else []
        members = [p for p in doc.peaks.peaks if p.group == g]
        members.sort(key=lambda p: p.two_theta)
        return [(p, _Carry(origin=p.origin, excluded="excluded" in p.flags,
                           from_reseed=bool(reseed[j]) if j < len(reseed)
                           else False))
                for j, p in enumerate(members)]

    def _group_containing(self, doc: PeakDoc, tt: float) -> int | None:
        hits = [(g, m) for g, m in doc.groups.items() if m.lo <= tt <= m.hi]
        if not hits:
            return None
        # windows can overlap by their margins; the group whose components sit
        # closest is the one a human meant
        def distance(item):
            g, _ = item
            members = [p.two_theta for p in doc.peaks.peaks if p.group == g]
            return min((abs(tt - m) for m in members), default=float("inf"))
        return min(hits, key=distance)[0]

    def _new_group(self, doc: PeakDoc, tt: float) -> tuple[int, GroupMeta]:
        """A fresh window around ``tt``, sized as detection sizes its own."""
        det = self.det
        if not det.two_theta[0] <= tt <= det.two_theta[-1]:
            raise ValueError(
                f"2θ = {tt:.4f}° is outside the picked range "
                f"{det.two_theta[0]:.4f}–{det.two_theta[-1]:.4f}°")
        fw = float(predicted_fwhm(np.array([tt]), self.instrument)[0]
                   * det.width_scale)
        half = PEAK_WINDOW_FWHM_MULT * fw
        sl_ap = self.instrument.geometry.axial_sl.value
        hl_ap = self.instrument.geometry.axial_hl.value
        extra = (float(fcj_extent_deg(np.array(tt), sl_ap, hl_ap))
                 if sl_ap > 0.0 and hl_ap > 0.0 else 0.0)
        i0 = int(np.searchsorted(det.two_theta, tt - half - extra, "left"))
        i1 = int(np.searchsorted(det.two_theta, tt + half, "right"))
        if i1 - i0 < _MIN_GROUP_POINTS:
            raise ValueError(
                f"only {i1 - i0} channel(s) around 2θ = {tt:.4f}°; that is a "
                "gap or an excluded region, not a place a peak can be fitted")
        g = max(doc.groups, default=-1) + 1
        return g, GroupMeta(
            lo=float(det.two_theta[i0]), hi=float(det.two_theta[i1 - 1]),
            seed_fwhm=fw, gamma_g=0.0, gamma_l=0.0, from_reseed=[])

    def _peak_group(self, meta: GroupMeta, seeds: list[float]) -> PeakGroup:
        det = self.det
        i0 = int(np.searchsorted(det.two_theta, meta.lo, "left"))
        i1 = int(np.searchsorted(det.two_theta, meta.hi, "right"))
        return PeakGroup(i0=i0, i1=i1,
                         seed_two_theta=np.sort(np.asarray(seeds, dtype=np.float64)),
                         seed_fwhm=meta.seed_fwhm,
                         from_shoulder=np.zeros(len(seeds), dtype=bool))

    def _solve(self, meta: GroupMeta, seeds: list[float]) -> GroupFit:
        pg = self._peak_group(meta, seeds)
        return fit_group_at(self.det, pg, self.instrument, pg.seed_two_theta)

    def _as_fit(self, meta: GroupMeta, members: list[ObservedPeak]
                ) -> tuple[PeakGroup, GroupFit]:
        """A drawable :class:`GroupFit` from stored state — no solving."""
        members = sorted(members, key=lambda p: p.two_theta)
        pg = self._peak_group(meta, [p.two_theta for p in members])
        n = len(members)
        fit = GroupFit(
            group=pg, n=n,
            two_theta=np.array([p.two_theta for p in members]),
            two_theta_esd=np.array([p.two_theta_esd for p in members]),
            intensity=np.array([p.intensity for p in members]),
            intensity_esd=np.array([p.intensity_esd for p in members]),
            gamma_g=meta.gamma_g, gamma_l=meta.gamma_l,
            fwhm=members[0].fwhm, eta=members[0].eta,
            chi2_red=members[0].chi2_red, converged=True,
            at_bound=np.zeros(n, dtype=bool), asymmetry_t=np.zeros(n),
            n_points=pg.i1 - pg.i0)
        return pg, fit

    def _refit_fresh(self, doc: PeakDoc, g: int, seeds: list[float],
                     carries: list[_Carry]) -> PeakDoc:
        """The picker's own judgement over this group (prune + reseed)."""
        meta = self._meta(doc, g)
        pg = self._peak_group(meta, seeds)
        fit = fit_group(self.det, pg, self.instrument)
        # fit_group may have added components (its from_reseed marks them) but
        # never reorders the survivors; carries map onto the non-added slots
        added = fit.reseeded()
        merged: list[_Carry] = []
        k = 0
        for j in range(fit.n):
            if added[j]:
                merged.append(_Carry(origin="fitted", from_reseed=True))
            else:
                merged.append(carries[k] if k < len(carries) else _Carry())
                k += 1
        return self._absorb(doc, g, meta, fit, merged)

    def _refit_with(self, doc: PeakDoc, g: int, seeds: list[float],
                    carries: list[_Carry]) -> PeakDoc:
        """One frozen-count solve at the caller's seeds."""
        meta = self._meta(doc, g)
        order = np.argsort(np.asarray(seeds))
        fit = self._solve(meta, [seeds[int(j)] for j in order])
        return self._absorb(doc, g, meta, fit,
                            [carries[int(j)] for j in order])

    def _absorb(self, doc: PeakDoc, g: int, meta: GroupMeta, fit: GroupFit,
                carries: list[_Carry]) -> PeakDoc:
        """Translate, re-apply what humans own, splice, and update the meta."""
        fit.from_reseed = np.array([c.from_reseed for c in carries], dtype=bool)
        fresh = peaks_of_group(fit, g, self.wavelength)
        for peak, carry in zip(fresh, carries):
            peak.origin = carry.origin
            if carry.excluded and "excluded" not in peak.flags:
                peak.flags = [*peak.flags, "excluded"]
        doc.peaks = _spliced(doc.peaks, g, fresh, self.det,
                             self.instrument.source.lines)
        meta.gamma_g, meta.gamma_l = float(fit.gamma_g), float(fit.gamma_l)
        meta.from_reseed = [bool(b) for b in fit.reseeded()]
        return doc


def _spliced(peaks: PeakList, g: int, fresh: list[ObservedPeak],
             det: Detection, lines=()) -> PeakList:
    """The list with group ``g`` replaced by ``fresh``, marks and diagnostics
    recomputed for exactly the spliced components."""
    merged = [p for p in peaks.peaks if p.group != g] + list(fresh)
    merged.sort(key=lambda p: p.two_theta)
    if fresh:
        new_ids = {id(p) for p in fresh}
        only = {i for i, p in enumerate(merged) if id(p) in new_ids}
        flag_ghosts(merged, peaks.wavelength, det, only=only)
        # the same one-group restriction, for the same reason: recomputing the
        # Kα2-residual mark on edited components must not resurrect one a user
        # cleared on an untouched line (WP-1043)
        flag_kalpha2_residuals(merged, lines, only=only)
    out = peaks.model_copy(update={"peaks": merged})
    return out.model_copy(update={"diagnostics": peak_diagnostics(out, det)})
