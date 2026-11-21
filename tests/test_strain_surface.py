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
    S_NAMES,
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
    # a block near the cone has directions where the sum cancels toward zero,
    # so the bar is relative to the largest value, not to each one (measured:
    # Linux x86-64 libm missed a per-value 1e-12 on P-3m1, darwin/arm64 did not)
    assert np.allclose(got, expected, rtol=1e-12, atol=1e-12 * np.abs(expected).max())


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
    c_star = reciprocal_frame(cell)[:, 2]
    c_star = c_star / np.linalg.norm(c_star)
    sigma2_c = directional_sigma2(s, cell, c_star[None, :])[0]
    assert sigma2_c < 0.0
    tops = surface["verts"].reshape(-1, 3)
    unit = tops / np.linalg.norm(tops, axis=1)[:, None]
    top = tops[np.argmax(unit @ c_star)]
    assert np.linalg.norm(top) == pytest.approx(np.sqrt(-sigma2_c), rel=1e-3)


def test_a_silent_guard_is_said_to_be_silent(outside_the_cone):
    """Passed diagnostics with no finding for this block: the note says the
    guard reported nothing, and claims nothing about where the region lies."""
    import matplotlib.pyplot as plt

    from rietx.viz import plot_strain_surface

    phase, _ = outside_the_cone
    fig = plot_strain_surface(phase, [])
    assert "reported nothing for phases.0.microstrain" in _text(fig)
    assert "between" not in _text(fig)
    plt.close(fig)
    # no diagnostics at all: the figure claims nothing about the guard
    fig = plot_strain_surface(phase)
    assert "reported nothing" not in _text(fig)
    plt.close(fig)


def test_another_phases_finding_is_not_quoted(outside_the_cone):
    import matplotlib.pyplot as plt

    from rietx.viz import plot_strain_surface

    phase, diags = outside_the_cone
    fig = plot_strain_surface(Structure(phases=[phase, phase]), diags, phase=1)
    # the finding names phases.0; phase 1 is the same block, still drawn red,
    # and the guard is then said to be silent about it
    assert "STEPHENS_STRAIN_NOT_POSITIVE:" not in _text(fig)
    assert "reported nothing for phases.1.microstrain" in _text(fig)
    plt.close(fig)


def test_a_phase_without_a_drawable_block_is_refused():
    from rietx.viz import plot_strain_surface

    with pytest.raises(ValueError, match="no Stephens microstrain block"):
        plot_strain_surface(brucite())
    with pytest.raises(ValueError, match="all-zero"):
        plot_strain_surface(brucite(StephensStrain.from_values([0.0] * 15)))


def _l4_block(scale: float) -> np.ndarray:
    """The P-3m1 pure l⁴ pattern at ``scale``, every other pattern zero."""
    coef = np.zeros(stephens_basis("P -3 m 1").shape[0])
    coef[_L4_ROW] = scale
    return coef


def test_the_colourbar_follows_the_drawn_facets():
    """The bar is drawn when some facet is in its scale, and only then.  The
    l⁴ block driven negative is below zero everywhere but the basal plane: a
    band of vertices there is inside the tolerance, yet every facet touches a
    vertex outside it, so the whole surface is red and a bar would be a legend
    for nothing (review of PR #1620: 22 such vertices, 0 such facets)."""
    import matplotlib.pyplot as plt

    from rietx.viz import plot_strain_surface
    from rietx.viz.strain import _surface

    phase = brucite(_strain_from_coef(_l4_block(-1e6), vary=False))
    surface = _surface(np.array(phase.microstrain.values()),
                       phase.cell.lengths_angles(), 4000)
    # the case the check must tell apart: good vertices, no good facet
    assert (~surface["bad"]).any() and surface["face_bad"].all()
    fig = plot_strain_surface(phase)
    assert len(fig.axes) == 1
    plt.close(fig)

    # the positive arm: a block with facets on the scale gets its bar
    fig = plot_strain_surface(brucite(_strain_from_coef(_brucite_coef(600.0),
                                                        vary=False)))
    assert len(fig.axes) == 2
    plt.close(fig)


def test_rounding_at_the_cone_face_is_not_drawn_as_a_region(monkeypatch):
    """A block on the cone's face, below zero by a round-off-sized amount: the
    positive l⁴ pattern, zero on the basal plane, less an in-plane quartic at
    1e-10 of the largest value, under the guard's 1e-9.  The tolerance keeps it
    off the red; without it the basal band turns red."""
    import matplotlib.pyplot as plt

    from rietx.viz import plot_strain_surface
    from rietx.viz.strain import _surface

    cell = CELLS[1]
    u = sphere_points(4000)
    basis = stephens_basis("P -3 m 1").astype(np.float64)
    in_plane = next(k for k, row in enumerate(basis) if row[S_NAMES.index("s400")])
    coef = _l4_block(1e6)
    top = directional_sigma2(basis.T @ coef, cell, u).max()
    unit = np.zeros_like(coef)
    unit[in_plane] = 1.0
    coef[in_plane] = -1e-10 * top / directional_sigma2(basis.T @ unit, cell, u).max()
    s = basis.T @ coef
    sigma2 = directional_sigma2(s, cell, u)
    # the block does dip below zero on the sampled sphere, inside the tolerance
    assert (sigma2 < 0.0).any()
    assert sigma2.min() > -1e-9 * np.abs(sigma2).max()

    phase = brucite(_strain_from_coef(coef, vary=False))
    assert not _surface(s, cell, 4000)["face_bad"].any()
    fig = plot_strain_surface(phase)
    assert _bad_faces(fig, "light") == 0
    assert "σ²(M) < 0" not in _text(fig)
    plt.close(fig)

    # the positive arm: with no tolerance the same block draws a red band
    monkeypatch.setattr("rietx.strategy.staged.STEPHENS_CONE_TOL", 0.0)
    assert _surface(s, cell, 4000)["face_bad"].any()
