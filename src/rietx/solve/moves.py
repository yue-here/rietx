"""What a direct-space search moves, and the |F|² it sees (#562 S2a; WP number pending).

A search holds, per replica, one flat vector u of free parameters.  Two kinds
of **unit** own slices of it:

* :class:`FreeSite` — one atom on one Wyckoff class from
  :func:`~rietx.crystallography.site_classes.site_classes`, moving in that
  class's free subspace, x(u) = point + uᵀ·basis (amendment (b) on #562:
  special positions are searched from the start, not deferred).  A class with
  no free parameter is a unit with no slice; it still scatters.
* :class:`FragmentUnit` — a rigid :class:`~rietx.crystallography.fragments.Fragment`
  on the general position: origin o (fractional, 3), rotation vector ω
  (radians, 3) and one angle per named torsion (degrees).  Its atoms sit at
  x_i = o + M⁻¹·Exp(ω)·T_i, with T the template about its centroid after its
  torsions, M the Cartesian frame of
  :func:`~rietx.params.derived.cartesian_frame`, Exp the Rodrigues map of
  :func:`~rietx.crystallography.rotation.matrix_from_vector` and the torsions
  :func:`~rietx.params.bodies.apply_torsions`'s: the map
  :mod:`~rietx.crystallography.bodies` places a body with (WP-1801/1802/1808),
  never a second one.  A fragment on a special position is WP-1807's and is
  not searched here.

**Seeds on a special position are refused by name** (:class:`SearchRefused`,
``"special_position_seed"``).  Every atom's orbit operations are frozen from
its class (the class's coset representatives, so the image count is the
multiplicity for every u, as :meth:`SiteClass.orbit` keeps it).  A seed that
puts an atom on a position more special than its class double-counts an
orbit from the first evaluation, and nothing downstream could tell that from
a solution; a move that reaches one later meets its own images in the clash
term, as the forward model counts them.

**Moves** (:meth:`SearchSpace.propose`) displace one unit per replica by a
Gaussian whose size is a length in Å: σ along each free direction of a site
(per unit length of the basis vector); for a fragment, one block at a time,
chosen uniformly: the origin (σ, Cartesian), the orientation (a left-composed
rotation of σ/r_g radians per component, r_g the template's radius of
gyration, so an atom at r_g moves about σ) or one torsion (σ/r_t radians, r_t
the moving atoms' RMS distance from the axis).  The σ per temperature is the
tempering ladder's, measured (:mod:`~rietx.solve.tempering`).

**The site exchange.**  Two free sites of one class holding different species
swap their parameters: the move #562's 2026-09-30 note named as an unmeasured
lever ("swap-two-atom").  It is measured here: on NAC every seed that missed
the structure had found it with species permuted within a class (Na⁺ and
Al³⁺ on 8a are both ten-electron ions), its RMSD to the truth 0.03 Å with
species ignored, and no budget up to 40 000 sweeps moved it out; the
exchange is the one move that connects those basins.  The exchange is
symmetric (a proposal and its reverse are equally likely), so Metropolis
acceptance keeps detailed balance.

**The structure factor.**  :class:`Scattering` freezes, per atom, its orbit
table Q[n, m] = h_nᵀ·R_m and HT[n, m] = h_n·t_m over the class's coset
operations, and its amplitude occ·f(s)·exp(−B s²) (and occ·f″·exp(−B s²) on a
dispersive source) from
:func:`~rietx.crystallography.structure_factor._orbit_terms`, the forward
model's own expression, read once at build.  With S_j(h) = Σ_m exp(2πi(Q·x_j +
HT)), F = Σ_j a_j·S_j and |F|² = |A|² + |B|², the Friedel average
:func:`~rietx.crystallography.structure_factor.structure_factors_squared`
returns, in its units (electrons², fm²).  A move updates the running sums,
F_new = F_old + a_j·(S_j,new − S_j,old), and :meth:`Scattering.refresh`
recomputes them in full.  The orbit sums dispatch to the compiled kernels
(:func:`~rietx.model.compiled.solve_orbit_sums`,
:func:`~rietx.model.compiled.solve_orbit_sums_one`); where those decline
(``RIETX_COMPILED=0``, or a wheel before 1.4.0) the numpy expression here
runs, and it is their oracle (``tests/test_solve_engine.py``).

**The clash term** is chemistry's (:mod:`~rietx.solve.chemistry`): r₀ from
:func:`~rietx.solve.chemistry.compile_chemistry` over the search's atoms, the
per-site energy from the compiled
:func:`~rietx.model.compiled.solve_clash` or its numpy oracle
:func:`~rietx.solve.chemistry.site_clash`.  Before either is reached,
:func:`~rietx.solve.chemistry.clash_cells_suffice` is asked once at build:
the compiled kernel refuses a cell its 27 cells cannot cover by itself (#1015's
review round), and this check is the same predicate read before a sweep
rather than a refusal mid-run.  The coordination prior is read per candidate
(:meth:`~rietx.solve.chemistry.CompiledChemistry.terms`), not in the move
loop.

Isotropic displacement only: a search refines no ADP, and one B per unit is
declared by the caller.  Nothing here is exported from :mod:`rietx`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from ..crystallography import rotation
from ..crystallography.fragments import Fragment
from ..crystallography.site_classes import SiteClass, site_classes
from ..crystallography.structure_factor import _orbit_terms, compile_phase_sites
from ..crystallography.symmetry import resolve_group, site_orbit
from ..model import compiled
from ..model.restraints import _metric_g
from ..params.bodies import apply_torsions
from ..params.derived import fractional_frame

_CELL = ("a", "b", "c", "alpha", "beta", "gamma")
_TAU = 2.0 * math.pi

Refusal = Literal["special_position_seed", "no_units", "clash_reach", "torsion"]


class SearchRefused(ValueError):
    """The search cannot start as asked; ``reason`` says why.

    ``"special_position_seed"``: a seed puts an atom on a position more special
    than its class (module docstring).  ``"no_units"``: nothing to place.
    ``"clash_reach"``: a clash radius reaches past the 27 cells the clash term
    searches (:func:`~rietx.solve.chemistry.clash_cells_suffice`).
    ``"torsion"``: a torsion names an atom outside its fragment, or turns an
    atom on its own axis.
    """

    def __init__(self, reason: Refusal, message: str):
        super().__init__(message)
        self.reason = reason


# ----------------------------------------------------------------------
# units
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class FreeSite:
    """One atom on one Wyckoff class, moving in the class's free subspace."""

    species: str
    site_class: SiteClass
    label: str = ""
    occ: float = 1.0
    biso: float = 1.0


@dataclass(frozen=True)
class FragmentUnit:
    """A rigid fragment on the general position.

    ``torsions`` are ``(axis_a, axis_b, moves)`` index triples into the
    fragment, as :func:`~rietx.params.bodies.apply_torsions` reads them.
    ``labels`` default to species + index.
    """

    fragment: Fragment
    labels: tuple[str, ...] = ()
    occ: float = 1.0
    biso: float = 1.0
    torsions: tuple[tuple[int, int, tuple[int, ...]], ...] = ()


Unit = FreeSite | FragmentUnit


@dataclass
class _Block:
    """One unit's place in u and in the atom list."""

    unit: Unit
    lo: int                       # u slice
    hi: int
    atoms: np.ndarray             # indices into the atom list
    # fragments only
    template: np.ndarray | None = None      # (n, 3) Å about the centroid
    torsions: tuple = ()                    # (axis_a, axis_b, moves as an index array)
    r_gyr: float = 0.0
    r_tors: np.ndarray | None = None        # (k,) Å
    # free sites only
    lengths: np.ndarray | None = None       # (dof,) Å per unit of each basis vector

    @property
    def n_par(self) -> int:
        return self.hi - self.lo


# ----------------------------------------------------------------------
# the search space
# ----------------------------------------------------------------------
class SearchSpace:
    """Units laid out over one flat parameter vector, for one phase's cell and group.

    ``phase`` carries the cell and the space group (its atoms are not read).
    ``classes`` defaults to :func:`site_classes` of the group; a
    :class:`FreeSite`'s class must be one of them (identity is not required,
    but its operations are what the site is frozen with).
    """

    def __init__(self, units: Sequence[Unit], phase):
        if not units:
            raise SearchRefused("no_units", "a search needs at least one unit to place")
        self.phase = phase
        self.cell = tuple(float(getattr(phase.cell, k).value) for k in _CELL)
        self.group = resolve_group(phase.space_group, phase.symmetry_operations)
        self.classes = site_classes(self.group)
        self.general = max(self.classes, key=lambda c: c.multiplicity)
        self.g = np.asarray(_metric_g(self.cell), dtype=np.float64)
        self.minv = np.asarray(fractional_frame(self.cell), dtype=np.float64)
        self.blocks: list[_Block] = []
        species, labels, occ, biso, classes = [], [], [], [], []
        lo = 0
        for k, unit in enumerate(units):
            first = len(species)
            if isinstance(unit, FreeSite):
                c = unit.site_class
                n = c.dof
                lengths = np.sqrt(np.einsum("ki,ij,kj->k", c.basis.astype(float), self.g,
                                            c.basis.astype(float))) if n else np.zeros(0)
                species.append(unit.species)
                labels.append(unit.label or f"{unit.species}{k + 1}")
                occ.append(float(unit.occ))
                biso.append(float(unit.biso))
                classes.append(c)
                block = _Block(unit, lo, lo + n, np.arange(first, first + 1), lengths=lengths)
            elif isinstance(unit, FragmentUnit):
                frag = unit.fragment
                t = np.asarray(frag.xyz, dtype=np.float64)
                t = t - t.mean(axis=0)
                r_tors = []
                for ia, ib, moves in unit.torsions:
                    mv = np.asarray(moves, dtype=np.intp)
                    if (min(ia, ib, *mv) < 0 or max(ia, ib, *mv) >= len(frag)
                            or ia in mv or ib in mv):
                        raise SearchRefused(
                            "torsion", f"torsion ({ia}, {ib}) of unit {k} names an atom "
                            f"outside its {len(frag)} atoms or turns an axis atom")
                    axis = t[ib] - t[ia]
                    axis = axis / np.linalg.norm(axis)
                    rel = t[mv] - t[ia]
                    perp = rel - np.outer(rel @ axis, axis)
                    r_tors.append(float(np.sqrt(np.mean(np.sum(perp * perp, axis=1)))))
                n = 6 + len(unit.torsions)
                labs = unit.labels or tuple(f"{s}{k + 1}_{i + 1}"
                                            for i, s in enumerate(frag.species))
                for i, s in enumerate(frag.species):
                    species.append(s)
                    labels.append(labs[i])
                    occ.append(float(unit.occ))
                    biso.append(float(unit.biso))
                    classes.append(self.general)
                block = _Block(unit, lo, lo + n, np.arange(first, first + len(frag)),
                               template=t,
                               torsions=tuple((int(ia), int(ib), np.asarray(mv, dtype=np.intp))
                                              for ia, ib, mv in unit.torsions),
                               r_gyr=max(float(np.sqrt(np.mean(np.sum(t * t, axis=1)))), 1e-6),
                               r_tors=np.array(r_tors))
            else:
                raise TypeError(f"unit {k} is a {type(unit).__name__}, not a FreeSite "
                                "or a FragmentUnit")
            self.blocks.append(block)
            lo += block.n_par
        self.n_par = lo
        self.species = species
        self.labels = labels
        self.occ = np.array(occ)
        self.biso = np.array(biso)
        self.atom_class = classes
        self.n_atoms = len(species)
        self.unit_of_atom = np.concatenate([np.full(len(b.atoms), k, dtype=np.intp)
                                            for k, b in enumerate(self.blocks)])
        # units that move: a fixed site has no slice
        self.movable = np.array([k for k, b in enumerate(self.blocks) if b.n_par > 0],
                                dtype=np.intp)
        mults = np.array([c.multiplicity for c in classes], dtype=np.intp)
        self.img_hi = np.cumsum(mults)
        self.img_lo = self.img_hi - mults
        self.rot = np.concatenate([c.coset_rot for c in classes]).astype(np.float64)
        self.tran = np.concatenate([c.coset_tran for c in classes]).astype(np.float64)
        self.site_of_image = np.repeat(np.arange(self.n_atoms), mults)
        self._partners = [np.array([o for o, ob in enumerate(self.blocks)
                                    if o != k and isinstance(b.unit, FreeSite)
                                    and isinstance(ob.unit, FreeSite)
                                    and ob.unit.site_class is b.unit.site_class
                                    and ob.n_par > 0
                                    and ob.unit.species != b.unit.species], dtype=np.intp)
                          for k, b in enumerate(self.blocks)]

    # -- coordinates -----------------------------------------------------------
    def xyz(self, u: np.ndarray) -> np.ndarray:
        """Asymmetric-unit coordinates (R, n_atoms, 3) for u (R, n_par)."""
        u = np.atleast_2d(np.asarray(u, dtype=np.float64))
        out = np.empty((u.shape[0], self.n_atoms, 3))
        for k in range(len(self.blocks)):
            out[:, self.blocks[k].atoms] = self.unit_xyz(u, k)
        return out

    def unit_xyz(self, u: np.ndarray, k: int) -> np.ndarray:
        """Unit ``k``'s atoms (R, n_k, 3) for u (R, n_par)."""
        b = self.blocks[k]
        p = u[:, b.lo:b.hi]
        if isinstance(b.unit, FreeSite):
            c = b.unit.site_class
            x = np.broadcast_to(c.point, (len(u), 3)).astype(np.float64)
            if c.dof:
                x = x + p @ c.basis.astype(np.float64)
            return x[:, None, :]
        out = np.empty((len(u), len(b.atoms), 3))
        tors = b.torsions
        for r in range(len(u)):
            pts = b.template if not tors else apply_torsions(b.template, tors, p[r, 6:])
            rot = np.asarray(rotation.matrix_from_vector(p[r, 3:6]), dtype=np.float64)
            out[r] = p[r, :3] + pts @ (self.minv @ rot).T
        return out

    def images(self, xyz: np.ndarray) -> np.ndarray:
        """Every atom of the cell (R, n_images, 3), site by site, unwrapped."""
        x = np.repeat(xyz, self.img_hi - self.img_lo, axis=1)               # (R, M, 3)
        return np.einsum("mij,rmj->rmi", self.rot, x) + self.tran

    # -- starts and moves ------------------------------------------------------
    def random(self, rng: np.random.Generator, n: int) -> np.ndarray:
        """``n`` uniform starts (n, n_par): every free coordinate uniform over its
        period, every fragment orientation uniform over rotations, every torsion
        uniform over the circle."""
        u = np.zeros((n, self.n_par))
        for b in self.blocks:
            if isinstance(b.unit, FreeSite):
                u[:, b.lo:b.hi] = rng.uniform(0.0, 1.0, (n, b.n_par))
                continue
            u[:, b.lo:b.lo + 3] = rng.uniform(0.0, 1.0, (n, 3))
            q = rng.normal(size=(n, 4))
            q /= np.linalg.norm(q, axis=1, keepdims=True)
            for r in range(n):
                u[r, b.lo + 3:b.lo + 6] = np.asarray(
                    rotation.vector_from_quaternion(q[r]), dtype=np.float64)
            u[:, b.lo + 6:b.hi] = rng.uniform(-180.0, 180.0, (n, b.n_par - 6))
        return u

    def wrap(self, u: np.ndarray) -> np.ndarray:
        """Free coordinates and fragment origins into [0, 1), torsions into
        [−180, 180); a site's basis vectors are integer, so u has period 1."""
        u = np.array(u, dtype=np.float64)
        for b in self.blocks:
            if isinstance(b.unit, FreeSite):
                u[:, b.lo:b.hi] %= 1.0
            else:
                u[:, b.lo:b.lo + 3] %= 1.0
                u[:, b.lo + 6:b.hi] = (u[:, b.lo + 6:b.hi] + 180.0) % 360.0 - 180.0
        return u

    def partners(self, k: int) -> np.ndarray:
        """Units a site-exchange move may swap with unit ``k``: free sites of the
        same class holding another species."""
        return self._partners[k]

    def propose(self, u: np.ndarray, unit_of_rep: np.ndarray, step: np.ndarray,
                rng: np.random.Generator, *, exchange: float = 0.0
                ) -> tuple[np.ndarray, list[np.ndarray]]:
        """u with unit ``unit_of_rep[r]`` of replica r displaced by σ = ``step[r]`` Å
        (module docstring), every other parameter bit-identical, and the atoms
        each replica's move touched.  With probability ``exchange`` a free site
        with :meth:`partners` instead swaps its parameters with one of them."""
        new = np.array(u, dtype=np.float64)
        moved: list[np.ndarray] = []
        for r, (k, s) in enumerate(zip(unit_of_rep, step, strict=True)):
            b = self.blocks[int(k)]
            if isinstance(b.unit, FreeSite):
                partners = self._partners[int(k)]
                if len(partners) and exchange > 0.0 and rng.random() < exchange:
                    o = self.blocks[int(partners[rng.integers(len(partners))])]
                    new[r, b.lo:b.hi], new[r, o.lo:o.hi] = u[r, o.lo:o.hi], u[r, b.lo:b.hi]
                    moved.append(np.array([b.atoms[0], o.atoms[0]]))
                    continue
                new[r, b.lo:b.hi] += s * rng.normal(size=b.n_par) / b.lengths
                new[r, b.lo:b.hi] %= 1.0
                moved.append(b.atoms)
                continue
            which = int(rng.integers(2 + len(b.unit.torsions)))
            if which == 0:
                new[r, b.lo:b.lo + 3] = (new[r, b.lo:b.lo + 3]
                                         + self.minv @ (s * rng.normal(size=3))) % 1.0
            elif which == 1:
                dw = (s / b.r_gyr) * rng.normal(size=3)
                new[r, b.lo + 3:b.lo + 6] = np.asarray(
                    rotation.compose_vectors(dw, new[r, b.lo + 3:b.lo + 6]), dtype=np.float64)
            else:
                t = which - 2
                ang = new[r, b.lo + 6 + t] + math.degrees(s / max(b.r_tors[t], 1e-6)) \
                    * rng.normal()
                new[r, b.lo + 6 + t] = (ang + 180.0) % 360.0 - 180.0
            moved.append(b.atoms)
        return new, moved

    def check_seed(self, u: np.ndarray) -> None:
        """Refuse a seed that puts an atom on a position more special than its
        class (module docstring), naming the atom."""
        xyz = self.xyz(u)
        for r in range(len(xyz)):
            for j in range(self.n_atoms):
                orbit = site_orbit(self.group, xyz[r, j])
                want = self.atom_class[j].multiplicity
                if orbit.multiplicity != want:
                    raise SearchRefused(
                        "special_position_seed",
                        f"seed {r} puts {self.labels[j]} at {np.round(xyz[r, j] % 1.0, 4)}, "
                        f"a {orbit.multiplicity}-fold position, where its class is "
                        f"{want}-fold: its orbit would be counted "
                        f"{want // max(orbit.multiplicity, 1)} times")

    def search_phase(self, xyz: np.ndarray | None = None):
        """The phase with the search's atoms at ``xyz`` (n_atoms, 3), default each
        class's representative point: for amplitudes, chemistry and output."""
        from ..schemas.common import Parameter
        from ..schemas.structure import Atom

        if xyz is None:
            xyz = np.array([c.position(np.full(c.dof, 0.0137)) for c in self.atom_class])
        atoms = [Atom(label=lab, species=s, x=Parameter(value=float(x[0] % 1.0)),
                      y=Parameter(value=float(x[1] % 1.0)), z=Parameter(value=float(x[2] % 1.0)),
                      occ=Parameter(value=float(o)), biso=Parameter(value=float(bi)))
                 for lab, s, x, o, bi in zip(self.labels, self.species, xyz, self.occ,
                                             self.biso, strict=True)]
        return self.phase.model_copy(update={"atoms": atoms, "rigid_bodies": []}, deep=True)


# ----------------------------------------------------------------------
# the radiation and the structure factor
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Radiation:
    """What the source decides about the amplitudes: neutron or X-ray, and the
    X-ray dispersion per species (``None`` when the source declares none)."""

    neutron: bool = False
    f_anom: Mapping[str, complex] | None = None

    @classmethod
    def from_instrument(cls, instrument, species: Sequence[str]) -> Radiation:
        """The choice :func:`~rietx.model.forward.compile_model` makes per phase,
        read the same way: a ``neutron_cw`` source is neutron, and an X-ray
        source with ``dispersion`` set resolves f′ + i·f″ at its lines."""
        from ..crystallography.dispersion import resolve as resolve_dispersion

        src = instrument.source
        neutron = src.kind == "neutron_cw"
        f_anom = None
        if src.dispersion is not None and not neutron:
            lams = tuple(line.wavelength.value for line in src.lines)
            f_anom = resolve_dispersion(list(species), lams, src.dispersion.overrides)
        return cls(neutron=neutron, f_anom=f_anom)


class Scattering:
    """|F|² over a frozen reflection list for a :class:`SearchSpace`, with
    running orbit sums for one-unit moves (module docstring)."""

    def __init__(self, space: SearchSpace, hkl: np.ndarray, d: np.ndarray,
                 radiation: Radiation = Radiation()):
        self.space = space
        h = np.asarray(hkl, dtype=np.float64)
        self.hkl = h
        self.d = np.asarray(d, dtype=np.float64)
        self.q = np.ascontiguousarray(np.einsum("nk,mkc->nmc", h, space.rot))  # (N, M, 3)
        self.ht = np.ascontiguousarray(h @ space.tran.T)                     # (N, M)
        phase = space.search_phase()
        sites = compile_phase_sites(phase, dict(radiation.f_anom) if radiation.f_anom else None,
                                    neutron=radiation.neutron)
        stol = 1.0 / (2.0 * self.d)
        xyz0 = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
        amp_a, amp_b = [], []
        for j in range(space.n_atoms):
            a, b, _phase, dw = _orbit_terms(h, stol, sites, xyz0, space.occ, space.biso,
                                            None, None, j)
            if dw is not None:            # pragma: no cover - isotropic by construction
                raise ValueError("an anisotropic site reached the search")
            amp_a.append(np.asarray(a, dtype=np.float64))
            if b is not None:
                amp_b.append(np.asarray(b, dtype=np.float64))
        self.amp_a = np.array(amp_a)                                          # (n_atoms, N)
        self.amp_b = np.array(amp_b) if amp_b else None
        self.compiled_used = {"orbit_sums": 0, "orbit_sums_one": 0}

    # -- orbit sums ------------------------------------------------------------
    def orbit_sums(self, xyz: np.ndarray, atoms: np.ndarray) -> np.ndarray:
        """S_j(h), complex (R, len(atoms), N), for ``xyz`` (R, n_atoms, 3)."""
        xyz = np.ascontiguousarray(xyz, dtype=np.float64)
        atoms = np.asarray(atoms, dtype=np.intp)
        got = compiled.solve_orbit_sums(self.q, self.ht, xyz, self.space.img_lo,
                                        self.space.img_hi, atoms)
        if got is not None:
            self.compiled_used["orbit_sums"] += 1
            return got[0] + 1j * got[1]
        return self._orbit_sums_numpy(xyz, atoms)

    def orbit_sums_one(self, xyz: np.ndarray, atom_of_rep: np.ndarray) -> np.ndarray:
        """S of atom ``atom_of_rep[r]`` in replica r, complex (R, N)."""
        xyz = np.ascontiguousarray(xyz, dtype=np.float64)
        atom_of_rep = np.asarray(atom_of_rep, dtype=np.intp)
        got = compiled.solve_orbit_sums_one(self.q, self.ht, xyz, self.space.img_lo,
                                            self.space.img_hi, atom_of_rep)
        if got is not None:
            self.compiled_used["orbit_sums_one"] += 1
            return got[0] + 1j * got[1]
        out = np.empty((len(xyz), len(self.d)), dtype=np.complex128)
        for r, j in enumerate(atom_of_rep):
            out[r] = self._orbit_sums_numpy(xyz[r:r + 1], np.array([j]))[0, 0]
        return out

    def _orbit_sums_numpy(self, xyz: np.ndarray, atoms: np.ndarray) -> np.ndarray:
        """The numpy path and the kernels' oracle: Σ_m cos + i·sin of
        2π(Q[n, m]·x_j + HT[n, m]) over site j's images (the geometrical
        structure factor of one orbit; Giacovazzo et al., Fundamentals of
        Crystallography, 3rd ed., OUP 2011)."""
        out = np.empty((len(xyz), len(atoms), len(self.d)), dtype=np.complex128)
        for a, j in enumerate(atoms):
            lo, hi = self.space.img_lo[j], self.space.img_hi[j]
            arg = _TAU * (np.einsum("nmc,rc->rnm", self.q[:, lo:hi], xyz[:, j])
                          + self.ht[None, :, lo:hi])
            out[:, a] = np.cos(arg).sum(axis=2) + 1j * np.sin(arg).sum(axis=2)
        return out

    # -- amplitudes ------------------------------------------------------------
    def sums(self, xyz: np.ndarray) -> np.ndarray:
        """Every atom's S, complex (R, n_atoms, N)."""
        return self.orbit_sums(xyz, np.arange(self.space.n_atoms))

    def amplitudes(self, s: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
        """(A, B), each complex (R, N), from all atoms' S (R, n_atoms, N)."""
        a = np.einsum("jn,rjn->rn", self.amp_a, s)
        b = None if self.amp_b is None else np.einsum("jn,rjn->rn", self.amp_b, s)
        return a, b

    @staticmethod
    def f2_of(a: np.ndarray, b: np.ndarray | None) -> np.ndarray:
        f2 = a.real * a.real + a.imag * a.imag
        if b is not None:
            f2 = f2 + b.real * b.real + b.imag * b.imag
        return f2

    def f2(self, xyz: np.ndarray) -> np.ndarray:
        """|F|² (R, N) from scratch."""
        return self.f2_of(*self.amplitudes(self.sums(np.atleast_3d(xyz)
                                                     if np.ndim(xyz) == 3 else xyz[None])))


# ----------------------------------------------------------------------
# the clash term over the search's atoms
# ----------------------------------------------------------------------
@dataclass
class Clash:
    """The clash term on the search's atoms: r₀ per atom pair from
    :func:`~rietx.solve.chemistry.compile_chemistry`, and its notes."""

    space: SearchSpace
    r0: np.ndarray
    sigma: float
    weight: float
    notes: list[str] = field(default_factory=list)
    compiled_used: int = 0

    @classmethod
    def build(cls, space: SearchSpace, priors) -> Clash:
        """The clash term for ``priors``, a :class:`~rietx.solve.chemistry.SolvePriors`
        the caller declares: its σ, radius fraction and weights have no default
        (#1016's review round), so neither has this."""
        from .chemistry import clash_cells_suffice, compile_chemistry

        try:
            chem = compile_chemistry(space.search_phase(), priors)
        except ValueError as exc:
            if "27 cells" in str(exc):
                raise SearchRefused("clash_reach", str(exc)) from exc
            raise
        if not clash_cells_suffice(space.g, chem.r0):      # pragma: no cover - chem refuses first
            raise SearchRefused("clash_reach", "a clash radius reaches past the 27 cells")
        return cls(space, chem.r0, float(priors.sigma), float(priors.weights.clash),
                   list(chem.notes))

    @property
    def active(self) -> bool:
        return self.weight > 0.0 and bool(np.any(self.r0 > 0.0))

    def site(self, pos: np.ndarray, moved: np.ndarray, w_same: float) -> np.ndarray:
        """Per-replica energy of atom ``moved[r]``'s images against the cell."""
        from .chemistry import site_clash

        site_of = self.space.site_of_image
        got = compiled.solve_clash(pos, site_of, np.asarray(moved, dtype=np.intp),
                                   self.space.g, self.r0, self.sigma, w_same)
        if got is not None:
            self.compiled_used += 1
            return got
        return site_clash(pos, site_of, moved, self.space.g, self.r0, self.sigma, w_same)

    def total(self, xyz: np.ndarray) -> np.ndarray:
        """The structure's clash energy per replica (R,), each contact once."""
        pos = self.space.images(xyz)
        n_rep, n = len(pos), self.space.n_atoms
        stack = np.repeat(pos, n, axis=0)
        moved = np.tile(np.arange(n), n_rep)
        return 0.5 * self.site(stack, moved, 1.0).reshape(n_rep, n).sum(axis=1)


__all__ = ["Clash", "FragmentUnit", "FreeSite", "Radiation", "Scattering",
           "SearchRefused", "SearchSpace"]
