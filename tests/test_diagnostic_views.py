"""A diagnostic names the rendered view that shows it (WP-1133).

``Diagnostic.view`` reads :data:`rietx.help.DIAGNOSTIC_VIEW_OF` by code, and
each name it returns is a panel of :func:`rietx.viz.plot_for_vlm`.  These tests
hold the three halves together.  A name with no panel fails, as does a panel
name no code uses, because a declared name nothing produces reads as a claim
(root CLAUDE.md, WP-1076).  A code listed with a view must have a fit here that
fires it, and that fit's montage is drawn to ``tests/output/wp1133/`` to be
looked at.  Whether the finding is legible on the panel is read off those
pictures; no assertion can see it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rietx._display import diagnostic_lines
from rietx.help import DIAGNOSTIC_HELP, DIAGNOSTIC_VIEW_OF, DIAGNOSTIC_VIEWS
from rietx.schemas.common import Diagnostic

OUT = Path(__file__).parent / "output" / "wp1133"


def _low_angle():
    from tests import test_low_angle_region as t
    return t._fit_plain_chebyshev(t._lab6_air_scatter_pattern(lo=4.0))


def _air_scatter():
    from tests import test_air_scatter_undeclared as t
    return t._fit(t._pattern(600.0, step=0.01))[1]


def _far_from_data():
    from tests import test_fit_usable as t
    return t._nac(seeded=False, n_stages=3)


#: A fit that fires each code with a view, from that code's own test file.
CASES = {
    "AIR_SCATTER_UNDECLARED": _air_scatter,
    "LOW_ANGLE_UNMODELLED": _low_angle,
    "MODEL_FAR_FROM_DATA": _far_from_data,
}


def test_every_view_a_code_names_is_in_the_vocabulary():
    assert set(DIAGNOSTIC_VIEW_OF.values()) <= set(DIAGNOSTIC_VIEWS)


def test_every_view_in_the_vocabulary_is_named_by_a_code():
    assert set(DIAGNOSTIC_VIEWS) == set(DIAGNOSTIC_VIEW_OF.values())


def test_every_code_with_a_view_is_a_code_the_package_raises():
    assert set(DIAGNOSTIC_VIEW_OF) <= set(DIAGNOSTIC_HELP)


def test_every_code_with_a_view_has_a_fit_that_fires_it():
    assert set(CASES) == set(DIAGNOSTIC_VIEW_OF)


@pytest.mark.parametrize("code", sorted(DIAGNOSTIC_VIEW_OF))
def test_the_named_panel_is_drawn_on_a_fit_that_fires_the_code(code):
    plt = pytest.importorskip("matplotlib.pyplot")
    from rietx.viz import plot_for_vlm

    result = CASES[code]()
    found = [d for d in result.diagnostics if d.code == code]
    assert found, sorted(d.code for d in result.diagnostics)
    assert found[0].view == DIAGNOSTIC_VIEW_OF[code]
    OUT.mkdir(parents=True, exist_ok=True)
    fig = plot_for_vlm(result, path=str(OUT / f"{code.lower()}.png"))
    try:
        assert set(DIAGNOSTIC_VIEWS) <= {ax.get_gid() for ax in fig.axes}
    finally:
        plt.close(fig)


def test_the_view_is_looked_up_and_never_stored():
    d = Diagnostic(level="warning", code="LOW_ANGLE_UNMODELLED", message="m")
    assert d.view == "plot_for_vlm.residual"
    assert "view" not in d.model_dump(mode="json")
    again = Diagnostic.model_validate_json(d.model_dump_json())
    assert again == d and again.view == d.view


@pytest.mark.parametrize("code", ["HIGH_CORRELATION", "BACKGROUND_ABSORPTION",
                                  "A_CODE_NO_BUILD_RAISES"])
def test_a_code_with_no_view_reads_none(code):
    assert Diagnostic(level="info", code=code, message="m").view is None


def test_the_notebook_form_names_the_view_and_the_text_form_does_not():
    d = Diagnostic(level="warning", code="MODEL_FAR_FROM_DATA", message="m",
                   suggestion="s")
    text = "\n".join(diagnostic_lines(d))
    notebook = "\n".join(diagnostic_lines(d, notebook=True))
    assert "see:" not in text and "see:" not in str(d)
    assert "  see: the top panel of rietx.viz.plot_for_vlm" in notebook
    plain = Diagnostic(level="info", code="HIGH_CORRELATION", message="m")
    assert "see:" not in "\n".join(diagnostic_lines(plain, notebook=True))
