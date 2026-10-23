"""How rietx objects read when printed or shown in a notebook (WP-1544).

The regression pinned here is size: a pattern's repr was 1.4 MB and a result's
0.8 MB, and pydantic's ``__str__`` is its repr, so ``print`` was no escape. The
ceilings sit well above what the objects print now, so they fail on a sequence
leaking back in, not on a reworded line.

One FAP fit is shared by the module, so it sits on one xdist worker.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import rietx as rx
from rietx._display import summarise

DATA = Path(__file__).parent / "data"

pytestmark = pytest.mark.xdist_group("display")


@pytest.fixture(scope="module")
def fap():
    data = rx.read_pattern(DATA / "FAP.XRA")
    structure = rx.Structure.from_cif(str(DATA / "fluorapatite.cif"))
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, plan="mccusker_default", two_theta_limits=(15, 130))
    return {"data": data, "structure": structure, "instrument": instrument,
            "ref": ref, "result": result}


@pytest.mark.parametrize("name, ceiling", [
    ("data", 1_000), ("instrument", 6_000), ("structure", 12_000),
    ("result", 30_000)])
def test_repr_and_str_stay_short(fap, name, ceiling):
    obj = fap[name]
    assert len(repr(obj)) < ceiling, f"repr({name}) is {len(repr(obj))} chars"
    assert len(str(obj)) < ceiling, f"str({name}) is {len(str(obj))} chars"


def test_a_pattern_repr_keeps_its_range_not_its_channels(fap):
    text = repr(fap["data"])
    n = len(fap["data"].two_theta)
    assert f"two_theta=<{n} floats 15…130.04>" in text


def test_summarise_walks_dicts_and_short_sequences():
    ticks = {"phase": [float(x) for x in range(100)]}
    assert repr(summarise(ticks)) == "{'phase': <100 floats 0…99>}"
    assert summarise([1.0, 2.0]) == [1.0, 2.0]
    assert repr(summarise([[1.0, 2.0]] * 20)) == "<20 lists>"
    assert repr(summarise(["a"] * 9)) == "<9 strings>"


def test_a_schema_prints_as_a_tree_with_one_line_per_parameter(fap):
    text = str(fap["instrument"])
    assert text.startswith("Instrument\n")
    assert "  zero_shift: 0 deg 2θ" in text.splitlines()
    assert "None" not in text, "a None field says nothing and is left out"


def test_a_free_parameter_is_marked_and_carries_its_esd(fap):
    from rietx._display import parameter_text
    from rietx.schemas.common import Parameter
    a = fap["result"].parameter("phases.0.cell.a")
    text = parameter_text(Parameter(value=a.value, stderr=a.stderr, vary=True, unit="A"))
    assert text.endswith(" Å (vary)") and "(" in text.split()[0]


def test_diagnostics_print_every_field_under_its_heading(fap):
    """Three headings, the maintainer's choice of 2026-10-23 (WP-2037): every
    field once, the range in the head, and ``contamination_searches`` read by
    the ``contamination`` row rather than printed as one of its own."""
    from rietx.background.diagnostics import PatternDiagnostics
    groups = PatternDiagnostics._READING_ORDER
    order = [name for _, names in groups for name in names]
    fields = set(PatternDiagnostics.model_fields) - {
        "n_points", "two_theta_min", "two_theta_max", "contamination_searches"}
    assert sorted(order) == sorted(fields), "every field once, the range in the head"
    assert [heading for heading, _ in groups] == [
        "checked on every pattern", "matters on some instruments",
        "rietx's own measurements"]
    lines = str(rx.diagnose(fap["data"], wavelength=1.5406)).splitlines()
    expected = []
    for heading, names in groups:
        expected += [heading, *names]
    assert [ln.split(":")[0].strip() for ln in lines[1:]] == expected
    assert lines[1] == "  checked on every pattern"
    assert lines[2].startswith("    signal_cutoffs:"), "an empty finding is printed, first"


def test_diagnostics_cut_their_numbers_and_say_which_checks_did_not_run(fap):
    """Each empty state is read off a field, never recomputed: FAP.XRA has no
    σ column, so the three σ checks did not run, and the ghost screen runs
    only when it was given a wavelength."""
    d = rx.diagnose(fap["data"], wavelength=1.5406)
    rows = {ln.split(":")[0].strip(): ln.split(":", 1)[1].strip()
            for ln in str(d).splitlines()[1:] if ":" in ln}
    for name in ("dead_channels", "coverage_plateau", "coverage_regions"):
        assert rows[name] == "not checked (no measured σ)", name
    assert rows["contamination"] == "none", "the screen ran and found nothing"
    assert d.contamination_searches == ["kbeta", "tungsten_la"]
    assert rows["signal_cutoffs"] == "none"
    assert rows["steps_per_fwhm"] == "4.65" and rows["baseline_lambda"] == "10000"
    assert rows["peak_density_per_deg"] == "0.843"

    blind = rx.diagnose(fap["data"])
    assert blind.contamination == [] and blind.contamination_searches == []
    assert "    contamination:        not checked" in str(blind).splitlines()

    measured = d.model_copy(update={"coverage_plateau": 1.0})
    lines = str(measured).splitlines()
    assert "    dead_channels:        none" in lines, "σ measured: checked, and nothing"
    assert "    coverage_plateau:     1.00" in lines
    unmeasurable = d.model_copy(update={"steps_per_fwhm": None, "n_peaks_measured": 0})
    assert ("    steps_per_fwhm:       not measured (no peak measurable)"
            in str(unmeasurable).splitlines())
    unrecorded = d.model_copy(update={"contamination_searches": None})
    assert ("    contamination:        none, or not checked (not recorded)"
            in str(unrecorded).splitlines())


def test_a_number_is_cut_to_three_significant_figures():
    from rietx._display import significant
    cases = {4.6463609: "4.65", 146.22781: "146", 10000.0: "10000",
             0.84318498: "0.843", 12.041595: "12.0", 9.996: "10.0",
             123456.7: "123457", 1e7: "1e+07", 1.234e-5: "1.23e-05", 0.0: "0",
             -0.0517: "-0.0517"}
    assert {x: significant(x) for x in cases} == cases


def test_a_block_prints_its_values_in_one_column(fap):
    """WP-2037: the one-line fields of a block share a value column; a field
    that opens a block of its own keeps ``name: Type``.  A ``Parameter`` keeps
    its own digits, since a wavelength needs them."""
    lines = str(fap["data"]).splitlines()
    assert lines[0].startswith("PatternData of 5753 points, 15–130.04° 2θ")
    assert "  sigma:            None" in lines
    starts ={len(ln) - len(ln.split(":", 1)[1].lstrip()) for ln in lines[1:]}
    assert starts == {len("  excluded_regions: ")}, lines
    text = str(fap["instrument"]).splitlines()
    assert "  source: Source" in text, "a block's opener keeps its form"
    assert "    polarization: 0.5" in text
    assert "    kind:         'xray_cw'" in text, "padded to its longest sibling"
    assert any("wavelength=1.5405929 Å" in ln for ln in text)


def test_a_parameter_row_prints_on_one_line(fap):
    rows = fap["ref"].parameters()
    assert all("\n" not in str(row) for row in rows)
    tied = next(r for r in rows if r.path == "phases.0.cell.b")
    assert str(tied).endswith("tied = 1·phases.0.cell.a")


def test_a_refined_parameter_prints_on_one_line_as_a_row_does(fap):
    from rietx.schemas.results import RefinedParameter
    a = fap["result"].parameter("phases.0.cell.a")
    row = next(r for r in fap["ref"].parameters() if r.path == a.path)
    assert str(a) == str(row), "a result's row and the table's row read alike"
    tied = RefinedParameter(path="p", value=1.0, stderr=0.1, vary=False, at_bound=True,
                            equations=["ramp"])
    assert str(tied) == "p  1.00(10)  tied  at_bound  equations: ramp"


def test_a_distance_prints_on_one_line_and_so_does_its_table():
    from rietx.schemas.results import GeometryDistance, GeometryTable
    bond = GeometryDistance(phase_index=0, atom_1="P3", atom_2="O7", atom_index_1=2,
                            atom_index_2=6, distance=1.5331, stderr=0.005, symmetry_2="2_554")
    assert str(bond) == "P3–O7  1.5331(50) Å  2_554"
    contact = bond.model_copy(update={"bonded": False, "symmetry_2": ".", "stderr": None})
    assert str(contact) == "P3–O7  1.5331 Å  contact"
    assert "    [0] P3–O7  1.5331(50) Å  2_554" in str(GeometryTable(distances=[bond])).splitlines()


def test_displaying_a_refinement_runs_nothing(fap, monkeypatch):
    """IPython builds every form a displayed value has, so a view that called
    ``summary()`` would build a report, and a report's layer 2 runs rival
    fits, on every displayed cell."""
    ref = fap["ref"]

    def refuse(*a, **k):
        raise AssertionError("a display computed a fit or a report")
    for name in ("fit", "report", "summary"):
        monkeypatch.setattr(type(ref), name, refuse)
    text = str(ref)
    assert "last fit: converged" in text
    assert any(line.split()[:1] == ["phases.0.cell.a"] for line in text.splitlines())


def test_html_is_escaped_and_carries_no_style(fap):
    from rietx.schemas.common import Diagnostic
    d = Diagnostic(level="warning", code="NOT_A_CODE_HERE", message="<script> & more")
    html = fap["result"].model_copy(update={"diagnostics": [d]})._repr_html_()
    assert "<script>" not in html and "&lt;script&gt; &amp; more" in html
    assert "style" not in html and "<script" not in html


def test_a_tree_prints_its_summary(fap):
    tree = fap["ref"].history
    assert str(tree) == tree.summary()


def test_a_structure_figure_shows_its_picture(fap):
    fig = rx.viz.render_structure(fap["structure"], size=120)
    data, md = fig._repr_png_()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    # the width alone, or a column narrower than the figure squashes it (WP-1957)
    assert md == {"width": fig.image.shape[1] // 2}
    import io

    from PIL import Image
    assert Image.open(io.BytesIO(data)).mode == "P"  # a notebook palette, like a fit figure
    from rietx.viz import plots
    from rietx.viz.figure3d import render
    assert render.NOTEBOOK_COLOURS == plots._NOTEBOOK_COLOURS  # restated across the boundary
    assert render.NOTEBOOK_DARK_GROUND == plots.PALETTES["dark"]["ground"]  # likewise
    clear = rx.viz.render_structure(fap["structure"], size=120, background=None)
    assert Image.open(io.BytesIO(clear._repr_png_()[0])).mode == "RGBA"  # its alpha kept
    assert len(repr(fig)) < 100


def test_a_structure_figure_carries_a_dark_copy_drawn_from_what_it_was(fap):
    """WP-1970: on the default white ground the figure's notebook output
    carries the pair, the dark one drawn again from the recipe on the dark
    page's ground.  It is drawn from a copy taken at the call, so a structure
    edited afterwards cannot make the two pictures differ.  A figure on any
    other ground was the caller's choice, and shows alone."""
    import base64
    import re

    from rietx.viz.plots import PALETTES

    structure = fap["structure"].model_copy(deep=True)
    fig = rx.viz.render_structure(structure, size=120)
    dark = rx.viz.render_structure(structure, **{
        **fig.recipe, "background": PALETTES["dark"]["ground"]})
    structure.phases[0].cell.a.value *= 1.2
    bundle, metadata = fig._repr_mimebundle_()
    assert bundle["image/png"] == fig._repr_png_()[0]
    assert metadata == {"image/png": fig._repr_png_()[1]}
    light_img, dark_img = re.findall(r"<img [^>]*>", bundle["text/html"])
    assert "display:none" in dark_img and "display:none" not in light_img
    assert (re.search(r'base64,([^"]+)"', dark_img).group(1)
            == base64.b64encode(dark._repr_png_()[0]).decode())
    for ground in ("black", None, "#ffeedd"):
        alone = rx.viz.render_structure(structure, size=120, background=ground)
        assert list(alone._repr_mimebundle_()[0]) == ["image/png"]


def _notebook_text(obj) -> str:
    """The text inside an object's one ``<pre>``, unescaped."""
    import html
    page = obj._repr_html_()
    assert page.startswith("<pre>") and page.endswith("</pre>")
    return html.unescape(page[len("<pre>"):-len("</pre>")])


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_a_result_notebook_form_is_its_text_and_its_parameter_table(fap):
    """WP-2037: one ``<pre>``, the text ``print`` gives and then the refined
    parameters laid out as text, one row each under a header."""
    result = fap["result"]
    text, table = _notebook_text(result).split(f"\n  parameters: {len(result.parameters)}\n")
    assert text.startswith("RefinementResult: ")
    rows = table.splitlines()
    assert rows[0].split() == ["path", "value", "at_bound"]
    assert [row.split()[0] for row in rows[1:]] == [p.path for p in result.parameters]
    explained = [d for d in result.diagnostics if d.explanation]
    text = _flat(text)
    for d in explained:
        text = text.replace(" means: " + _flat(d.explanation), "", 1)
    assert text == _flat(str(result)), "the text form, and nothing else"


def test_a_result_notebook_form_says_what_each_diagnostic_means_and_print_does_not(fap):
    """WP-2037, decision 1: the explanation (``rietx.help.explain``) is in
    the notebook form, as ``means:`` under ``help:``, wrapped at the
    notebook's width with each continuation under the text after its label.
    ``print``, which an agent reads, leaves it out (WP-1985)."""
    from rietx._display import NOTEBOOK_WIDTH
    from rietx.schemas.common import Diagnostic
    long = Diagnostic(level="warning", code="BOUND_HIT",
                      message="a refined to its upper bound " + "and kept going " * 8,
                      where=["phases.0.cell.a"], suggestion="check the tie " * 10)
    floor = Diagnostic(level="warning", code="FLOOR_HIT", message="y refined to its floor",
                       where=["instrument.profile.y"])
    unknown = Diagnostic(level="info", code="NOT_A_CODE_HERE", message="from another version")
    result = fap["result"].model_copy(update={"diagnostics": [long, floor, unknown]})
    notebook, printed = _notebook_text(result), str(result)
    for d in (long, floor):
        assert "means: " + _flat(d.explanation) in _flat(notebook)
        assert d.explanation.split(".")[0] not in printed
    assert "means:" not in printed and _flat(notebook).count("means:") == 2
    lines = notebook.splitlines()
    label = "    warning[BOUND_HIT]: "
    head = next(i for i, line in enumerate(lines) if line.startswith(label))

    def under(line, label):
        return line.startswith(" " * len(label)) and line[len(label)] != " "
    assert under(lines[head + 1], label), "under the message"
    helps = [i for i, line in enumerate(lines) if line.startswith("      help: ")]
    means = [i for i, line in enumerate(lines) if line.startswith("      means: ")]
    assert under(lines[helps[0] + 1], "      help: ")
    assert helps[0] < means[0] and under(lines[means[0] + 1], "      means: ")
    assert lines[means[1] - 1] == "      at: instrument.profile.y", "no help: it follows at:"
    last = lines.index("    info[NOT_A_CODE_HERE]: from another version")
    assert max(len(line) for line in lines[head:last + 1]) <= NOTEBOOK_WIDTH
    assert last > means[1] and "means:" not in lines[last + 1], "an unknown code means nothing"


@pytest.mark.parametrize("name", ["result", "peaks", "indexing"])
def test_every_notebook_form_is_one_pre(fap, name):
    """WP-2037, decision 1: GitHub's sanitiser strips ``<details>``, and GitHub
    and JupyterLab draw a bare table in the body font, right-aligned.  So
    every ``_repr_html_`` in the package is one ``<pre>`` and nothing else,
    and the instances here are one per class that has one, found in the
    source so a new one cannot land untested."""
    import ast

    from rietx.schemas.common import Diagnostic, Provenance
    from rietx.schemas.indexing import CellCandidate, IndexingResult, PeakList
    owners = set()
    for path in Path(rx.__file__).parent.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "_repr_html_" in source:
            owners |= {node.name for node in ast.walk(ast.parse(source))
                       if isinstance(node, ast.ClassDef)
                       and any(getattr(f, "name", None) == "_repr_html_" for f in node.body)}
    d = Diagnostic(level="warning", code="BOUND_HIT", message="a refined to its upper bound",
                   where=["phases.0.cell.a"], suggestion="check the tie")
    cand = CellCandidate(cell=(5.43, 5.43, 5.43, 90, 90, 90), cell_esd=(1e-4,) * 3 + (0,) * 3,
                         system="cubic", diagnostics=[d])
    build = {
        "result": lambda: fap["result"].model_copy(update={"diagnostics": [d]}),
        "peaks": lambda: PeakList.from_positions([21.07, 26.22], 1.5406).model_copy(
            update={"diagnostics": [d]}),
        "indexing": lambda: IndexingResult(
            candidates=[cand], diagnostics=[d], engines_run=["svd"], systems_searched=["cubic"],
            provenance=Provenance(package_version="test", created_utc="2026-10-07T00:00:00Z")),
    }
    assert owners == {"RefinementResult", "PeakList", "IndexingResult"}, (
        "a new _repr_html_: give it an instance here")
    page = build[name]()._repr_html_()
    assert page.startswith("<pre>") and page.endswith("</pre>") and page.count("<pre>") == 1
    for tag in ("<details", "<summary", "<table", "<p>"):
        assert tag not in page
    assert "means: " in page


@pytest.mark.parametrize("name", ["ref", "microstructure", "trajectory", "moment"])
def test_a_view_a_notebook_form_would_not_add_to_shows_its_text(fap, name):
    """WP-2037: where one ``<pre>`` of the text would be all a notebook form
    carried, the object has none, and a notebook shows its text as it is."""
    formatters = pytest.importorskip("IPython.core.formatters")
    from rietx.schemas.results import MicrostructureTerm, PhaseMicrostructure
    from rietx.schemas.sequential import MagneticTrajectory, Trajectory
    obj = {
        "ref": lambda: fap["ref"],
        "microstructure": lambda: PhaseMicrostructure(
            phase_index=0, scherrer_k=0.9, terms=[MicrostructureTerm(
                path="phases.0.lor_size", kind="size", coefficient=0.27, value=298.9, esd=2.2)]),
        "trajectory": lambda: Trajectory(path="phases.0.cell.a", x=[300.0], value=[4.1566],
                                         stderr=[4.3e-6], labels=["300 K"], positions=[0]),
        "moment": lambda: MagneticTrajectory(
            path="magnetic.Cr1", x=[10.0], value=[2.1], stderr=[0.1], labels=["10 K"],
            supported=[True], measured=[True], status=["converged"]),
    }[name]()
    bundle, _ = formatters.DisplayFormatter().format(obj)
    assert bundle == {"text/plain": str(obj)}


def test_an_indexing_result_prints_its_candidates_and_verdict():
    from rietx.schemas.common import Provenance
    from rietx.schemas.indexing import CellCandidate, IndexingResult
    cand = CellCandidate(cell=(5.43, 5.43, 5.43, 90, 90, 90), cell_esd=(1e-4,) * 3 + (0,) * 3,
                         system="cubic")
    res = IndexingResult(candidates=[cand], engines_run=["svd"], systems_searched=["cubic"],
                         provenance=Provenance(package_version="test",
                                               created_utc="2026-10-07T00:00:00Z"))
    text = str(res)
    assert text.splitlines()[0].startswith("engines: svd   systems: cubic")
    assert "5.43000 5.43000 5.43000 Å" in text and "NO CELL" in text
    assert _notebook_text(res) == text, "no diagnostic, so nothing to add"


def test_a_peak_list_prints_one_row_per_peak():
    """The generic tree spent fourteen lines a peak (WP-1545's notebook 03)."""
    from rietx.schemas.indexing import PeakList
    peaks = PeakList.from_positions([21.07, 26.22, 27.22], 1.5406)
    text = str(peaks)
    lines = text.splitlines()
    assert lines[0].startswith("PeakList: 3 peaks, 3 usable")
    assert len(lines) == 2 + 3 and "26.2200" in lines[3]
    assert _notebook_text(peaks) == text, "no diagnostic, so nothing to add"


def test_a_microstructure_block_prints_one_row_a_term_and_its_verdict():
    """The generic tree spent five lines on a term and printed a size as an
    unrounded float (WP-1545's notebook 04).  ``None`` in the tail is printed,
    since there it is the field's answer."""
    from rietx.schemas.results import MicrostructureTerm, PhaseMicrostructure
    block = PhaseMicrostructure(
        phase_index=0, phase_name="CeO2", wavelength=1.5444274, scherrer_k=0.9,
        terms=[MicrostructureTerm(path="phases.0.lor_size", kind="size", coefficient=0.27,
                                  value=298.93723, esd=2.1510486),
               MicrostructureTerm(path="phases.0.gauss_size", kind="size", coefficient=0.0,
                                  unavailable="at_zero"),
               MicrostructureTerm(path="phases.0.lor_strain", kind="strain", coefficient=0.11,
                                  value=0.00096550893, esd=4.2017779e-05)],
        size_agreement=7.9111007)
    lines = str(block).splitlines()
    assert lines[0] == ("PhaseMicrostructure: CeO2 (phase 0), scherrer_k 0.9, "
                        "wavelength 1.54443 Å")
    assert lines[1].split() == ["path", "value", "unavailable"]
    assert lines[2].split() == ["phases.0.lor_size", "298.9(22)", "Å"]
    assert lines[3].split() == ["phases.0.gauss_size", "at_zero"]
    assert lines[4].split() == ["phases.0.lor_strain", "0.000966(42)"]
    assert lines[5:] == ["  size_agreement: 7.91   strain_agreement: None",
                         "  separable: None   size_strain_collinearity: None"]


def test_a_trajectory_prints_one_row_a_point_with_its_esd():
    """The generic tree printed the values and the esds as two lists, so a
    reader paired them by counting (WP-1545's notebook 05).  The x column is
    headed by the series' own label, and a point with no esd prints its value
    alone.  A moment trajectory keeps its own view, verdicts included."""
    from rietx.schemas.sequential import MagneticTrajectory, Trajectory
    traj = Trajectory(path="phases.0.cell.a", x=[300.0, 400.0], x_label="T (K)",
                      value=[4.15660247525093, 4.15868088118438],
                      stderr=[4.3e-6, None], labels=["300 K", "400 K"], positions=[0, 1])
    lines = str(traj).splitlines()
    assert lines[0] == "Trajectory: phases.0.cell.a, 2 point(s)"
    assert lines[1].split() == ["label", "T", "(K)", "value"]
    assert lines[2].split() == ["300", "K", "300", "4.1566025(43)"]
    assert lines[3].split() == ["400", "K", "400", "4.1586809"]
    moment = MagneticTrajectory(path="magnetic.Cr1", x=[10.0], value=[2.1], stderr=[0.1],
                                labels=["10 K"], supported=[True], measured=[True],
                                status=["converged"])
    assert str(moment).startswith("MagneticTrajectory")


def test_a_diagnostic_prints_rustc_s_form_and_a_notebook_adds_what_it_means():
    """The text form is rustc's (WP-1985).  The notebook form adds the code's
    explanation as ``means:`` after ``help:`` (WP-2037), and ``on:`` sits
    under the headline in both."""
    from rietx._display import diagnostic_lines
    from rietx.help import explain
    from rietx.schemas.common import Diagnostic
    d = Diagnostic(level="warning", code="BOUND_HIT", message="a refined to its upper bound",
                   where=["phases.0.cell.a"], suggestion="check the tie")
    assert str(d).splitlines() == ["warning[BOUND_HIT]: a refined to its upper bound",
                                   "  at: phases.0.cell.a", "  help: check the tie"]
    text = diagnostic_lines(d, "  ", on="candidate cubic P")
    assert text == ["  warning[BOUND_HIT]: a refined to its upper bound",
                    "    on: candidate cubic P", "    at: phases.0.cell.a",
                    "    help: check the tie"]
    notebook = diagnostic_lines(d, "  ", on="candidate cubic P", notebook=True)
    assert notebook[:4] == text and notebook[4].startswith("    means: ")
    assert _flat(" ".join(notebook[4:])) == "means: " + _flat(explain("BOUND_HIT").description)
    unknown = Diagnostic(level="info", code="NOT_A_CODE_HERE", message="from another version")
    assert unknown.explanation is None
    assert diagnostic_lines(unknown, notebook=True) == diagnostic_lines(unknown)


def test_pre_fit_ticks_are_where_the_fit_puts_its_own(fap):
    """One answer to where a tick goes: drawn from the fitted refinement, the
    pre-fit rows are the result's own ticks over the same range."""
    import numpy as np

    from rietx.viz.plots import _starting_model
    drawn, _, _ = _starting_model(fap["ref"], fap["data"])
    (name, own), = fap["result"].ticks.items()
    lo, hi = fap["result"].two_theta[0], fap["result"].two_theta[-1]
    pos = np.asarray(drawn[name])
    pos = pos[(pos >= lo) & (pos <= hi)]
    own = np.asarray(own)
    own = own[(own >= lo) & (own <= hi)]
    assert pos.size == own.size and np.allclose(pos, own, atol=1e-5)


def test_pre_fit_ticks_draw_one_row_per_phase_and_need_a_linear_axis(fap):
    pytest.importorskip("matplotlib")
    ref = rx.Refinement(fap["structure"], fap["instrument"])
    fig = fap["data"].plot(model=ref, two_theta_range=(25, 40), dpi=72)
    texts = [t.get_text() for t in fig.axes[0].texts]
    assert texts == ["observed", "fluorapatite"]
    with pytest.raises(ValueError, match="linear intensity axis"):
        fap["data"].plot(model=ref, y_scale="log")
    import matplotlib.pyplot as plt
    plt.close("all")


def test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone():
    """Measured before WP-1544: no rietx figure showed an image in a kernel,
    and one plot call left the session on Agg, so a plain ``plt.show()``
    afterwards warned and drew nothing. With Agg no longer forced, a bare
    call showed twice and later figures leaked into the next ``plt.show()``."""
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    cells = [f"import rietx as rx\ndata = rx.read_pattern({str(DATA / 'FAP.XRA')!r})",
             "data.plot()",
             "data.plot();",
             "fig = data.plot()",
             "import matplotlib, matplotlib.pyplot as plt\n"
             "plt.plot([1, 2]); plt.show()\nprint(matplotlib.get_backend())"]
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(c) for c in cells])
    # the suite pins MPLBACKEND=Agg (conftest), and a kernel honours it as a
    # choice, so this kernel starts without it, as a notebook's does
    env = {k: v for k, v in os.environ.items() if k != "MPLBACKEND"}
    nbclient.NotebookClient(nb, timeout=120, kernel_name="python3").execute(env=env)

    def images(cell):
        return sum("image/png" in o.get("data", {}) for o in cell.outputs)
    assert [images(c) for c in nb.cells[1:]] == [1, 0, 0, 1]
    backend = "".join(o.get("text", "") for o in nb.cells[-1].outputs)
    assert "inline" in backend

    # the notebook encoding reached the rietx figure (132 320 base64 chars at
    # the figure's own 300 dpi, 34 392 encoded), and only the rietx figure
    rietx_out = next(o for o in nb.cells[1].outputs if "image/png" in o.get("data", {}))
    assert len(rietx_out["data"]["image/png"]) < 60_000
    assert rietx_out["metadata"]["image/png"]["width"] < 800
    plain_out = next(o for o in nb.cells[-1].outputs if "image/png" in o.get("data", {}))
    assert "width" not in plain_out.get("metadata", {}).get("image/png", {})
    # beside the PNG, the light and dark pair a frontend's theme picks from
    # (WP-1970), and only for the rietx figure
    assert rietx_out["data"]["text/html"].count("<img ") == 2
    assert "text/html" not in plain_out["data"]


def test_a_notebook_figure_is_encoded_for_a_screen_and_files_are_not(fap, tmp_path):
    """Twice a 100-dpi screen, a 256-colour palette, drawn at half its pixel
    width; ``savefig`` still writes the figure's own dpi in full colour."""
    pytest.importorskip("matplotlib")
    import io

    from PIL import Image

    fig = fap["data"].plot()
    data, md = fig._repr_png_()
    image = Image.open(io.BytesIO(data))
    assert image.mode == "P"
    # the width alone, or a column narrower than the figure squashes it (WP-1957)
    assert md == {"width": image.size[0] // 2}
    fig.savefig(tmp_path / "file.png")
    saved = Image.open(tmp_path / "file.png")
    assert saved.mode == "RGBA"
    assert saved.size[0] == round(fig.get_figwidth() * fig.dpi) and fig.dpi == 300
    import matplotlib.pyplot as plt
    plt.close("all")


@pytest.mark.parametrize("name", ["data", "instrument", "structure", "result", "ref"])
def test_ipython_text_plain_stays_short(fap, name):
    """What a notebook *stores*: text/plain is saved beside any HTML, so a
    long repr fills the .ipynb even where the HTML is what shows."""
    formatters = pytest.importorskip("IPython.core.formatters")
    bundle, _ = formatters.DisplayFormatter().format(fap[name])
    assert len(bundle["text/plain"]) < 10_000
    assert "two_theta=" not in bundle["text/plain"], "the str view, not pydantic's repr"
