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
from ..crystallography.symmetry import (
    cell_constraints,
    check_cell_angles,
    get_spacegroup,
    rotation_matrices,
)
from ..crystallography.wyckoff import adp_basis, coordinate_basis, stabilizer_rotations
from ..schemas.common import Parameter
from ..schemas.instrument import (
    CAPILLARY_OFFSETS,
    BackgroundChebyshev,
    BackgroundPSpline,
    Instrument,
)
from ..schemas.structure import Structure
from .transforms import dphys_dinternal, internal_bounds, to_internal, to_physical

#: Dot-path suffix of a source line's wavelength row.  One authority for the
#: spelling, since three places test for it: the collector, the freedom check
#: below and the ``WAVELENGTH_CALIBRATION`` diagnostic in ``multi.py``.
WAVELENGTH_SUFFIX = ".wavelength"


def _is_wavelength(path: str) -> bool:
    return (path.startswith("instrument.source.lines.")
            and path.endswith(WAVELENGTH_SUFFIX))


def check_wavelength_freedom(free_wavelengths: list[str], n_wavelengths: int,
                             n_histograms: int, *,
                             cell_shared: bool = True) -> None:
    """Refuse a wavelength freedom the data cannot support.  Three cases.

    A powder pattern measures d = λ/(2 sin θ), which fixes only the *product*
    λ·(1/d) — so for **one** histogram a free λ beside a free cell is a flat
    direction, exactly, and no amount of data removes it.  Across **N**
    histograms of one specimen sharing one cell the degeneracy breaks: holding
    one λ pins the cell's scale, and the remaining N − 1 are then
    over-determined by that shared cell and genuinely measurable.  Holding
    *all* of them instead forces every monochromator's calibration error into
    the shared cell; freeing all of them restores the flat direction.

    **The shared cell is the whole mechanism, so it is part of the rule**:

        a free wavelength requires its histogram's cell to be *shared* with at
        least one histogram whose wavelength is held.

    "Exactly one held, at most N − 1 free" is that statement's special case
    when every histogram shares one cell, which is the default
    (:class:`~rietx.params.multi.SharingMap` shares everything that is not
    ``instrument.*`` or ``*.scale``).  Un-share the cell — a legitimate thing to
    want, when two histograms are two preparations — and the degeneracy of a
    single-histogram fit is back inside the joint one, per histogram, which is
    why ``cell_shared=False`` refuses every free λ rather than letting the fit
    wander.

    **Which one to hold is not arbitrary**: hold the wavelength of the
    histogram that determines the cell.  On a synchrotron-plus-neutron pair
    that is the synchrotron — its wavelength calibration is the better known
    *and* its angular resolution makes its cell the better determined — and the
    neutron wavelengths then refine against a cell the X-ray data has pinned,
    which is the only way their monochromator calibrations can be measured at
    all.

    This is :class:`~rietx.schemas.instrument.EmissionLine`'s weight convention
    one rank up — one member of a set pinned to fix a scale the data cannot
    set, the rest free — and the same argument fixes *where* each is enforced.
    A line weight's scale lives inside one source, so line 0 can be locked in
    the collector.  A wavelength's scale lives in the *cell*, which is shared
    across instruments, so no single instrument can count the set and the check
    has to sit at the two constructors that see it: :class:`ParameterTable`
    (which sees one instrument, hence always the N = 1 case) and
    :class:`~rietx.params.multi.MultiParameterTable` (which sees all of them).
    That is why this is a function and not a validator on ``EmissionLine``.

    ``free_wavelengths`` are the free wavelength paths, spelled as the caller's
    own surface spells them; ``n_wavelengths`` is how many wavelength rows the
    whole problem has and ``n_histograms`` how many patterns it stacks.

    **Scope: constant-wavelength only.**  The same fence generalises verbatim to
    a time-of-flight multi-bank fit, where each bank carries its own DIFC
    calibration and exactly one of them must be held to pin the cell; nothing
    here implements TOF.
    """
    if not free_wavelengths:
        return
    if not cell_shared:
        raise ValueError(
            f"{free_wavelengths[0]} cannot vary while the cell is "
            "per-histogram: λ is measurable only against a cell some *other* "
            "histogram's held wavelength has pinned, so a histogram with its "
            "own cell is back in the single-histogram degeneracy — inside a "
            "joint fit, where it looks solved.  Share the cell "
            "(SharingMap's default does) or hold every wavelength")
    if n_histograms < 2:
        raise ValueError(
            f"{free_wavelengths[0]} cannot vary in a single-histogram fit: "
            "d = λ/(2 sin θ) fixes only the product, so a free wavelength "
            "beside a free cell is an exactly flat direction — the same "
            "degeneracy that makes a certified standard's cell the thing you "
            "hold in order to calibrate λ.  It becomes measurable only in a "
            "joint fit of several histograms of one specimen sharing one cell "
            "(rietx.refine_multi), where one wavelength is held and the rest "
            "are free")
    if len(free_wavelengths) >= n_wavelengths:
        raise ValueError(
            f"{len(free_wavelengths)} of {n_wavelengths} wavelengths are "
            f"free; hold one.  Across {n_histograms} histograms of one "
            "specimen the shared cell makes N − 1 wavelengths measurable, but "
            "only because the held one pins the cell's scale — free them all "
            "and the flat direction of a single-histogram fit is back.  Hold "
            f"{sorted(free_wavelengths)[0]} (the convention is to hold the "
            "best-calibrated histogram's) and leave the others free")


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


#: Cell parameter names in table order — lengths first, then angles.
_CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")

#: Fraction of the value a stage *starts from* that a cell length may travel
#: within that stage, and an additive pad in Å so a small cell is not held
#: tighter than a large one in absolute terms.
CELL_WINDOW_FRACTION = 0.05
CELL_WINDOW_PAD_A = 0.05

#: The same window for a cell angle, in degrees.
CELL_WINDOW_ANGLE_DEG = 2.0

#: Absolute floor on a cell length (Å).  TOPAS's number; no crystal has a
#: lattice repeat this short, so it is a floor on nonsense rather than a
#: refinement bound.
CELL_MIN_LENGTH_A = 1.5

#: A cell angle is degenerate at 0° and 180° — the metric tensor is singular
#: there — so the window is clipped inside them.
_ANGLE_MIN_DEG = 1.0
_ANGLE_MAX_DEG = 179.0


def _cell_parameter_name(path: str, *, phases: set[int]) -> str | None:
    """``"phases.0.cell.a"`` → ``"a"`` when phase 0 is in ``phases``, else None.

    Read off the path rather than recorded on the :class:`Entry`, because the
    window is applied at the optimiser interface and the entries there arrive
    from :meth:`ParameterTable.bounds` with nothing but their paths to go on.
    """
    parts = path.split(".")
    if len(parts) == 4 and parts[0] == "phases" and parts[2] == "cell":
        if parts[3] not in _CELL_NAMES:
            return None
        try:
            ip = int(parts[1])
        except ValueError:
            return None
        return parts[3] if ip in phases else None
    return None


def cell_window(name: str, value: float, lo: float, hi: float) -> tuple[float, float]:
    """The default bounds on one cell parameter, anchored at ``value``.

    **Why a cell needs a default bound at all.**  Every structural parameter of
    a phase reaches the pattern only through ``scale × |F|² × profile``, so a
    phase whose scale has fallen to its floor contributes a *flat direction*:
    moving its cell changes the calculated pattern by nothing, the Jacobian
    column is zero to within noise, and the trust region wanders along it.  The
    fit still reports ``converged`` — the runaway parameter genuinely does not
    affect Rwp — while the reflection count grows with the cell volume until
    :func:`~rietx.crystallography.symmetry.generate_reflections` refuses
    outright, hundreds of stages downstream of the cause.  Measured in WP-1110:
    an absent phase went 5.2 → 25.6 Å in one synthetic fit (Rwp 0.0415,
    ``converged``), and two independent agents drove real phases to a ≈ 39 293 Å
    and a ≈ 40 000 Å on a 68-pattern series.

    **The shape is TOPAS's** (TOPAS-Academic v8 Technical Reference § 2.17,
    Table 2-1), which bounds ``a, b, c`` by ``Max(1.5, 0.995·Val − 0.05)`` to
    ``1.005·Val + 0.05`` and the angles by ``Val ± 0.2``, re-evaluating ``Val``
    every iteration — *"hard limits are avoided where possible; instead,
    parameter values move within a range during an iteration."*  A moving
    window is not available here: a stage hands ``scipy.optimize.least_squares``
    one fixed ``bounds`` pair.  So the window is re-anchored at every **stage**
    compile instead — this table is rebuilt there, and ``apply_to_models``
    writes back only ``Parameter.value``, so the window never enters the stored
    structure and a cell that legitimately drifts across a series re-anchors on
    every stage of every pattern.

    That makes the fraction a stage's worth of TOPAS travel rather than an
    iteration's, and 0.5 % per iteration compounds to 5.1 % over ten.  WP-1110
    measured the other side of it: across 51 stage transitions of the 11-BM NAC
    and SRM 660c protocols the widest honest single-stage move was 2.8e-4
    (median 9.2e-8), a synthetic LaB₆ started 1 % wrong closed the whole gap in
    one stage at 9.9e-3, and started 3 % wrong the fit failed on its own (Rwp
    0.96) with the basin, not any bound, as the obstacle.  So
    :data:`CELL_WINDOW_FRACTION` clears the widest legitimate single-stage move
    by 5× and the real-protocol one by 180×.

    **A finite stored bound is the caller's claim and is kept**, per side —
    TOPAS's *"user defined min/max limits override the defaults"*.  Only an
    infinite side is a side on which nobody made a claim, and ±inf is what a
    :class:`~rietx.schemas.common.Parameter` carries when its bounds were never
    set.  That test is used rather than ``model_fields_set`` because it has to
    survive a JSON round trip, where every field arrives "set".

    **It is applied only to phases the data cannot see** — the set
    ``run_least_squares`` freezes through
    :meth:`ParameterTable.freeze_cell_windows`, off
    :meth:`~rietx.model.forward.CompiledModel.phase_support` — and that
    restriction is measured, not conservatism.  A window is not free: scipy's
    TRF derives its per-coordinate trust-region scale from the distance to the
    bounds, so bounding a cell changes the *step* the solver takes in it even
    when the bound is never reached.  Measured on the IUCr round robin's
    chained ``cpd-1c``, whose cell finishes 0.24 Å inside a ±5 % window and
    never touches it: windowing every phase took the collapsed warm refit from
    82 iterations to its 400-iteration budget, and it stopped at Rwp 0.1501
    against 0.1079 — just good enough to clear ``sequential``'s reseed fence, so
    the pattern was accepted rather than rescued and its corundum fraction came
    back 9.04 wt % against 6.30. A bound that silently degrades a fit nothing
    reports is the failure this WP exists to remove, not a cost worth paying on
    phases that were never going to run away.

    (The same sweep found ±10 % and wider *beating* unbounded on that pattern —
    82 iterations against 641, same answer — because finite bounds precondition
    a badly-scaled problem.  That is a speed lead for the v1.1 harness WPs, not
    something to take here: a correction does not ship on an Rwp comparison, and
    this one's evidence is a diagnostic.)
    """
    if name in ("alpha", "beta", "gamma"):
        window_lo = max(_ANGLE_MIN_DEG, value - CELL_WINDOW_ANGLE_DEG)
        window_hi = min(_ANGLE_MAX_DEG, value + CELL_WINDOW_ANGLE_DEG)
    else:
        window_lo = max(CELL_MIN_LENGTH_A,
                        value * (1.0 - CELL_WINDOW_FRACTION) - CELL_WINDOW_PAD_A)
        window_hi = value * (1.0 + CELL_WINDOW_FRACTION) + CELL_WINDOW_PAD_A
    # never propose a window that excludes where the parameter already is: a
    # cell below the floor is a model to refuse elsewhere, not a bound to raise
    # on here (ParameterTable has no diagnostics channel — the rule in
    # crystallography.cif one rank up)
    window_lo, window_hi = min(window_lo, value), max(window_hi, value)
    return (window_lo if lo == -np.inf else lo,
            window_hi if hi == np.inf else hi)


class ParameterTable:
    def __init__(self, structure: Structure, instrument: Instrument, *,
                 joint: bool = False):
        #: ``True`` when this table is one histogram of a joint fit, so the
        #: wavelength count is somebody else's to make —
        #: :class:`~rietx.params.multi.MultiParameterTable`, the only object
        #: that can see the whole set (:func:`check_wavelength_freedom`).
        #: ``False`` (the default) is a single-histogram fit, where a free
        #: wavelength is refused here, in ``__init__``, like every other
        #: symmetry-of-the-problem refusal.
        self._joint = joint
        self.entries: list[Entry] = []
        #: phase base path → the Stephens DOF vector of the *unit* isotropic
        #: limit (1 ppm), kept so :meth:`seed_stephens` can put a freed block
        #: on the isotropic ray without rebuilding the symmetry basis
        self._strain_unit: dict[str, np.ndarray] = {}
        #: phases whose cells take the default window this stage, or None for
        #: "no claim made" — see :meth:`freeze_cell_windows`
        self._cell_window_phases: set[int] | None = None
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
            # The cell ties come from the *setting*, not from the crystal system
            # alone: a c-unique monoclinic symbol fixes β, not γ, and an R group
            # on rhombohedral axes ties c←a and α=β=γ rather than leaving c free
            # (WP-1036, crystallography.symmetry.CellConstraints).
            constraints = cell_constraints(sg)
            check_cell_angles(sg, {name: getattr(phase.cell, name).value
                                   for name in ("alpha", "beta", "gamma")})
            base = f"phases.{ip}"
            for name in _CELL_NAMES:
                p: Parameter = getattr(phase.cell, name)
                if name in constraints.ties:
                    self._add(f"{base}.cell.{name}", p, tie=AffineTie.identity(
                        f"{base}.cell.{constraints.ties[name]}"))
                elif name in constraints.fixed_angles:
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
        # K is a fact about the radiation, not about this instrument, wherever
        # the radiation pins it.  A neutron beam is not polarised the way the
        # Thomson cross-section polarises X-rays, so Lp collapses to the bare
        # Lorentz factor at K = 1 — and a *free* entry there is worse than a
        # dead column: Lp(2θ, K) does move the pattern, so the solver would buy
        # Rwp by refining a term whose value the physics already knows.
        # Force-fixed rather than merely unfree, the WP-1073 rule — a parameter
        # the forward branch cannot legitimately use must be locked, or
        # ``set_vary`` frees it and nothing objects.
        self._add("instrument.polarization", instrument.source.polarization,
                  force_fixed=instrument.source.kind != "xray_cw")
        for il, line in enumerate(instrument.source.lines):
            # line 0 defines the intensity scale: its weight is degenerate with
            # the phase scale factors, so it is always held fixed
            self._add(f"instrument.source.lines.{il}.weight", line.weight,
                      force_fixed=(il == 0))
        # The wavelength, and the mirror image of the weight rule above it.  A
        # line weight's scale lives inside this source, so **line 0** is the one
        # that must be held; a wavelength's scale lives in the *cell*, which may
        # be shared across histograms this table cannot see, so line 0 is the
        # one that may be *free* — and only when somebody else is counting.
        #
        # Two locks and one refusal, in the shape ``CAPILLARY_OFFSETS`` uses
        # just below.  Lines 1+ are force-fixed unconditionally: within one
        # source the lines' wavelength *ratio* is atomic physics (the NIST
        # column in ``schemas.instrument._KA_DOUBLETS`` is quoted for exactly
        # this reason, ~20 ppm), so a free secondary line is a second flat
        # direction beside the first — the WP-1073 rule that a parameter which
        # cannot legitimately move is force-fixed rather than merely unfree.  In
        # a single-histogram table *every* line is force-fixed, because there λ
        # is exactly degenerate with the cell whatever the data; that is what
        # lets ``ParameterRow.held_because`` tell the truth about it without a
        # fourth held-reason, and what stops a glob freeing it by accident.  And
        # a *declared* ``vary=True`` there is refused by name rather than
        # quietly swallowed, because it is a claim the caller made.
        wl_params = list(instrument.source.wavelength_parameters)
        if not self._joint:
            check_wavelength_freedom(
                [f"instrument.source.lines.{il}.wavelength"
                 for il, p in enumerate(wl_params) if p.vary],
                len(wl_params), 1)
        for il, wl in enumerate(wl_params):
            self._add(f"instrument.source.lines.{il}.wavelength", wl,
                      force_fixed=(il > 0 or not self._joint))
        geom = instrument.geometry
        for name in ("sample_displacement", "sample_transparency",
                     "axial_sl", "axial_hl"):
            self._add(f"instrument.geometry.{name}", getattr(geom, name),
                      force_fixed=(geom.kind != "bragg_brentano"
                                   and name.startswith("sample_")))
        for name in CAPILLARY_OFFSETS:
            offset = getattr(geom, name)
            # eq (4) divides by R.  Geometry's validator refuses a *stored*
            # free offset without one, but ``vary`` set after construction
            # re-runs no validator, and this is the last gate before a solve —
            # so refuse here too, naming the field rather than quietly holding
            # the parameter (a held aberration reads as "measured zero").
            usable = bool(geom.kind == "debye_scherrer"
                          and geom.goniometer_radius_mm)
            if offset.vary and not usable:
                raise ValueError(
                    f"instrument.geometry.{name} cannot vary without "
                    f"goniometer_radius_mm: eq (4) is "
                    f"Δ2θ = (−a·sin2θ + b·cos2θ)/R and R is unset")
            # force-fixed rather than merely unfree when R is missing, because
            # ``_position_shift_deg`` skips the term without one: a free entry
            # there would be a dead column — a parameter the solver moves and
            # the model does not read.
            self._add(f"instrument.geometry.{name}", offset,
                      force_fixed=not usable)
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

    def refresh_ties(self) -> None:
        """Recompute every tied entry's value from its sources.

        :meth:`commit` does this as a side effect of decoding θ, which is the
        only way values change *during* a refinement.  A direct edit of a source
        value — ``Refinement.set_values`` — has no θ to decode, and without this
        the dependents would keep the values they were collected with: setting
        ``a`` on a cubic phase would leave ``b`` and ``c`` behind, silently
        breaking the symmetry the tie exists to enforce.

        One pass suffices: :meth:`_flatten` resolves each tie onto *untied*
        entries, so no dependent is read before it is written.
        """
        self._rebuild()
        for e in self.entries:
            if e.tie is not None:
                terms, const = self._flatten(e.tie, (e.path,))
                e.value = const + sum(c * self.entries[j].value for j, c in terms)
        self._rebuild()  # held tied entries contribute to d through their values

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

    @property
    def moving_paths(self) -> list[str]:
        """Every path this table can move — the free entries *and* their ties.

        ``free_paths`` answers "which entries are columns of θ"; this answers
        "which physical values can change while θ moves", and the two differ by
        exactly the tied rows: a tie carries its coefficient on the free
        column it follows (p = C·p_free + d), so a tied entry has a nonzero row
        of C while a held one lives entirely in ``d``.

        A consumer freezing a *structural* decision on "this cannot change
        during the stage" — window sizing, or a correction gated at its off
        state — must ask this rather than ``free_paths``, or a user tie
        (:meth:`Refinement.tie`) silently invalidates the freeze.  Read in
        entry order, so the answer does not depend on how θ was assembled.
        """
        reach = np.asarray(abs(self._C).sum(axis=1)).ravel()
        return [e.path for i, e in enumerate(self.entries) if reach[i] > 0.0]

    def x0(self) -> np.ndarray:
        return np.array([to_internal(self.entries[i].value, self.entries[i].transform)
                         for i in self._free_idx], dtype=np.float64)

    def freeze_cell_windows(self, phases: set[int] | None) -> None:
        """Declare which phases' cells get the default window this stage.

        Frozen at stage compile like every other per-stage decision, and
        ``None`` means **no claim made** and windows nothing — the
        ``moving_paths`` convention, where an empty set is the claim that
        nothing needs one.  Held on the table rather than passed to
        :meth:`bounds` so that every reader agrees: ``run_least_squares`` solves
        against these bounds and ``staged.check_guards`` calls ``bounds()``
        again afterwards to decide ``at_bounds``, and a window the solver used
        but the guard did not see would be a bound hit nothing could report.
        """
        self._cell_window_phases = phases

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Internal-space bounds for the free vector, in ``free_paths`` order.

        This is where :func:`cell_window` is applied, rather than on the
        :class:`Entry`, and the distinction is the point: a window is a
        **solver** bound for the stage about to run, not a fact about the
        stored parameter.  Putting it on the entry would surface it through
        ``ParameterRow`` and the ``.rxt`` document, both of which tell a reader
        that bounds come from the schema — and there it would read as a claim
        the caller never made.  ``bound_findings`` is fed from here, so a cell
        that reaches its window is still reported.
        """
        windowed = getattr(self, "_cell_window_phases", None)
        lo, hi = [], []
        for i in self._free_idx:
            e = self.entries[i]
            e_lo, e_hi = e.lo, e.hi
            if windowed:
                cell_name = _cell_parameter_name(e.path, phases=windowed)
                if cell_name is not None:
                    e_lo, e_hi = cell_window(cell_name, e.value, e_lo, e_hi)
            low, high = internal_bounds(e_lo, e_hi, e.transform)
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

        **A row drawing on a column that measured nothing is omitted too**, so
        the caller's ``.get(path)`` gives ``None`` (WP-1110 item 14).  Such a
        column comes back from the covariance solve with infinite variance, and
        WP-1072's rule is that a derived quantity which cannot be measured is
        *absent* rather than zero — this is that rule one rank down, and it
        reaches the tied rows as well, since a tie whose source measured
        nothing measured nothing.
        """
        if correlation is None:
            # stays on the diagonal *vector*: this branch is the cheap one, and
            # a Pawley table's dense n×n would be tens of MB for a number that
            # never leaves the diagonal
            s = self._sigma_free_measured(theta, stderr_internal)
            var = np.asarray(self._C.multiply(self._C) @ (s * s)).ravel()
        else:
            cov = self._cov_free(theta, stderr_internal, correlation)
            var = np.asarray(self._C.multiply(self._C @ cov).sum(axis=1)).ravel()
        var = np.maximum(var, 0.0)
        touched = np.diff(self._C.indptr) > 0  # rows with any free source
        blind = self.unmeasured_rows(theta, stderr_internal)
        return {e.path: float(np.sqrt(var[i]))
                for i, e in enumerate(self.entries) if touched[i] and not blind[i]}

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
        when given.  This is the construction :meth:`stderr_physical` uses —
        it calls this method rather than repeating it — so any block extracted
        from it carries the same Bérar-Lelann conditioning as the reported
        per-parameter esds.

        **A column the data carries no gradient in is left out of the matrix,
        not written into it** (WP-1110 item 14).
        :func:`~rietx.optimize.statistics.normal_covariance` reports such a
        direction as infinite variance, which is the true value and an
        unusable one to propagate with: every product against a zero
        coefficient — an off-diagonal correlation of exactly 0, a ``C`` row
        that does not use the column — is ``0 × inf``, a NaN, and one NaN in
        ``Cov_free`` reaches every row of ``C @ Cov_free`` that shares any
        source with it.  A rutile geometry table lost all six Ti-O bond esds
        that way while the offender was ``instrument.profile.y``, a parameter
        no bond depends on.

        So the infinite entries are zeroed here and reported through
        :meth:`unmeasured_free`, which names the columns.  A consumer marks the
        rows that *use* one absent and propagates the rest exactly — a bond
        length is not made unmeasurable by an unrelated profile term, and it is
        made unmeasurable by a coordinate that measured nothing.
        """
        s = self._sigma_free_measured(theta, stderr_internal)
        if correlation is None:
            return np.diag(s * s)
        return np.asarray(correlation, dtype=np.float64) * np.outer(s, s)

    def _sigma_free_measured(self, theta: np.ndarray, stderr_internal: np.ndarray
                             ) -> np.ndarray:
        """:meth:`_phys_sigma_free` with the unmeasured columns zeroed.

        The one place the infinities leave the arithmetic, so no consumer can
        forget: :meth:`unmeasured_free` is where they are *reported*.
        """
        s = self._phys_sigma_free(theta, stderr_internal)
        return np.where(np.isfinite(s), s, 0.0)

    def unmeasured_free(self, theta: np.ndarray, stderr_internal: np.ndarray
                        ) -> np.ndarray:
        """Boolean over the free columns: which of them measured nothing.

        A free column with no gradient anywhere in the residual comes back from
        the covariance solve with infinite variance (WP-1110 item 14).  This is
        the mask of those, in θ-column order, so a caller propagating through
        ``C`` can tell "no free source" — the all-zero ``C`` row WP-1072
        already reports as ``None`` — from "a free source that measured
        nothing", which needs the same answer for the same reason.
        """
        return ~np.isfinite(self._phys_sigma_free(theta, stderr_internal))

    def unmeasured_rows(self, theta: np.ndarray, stderr_internal: np.ndarray,
                        rows: np.ndarray | None = None) -> np.ndarray:
        """Boolean over ``C``'s rows (or ``rows`` of it): which are unmeasured.

        A row is unmeasured when it draws on any column
        :meth:`unmeasured_free` names — the propagated variance would be
        infinite, and an infinite esd is the absent one, not a large one.
        """
        bad = self.unmeasured_free(theta, stderr_internal)
        if not bad.any():
            n = self._C.shape[0] if rows is None else len(rows)
            return np.zeros(n, dtype=bool)
        c = self._C if rows is None else self._C[rows, :]
        return np.asarray(abs(c) @ bad.astype(np.float64)).ravel() > 0.0

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
        # …and the wavelength through ``wavelength_parameters``, never through
        # ``lines``: a neutron source's ``lines`` is a *property* that builds a
        # fresh EmissionLine per access, so a write there lands on a throwaway
        # and the refined λ is silently lost at the next recompile — exactly the
        # half-wired-parameter failure this file's docstring warns about.
        for il, wl in enumerate(instrument.source.wavelength_parameters):
            put(wl, f"instrument.source.lines.{il}.wavelength")
        for name in ("sample_displacement", "sample_transparency",
                     "axial_sl", "axial_hl", *CAPILLARY_OFFSETS):
            put(getattr(instrument.geometry, name), f"instrument.geometry.{name}")
        for sub, cp in roughness_parameters(instrument.geometry.surface_roughness):
            put(cp, f"instrument.geometry.surface_roughness.{sub}")
        for name in ("u", "v", "w", "x", "y"):
            put(getattr(instrument.profile, name), f"instrument.profile.{name}")
        for sub, cp in _background_parameters(instrument.background):
            put(cp, f"instrument.background.{sub}")
