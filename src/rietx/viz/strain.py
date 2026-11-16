"""The Stephens strain surface: a refined block drawn over every direction (WP-1318).

A Stephens block (:mod:`rietx.crystallography.stephens`, Stephens 1999,
J. Appl. Cryst. 32, 281) is fifteen numbers that nobody reads as numbers.  What
they say is a shape: how broad the ΔM/M distribution is along each direction of
reciprocal space.  This module draws that shape and computes none of it.  The
values are :func:`~rietx.crystallography.stephens.directional_sigma2`, the
module's own sum read at unit-M hkl along directions from
:func:`~rietx.crystallography.spherical_harmonics.sphere_points`, the sampler
the texture surface uses.

Three rules decide what is drawn.

* **The radius is the FWHM of ΔM/M in ppm**, √(σ²(M))/M, the module's
  convention and not a standard deviation (no √(8 ln 2) anywhere).  An
  isotropic block is therefore a sphere whose radius is its microstrain.
* **A direction below zero is drawn, not clipped.**  σ²(M) < 0 is outside the
  physical cone.  Such a facet is drawn at √|σ²| in the ``--bad`` colour, so the
  region keeps its true extent; flooring it to zero would draw a dimple, which
  reads as a narrow direction rather than an impossible one.  "Below zero" is the
  guard's own test, ``-STEPHENS_CONE_TOL`` times the largest magnitude, so the
  figure and ``STEPHENS_STRAIN_NOT_POSITIVE`` agree about what negative means.
* **The guard's finding goes beside the picture.**  The guard tests the fitted
  reflections and this tests the sphere, so the two can differ: a fit the
  default LM driver held on the cone can still dip between measured directions.
  The text under the figure says which case it is.

No confidence band is drawn.  The coefficients' esds exist, but a band needs
the S_HKL block of the covariance propagated direction by direction, which a
result does not carry, and a diagonal shortcut is wrong in both directions
(root CLAUDE.md, WP-1072).
"""

from __future__ import annotations

import textwrap

import numpy as np

from .plots import BASE, _figure_class, _handed_back, _palette, _pyplot, _style_context

#: The code whose findings the figure quotes.
_GUARD_CODE = "STEPHENS_STRAIN_NOT_POSITIVE"


def _phase_of(structure, phase: int):
    """The phase to draw: ``structure`` itself when it is a ``Phase``."""
    from ..schemas.structure import Phase

    if isinstance(structure, Phase):
        return structure
    return structure.phases[phase]


def _findings(diagnostics, phase: int) -> list[str]:
    """The guard's messages about this phase's block among ``diagnostics``."""
    where = f"phases.{phase}.microstrain"
    return [d.message for d in diagnostics or []
            if d.code == _GUARD_CODE and where in (d.where or [])]


def _surface(s: np.ndarray, cell, n_directions: int) -> dict[str, np.ndarray]:
    """The drawn geometry: triangles at radius √|σ²(M)|/M over the sphere.

    ``radius`` and ``bad`` are per direction, ``verts`` (faces, 3, 3),
    ``face_bad`` and ``face_r`` per triangle.  A triangle touching a direction
    below zero is unphysical, so the region is never drawn smaller than it is.
    "Below zero" is the guard's own test, ``-STEPHENS_CONE_TOL`` times the
    largest magnitude.
    """
    from scipy.spatial import ConvexHull

    from ..crystallography.spherical_harmonics import sphere_points
    from ..crystallography.stephens import directional_sigma2
    from ..strategy.staged import STEPHENS_CONE_TOL

    u = sphere_points(int(n_directions))
    sigma2 = directional_sigma2(s, cell, u)
    bad = sigma2 < -STEPHENS_CONE_TOL * float(np.max(np.abs(sigma2)))
    radius = np.sqrt(np.abs(sigma2))
    faces = ConvexHull(u).simplices
    # the hull's simplices come in either winding; shading reads the normal,
    # so each is turned to face outward or the surface draws as a checkerboard
    p0, p1, p2 = u[faces[:, 0]], u[faces[:, 1]], u[faces[:, 2]]
    inward = np.einsum("ij,ij->i", np.cross(p1 - p0, p2 - p0), p0 + p1 + p2) < 0.0
    faces[inward] = faces[inward][:, ::-1]
    return {"radius": radius, "bad": bad,
            "verts": (u * radius[:, None])[faces],
            "face_bad": bad[faces].any(axis=1),
            "face_r": radius[faces].mean(axis=1)}


def plot_strain_surface(structure, diagnostics=None, *, phase: int = 0,
                        path: str | None = None, style: str = "light",
                        n_directions: int = 4000, elev: float = 22.0,
                        azim: float = -58.0, font_size: float = BASE,
                        dpi: int = 150, title: str | None = None):
    """Draw a phase's Stephens block as a surface over reciprocal-space directions.

    ``structure`` is a ``Structure`` (``phase`` picks the phase) or a single
    ``Phase``; after a fit pass ``Refinement.fitted_structure``.
    ``diagnostics``, that fit's ``RefinementResult.diagnostics``, puts the
    guard's ``STEPHENS_STRAIN_NOT_POSITIVE`` finding for
    ``phases.<phase>.microstrain`` under the figure, or says the guard stayed
    silent; with a bare ``Phase``, ``phase`` is its index in that fit.

    The distance from the origin along a direction is the FWHM of the ΔM/M
    distribution there, in ppm, and the colour repeats it.  Facets where σ²(M)
    is below zero are drawn at √|σ²| in the ``--bad`` colour, never clipped.
    The reciprocal axes a*, b*, c* are drawn from the origin.

    ``n_directions`` points of a Fibonacci lattice sample the sphere; ``elev``
    and ``azim`` are the view, in degrees.  Returns the matplotlib figure and
    writes it to ``path`` when one is given.
    """
    from ..crystallography.stephens import reciprocal_frame

    hue = _palette(style)
    ph = _phase_of(structure, phase)
    if ph.microstrain is None:
        raise ValueError(f"phase {ph.name!r} has no Stephens microstrain block to draw")
    s = np.array(ph.microstrain.values(), dtype=np.float64)
    if not np.any(s):
        raise ValueError(f"phase {ph.name!r} has an all-zero Stephens block: "
                         "it is the no-broadening identity and has no surface")
    cell = ph.cell.lengths_angles()
    surface = _surface(s, cell, n_directions)
    verts, face_bad, face_r, bad = (surface["verts"], surface["face_bad"],
                                    surface["face_r"], surface["bad"])
    radius = surface["radius"]
    top = float(radius.max())
    good_top = float(radius[~bad].max()) if (~bad).any() else top

    plt = _pyplot()
    from matplotlib import colormaps
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import LightSource, Normalize
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    # the --bad role, the colour the GUI and the trajectory give a verdict
    # that is not a measurement
    bad_colour = hue["reseeded"]
    cmap = colormaps["viridis"]
    norm = Normalize(vmin=0.0, vmax=good_top)
    colours = np.array([cmap(norm(r)) for r in face_r])
    if face_bad.any():
        from matplotlib.colors import to_rgba
        colours[face_bad] = to_rgba(bad_colour)

    with _style_context(plt, style, font_size):
        fig = plt.figure(figsize=(6.4, 6.2), dpi=dpi, FigureClass=_figure_class())
        ax = fig.add_axes((0.0, 0.12, 0.84, 0.86), projection="3d")
        ax.add_collection3d(Poly3DCollection(
            verts, facecolors=colours, edgecolors=colours, linewidths=0.0, shade=True,
            lightsource=LightSource(azdeg=225, altdeg=35)))

        frame = reciprocal_frame(cell)
        reach = 1.2 * top
        for k, name in enumerate(("a", "b", "c")):
            axis = frame[:, k] / np.linalg.norm(frame[:, k])
            end = reach * axis
            ax.plot([0.0, end[0]], [0.0, end[1]], [0.0, end[2]],
                    color=hue["obs"], lw=1.0)
            ax.text(*(1.08 * end), f"${name}^*$", color=hue["obs"],
                    ha="center", va="center")

        ax.set_xlim(-reach, reach)
        ax.set_ylim(-reach, reach)
        ax.set_zlim(-reach, reach)
        ax.set_box_aspect((1, 1, 1), zoom=1.35)
        ax.set_axis_off()
        ax.view_init(elev=elev, azim=azim)

        cax = fig.add_axes((0.86, 0.30, 0.03, 0.52))
        bar = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax)
        bar.set_label("FWHM of ΔM/M (ppm)")

        lines = []
        if bad.any():
            share = float(bad.mean())
            lines.append(f"σ²(M) < 0 over {100.0 * share:.3g} % of directions "
                         "(red): outside the physical cone, drawn at √|σ²(M)|.")
        findings = _findings(diagnostics, phase)
        lines += [f"{_GUARD_CODE}: {m}" for m in findings]
        if diagnostics is not None and bad.any() and not findings:
            lines.append(f"{_GUARD_CODE} did not fire: the guard tests the fitted "
                         "reflections, and the negative region lies between them.")
        if lines:
            text = "\n".join(textwrap.fill(line, width=74) for line in lines)
            fig.text(0.02, 0.13, text, ha="left", va="top",
                     fontsize=font_size, color=hue.get("fg", hue["obs"]))
        if title is not None:
            fig.suptitle(title, fontsize=font_size)

        if path is not None:
            fig.savefig(path)
    return _handed_back(fig, style)

