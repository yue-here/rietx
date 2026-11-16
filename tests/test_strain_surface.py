"""WP-1318: the Stephens strain surface, drawn from the coefficients.

The surface is :func:`rietx.crystallography.stephens.directional_sigma2`, which
reads the module's one sum (:func:`~rietx.crystallography.stephens.sigma2_m`)
at the hkl along a unit direction with M = 1 Å⁻².  So the bar is identity, not
tolerance-shopping: along any reflection h the surface equals
``sigma2_m(h)·d⁴``, an isotropic block is a sphere of radius ε, and a block
outside the physical cone draws its region and the guard's own finding.  The
refined-block half of the bar runs on the brucite acceptance fit, in
``tests/test_acceptance_stephens.py``, where that fit already lives.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rietx.crystallography.lattice import d_spacings, reciprocal_metric_tensor
from rietx.crystallography.spherical_harmonics import sphere_points
from rietx.crystallography.stephens import (
    directional_sigma2,
    isotropic_coefficients,
    monomial_matrix,
    reciprocal_frame,
    sigma2_m,
    stephens_basis,
)
from rietx.schemas.structure import StephensStrain, Structure
from rietx.viz.plots import PALETTES
from tests.test_stephens import (
    _L4_ROW,
    CELLS,
    _brucite_coef,
    _compiled,
    _strain_from_coef,
    brucite,
)

OUT = Path(__file__).parent / "output"

#: (space group, cell): the hexagonal acceptance material, corundum's
#: rhombohedral class on hexagonal axes, and the two low-symmetry cells, whose
#: oblique reciprocal frames are where a wrong B⁻¹ would show
GROUPS = [
    ("P -3 m 1", CELLS[1]),
    ("R -3 c", (4.759, 4.759, 12.992, 90.0, 90.0, 120.0)),
    ("P 1 21/c 1", CELLS[3]),
    ("P -1", CELLS[4]),
]

HKL = np.array([(h, k, ll) for h in range(-3, 4) for k in range(-3, 4)
                for ll in range(-4, 5) if (h, k, ll) != (0, 0, 0)], dtype=float)


def _unit(cell, hkl):
    q = (reciprocal_frame(cell) @ hkl.T).T
    return q / np.linalg.norm(q, axis=1)[:, None]


def _random_block(symbol, cell, seed=7):
    """An in-subspace block near the isotropic ray, anisotropic in every pattern."""
    basis = stephens_basis(symbol).astype(np.float64)
    iso = isotropic_coefficients(cell, 800.0)
    rng = np.random.default_rng(seed)
    return iso + 0.3 * np.abs(iso).max() * (rng.normal(size=basis.shape[0]) @ basis)


def test_the_frame_is_the_reciprocal_metric():
    for cell in CELLS:
        b = reciprocal_frame(cell)
        assert np.allclose(b.T @ b, reciprocal_metric_tensor(*cell), rtol=0, atol=1e-15)
        assert b[1, 0] == 0.0 and b[2, 0] == 0.0 and b[2, 1] == 0.0


@pytest.mark.parametrize("symbol,cell", GROUPS)
def test_the_surface_is_the_module_sum_along_every_reflection(symbol, cell):
    s = _random_block(symbol, cell)
    d = d_spacings(HKL, *cell)
    expected = np.asarray(sigma2_m(monomial_matrix(HKL), s)) * d**4
    got = directional_sigma2(s, cell, _unit(cell, HKL))
    assert np.allclose(got, expected, rtol=1e-12, atol=0.0)


@pytest.mark.parametrize("cell", CELLS)
def test_an_isotropic_block_is_a_sphere_of_its_microstrain(cell):
    s = isotropic_coefficients(cell, 1250.0)
    got = directional_sigma2(s, cell, sphere_points(2000))
    assert np.allclose(np.sqrt(got), 1250.0, rtol=1e-12, atol=0.0)


def _bad_faces(fig, style) -> int:
    """How many drawn facets carry the --bad hue.  Shading scales a facet's
    rgb by one factor, so the hue is its rgb normalised; the count is
    independent of the depth order the renderer sorts the facets into."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    (coll,) = [c for c in fig.axes[0].collections if isinstance(c, Poly3DCollection)]
    rgb = np.asarray(coll.get_facecolor())[:, :3]
    hue = rgb / rgb.sum(axis=1, keepdims=True)
    bad = _bad_rgb(style) / _bad_rgb(style).sum()
    return int(np.all(np.abs(hue - bad) < 1e-6, axis=1).sum())


def _text(fig) -> str:
    return "\n".join(t.get_text() for t in fig.texts)


def _bad_rgb(style="light"):
    from matplotlib.colors import to_rgb

    return np.array(to_rgb(PALETTES[style]["reseeded"]))


def test_an_isotropic_figure_has_no_unphysical_region_and_no_note():
    import matplotlib.pyplot as plt

    from rietx.viz import plot_strain_surface

    phase = brucite(_strain_from_coef(_brucite_coef(600.0), vary=False))
    OUT.mkdir(exist_ok=True)
    fig = plot_strain_surface(phase, [], path=str(OUT / "strain_surface_isotropic.png"))
    assert _text(fig) == ""
    assert _bad_faces(fig, "light") == 0
    plt.close(fig)

    from rietx.viz.strain import _surface

    surface = _surface(np.array(phase.microstrain.values()),
                       phase.cell.lengths_angles(), 1000)
    assert not surface["face_bad"].any()
    radii = np.linalg.norm(surface["verts"].reshape(-1, 3), axis=1)
    assert np.allclose(radii, 600.0, rtol=1e-9)


@pytest.fixture(scope="module")
def outside_the_cone():
    """The guard test's block: the l⁴ pattern driven far negative, so 00l is
    outside the cone, with the guard's own diagnostics for it."""
    from rietx.refine import _guard_diagnostics
    from rietx.strategy.staged import GuardReport, check_stephens_positive

    coef = _brucite_coef(600.0)
    coef[_L4_ROW] = -50.0 * abs(coef[_L4_ROW])
    model, table = _compiled(_strain_from_coef(coef, vary=False))
    diags = _guard_diagnostics(GuardReport(
        nonpositive_strain=check_stephens_positive(table, model)))
    assert [d.code for d in diags] == ["STEPHENS_STRAIN_NOT_POSITIVE"]
    return brucite(_strain_from_coef(coef, vary=False)), diags


@pytest.mark.parametrize("style", ["light", "dark"])
def test_a_block_outside_the_cone_draws_its_region_and_the_finding(
        outside_the_cone, style):
    import matplotlib.pyplot as plt

    from rietx.viz import plot_strain_surface

    phase, diags = outside_the_cone
    OUT.mkdir(exist_ok=True)
    fig = plot_strain_surface(phase, diags, style=style,
                              path=str(OUT / f"strain_surface_outside_{style}.png"))
    text = _text(fig)
    assert "σ²(M) < 0 over" in text
    # the finding's own words, not a paraphrase: the diagnostic's message
    # wrapped, so compare with the whitespace folded
    assert " ".join(diags[0].message.split()) in " ".join(text.split())

    # every facet the geometry calls unphysical is drawn in the --bad colour,
    # and no other is
    from rietx.viz.strain import _surface

    s = np.array(phase.microstrain.values())
    cell = phase.cell.lengths_angles()
    surface = _surface(s, cell, 4000)
    assert 0 < _bad_faces(fig, style) == int(surface["face_bad"].sum())
    plt.close(fig)

    # …at its true extent, never clipped to zero: c* lies inside the region,
    # and the vertex nearest it sits at √|σ²| there, not at the origin
    sigma2_c = directional_sigma2(s, cell, np.array([[0.0, 0.0, 1.0]]))[0]
    assert sigma2_c < 0.0
    tops = surface["verts"].reshape(-1, 3)
    top = tops[np.argmax(tops[:, 2])]
    assert np.linalg.norm(top) == pytest.approx(np.sqrt(-sigma2_c), rel=1e-3)


def test_a_silent_guard_is_said_to_be_silent(outside_the_cone):
    """Passed diagnostics with no finding: the guard tests reflections and the
    figure the sphere, so the note says which one spoke."""
    import matplotlib.pyplot as plt

    from rietx.viz import plot_strain_surface

    phase, _ = outside_the_cone
    fig = plot_strain_surface(phase, [])
    assert "did not fire" in _text(fig)
    plt.close(fig)
    # no diagnostics at all: the figure claims nothing about the guard
    fig = plot_strain_surface(phase)
    assert "did not fire" not in _text(fig)
    plt.close(fig)


def test_another_phases_finding_is_not_quoted(outside_the_cone):
    import matplotlib.pyplot as plt

    from rietx.viz import plot_strain_surface

    phase, diags = outside_the_cone
    fig = plot_strain_surface(Structure(phases=[phase, phase]), diags, phase=1)
    # the finding names phases.0; phase 1 is the same block, still drawn red,
    # and the guard is then said to be silent about it
    assert "STEPHENS_STRAIN_NOT_POSITIVE:" not in _text(fig)
    assert "did not fire" in _text(fig)
    plt.close(fig)


def test_a_phase_without_a_drawable_block_is_refused():
    from rietx.viz import plot_strain_surface

    with pytest.raises(ValueError, match="no Stephens microstrain block"):
        plot_strain_surface(brucite())
    with pytest.raises(ValueError, match="all-zero"):
        plot_strain_surface(brucite(StephensStrain.from_values([0.0] * 15)))
