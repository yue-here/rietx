"""The named ↔ flat-vector translation layer.

Compiles a (Structure, Instrument) pair into:

* an ordered table of every :class:`Parameter` with a stable dot-separated
  path (``phases.0.cell.a``, ``instrument.profile.w``,
  ``instrument.background.c2`` …);
* an affine constraint block **p_phys = C·p_free + d** (sparse C, rebuilt at
  every stage boundary, constant during a least-squares run — a constant
  matmul stays exact under the future autodiff backends).  Crystal-system
  cell ties are the identity-row special case; Wyckoff site constraints
  (``crystallography.wyckoff``) supply general rows;
* the mapping between the free internal vector θ (what the optimiser sees)
  and the full physical value dict consumed by the forward model.

The decode path is plain float/array arithmetic on a pre-built sparse
matrix — no pydantic objects are touched per iteration.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse

from ..crystallography.adp import U_NAMES
from ..crystallography.stephens import S_NAMES, isotropic_coefficients, strain_basis
from ..crystallography.symmetry import get_spacegroup, rotation_matrices
from ..crystallography.wyckoff import adp_basis, coordinate_basis, stabilizer_rotations
from ..schemas.common import Parameter
from ..schemas.instrument import BackgroundChebyshev, BackgroundPSpline, Instrument
from ..schemas.structure import Structure
from .transforms import dphys_dinternal, internal_bounds, to_internal, to_physical


def _background_parameters(bkg) -> list[tuple[str, Parameter]]:
    """(sub-path, Parameter) pairs for any background model, in design order."""
    if isinstance(bkg, BackgroundPSpline):
        out = [(f"c{n}", p) for n, p in enumerate(bkg.coefficients)]
        out.append(("air", bkg.air_scatter))
        return out
    cheb = bkg.coefficients if isinstance(bkg, BackgroundChebyshev) else bkg.chebyshev.coefficients
    return [(f"c{n}", p) for n, p in enumerate(cheb)]


def roughness_parameters(rough) -> list[tuple[str, Parameter]]:
    """(sub-path, Parameter) pairs for a surface-roughness block, or [].

    Shared by the collector and by :meth:`ParameterTable.apply_to_models` on
    purpose: a parameter registered in one and forgotten in the other silently
    loses its refined value at the next stage's recompile, which has bitten this
    file before (see the coordinate write-back comment below).  One source of
    truth for the field names makes that class of bug unrepresentable.

    The sub-path is the model's own field name, so the ``kind`` is legible
    straight from the dot-path (``…surface_roughness.b`` vs
    ``…surface_roughness.tau``) and a glob over
    ``instrument.geometry.surface_roughness.*`` frees whichever model is
    attached without the stage plan having to know which one it is.
    """
    if rough is None:
        return []
    return [(name, getattr(rough, name)) for name in type(rough).model_fields
            if name != "kind"]


@dataclass(frozen=True)
class AffineTie:
    """Declares one physical parameter as an affine function of others.

    value(path) = Σ coeff · value(source path) + const.  Sources may
    themselves be tied (chains are flattened at rebuild); cycles are an
    error.  :meth:`identity` gives the b ← a cell-tie special case.
    """

    terms: tuple[tuple[str, float], ...]
    const: float = 0.0

    @classmethod
    def identity(cls, source: str) -> "AffineTie":
        return cls(terms=((source, 1.0),))


@dataclass
class Entry:
    path: str
    value: float
    vary: bool
    lo: float
    hi: float
    transform: str
    tie: AffineTie | None = None  # affine dependence on other entries
    locked: bool = False  # structurally fixed: set_vary may never free it


# crystal-system cell ties: dependent → source for the identity ties, plus a
# set of angle values fixed by symmetry (never refinable in those systems).
_CELL_TIES: dict[str, dict[str, str]] = {
    "cubic": {"b": "a", "c": "a"},
    "tetragonal": {"b": "a"},
    "hexagonal": {"b": "a"},
    "trigonal": {"b": "a"},  # hexagonal-axes setting (gemmi default for R groups)
    "orthorhombic": {},
    "monoclinic": {},
    "triclinic": {},
}
_FIXED_ANGLES: dict[str, tuple[str, ...]] = {
    "cubic": ("alpha", "beta", "gamma"),
    "tetragonal": ("alpha", "beta", "gamma"),
    "hexagonal": ("alpha", "beta", "gamma"),
    "trigonal": ("alpha", "beta", "gamma"),
    "orthorhombic": ("alpha", "beta", "gamma"),
    "monoclinic": ("alpha", "gamma"),
    "triclinic": (),
}


class ParameterTable:
    def __init__(self, structure: Structure, instrument: Instrument):
        self.entries: list[Entry] = []
        #: phase base path → the Stephens DOF vector of the *unit* isotropic
        #: limit (1 ppm), kept so :meth:`seed_stephens` can put a freed block
        #: on the isotropic ray without rebuilding the symmetry basis
        self._strain_unit: dict[str, np.ndarray] = {}
        self._collect(structure, instrument)
        self._rebuild()

    # -- collection ----------------------------------------------------
    def _add(self, path: str, p: Parameter, *, force_fixed: bool = False,
             tie: AffineTie | None = None) -> None:
        self.entries.append(Entry(
            path=path, value=p.value, vary=p.vary and not force_fixed and tie is None,
            lo=p.min, hi=p.max, transform=p.transform, tie=tie,
            locked=force_fixed,
        ))

    def _collect(self, structure: Structure, instrument: Instrument) -> None:
        for ip, phase in enumerate(structure.phases):
            sg = get_spacegroup(phase.space_group)
            system = sg.crystal_system_str()
            ties = _CELL_TIES.get(system, {})
            fixed_angles = _FIXED_ANGLES.get(system, ())
            base = f"phases.{ip}"
            for name in ("a", "b", "c", "alpha", "beta", "gamma"):
                p: Parameter = getattr(phase.cell, name)
                if name in ties:
                    self._add(f"{base}.cell.{name}", p,
                              tie=AffineTie.identity(f"{base}.cell.{ties[name]}"))
                elif name in fixed_angles:
                    self._add(f"{base}.cell.{name}", p, force_fixed=True)
                else:
                    self._add(f"{base}.cell.{name}", p)
            self._add(f"{base}.scale", phase.scale)
            self._add(f"{base}.extinction", phase.extinction)
            if phase.preferred_orientation is not None:
                self._add(f"{base}.preferred_orientation.r",
                          phase.preferred_orientation.r)
            self._add(f"{base}.lor_size", phase.lor_size)
            # a Stephens block owns the tanθ Lorentzian channel outright: its
            # isotropic direction is the same column, so lor_strain is locked
            # (the Atom.aniso ⇒ biso bargain, one level up)
            self._add(f"{base}.lor_strain", phase.lor_strain,
                      force_fixed=phase.microstrain is not None)
            self._add(f"{base}.gauss_size", phase.gauss_size)
            self._add(f"{base}.gauss_strain", phase.gauss_strain)
            self._collect_microstrain(base, sg, phase)
            for j, atom in enumerate(phase.atoms):
                self._collect_atom_coords(f"{base}.atoms.{j}", sg, atom)
                self._add(f"{base}.atoms.{j}.occ", atom.occ)
                self._collect_atom_adps(f"{base}.atoms.{j}", sg, atom)

        self._add("instrument.zero_shift", instrument.zero_shift)
        self._collect_instrument(instrument)

    def _collect_microstrain(self, base: str, sg, phase) -> None:
        """Stephens S_HKL enter θ through Laue-symmetry-allowed patterns.

        The rank-4 twin of :meth:`_collect_atom_adps`: the phase contributes
        ``phases.i.microstrain.dof.k`` parameters, one per allowed pattern
        (``crystallography.stephens``), and the fifteen components become
        affine rows S = Σₖ Bₖ·θₖ.  **Absolute**, like the ADP patterns — the
        basis spans the whole allowed subspace, so writing S this way enforces
        the lattice symmetry exactly and coefficients outside it are an error
        rather than something to symmetrise.  Components the symmetry forces to
        zero are locked; the DOFs are unbounded, because σ²(M) ≥ 0 couples all
        fifteen and cannot be a box (positivity is a guard — the same argument
        that keeps the ADP cone out of ``bounds``).

        An all-zero block is the exact no-broadening identity, so it is allowed
        to *exist*; refining from there is not.  Λ ∝ √Σ has unbounded slope at
        the origin, so the first Jacobian column would be enormous and TRF's
        first step garbage — the failure inverts the softplus-at-zero trap
        (dead gradient) into an exploding one, and neither is something to
        discover from a bad fit.  ``Stage(seed=…)`` cannot help: it lifts
        softplus entries only, and these are identity-transform.
        """
        block = phase.microstrain
        if block is None:
            return
        basis = strain_basis(rotation_matrices(sg))  # (n_free, 15)
        s0 = np.array(block.values(), dtype=np.float64)
        coef, *_ = np.linalg.lstsq(basis.T.astype(np.float64), s0, rcond=None)
        residual = basis.T @ coef - s0
        scale = max(float(np.abs(s0).max()), 1.0)
        if float(np.abs(residual).max()) > 1e-6 * scale:
            raise ValueError(
                f"{base}.microstrain: the coefficients {s0.tolist()} are not "
                f"compatible with the lattice symmetry, which allows only "
                f"{basis.tolist()} in {list(S_NAMES)}; the nearest allowed set "
                f"is {(basis.T @ coef).tolist()}")
        want_vary = any(getattr(block, n).vary for n in S_NAMES)
        if want_vary and not np.any(s0):
            raise ValueError(
                f"{base}.microstrain: every S_HKL is zero, which is the point "
                "where the √ of the width law has unbounded slope — refining "
                "from there gives a meaningless first step.  Start from the "
                "isotropic limit instead: "
                "StephensStrain.isotropic(microstrain_ppm, phase.cell)")
        dof_paths = [f"{base}.microstrain.dof.{k}" for k in range(len(basis))]
        for v, name in enumerate(S_NAMES):
            p: Parameter = getattr(block, name)
            terms = tuple((dof_paths[k], float(basis[k][v]))
                          for k in range(len(basis)) if basis[k][v] != 0)
            if terms:
                self._add(f"{base}.microstrain.{name}", p, tie=AffineTie(terms=terms))
            else:
                # symmetry forces this monomial to vanish, so it is locked *at
                # zero* rather than at whatever the caller passed: the residual
                # check above has already bounded that to roundoff (the
                # isotropic seed goes through a matrix inverse), and carrying
                # the noise forward would break the symmetry the basis exists
                # to enforce exactly
                self.entries.append(Entry(
                    path=f"{base}.microstrain.{name}", value=0.0, vary=False,
                    lo=p.min, hi=p.max, transform=p.transform, locked=True))
        for k, path in enumerate(dof_paths):
            self.entries.append(Entry(path=path, value=float(coef[k]), vary=want_vary,
                                      lo=-np.inf, hi=np.inf, transform="identity"))
        # S scales as microstrain², so one unit-ppm projection serves any seed
        unit, *_ = np.linalg.lstsq(
            basis.T.astype(np.float64),
            isotropic_coefficients(phase.cell.lengths_angles(), 1.0), rcond=None)
        self._strain_unit[base] = unit

    def _collect_atom_coords(self, base: str, sg, atom) -> None:
        """Coordinates enter θ through site-symmetry displacement DOFs.

        Each site contributes ``…dof.k`` parameters — one per site-symmetry-
        allowed direction (``crystallography.wyckoff``) — and x, y, z become
        affine rows x = x₀ + Σₖ Bₖ·θₖ anchored at the compile-time position.
        Fully fixed special positions contribute none (their coordinates are
        locked); ``vary=True`` on any coordinate of such a site is an error.
        A vary request on a constrained-but-free site frees *all* of the
        site's DOFs — per-axis intent does not map onto rows such as [1,1,0].
        DOFs are unbounded displacements; bounds declared on x/y/z do not
        constrain them.
        """
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        basis = coordinate_basis(stabilizer_rotations(sg, xyz))
        want_vary = any(getattr(atom, c).vary for c in ("x", "y", "z"))
        if len(basis) == 0 and want_vary:
            raise ValueError(
                f"{base} sits on a fully fixed special position; its site "
                "symmetry allows no positional freedom — set vary=False")
        dof_paths = [f"{base}.dof.{k}" for k in range(len(basis))]
        for c_idx, c in enumerate(("x", "y", "z")):
            p: Parameter = getattr(atom, c)
            terms = tuple((dof_paths[k], float(basis[k][c_idx]))
                          for k in range(len(basis)) if basis[k][c_idx] != 0)
            if terms:
                self._add(f"{base}.{c}", p, tie=AffineTie(terms=terms, const=p.value))
            else:
                self._add(f"{base}.{c}", p, force_fixed=True)
        for path in dof_paths:
            self.entries.append(Entry(path=path, value=0.0, vary=want_vary,
                                      lo=-np.inf, hi=np.inf, transform="identity"))

    def _collect_atom_adps(self, base: str, sg, atom) -> None:
        """Displacement parameters: ``biso``, or aniso U^ij through DOFs.

        An anisotropic site contributes ``…adp.k`` parameters — one per
        site-symmetry-allowed U^ij *pattern* (``crystallography.wyckoff``) —
        and the six components become affine rows U = Σₖ Bₖ·θₖ.  Unlike the
        coordinate DOFs these are **absolute**, not displacements from an
        anchor: the pattern basis spans the whole allowed subspace, so writing
        U that way enforces the site symmetry exactly rather than only
        preserving whatever asymmetry the starting values carried.  θ₀ is
        therefore the least-squares projection of the input tensor onto the
        basis, and an input that does not lie in it is an error, not something
        to silently symmetrise.

        Components the site symmetry forces to zero (empty rows) are locked;
        the DOFs are unbounded, so ``min``/``max`` on a component do not
        constrain them — positive-definiteness is a guard, not a box.
        ``biso`` is still collected (locked when aniso is present) so its
        path exists for globs and write-back either way.
        """
        if atom.aniso is None:
            self._add(f"{base}.biso", atom.biso)
            return
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        basis = adp_basis(stabilizer_rotations(sg, xyz))  # (n_free, 6)
        u0 = np.array(atom.aniso.values(), dtype=np.float64)
        coef, *_ = np.linalg.lstsq(basis.T.astype(np.float64), u0, rcond=None)
        residual = basis.T @ coef - u0
        scale = max(float(np.abs(u0).max()), 1e-6)
        if float(np.abs(residual).max()) > 1e-6 * scale:
            raise ValueError(
                f"{base}: the anisotropic tensor {u0.tolist()} is not "
                f"compatible with the site symmetry, which allows only "
                f"{basis.tolist()} in (U11, U22, U33, U12, U13, U23); the "
                f"nearest allowed tensor is {(basis.T @ coef).tolist()}")
        dof_paths = [f"{base}.adp.{k}" for k in range(len(basis))]
        want_vary = any(getattr(atom.aniso, n).vary for n in U_NAMES)
        for v, name in enumerate(U_NAMES):
            p: Parameter = getattr(atom.aniso, name)
            terms = tuple((dof_paths[k], float(basis[k][v]))
                          for k in range(len(basis)) if basis[k][v] != 0)
            if terms:
                self._add(f"{base}.{name}", p, tie=AffineTie(terms=terms))
            else:
                self._add(f"{base}.{name}", p, force_fixed=True)
        for k, path in enumerate(dof_paths):
            self.entries.append(Entry(path=path, value=float(coef[k]), vary=want_vary,
                                      lo=-np.inf, hi=np.inf, transform="identity"))
        self._add(f"{base}.biso", atom.biso, force_fixed=True)

    def _collect_instrument(self, instrument: Instrument) -> None:
        self._add("instrument.polarization", instrument.source.polarization)
        for il, line in enumerate(instrument.source.lines):
            # line 0 defines the intensity scale: its weight is degenerate with
            # the phase scale factors, so it is always held fixed
            self._add(f"instrument.source.lines.{il}.weight", line.weight,
                      force_fixed=(il == 0))
        geom = instrument.geometry
        for name in ("sample_displacement", "sample_transparency",
                     "axial_sl", "axial_hl"):
            self._add(f"instrument.geometry.{name}", getattr(geom, name),
                      force_fixed=(geom.kind != "bragg_brentano"
                                   and name.startswith("sample_")))
        # surface roughness is opt-in, so it is *skipped* when absent rather
        # than added locked: a table built from an instrument without the block
        # is byte-for-byte the pre-WP-0502 table.  No geometry gate needed —
        # Geometry's validator already refuses the block on non-flat specimens.
        for sub, cp in roughness_parameters(geom.surface_roughness):
            self._add(f"instrument.geometry.surface_roughness.{sub}", cp)
        for name in ("u", "v", "w", "x", "y"):
            self._add(f"instrument.profile.{name}", getattr(instrument.profile, name))
        for sub, cp in _background_parameters(instrument.background):
            self._add(f"instrument.background.{sub}", cp)

    # -- the affine constraint block -----------------------------------
    def _flatten(self, tie: AffineTie, _seen: tuple[str, ...] = ()
                 ) -> tuple[list[tuple[int, float]], float]:
        """Resolve a tie onto untied entries: chains collapse, cycles raise."""
        terms: list[tuple[int, float]] = []
        const = tie.const
        for path, coeff in tie.terms:
            if path in _seen:
                raise ValueError(f"cyclic parameter tie through {path!r}")
            i = self._paths.get(path)
            if i is None:
                raise ValueError(f"tie references unknown parameter {path!r}")
            src = self.entries[i]
            if src.tie is None:
                terms.append((i, coeff))
            else:
                sub_terms, sub_const = self._flatten(src.tie, _seen + (path,))
                terms.extend((j, coeff * c) for j, c in sub_terms)
                const += coeff * sub_const
        return terms, const

    def _rebuild(self) -> None:
        """Recompile p_phys = C·p_free + d from the current entries.

        Free entries get unit rows, held entries put their value in ``d``,
        tied entries scatter flattened coefficients into ``C`` (free
        sources) and ``d`` (held sources + constants).  Rebuilds happen
        only at stage boundaries (``set_vary`` / ``commit`` / ``set_tie``),
        never inside a least-squares run, so the map is a constant matmul
        while the optimiser looks at it.
        """
        self._paths = {e.path: i for i, e in enumerate(self.entries)}
        self._free_idx = [i for i, e in enumerate(self.entries) if e.vary and e.tie is None]
        col = {i: k for k, i in enumerate(self._free_idx)}
        n, m = len(self.entries), len(self._free_idx)
        c_rows: list[int] = []
        c_cols: list[int] = []
        c_vals: list[float] = []
        d = np.zeros(n, dtype=np.float64)
        for i, e in enumerate(self.entries):
            if e.tie is None:
                if i in col:
                    c_rows.append(i)
                    c_cols.append(col[i])
                    c_vals.append(1.0)
                else:
                    d[i] = e.value
            else:
                terms, const = self._flatten(e.tie, (e.path,))
                d[i] = const
                for j, coeff in terms:
                    if j in col:
                        c_rows.append(i)
                        c_cols.append(col[j])
                        c_vals.append(coeff)
                    else:
                        d[i] += coeff * self.entries[j].value
        self._C = sparse.csr_matrix((c_vals, (c_rows, c_cols)), shape=(n, m))
        self._d = d

    def constraint_block(self) -> tuple[sparse.csr_matrix, np.ndarray]:
        """The current (C, d) with rows in entry order, columns in θ order."""
        return self._C, self._d

    # -- table surgery (used by Wyckoff constraint wiring) -------------
    def add_parameter(self, path: str, value: float, *, vary: bool = False,
                      lo: float = -np.inf, hi: float = np.inf,
                      transform: str = "identity") -> None:
        """Append a synthetic parameter (e.g. a Wyckoff displacement DOF).

        Synthetic paths must not collide with existing entries; pick names
        outside the model tree, e.g. ``phases.0.atoms.2.dof.0``.
        """
        if path in self._paths:
            raise ValueError(f"parameter {path!r} already exists")
        self.entries.append(Entry(path=path, value=value, vary=vary,
                                  lo=lo, hi=hi, transform=transform))
        self._rebuild()

    def set_tie(self, path: str, tie: AffineTie | None) -> None:
        """(Re)declare an entry as an affine function of other entries.

        Tying forces ``vary=False`` (the entry leaves θ; its sources carry
        the freedom).  Locked entries cannot be retied.  ``None`` unties.
        """
        i = self._paths.get(path)
        if i is None:
            raise ValueError(f"unknown parameter {path!r}")
        e = self.entries[i]
        if e.locked:
            raise ValueError(f"cannot tie structurally locked parameter {path!r}")
        e.tie = tie
        if tie is not None:
            e.vary = False
        self._rebuild()

    # -- vary control (used by the staged strategy) --------------------
    def set_vary(self, path_globs: list[str], vary: bool) -> list[str]:
        """Glob-match entry paths (fnmatch semantics on dot paths); returns hits.

        Tied and locked entries never match: symmetry-fixed cell angles and
        the line-0 emission weight cannot be freed even by a broad glob such
        as ``phases.*.cell.*``.
        """
        import fnmatch

        hits = []
        for e in self.entries:
            if any(fnmatch.fnmatchcase(e.path, g) for g in path_globs):
                if e.tie is None and not e.locked:
                    e.vary = vary
                    hits.append(e.path)
        self._rebuild()
        return hits

    def seed_softplus(self, paths: list[str], value: float) -> list[str]:
        """Lift softplus-bounded free params sitting below ``value`` up to it.

        A softplus coefficient at ~0 has an internal gradient ≈ 0 (dp/du =
        σ(u) → 0 as p → 0), so TRF cannot move it off the floor.  When a stage
        frees such a parameter this nudges it to a small positive seed so the
        first Jacobian has a live column.  Only softplus entries strictly
        below ``value`` are touched (already-lifted ones and other transforms
        are left alone); returns the paths actually seeded.
        """
        seeded = []
        for path in paths:
            i = self._paths.get(path)
            if i is None:
                continue
            e = self.entries[i]
            if e.transform == "softplus" and e.value < value:
                e.value = value
                seeded.append(path)
        if seeded:
            self._rebuild()
        return seeded

    def seed_stephens(self, paths: list[str], microstrain: float) -> list[str]:
        """Put a freed but still all-zero Stephens block on the isotropic ray.

        The counterpart of :meth:`seed_softplus` for the anisotropic-strain
        DOFs, and needed for the opposite reason: they are identity-transform,
        so ``seed_softplus`` skips them, and their pathology at zero is an
        *exploding* rather than a dead gradient (Λ ∝ √Σ).  The seed is the
        isotropic limit — S = microstrain²·[M²], the one point of the allowed
        subspace that is guaranteed to give σ²(M) > 0 for every reflection.

        Only phases whose *whole* block is still zero are touched, so a
        deliberate starting model is never overwritten.  Returns the paths
        actually seeded.
        """
        if microstrain <= 0.0:
            return []
        wanted: dict[str, set[int]] = {}
        for path in paths:
            base, _, tail = path.rpartition(".microstrain.dof.")
            if base and tail.isdigit():
                wanted.setdefault(base, set()).add(int(tail))
        seeded: list[str] = []
        for base, _ in wanted.items():
            unit = self._strain_unit.get(base)
            if unit is None:
                continue
            dofs = [(k, self._paths[f"{base}.microstrain.dof.{k}"])
                    for k in range(len(unit))]
            if any(self.entries[i].value != 0.0 for _, i in dofs):
                continue
            for k, i in dofs:
                self.entries[i].value = float(microstrain) ** 2 * float(unit[k])
                seeded.append(self.entries[i].path)
        if seeded:
            self._rebuild()
        return seeded

    # -- optimiser interface -------------------------------------------
    @property
    def free_paths(self) -> list[str]:
        return [self.entries[i].path for i in self._free_idx]

    def x0(self) -> np.ndarray:
        return np.array([to_internal(self.entries[i].value, self.entries[i].transform)
                         for i in self._free_idx], dtype=np.float64)

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        lo, hi = [], []
        for i in self._free_idx:
            e = self.entries[i]
            low, high = internal_bounds(e.lo, e.hi, e.transform)
            lo.append(low)
            hi.append(high)
        return np.asarray(lo), np.asarray(hi)

    def decode(self, theta: np.ndarray) -> dict[str, float]:
        """Internal free vector → full physical value dict, via C·p_free + d."""
        p_free = np.array([to_physical(float(t), self.entries[i].transform)
                           for t, i in zip(theta, self._free_idx, strict=True)],
                          dtype=np.float64)
        p = self._C @ p_free + self._d if len(p_free) else self._d
        return {e.path: float(p[i]) for i, e in enumerate(self.entries)}

    def commit(self, theta: np.ndarray) -> None:
        """Write refined values back into the table (used between stages)."""
        values = self.decode(theta)
        for e in self.entries:
            e.value = values[e.path]
        self._rebuild()  # held-source contributions to d follow the new values

    def stderr_physical(self, theta: np.ndarray, stderr_internal: np.ndarray,
                        correlation: np.ndarray | None = None) -> dict[str, float]:
        """Physical esds for every free or tied parameter.

        σ²_phys = diag(C · Cov_free · Cᵀ), where Cov_free is the covariance
        of the *physical* free parameters: the internal esds chain-ruled
        through the transforms, correlated by ``correlation`` when given
        (diagonal otherwise — the pre-v0.3 behaviour).  Identity ties
        thereby report exactly the source esd; general rows get full linear
        propagation including cross terms.  Held parameters are omitted.
        """
        s = self._phys_sigma_free(theta, stderr_internal)
        if correlation is None:
            var = self._C.multiply(self._C) @ (s * s)
        else:
            cov = np.asarray(correlation, dtype=np.float64) * np.outer(s, s)
            var = np.asarray(self._C.multiply(self._C @ cov).sum(axis=1)).ravel()
        var = np.maximum(np.asarray(var).ravel(), 0.0)
        touched = np.diff(self._C.indptr) > 0  # rows with any free source
        return {e.path: float(np.sqrt(var[i]))
                for i, e in enumerate(self.entries) if touched[i]}

    def _phys_sigma_free(self, theta: np.ndarray, stderr_internal: np.ndarray
                         ) -> np.ndarray:
        """Chain-ruled physical esd of each free parameter (θ-column order)."""
        return np.array(
            [abs(dphys_dinternal(float(t), self.entries[i].transform)) * float(sd)
             for t, sd, i in zip(theta, stderr_internal, self._free_idx, strict=True)],
            dtype=np.float64)

    def _cov_free(self, theta: np.ndarray, stderr_internal: np.ndarray,
                  correlation: np.ndarray | None) -> np.ndarray:
        """Covariance of the *physical* free parameters (Cov_free).

        Diagonal from the chain-ruled esds; off-diagonal from ``correlation``
        when given.  This is the exact construction :meth:`stderr_physical`
        uses, so any block extracted from it carries the same Bérar-Lelann
        conditioning as the reported per-parameter esds.
        """
        s = self._phys_sigma_free(theta, stderr_internal)
        if correlation is None:
            return np.diag(s * s)
        return np.asarray(correlation, dtype=np.float64) * np.outer(s, s)

    def physical_covariance(self, theta: np.ndarray, stderr_internal: np.ndarray,
                            correlation: np.ndarray | None,
                            paths: list[str]) -> np.ndarray:
        """Physical covariance sub-block for ``paths`` (free or tied entries).

        Generalises :meth:`stderr_physical` (which returns only the diagonal)
        to the full block ``Cov = C_rows · Cov_free · C_rowsᵀ``, so callers can
        propagate correlated functions of several parameters — e.g. QPA weight
        fractions from the phase scales.  A parameter that was never freed has
        an all-zero ``C`` row, hence a zero covariance row/column (no
        uncertainty), which the caller handles naturally.
        """
        rows = [self._paths[p] for p in paths]
        if not self._free_idx:
            return np.zeros((len(paths), len(paths)), dtype=np.float64)
        cov_free = self._cov_free(theta, stderr_internal, correlation)
        c_rows = self._C[rows, :].toarray()
        return c_rows @ cov_free @ c_rows.T

    def apply_to_models(self, structure: Structure, instrument: Instrument,
                        stderr: dict[str, float] | None = None) -> None:
        """Write current table values back into (copies of) the pydantic models.

        With ``stderr`` (a path → esd map, e.g. from
        :meth:`stderr_physical`) every parameter touched here also gets its
        ``stderr`` set — to ``None`` where the map has no entry, so a stale
        esd from an earlier stage can never survive.  That is what lets the
        CIF exporter write standard uncertainties.
        """
        values = {e.path: e.value for e in self.entries}

        def put(p: Parameter, path: str) -> None:
            p.value = values[path]
            if stderr is not None:
                p.stderr = stderr.get(path)

        for ip, phase in enumerate(structure.phases):
            base = f"phases.{ip}"
            for name in ("a", "b", "c", "alpha", "beta", "gamma"):
                put(getattr(phase.cell, name), f"{base}.cell.{name}")
            put(phase.scale, f"{base}.scale")
            put(phase.extinction, f"{base}.extinction")
            if phase.preferred_orientation is not None:
                put(phase.preferred_orientation.r, f"{base}.preferred_orientation.r")
            put(phase.lor_size, f"{base}.lor_size")
            put(phase.lor_strain, f"{base}.lor_strain")
            put(phase.gauss_size, f"{base}.gauss_size")
            put(phase.gauss_strain, f"{base}.gauss_strain")
            if phase.microstrain is not None:
                for name in S_NAMES:
                    put(getattr(phase.microstrain, name), f"{base}.microstrain.{name}")
            for j, atom in enumerate(phase.atoms):
                # coordinates too — without this, refined positions vanish at
                # the next stage's recompile (models feed compile_phase_sites)
                for name in ("x", "y", "z", "occ", "biso"):
                    put(getattr(atom, name), f"{base}.atoms.{j}.{name}")
                if atom.aniso is not None:
                    for name in U_NAMES:
                        put(getattr(atom.aniso, name), f"{base}.atoms.{j}.{name}")
        put(instrument.zero_shift, "instrument.zero_shift")
        put(instrument.source.polarization, "instrument.polarization")
        for il, line in enumerate(instrument.source.lines):
            put(line.weight, f"instrument.source.lines.{il}.weight")
        for name in ("sample_displacement", "sample_transparency",
                     "axial_sl", "axial_hl"):
            put(getattr(instrument.geometry, name), f"instrument.geometry.{name}")
        for sub, cp in roughness_parameters(instrument.geometry.surface_roughness):
            put(cp, f"instrument.geometry.surface_roughness.{sub}")
        for name in ("u", "v", "w", "x", "y"):
            put(getattr(instrument.profile, name), f"instrument.profile.{name}")
        for sub, cp in _background_parameters(instrument.background):
            put(cp, f"instrument.background.{sub}")
