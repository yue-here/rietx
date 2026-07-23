"""Multi-histogram parameter bookkeeping (WP-0308).

A joint refinement fits one **shared** :class:`~pxrdref.schemas.structure.Structure`
against several patterns, each measured on its **own**
:class:`~pxrdref.schemas.instrument.Instrument` (different wavelength, geometry,
resolution, background).  Physically the split is instrument-vs-sample: the
crystal (cell, coordinates, occupancies, ADPs, size/strain, extinction, texture)
is one object seen by every histogram, while the instrument and the per-pattern
scale (incident flux × illuminated volume) differ.

:class:`MultiParameterTable` owns one ordinary :class:`ParameterTable` per
histogram — so each keeps its crystal-system cell ties, Wyckoff DOFs and
transforms unchanged — and threads a single combined free vector θ through them
with a column map that folds *shared* columns onto one shared combined column
(fed to every histogram's model) while giving *per-histogram* columns their own.
The stacked residual/Jacobian in
:func:`~pxrdref.optimize.least_squares.run_multi_least_squares` scatters each
histogram's block through this map.

Per-histogram parameters are named with a ``hist.{h}.`` scope
(``hist.0.instrument.zero_shift``, ``hist.1.phases.0.scale``); shared parameters
keep their bare path (``phases.0.cell.a``).  A turn-on glob frees a parameter
when it matches either form, so every existing single-histogram plan
(``phases.*.scale``, ``instrument.background.*``) frees *all* histograms' copies
unchanged, while a scoped glob (``hist.1.*``) targets one.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

import numpy as np

from ..schemas.instrument import Instrument
from ..schemas.structure import Structure
from .vector import ParameterTable


@dataclass
class SharingMap:
    """Which parameter paths are shared across histograms vs. per-histogram.

    Default rule: a path is **per-histogram** iff it starts with ``instrument.``
    or ends with ``.scale``; everything else (cell, coordinates, occupancies,
    ADPs, size/strain, extinction, preferred orientation) is **shared** — one
    specimen, one crystal.  ``per_histogram`` / ``shared`` are override glob
    lists (fnmatch on the bare unscoped path, no brackets), checked in that
    order before the default, so a caller can e.g. give each histogram its own
    preferred-orientation axis (``per_histogram=["phases.*.preferred_orientation.*"]``)
    or tie a sample-displacement across mounts.
    """

    per_histogram: list[str] = field(default_factory=list)
    shared: list[str] = field(default_factory=list)

    def is_shared(self, path: str) -> bool:
        if any(fnmatch.fnmatchcase(path, g) for g in self.per_histogram):
            return False
        if any(fnmatch.fnmatchcase(path, g) for g in self.shared):
            return True
        return not (path.startswith("instrument.") or path.endswith(".scale"))


class MultiParameterTable:
    """One :class:`ParameterTable` per histogram + a shared/per-histogram θ map."""

    def __init__(self, structure: Structure, instruments: list[Instrument], *,
                 sharing: SharingMap | None = None):
        if len(instruments) < 1:
            raise ValueError("need at least one instrument")
        self.sharing = sharing or SharingMap()
        # a private structure copy per histogram: shared parameters are written
        # identically into every copy at each commit; only the per-histogram
        # scale (and any per-histogram override) diverges.
        self.structures: list[Structure] = [structure.model_copy(deep=True)
                                             for _ in instruments]
        self.instruments: list[Instrument] = [ins.model_copy(deep=True)
                                              for ins in instruments]
        self.tables: list[ParameterTable] = [
            ParameterTable(s, ins)
            for s, ins in zip(self.structures, self.instruments, strict=True)]
        self._rebuild_columns()

    @property
    def n_histograms(self) -> int:
        return len(self.tables)

    # -- vary control --------------------------------------------------
    def _canonical(self, h: int, path: str) -> str:
        """The scoped name of ``path`` in histogram ``h`` (bare if shared)."""
        return path if self.sharing.is_shared(path) else f"hist.{h}.{path}"

    def set_vary(self, path_globs: list[str], vary: bool) -> list[str]:
        """Free/fix by glob across every histogram; returns scoped hits.

        A glob matches an entry when it matches either the scoped canonical name
        or the bare path, so single-histogram plans keep working verbatim.
        """
        freed: list[str] = []
        for h, table in enumerate(self.tables):
            matched = []
            for e in table.entries:
                if e.tie is not None or e.locked:
                    continue
                canon = self._canonical(h, e.path)
                if any(fnmatch.fnmatchcase(canon, g)
                       or fnmatch.fnmatchcase(e.path, g) for g in path_globs):
                    matched.append(e.path)
            if matched:
                for p in table.set_vary(matched, vary):
                    freed.append(self._canonical(h, p))
        self._rebuild_columns()
        return freed

    def seed_softplus(self, scoped_paths: list[str], value: float) -> list[str]:
        """Lift softplus params off the zero floor (per histogram); see the
        single-histogram :meth:`ParameterTable.seed_softplus`."""
        seeded: list[str] = []
        for h, table in enumerate(self.tables):
            want = [self._unscope(h, p) for p in scoped_paths
                    if self._owner(p) in (None, h)]
            for p in table.seed_softplus([w for w in want if w is not None], value):
                seeded.append(self._canonical(h, p))
        if seeded:
            self._rebuild_columns()
        return seeded

    # -- combined column layout ----------------------------------------
    def _rebuild_columns(self) -> None:
        """Recompute the shared/per-histogram combined column layout.

        Shared free columns come first (in histogram 0's order, and asserted
        identical across histograms — same structure copy, same globs), then
        each histogram's per-histogram free columns in turn.  ``_col_map[h][c]``
        is the combined index of histogram ``h``'s c-th free column.
        """
        shared_order: list[str] = []
        shared_seen: set[str] = set()
        per_hist_paths: list[list[str]] = [[] for _ in self.tables]
        shared_sets: list[set[str]] = []
        for h, table in enumerate(self.tables):
            sset: set[str] = set()
            for p in table.free_paths:
                if self.sharing.is_shared(p):
                    sset.add(p)
                    if p not in shared_seen:
                        shared_seen.add(p)
                        shared_order.append(p)
                else:
                    per_hist_paths[h].append(p)
            shared_sets.append(sset)
        for h, sset in enumerate(shared_sets):
            if sset != shared_seen:
                missing = sorted(shared_seen - sset)
                extra = sorted(sset - shared_seen)
                raise ValueError(
                    f"histogram {h} disagrees on the shared free set "
                    f"(missing {missing[:3]}, extra {extra[:3]}); shared "
                    "parameters must be freed identically in every histogram")

        shared_index = {p: k for k, p in enumerate(shared_order)}
        combined_paths = list(shared_order)
        per_hist_index: list[dict[str, int]] = [{} for _ in self.tables]
        for h in range(len(self.tables)):
            for p in per_hist_paths[h]:
                per_hist_index[h][p] = len(combined_paths)
                combined_paths.append(f"hist.{h}.{p}")

        n = len(combined_paths)
        col_map: list[np.ndarray] = []
        x0 = np.zeros(n, dtype=np.float64)
        lo = np.zeros(n, dtype=np.float64)
        hi = np.zeros(n, dtype=np.float64)
        for h, table in enumerate(self.tables):
            free = table.free_paths
            idx = np.array(
                [shared_index[p] if self.sharing.is_shared(p) else per_hist_index[h][p]
                 for p in free], dtype=np.int64)
            col_map.append(idx)
            xh = table.x0()
            loh, hih = table.bounds()
            # shared columns get identical values from each histogram (harmless
            # overwrite); per-histogram columns are written once.
            x0[idx] = xh
            lo[idx] = loh
            hi[idx] = hih

        self.shared_paths = shared_order
        self.per_hist_paths = per_hist_paths
        self._combined_paths = combined_paths
        self._col_map = col_map
        self._x0 = x0
        self._lo = lo
        self._hi = hi
        self.n_shared = len(shared_order)

    # -- optimiser interface -------------------------------------------
    @property
    def free_paths(self) -> list[str]:
        return list(self._combined_paths)

    def x0(self) -> np.ndarray:
        return self._x0.copy()

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        return self._lo.copy(), self._hi.copy()

    def col_map(self, h: int) -> np.ndarray:
        return self._col_map[h]

    def split(self, theta: np.ndarray) -> list[np.ndarray]:
        """Gather the per-histogram internal free vectors from combined θ."""
        return [theta[self._col_map[h]] for h in range(len(self.tables))]

    def decode(self, theta: np.ndarray) -> list[dict[str, float]]:
        thetas = self.split(theta)
        return [self.tables[h].decode(thetas[h]) for h in range(len(self.tables))]

    def commit(self, theta: np.ndarray) -> None:
        thetas = self.split(theta)
        for h, table in enumerate(self.tables):
            table.commit(thetas[h])

    def apply_to_models(self) -> None:
        for h, table in enumerate(self.tables):
            table.apply_to_models(self.structures[h], self.instruments[h])

    # -- helpers used by esd assembly ----------------------------------
    def _owner(self, scoped: str) -> int | None:
        """Histogram index of a scoped per-histogram path, or None if shared."""
        if scoped.startswith("hist."):
            return int(scoped.split(".", 2)[1])
        return None

    def _unscope(self, h: int, scoped: str) -> str | None:
        """Bare path of ``scoped`` as seen by histogram ``h`` (None if it
        belongs to another histogram)."""
        owner = self._owner(scoped)
        if owner is None:
            return scoped
        if owner != h:
            return None
        return scoped.split(".", 2)[2]
