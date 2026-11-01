"""Does the data want a rigid body to be a different shape? (``RIGID_BODY_MISFIT``)

A rigid body imposes a geometry, and a wrong one still refines to a converged
fit with sensible esds.  Measured on a synthetic pattern of a small organic
molecule: the right body fitted at GOF 1.01, the same body with one C–C bond 0.3 Å too long at GOF 2.33
(Δχ² ≈ 1.7×10⁴ at equal parameter count), and nothing named the body —
``RESTRAINT_TENSION`` cannot fire for a body, which has no restraint rows.

**The check.**  Per body, two short refinements from the fitted state, each an
internal trial (``telemetry=False``, no history):

* the **body** arm: the body's own DOFs (origin, rotation, torsions) and the
  caller's ``free`` globs;
* the **released** arm: the body removed and its heavy atoms' coordinates
  freed, held near the template by soft restraints on every template bond and
  bonded angle among them (observational restraints, Waser 1963, *Acta Cryst.*
  **16**, 1091), with the same ``free`` globs.  Each riding hydrogen
  (``RigidBody.riding``, WP-1810) keeps riding: its coordinate DOFs are tied
  to its parent's, so it takes its parent's every shift and its parent–H
  vector stays as the body placed it.  The arm then adds 3·n_heavy − n_pose
  parameters, read off the fit (36 on acridine, 14 heavy atoms against a
  6-DOF pose; issue #1008, WP-1989).  :func:`released_arm` builds it, and
  ``Refinement.released_arm`` is the same builder for a caller who fits it by
  hand or frees other members.

Both arms are history-free
:meth:`~rietx.refine.Refinement._trial` trials, so they carry
the caller's declarations (2θ limits, user ties, named variables, holds,
backend, solver).  A tie, variable-bearing tie or hold on a path of the released
body — or of a later body of its phase, whose index the removal shifts — cannot
mean the same thing in the released arm and is dropped there; the row's
``dropped`` lists each.  The arm's own rider ties are declared after that
drop, so it never reaches them.  The body arm's glob ``torsions.*.twist``
frees the body's torsions (WP-1808, #823).

**What riding by tie is.**  The tie is on the coordinate DOFs, which are
displacements in fractional coordinates, so at a held cell the parent–H
vector is kept exactly.  It is the riding model in its constant-vector form:
the H is not re-placed from its parent's neighbours, so a turn of the heavy
skeleton turns the body arm's H and leaves the released arm's where it points,
and a refined cell rescales the vector by the cell strain.  Re-placing it is
riding on a free atom (#759), not built.

The two are compared on the **data** χ² (restraint rows excluded, as every
``Statistics`` field is) with the package's two model-comparison tests, both at
the effective sample size N/f² (``optimize.statistics.effective_sample_size``,
#270): Hamilton's R-factor ratio test (Hamilton 1965, *Acta Cryst.* **18**, 502)
at ``alpha`` through :func:`~rietx.report.layer2.hamilton_justified`, and ΔBIC
(Schwarz 1978, *Ann. Statist.* **6**, 461) through
:func:`~rietx.report.layer2.delta_bic`, against ``bic_threshold`` (10, "very
strong": Kass & Raftery 1995, *J. Am. Stat. Assoc.* **90**, 773).  It fires on
the **conjunction**, so a serially correlated residual cannot make a released
molecule's noise-fitting look significant.

**Where.**  The released arm's restrained bond and angle deviations from the
template, in units of their restraint σ, ranked; the message names the worst
three.  A bond or angle with a riding H in it is not restrained: the tie
holds its bond exactly, and its angle would restrain the skeleton's turn
against an H that cannot turn.

**Not found.**  A template bond wrong by more than ``BOND_SLACK_ANG`` beyond
its covalent-radii sum is not found as a bond, so it is neither restrained in
the released arm nor named: the geometry table's criterion applies to the
template as placed.  The check is blind to that large-error case; read it as
"the data want a different shape", never as "the template is right".

It is never run inside ``fit()``: it costs two refinements per body, so a
caller asks for it once, before quoting a body's geometry or calling a solve
solved.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.pattern import require_two_theta
from ..schemas.structure import AngleRestraint, BondRestraint, Structure

#: the default significance of the Hamilton test (the conjunction's first half)
MISFIT_ALPHA = 1e-3
#: the default ΔBIC threshold, "very strong" (Kass & Raftery 1995)
MISFIT_BIC = 10.0


@dataclass
class BodyMisfitRow:
    """One body's comparison; ``deviations`` are (label, template, released, Δ/σ)."""

    phase_index: int
    body: str
    chi2_body: float
    chi2_released: float
    n_points: int
    n_effective: float
    n_free_body: int
    n_added: int
    f_statistic: float
    p_value: float
    delta_bic: float
    fires: bool
    deviations: list[tuple[str, float, float, float]] = field(default_factory=list)
    #: declarations of the caller's that could not follow into the released arm
    dropped: list[str] = field(default_factory=list)


@dataclass
class BodyMisfitResult:
    rows: list[BodyMisfitRow]
    diagnostics: list[Diagnostic]


@dataclass
class ReleasedArm:
    """One body's released arm, built by :func:`released_arm`.

    Fit it as the check does: a ``Refinement`` over ``structure``, each of
    ``ties`` declared with ``Refinement.tie(path, source)``, and a stage
    freeing ``free`` beside the scale and background globs.
    """

    #: the structure with the body removed and ``restraints`` added
    structure: Structure
    phase_index: int
    #: the body's name
    body: str
    #: the member labels whose coordinate DOFs ``free`` frees
    freed: list[str]
    #: each riding H that rides, by label, and the parent label it is tied to
    riders: dict[str, str]
    #: the restraints added, at the geometry the body placed its atoms in
    restraints: list[BondRestraint | AngleRestraint]
    #: the coordinate-DOF globs of the freed members
    free: list[str]
    #: each rider's DOF path and its source, ``{parent DOF path: coefficient}``
    ties: dict[str, dict[str, float]]


def _body_at(structure: Structure, body: str, phase: int | None):
    hits = [(ip, b) for ip, ph in enumerate(structure.phases)
            if phase is None or ip == phase
            for b, x in enumerate(ph.rigid_bodies) if x.name == body]
    if len(hits) != 1:
        names = sorted({x.name for ph in structure.phases for x in ph.rigid_bodies})
        raise ValueError(
            f"{'no' if not hits else 'more than one'} rigid body named {body!r}"
            + (f" in phase {phase}" if phase is not None else "")
            + (" (name the phase with phase=)" if hits else "")
            + f"; bodies: {names or 'none'}")
    return hits[0]


def _rider_ties(phase, ip: int, rider: int, parent: int) -> dict[str, dict[str, float]]:
    """The rider's DOF rows as its parent's: B_Hᵀ·θ_H = B_Pᵀ·θ_P, so both
    atoms take one fractional shift."""
    from ..crystallography.symmetry import resolve_group
    from ..crystallography.wyckoff import coordinate_basis, stabilizer_rotations
    from ..optimize import lapack

    sg = resolve_group(phase.space_group, phase.symmetry_operations)

    def basis(j):
        a = phase.atoms[j]
        return np.asarray(coordinate_basis(stabilizer_rotations(
            sg, np.array([a.x.value, a.y.value, a.z.value]))), dtype=np.float64)

    bh, bp = basis(rider), basis(parent)
    if not len(bp):
        return {}           # a parent with no freedom: the rider is held with it
    c = lapack.lstsq(bh.T, bp.T)[0] if len(bh) else None
    if c is None or not np.allclose(bh.T @ c, bp.T, atol=1e-12):
        raise ValueError(
            f"{phase.atoms[rider].label!r} cannot take every shift of its parent "
            f"{phase.atoms[parent].label!r}: its site symmetry allows fewer "
            "directions; free it with freed=")
    return {f"phases.{ip}.atoms.{rider}.dof.{k}": {
        f"phases.{ip}.atoms.{parent}.dof.{m}": float(c[k, m])
        for m in range(len(bp)) if c[k, m] != 0.0}
        for k in range(len(bh))}


def released_arm(structure: Structure, body: str, *, phase: int | None = None,
                 freed: Iterable[str] | None = None, bond_sigma: float = 0.02,
                 angle_sigma: float = 2.0) -> ReleasedArm:
    """The released arm of the rigid body ``body``: the model the misfit check
    compares the body with.

    The body is removed from its phase and its atoms stay where it placed
    them.  ``freed`` lists the member labels whose coordinates the arm frees;
    by default every member that is not a riding H.  Each riding H not in
    ``freed`` rides: its DOFs are tied to its parent's (the nearest atom of
    the template that does not ride, the rule
    :func:`~rietx.crystallography.riding.set_riding_lengths` places it by), so
    it adds no parameter.  ``freed=body.atoms`` frees every member, riding H
    included, as the check did before WP-1989.  A member neither freed nor
    riding is held where the body placed it.

    Every template bond and bonded angle with a freed atom in it and no rider
    is restrained at its placed value, bonds at ``bond_sigma`` (Å) and angles
    at ``angle_sigma`` (deg), by the geometry table's bonding criterion.
    ``phase`` names the phase when two phases carry a body of that name.
    """
    from ..crystallography.riding import riding_parents
    from ..crystallography.structure_factor import compile_phase_sites

    ip, b = _body_at(structure, body, phase)
    ph = structure.phases[ip]
    rb = ph.rigid_bodies[b]
    chosen = [lab for lab in rb.atoms if lab not in rb.riding] if freed is None \
        else list(dict.fromkeys(freed))
    outside = sorted(set(chosen) - set(rb.atoms))
    if outside:
        raise ValueError(f"freed= names atoms that are not members of {body!r}: {outside}")
    index = {a.label: j for j, a in enumerate(ph.atoms)}
    riders = {h: p for h, p in riding_parents(rb).items() if h not in chosen}
    free_j = {index[lab] for lab in chosen}
    rider_j = {index[h] for h in riders}
    _, bonds, angles = _template_geometry(ph, rb)
    sites = compile_phase_sites(ph)
    ident = {j: _identity_op(sites, j) for j in (index[lab] for lab in rb.atoms)}

    def kept(*js):
        return not rider_j & set(js) and bool(free_j & set(js))
    restraints: list[BondRestraint | AngleRestraint] = [
        BondRestraint(atom_i=i, atom_j=j, target=d, sigma=bond_sigma, op_index=ident[j])
        for i, j, d in bonds if kept(i, j)]
    restraints += [AngleRestraint(atom_i=i, atom_j=k, atom_k=j, target_deg=a,
                                  sigma=angle_sigma, op_index_i=ident[i],
                                  op_index_k=ident[j])
                   for i, k, j, a in angles if kept(i, k, j)]
    released = structure.model_copy(deep=True)
    released.phases[ip] = ph.model_copy(update={
        "rigid_bodies": [x for x in ph.rigid_bodies if x.name != rb.name],
        "restraints": [*ph.restraints, *restraints]}, deep=True)
    ties: dict[str, dict[str, float]] = {}
    for h, p in riders.items():
        ties.update(_rider_ties(released.phases[ip], ip, index[h], index[p]))
    return ReleasedArm(
        structure=released, phase_index=ip, body=rb.name, freed=chosen, riders=riders,
        restraints=restraints,
        free=[f"phases.{ip}.atoms.{index[lab]}.dof.*" for lab in chosen], ties=ties)


def _element(species: str) -> str:
    """``crystallography.species.element_symbol``, the one parser: a label gemmi
    maps to its 1.0 Å placeholder is refused there, and would otherwise change
    which pairs count as bonds."""
    from ..crystallography.species import element_symbol

    return element_symbol(species)


def _template_geometry(phase, body):
    """Bonded pairs and angles of the body as placed, by the geometry table's
    bonding criterion (covalent radii + ``BOND_SLACK_ANG``)."""
    import gemmi

    from ..model.geometry import BOND_SLACK_ANG
    from ..params.derived import cartesian_frame

    index = {a.label: j for j, a in enumerate(phase.atoms)}
    members = [index[lab] for lab in body.atoms]
    m = np.asarray(cartesian_frame(phase.cell.lengths_angles()))
    xyz = {j: m @ np.array([phase.atoms[j].x.value, phase.atoms[j].y.value,
                            phase.atoms[j].z.value]) for j in members}
    rad = {j: float(gemmi.Element(_element(phase.atoms[j].species)).covalent_r)
           for j in members}
    bonds = []
    for a_i, i in enumerate(members):
        for j in members[a_i + 1:]:
            d = float(np.linalg.norm(xyz[i] - xyz[j]))
            if d <= rad[i] + rad[j] + BOND_SLACK_ANG:
                bonds.append((i, j, d))
    neigh: dict[int, list[int]] = {j: [] for j in members}
    for i, j, _ in bonds:
        neigh[i].append(j)
        neigh[j].append(i)
    angles = []
    for k, nb in neigh.items():
        for a in range(len(nb)):
            for b in range(a + 1, len(nb)):
                i, j = nb[a], nb[b]
                u, v = xyz[i] - xyz[k], xyz[j] - xyz[k]
                ang = math.degrees(math.acos(np.clip(
                    u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1.0, 1.0)))
                if 5.0 < ang < 175.0:         # a straight angle is not restrainable
                    angles.append((i, k, j, ang))
    return members, bonds, angles


def _identity_op(sites, j) -> int:
    ops_r, ops_t = sites.ops[j]
    for k, (r, t) in enumerate(zip(ops_r, ops_t, strict=True)):
        if np.array_equal(np.asarray(r), np.eye(3)) and np.allclose(np.asarray(t), 0.0):
            return k
    raise ValueError(f"atom {j}'s orbit holds no identity operation")


def _later_bodies(ip: int, b: int):
    """The matcher for paths of body ``b`` of phase ``ip`` or of a later body,
    whose index removing ``b`` shifts."""
    import re
    pat = re.compile(rf"phases\.{ip}\.rigid_bodies\.(\d+)\.")

    def hit(path: str) -> bool:
        m = pat.match(path)
        return m is not None and int(m.group(1)) >= b
    return hit


def _fit(ref, structure, data, globs, max_iter, drop=None, ties=None):
    """One arm: a trial over the caller's declarations, on ``structure``.

    ``drop`` (a path predicate) removes the ties and holds that could not mean
    the same thing on ``structure``; the paths dropped are returned.  ``ties``
    (``ReleasedArm.ties``) are the arm's own, declared once ``structure`` is
    in, so the drop never reaches them.
    """
    from ..strategy.staged import RefinementPlan, Stage

    trial = ref._trial(record=False)
    dropped: list[str] = []
    if drop is not None:
        for path in [p for p, s in trial._ties.items()
                     if drop(p) or any(drop(q) for q, _ in s.terms)]:
            del trial._ties[path]
            dropped.append(f"tie {path}")
        for path in sorted(p for p in trial._user_holds if drop(p)):
            trial._user_holds.discard(path)
            dropped.append(f"hold {path}")
    trial.edit(structure=structure)
    if ties:
        # the caller's free set names the removed body's rows, and a tie's
        # table build would restore it and warn they are gone; the arm's one
        # stage replaces the free set anyway
        trial._free_paths = []
        for path, source in ties.items():
            trial.tie(path, source)
    res = trial.fit(data, mode=ref._mode, telemetry=False,
                    two_theta_limits=ref._two_theta_limits,
                    plan=RefinementPlan(stages=[
                        Stage("misfit_check", list(globs), max_iter=max_iter)],
                        # the plan settings the caller's fit ran with
                        # (``Refinement._plan_settings``, WP-2002 B1)
                        correlation_guard=trial._plan_settings["correlation_guard"],
                        phase_support_sigma=trial._plan_settings["phase_support_sigma"],
                        # and no closing stage: the two arms are compared with
                        # each other, never with the fit, so their windows need
                        # only agree, and a trial the package discards pays for
                        # no extra solve (WP-2002, the sixth round's Q1 and Q2)
                        closing_window_tol=None))
    return trial, res, dropped


def rigid_body_misfit(ref, data, *, free: tuple[str, ...] = (
        "phases.*.scale", "instrument.background.*"),
        alpha: float = MISFIT_ALPHA, bic_threshold: float = MISFIT_BIC,
        bond_sigma: float = 0.02, angle_sigma: float = 2.0,
        max_iter: int = 200,
        on_arm: Callable[[str, str, object], None] | None = None) -> BodyMisfitResult:
    """Test every rigid body of ``ref``'s fitted model against ``data``.

    ``ref`` must have been fitted: both arms start from its refined state, and
    from an unrefined pose a badly placed body would read as a misshapen one.
    ``on_arm(body, "body" | "released", result)`` sees each arm's result.

    ``free`` are the non-body globs both arms refine (the scale and background
    by default; add the profile or a free atom's DOFs to match your plan).
    ``bond_sigma`` (Å) and ``angle_sigma`` (deg) are the released arm's
    restraint widths: stiff enough to keep the molecule a molecule, loose enough
    that the data can say which bond it disagrees with.  Returns a row per
    body and a ``RIGID_BODY_MISFIT`` warning per body that fails.
    """
    require_two_theta(data, "rigid_body_misfit()", instrument=ref.instrument)
    if ref.result_ is None:
        raise ValueError(
            "rigid_body_misfit needs a fitted Refinement: both arms start from "
            "its refined state, and from an unrefined pose a badly placed body "
            "would read as a misshapen one. Call ref.fit(...) first.")
    from scipy.stats import f as f_dist

    from ..optimize.statistics import _chi2_absolute, effective_sample_size
    from ..params.derived import cartesian_frame
    from .layer2 import _hamilton_f, delta_bic, hamilton_justified

    base: Structure = ref.fitted_structure.model_copy(deep=True)
    rows: list[BodyMisfitRow] = []
    diagnostics: list[Diagnostic] = []
    for ip, phase in enumerate(base.phases):
        if not phase.rigid_bodies:
            continue
        labels = [a.label for a in phase.atoms]
        index = {lab: j for j, lab in enumerate(labels)}
        for b, body in enumerate(phase.rigid_bodies):
            bb = f"phases.{ip}.rigid_bodies.{b}"
            _, res_a, _ = _fit(ref, base.model_copy(deep=True), data,
                               [*free, f"{bb}.origin.dof.*", f"{bb}.rotation.*",
                                f"{bb}.torsions.*.twist"], max_iter)
            if on_arm is not None:
                on_arm(body.name, "body", res_a)
            # the released arm: same model, this body's heavy atoms freed and
            # held by restraints at the geometry the body placed them in, each
            # riding H tied to its parent (WP-1989)
            arm = released_arm(base, body.name, phase=ip, bond_sigma=bond_sigma,
                               angle_sigma=angle_sigma)
            members = [index[lab] for lab in body.atoms]
            ref_b, res_b, dropped = _fit(
                ref, arm.structure, data, [*free, *arm.free], max_iter,
                drop=_later_bodies(ip, b), ties=arm.ties)
            if on_arm is not None:
                on_arm(body.name, "released", res_b)
            sa, sb = res_a.statistics, res_b.statistics
            chi_a, chi_b = _chi2_absolute(sa), _chi2_absolute(sb)
            n = int(sa.n_points)
            n_eff = effective_sample_size(n, sa.esd_inflation)
            k_a = int(sa.n_free_parameters)
            added = int(sb.n_free_parameters) - k_a
            test = _hamilton_f(chi_a, chi_b, n, k_a, added, n_effective=n_eff)
            if test is None:
                f_stat, p = 0.0, 1.0
            else:
                f_stat, dof = test
                p = float(f_dist.sf(f_stat, added, dof))
            dbic = delta_bic(chi_a, chi_b, n, added, n_effective=n_eff)
            fires = (hamilton_justified(chi_a, chi_b, n, k_a, added, alpha=alpha,
                                        n_effective=n_eff)
                     and dbic > bic_threshold)
            # where: the released geometry against the template, in σ units,
            # for each restrained bond and angle
            fitted = ref_b.fitted_structure.phases[ip]
            devs = []
            m = np.asarray(cartesian_frame(fitted.cell.lengths_angles()))

            def cart(j, ph=fitted, m=m):
                return m @ np.array([ph.atoms[j].x.value, ph.atoms[j].y.value,
                                     ph.atoms[j].z.value])
            for r in arm.restraints:
                if isinstance(r, BondRestraint):
                    i, j, d = r.atom_i, r.atom_j, r.target
                    d1 = float(np.linalg.norm(cart(i) - cart(j)))
                    devs.append((f"{labels[i]}–{labels[j]}", d, d1, (d1 - d) / bond_sigma))
                else:
                    i, k, j, a = r.atom_i, r.atom_j, r.atom_k, r.target_deg
                    u, v = cart(i) - cart(k), cart(j) - cart(k)
                    a1 = math.degrees(math.acos(np.clip(
                        u @ v / (np.linalg.norm(u) * np.linalg.norm(v)), -1, 1)))
                    devs.append((f"{labels[i]}–{labels[k]}–{labels[j]}", a, a1,
                                 (a1 - a) / angle_sigma))
            devs.sort(key=lambda r: -abs(r[3]))
            row = BodyMisfitRow(
                phase_index=ip, body=body.name, chi2_body=chi_a, chi2_released=chi_b,
                n_points=n, n_effective=n_eff, n_free_body=k_a, n_added=added,
                f_statistic=f_stat, p_value=p, delta_bic=dbic, fires=fires,
                deviations=devs, dropped=dropped)
            rows.append(row)
            if fires:
                worst = "; ".join(
                    f"{lab} {t:.3f} → {r:.3f} ({s:+.1f}σ)" for lab, t, r, s in devs[:3])
                diagnostics.append(Diagnostic(
                    level="warning", code="RIGID_BODY_MISFIT",
                    message=(f"Rigid body {body.name!r} (phase {ip}) fits the data "
                             f"better released as restrained free atoms: "
                             f"χ² {chi_a:.4g} → {chi_b:.4g} for {added} more "
                             f"parameters, Hamilton p = {p:.2g}, ΔBIC = {dbic:.1f} at "
                             f"N_eff = {n_eff:.0f}. Largest released deviations "
                             f"from the template: {worst}."
                             + (f" Not carried into the released arm: "
                                f"{'; '.join(dropped)}." if dropped else "")),
                    where=[f"phases.{ip}.atoms.{j}" for j in members],
                    suggestion=("Check the named bond and angle values in the "
                                "template against their source, and check the "
                                "atom assignment."),
                    value=dbic))
    return BodyMisfitResult(rows=rows, diagnostics=diagnostics)
