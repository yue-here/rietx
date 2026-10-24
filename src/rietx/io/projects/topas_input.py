"""A whole TOPAS ``.inp`` from a rietx model: the refined set, the instrument, the data.

:func:`~rietx.io.projects.topas.write_topas_inp` on its own writes the ``str``
blocks with each ``Parameter``'s stored flag, and nothing outside them. This
module is what it calls when it is given more:

* ``free=`` — a ``Refinement`` (or its ``parameters()``, a ``RefinementResult``,
  a list of paths): the free set and the ties, written as TOPAS names and
  equations (:mod:`.topas_refined`);
* ``scale="topas"`` — the scale in TOPAS's convention, stated in a comment;
* ``instrument=`` / ``pattern=`` — the data file, the wavelength, the neutron
  flag, the Lorentz-polarisation factor, the zero and displacement, the
  background, the profile, the axial divergence and the extinction (issue #732);
* ``p1_expand`` — a magnetic phase restated in P1, with every copy tied back to
  the parameter it is a copy of (#721);
* a magnetic phase with a magnetic-only width is written as two ``str``: the
  nuclear part and a ``mag_only`` magnetic part whose Lorentzian widths carry
  the extra term, which is rietx's own model term for term (§ The magnetic
  width).

Everything here was written from the TOPAS Technical Reference (keywords and
equations) and from TOPAS 6 runs as a black box; no TOPAS code or macro body
was read. Each mapping cites where it came from. A moment's equations
(``Sin``/``Cos`` of its angle DOFs, taken here in radians) have not been run in
TOPAS.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

import numpy as np

from ...model.profiles.caglioti import _MIN_GAMMA_G2  # the Γ_G² clamp, deg²
from .topas_refined import (
    Affine,
    Expr,
    RefinedSet,
    Slot,
    number,
    render_slots,
    stored_free_paths,
    topas_scale_factor,
)

_CELL_KEYS = (("a", "a"), ("b", "b"), ("c", "c"), ("al", "alpha"),
              ("be", "beta"), ("ga", "gamma"))
_ADP_KEYS = ("u11", "u22", "u33", "u12", "u13", "u23")
_MOMENT_KEYS = ("mlx", "mly", "mlz")

#: The Thompson-Cox-Hastings constants rietx uses (``model.profiles.pseudovoigt``
#: ``_TCH_GAMMA``/``_TCH_ETA``; Thompson, Cox & Hastings 1987). Written into the
#: file rather than left to a TOPAS macro, so the profile TOPAS computes is
#: rietx's: the Technical Reference prints 0.1116 for the cubic η term where
#: TCH (1987) and rietx have 0.11116.
_TCH_GAMMA = (2.69269, 2.42843, 4.47163, 0.07842)
_TCH_ETA = (1.36603, -0.47719, 0.11116)
#: rietx's Sabine extinction constants (``model.extinction``).
_SABINE_LAUE = (-0.5, 0.25, -0.10416667, 0.036458333, -0.0109375, 2.8497409e-3)
_SABINE_XPOL = 0.079411
#: The goniometer radius written when the instrument states none. Only the
#: axial lengths and a displacement read it, and both are written against the
#: same number, so its value is a convention of the file, not a measurement.
DEFAULT_RADIUS_MM = 217.5


def _p(ip: int, rest: str) -> str:
    return f"phases.{ip}.{rest}"


def _a(ip: int, ia: int, rest: str) -> str:
    return f"phases.{ip}.atoms.{ia}.{rest}"


# ----------------------------------------------------------------- moments

def _moment_component_items(phase, ip, ia, atom, refined: RefinedSet,
                            rotation: np.ndarray | None = None) -> list:
    """``mlx … mly … mlz …`` for one written site, as slots over the DOFs.

    The moment block's freedom is ``…moment.dof<k>`` (a signed modulus on a
    one-dimensional subspace, a modulus and angles on a larger one;
    ``crystallography.magnetic.moments``), so each written component is that
    function of the DOFs, carried to the image by ``rotation`` (the axial matrix
    of a copy) and divided by its edge (TOPAS's fractional basis, measured:
    crystal-axis μ_B = ``mlx``·a). With every angle held it is linear in the
    modulus and written as an affine equation; otherwise through ``Sin``/``Cos``.
    A component the site's symmetry forbids has no term and is written held,
    which is what TOPAS needs ("cannot be refined as it has no derivative").
    """
    from ...crystallography.magnetic.moments import (
        dofs_from_moment,
        moment_frame,
        moment_from_dofs,
    )

    cell = phase.cell
    edges = (cell.a.value, cell.b.value, cell.c.value)
    group = phase.magnetic_symmetry.group()
    xyz = (atom.x.value, atom.y.value, atom.z.value)
    cell6 = cell.lengths_angles()
    frame = moment_frame(group.allowed_moment_basis(xyz), cell6)
    rot = np.eye(3) if rotation is None else np.asarray(rotation, dtype=float)
    n = len(frame)
    m_now = rot @ np.asarray(atom.moment.values(), dtype=float)
    seed = (dofs_from_moment(frame, cell6, atom.moment.values()) if n
            else np.zeros(0))
    dof_aff = []
    for k in range(n):
        path = _a(ip, ia, f"moment.dof{k}")
        value = (refined.rows[path].value if refined.rows is not None
                 and path in refined.rows else float(seed[k]))
        dof_aff.append(refined.affine(path, value))
    angles_held = all(not a.terms for a in dof_aff[1:])
    out = []
    if n and angles_held:
        unit = rot @ moment_from_dofs(frame, [1.0] + [a.const for a in dof_aff[1:]])
    for i, key in enumerate(_MOMENT_KEYS):
        if n == 0:
            out += [f" {key} ", Slot(Affine({}, 0.0), 1.0 / edges[i], 0.0)]
        elif angles_held:
            out += [f" {key} ", Slot(dof_aff[0] * float(unit[i]), 1.0 / edges[i],
                                     float(m_now[i]), carry=False)]
        else:
            e = frame @ rot.T
            c = [number(e[k][i] / edges[i]) for k in range(n)]
            if n == 2:
                tpl = f"= {{0}}*(({c[0]})*Cos({{1}}) + ({c[1]})*Sin({{1}}));"
            else:
                tpl = (f"= {{0}}*(({c[0]})*Sin({{1}})*Cos({{2}}) + "
                       f"({c[1]})*Sin({{1}})*Sin({{2}}) + ({c[2]})*Cos({{1}}));")
            out += [f" {key} ", Expr(tpl, dof_aff)]
    if atom.moment.g is not None:
        out.append(f" mg ! {number(atom.moment.g)}")
    return out


# ----------------------------------------------------------------- one phase

def _site_items(phase, ip, ia, atom, refined, *, label, species, xyz_aff, xyz_now,
                occ_aff, biso_aff, aniso, moment_rotation, with_moment, mag_only):
    from .topas import _number  # the legacy writer's refusal of a non-finite value

    items: list = [f"  site {label}"]
    for key, aff, now in zip(("x", "y", "z"), xyz_aff, xyz_now):
        items += [f" {key} ", Slot(aff, 1.0, now,
                                   path=None if moment_rotation is not None
                                   or label != atom.label else _a(ip, ia, key))]
    items += [f" occ {species} ", Slot(occ_aff, 1.0, atom.occ.value)]
    if aniso is not None:
        items.append(f" beq ! {_number(atom.biso.value)}")
        for key, (aff, now) in zip(_ADP_KEYS, aniso):
            items += [f" {key} ", Slot(aff, 1.0, now)]
    else:
        items += [" beq ", Slot(biso_aff, 1.0, atom.biso.value)]
    if with_moment and atom.moment is not None:
        items += _moment_component_items(phase, ip, ia, atom, refined, moment_rotation)
    if mag_only:
        items.append(" mag_only")
    items.append("\n")
    return items


def _aniso_affines(refined, ip, ia, atom):
    if atom.aniso is None:
        return None
    return [(refined.affine(_a(ip, ia, k), getattr(atom.aniso, k).value),
             getattr(atom.aniso, k).value) for k in _ADP_KEYS]


def _image_maps(phase, atom):
    """``(rot, tran, shift, axial)`` per image of ``atom`` — the forward model's
    own expansion (``structure_factor.select_orbit_ops``), in its order, with the
    whole-cell shift that wraps each image into [0, 1) and the axial matrix of
    each image's moment (``magnetic.scattering._axial_matrices``)."""
    from ...crystallography.structure_factor import select_orbit_ops
    from ...crystallography.symmetry import resolve_group

    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
    rot, tran = select_orbit_ops(sg, xyz)
    axial = None
    if atom.moment is not None and phase.magnetic_symmetry is not None:
        from ...crystallography.magnetic.scattering import _axial_matrices
        axial = _axial_matrices(phase.magnetic_symmetry.group(), xyz, rot, tran,
                                phase.name, atom.label)
    out = []
    for k in range(len(rot)):
        pos = rot[k] @ xyz + tran[k]
        wrapped = pos % 1.0
        wrapped[wrapped >= 1.0 - 1e-12] = 0.0
        out.append((np.asarray(rot[k], dtype=float), np.asarray(tran[k], dtype=float),
                    wrapped - pos, None if axial is None else axial[k]))
    return out


def _p1_labels(label: str, n: int, taken: set[str]) -> list[str]:
    """The ``site`` labels of one atom's ``n`` images: ``label`` alone for one,
    else ``<label>_<k>`` made unique against every other label of the phase and
    each other (``taken`` grows; ``magnetic.p1._unique``'s rule, an underscore appended), since a
    repeated label is read back as one site."""
    if n == 1:
        return [label]
    out = []
    for k in range(n):
        cand = f"{label}_{k + 1}"
        while cand in taken:
            cand += "_"
        taken.add(cand)
        out.append(cand)
    return out


def _aniso_image_matrix(rot, cell):
    """The 6×6 linear map U^ij → U^ij of the image under ``rot`` (U* → R·U*·Rᵀ)."""
    from ...crystallography.adp import reciprocal_axis_lengths, tensor_from_voigt, voigt_from_tensor

    astar = np.asarray(reciprocal_axis_lengths(*cell), dtype=np.float64)
    scale = astar[:, None] * astar[None, :]
    m = np.zeros((6, 6))
    for j in range(6):
        u = np.zeros(6)
        u[j] = 1.0
        ustar = tensor_from_voigt(u) * scale
        m[:, j] = voigt_from_tensor((rot @ ustar @ rot.T) / scale)
    return m


def phase_items(structure, ip, phase, refined: RefinedSet, *, scale_factor: float,
                header: list[str], profile: list | None, extinction: list | None,
                p1: bool, part: str, species_of) -> list:
    """One ``str``: ``part`` is ``"all"``, ``"nuclear"`` (no moments) or
    ``"magnetic"`` (moment-bearing sites only, each ``mag_only``)."""
    items: list = ["str\n"]
    items += [f"  {h}\n" for h in header]
    items += ["  scale ", Slot(refined.affine(_p(ip, "scale"), phase.scale.value),
                                scale_factor, phase.scale.value), "\n"]
    for key, attr in _CELL_KEYS:
        param = getattr(phase.cell, attr)
        items += [f"  {key} ", Slot(refined.affine(_p(ip, f"cell.{attr}"), param.value),
                                     1.0, param.value), "\n"]
    if profile:
        items += profile
    else:
        items += width_items(ip, phase, refined)
    if extinction:
        items += extinction
    from ...crystallography.symmetry import get_spacegroup
    from .topas import _snapped_xyz

    sg = get_spacegroup(phase.space_group)
    cell6 = phase.cell.lengths_angles()
    with_moment = part != "nuclear"
    taken = {a.label for a in phase.atoms}
    for ia, atom in enumerate(phase.atoms):
        if part == "magnetic" and atom.moment is None:
            continue
        species = species_of(atom, with_moment)
        if not p1:
            # a site near a special position is written on it, as the str-only
            # writer writes it (#710): TOPAS reads x 0.3333 as a general position
            snapped = _snapped_xyz(sg, atom)
            items += _site_items(
                phase, ip, ia, atom, refined, label=atom.label, species=species,
                xyz_aff=[refined.affine(_a(ip, ia, k), getattr(atom, k).value)
                         + (now - getattr(atom, k).value)
                         for k, now in zip(("x", "y", "z"), snapped)],
                xyz_now=snapped,
                occ_aff=refined.affine(_a(ip, ia, "occ"), atom.occ.value),
                biso_aff=refined.affine(_a(ip, ia, "biso"), atom.biso.value),
                aniso=_aniso_affines(refined, ip, ia, atom),
                moment_rotation=None, with_moment=with_moment,
                mag_only=part == "magnetic")
            continue
        # P1: every image of the site, each tied to the parameters of the site
        xyz_aff = [refined.affine(_a(ip, ia, k), getattr(atom, k).value)
                   for k in ("x", "y", "z")]
        aniso = _aniso_affines(refined, ip, ia, atom)
        maps = _image_maps(phase, atom)
        labels = _p1_labels(atom.label, len(maps), taken)
        for k, (rot, tran, shift, axial) in enumerate(maps):
            img = [sum((xyz_aff[j] * rot[i, j] for j in range(3)), Affine({}, 0.0))
                   + float(tran[i] + shift[i]) for i in range(3)]
            now = [float(sum(rot[i, j] * getattr(atom, "xyz"[j]).value for j in range(3))
                         + tran[i] + shift[i]) for i in range(3)]
            img_aniso = None
            if aniso is not None:
                mat = _aniso_image_matrix(rot, cell6)
                img_aniso = []
                for r in range(6):
                    aff = sum((aniso[c][0] * mat[r, c] for c in range(6)), Affine({}, 0.0))
                    img_aniso.append((aff, float(mat[r] @ np.array([v for _, v in aniso]))))
            label = labels[k]
            items += _site_items(
                phase, ip, ia, atom, refined, label=label, species=species,
                xyz_aff=img, xyz_now=now,
                occ_aff=refined.affine(_a(ip, ia, "occ"), atom.occ.value),
                biso_aff=refined.affine(_a(ip, ia, "biso"), atom.biso.value),
                aniso=img_aniso, moment_rotation=axial, with_moment=with_moment,
                mag_only=part == "magnetic")
    return items


def width_items(ip, phase, refined: RefinedSet) -> list:
    """The phase's sample widths as ``str``-level ``lor_fwhm``/``gauss_fwhm``.

    :func:`~.topas._width_lines`, the structure-only writer's own lines (one
    spelling for both, Λ included), with each term a free source reaches
    written over its name and a free term at zero kept. Only in a ``str``
    with no profile: :func:`_profile_items` folds the same terms into
    ``pv_fwhm``/``pv_lor``, and TOPAS would add a ``str``-level width to them
    a second time.
    """
    from operator import attrgetter

    from .topas import _number, _width_lines

    parts: list[Affine] = []

    def keep(key):
        value = attrgetter(key)(phase).value
        return bool(refined.affine(_p(ip, key), value).terms)

    def spell(value, key):
        aff = refined.affine(_p(ip, key), value)
        if not aff.terms:
            return _number(value)
        parts.append(aff)
        return f"{{{len(parts) - 1}}}"

    out: list = []
    for line in _width_lines(phase, spell, keep):
        out += [Expr(line, parts), "\n"] if parts else [line + "\n"]
    return out


# ----------------------------------------------------------------- profile

def _profile_items(instrument, ip, phase, refined: RefinedSet, *, magnetic: bool) -> list:
    """``peak_type pv`` with rietx's TCHZ width laws written as equations.

    rietx: Γ_G² = (U + gauss_strain)·tan²θ + V·tanθ + W + gauss_size/cos²θ
    (floored at 1e-8 deg²), Γ_L = (X + lor_size)/cosθ + (Y + lor_strain)·tanθ
    (``model.profiles.caglioti``), and the magnetic part adds
    ``magnetic_lor_size``/``magnetic_lor_strain`` to the two Lorentzian terms
    (``schemas.structure.Phase``). Γ and η are Thompson, Cox & Hastings
    (1987), *J. Appl. Cryst.* 20, 79. TOPAS ``Th`` is θ in radians, and
    ``pv_fwhm``/``pv_lor`` are the width and Lorentzian fraction of its ``pv``
    peak type (Technical Reference § 5.2); the profile keywords sit in the
    ``str`` because a TOPAS peak shape is a phase's. The widths are written as
    equations in rietx's own terms, by their physics (size ↔ 1/cosθ, strain ↔
    tanθ), so no program's X/Y letters are involved.
    """
    prof = instrument.profile
    kind = getattr(prof, "shape", None)
    if kind != "tchz_pv":
        raise ValueError(
            f"instrument.profile is {type(prof).__name__} ({kind!r}); only the "
            f"TCHZ pseudo-Voigt has a TOPAS statement here (peak_type pv with "
            f"rietx's width laws). Write the structure alone (no instrument=)")
    if getattr(phase, "microstrain", None) is not None:
        raise ValueError(
            f"phase {phase.name!r} carries a Stephens microstrain block, which "
            f"this writer does not state in TOPAS; write without instrument=")

    def aff(path, param):
        return refined.affine(path, param.value)

    u = aff("instrument.profile.u", prof.u)
    v = aff("instrument.profile.v", prof.v)
    w = aff("instrument.profile.w", prof.w)
    x = aff("instrument.profile.x", prof.x) + aff(_p(ip, "lor_size"), phase.lor_size)
    y = aff("instrument.profile.y", prof.y) + aff(_p(ip, "lor_strain"), phase.lor_strain)
    u = u + aff(_p(ip, "gauss_strain"), phase.gauss_strain)
    z = aff(_p(ip, "gauss_size"), phase.gauss_size)
    if magnetic:
        x = x + aff(_p(ip, "magnetic_lor_size"), phase.magnetic_lor_size)
        y = y + aff(_p(ip, "magnetic_lor_strain"), phase.magnetic_lor_strain)
    g = (f"Sqrt(Max({{0}}*Tan(Th)^2 + {{1}}*Tan(Th) + {{2}} + {{3}}/Cos(Th)^2, "
         f"{number(_MIN_GAMMA_G2)}))")
    lor = "({4}/Cos(Th) + {5}*Tan(Th))"
    a1, a2, a3, a4 = _TCH_GAMMA
    gam = (f"({g}^5 + {a1}*{g}^4*{lor} + {a2}*{g}^3*{lor}^2 + {a3}*{g}^2*{lor}^3"
           f" + {a4}*{g}*{lor}^4 + {lor}^5)^0.2")
    e1, e2, e3 = _TCH_ETA
    q = f"({lor}/{gam})"
    eta = f"({e1}*{q} - {-e2}*{q}^2 + {e3}*{q}^3)"
    parts = [u, v, w, z, x, y]
    return ["  peak_type pv\n",
            "  pv_fwhm = ", Expr(gam, parts), ";\n",
            "  pv_lor = ", Expr(eta, parts), ";\n"]


def _extinction_items(instrument, ip, phase, refined: RefinedSet) -> list:
    """rietx's Sabine extinction as a ``scale_pks`` equation.

    Sabine (1988), *Acta Cryst.* A44, 368; Sabine, Von Dreele & Jørgensen
    (1988), *Acta Cryst.* A44, 374 (the references ``model.extinction`` lists).

    E = E_B sin²θ + E_L cos²θ with x = ext·|F|²·(λ/V)²·Xpol, E_B = (1 + x)^-½,
    and E_L the six-term series for x ≤ 1 and √(2/πx)(1 − 1/(8x)) above
    (``model.extinction``). TOPAS states |F|² per reflection as
    ``A01^2 + B01^2 + A11^2 + B11^2`` (Technical Reference § 10.2.2, p. 71,
    eqs. 10-10 and 10-12) and the cell volume as ``Get(cell_volume)``. Its unit
    is measured against TOPAS 6, never assumed: a neutron |F|² there is in barn,
    rietx's in fm², hence the 100 (``case_nacl_neutron``); an X-ray |F|² is in
    electrons², rietx's unit, hence 1 (``case_nacl_xray`` at extinction 20:
    TOPAS's Y_calc matched at 2.6e-3, the factor 100 misses by 0.79, and its
    A01..B11 sum is 1.0008 × rietx's |F|² per reflection). λ is the first
    emission line's, for every line. Written only when the extinction is on or
    free.
    """
    path = _p(ip, "extinction")
    if phase.extinction.value == 0.0 and not refined.is_free(path):
        return []
    refined.named.add(path)       # read back by name (topas_ties)
    ext = refined.affine(path, phase.extinction.value)
    lam = float(instrument.source.lines[0].wavelength.value)
    f2 = "(A01^2 + B01^2 + A11^2 + B11^2)"
    if instrument.source.kind == "neutron_cw":
        f2 = "100*" + f2          # barn -> fm²
    xv = (f"({{0}}*{f2}*({number(lam)}/Get(cell_volume))^2*{number(_SABINE_XPOL)}"
          f"*(1 + Cos(2*Th)^2)/2)")
    c = _SABINE_LAUE
    series = " + ".join(f"({number(ci)})*{xv}^{i + 1}" for i, ci in enumerate(c))
    el = (f"If({xv} <= 0, 1, If({xv} <= 1, 1 + {series}, "
          f"Sqrt(2/(Pi*{xv}))*(1 - 0.125/{xv})))")
    e = f"(1/Sqrt(1 + {xv}))*Sin(Th)^2 + {el}*Cos(Th)^2"
    return ["  scale_pks = ", Expr(e, [ext]), ";\n"]


# --------------------------------------------------------------- instrument

def _fit_points(pattern):
    tt, y, s = pattern.tt(), pattern.y(), pattern.sig()
    mask = pattern.in_range_mask()
    idx = np.nonzero(mask)[0]
    if len(idx) < 10:
        raise ValueError("fewer than 10 points remain in the fit range")
    lo, hi = idx[0], idx[-1] + 1
    return tt[lo:hi], y[lo:hi], s[lo:hi], mask[lo:hi]


def _bspline_pieces(breakpoints, k: int):
    """Basis function ``k`` of rietx's clamped cubic B-spline as cubic pieces.

    ``[(lo, hi, (a0, a1, a2, a3)), …]`` with N_k(x) = Σ aₙ (x − lo)ⁿ on
    [lo, hi): the knot vector is ``background.models.bspline_design_matrix``'s
    own (the breakpoints with each end repeated three more times), and the
    power-basis coefficients are scipy's exact conversion of the basis.
    """
    from scipy.interpolate import BSpline, PPoly

    b = np.asarray(breakpoints, dtype=np.float64)
    t = np.concatenate([[b[0]] * 3, b, [b[-1]] * 3])
    coef = np.zeros(len(t) - 4)
    coef[k] = 1.0
    pp = PPoly.from_spline(BSpline(t, coef, 3))
    out = []
    for i in range(len(pp.x) - 1):
        lo, hi = float(pp.x[i]), float(pp.x[i + 1])
        if hi <= lo:
            continue
        c = pp.c[:, i][::-1]          # ascending powers of (x − lo)
        if np.all(np.abs(c) < 1e-300):
            continue
        out.append((lo, hi, tuple(float(v) for v in c)))
    return out


def background_items(instrument, tt, mask, sigma, refined: RefinedSet,
                     notes: list[str]) -> list:
    """The instrument's background in TOPAS, as the same function rietx fits.

    * **Chebyshev** → ``bkg``: TOPAS's ``bkg`` is the Chebyshev series on its
      data range (measured, TOPAS 6 against rietx, 1.7e-9 of the peak), and the
      data file written here runs from the first to the last fitted point, which
      is rietx's domain. ``bkg`` takes one flag for every coefficient.
    * **P-spline** → one ``fit_obj`` per cubic B-spline basis function, each the
      basis written as its cubic pieces (``If`` on ``X``) times its coefficient,
      and rietx's smoothness penalty as TOPAS ``penalty`` terms. TOPAS minimises
      K·[Σ w (Yo − Yc)² + K₁ K_P Σ P] (Technical Reference eq. 4-1 to 4-3, K₁ and
      K_P at their default of 1), so ``penalty = r²`` for each of rietx's
      penalty rows r = √λ·s·(c_i − 2c_{i+1} + c_{i+2}) (s = √(m/n)/σ̄ when λ is
      dimensionless, ``background.models.pspline_penalty_scale``) is rietx's
      objective term for term. A Chebyshev series refitted to it is a
      different, unpenalised background, and a TOPAS refinement from it lands
      on another minimum, the background taking up structure.
    """
    from ...background.models import pspline_penalty_scale, second_difference_matrix
    from ...schemas.instrument import BackgroundChebyshev, BackgroundPSpline

    bkg = instrument.background
    if isinstance(bkg, BackgroundChebyshev):
        paths = [f"instrument.background.c{k}" for k in range(len(bkg.coefficients))]
        free = any(refined.is_free(p) for p in paths)
        if free and not all(refined.is_free(p) for p in paths):
            notes.append("background: TOPAS's bkg takes one flag for every "
                         "coefficient, and some were held; all are written free")
        return [f"  bkg {'@ ' if free else '! '}"
                + " ".join(number(c.value) for c in bkg.coefficients) + "\n"]
    if not isinstance(bkg, BackgroundPSpline):
        raise ValueError(
            f"a {type(bkg).__name__} background has no TOPAS statement here; "
            f"write the structure alone (no instrument=)")
    items: list = []
    for k, c in enumerate(bkg.coefficients):
        path = f"instrument.background.c{k}"
        pieces = _bspline_pieces(bkg.breakpoints, k)
        last = float(bkg.breakpoints[-1])
        body = "0"
        for lo, hi, a in reversed(pieces):
            u = f"(X - {number(lo)})"
            poly = " + ".join(f"({number(an)})*{u}^{n}" if n else f"({number(an)})"
                              for n, an in enumerate(a) if an != 0.0) or "0"
            # the last breakpoint belongs to the last piece (rietx clamps a
            # point there into the span), every other one to the piece above it
            below = "<=" if hi >= last else "<"
            body = f"If(X < {number(lo)}, 0, If(X {below} {number(hi)}, {poly}, {body}))"
        items += ["  fit_obj = ", Expr(f"{{0}}*{body}",
                                       [refined.affine(path, c.value)]), ";\n"]
    if bkg.air_scatter is not None:
        items += ["  fit_obj = ", Expr("{0}/Max(X, 0.001)",
                                       [refined.affine("instrument.background.air",
                                                       bkg.air_scatter.value)]), ";\n"]
    n = len(bkg.coefficients)
    if bkg.lambda_smooth > 0.0 and n > 2:
        weight = math.sqrt(bkg.lambda_smooth)
        if bkg.lambda_units == "dimensionless":
            weight *= pspline_penalty_scale(sigma[mask], n)
        d2 = second_difference_matrix(n)
        for row in d2:
            parts = [refined.affine(f"instrument.background.c{k}", bkg.coefficients[k].value)
                     * float(v) for k, v in enumerate(row) if v != 0.0]
            total = parts[0]
            for p_ in parts[1:]:
                total = total + p_
            items += ["  penalty = ", Expr(f"({number(weight)}*{{0}})^2", [total]), ";\n"]
        # TOPAS weighs a penalty by an adaptive K_P unless told otherwise
        # (Technical Reference eq. 4-7), and with it a refinement settles where
        # the penalty counts for less than in rietx's objective; pen_weight = 1
        # is rietx's fixed weight, and TOPAS's zero-cycle penalty sum is then
        # rietx's Σr² (test_topas_whole_input.py)
        items.append("  pen_weight = 1;\n")
        notes.append(f"background: rietx's P-spline ({n} cubic B-spline coefficients, "
                     f"smoothing lambda {number(bkg.lambda_smooth)} {bkg.lambda_units}) "
                     f"written as fit_obj pieces and TOPAS penalty terms, the same "
                     f"function and the same objective")
    return items


#: Calculation points per narrowest FWHM asked of TOPAS (``convolution_step``).
CALC_POINTS_PER_FWHM = 16


def _convolution_step(instrument, tt) -> int:
    """TOPAS computes a peak on a grid of the data step / ``convolution_step``
    (Technical Reference § 10.3.2) and convolves numerically there, where rietx
    samples each point. On a 0.1° neutron grid with FCJ asymmetry (the
    committed ``nacl_pspline`` case, TOPAS 6 at zero cycles) a step of 1 left
    TOPAS 6.3e-2 of the peak from rietx; 16 points per narrowest instrumental
    FWHM (a step of 6 there) brought it to 2.6e-3."""
    from ...model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm

    prof = instrument.profile
    theta = np.linspace(float(tt[0]), float(tt[-1]), 256) / 2.0
    g = gaussian_fwhm(theta, prof.u.value, prof.v.value, prof.w.value)
    lo = lorentzian_fwhm(theta, prof.x.value, prof.y.value)
    fwhm = float(np.min(0.5346 * lo + np.sqrt(0.2166 * lo ** 2 + g ** 2)))
    step = float(np.median(np.diff(tt)))
    return max(1, int(math.ceil(CALC_POINTS_PER_FWHM * step / fwhm)))


def _lp_factor(instrument) -> str:
    """``LP_Factor(c)``: neutron 90° (Lp = 1/(sin²θ cosθ)); X-ray
    cos² c = (1 − K)/K (measured against TOPAS 6 to 5e-8, K = 0.5, 0.5556,
    0.99). A K below ½ has no ``LP_Factor`` and is refused.

    rietx's own factor is ``model.corrections.lorentz_polarization``,
    Lp = [K + (1 − K)cos²2θ]/(sin²θ cosθ) (International Tables for
    Crystallography vol. C, § 6.2; Klug & Alexander 1974, ch. 5); the TOPAS
    statement above is matched to it by the measurement, not derived from
    TOPAS's definition."""
    if instrument.source.kind == "neutron_cw":
        return "LP_Factor(90)"
    k = float(instrument.source.polarization.value)
    if not 0.5 <= k <= 1.0:
        raise ValueError(
            f"a polarisation K = {k!r} has no TOPAS LP_Factor (cos² c = (1-K)/K "
            f"needs 1/2 <= K <= 1)")
    c = math.degrees(math.acos(math.sqrt((1.0 - k) / k)))
    return f"LP_Factor({number(c)})"


def instrument_items(instrument, pattern, refined: RefinedSet, data_name: str,
                     notes: list[str]) -> tuple[list, dict]:
    """The ``xdd`` block up to its first ``str``, and the data file's columns."""
    from ...schemas.instrument import NeutronSource

    source = instrument.source
    if source.kind not in ("neutron_cw", "xray_cw"):
        raise ValueError(f"a {source.kind!r} source has no TOPAS statement here")
    geom = instrument.geometry
    for name in ("sample_transparency", "capillary_offset_along_beam",
                 "capillary_offset_across_beam"):
        p = getattr(geom, name, None)
        if p is not None and (p.value != 0.0 or refined.is_free(f"instrument.geometry.{name}")):
            raise ValueError(
                f"instrument.geometry.{name} = {p.value!r} has no measured TOPAS "
                f"mapping in this writer; refused rather than dropped")
    for name in ("mu_r", "mu_t", "surface_roughness"):
        if getattr(geom, name, None) is not None:
            raise ValueError(
                f"instrument.geometry.{name} is set; the absorption corrections "
                f"have no measured TOPAS mapping in this writer, refused rather "
                f"than dropped")
    if getattr(source, "harmonics", None):
        raise ValueError("a λ/n harmonic has no TOPAS statement in this writer")
    if instrument.extra_components:
        raise ValueError("Instrument.extra_components have no TOPAS statement here")
    if any(ch in data_name for ch in '"\r\n'):
        raise ValueError(
            f"data file name {data_name!r} cannot be written to a TOPAS `.inp`: "
            f"the `xdd` line holds it in double quotes, so a quote or a line "
            f"break splits the card. Rename the output file")
    tt, y, s, mask = _fit_points(pattern)
    radius = float(geom.goniometer_radius_mm or DEFAULT_RADIUS_MM)
    items: list = [f"xdd \"{data_name}\" xye_format\n",
                   "  weighting = 1 / SigmaYobs^2;\n",
                   f"  Rp {number(radius)} Rs {number(radius)}\n",
                   f"  convolution_step {_convolution_step(instrument, tt)}\n"]
    # interior excluded regions (the file starts and ends at fitted points)
    edges = np.flatnonzero(np.diff(mask.astype(int)))
    for lo_i, hi_i in zip(edges[::2], edges[1::2]):
        items.append(f"  exclude {number(float(tt[lo_i]))} {number(float(tt[hi_i + 1]))}\n")
    items += background_items(instrument, tt, mask, s, refined, notes)
    lines = list(source.lines)
    lam_items: list = ["  lam ymin_on_ymax 1e-06\n"]
    for k, line in enumerate(lines):
        w = line.weight.value
        lam_items.append(f"    la {number(w)} lo {number(line.wavelength.value)} lh 1e-06\n")
    items += lam_items
    if isinstance(source, NeutronSource) or source.kind == "neutron_cw":
        items.append("  neutron_data\n")
    items.append(f"  {_lp_factor(instrument)}\n")
    items += ["  th2_offset ", Slot(refined.affine("instrument.zero_shift",
                                                   instrument.zero_shift.value),
                                    1.0, instrument.zero_shift.value), "\n"]
    sd = geom.sample_displacement
    sd_aff = refined.affine("instrument.geometry.sample_displacement", sd.value)
    if sd_aff.terms or sd_aff.const != 0.0:
        # rietx's own displacement law, Δ2θ = -(2·s/R)·cosθ rad (Wilson 1963,
        # Mathematical Theory of X-ray Powder Diffractometry, ch. 4; Klug &
        # Alexander 1974, ch. 5; model.corrections.displacement_shift_deg),
        # as a th2_offset equation in degrees (Rad = 180/π); the sign and the
        # unit measured against TOPAS 6 on the X-ray case
        items += ["  th2_offset = ", Expr(f"-2*Rad*{{0}}*Cos(Th)/{number(radius)}",
                                          [sd_aff]), ";\n"]
    sl = refined.affine("instrument.geometry.axial_sl", geom.axial_sl.value) \
        if getattr(geom, "axial_sl", None) is not None else Affine({}, 0.0)
    hl = refined.affine("instrument.geometry.axial_hl", geom.axial_hl.value) \
        if getattr(geom, "axial_hl", None) is not None else Affine({}, 0.0)
    if sl.terms or hl.terms or sl.const or hl.const:
        # Finger, Cox & Jephcoat (1994), J. Appl. Cryst. 27, 892: S/L and H/L
        # as TOPAS's Finger_et_al(s2, h2), whose
        # arguments are the full sample and receiving-slit lengths (Technical
        # Reference § 12.2.4): s2 = 2·(S/L)·Rs. Measured against TOPAS 6
        # (S/L = H/L = 0.01, Rs 217.5): largest residual 2.2e-3 of the peak on
        # a 0.001° grid, the grid's own floor being 2.07e-3.
        items += finger_items(sl, hl, radius)
    columns = {"x": tt, "y": y, "sigma": s}
    return items, columns


def finger_items(sl: Affine, hl: Affine, radius: float) -> list:
    """FCJ S/L and H/L as TOPAS's ``Finger_et_al(s2, h2)``.

    Finger, Cox & Jephcoat (1994), *J. Appl. Cryst.* 27, 892.

    Its arguments are the full sample and receiving-slit lengths in mm
    (Technical Reference § 12.2.4), so s2 = 2·(S/L)·Rs and h2 = 2·(H/L)·Rs:
    measured against TOPAS 6 with S/L = H/L = 0.01 and Rs 217.5, the largest
    residual is 2.2e-3 of the peak on a 0.001° grid, the grid's own floor
    being 2.07e-3. The two lengths are passed as dependent parameters of the
    two rietx ratios, so a free ratio refines through them; a macro argument
    takes a value or an equation, and a bare name stops TOPAS 6 ("Error at:
    sample_length"), so each is spelt ``=name;``.
    """
    two_r = number(2 * radius)
    return ["  prm rx_fcj_s2 = ", Expr(f"{two_r}*{{0}}", [sl]), ";\n",
            "  prm rx_fcj_h2 = ", Expr(f"{two_r}*{{0}}", [hl]), ";\n",
            "  Finger_et_al(=rx_fcj_s2;, =rx_fcj_h2;)\n"]


# ----------------------------------------------------------------- the file

def whole_input(structure, *, refined: RefinedSet, scale: str, instrument=None,
                pattern=None, data_name: str | None = None, p1: dict[int, bool],
                species_of, magnetic_numbers: dict[int, str | None],
                provenance: str) -> tuple[str, dict | None, list[str]]:
    """The ``.inp`` text, the data columns (or None) and the notes for its header."""
    from .topas import _topas_space_group

    notes: list[str] = []
    factor = 1.0
    if scale == "topas":
        if instrument is None:
            raise ValueError("scale='topas' needs instrument= (the constant depends "
                             "on the radiation)")
        factor = topas_scale_factor(instrument)
        xray = instrument.source.kind != "neutron_cw"
        notes.append(
            f"scale: TOPAS convention (LP_Factor, |F|^2 in "
            f"{'electrons^2' if xray else 'barn'}) = rietx Phase.scale x "
            f"{number(factor)}"
            + (" (x K, measured against TOPAS 6 at K = 0.5)" if xray else ""))
    else:
        notes.append("scale: rietx's own Phase.scale, NOT TOPAS's convention "
                     "(TOPAS's is x100 for neutrons, xK for X-rays)")
    if refined.from_stored_flags:
        notes.append("free set: each Parameter.vary as stored (no free= given)")
    elif refined.rows is None and refined.free_paths is not None:
        notes.append("free set given without ties: a tied copy refines as its own "
                     "parameter (pass the Refinement to free= for the ties)")
    elif refined.from_result:
        notes.append("free set from a result: symmetry ties are written as "
                     "equations over their sources; a user tie's copy refines "
                     "as its own parameter (a result does not keep the tie)")
    body: list = []
    columns = None
    if instrument is not None and pattern is not None:
        inst_items, columns = instrument_items(instrument, pattern, refined,
                                               data_name or "data.xye", notes)
        body += inst_items
    elif pattern is not None:
        raise ValueError("pattern= needs instrument=: the data file is written with "
                         "the wavelength, background and zero that describe it")
    for ip, phase in enumerate(structure.phases):
        mag_number = magnetic_numbers.get(ip)
        is_p1 = p1.get(ip, False)
        has_moments = any(a.moment is not None for a in phase.atoms)
        # a magnetic-only width is a profile term: without instrument= the file
        # has no profile, and TOPAS_FIELD_NOT_WRITTEN names it instead
        mag_width = instrument is not None and has_moments and any(
            refined.affine(_p(ip, n), getattr(phase, n).value).terms
            or getattr(phase, n).value != 0.0
            for n in ("magnetic_lor_size", "magnetic_lor_strain"))
        if mag_width and (phase.extinction.value != 0.0
                          or refined.is_free(_p(ip, "extinction"))):
            raise ValueError(
                f"phase {phase.name!r} cannot be written to a TOPAS `.inp`: it has a "
                f"magnetic-only width and extinction, and rietx applies one Sabine "
                f"factor, from |F|² of the nuclear and magnetic parts together, to both "
                f"components. TOPAS computes a `scale_pks` from one `str`'s own A01..B11, "
                f"so the split would scale each part by a different factor and the "
                f"magnetic peaks would come out too strong. Hold extinction at zero, or "
                f"drop the magnetic-only width")
        if mag_width:
            refined.named.update({_p(ip, "magnetic_lor_size"), _p(ip, "magnetic_lor_strain")})

        def header(part):
            name = phase.name if part != "magnetic" else f"{phase.name} magnetic part"
            out = [f'phase_name "{name}"']
            if part == "nuclear" or mag_number is None:
                sg = "P 1" if is_p1 else _topas_space_group(phase.space_group)
                out.append(f'space_group "{sg}"')
            else:
                out.append(f"mag_space_group {mag_number}")
                if part == "magnetic":
                    out.append("' the magnetic scattering of this phase only (mag_only):"
                               " its Lorentzian widths carry the magnetic-only terms")
            return out

        parts = ["nuclear", "magnetic"] if mag_width else ["all"]
        for part in parts:
            prof = (_profile_items(instrument, ip, phase, refined,
                                   magnetic=part == "magnetic")
                    if instrument is not None else None)
            ext = (_extinction_items(instrument, ip, phase, refined)
                   if instrument is not None and part != "magnetic" else None)
            if instrument is None and phase.extinction.value != 0.0:
                notes.append(f"phase {phase.name!r}: extinction "
                             f"{number(phase.extinction.value)} not written "
                             f"(a scale_pks term, written with instrument=)")
            body += phase_items(structure, ip, phase, refined, scale_factor=factor,
                                header=header(part), profile=prof, extinction=ext,
                                p1=is_p1, part=part, species_of=species_of)
        if mag_width:
            notes.append(
                f"phase {phase.name!r}: written as two str, the nuclear part and the "
                f"magnetic part (mag_only), sharing every parameter; the magnetic "
                f"part's Lorentzian widths add magnetic_lor_size/_strain, which is "
                f"rietx's magnetic-only width term for term")
    declarations = render_slots(body, refined)
    text = "".join(str(i) for i in body)
    head = [f"' Written by {provenance}"]
    head += [f"' {n}" for n in notes]
    if instrument is not None and pattern is not None:
        head += ["r_wp 0 r_exp 0 r_p 0 gof 0", "iters 100000",
                 "chi2_convergence_criteria 1e-07", "do_errors"]
    head += declarations
    return "\n".join(head) + "\n" + text, columns, notes


def write_data_file(path: Path, columns: dict) -> None:
    """The data as TOPAS's ``xye_format``: 2θ, intensity, σ (the σ rietx fits with)."""
    rows = np.column_stack([columns["x"], columns["y"], columns["sigma"]])
    path.write_text("".join(f"{repr(float(a))} {repr(float(b))} {repr(float(c))}\n"
                            for a, b, c in rows), encoding="utf-8")


def check_p1_expand(p1_expand) -> None:
    """``p1_expand`` is ``False``, ``True`` or ``"auto"`` and nothing else: the
    callers dispatch on identity, so a truthy ``1`` or ``np.True_`` would take
    the refined route with no P 1 and no error."""
    if not (p1_expand is True or p1_expand is False
            or (isinstance(p1_expand, str) and p1_expand == "auto")):
        raise ValueError(f"p1_expand must be False, True or 'auto', not {p1_expand!r}")


def any_phase_needs_p1(structure) -> bool:
    """Whether ``p1_expand="auto"`` would restate any phase: a magnetic group
    TOPAS cannot name (the group-identity refusals of ``_magnetic_group_line``)."""
    from .topas import _GroupIdentityRefusal, _magnetic_group_line

    for phase in structure.phases:
        try:
            _magnetic_group_line(phase, ion_species_ok=True)
        except _GroupIdentityRefusal:
            if phase.magnetic_symmetry is not None:
                return True
        except ValueError:
            pass     # not a restatement's to fix; the writer raises it
    return False


def from_structure_refined(structure, *, free: Any = None, scale: str | None = None,
                           instrument=None, pattern=None, data_name: str | None = None,
                           p1_expand: bool | Literal["auto"] = False, diagnostics=None,
                           names: dict | None = None) -> tuple[str, dict | None]:
    """The new path of :func:`~rietx.io.projects.topas.from_structure`."""
    check_p1_expand(p1_expand)
    from ..._about import DIST_NAME
    from .topas import (
        _GroupIdentityRefusal,
        _magnetic_group_line,
        _sign_first,
        refuse_distortion_modes,
        refuse_operation_list,
        topas_species,
    )

    if scale is None:
        scale = "topas" if instrument is not None else "rietx"
    if scale not in ("rietx", "topas"):
        raise ValueError(f"scale must be 'rietx' or 'topas', not {scale!r}")
    neutron = instrument is not None and instrument.source.kind == "neutron_cw"
    p1: dict[int, bool] = {}
    magnetic_numbers: dict[int, str | None] = {}
    for ip, phase in enumerate(structure.phases):
        if '"' in phase.name or "\n" in phase.name or "\r" in phase.name:
            raise ValueError(f"phase name {phase.name!r} cannot be written to a TOPAS "
                             f"`.inp`: it carries a double quote or a line break")
        refuse_operation_list(phase, "a TOPAS `.inp`")
        refuse_distortion_modes(phase, "a TOPAS `.inp`")
        for atom in phase.atoms:
            if any(ch.isspace() or ch == "'" for ch in atom.label + atom.species):
                raise ValueError(
                    f"phase {phase.name!r}: atom label {atom.label!r} / species "
                    f"{atom.species!r} carries whitespace or a single quote, which a "
                    f"`site` line cannot carry")
        want_p1 = p1_expand is True
        number_ = None
        if not want_p1:
            try:
                # the group's verdict alone; the species is species_of's below
                number_ = _magnetic_group_line(phase, ion_species_ok=True)
            except _GroupIdentityRefusal:
                if p1_expand != "auto" or phase.magnetic_symmetry is None:
                    raise
                want_p1 = True
                if diagnostics is not None:
                    from ...schemas.common import Diagnostic
                    diagnostics.append(Diagnostic(
                        level="info", code="TOPAS_PHASE_RESTATED_IN_P1",
                        where=[f"phases.{ip}"],
                        message=(f"Phase {phase.name!r} has no mag_space_group "
                                 f"in TOPAS as it stands, so it was written "
                                 f"in P1 with every copy tied to the "
                                 f"parameter it copies.")))
        if not want_p1 and not neutron:
            _magnetic_group_line(phase)    # main's refusal of a species ≠ ion
        if want_p1:
            p1[ip] = True
            magnetic_numbers[ip] = "1.1" if phase.magnetic_symmetry is not None else None
        else:
            magnetic_numbers[ip] = number_
    stored = free is None
    refined = RefinedSet(stored_free_paths(structure) if stored else free, structure)
    refined.from_stored_flags = stored

    def species_of(atom, with_moment):
        # TOPAS reads a moment's form factor from the `occ` species, so a
        # moment-bearing site states its ion; a neutron's nuclear length is the
        # element's, so that changes nothing else (showcase row M3)
        if atom.moment is not None and (neutron or instrument is None
                                        or atom.moment.ion == atom.species):
            # with no instrument the radiation is unknown: the ion, as a P1
            # restatement states it (a non-P1 phase was refused above)
            return _sign_first(atom.moment.ion)
        if atom.moment is not None and with_moment:
            raise ValueError(
                f"site {atom.label!r} has species {atom.species!r} and magnetic "
                f"ion {atom.moment.ion!r}; TOPAS takes the magnetic form factor "
                f"from the `occ` species, which on an X-ray pattern is also the "
                f"charge density. Set the species to the ion first")
        return topas_species(atom.species)

    text, columns, _ = whole_input(
        structure, refined=refined, scale=scale, instrument=instrument, pattern=pattern,
        data_name=data_name, p1=p1, species_of=species_of,
        magnetic_numbers=magnetic_numbers,
        provenance=f"{DIST_NAME}.io.projects.topas.write_topas_inp")
    if names is not None:
        names.update(refined.carriers)
    return text, columns
