"""Quantitative phase analysis (QPA) from refined Rietveld scales.

Weight fractions follow the scale-factor relation of Hill & Howard (1987),
J. Appl. Cryst. 20, 467 (see also Bish & Howard 1988, J. Appl. Cryst. 21, 86):
for phase ``p`` with refined scale ``S_p``,

    W_p = S_p·(Z·M·V)_p / Σ_q S_q·(Z·M·V)_q

with Z the formula units per cell, M the formula mass, V the cell volume.  All
three are derived from the refined model — the point of this package is to
remove the GUI-era ritual of typing Z·M·V by hand.  Occupancies enter the mass
(a partly-occupied site weighs less), so the cell mass Z·M is computed from the
*refined* occupancies, not a formula string.

The load-bearing, unambiguous quantity is the **cell mass** Z·M =
Σ_atoms occ·multiplicity·atomic_weight; the Z/M split is a display convenience
recovered by reducing the cell composition to integer formula units, and QPA
never depends on it (weight fractions use Z·M·V directly).

Scope: these are fractions of the **modelled crystalline** content.  An
unmodelled amorphous fraction or a missing phase still makes them sum to 1.
Internal-standard / amorphous quantification is fenced to v2 — that is
O'Connor & Raven (1988), Powder Diffr. 3, 2, whose calibration constant
is what ``K`` means in this field, which is why nothing here spells a
Z·M·V with that letter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import gemmi
import numpy as np

from ..crystallography.attenuation import (
    linear_attenuation,
    packed_mu_r,
    packed_mu_t,
)
from ..crystallography.lattice import cell_volume
from ..crystallography.neutron import linear_attenuation_neutron
from ..crystallography.species import _parse_species, element_symbol
from ..crystallography.symmetry import (
    as_group,
    expand_positions,
    resolve_group,
    site_twin_merge,
)
from ..schemas.common import Diagnostic
from ..schemas.results import (
    MicroabsorptionCorrection,
    PhaseQuantity,
    QuantitativePhaseAnalysis,
)
from ..schemas.structure import Structure


def atomic_weight(species: str) -> float:
    """Atomic weight (g/mol) for a scattering species, via gemmi.

    An element takes gemmi's IUPAC standard atomic weight.
    :func:`element_symbol` has already rejected any symbol gemmi maps to its
    placeholder element "X" (atomic number 0, weight 1.0), so a wrong-mass
    phase can never silently poison the QPA ratio.

    A **nuclide** is not the natural-abundance mixture, so it takes its own
    mass: deuterium (``"D"``, ``"2H"``) gemmi's 2.0141, and every other
    nuclide its mass number A.  gemmi carries no other nuclide mass.  A differs
    from the nuclide's atomic mass by its mass excess: against the NIST masses
    (``periodictable`` 2.1.0), over the 275 mass-numbered nuclides of the
    Sears table the error is at most 0.78 % (¹H), 0.53 % (³H) and 0.26 %
    (⁶Li) above A = 4, and at most 0.098 u (¹¹⁸Sn).  The natural-abundance
    weight would be wrong by far more on exactly the nuclides a neutron
    structure is written with: 1.008 for ²H, 6.94 for ⁷Li.
    """
    element, mass_number = _parse_species(species)
    if mass_number is None:
        return float(gemmi.Element(element).weight)
    if element == "H" and mass_number == 2:
        return float(gemmi.Element("D").weight)
    return float(mass_number)


@dataclass(frozen=True)
class ZMV:
    """Cell-mass / volume factors for one phase.

    ``cell_mass`` (= Z·M) and ``cell_volume`` are unambiguous; ``z`` and
    ``molar_mass`` are the best-effort integer-formula-unit split (``z`` = 1,
    ``molar_mass`` = ``cell_mass`` when the composition does not reduce to
    integers, e.g. under refined partial occupancy).
    """

    cell_mass: float      # Z·M, g/mol per unit cell (occupancy-weighted)
    cell_volume: float    # V, Å³
    zmv: float            # cell_mass · V
    z: int                # formula units per cell (>= 1)
    molar_mass: float     # M = cell_mass / z, g/mol per formula unit
    # occupancy-weighted atom counts per cell, keyed by element symbol — the
    # composition an element's question reads (the formula units, and the
    # X-ray attenuation: crystallography.attenuation.linear_attenuation)
    element_counts: dict[str, float] = field(default_factory=dict)
    # the same counts keyed by the species *as written* ("D", "7Li", "Fe3+"),
    # for a table that tells nuclides apart: the neutron attenuation reads
    # these, where ²H scatters incoherently 2.05 barn against ¹H's 80.26
    species_counts: dict[str, float] = field(default_factory=dict)

    @property
    def density(self) -> float:
        """X-ray density rho = cell_mass / (N_A · V), g/cm³."""
        return self.cell_mass / (0.602214076 * self.cell_volume)


def _formula_units(element_counts: dict[str, float], *, tol: float = 0.02) -> int:
    """Formula units per cell = GCD of the integer per-element cell counts.

    Returns 1 when any element count is not within ``tol`` of a positive
    integer (partial occupancy / solid solution), i.e. the composition does
    not reduce and the whole cell is treated as one formula unit.
    """
    integers = []
    for count in element_counts.values():
        rounded = round(count)
        if rounded <= 0 or abs(count - rounded) > tol:
            return 1
        integers.append(rounded)
    if not integers:
        return 1
    z = integers[0]
    for n in integers[1:]:
        z = math.gcd(z, n)
    return max(z, 1)


def phase_zmv(space_group, cell: tuple[float, float, float, float, float, float],
              atoms, multiplicities=None) -> ZMV:
    """Z·M·V factors for one phase.

    ``atoms`` is an iterable of ``(species, x, y, z, occ)`` for the
    asymmetric-unit atoms; each atom's cell contribution is
    ``occ · multiplicity``.

    ``multiplicities`` (one per atom, in order) supplies the site
    multiplicities directly — pass the counts frozen on the compiled model
    (``len(PhaseSites.ops[j][0])``) so QPA uses exactly the orbit the forward
    model used.  When omitted they are recomputed from the coordinates via
    :func:`crystallography.symmetry.expand_positions`; that path must only be
    fed coordinates that are genuinely on their site, because an atom refined
    to within the dedup tolerance of a special position would otherwise
    collapse its orbit and mis-weigh the cell.  A site whose own images sit
    closer than :data:`~rietx.crystallography.symmetry.TWIN_DISTANCE` counts
    at the special position they collapse to, as ``Phase`` construction
    moves it there (issue #1007).
    """
    sg = as_group(space_group) if multiplicities is None else None
    volume = cell_volume(*cell)
    cell_mass = 0.0
    element_counts: dict[str, float] = {}
    species_counts: dict[str, float] = {}
    for idx, (species, x, y, z, occ) in enumerate(atoms):
        if multiplicities is not None:
            multiplicity = int(multiplicities[idx])
        else:
            # a site whose own images coincide counts once, on the special
            # position its orbit collapses to — what a ``Phase`` holding
            # these coordinates would be moved to at construction (#1007)
            xyz = np.array([x, y, z], dtype=np.float64)
            merge = site_twin_merge(sg, cell, xyz)
            multiplicity = (merge.after if merge is not None
                            else len(expand_positions(sg, xyz)))
        count = float(occ) * multiplicity
        cell_mass += count * atomic_weight(species)
        sym = element_symbol(species)
        element_counts[sym] = element_counts.get(sym, 0.0) + count
        species_counts[species] = species_counts.get(species, 0.0) + count
    z_units = _formula_units(element_counts)
    molar_mass = cell_mass / z_units if z_units else cell_mass
    return ZMV(cell_mass=cell_mass, cell_volume=volume, zmv=cell_mass * volume,
               z=z_units, molar_mass=molar_mass, element_counts=element_counts,
               species_counts=species_counts)


def weight_fractions(zmv, scales, scale_cov=None):
    """Weight fractions and their esds from refined scales.

    ``zmv`` is the per-phase Z·M·V, ``scales`` the refined phase scales; W_p =
    S_p·ZMV_p / Σ_q S_q·ZMV_q.  Hill & Howard (1987) give the product no
    letter of its own, and ``K`` in quantitative phase analysis is O'Connor &
    Raven's calibration constant, whose method this module fences to v2 (see
    the module docstring) — so the argument is spelled out.  When
    ``scale_cov`` (the physical covariance of the scales, in phase order) is
    given, propagate it through the ratio:

        ∂W_p/∂S_j = (ZMV_p·δ_pj − W_p·ZMV_j) / D,   D = Σ_q S_q·ZMV_q
        Cov(W) = J · Cov(S) · Jᵀ

    Returns ``(W, sigma_corr, sigma_indep)`` where ``sigma_indep`` uses only
    the covariance diagonal — the naïve independent-scale propagation, returned
    so callers can show that the correlated path genuinely differs.  Both esds
    are ``None`` when ``scale_cov`` is ``None`` or carries no variance (no scale
    was freed) — an all-zero block is absence of information, not σ(W) = 0.
    """
    zmv = np.asarray(zmv, dtype=np.float64)
    scales = np.asarray(scales, dtype=np.float64)
    a = scales * zmv
    total = a.sum()
    if total <= 0.0:
        raise ValueError("phase scales give a non-positive scaled total "
                         f"(Σ S·ZMV = {total}); cannot form weight fractions")
    w = a / total
    if scale_cov is None:
        return w, None, None
    cov = np.asarray(scale_cov, dtype=np.float64)
    if not np.any(cov):
        return w, None, None
    jac = (np.diag(zmv) - np.outer(w, zmv)) / total
    cov_w = jac @ cov @ jac.T
    sigma_corr = np.sqrt(np.maximum(np.diag(cov_w), 0.0))
    cov_w_indep = jac @ np.diag(np.diag(cov)) @ jac.T
    sigma_indep = np.sqrt(np.maximum(np.diag(cov_w_indep), 0.0))
    return w, sigma_corr, sigma_indep


def brindley_tau(x: float) -> float:
    """Brindley particle-absorption factor for a spherical particle.

    Brindley (1945), Phil. Mag. 36, 347: a particle of phase ``p`` embedded in
    a powder of mean linear attenuation mu_bar diffracts with its intensity
    scaled by tau_p = (1/V) integral exp(-(mu_p - mu_bar) * path) dV.  Here the
    integral is evaluated in the parallel-path approximation (incident and
    diffracted beams traverse the same chord), which for a sphere of radius R
    has the closed form

        tau(x) = 3 [2 - e^(-u) (u^2 + 2u + 2)] / u^3,   u = 2x,
        x = (mu_p - mu_bar) * R   (dimensionless, signed)

    with the Taylor series 1 - 3u/4 + 3u^2/10 - u^3/12 + u^4/56 used near
    u = 0 where the closed form cancels catastrophically.  Brindley's own
    tabulation averages over reflection geometry instead; inside the validity
    domain |x| <= 0.1 the two agree to <1 % — the tests pin this against two
    independently published representations of his table (the quadratic
    1 - 1.450 x + 1.426 x^2 used by FullProf, Rodriguez-Carvajal's QPA notes,
    and the exponential fit used by MAUD, Lutterotti's QPA course notes),
    which themselves scatter by ~1 %.  Unlike either fit this form is exact
    at tau(0) = 1 (zero contrast, no correction) and stays positive and
    monotone when a user pushes past the fence, instead of going polynomial-
    wild.  tau > 1 for a phase less absorbing than the matrix (x < 0).
    """
    u = 2.0 * x
    if abs(u) < 0.05:
        return 1.0 + u * (-0.75 + u * (0.3 + u * (-1.0 / 12.0 + u / 56.0)))
    return 3.0 * (2.0 - math.exp(-u) * (u * u + 2.0 * u + 2.0)) / u ** 3


def brindley_correction(w_measured, densities, mus, radii_um, *,
                        tol: float = 1e-12, max_iter: int = 100):
    """Brindley-corrected weight fractions for spherical particles.

    The measured (Hill-Howard) fraction of phase ``p`` overweights it by its
    particle-absorption factor tau_p, so the true fractions are the fixed
    point of

        W'_p = (W_p / tau_p) / sum_q (W_q / tau_q),
        tau_p = brindley_tau((mu_p - mu_bar) * R_p),
        mu_bar = sum_q v_q * mu_q,   v_q = (W'_q / rho_q) / sum (W'_q / rho_q)

    iterated from tau = 1 (Brindley 1945; iteration scheme as in the FullProf
    QPA formulation, Rodriguez-Carvajal).  mu_bar is the volume-weighted mean
    over the *solid* crystalline mixture — powder porosity, which dilutes the
    matrix attenuation, is not modelled; with porosity the true correction is
    slightly larger, so the solid-average choice is the conservative one.

    ``mus`` in 1/cm, ``radii_um`` in micrometres.  Returns
    ``(w_corrected, taus, mu_bar)``.
    """
    w0 = np.asarray(w_measured, dtype=np.float64)
    rho = np.asarray(densities, dtype=np.float64)
    mu = np.asarray(mus, dtype=np.float64)
    r_cm = np.asarray(radii_um, dtype=np.float64) * 1e-4
    w = w0.copy()
    mu_bar = 0.0
    for _ in range(max_iter):
        v = (w / rho) / np.sum(w / rho)
        mu_bar = float(np.dot(v, mu))
        taus = np.array([brindley_tau(x) for x in (mu - mu_bar) * r_cm])
        w_new = (w0 / taus) / np.sum(w0 / taus)
        if np.max(np.abs(w_new - w)) < tol:
            w = w_new
            break
        w = w_new
    return w, taus, mu_bar


#: Applicability fence for the Brindley correction, in µ·R (R = particle
#: radius).  Brindley (1945) derives the treatment for his fine/medium powder
#: regimes, bounded by µ·D ≤ 0.1 with D = 2R the particle *diameter* (the
#: classification restated in Rodríguez-Carvajal's FullProf QPA notes), i.e.
#: µ·R ≤ 0.05.  Past it a particle no longer diffracts from its bulk and τ is
#: applied outside its derivation.
BRINDLEY_MU_R_FENCE = 0.05


def microabsorption_diagnostics(qpa: QuantitativePhaseAnalysis) -> list[Diagnostic]:
    """Structured diagnostics for the Brindley correction's applicability.

    Two things are worth saying loudly (Taylor & Matulis 1991, J. Appl.
    Cryst. 24, 14, on how routinely this correction is over-trusted): a phase
    whose µ·R exceeds :data:`BRINDLEY_MU_R_FENCE` is outside the fine/medium
    powder regime the correction is derived for — beyond it the "corrected"
    fractions can be *worse* than the uncorrected ones while looking more
    authoritative — and a correction the user asked for (radii supplied) that
    could not run must not stay quiet.
    """
    out: list[Diagnostic] = []
    if qpa.microabsorption_skipped is not None:
        out.append(Diagnostic(
            level="warning", code="MICROABSORPTION_SKIPPED",
            where=[r.name for r in qpa.phases],
            message=qpa.microabsorption_skipped,
            suggestion="Supply particle_radius_um on every phase, and use a "
                       "wavelength inside the attenuation tables.",
        ))
        return out
    offenders = [r for r in qpa.phases
                 if r.mu_r is not None and r.mu_r > BRINDLEY_MU_R_FENCE]
    if offenders:
        listing = ", ".join(f"{r.name} (µR = {r.mu_r:.3f})" for r in offenders)
        out.append(Diagnostic(
            level="warning", code="BRINDLEY_OUTSIDE_REGIME",
            where=[r.name for r in offenders],
            message=(f"µ·R exceeds Brindley's medium-powder limit of "
                     f"{BRINDLEY_MU_R_FENCE} (= µ·D of 0.1) for {listing}."),
            suggestion="Grind the sample finer, use a shorter wavelength, or "
                       "quote the uncorrected fractions with microabsorption "
                       "named as an unquantified systematic.",
        ))
    return out


def compute_qpa(structure: Structure, values: dict[str, float],
                scale_cov=None, multiplicities=None,
                wavelength: float | None = None, *,
                source_kind: str = "xray_cw",
                ) -> QuantitativePhaseAnalysis | None:
    """Assemble the per-phase QPA rows from a decoded parameter dict.

    ``values`` is the physical value dict from ``ParameterTable.decode`` (refined
    cell, occupancies and scales); ``scale_cov`` is the physical covariance of
    the phase scales in phase order (``None`` when no esds were estimated).
    ``multiplicities`` (one list per phase, one entry per atom) should be the
    site multiplicities frozen on the compiled model, so QPA counts the same
    orbits the forward model did rather than re-deriving them from refined
    coordinates that may have drifted near a special position.

    ``wavelength`` (Å, primary emission line) enables the Brindley
    microabsorption correction for phases carrying ``particle_radius_um``,
    with µ from the table ``source_kind`` (the histogram's ``Source.kind``)
    names in :data:`LINEAR_ATTENUATION_BY_SOURCE`.
    The correction needs *every* phase's radius (τ compares each phase to the
    mixture average µ̄, which a phase of unknown size would corrupt); partial
    input or an unavailable µ records ``microabsorption_skipped`` instead of
    guessing, and the uncorrected fractions are always reported either way.

    Returns ``None`` when there is no composition to report — a phase-free
    model (WP-1207) — and when the scales cannot form fractions at all (WP-1028
    §(f)).  This used to raise from inside ``_build_result``, which meant one
    pattern whose scale hit zero destroyed **all 157 refinements** of a
    ``refine_sequential`` run — a fit that produced a bad number took down
    fits that had produced good ones.  A refinement that converged badly is a
    result; QPA is one *field* of it, and a field that cannot be computed is
    absent, not fatal.  The caller turns the ``None`` into a
    ``QPA_UNAVAILABLE`` diagnostic naming the phases.  A **single-phase**
    model never reaches that path: its answer is 100 % by definition, so the
    scale — a brightness, not a composition — cannot make it unanswerable.
    """
    if not structure.phases:
        # Zero phases is neither case the test below tells apart (WP-1207).
        # Σ zmv·s is 0 there, so a phase-free model fell through `> 1` into the
        # *single-phase* branch — "one phase is 100 % whatever its scale did" —
        # and returned an empty table, which reads as "QPA was done, the
        # specimen holds no crystalline phase".  There is no composition to
        # report and none was measured, so the answer is the absence.
        return None
    zmvs, scales = [], []
    for ip, phase in enumerate(structure.phases):
        base = f"phases.{ip}"
        cell = tuple(values[f"{base}.cell.{n}"]
                     for n in ("a", "b", "c", "alpha", "beta", "gamma"))
        atoms = [(atom.species,
                  values[f"{base}.atoms.{j}.x"], values[f"{base}.atoms.{j}.y"],
                  values[f"{base}.atoms.{j}.z"], values[f"{base}.atoms.{j}.occ"])
                 for j, atom in enumerate(phase.atoms)]
        mult = multiplicities[ip] if multiplicities is not None else None
        zmvs.append(phase_zmv(
            resolve_group(phase.space_group, phase.symmetry_operations),
            cell, atoms, multiplicities=mult))
        scales.append(values[f"{base}.scale"])

    if sum(z.zmv * s for z, s in zip(zmvs, scales)) <= 0.0:
        if len(structure.phases) > 1:
            return None
        # one phase is 100 % whatever its scale did; σ(W) is meaningless here
        # (the fraction is a definition, not a measurement), so it stays None
        w, sigma_corr = np.array([1.0]), None
    else:
        w, sigma_corr, _ = weight_fractions([z.zmv for z in zmvs], scales, scale_cov)
    rows = [
        PhaseQuantity(
            name=phase.name,
            weight_fraction=float(w[ip]),
            weight_fraction_stderr=(float(sigma_corr[ip]) if sigma_corr is not None
                                    else None),
            scale=float(scales[ip]),
            z=zmvs[ip].z, molar_mass=zmvs[ip].molar_mass,
            cell_mass=zmvs[ip].cell_mass, cell_volume=zmvs[ip].cell_volume,
            zmv=zmvs[ip].zmv,
        )
        for ip, phase in enumerate(structure.phases)
    ]
    qpa = QuantitativePhaseAnalysis(phases=rows)
    _apply_microabsorption(qpa, structure, zmvs, w, wavelength, source_kind)
    return qpa


def _phase_mu_xray(zmv: ZMV, wavelength: float) -> float:
    """X-ray µ (1/cm) of one phase: McMaster, read by element."""
    return linear_attenuation(zmv.element_counts, zmv.cell_volume, wavelength)


def _phase_mu_neutron(zmv: ZMV, wavelength: float) -> float:
    """Neutron µ (1/cm) of one phase: Sears (1992), read by nuclide."""
    return linear_attenuation_neutron(zmv.species_counts, zmv.cell_volume,
                                      wavelength)


#: The per-phase linear attenuation µ (1/cm) that answers for each
#: ``Source.kind`` — the **one** place radiation enters the specimen-absorption
#: estimates (WP-1132) and the Brindley microabsorption correction (#543).
#: Everything around it — the composition, the volume fractions from the
#: refined scales, the packing fraction, which length µ_bulk multiplies, and
#: Brindley's τ(µR) — is radiation-blind and shared.  Each entry also picks
#: which identity its table reads: X-ray µ is an electron-cloud property and
#: reads the composition by element, neutron µ is a nuclear one and reads it
#: by nuclide (²H and ¹H differ forty-fold in σ_inc).  A kind missing here has
#: no table, and every caller declines for it with a reason rather than borrow
#: another radiation's: X-ray and neutron µ are different quantities, not
#: coarse and fine versions of one.
LINEAR_ATTENUATION_BY_SOURCE = {
    "xray_cw": _phase_mu_xray,
    "neutron_cw": _phase_mu_neutron,
}


def estimate_capillary_mu_r(structure: Structure, values: dict[str, float],
                            wavelength: float, radius_mm: float,
                            packing_fraction: float,
                            multiplicities=None, *,
                            source_kind: str = "xray_cw",
                            ) -> tuple[float | None, str | None]:
    """(µR estimate, reason it was skipped) for a packed capillary.

    Composition → per-phase linear attenuation → volume-fraction-weighted bulk
    µ → µR, reusing exactly the machinery WP-0305 built for Brindley.  µ per
    phase comes from the table ``source_kind`` names
    (:data:`LINEAR_ATTENUATION_BY_SOURCE`): McMaster for X-rays, Sears (1992)
    for constant-wavelength neutrons.  Volume
    fractions come from the refined phase scales via the Hill-Howard weight
    fractions and the X-ray densities; when the scales are not yet meaningful
    every phase contributes equally, which is stated in the reason string
    rather than hidden.

    **Never raises.**  The attenuation tables refuse a wavelength whose grid
    interval straddles an absorption edge, refuse outside 2-120 keV, and have
    gaps at seven elements — all of which are ordinary situations for a real
    specimen, not programming errors, so they come back as a reason string the
    caller can surface as a diagnostic.  The neutron table refuses a species it
    does not tabulate and a resonant absorber the same way.  Same contract as
    :func:`_apply_microabsorption`.
    """
    mus_vols, note = _specimen_mu_and_volumes(structure, values, wavelength,
                                              multiplicities, source_kind)
    if mus_vols is None:
        return None, note
    mus, vols = mus_vols
    try:
        mu_r = packed_mu_r(mus, vols, radius_mm, packing_fraction)
    except ValueError as exc:
        return None, str(exc)
    return float(mu_r), note


def estimate_flat_plate_mu_t(structure: Structure, values: dict[str, float],
                             wavelength: float, thickness_mm: float,
                             packing_fraction: float,
                             multiplicities=None, *,
                             source_kind: str = "xray_cw",
                             ) -> tuple[float | None, str | None]:
    """(µt estimate, reason it was skipped) for a packed flat specimen.

    The flat-plate twin of :func:`estimate_capillary_mu_r`, sharing everything
    but the length the bulk µ multiplies (WP-0508).  Same never-raises
    contract: an absorption edge inside a tabulation interval, an element
    outside the McMaster compilation or an energy outside 2-120 keV are all
    ordinary properties of a real specimen, so they come back as a reason
    string the caller surfaces as a diagnostic.  ``source_kind`` selects the
    table exactly as it does there.
    """
    mus_vols, note = _specimen_mu_and_volumes(structure, values, wavelength,
                                              multiplicities, source_kind)
    if mus_vols is None:
        return None, note
    mus, vols = mus_vols
    try:
        mu_t = packed_mu_t(mus, vols, thickness_mm, packing_fraction)
    except ValueError as exc:
        return None, str(exc)
    return float(mu_t), note


def _specimen_mu_and_volumes(structure: Structure, values: dict[str, float],
                             wavelength: float, multiplicities,
                             source_kind: str = "xray_cw",
                             ) -> tuple[tuple[list[float], list[float]] | None,
                                        str | None]:
    """((per-phase µ, volume fractions), note) or (None, reason it failed).

    Composition → per-phase linear attenuation → volume fractions from the
    refined scales via the Hill-Howard weight fractions and the X-ray densities.
    When the scales are not yet meaningful every phase contributes equally,
    which is stated in the note rather than hidden.  Shape-independent: what the
    two estimators above add is only which length µ_bulk multiplies.  The
    densities are mass densities and radiation-blind; only µ per phase reads
    ``source_kind``.
    """
    attenuation = LINEAR_ATTENUATION_BY_SOURCE.get(source_kind)
    if attenuation is None:
        return None, (f"attenuation unavailable — no attenuation table for a "
                      f"{source_kind!r} source")
    try:
        zmvs, scales = [], []
        for ip, phase in enumerate(structure.phases):
            base = f"phases.{ip}"
            cell = tuple(values[f"{base}.cell.{n}"]
                         for n in ("a", "b", "c", "alpha", "beta", "gamma"))
            atoms = [(atom.species,
                      values[f"{base}.atoms.{j}.x"], values[f"{base}.atoms.{j}.y"],
                      values[f"{base}.atoms.{j}.z"], values[f"{base}.atoms.{j}.occ"])
                     for j, atom in enumerate(phase.atoms)]
            mult = multiplicities[ip] if multiplicities is not None else None
            zmvs.append(phase_zmv(
                resolve_group(phase.space_group, phase.symmetry_operations),
                cell, atoms, multiplicities=mult))
            scales.append(values[f"{base}.scale"])
        mus = [attenuation(z, wavelength) for z in zmvs]
    except (KeyError, ValueError) as exc:
        return None, f"attenuation unavailable — {exc}"

    if any(s > 0.0 for s in scales):
        w, _, _ = weight_fractions([z.zmv for z in zmvs], scales, None)
        return (mus, [wi / z.density for wi, z in zip(w, zmvs)]), None
    return (mus, [1.0] * len(zmvs)), \
        "phase scales are all zero; assumed equal volume fractions"


def _apply_microabsorption(qpa: QuantitativePhaseAnalysis, structure: Structure,
                           zmvs: list[ZMV], w, wavelength: float | None,
                           source_kind: str = "xray_cw") -> None:
    """Attach the Brindley correction to assembled QPA rows, in place.

    Fills the per-phase τ / µ / µR / corrected-fraction fields and the
    mixture-level :class:`MicroabsorptionCorrection`, or records the reason in
    ``microabsorption_skipped`` — silence is reserved for "nobody asked"
    (no phase has a radius).  µ comes from the table ``source_kind`` names
    (:data:`LINEAR_ATTENUATION_BY_SOURCE`), and a kind with none skips with
    that reason.  Until #543 this path read the X-ray table on every source,
    so on a neutron histogram a correction of well under 1 % rewrote the
    fractions by the X-ray µ, two to four orders of magnitude too large.
    """
    radii = [phase.particle_radius_um for phase in structure.phases]
    if all(r is None for r in radii):
        return
    missing = [structure.phases[ip].name for ip, r in enumerate(radii) if r is None]
    if missing:
        qpa.microabsorption_skipped = (
            "Brindley correction skipped: no particle_radius_um on phase(s) "
            f"{', '.join(missing)}.")
        return
    if wavelength is None:
        qpa.microabsorption_skipped = (
            "Brindley correction skipped: no wavelength available to evaluate "
            "attenuation coefficients.")
        return
    attenuation = LINEAR_ATTENUATION_BY_SOURCE.get(source_kind)
    if attenuation is None:
        qpa.microabsorption_skipped = (
            f"Brindley correction skipped: no attenuation table for a "
            f"{source_kind!r} source.")
        return
    try:
        mus = [attenuation(z, wavelength) for z in zmvs]
    except (KeyError, ValueError) as exc:
        qpa.microabsorption_skipped = (
            f"Brindley correction skipped: attenuation unavailable ({exc}).")
        return
    w_corr, taus, mu_bar = brindley_correction(
        w, [z.density for z in zmvs], mus, radii)
    for ip, row in enumerate(qpa.phases):
        row.weight_fraction_corrected = float(w_corr[ip])
        row.brindley_tau = float(taus[ip])
        row.mu_cm = float(mus[ip])
        row.mu_r = float(mus[ip] * radii[ip] * 1e-4)   # µm → cm
        row.particle_radius_um = float(radii[ip])
    qpa.microabsorption = MicroabsorptionCorrection(
        wavelength=float(wavelength), mu_mean_cm=float(mu_bar))
