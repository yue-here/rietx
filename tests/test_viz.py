"""WP-1444: the pattern before the model, and a title on the figure.

`plot_pattern` is the result panel with nothing modelled in it, so most of
what is asserted here is *agreement*: the same data drawn by both verbs lands
on the same axis.  The title is opt-in, and the default figure must not move
for it, which is pinned by bytes where bytes can be pinned (see
`test_the_default_result_render_is_the_pre_title_render`).
"""

from __future__ import annotations

import hashlib
import io
import platform
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev, NeutronSource
from rietx.schemas.pattern import PatternData
from rietx.viz.indexing import plot_candidates, plot_peak_list, plot_validation
from rietx.viz.plots import PALETTES, plot_for_vlm, plot_pattern, plot_result
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_BKG,
    WAVELENGTH,
    perturbed_models,
    synthesize,
)

pytestmark = pytest.mark.xdist_group("viz-pattern")

OUT = Path(__file__).parent / "output"

#: The one window the fixture's fit holds back — a stretch of background
#: between the first two LaB6 lines of the synthetic pattern.
EXCLUDED = (6.5, 7.5)


@pytest.fixture(scope="module")
def fitted():
    """One synthetic LaB6 fit with an excluded region, and the pattern it saw."""
    pattern = synthesize()
    pattern.excluded_regions = [EXCLUDED]
    structure, ins = perturbed_models()
    result = rx.Refinement(structure, ins, history=False).fit(pattern)
    return pattern, result


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return buf.getvalue()


def _as_pattern(result) -> PatternData:
    """The result's own channels as a bare pattern: the same data, no model."""
    return PatternData(two_theta=list(result.two_theta),
                       intensity=list(result.y_obs))


def _span(band) -> tuple[float, float]:
    """The x extent of an ``axvspan`` band, in data coordinates."""
    return band.get_x(), band.get_x() + band.get_width()


def _axis(ax) -> dict:
    """What a reader takes off an intensity axis, and nothing drawn on it."""
    return {"xlim": ax.get_xlim(), "xlabel": ax.get_xlabel(),
            "yscale": ax.get_yscale(), "ylabel": ax.get_ylabel(),
            "yticks": list(ax.get_yticks()),
            "spine": tuple(ax.spines["left"].get_bounds()),
            "label_y": ax.yaxis.label.get_position()[1]}


# ----------------------------------------------------------------------
# plot_pattern
# ----------------------------------------------------------------------
def test_a_pattern_and_its_fit_share_one_intensity_axis(fitted):
    """Same data, same axis: ticks, label, scale, spine and x range agree.

    On a nonlinear scale the result's data panel has the pattern figure's
    whole y range too, headroom included, so a before-and-after pair shows a
    peak at one height.  On the linear axis the result's floor is lower — the
    residual and the tick rows sit under the data there — and everything the
    reader reads off the axis still agrees.
    """
    _, result = fitted
    bare = _as_pattern(result)
    OUT.mkdir(exist_ok=True)
    lam = 0.45
    for kw in ({}, {"y_scale": "sqrt"}, {"y_scale": "log"}, {"y_scale": "asinh"},
               {"x_axis": "d", "wavelength": lam}, {"x_axis": "q", "wavelength": lam},
               {"two_theta_range": (8.0, 16.0)}):
        stem = "_".join(["viz_pattern", *(f"{k}-{v}" for k, v in kw.items())])
        mine = plot_pattern(bare, path=str(OUT / f"{stem}.png"), **kw).get_axes()
        panels = plot_result(result, **kw).get_axes()
        theirs = panels[0]
        assert len(mine) == 1, "a pattern has no residual panel"
        a, b = _axis(mine[0]), _axis(theirs)
        # the x label sits under the lowest panel, which is the residual's
        # when the result draws one
        b["xlabel"] = panels[-1].get_xlabel()
        label_a, label_b = a.pop("label_y"), b.pop("label_y")
        assert a.keys() == b.keys()
        for key in a:
            if isinstance(a[key], str):
                assert a[key] == b[key], (kw, key)
            else:
                assert np.allclose(a[key], b[key]), (kw, key, a[key], b[key])
        if kw.get("y_scale", "linear") != "linear":
            assert mine[0].get_ylim() == pytest.approx(theirs.get_ylim()), kw
            assert label_a == pytest.approx(label_b), kw


def test_the_pattern_draws_the_measurement_and_nothing_modelled(fitted):
    """Observed markers in the result's own ink, one gutter name, no σ, no title."""
    pattern, _ = fitted
    ax = plot_pattern(pattern).get_axes()[0]
    (line,) = ax.get_lines()        # σ is not drawn, even where it is known
    assert line.get_linestyle() == "None" and line.get_marker() == "x"
    assert line.get_color() == PALETTES["light"]["obs"]
    assert [t.get_text() for t in ax.texts] == ["observed"]
    lo, hi = ax.get_ylim()
    assert lo <= ax.texts[0].get_position()[1] <= hi
    assert ax.get_title() == "" and ax.get_legend() is None

    dark = plot_pattern(pattern, style="dark")
    assert sum(dark.get_facecolor()[:3]) < 0.3
    assert dark.get_axes()[0].get_lines()[0].get_color() == PALETTES["dark"]["obs"]


def test_an_excluded_region_is_shaded_over_channels_the_fit_left_out(fitted):
    """The shading covers exactly the gap the result's own channels leave.

    A result carries only the fitted channels, so the region is a hole in its
    data; the pattern still holds those counts, so they are drawn and the
    region is shaded over them instead.  The agreement asserted is that the
    band and the hole are the same stretch of 2θ.
    """
    pattern, result = fitted
    OUT.mkdir(exist_ok=True)
    ax = plot_pattern(pattern, path=str(OUT / "viz_pattern_excluded.png")).get_axes()[0]
    (band,) = ax.patches
    assert _span(band) == pytest.approx(EXCLUDED)

    drawn = ax.get_lines()[0].get_xdata()
    assert np.any((drawn >= EXCLUDED[0]) & (drawn <= EXCLUDED[1])), \
        "the excluded channels are still a measurement, and are drawn"
    fit_x = plot_result(result).get_axes()[0].get_lines()[0].get_xdata()
    inside = (fit_x >= EXCLUDED[0]) & (fit_x <= EXCLUDED[1])
    assert not inside.any(), "the result has no channel inside the region"
    gap = np.diff(fit_x).argmax()
    assert fit_x[gap] < EXCLUDED[0] and fit_x[gap + 1] > EXCLUDED[1]

    # on a d axis the edges arrive in the other order and the band follows
    lam = 0.45
    d_ax = plot_pattern(pattern, x_axis="d", wavelength=lam).get_axes()[0]
    expect = sorted(lam / (2 * np.sin(np.radians(t) / 2)) for t in EXCLUDED)
    assert _span(d_ax.patches[0]) == pytest.approx(expect)
    # a window that misses the region draws no band at all
    assert not plot_pattern(pattern, two_theta_range=(10.0, 14.0)).get_axes()[0].patches


def test_a_region_from_two_theta_zero_is_clipped_before_it_becomes_d_or_q(fitted):
    """A beamstop exclusion from 2θ = 0 has no d or Q edge; only the part of it
    inside the drawn span is converted and shaded (review of #529)."""
    pattern, _ = fitted
    tt = pattern.tt()
    start = float(tt.min())
    beamstop = pattern.model_copy(deep=True)
    beamstop.excluded_regions = [(0.0, start + 0.5)]
    lam = 1.54
    for axis in ("d", "q"):
        ax = plot_pattern(beamstop, x_axis=axis, wavelength=lam).get_axes()[0]
        (band,) = ax.patches
        if axis == "d":
            ends = [lam / (2 * np.sin(np.radians(t) / 2)) for t in (start, start + 0.5)]
        else:
            ends = [4 * np.pi * np.sin(np.radians(t) / 2) / lam for t in (start, start + 0.5)]
        assert _span(band) == pytest.approx(sorted(ends))
    # a region wholly below the drawn span draws nothing and does not raise
    below = pattern.model_copy(deep=True)
    below.excluded_regions = [(0.0, start / 2)]
    assert not plot_pattern(below, x_axis="d", wavelength=lam).get_axes()[0].patches


def test_pattern_data_plot_forwards_and_refuses_what_the_result_refuses(fitted):
    pattern, _ = fitted
    OUT.mkdir(exist_ok=True)
    out = OUT / "viz_pattern_default.png"
    fig = pattern.plot(str(out), y_scale="sqrt")
    assert out.stat().st_size > 5_000
    assert fig.get_axes()[0].get_yscale() == "function"
    with pytest.raises(ValueError, match="style must be one of"):
        pattern.plot(style="solarized")
    with pytest.raises(ValueError, match="wavelength"):
        pattern.plot(x_axis="q")
    with pytest.raises(ValueError, match="y_scale must be one of"):
        pattern.plot(y_scale="logit")
    with pytest.raises(ValueError, match="contains no points"):
        pattern.plot(two_theta_range=(90.0, 91.0))


# ----------------------------------------------------------------------
# model=: the starting background, and the radiation on the 2θ label (WP-2037)
# ----------------------------------------------------------------------
def _starting(instrument=None, background=TRUE_BKG) -> rx.Refinement:
    """The perturbed LaB6 model, its background set to ``background``."""
    structure, ins = perturbed_models()
    ins = instrument if instrument is not None else ins
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in background])
    return rx.Refinement(structure, ins, history=False)


def _dashed(ax) -> list:
    """The modelled curves on ``ax``: the only lines drawn dashed."""
    return [line for line in ax.get_lines() if line.get_linestyle() == "--"]


TWO_THETA = r"$2\theta$ (degrees)"


def test_a_model_draws_its_starting_background_under_the_data(fitted):
    """The background a fit would start from, dashed in the result panel's
    background ink, over the channels the fit would use, with its name in the
    gutter between the curve above it and the tick row below it."""
    pattern, _ = fitted
    OUT.mkdir(exist_ok=True)
    ax = plot_pattern(pattern, model=_starting(),
                      path=str(OUT / "viz_pattern_model_background.png")).get_axes()[0]
    (line,) = _dashed(ax)
    assert line.get_color() == PALETTES["light"]["bkg"]
    # the synthetic pattern was drawn with TRUE_BKG on this same range, so the
    # starting curve is that Chebyshev series, computed here independently
    tt, y = np.asarray(line.get_xdata()), np.asarray(line.get_ydata())
    lo, hi = pattern.two_theta[0], pattern.two_theta[-1]
    expect = np.polynomial.chebyshev.chebval(2 * (tt - lo) / (hi - lo) - 1, TRUE_BKG)
    assert np.allclose(y, expect, rtol=1e-12)
    assert not ((tt >= EXCLUDED[0]) & (tt <= EXCLUDED[1])).any(), \
        "drawn over the channels a fit would use, as the result's is"
    assert [t.get_text() for t in ax.texts] == ["observed", "background", "LaB6"]
    obs, bkg, row = (t.xy[1] for t in ax.texts)
    assert obs > bkg > row

    # a window draws the window's part of the same curve
    windowed = plot_pattern(pattern, model=_starting(),
                            two_theta_range=(8.0, 16.0)).get_axes()[0]
    tt_w = np.asarray(_dashed(windowed)[0].get_xdata())
    assert tt_w.min() >= 8.0 and tt_w.max() <= 16.0

    # a starting value far above the counts is in the picture, not off it
    tall = 3.0 * max(pattern.intensity)
    high = plot_pattern(pattern, model=_starting(background=[tall])).get_axes()[0]
    assert high.get_ylim()[1] > tall


def test_no_model_and_a_zero_background_draw_no_background(fitted):
    """Without a model nothing modelled is drawn; with the default instrument's
    background, zero everywhere, there is nothing to check against the data."""
    pattern, _ = fitted
    bare = plot_pattern(pattern).get_axes()[0]
    assert not _dashed(bare) and "background" not in [t.get_text() for t in bare.texts]
    zero = plot_pattern(pattern, model=_starting(background=[0.0, 0.0])).get_axes()[0]
    assert not _dashed(zero)
    assert [t.get_text() for t in zero.texts] == ["observed", "LaB6"]


@pytest.mark.parametrize("instrument, label", [
    (lambda: rx.Instrument.bragg_brentano(radiation="CuKa"),
     TWO_THETA + r", Cu Kα, $\lambda$ = 1.54059 Å"),
    (lambda: rx.Instrument.bragg_brentano(radiation="MoKa1"),
     TWO_THETA + r", Mo Kα1, $\lambda$ = 0.709317 Å"),
    # one line 24 ppm from Mo Kα1, as a synchrotron can be: λ alone, since a
    # source is named from the table's own lines and never by nearness
    (lambda: rx.Instrument.debye_scherrer(wavelength=0.7093),
     TWO_THETA + r", $\lambda$ = 0.7093 Å"),
    # a neutron beam at Cu Kα1's λ is no copper tube: never matched from λ
    (lambda: rx.Instrument(source=NeutronSource(wavelength=1.5405929)),
     TWO_THETA + r", $\lambda$ = 1.54059 Å"),
], ids=["doublet", "kalpha1", "synchrotron", "neutron"])
def test_the_2theta_label_names_what_the_models_source_states(fitted, instrument,
                                                               label):
    pattern, _ = fitted
    # the model's source wins over what the file recorded
    noted = pattern.model_copy(update={"metadata": {"anode": "Ag",
                                                    "wavelength": "0.5594"}})
    ax = plot_pattern(noted, model=_starting(instrument())).get_axes()[0]
    assert ax.get_xlabel() == label


@pytest.mark.parametrize("metadata, label", [
    ({"anode": "Cu", "wavelength": "1.540598"},
     TWO_THETA + r", Cu Kα, $\lambda$ = 1.5406 Å"),
    # a recorded Kα2 of zero says the doublet was not used
    ({"anode": "CU ", "wavelength": "1.540598", "wavelength_alpha2": "0"},
     TWO_THETA + r", Cu Kα1, $\lambda$ = 1.5406 Å"),
    ({"anode": "Cu"}, TWO_THETA + ", Cu Kα"),
    # an anode outside the package's table is not named; the λ still is
    ({"anode": "W", "wavelength": "0.2"}, TWO_THETA + r", $\lambda$ = 0.2 Å"),
    ({"wavelength": "not a number"}, TWO_THETA),
    ({"source_file": "FAP.XRA", "format": "gsas-std"}, TWO_THETA),
], ids=["anode", "kalpha1", "anode-only", "foreign-anode", "unreadable", "neither"])
def test_without_a_model_the_label_reads_what_the_file_recorded(fitted, metadata,
                                                                label):
    pattern, _ = fitted
    noted = pattern.model_copy(update={"metadata": metadata})
    assert plot_pattern(noted).get_axes()[0].get_xlabel() == label


def test_an_explicit_wavelength_replaces_what_the_model_and_file_state(fitted):
    pattern, _ = fitted
    noted = pattern.model_copy(update={"metadata": {"anode": "Cu",
                                                    "wavelength": "1.540598"}})
    cu = _starting(rx.Instrument.bragg_brentano(radiation="CuKa"))
    for kw in ({}, {"model": cu}):
        ax = plot_pattern(noted, wavelength=0.5, **kw).get_axes()[0]
        assert ax.get_xlabel() == TWO_THETA + r", $\lambda$ = 0.5 Å", kw


# ----------------------------------------------------------------------
# title=
# ----------------------------------------------------------------------
def test_a_title_is_the_callers_words_in_the_panels_type(fitted):
    pattern, result = fitted
    OUT.mkdir(exist_ok=True)
    for kw in ({}, {"weighted": True}, {"y_scale": "log"}):
        fig = plot_result(result, title="pattern 3 of 30", font_size=9.0, **kw)
        top = fig.get_axes()[0]
        assert top.get_title() == "pattern 3 of 30", kw
        assert top.title.get_fontsize() == 9.0, "one type size for the figure"
        # the statistics stay a corner annotation beside a title, not in it
        assert any("R_" in t.get_text() for t in top.texts)
        assert all(ax.get_title() == "" for ax in fig.get_axes()[1:])
    result.plot(path=str(OUT / "viz_result_titled.png"), title="LaB6, synthetic")
    ax = pattern.plot(str(OUT / "viz_pattern_titled.png"),
                      title="LaB6, before the model").get_axes()[0]
    assert ax.get_title() == "LaB6, before the model"


def test_no_title_is_the_figure_without_the_keyword(fitted):
    """`title=None` draws nothing, byte for byte, on every figure that takes it."""
    pattern, result = fitted
    assert _png(plot_result(result)) == _png(plot_result(result, title=None))
    assert _png(plot_result(result, weighted=True)) == \
        _png(plot_result(result, weighted=True, title=None))
    assert _png(plot_pattern(pattern)) == _png(plot_pattern(pattern, title=None))
    assert _png(plot_result(result)) != _png(plot_result(result, title="x"))


def test_the_vlm_montage_refuses_a_title_by_name(fitted, tmp_path):
    """Its panel titles are evidence a model reads; a caller's is not added."""
    _, result = fitted
    with pytest.raises(TypeError, match="title"):
        plot_for_vlm(result, path=str(tmp_path / "vlm.png"), title="x")


#: sha256 of :func:`plot_result`'s renders of :func:`_pinned_result`,
#: captured from ``origin/main`` at ``f1b89d63`` — before WP-1444 moved the
#: intensity-axis code into a helper and added ``title=`` — and matched by the
#: tree after it.  Pinned where it was captured, as the bit-identity goldens
#: are (``tests/test_backend_shim.py``): a PNG's bytes follow matplotlib's and
#: FreeType's versions, not only this code.  Re-captured under matplotlib
#: 3.11.2 from ``origin/main`` at ``703d3fbd`` and matched by WP-1971's tree,
#: because under the 3.11.1 pin the test had been skipping everywhere.
PRE_TITLE_RENDER = {
    "default": "5f6b7e318ea0aacaecd0dbaa16a334c9ef0fc1d687c2fe181b10ffdf3461c84f",
    "weighted": "cff5d9a9368c173a6536a2ee51a58818faf88a471835998b1f33656c0fdab472",
    "log": "1a7126b2edc25e1823efdf2eaf97dd49150b5160652737d99727aade1f550e12",
}
PINNED_ON = (("darwin", "arm64"), "3.11.2")


def _pinned_result(result):
    """A result whose drawn arrays are closed-form, so no fit's last digit
    reaches the render; only the rendering code and its libraries do."""
    pinned = result.model_copy(deep=True)
    tt = np.arange(5.0, 25.0, 0.02)
    peaks = sum(a * np.exp(-0.5 * ((tt - c) / 0.05) ** 2)
                for a, c in ((1000.0, 8.0), (600.0, 12.5), (300.0, 19.0)))
    bkg = 50.0 + 2.0 * (tt - 5.0)
    pinned.two_theta = tt.tolist()
    pinned.y_calc = (peaks + bkg).tolist()
    pinned.y_obs = (peaks * 1.03 + bkg + 3.0 * np.sin(7.0 * tt)).tolist()
    pinned.y_background = bkg.tolist()
    pinned.sigma = np.sqrt(peaks + bkg).tolist()
    pinned.ticks = {"LaB6": [8.0, 12.5, 19.0]}
    pinned.statistics = pinned.statistics.model_copy(update={"rwp": 0.05, "gof": 1.5})
    return pinned


def test_the_default_result_render_is_the_pre_title_render(fitted):
    import matplotlib

    here = ((sys.platform, platform.machine()), matplotlib.__version__)
    if here != PINNED_ON:
        pytest.skip(f"render pinned on {PINNED_ON}, this is {here}")
    _, result = fitted
    pinned = _pinned_result(result)
    for name, kw in (("default", {}), ("weighted", {"weighted": True}),
                     ("log", {"y_scale": "log"})):
        got = hashlib.sha256(_png(plot_result(pinned, **kw))).hexdigest()
        assert got == PRE_TITLE_RENDER[name], name


# -- WP-1970: the dark copy a notebook shows beside the light figure --------

def _pixels(fig) -> np.ndarray:
    """``fig`` as the notebook encoder frames it, unquantised."""
    from PIL import Image

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    return np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))


def _series():
    """A four-pattern series carrying a reseeded, a diverged and an outlier mark."""
    from rietx.schemas.results import RefinedParameter, Statistics
    from rietx.schemas.sequential import SeriesEntry, SeriesResult

    def entry(i, **kw):
        return SeriesEntry(
            index=i, label=f"p{i}", x=float(i),
            statistics=Statistics(rwp=0.1, rp=0.1, rexp=0.05, chi2=1.0, gof=1.0,
                                  n_points=10, n_free_parameters=1),
            parameters=[RefinedParameter(path="phases.0.cell.a",
                                         value=4.0 + 0.01 * i, stderr=1e-3)], **kw)

    return SeriesResult(entries=[entry(0), entry(1, reseeded=True, rung="cold"),
                                 entry(2, status="diverged"),
                                 entry(3, rwp_fence=0.05)])


def _two_phases(result):
    """The fit with a second tick row, so the phase colours are drawn."""
    (name, ticks), = result.ticks.items()
    return result.model_copy(update={"ticks": {
        name: ticks, "second": [t + 0.7 for t in ticks]}})


def _peaks(result):
    """The fit's own reflection positions as a position-only peak list."""
    from rietx.schemas.indexing import PeakList

    (ticks,) = result.ticks.values()
    return PeakList.from_positions(np.asarray(ticks), WAVELENGTH)


def _candidates():
    """Nine cubic cells, so every rank colour is drawn and the ninth row
    falls back to the recessive grey."""
    from rietx.schemas.indexing import CellCandidate

    return [CellCandidate(cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(0.0,) * 6,
                          system="cubic", volume=a ** 3)
            for a in TRUE_A * np.array([1.0, 2.0, 2 ** 0.5, 3 ** 0.5, 3.0,
                                        1.002, 0.998, 2.5, 5 ** 0.5])]


def _validation():
    """A Le Bail verdict carrying both detector lists."""
    from rietx.schemas.indexing import LeBailValidation

    return LeBailValidation(rwp=0.1, gof=1.2, space_group="P m -3 m",
                            n_reflections=20, predicted_but_absent=2,
                            unmatched_observed=1,
                            predicted_but_absent_two_theta=[12.0, 21.5],
                            unmatched_observed_two_theta=[16.2])


DRAWINGS = {
    "result": lambda pattern, result, **kw: plot_result(result, dpi=100, **kw),
    "weighted": lambda pattern, result, **kw: plot_result(result, weighted=True,
                                                          dpi=100, **kw),
    "sqrt, two phases": lambda pattern, result, **kw: plot_result(
        _two_phases(result), y_scale="sqrt", dpi=100, **kw),
    "pattern": lambda pattern, result, **kw: plot_pattern(pattern, dpi=100, **kw),
    "trajectory": lambda pattern, result, **kw: _series().plot(
        ["phases.0.cell.a"], dpi=100, **kw),
    # WP-1972: the indexing figures, each of their branches
    "peak list": lambda pattern, result, **kw: plot_peak_list(
        _peaks(result), pattern, dpi=100, **kw),
    "peak list alone": lambda pattern, result, **kw: plot_peak_list(
        _peaks(result), dpi=100, **kw),
    "candidates": lambda pattern, result, **kw: plot_candidates(
        _candidates(), _peaks(result), n=9, dpi=100, **kw),
    "validation": lambda pattern, result, **kw: plot_validation(
        _validation(), result, dpi=100, **kw),
    "validation alone": lambda pattern, result, **kw: plot_validation(
        _validation(), dpi=100, **kw),
}


@pytest.mark.parametrize("name", list(DRAWINGS))
def test_the_dark_copy_is_the_dark_figure_pixel_for_pixel(fitted, name):
    """Recolouring a light figure gives the one drawn with ``style="dark"``.

    This is what lets the notebook's dark image be a recoloured copy, which
    keeps what a caller added, rather than a redraw, which drops it.  The
    light figure is encoded first, as the formatter encodes it, because that
    draw creates the tick artists the copy recolours.
    """
    import copy

    import matplotlib.pyplot as plt

    from rietx.viz.plots import _darkened

    draw = DRAWINGS[name]
    light = draw(*fitted)
    _pixels(light)
    twin = _darkened(copy.deepcopy(light))
    assert np.array_equal(_pixels(twin), _pixels(draw(*fitted, style="dark")))
    plt.close("all")


# -- WP-1971: the figure a plot hands back, once a caller has changed it ----

def _notebook_size(fig) -> tuple[int, int]:
    """The notebook image's size in pixels, as the encoder frames it."""
    from PIL import Image

    from rietx.viz.plots import _notebook_png

    return Image.open(io.BytesIO(_notebook_png(fig)[0])).size


def _zoom(ax, axis: str, lo: float, hi: float) -> None:
    """Narrow ``ax`` to the fractions ``lo``-``hi`` of its own range."""
    get, put = ((ax.get_xlim, ax.set_xlim) if axis == "x"
                else (ax.get_ylim, ax.set_ylim))
    a, b = get()
    put(a + lo * (b - a), a + hi * (b - a))


@pytest.mark.parametrize("name", ["result", "weighted", "sqrt, two phases", "pattern"])
@pytest.mark.parametrize("zoom", [("x", 0.4, 0.5), ("y", 0.0, 0.05), ("y", 0.5, 1.0)])
def test_a_callers_zoom_keeps_the_notebook_image_its_designed_size(fitted, name, zoom):
    """The gutter labels and the statistics annotation stay beside the axes,
    and a label or spine the zoom leaves outside them is clipped.  Placed in
    data coordinates, a zoom to a tenth of the x range made the image 7.7
    times wider and one to the lowest twentieth of y 15 times taller.  The
    height may grow by the clip's margin, ``_CLIP_MARGIN`` of the axes
    height at each end, which a clipped spine reaches: 15 px of 871."""
    import matplotlib.pyplot as plt

    fig = DRAWINGS[name](*fitted)
    width, height = _notebook_size(fig)
    _zoom(fig.axes[0], *zoom)
    zoomed_width, zoomed_height = _notebook_size(fig)
    assert zoomed_width <= width
    assert zoomed_height <= 1.05 * height
    plt.close("all")


def test_a_gutter_label_the_zoom_leaves_outside_the_view_is_hidden_whole(fitted):
    """A label whose height a ``set_ylim`` leaves just above the view is not
    drawn at all, rather than drawn sliced by a clip edge."""
    import matplotlib.pyplot as plt

    fig = DRAWINGS["pattern"](*fitted)
    ax = fig.axes[0]
    (label,) = [t for t in ax.texts if t.get_text() == "observed"]
    lo, _ = ax.get_ylim()
    ax.set_ylim(lo, lo + (label.xy[1] - lo) / 1.018)
    _notebook_size(fig)
    assert not label.get_tightbbox().width > 0
    plt.close("all")


@pytest.mark.parametrize("name", list(DRAWINGS))
def test_a_returned_figure_pickles_and_comes_back_the_same(fitted, name, monkeypatch):
    """A figure pickles as any matplotlib figure does, and loads to the same
    pixels.  The class is found by name through the module's ``__getattr__``.
    The cached class is dropped before loading, as in a fresh process, so the
    load has to build it."""
    import pickle

    import matplotlib.pyplot as plt

    from rietx.viz import plots

    fig = DRAWINGS[name](*fitted)
    blob = pickle.dumps(fig)
    monkeypatch.setattr(plots, "_FIGURE_CLASS", None)
    back = pickle.loads(blob)
    assert type(back) is plots._NotebookFigure
    assert back._rietx_style == fig._rietx_style
    assert np.array_equal(_pixels(back), _pixels(fig))
    plt.close("all")


def _inks(fig) -> set[str]:
    """Every colour ``fig`` puts on the page, as hex: visible artists only,
    and a marker-only line's markers without its unused line colour."""
    from matplotlib.collections import Collection
    from matplotlib.colors import to_hex, to_rgba
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.text import Text

    out: set[str] = set()
    for artist in fig.findobj(lambda a: a.get_visible()):
        if isinstance(artist, Text):
            colours = [artist.get_color()]
        elif isinstance(artist, Line2D):
            if not len(artist.get_xdata()):
                continue
            colours = [artist.get_markerfacecolor(), artist.get_markeredgecolor()]
            if artist.get_linestyle() not in ("None", "none", ""):
                colours.append(artist.get_color())
        elif isinstance(artist, Patch):
            colours = [artist.get_facecolor(), artist.get_edgecolor()]
        elif isinstance(artist, Collection):
            colours = [*artist.get_facecolor(), *artist.get_edgecolor()]
        else:
            continue
        for colour in colours:
            if isinstance(colour, str) and colour.lower() in ("none", "auto"):
                continue
            rgba = to_rgba(colour)
            if rgba[3] > 0:
                out.add(to_hex(rgba[:3]))
    return out


@pytest.mark.parametrize("name", list(DRAWINGS))
def test_every_ink_a_light_figure_draws_has_a_dark_form(fitted, name):
    """The pixel test above cannot see a colour outside :data:`PALETTES`:
    the copy leaves it as drawn and the dark figure draws it too, so both
    agree on a light colour on the dark page.  That is how the indexing
    figures went without a dark form until WP-1972.  So a light figure
    draws palette colours and matplotlib's black and white, and nothing
    else."""
    import io

    import matplotlib.pyplot as plt

    known = {"#000000", "#ffffff"}
    for value in PALETTES["light"].values():
        known.update(c.lower() for c in (value if isinstance(value, list) else [value]))
    fig = DRAWINGS[name](*fitted)
    fig.savefig(io.BytesIO(), format="png")  # the draw that makes the ticks
    assert _inks(fig) <= known, sorted(_inks(fig) - known)
    plt.close("all")


def test_the_light_palette_maps_onto_the_dark_one():
    """The recolour is a function of the light colour, so two roles sharing a
    light colour share a dark one.  Black and white are matplotlib's own inks,
    mapped by the artist's kind, so no role may take either.  A ranked list
    maps entry by entry, so its two grounds' lists are one length."""
    light, dark = PALETTES["light"], PALETTES["dark"]
    seen: dict[str, str] = {}
    for role, value in light.items():
        if role == "ground":
            continue
        if isinstance(value, list):
            assert len(value) == len(dark[role]), role
            pairs = list(zip(value, dark[role]))
        else:
            pairs = [(value, dark[role])]
        for colour, ink in pairs:
            assert colour.lower() not in ("#000000", "#ffffff"), role
            assert seen.setdefault(colour.lower(), ink) == ink, role


def test_what_the_caller_adds_shows_in_the_dark_copy(fitted):
    """A note keeps its place; black ink turns to the dark page's, and a
    colour of the caller's own is left as drawn."""
    import copy

    import matplotlib.pyplot as plt
    from matplotlib.colors import to_hex

    from rietx.viz.plots import _darkened

    _, result = fitted
    light = plot_result(result, dpi=100)
    ax = light.axes[0]
    ax.annotate("note", (8.0, 100.0), xytext=(10.0, 200.0),
                arrowprops={"arrowstyle": "-|>"})
    ax.axvline(9.0, color="#d62728")
    twin = _darkened(copy.deepcopy(light))
    (note,) = [t for t in twin.axes[0].texts if t.get_text() == "note"]
    assert to_hex(note.get_color()) == PALETTES["dark"]["fg"]
    assert to_hex(note.arrow_patch.get_edgecolor()) == PALETTES["dark"]["rule"]
    assert to_hex(twin.axes[0].lines[-1].get_color()) == "#d62728"
    plt.close("all")


def test_the_notebook_html_holds_the_light_image_and_a_hidden_dark_one(fitted, tmp_path):
    """The bundle's shape (WP-1970).  The dark image is hidden inline, which
    every sanitizer measured keeps, so where the ``<style>`` is stripped the
    light figure is the one shown.  Every rule in the ``<style>`` names a
    prefixed class, since in a Sphinx page it applies to the whole page."""
    import base64
    import re

    import matplotlib.pyplot as plt

    from rietx.viz._notebook import DARK_MARKERS
    from rietx.viz.plots import _notebook_png

    _, result = fitted
    fig = plot_result(result)
    bundle, metadata = fig._repr_mimebundle_()
    html = bundle["text/html"]
    light, dark = re.findall(r"<img [^>]*>", html)
    assert 'class="rx-fig-light only-light"' in light and "display:none" not in light
    assert 'class="rx-fig-dark only-dark"' in dark and "display:none" in dark
    # the PNG beside it is the light image, encoded once for both
    data, meta = _notebook_png(fig)
    assert bundle["image/png"] == data and metadata == {"image/png": meta}
    assert re.search(r'base64,([^"]+)"', light).group(1) == base64.b64encode(data).decode()
    assert re.search(r'base64,([^"]+)"', dark).group(1) != base64.b64encode(data).decode()
    for image in (light, dark):
        assert f'width="{meta["width"]}"' in image
    (style,) = re.findall(r"<style>(.*?)</style>", html)
    for rule in re.findall(r"([^{}]+)\{[^}]*\}", style):
        for selector in rule.split(","):
            assert re.search(r"\.rx-fig-(light|dark)$", selector.strip()), selector
    for marker in DARK_MARKERS:
        assert f"{marker} .rx-fig-dark" in style
    # a figure with no dark form shows the PNG alone
    for alone in (plot_result(result, style="dark"),
                  plot_for_vlm(result, path=str(tmp_path / "vlm.png"))):
        assert list(alone._repr_mimebundle_()[0]) == ["image/png"]
    # a display that drops the HTML is not made to draw it
    assert list(fig._repr_mimebundle_(include=["image/png"])[0]) == ["image/png"]
    assert list(fig._repr_mimebundle_(exclude=["text/html"])[0]) == ["image/png"]
    plt.close("all")


def test_the_dark_copy_leaves_pyplot_s_figures_alone(fitted):
    """Under any backend but the inline one, pyplot still holds the returned
    figure, and a deep copy of it registers itself with pyplot too: one stray
    figure, or window, per display, until the copy is made detached."""
    import matplotlib.pyplot as plt

    plt.close("all")
    _, result = fitted
    fig = plot_result(result, dpi=100)
    before = plt.get_fignums()
    assert len(before) == 1  # the suite's Agg keeps it, as a script's backend does
    assert "text/html" in fig._repr_mimebundle_()[0]
    assert plt.get_fignums() == before
    assert fig.canvas.manager is not None  # handed back as it was
    plt.close("all")
