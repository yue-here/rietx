"""What the chemist knows, as terms beside the solve cost (#562 S3; WP-1997).

A direct-space search minimising the data χ² alone can reach a low χ² with
chemically absurd coordination: the source run's prior was necessary (WP-1515
§ Context).  An unreported prior can also manufacture a solution.  So the
chemistry here enters as **declared terms with weights, reported per term
beside** ``chi2_data`` **and never folded into it** (the architecture's D8):

* :class:`Composition` — the atom inventory, Z and the volume window from
  WP-1510's per-atom volumes.  A **gate**, not a term: a candidate whose sites
  do not add up to the formula is not a candidate.
* :func:`contacts` — every image within a cutoff, by the minimum image.  Its
  oracle is :func:`rietx.model.geometry._neighbours`, whose completeness is
  proved by orbit counting; the two return the same set out to
  :data:`~rietx.model.geometry.CONTACT_MAX_ANG` on WP-1466's 21 phases
  (``tests/test_solve_chemistry.py``).
* :func:`site_clash` — the clash term Σ w·((r₀ − d)/σ)² over contacts closer
  than r₀, the per-site form a Metropolis move needs.  It is the numpy path
  and the oracle of the compiled ``solve_clash`` kernel (#562 chunk 1, not on
  ``main`` yet), and takes that kernel's arguments in its order, so the engine
  swaps one for the other in one line.
* :class:`CoordinationPrior` — "each A has n_lo to n_hi B within [d_lo, d_hi]",
  a squared hinge outside, and :class:`ExcludedContact` — "A and B never
  within d", which raises r₀ and so is folded into the clash term, listed.
* :class:`CandidateCost` — ``chi2_data``, ``chi2_prior`` per term, the prior's
  share of the total and the ``prior_dominant`` reading of it.

**Images are wrapped before they are shifted.**  The source run's contact code
applied ±1 cell shifts to symmetry images it had not brought into the cell,
so every contact of an atom with a coordinate above ½ was looked for a whole
cell away and missed (WP-1513 § Context): the chemistry terms were blind for
the whole run while the diffraction terms were right.  Every distance here is
taken from the difference d of two positions reduced to d − ⌊d + ½⌋, each
component in [−½, ½), before any lattice shift is added; the shift set is then
sized to the cutoff from there.

**Clash radii are sourced or absent** (#677).  r₀(A, B) =
:data:`CLASH_FRACTION` × (r_A + r_B), with both radii from one table, chosen per
species by the rule of :func:`contact_radius`: Shannon (1976) crystal radii for
an ion, Pauling (1960) R₁ for a neutral metal in an anion-free phase, and
Pyykkö & Atsumi (2009) r₁ for any other neutral atom
(:mod:`rietx.crystallography.radii`).  A species with no row, or a pair whose
two radii come from different tables, carries **no radius-derived clash term**, and the
compiled priors say so in :attr:`CompiledChemistry.notes`.  Nothing falls back
to a typed or a floor radius.  A prior that matches nothing (an
element no site holds, a ``cn``/``spin`` key naming no species) is said there
too, so it never reads as a satisfied one.  A radius that reaches past the 27
cells :func:`site_clash` searches is refused at compile.

**Occupancy.**  Two sites whose occupancies sum to at most 1 need not coexist
— a split site overlaps its partner on purpose — and nothing here knows which
atoms of a disordered model coexist.  Such a pair carries no clash term and
is named in the notes (WP-1513's first cut); a configuration-aware check waits
for a representation of configurations.  **A declared** :class:`ExcludedContact`
**outranks this rule**: the chemist named the pair, so it keeps its own
distance (never the radius-derived r₀) and the notes say it was kept.  The coordination count weighs each
neighbour by its occupancy.

**Thresholds are provisional.**  :data:`CLASH_FRACTION`,
:data:`CLASH_SIGMA_ANG`, :data:`COORDINATION_WEIGHT` and
:data:`PRIOR_SHARE_MAX` are declared, not cited
and not measured on public data.  The grades that read them ship under a
versioned thresholds contract (WP-1515's 2026-09-30 review), which arrives
with the answer type; until then a change to one of them is a change to this
module's docstring and nothing else.

Nothing here is exported from :mod:`rietx`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import numpy as np

from ..crystallography.atomic_volume import (
    TABLE_TEMPERATURE,
    VOLUME_RATIO_BOUNDS,
    _parse_formula,
    formula_unit_volume,
)
from ..crystallography.species import element_symbol
from ..crystallography.structure_factor import select_orbit_ops
from ..crystallography.symmetry import resolve_group
from ..indexing.extinction import DECISIVE_DELTA_BIC
from ..model.geometry import _COINCIDENT_D2, CONTACT_MAX_ANG
from ..model.restraints import _metric_g

#: r₀(A, B) = CLASH_FRACTION × (r_A + r_B).  Declared, cited to nobody, like
#: :data:`~rietx.model.geometry.BOND_SLACK_ANG`: a sum of radii is a bond
#: length, and a clash is a contact well short of one.  At 0.8 a Ti⁴⁺–O²⁻ pair
#: (Shannon crystal radii, CN VI) clashes below 1.60 Å against a 1.95 Å bond.
CLASH_FRACTION = 0.8

#: σ of the clash term, Å: an overlap of σ costs 1 in χ² units at weight 1.
#: Declared, not measured.
CLASH_SIGMA_ANG = 0.1

#: A candidate whose priors carry more than this share of its total cost is
#: ``prior_dominant``: its minimum is the prior's as much as the data's.
#: Proposed in the architecture (D8), not measured.
PRIOR_SHARE_MAX = 0.25

#: The default weight of the coordination term: one atom one neighbour off
#: costs :data:`~rietx.indexing.extinction.DECISIVE_DELTA_BIC` (10) in χ²
#: units, the package's margin for the data choosing one hypothesis over
#: another, so a count the chemist declares is as strong a statement as a
#: decisive fit.  Declared, not measured.
COORDINATION_WEIGHT = DECISIVE_DELTA_BIC

#: Shannon (1976) coordination looked up when the caller names none: VI, the
#: coordination both of his scales are anchored on (r(ᵛᴵO²⁻), pp. 759-760).
DEFAULT_CN = 6

#: |Σ found − Σ expected| per element, in atoms per cell, under which an
#: inventory matches: occupancies printed to three decimals (⅓ as 0.333) sum
#: to within this of a whole number over the multiplicities a cell holds.
INVENTORY_TOL = 0.05

_CELL = ("a", "b", "c", "alpha", "beta", "gamma")


# ----------------------------------------------------------------------
# composition: the gate
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CompositionCheck:
    """What a phase's sites hold against a :class:`Composition`.

    ``expected`` and ``found`` are atoms per cell by element: the formula times
    Z, and Σ multiplicity × occupancy over the sites.  ``z`` is the declared Z,
    or the whole number nearest ``z_implied`` = V/V_fu when none was declared.
    ``volume_ratio`` is V/(Z·V_fu), and ``in_volume_window`` whether it lies in
    Hofmann's (2002) 0.8-1.25 (:data:`~rietx.crystallography.atomic_volume.VOLUME_RATIO_BOUNDS`).
    """

    formula: str
    z: int
    z_implied: float
    volume: float
    formula_unit_volume: float
    volume_ratio: float
    in_volume_window: bool
    expected: dict[str, float]
    found: dict[str, float]
    omitted: tuple[str, ...]

    @property
    def inventory_matches(self) -> bool:
        """Every element within :data:`INVENTORY_TOL` atoms, and none extra."""
        keys = set(self.expected) | set(self.found)
        return all(abs(self.expected.get(k, 0.0) - self.found.get(k, 0.0)) <= INVENTORY_TOL
                   for k in keys)

    @property
    def missing(self) -> dict[str, float]:
        """Atoms per cell the formula needs and the sites lack (negative: extra)."""
        keys = set(self.expected) | set(self.found)
        out = {k: self.expected.get(k, 0.0) - self.found.get(k, 0.0) for k in sorted(keys)}
        return {k: v for k, v in out.items() if abs(v) > INVENTORY_TOL}


class CompositionMismatch(ValueError):
    """The sites do not hold the formula; :attr:`check` says by how much."""

    def __init__(self, check: CompositionCheck):
        self.check = check
        parts = ", ".join(f"{k} {v:+.3g}" for k, v in check.missing.items())
        super().__init__(
            f"the sites do not hold {check.z} × {check.formula}: atoms per cell "
            f"missing (+) or extra (−): {parts}")


@dataclass(frozen=True)
class Composition:
    """The formula and Z a solve places atoms for.

    ``formula`` reads as :func:`~rietx.crystallography.atomic_volume.formula_unit_volume`
    reads it (``"TiO2"``, ``"CuSO4·5H2O"``, a CIF's ``"C7 H6 O2"``), and is
    parsed by the same function, so the volume and the inventory cannot read
    one formula two ways.  ``z`` is formula units per cell, ``None`` to infer
    it from the cell volume.  ``temperature`` (K) scales Hofmann's volumes.
    """

    formula: str
    z: int | None = None
    temperature: float = TABLE_TEMPERATURE

    def __post_init__(self) -> None:
        _parse_formula(self.formula)          # a bad formula raises here
        if self.z is not None and (isinstance(self.z, bool) or int(self.z) != self.z
                                   or self.z < 1):
            raise ValueError(f"z must be a positive whole number of formula units, "
                             f"got {self.z!r}")

    @property
    def counts(self) -> dict[str, float]:
        """Atoms of each element in one formula unit."""
        return _parse_formula(self.formula)

    def formula_unit_volume(self) -> float:
        """Hofmann's (2002) volume of one formula unit, Å³, at ``temperature``."""
        return formula_unit_volume(self.formula, self.temperature)[0]

    def implied_z(self, volume: float) -> float:
        """Formula units a cell of ``volume`` Å³ holds by Hofmann's volumes."""
        return float(volume) / self.formula_unit_volume()

    def volume_window(self, z: int | None = None) -> tuple[float, float]:
        """(V_min, V_max) for ``z`` (default: the declared Z), Å³: Z·V_fu
        times Hofmann's 0.8-1.25 (WP-1510).  His table is fitted to organic
        and metal-organic crystals; an ionic specimen runs large.

        Hofmann, D. W. M. (2002) *Acta Cryst.* B58, 489-493."""
        z = self.z if z is None else z
        if z is None:
            raise ValueError("volume_window needs a Z: declare one or pass z=")
        lo, hi = VOLUME_RATIO_BOUNDS
        v = z * self.formula_unit_volume()
        return lo * v, hi * v

    def check(self, phase, *, omit: tuple[str, ...] = ()) -> CompositionCheck:
        """The phase's sites against the formula.  ``omit`` names elements the
        sites are allowed to leave out (hydrogen, in an X-ray solve) — left out
        of the inventory on both sides, never out of the volume."""
        cell = tuple(float(getattr(phase.cell, k).value) for k in _CELL)
        volume = math.sqrt(max(float(np.linalg.det(_metric_g(cell))), 0.0))
        v_fu = self.formula_unit_volume()
        z_implied = volume / v_fu
        z = self.z if self.z is not None else max(1, round(z_implied))
        omitted = tuple(sorted({element_symbol(e) for e in omit}))
        expected = {el: n * z for el, n in self.counts.items() if el not in omitted}
        found: dict[str, float] = {}
        sg = resolve_group(phase.space_group, phase.symmetry_operations)
        for atom in phase.atoms:
            el = element_symbol(atom.species)
            if el in omitted:
                continue
            rot, _ = select_orbit_ops(sg, np.array([atom.x.value, atom.y.value,
                                                    atom.z.value]))
            found[el] = found.get(el, 0.0) + len(rot) * float(atom.occ.value)
        ratio = volume / (z * v_fu)
        lo, hi = VOLUME_RATIO_BOUNDS
        return CompositionCheck(
            formula=self.formula, z=int(z), z_implied=z_implied, volume=volume,
            formula_unit_volume=v_fu, volume_ratio=ratio,
            in_volume_window=bool(lo <= ratio <= hi), expected=expected, found=found,
            omitted=omitted)

    def require(self, phase, *, omit: tuple[str, ...] = ()) -> CompositionCheck:
        """:meth:`check`, raising :class:`CompositionMismatch` unless the
        inventory matches: the gate a run applies before it starts."""
        out = self.check(phase, omit=omit)
        if not out.inventory_matches:
            raise CompositionMismatch(out)
        return out


# ----------------------------------------------------------------------
# the contact set
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Contacts:
    """Image pairs within a cutoff: atom ``a`` sees atom ``b`` at
    ``pos[b] + shift − pos[a]`` (fractional), at distance ``d`` (Å)."""

    a: np.ndarray        # (k,) int
    b: np.ndarray        # (k,) int
    shift: np.ndarray    # (k, 3) int, applied to pos[b]
    d: np.ndarray        # (k,) Å


def _reach(g: np.ndarray, cutoff: float) -> list[int]:
    """Lattice shifts per axis that cover ``cutoff`` around a minimum image.

    A sphere of radius r spans |x_k| ≤ r·√(G*_kk) along fractional axis k (the
    plane spacing is 1/√(G*_kk)), and a minimum-image component already lies
    in [−½, ½), so the integer shifts needed are |n_k| ≤ ⌊r·√(G*_kk) + ½⌋.
    """
    gstar = np.linalg.inv(g)
    return [int(math.floor(cutoff * math.sqrt(gstar[k, k]) + 0.5)) for k in range(3)]


def _lattice(reach: list[int]) -> np.ndarray:
    grids = np.meshgrid(*[np.arange(-r, r + 1) for r in reach], indexing="ij")
    return np.stack([grid.ravel() for grid in grids], axis=1).astype(np.float64)


def contacts(pos: np.ndarray, g: np.ndarray, cutoff: float = CONTACT_MAX_ANG, *,
             centres=None) -> Contacts:
    """Every image of every atom within ``cutoff`` Å of each centre.

    ``pos`` (n, 3) is the cell's atoms in fractional coordinates, wrapped or
    not; ``g`` the direct metric tensor; ``centres`` the atoms to look from
    (default all).  An atom's own images count, itself in its own cell does
    not, and an image closer than √\\ :data:`~rietx.model.geometry._COINCIDENT_D2`
    is coincident and dropped — :func:`~rietx.model.geometry._neighbours`'s
    rule, which this function reproduces pair for pair.  Each difference is
    reduced to the minimum image first and the shift set sized from there
    (:func:`_reach`); the module docstring says why that order.
    """
    pos = np.asarray(pos, dtype=np.float64)
    g = np.asarray(g, dtype=np.float64)
    lattice = _lattice(_reach(g, cutoff))
    centres = np.arange(len(pos)) if centres is None else np.asarray(centres, dtype=np.intp)
    out_a, out_b, out_s, out_d = [], [], [], []
    for a in centres:
        diff = pos - pos[a]
        base = -np.floor(diff + 0.5)
        dd = (diff + base)[:, None, :] + lattice[None, :, :]          # (n, s, 3)
        d2 = np.einsum("nsi,ij,nsj->ns", dd, g, dd)
        b, s = np.nonzero((d2 > _COINCIDENT_D2) & (d2 <= cutoff * cutoff))
        out_a.append(np.full(len(b), a, dtype=np.intp))
        out_b.append(b.astype(np.intp))
        out_s.append((base[b] + lattice[s]).astype(np.int64))
        out_d.append(np.sqrt(d2[b, s]))
    if not out_a:
        return Contacts(np.zeros(0, np.intp), np.zeros(0, np.intp),
                        np.zeros((0, 3), np.int64), np.zeros(0))
    return Contacts(np.concatenate(out_a), np.concatenate(out_b),
                    np.concatenate(out_s), np.concatenate(out_d))


# ----------------------------------------------------------------------
# the clash term
# ----------------------------------------------------------------------
#: The 27 cells around a minimum image, (0, 0, 0) at index 13.
_CELLS27 = _lattice([1, 1, 1])


def clash_cells_suffice(g: np.ndarray, r0: np.ndarray) -> bool:
    """Whether the 27 cells around a minimum image hold every contact closer
    than max r₀: r·√(G*_kk) < 3/2 on every axis (:func:`_reach`).  False on a
    cell thinner than ⅔ of the largest r₀ along some axis."""
    r = float(np.max(r0)) if np.size(r0) else 0.0
    return max(_reach(np.asarray(g, dtype=np.float64), r)) <= 1


def _clash_overlaps(pos_r, site_of, mine, g, r0, sigma):
    """((r₀ − d)/σ)⁺ for the atoms ``mine`` against every atom, (m, n, 27)."""
    d = pos_r[None, :, :] - pos_r[mine][:, None, :]                     # b − a
    d -= np.floor(d + 0.5)
    dd = d[:, :, None, :] + _CELLS27[None, None, :, :]
    q = np.einsum("mnci,ij,mncj->mnc", dd, g, dd)
    dist = np.sqrt(np.maximum(q, 0.0))
    rr = r0[site_of[mine]][:, site_of][:, :, None]
    over = np.where(dist < rr, (rr - dist) / sigma, 0.0)
    over[np.arange(len(mine)), mine, 13] = 0.0                           # itself
    return over


def site_clash(pos: np.ndarray, site_of: np.ndarray, moved: np.ndarray,
               g: np.ndarray, r0: np.ndarray, sigma: float = CLASH_SIGMA_ANG,
               w_same: float = 0.5) -> np.ndarray:
    """The contact energy of site ``moved[r]`` in replica r, (R,).

    ``pos`` (R, n, 3): every atom of the cell per replica, fractional;
    ``site_of`` (n,): the site each atom belongs to; ``g`` the metric tensor;
    ``r0`` (n_sites, n_sites) the clash distances, 0 where a pair carries no
    term.  Σ w·((r₀ − d)/σ)² over the moved site's atoms against every atom,
    the site's own images included and an atom against itself in its own cell
    excluded, over the 27 cells around the minimum image d − ⌊d + ½⌋, for every
    contact closer than r₀; w = ``w_same`` inside the moved site and 1
    elsewhere.  With ``w_same`` = ½ the change of this quantity under a move of
    that site is the change of the structure's total (:func:`clash_energy`).

    The numpy path and the oracle of chunk 1's compiled ``solve_clash``, whose
    arguments these are, in its order.  Raises ``ValueError`` where the 27
    cells would miss a contact (:func:`clash_cells_suffice`), a refusal the
    kernel does not make, and for an index outside the sites.
    """
    pos = np.asarray(pos, dtype=np.float64)
    site_of = np.asarray(site_of, dtype=np.intp)
    moved = np.asarray(moved, dtype=np.intp)
    g = np.asarray(g, dtype=np.float64)
    r0 = np.asarray(r0, dtype=np.float64)
    if pos.ndim != 3 or pos.shape[2] != 3:
        raise ValueError(f"pos has shape {pos.shape}, site_clash reads (R, n_atoms, 3)")
    if site_of.shape != (pos.shape[1],) or moved.shape != (pos.shape[0],):
        raise ValueError(f"site_of {site_of.shape} and moved {moved.shape} must be "
                         f"({pos.shape[1]},) and ({pos.shape[0]},)")
    n_sites = r0.shape[0]
    if r0.shape != (n_sites, n_sites):
        raise ValueError(f"r0 has shape {r0.shape}, site_clash reads (n_sites, n_sites)")
    for name, v in (("site", site_of), ("moved site", moved)):
        if v.size and (v.min() < 0 or v.max() >= n_sites):
            raise ValueError(f"a {name} index lies outside the {n_sites} sites of r0")
    if not (math.isfinite(sigma) and sigma > 0.0):
        raise ValueError(f"sigma {sigma} is not a positive number")
    if not clash_cells_suffice(g, r0):
        raise ValueError(
            f"r0 up to {float(np.max(r0)):.3g} Å reaches past the 27 cells around a "
            "minimum image in this cell; the term would miss contacts")
    out = np.zeros(pos.shape[0])
    for r in range(pos.shape[0]):
        mine = np.flatnonzero(site_of == moved[r])
        if not mine.size:
            continue
        over = _clash_overlaps(pos[r], site_of, mine, g, r0, sigma)
        w = np.where(site_of == moved[r], w_same, 1.0)[None, :, None]
        out[r] = float(np.sum(w * over * over))
    return out


def clash_energy(pos: np.ndarray, site_of: np.ndarray, g: np.ndarray, r0: np.ndarray,
                 sigma: float = CLASH_SIGMA_ANG) -> float:
    """The structure's clash term, each unordered contact once: ½ Σ_s of
    :func:`site_clash` with ``w_same`` = 1, every site moved in turn."""
    pos = np.asarray(pos, dtype=np.float64)
    n_sites = np.asarray(r0).shape[0]
    stack = np.broadcast_to(pos, (n_sites, *pos.shape))
    return 0.5 * float(np.sum(site_clash(stack, site_of, np.arange(n_sites), g, r0,
                                         sigma, 1.0)))


def clash_count(pos: np.ndarray, site_of: np.ndarray, g: np.ndarray,
                r0: np.ndarray) -> int:
    """Unordered contacts closer than r₀: the contacts :func:`clash_energy` sums."""
    pos = np.asarray(pos, dtype=np.float64)
    site_of = np.asarray(site_of, dtype=np.intp)
    over = _clash_overlaps(pos, site_of, np.arange(len(pos)), np.asarray(g, float),
                           np.asarray(r0, float), 1.0)
    return int(np.count_nonzero(over > 0.0)) // 2


# ----------------------------------------------------------------------
# radii
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ContactRadius:
    """One species' radius for the clash term, and where it came from.

    ``table`` is ``"shannon_crystal"`` (Shannon 1976, Table 1, crystal radius),
    ``"pauling_r1"`` (Pauling 1960, Table 11-1, R₁) or ``"pyykko_r1"`` (Pyykkö &
    Atsumi 2009a, r₁); a sum is formed only within one.  ``detail`` names the
    row (ion, CN, spin) as a reader would look it up.
    """

    species: str
    radius: float
    table: str
    detail: str


def _is_charged(species: str) -> bool:
    from ..crystallography.radii import _CHARGE_RE

    m = _CHARGE_RE.match(species)
    return bool(m and (m.group("s") or m.group("s2")))


def contact_radius(species: str, *, cn: int | str | None = None, spin: str | None = None,
                   anion_free: bool = False) -> ContactRadius | None:
    """The radius the clash term gives ``species``, or ``None``: the selection rule.

    1. **An ion** (a species with a charge, ``"Ti4+"``, ``"O2-"``): Shannon's
       (1976) **crystal** radius, the scale he says "correspond[s] more closely
       to the physical size of ions in a solid" (p. 760), at ``cn`` (default
       :data:`DEFAULT_CN`, VI).  Where he prints a high- and a low-spin row and
       ``spin`` is ``None``, the **smaller** is taken: a clash is a floor, and
       the smaller radius can only admit a structure the larger refuses.  A CN
       or charge he does not tabulate gives ``None`` — never a neighbouring row.
    2. **A neutral metal in an anion-free phase** (``anion_free``, gemmi's
       ``is_metal``): Pauling's (1960) single-bond metallic radius R₁, the
       metal–metal radius of #677.
    3. **Any other neutral atom**: Pyykkö & Atsumi's (2009a) single-bond
       covalent radius r₁.

    A ``cn`` that matches two of Shannon's rows (Cu²⁺ at 4: ``IV`` and
    ``IVSQ``) raises :class:`ValueError` naming both: the choice is the
    caller's, and ``None`` would read as "no tabulated radius".

    References: Shannon, R. D. (1976) *Acta Cryst.* A32, 751-767; Pauling, L.
    (1960) *The Nature of the Chemical Bond*, 3rd ed., Cornell University
    Press; Pyykkö, P. & Atsumi, M. (2009) *Chem. Eur. J.* 15, 186-197.
    """
    import gemmi

    from ..crystallography import radii

    if _is_charged(species):
        cn = DEFAULT_CN if cn is None else cn
        rows = []
        refused = None
        for s in ((None, "HS", "LS") if spin is None else (spin,)):
            try:
                rows.append(radii.ionic_radius(species, cn, spin=s, kind="crystal"))
            except KeyError:                 # untabulated
                continue
            except ValueError as err:        # both spins printed (the HS and LS
                refused = refused or err     # tries below answer it), or ambiguous
        if not rows:
            if refused is not None:
                raise refused                # a choice the caller has to make
            return None
        row = min(rows, key=lambda r: r.radius)
        sp = f" {row.spin}" if row.spin else ""
        return ContactRadius(species, row.radius, "shannon_crystal",
                             f"Shannon (1976) crystal radius, "
                             f"{radii._label(row.ion, row.charge)} "
                             f"CN {row.cn}{sp}, p. {row.page}")
    el = element_symbol(species)
    if anion_free and gemmi.Element(el).is_metal:
        try:
            m = radii.metallic_radius(el)
        except KeyError:
            return None
        return ContactRadius(species, m.radius, "pauling_r1",
                             f"Pauling (1960) R1, {el}, Table 11-1 p. {m.page}")
    try:
        r = radii.covalent_radius(el, 1)
    except KeyError:
        return None
    return ContactRadius(species, r, "pyykko_r1", f"Pyykkö & Atsumi (2009a) r1, {el}")


# ----------------------------------------------------------------------
# the declared priors
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CoordinationPrior:
    """Each atom of element ``a`` has ``n_lo`` to ``n_hi`` atoms of element
    ``b`` at ``d_lo`` ≤ d ≤ ``d_hi`` Å.  Outside the band the term is the squared
    hinge (n_lo − n)² or (n − n_hi)², summed over the cell's ``a`` atoms
    weighted by occupancy; n counts neighbours by their occupancy."""

    a: str
    b: str
    d_lo: float
    d_hi: float
    n_lo: float
    n_hi: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.d_lo < self.d_hi:
            raise ValueError(f"need 0 ≤ d_lo < d_hi, got {self.d_lo}, {self.d_hi}")
        if not 0.0 <= self.n_lo <= self.n_hi:
            raise ValueError(f"need 0 ≤ n_lo ≤ n_hi, got {self.n_lo}, {self.n_hi}")


@dataclass(frozen=True)
class ExcludedContact:
    """Elements ``a`` and ``b`` are never closer than ``d`` Å: r₀ for the pair
    becomes max(r₀, d), so the exclusion is a clash term, listed as one."""

    a: str
    b: str
    d: float


@dataclass(frozen=True)
class PriorWeights:
    """The weight of each term; :meth:`control` is the zero-weight arm."""

    clash: float = 1.0
    coordination: float = COORDINATION_WEIGHT

    @classmethod
    def control(cls) -> PriorWeights:
        """Every prior weighted zero: the run the data alone would make,
        with every term still measured and reported."""
        return cls(clash=0.0, coordination=0.0)


@dataclass(frozen=True)
class SolvePriors:
    """What the chemist declares beside the composition.

    ``cn`` and ``spin`` name Shannon's row per species for the clash radii
    (:func:`contact_radius`); the defaults are its rule.
    """

    coordination: tuple[CoordinationPrior, ...] = ()
    exclude: tuple[ExcludedContact, ...] = ()
    cn: Mapping[str, int | str] = field(default_factory=dict)
    spin: Mapping[str, str] = field(default_factory=dict)
    weights: PriorWeights = field(default_factory=PriorWeights)
    sigma: float = CLASH_SIGMA_ANG
    fraction: float = CLASH_FRACTION

    def control(self) -> SolvePriors:
        """The same priors at zero weight (:meth:`PriorWeights.control`)."""
        return replace(self, weights=PriorWeights.control())


@dataclass(frozen=True)
class CoordinationReading:
    """One :class:`CoordinationPrior` at a structure: the realised count per
    site of element ``a`` (asymmetric-unit index → count), and its term."""

    prior: CoordinationPrior
    counts: dict[int, float]
    term: float


@dataclass(frozen=True)
class PriorTerms:
    """The chemistry at one structure.  ``chi2_prior`` is each term times its
    weight; ``raw`` the same terms unweighted, reported under the control too."""

    chi2_prior: dict[str, float]
    raw: dict[str, float]
    clash_count: int
    coordination: tuple[CoordinationReading, ...]


@dataclass(frozen=True)
class CandidateCost:
    """``chi2_data`` and ``chi2_prior`` per term, never summed into one another."""

    chi2_data: float
    chi2_prior: dict[str, float]

    @property
    def total(self) -> float:
        return self.chi2_data + sum(self.chi2_prior.values())

    @property
    def prior_share(self) -> float:
        """Σ chi2_prior / total; 0 when the total is 0."""
        t = self.total
        return sum(self.chi2_prior.values()) / t if t > 0.0 else 0.0

    @property
    def prior_dominant(self) -> bool:
        """The priors carry more than :data:`PRIOR_SHARE_MAX` of the total."""
        return self.prior_share > PRIOR_SHARE_MAX


# ----------------------------------------------------------------------
# compiled for one phase
# ----------------------------------------------------------------------
@dataclass
class CompiledChemistry:
    """The priors frozen onto one phase's sites, as the forward model freezes
    its orbit operations: an image list per site, an r₀ matrix, and the
    notes saying which pairs carry no clash term and why.

    :meth:`positions` takes asymmetric-unit coordinates (n_asym, 3) to the
    cell's atoms through the frozen operations; :meth:`terms` reads the
    priors there.  ``site_of`` lists the cell's atoms site by site, each
    site's first image its own coordinate.
    """

    priors: SolvePriors
    g: np.ndarray
    species: list[str]
    elements: list[str]
    occupancy: np.ndarray
    multiplicity: np.ndarray
    ops: list[tuple[np.ndarray, np.ndarray]]
    site_of: np.ndarray
    first: np.ndarray            # (n_asym,) index of each site's own image
    r0: np.ndarray
    radii: list[ContactRadius | None]
    notes: list[str]

    def positions(self, xyz: np.ndarray) -> np.ndarray:
        """The cell's atoms (n, 3) for asymmetric-unit ``xyz``, wrapped into [0, 1)."""
        xyz = np.asarray(xyz, dtype=np.float64)
        parts = [np.einsum("mab,b->ma", rot, xyz[j]) + tran
                 for j, (rot, tran) in enumerate(self.ops)]
        pos = np.concatenate(parts, axis=0)
        return pos - np.floor(pos)

    def coordination_counts(self, pos: np.ndarray, prior: CoordinationPrior
                            ) -> dict[int, float]:
        """Occupancy-weighted count of ``prior.b`` atoms in its distance band
        around each site of element ``prior.a``."""
        centres = [j for j, el in enumerate(self.elements) if el == element_symbol(prior.a)]
        if not centres:
            return {}
        c = contacts(pos, self.g, prior.d_hi, centres=self.first[centres])
        b_el = element_symbol(prior.b)
        occ_atom = self.occupancy[self.site_of]
        is_b = np.array([self.elements[s] == b_el for s in self.site_of])
        keep = is_b[c.b] & (c.d >= prior.d_lo)
        out = {}
        for j in centres:
            sel = keep & (c.a == self.first[j])
            out[j] = float(np.sum(occ_atom[c.b[sel]]))
        return out

    def terms(self, xyz: np.ndarray) -> PriorTerms:
        """The priors at asymmetric-unit coordinates ``xyz``."""
        pos = self.positions(xyz)
        raw_clash = clash_energy(pos, self.site_of, self.g, self.r0, self.priors.sigma)
        readings = []
        raw_coord = 0.0
        for prior in self.priors.coordination:
            counts = self.coordination_counts(pos, prior)
            term = 0.0
            for j, n in counts.items():
                hinge = max(prior.n_lo - n, 0.0) + max(n - prior.n_hi, 0.0)
                term += float(self.multiplicity[j] * self.occupancy[j]) * hinge * hinge
            readings.append(CoordinationReading(prior, counts, term))
            raw_coord += term
        w = self.priors.weights
        raw = {"clash": raw_clash, "coordination": raw_coord}
        return PriorTerms(
            chi2_prior={"clash": w.clash * raw_clash,
                        "coordination": w.coordination * raw_coord},
            raw=raw, clash_count=clash_count(pos, self.site_of, self.g, self.r0),
            coordination=tuple(readings))


def compile_chemistry(phase, priors: SolvePriors | None = None) -> CompiledChemistry:
    """Freeze ``priors`` onto ``phase``'s sites at their current coordinates.

    The orbit operations are :func:`~rietx.crystallography.structure_factor.select_orbit_ops`'s,
    the subsets the forward model freezes, so a coordinate the search moves
    onto a more special position meets its own images here (a clash), exactly
    as its structure factor counts them twice.
    """
    priors = SolvePriors() if priors is None else priors
    cell = tuple(float(getattr(phase.cell, k).value) for k in _CELL)
    g = _metric_g(cell)
    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    species = [a.species for a in phase.atoms]
    elements = [element_symbol(s) for s in species]
    occ = np.array([float(a.occ.value) for a in phase.atoms])
    ops = [select_orbit_ops(sg, np.array([a.x.value, a.y.value, a.z.value]))
           for a in phase.atoms]
    mult = np.array([len(rot) for rot, _ in ops], dtype=np.float64)
    site_of = np.concatenate([np.full(len(rot), j, dtype=np.intp)
                              for j, (rot, _) in enumerate(ops)]) if ops else \
        np.zeros(0, np.intp)
    first = np.concatenate([[0], np.cumsum(mult[:-1])]).astype(np.intp) if ops else \
        np.zeros(0, np.intp)

    notes: list[str] = []
    anion_free = all(_is_metal(el) for el in elements)
    radii_ = [contact_radius(s, cn=priors.cn.get(s), spin=priors.spin.get(s),
                             anion_free=anion_free) for s in species]
    for s in sorted({s for s, r in zip(species, radii_) if r is None}):
        notes.append(f"{s}: no tabulated radius by the selection rule, so no clash "
                     "term for any pair holding it")
    n = len(species)
    r0 = np.zeros((n, n))
    declared = np.zeros((n, n))      # the exclusions' own d, per site pair
    mixed, split = {}, []
    for i in range(n):
        for j in range(n):
            ri, rj = radii_[i], radii_[j]
            if ri is not None and rj is not None:
                if ri.table == rj.table:
                    r0[i, j] = priors.fraction * (ri.radius + rj.radius)
                else:
                    mixed.setdefault(tuple(sorted((species[i], species[j]))), []
                                     ).append((i, j))
            for ex in priors.exclude:
                pair = {element_symbol(ex.a), element_symbol(ex.b)}
                if {elements[i], elements[j]} == pair:
                    r0[i, j] = max(r0[i, j], ex.d)
                    declared[i, j] = max(declared[i, j], ex.d)
    for (a, b), sites in sorted(mixed.items()):
        d = max(declared[i, j] for i, j in sites)
        notes.append(f"{a}–{b}: the two radii come from different tables, so the "
                     "pair carries no radius-derived clash term"
                     + (f"; the declared exclusion at {d:g} Å is its clash term"
                        if d > 0.0 else ""))
    kept = []
    for i in range(n):
        for j in range(i, n):
            if occ[i] + occ[j] <= 1.0 + 1e-9 and r0[i, j] > 0.0:
                r0[i, j] = r0[j, i] = declared[i, j]
                lab = f"{phase.atoms[i].label}–{phase.atoms[j].label}"
                (kept if declared[i, j] > 0.0 else split).append(lab)
    if split:
        notes.append("occupancies summing to at most 1, so the atoms need not "
                     f"coexist; no clash term for: {', '.join(split)}")
    if kept:
        notes.append("occupancies summing to at most 1, but a declared exclusion "
                     "names the pair and outranks the occupancy rule, so only its "
                     f"own distance applies to: {', '.join(kept)}")
    if not clash_cells_suffice(g, r0):
        raise ValueError(
            f"the largest clash radius, {float(np.max(r0)):.3f} Å, reaches past the "
            "27 cells around a minimum image on this cell, which would miss "
            "contacts: shorten the ExcludedContact distance or use a larger cell")
    present = set(elements)
    for prior in priors.coordination:
        for el in (prior.a, prior.b):
            if element_symbol(el) not in present:
                notes.append(f"CoordinationPrior {prior.a}–{prior.b}: no site holds "
                             f"{el}, so the term is "
                             f"{'0 and reads as satisfied' if el == prior.a else 'a count of 0'}")
    for ex in priors.exclude:
        for el in (ex.a, ex.b):
            if element_symbol(el) not in present:
                notes.append(f"ExcludedContact {ex.a}–{ex.b}: no site holds {el}, "
                             "so it excludes nothing here")
    for name, mapping in (("cn", priors.cn), ("spin", priors.spin)):
        for key in mapping:
            if key not in species:
                notes.append(f"SolvePriors.{name}[{key!r}]: no site has that species, "
                             "so it names no radius here")
    return CompiledChemistry(priors=priors, g=g, species=species, elements=elements,
                             occupancy=occ, multiplicity=mult, ops=ops, site_of=site_of,
                             first=first, r0=r0, radii=radii_, notes=notes)


def _is_metal(el: str) -> bool:
    import gemmi

    return bool(gemmi.Element(el).is_metal)


def candidate_cost(cost, f2: np.ndarray, chemistry: CompiledChemistry,
                   xyz: np.ndarray) -> CandidateCost:
    """``chi2_data`` from :meth:`~rietx.solve.cost.SolveCost.chi2` at ``f2``,
    and the priors at ``xyz``, side by side.  ``chi2_data`` reads nothing but
    the cost and ``f2``, so it is the same number under any priors."""
    chi2_data, _scale = cost.chi2(f2)
    return CandidateCost(chi2_data=chi2_data,
                         chi2_prior=dict(chemistry.terms(xyz).chi2_prior))


__all__ = ["CLASH_FRACTION", "CLASH_SIGMA_ANG", "COORDINATION_WEIGHT", "DEFAULT_CN", "INVENTORY_TOL",
           "PRIOR_SHARE_MAX", "CandidateCost", "CompiledChemistry", "Composition",
           "CompositionCheck", "CompositionMismatch", "ContactRadius", "Contacts",
           "CoordinationPrior", "CoordinationReading", "ExcludedContact",
           "PriorTerms", "PriorWeights", "SolvePriors", "candidate_cost",
           "clash_cells_suffice", "clash_count", "clash_energy", "compile_chemistry",
           "contact_radius", "contacts", "site_clash"]
