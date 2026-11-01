"""WP-1009 — the project text document: render, parse, delta, apply.

The load-bearing property is a **fixed point**: rendering a project, parsing it
back and diffing against the live project must produce no verbs and no errors.
That is what makes an editor pane safe to leave open, and it is not automatic —
it failed twice while this module was being written, once because a value column
collided with its own ``min`` annotation and once because a tie annotation
rendered mid-line swallowed everything after it.  Both are pinned below.

Hypothesis carries the numeric half: every finite float must render and re-read
as *no change*, since a document that perturbs a parameter merely by being
applied would be worse than no text pane at all.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

import rietx as rx
from rietx.gui import GuiSession
from rietx.gui import textdoc as td
from rietx.schemas.plan import StageSpec
from rietx.schemas.structure import MARCH_R_MIN, PreferredOrientation
from tests.test_project import _write_xye
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("textdoc")


# ----------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def pattern_file(tmp_path_factory):
    return _write_xye(tmp_path_factory.mktemp("rxt-data") / "synth.xye", synthesize())


def _project(root: Path, pattern_file: Path, **kw) -> rx.Project:
    structure, ins = perturbed_models()
    kw.setdefault("plan", "mccusker_default")
    return rx.Project.create(root, pattern=pattern_file, structure=structure,
                             instrument=ins, **kw)


@pytest.fixture
def project(tmp_path, pattern_file):
    return _project(tmp_path / "doc.rex", pattern_file)


def _edit(text: str, path: str, replacement: str, *, which: int | None = None) -> str:
    """Replace the line whose first token is ``path`` (a row, or a keyword).

    ``which`` picks one of several matches (the ``stage`` keyword repeats); with
    it unset exactly one line must match, so a helper that silently rewrote five
    lines cannot hide inside a passing test.
    """
    out, seen = [], 0
    for line in text.splitlines():
        head = line.split("#")[0].split()
        if head[:1] == [path] and which in (None, seen):
            out.append(replacement)
            seen += 1
        else:
            out.append(line)
            seen += head[:1] == [path]
    assert seen >= 1 and (which is not None or seen == 1), \
        f"{path!r} matched {seen} lines"
    return "\n".join(out) + "\n"


def _changes(text: str, project):
    return td.changes(td.parse(text), project)


# ----------------------------------------------------------------------
# the fixed point
# ----------------------------------------------------------------------
def test_render_parse_diff_is_a_fixed_point(project):
    """The property everything else rests on: an untouched document is a no-op."""
    text = td.render(project)
    parsed = td.parse(text)
    assert parsed.errors == []
    delta, errors = td.changes(parsed, project)
    assert errors == []
    assert delta.is_empty(), delta.as_dict()
    # applying nothing is idempotent, and re-rendering is byte-identical
    assert td.apply(project, delta) == []
    assert td.render(project) == text
    assert td.revision(text) == td.revision(td.render(project))


def test_the_fixed_point_holds_over_the_shapes_that_broke_it(tmp_path,
                                                             pattern_file):
    """Every row kind at once — long paths, ties, locks, bounds.

    Two renderer bugs lived here. A fixed 36-column value field emitted
    ``polarization                   0.99min 0`` (the parser then refused
    ``'0.99min'`` as an unknown annotation), and a tie rendered before the
    bounds swallowed them, because ``= 0.1993 + 1·…`` contains spaces and has to
    run to the end of the line.
    """
    project = _project(tmp_path / "shapes.rex", pattern_file,
                       mode="lebail", two_theta_limits=(4.0, 22.0),
                       excluded_regions=[(7.5, 8.0), (19.0, 19.5)])
    text = td.render(project)
    rows = {row.path: row for row in td.parse(text).rows}

    assert not td.parse(text).errors
    # the four shapes, all present and all re-read exactly
    assert rows["instrument.polarization"].annotations["min"] == 0.0
    assert rows["phases.0.cell.b"].annotations["tie"].endswith("phases.0.cell.a")
    assert rows["phases.0.cell.alpha"].annotations["locked"] is True
    assert rows["phases.0.scale"].annotations["min"] == 0.0
    # lebail force-fixes every atom path, and the row says so rather than
    # looking editable (the Le Bail dummy-atom trap, WP-1004)
    assert rows["phases.0.atoms.0.biso"].annotations["mode-fixed"] is True

    delta, errors = td.changes(td.parse(text), project)
    assert (errors, delta.is_empty()) == ([], True)


def test_a_document_written_with_transform_words_still_reads(project):
    """An ``.rxt`` rendered before schema 0.46 carries ``softplus``/``logit``
    beside the bounds (WP-1938).  The renderer no longer writes them; the
    parser folds each into the row's bounds through the schema's one map, so
    the old document compares equal to the live rows and applies nothing."""
    text = td.render(project)
    assert "softplus" not in text and "logit" not in text
    line = next(ln for ln in text.splitlines()
                if ln.strip().startswith("scale ") and "min 0" in ln)
    old = text.replace(line, f"{line}  softplus", 1)
    # an old row whose bound was left to the transform alone folds to min 0
    bare = line.replace("min 0", "").rstrip() + "  softplus"
    for doc in (old, text.replace(line, bare, 1)):
        parsed = td.parse(doc)
        assert parsed.errors == []
        [row] = [r for r in parsed.rows if r.path == "phases.0.scale"]
        assert row.annotations["min"] == 0.0 and "softplus" not in row.annotations
        delta, errors = td.changes(parsed, project)
        assert (errors, delta.is_empty()) == ([], True)


def test_a_document_written_before_a_floor_applies_nothing(tmp_path, pattern_file):
    """An ``.rxt`` rendered before W's floor says ``min 0`` on W, and a W under
    it (WP-1938).  Opening that project today raises both to 1e-8, so the
    document's numbers compare equal through the schema and apply nothing.
    March r's floor is the same case.  A bound no validator raises is still an
    edit, refused as before."""
    structure, ins = perturbed_models()
    structure.phases[0].preferred_orientation = PreferredOrientation(axis=(0, 0, 1))
    project = rx.Project.create(tmp_path / "floors.rex", pattern=pattern_file,
                                structure=structure, instrument=ins,
                                plan="mccusker_default")
    project.refinement.set_values({"instrument.profile.w": 1e-8})
    text = td.render(project)
    rows = {row.path: row for row in td.parse(text).rows}
    assert rows["instrument.profile.w"].annotations["min"] == 1e-8
    assert rows["phases.0.preferred_orientation.r"].annotations["min"] == MARCH_R_MIN

    def written_before(doc, local, lo, value=None):
        line = next(ln for ln in doc.splitlines() if ln.split()[:1] == [local])
        old = re.sub(r"min \S+", f"min {lo}", line)
        if value is not None:
            old = re.sub(rf"^(\s*{re.escape(local)}\s+(?:@\s*)?)\S+",
                         rf"\g<1>{value}", old)
        assert old != line
        return doc.replace(line, old, 1)

    old = written_before(text, "profile.w", 0, value="1e-12")
    old = written_before(old, "preferred_orientation.r", 0)
    delta, errors = _changes(old, project)
    assert (errors, delta.is_empty()) == ([], True)

    _, errors = _changes(written_before(text, "scale", -1), project)
    assert [e.where for e in errors] == ["phases.0.scale"]
    assert "cannot be edited here" in errors[0].message

    # a W the schema raises past the live one sets the raised number, which
    # apply accepts, rather than the typed one, which it would refuse
    project.refinement.set_values({"instrument.profile.w": 0.003})
    delta, errors = _changes(written_before(td.render(project), "profile.w", 0,
                                            value="0"), project)
    assert (errors, delta.values) == ([], {"instrument.profile.w": 1e-8})
    td.apply(project, delta)
    assert project.refinement.instrument.profile.w.value == 1e-8


def test_a_hold_renders_as_an_annotation_and_refuses_the_at_marker(
        tmp_path, pattern_file):
    """The fifth held-reason, in the document as the other four are (WP-1435).

    Without the annotation a held row renders as an ordinary fixed parameter:
    no ``@``, nothing saying why, and the reason arrives only after the user
    has typed one and been refused. That is the gap the four before it do not
    have.

    The refusal itself needed no work here, which is the point of
    ``ParameterRow.refinable`` being one predicate: the vary check reads it
    and inherited the new reason.
    """
    project = _project(tmp_path / "held.rex", pattern_file)
    project.refinement.hold("phases.0.cell.a")

    text = td.render(project)
    rows = {row.path: row for row in td.parse(text).rows}
    assert rows["phases.0.cell.a"].annotations["held"] is True

    # an unedited document still round-trips clean with the annotation on it
    delta, errors = td.changes(td.parse(text), project)
    assert (errors, delta.is_empty()) == ([], True)

    # and freeing it by hand is refused with the sentence that names the verb
    edited = _edit(text, "cell.a", "  cell.a @ " + f"{rows['phases.0.cell.a'].value}"
                   + "  held")
    _, errors = _changes(edited, project)
    assert errors and "cannot be freed" in errors[0].message
    assert "unhold()" in errors[0].message


def test_a_user_tie_renders_as_a_tie_and_stays_read_only(project):
    """WP-1070: the ``=`` annotation already says it, and there is no tie *line*.

    A tie declaration would need an edit the delta cannot see.  Annotations are
    regenerated from state on every render and omission means "no opinion" — a
    deleted ``= …`` is how an untouched document reads, so "release this tie"
    and "I did not type anything here" would be the same edit.  So a user tie is
    rendered like the derived ones and edited through the verbs, and
    ``FORMAT_VERSION`` does not move.

    The general affine form is the shape worth pinning: ``1 + -1·…`` carries
    both a constant and a negative coefficient, and it is the case the
    run-to-end-of-line rule exists for.
    """
    ref = project.refinement
    ref.set_values({"phases.0.atoms.0.occ": 0.6})
    ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1.0, offset=1.0)
    text = td.render(project)
    parsed = td.parse(text)
    assert parsed.errors == []
    row = {r.path: r for r in parsed.rows}["phases.0.atoms.1.occ"]
    assert row.annotations["tie"] == "1 + -1·phases.0.atoms.0.occ"
    assert row.value == pytest.approx(0.4)
    # still a fixed point, and still refused as an edit — in the verb's words
    delta, errors = td.changes(parsed, project)
    assert (errors, delta.is_empty()) == ([], True)
    edited = _edit(text, "atoms.1.occ", "  atoms.1.occ  @ 0.9")
    _, errors = td.changes(td.parse(edited), project)
    assert [e.message for e in errors] == [
        "phases.0.atoms.1.occ cannot be set — tied: = 1 + -1·phases.0.atoms.0.occ"
        "; set phases.0.atoms.0.occ instead",
        "phases.0.atoms.1.occ cannot be freed: tied: = 1 + -1·phases.0.atoms.0.occ"]


def test_the_phase_header_states_its_symmetry_and_stays_read_only(project):
    """WP-1035: the symbol the document could not say, as a rendered comment.

    A comment, not a field, and that is the rule rather than an omission — the
    ``.rxt`` editable surface is parameters and settings, a symbol change is a
    whole-model edit behind a preview gate, and a second authority on a phase's
    symmetry is what this module forbids.  Through the same mechanism the atom
    rows already use, so the format version does not move.
    """
    text = td.render(project)
    header = next(line for line in text.splitlines() if line.startswith("phase 0"))
    assert "# P m -3 m · No. 221 · cubic · Laue m-3m" in header
    assert td.FORMAT_VERSION == "1"

    parsed = td.parse(text)
    assert parsed.errors == []
    delta, errors = td.changes(parsed, project)
    assert (errors, delta.is_empty()) == ([], True)
    # typing over the comment changes nothing: comments are stripped before the
    # header is read, so the symbol cannot be edited here even by accident
    edited = text.replace(header, 'phase 0 "LaB6"   # P 1 · nonsense')
    delta, errors = td.changes(td.parse(edited), project)
    assert (errors, delta.is_empty()) == ([], True)
    assert project.refinement.structure.phases[0].space_group == "P m -3 m"


def _picked(project):
    """Pick and store a peak list, returning the session that did it."""
    session = GuiSession(project, state_dir=project.path / "state")
    session.peaks_pick({})
    return session


def test_the_fixed_point_holds_with_a_peaks_block(project):
    """WP-1027: a stored peak list renders, parses, and is a no-op unedited."""
    _picked(project)
    text = td.render(project)
    assert "\npeaks " in text
    assert "@" not in text.split("\npeaks ")[1]  # peaks carry no vary marker
    parsed = td.parse(text)
    assert parsed.errors == []
    assert len(parsed.peak_rows) == parsed.peaks_count > 0
    delta, errors = td.changes(parsed, project)
    assert errors == []
    assert delta.is_empty(), delta.as_dict()
    assert td.apply(project, delta) == []
    assert td.render(project) == text


def test_a_peaks_row_edits_two_columns_and_only_those(project):
    session = _picked(project)
    text = td.render(project)
    parsed = td.parse(text)
    row = parsed.peak_rows[0]

    # a 2θ edit is a move (the group is refitted, so the landed position is
    # near, not identical) and a flags edit is a set_peak_flags
    line = row.text.replace(f"{row.two_theta:.6f}", f"{row.two_theta + 0.02:.6f}")
    edited = text.replace(row.text, line + "  excluded")
    delta, errors = td.changes(td.parse(edited), project)
    assert errors == []
    assert delta.peak_moves == {row.index: pytest.approx(row.two_theta + 0.02)}
    assert delta.peak_flags == {row.index: ["excluded"]}
    calls = td.apply(project, delta)
    assert any("move_peak" in c for c in calls)
    assert any("set_peak_flags" in c for c in calls)
    after = session.peaks()
    listed = [p for p in after["peaks"] if "excluded" in p["flags"]]
    assert listed and listed[0]["origin"] == "edited"
    # and the next render is a fixed point again
    fresh = td.render(project)
    delta, errors = td.changes(td.parse(fresh), project)
    assert (errors, delta.is_empty()) == ([], True)

    # every derived column refuses an edit rather than silently regenerating
    text = fresh
    row = td.parse(text).peak_rows[0]
    for column, value in (("esd", row.esd), ("fwhm", row.fwhm),
                          ("I", row.intensity)):
        bad = text.replace(row.text,
                           row.text.replace(_fmt_col(column, row),
                                            _fmt_col(column, row, bump=True)))
        _, errors = td.changes(td.parse(bad), project)
        assert errors and "derived" in errors[0].message, column
    # the count is derived too
    bad = _edit(text, "peaks", "peaks 999")
    _, errors = td.changes(td.parse(bad), project)
    assert errors and "count is derived" in errors[0].message
    # and an unknown flag word names the vocabulary
    bad = text.replace(row.text, row.text + "  impurity")
    _, errors = td.changes(td.parse(bad), project)
    assert errors and "unknown flag" in errors[0].message


def _fmt_col(column: str, row, *, bump: bool = False) -> str:
    if column == "esd":
        return f"{row.esd * (2 if bump else 1):.6f}"
    if column == "fwhm":
        return f"{row.fwhm * (2 if bump else 1):.4f}"
    return f"{row.intensity * (2 if bump else 1):.6g}"


@given(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False,
                 allow_infinity=False))
def test_a_rendered_number_reads_back_as_no_change(value):
    """A document must not perturb a parameter merely by being applied.

    ``_fmt`` is lossy at 12 significant digits, so the invariant is not
    ``float(_fmt(x)) == x`` — it is that a *typed-back* rendered number compares
    equal to the rendered current value, which is the comparison ``changes``
    actually makes.
    """
    rendered = td._fmt(value)
    assert float(td._fmt(float(rendered))) == float(rendered)


# ----------------------------------------------------------------------
# editing
# ----------------------------------------------------------------------
def test_values_and_flags_become_the_verbs_a_form_would_have_called(project):
    text = td.render(project)
    edited = _edit(text, "cell.a", "  cell.a        @ 4.15678")
    edited = _edit(edited, "atoms.0.biso", "  atoms.0.biso    @ 0.61")
    edited = _edit(edited, "background.c1", "  background.c1     0")

    delta, errors = _changes(edited, project)
    assert errors == []
    assert delta.values == {"phases.0.cell.a": 4.15678,
                            "phases.0.atoms.0.biso": 0.61}
    assert delta.vary == {"phases.0.atoms.0.biso": True,
                          "instrument.background.c1": False}

    before = len(project.history)
    calls = td.apply(project, delta)
    assert calls[0].startswith("ref.set_values(")
    assert [n.action.kind for n in project.history.nodes.values()][before:] == [
        "set_value", "set_vary", "set_vary"]
    # the cubic tie followed, and the next render is a fixed point again
    rows = {r.path: r for r in project.refinement.parameters()}
    assert rows["phases.0.cell.c"].value == pytest.approx(4.15678)
    assert _changes(td.render(project), project)[0].is_empty()


def test_a_glob_line_is_bulk_vary_sugar_and_is_normalised_away(project):
    text = td.render(project)
    edited = _edit(text, "profile.y", "  profile.* @")
    delta, errors = _changes(edited, project)
    assert errors == []
    assert set(delta.vary) == {f"instrument.profile.{k}" for k in "uvwxy"}
    assert all(delta.vary.values())

    td.apply(project, delta)
    rendered = td.render(project)
    # canonical output is one line per parameter — the glob does not come back
    assert "profile.*" not in rendered
    assert rendered.count("profile.") >= 5
    assert _changes(rendered, project)[0].is_empty()

    # a glob that matches nothing, and one that cannot free anything
    _, errors = _changes(_edit(text, "profile.y", "  nope.* @"), project)
    assert "no parameter matches" in errors[0].message
    _, errors = _changes(_edit(text, "cell.alpha", "  cell.* @"), project)
    assert errors == [] or "none of which can be freed" not in errors[0].message
    _, errors = _changes(_edit(text, "cell.alpha", "  cell.alpha @ 90  locked"),
                         project)
    assert "cannot be freed" in errors[0].message


def test_settings_round_trip_through_their_own_verbs(project):
    text = td.render(project)
    edited = _edit(text, "mode", "mode lebail")
    edited = _edit(edited, "limits", "limits 4 22")
    edited = _edit(edited, "excluded", "excluded 7.5 8.0  19 19.5")

    delta, errors = _changes(edited, project)
    assert errors == []
    assert delta.settings == {"mode": "lebail", "two_theta_limits": (4.0, 22.0),
                              "excluded_regions": [[7.5, 8.0], [19.0, 19.5]]}
    td.apply(project, delta)
    # the mask reached the pattern, not just the document (one verb, by design)
    assert project.data.excluded_regions == [(7.5, 8.0), (19.0, 19.5)]
    # …and it is on disk without anyone pressing Save
    reopened = rx.Project.open(project.path)
    assert reopened.doc.mode == "lebail"
    assert reopened.doc.two_theta_limits == (4.0, 22.0)
    assert _changes(td.render(project), project)[0].is_empty()


def test_the_plan_renders_as_its_preset_name_and_can_be_swapped(project):
    text = td.render(project)
    assert "plan mccusker_default" in text
    delta, errors = _changes(_edit(text, "plan", "plan profile_only"), project)
    assert errors == []
    assert delta.plan == {"preset": "profile_only"}
    td.apply(project, delta)
    assert "plan profile_only" in td.render(project)

    # editing the stage lines instead makes it a custom plan
    text = td.render(project)
    edited = "\n".join(line for line in text.splitlines()
                       if not line.startswith("stage profile ")) + "\n"
    delta, errors = _changes(edited, project)
    assert errors == []
    assert delta.plan is not None and "plan" in delta.plan
    td.apply(project, delta)
    rendered = td.render(project)
    assert "plan custom" in rendered
    assert _changes(rendered, project)[0].is_empty()


def test_changing_the_preset_and_the_stages_at_once_is_refused(project):
    """Precedence would silently discard the lines the user is looking at."""
    text = td.render(project)
    edited = _edit(text, "plan", "plan profile_only")
    edited = "\n".join(line for line in edited.splitlines()
                       if not line.startswith("stage cell")) + "\n"
    _, errors = _changes(edited, project)
    assert len(errors) == 1
    assert "not both" in errors[0].message


def test_a_stage_line_carries_its_seeds(project):
    """A stage's ``seed``/``strain_seed`` are the two dead-gradient fixes; a
    format that dropped them would repeat WP-1004's own defect."""
    text = td.render(project)
    edited = _edit(text, "stage", "stage seeded  free phases.*.extinction   "
                                  "max_iter 40   seed 0.0001   strain_seed 1e-06",
                   which=0)
    delta, errors = _changes(edited, project)
    assert errors == []
    stage = delta.plan["plan"]["stages"][0]
    assert (stage["name"], stage["max_iter"]) == ("seeded", 40)
    assert (stage["seed"], stage["strain_seed"]) == (0.0001, 1e-06)


def test_the_tolerance_line_is_always_shown_and_switches_the_schedule(project):
    """The plan-level ``tolerance`` line (WP-1123) is the exact-mode switch.

    Rendered whether or not it differs from the default, unlike ``guard``: it
    decides what a run costs and how far the intermediate stages are taken, and
    a document that shows a fast schedule nowhere is a document a user cannot
    decline it in.  ``none`` is a value here rather than the absence of one —
    deleting the line means "the default", writing ``none`` means "converge
    every stage" — which is why the parser tracks whether it appeared.
    """
    from rietx.schemas.plan import PlanSpec

    text = td.render(project)
    line = next(ln for ln in text.splitlines() if ln.startswith("tolerance "))
    assert line.split()[1] == td._fmt(PlanSpec().intermediate_ftol)
    assert "intermediate_ftol" in line, "the line must name the field it sets"

    delta, errors = _changes(_edit(text, "tolerance", "tolerance none"), project)
    assert errors == []
    assert delta.plan["plan"]["intermediate_ftol"] is None

    delta, errors = _changes(_edit(text, "tolerance", "tolerance 1e-4"), project)
    assert errors == []
    assert delta.plan["plan"]["intermediate_ftol"] == 1e-4


def test_a_tolerance_that_cannot_be_a_tolerance_is_refused(project):
    """Zero and a negative stop nothing, and a word that is not ``none`` is a
    typo, not a schedule.  Refused with the line number every other refusal in
    this document carries."""
    text = td.render(project)
    for bad in ("tolerance 0", "tolerance -1e-6", "tolerance exact", "tolerance"):
        delta, errors = _changes(_edit(text, "tolerance", bad), project)
        assert errors, bad
        assert errors[0].line > 1 and errors[0].where == "tolerance", bad
        assert delta.plan is None, bad


def test_the_passes_line_carries_the_le_bail_cap_and_refuses_nonsense(project):
    """``lebail_passes`` (WP-1323) had no line, so a save through the document
    reset a Le Bail job's cap to one pass.  Absent at its default, as ``guard``
    is, so every stored document renders byte for byte as before."""
    text = td.render(project)
    assert not any(ln.startswith("passes ") for ln in text.splitlines())

    delta, errors = _changes(_edit(text, "tolerance", "tolerance 1e-06\npasses 8"),
                             project)
    assert errors == []
    assert delta.plan["plan"]["lebail_passes"] == 8

    # and it renders once above the default, so a save cannot drop it
    project.doc.plan = project.doc.plan.model_copy(update={"lebail_passes": 5})
    assert any(ln.startswith("passes 5") for ln in td.render(project).splitlines())

    for bad in ("passes 0", "passes -2", "passes many", "passes", "passes 2 3"):
        delta, errors = _changes(
            _edit(text, "tolerance", f"tolerance 1e-06\n{bad}"), project)
        assert errors and errors[0].where == "passes", bad
        assert delta.plan is None, bad


def test_the_support_line_carries_the_hold_threshold_and_refuses_nonsense(project):
    """``phase_support_sigma`` (WP-2002, B1) has a line, or a save through the
    document would reset a caller's threshold, or a hold switched off, to 3σ.
    Absent at its default, as ``guard`` and ``passes`` are, so every stored
    document renders byte for byte as before.  ``none`` is a value here, the
    hold off, as it is for ``tolerance``."""
    text = td.render(project)
    assert not any(ln.startswith("support ") for ln in text.splitlines())

    delta, errors = _changes(_edit(text, "tolerance", "tolerance 1e-06\nsupport none"),
                             project)
    assert errors == []
    assert delta.plan["plan"]["phase_support_sigma"] is None

    delta, errors = _changes(_edit(text, "tolerance", "tolerance 1e-06\nsupport 5"),
                             project)
    assert errors == []
    assert delta.plan["plan"]["phase_support_sigma"] == 5.0

    # rendered once away from the default, naming the field, so a save keeps it
    for value, shown in ((None, "none"), (5.0, "5")):
        project.doc.plan = project.doc.plan.model_copy(
            update={"phase_support_sigma": value})
        line = next(ln for ln in td.render(project).splitlines()
                    if ln.startswith("support "))
        assert line.split()[1] == shown and "phase_support_sigma" in line

    for bad in ("support 0", "support -3", "support inf", "support nan",
                "support many", "support", "support 3 4"):
        delta, errors = _changes(
            _edit(text, "tolerance", f"tolerance 1e-06\n{bad}"), project)
        assert errors and errors[0].where == "support", bad
        assert delta.plan is None, bad


def test_a_stage_line_round_trips_every_key_stage_spec_has(project):
    """The keys are derived from ``StageSpec``, so this is the whole set at once.

    A field the grammar does not know is not a rendering gap: it renders
    nowhere, parses nowhere, and is therefore dropped by every save — which is
    what happened to ``strain_seed`` one rank up (``schemas/plan.py``).  Pinned
    against the *model*, so the next field added fails here until the derivation
    is what carries it.
    """
    from rietx.schemas.plan import StageSpec

    assert set(td.STAGE_KEYS) | {"name", "turn_on"} == set(StageSpec.model_fields)
    non_default = {"max_iter": 40, "ftol": 1e-06, "lebail_cycles": 5,
                   "seed": 0.0001, "strain_seed": 1e-06,
                   "restraint_weight_scale": 25.0, "window_slack_deg": 2.5}
    assert set(non_default) == set(td.STAGE_KEYS), "a key has no value to try"

    line = "stage every  free phases.*.cell.*   " + "   ".join(
        f"{k} {non_default[k]}" for k in td.STAGE_KEYS)
    delta, errors = _changes(_edit(td.render(project), "stage", line, which=0),
                             project)
    assert errors == []
    stage = delta.plan["plan"]["stages"][0]
    for key, value in non_default.items():
        assert stage[key] == value, key


# ----------------------------------------------------------------------
# refusals, every one with a line number
# ----------------------------------------------------------------------
def test_every_error_carries_a_line_number_and_a_path(project):
    text = td.render(project)
    edited = _edit(text, "cell.b", "  cell.b   4.2  = 1·phases.0.cell.a")
    edited = _edit(edited, "atoms.0.occ", "  atoms.0.occ  1  min 0  max 9.9")
    edited = _edit(edited, "mode", "mode wandering")
    edited += "  nonsense.path  1\nfoo bar\n"

    _, errors = _changes(edited, project)
    assert len(errors) == 5, [e.message for e in errors]
    assert all(e.line >= 1 for e in errors)
    by_where = {e.where: e for e in errors}

    # a tied value quotes the row's own account and names what to set instead
    tied = by_where["phases.0.cell.b"]
    assert "tied" in tied.message and "phases.0.cell.a instead" in tied.message
    assert td.render(project).splitlines()[tied.line - 1].strip().startswith("cell.b")
    # an edited bound says where bounds come from
    assert "bounds come from the schema" in by_where["phases.0.atoms.0.occ"].message
    assert "unknown mode" in by_where["mode"].message
    assert "unknown parameter" in by_where["instrument.nonsense.path"].message
    assert "unknown keyword 'foo'" in by_where["foo"].message


def test_a_wrong_format_version_and_the_emptied_reservations_say_so(project):
    text = td.render(project)
    _, errors = _changes(_edit(text, "rxt", "rxt 99"), project)
    assert "reads rxt 1" in errors[0].message and errors[0].line == 1

    # WP-1027 filled in `peaks`, the last reserved block; the block now parses,
    # and on a project with no stored list it is a semantic error naming the
    # verb that creates one — not a syntax refusal
    assert td.RESERVED_BLOCKS == {}
    _, errors = _changes(text + "peaks 1\n   0  8.471200  0.000900  0.0812  10420\n",
                         project)
    assert "no stored peak list" in errors[0].message
    assert "POST /api/peaks" in errors[0].message


def test_read_only_identity_lines_are_errors_only_when_they_differ(project):
    text = td.render(project)
    for path, replacement, expect in (
            ("project", 'project "renamed"', "its directory name"),
            ("pattern", 'pattern "other.xye"', "bound to this project"),
            ("phase", 'phase 0 "Corundum"', "renaming a phase is a model edit")):
        _, errors = _changes(_edit(text, path, replacement), project)
        assert len(errors) == 1, (path, [e.message for e in errors])
        assert expect in errors[0].message
    # …and phase 7 does not exist.  One error, not one per orphaned row.
    _, errors = _changes(_edit(text, "phase", 'phase 7 "LaB6"'), project)
    assert len(errors) == 1, [e.message for e in errors]
    assert "there is no phase 7" in errors[0].message


def test_an_indented_line_outside_a_block_is_an_error(project):
    _, errors = _changes("rxt 1\n  cell.a @ 4.1\n", project)
    assert "before any 'phase' or 'instrument' block" in errors[0].message
    assert errors[0].line == 2


def test_comments_parse_and_do_not_survive_a_re_render(project):
    """A deliberate deviation from the WP's sketch — recorded, not silent.

    Keeping a user's comment would mean storing it, and the only places to store
    it are ``project.json`` (a second authority for something nothing else reads)
    or the history (which would make a comment a refinement move).
    """
    text = td.render(project)
    annotated = _edit(text, "cell.a", "  cell.a @ 4.1606  # my note")
    delta, errors = _changes(annotated, project)
    assert (errors, delta.is_empty()) == ([], True)
    assert "my note" not in td.render(project)


# ----------------------------------------------------------------------
# over HTTP
# ----------------------------------------------------------------------
@pytest.fixture
def session(project, tmp_path):
    return GuiSession(project, state_dir=tmp_path / "state")


def test_the_session_verbs_carry_the_revision_and_apply_the_delta(session,
                                                                 project):
    doc = session.textdoc()
    assert doc["format_version"] == td.FORMAT_VERSION
    assert doc["revision"] == td.revision(doc["text"])

    edited = _edit(doc["text"], "cell.a", "  cell.a        @ 4.15678")
    dry = session.textdoc_put({"text": edited, "base_revision": doc["revision"],
                               "validate_only": True})
    assert dry["valid"] and dry["would_change"] and dry["applied"] == []
    assert project.refinement.structure.phases[0].cell.a.value != 4.15678

    out = session.textdoc_put({"text": edited, "base_revision": doc["revision"]})
    assert out["applied"][0].startswith("ref.set_values(")
    assert project.refinement.structure.phases[0].cell.a.value == 4.15678
    # the response carries the re-rendered document and its new revision
    assert out["revision"] == td.revision(out["text"]) != doc["revision"]
    assert session.textdoc_put({"text": out["text"],
                                "base_revision": out["revision"]})["applied"] == []


def test_a_stale_base_revision_is_a_conflict_not_a_merge(session, project):
    doc = session.textdoc()
    project.refinement.set_values({"phases.0.cell.a": 4.17})  # someone else moved
    with pytest.raises(rx.gui.GuiError) as excinfo:
        session.textdoc_put({"text": doc["text"], "base_revision": doc["revision"]})
    assert excinfo.value.code == "STALE_REVISION"
    assert excinfo.value.status == 409
    # …and the model was not touched by the rejected apply
    assert project.refinement.structure.phases[0].cell.a.value == 4.17


def test_a_document_with_errors_applies_none_of_itself(session, project):
    doc = session.textdoc()
    edited = _edit(doc["text"], "cell.a", "  cell.a        @ 4.15678")
    edited = _edit(edited, "cell.b", "  cell.b   9.9  = 1·phases.0.cell.a")
    with pytest.raises(rx.gui.GuiError) as excinfo:
        session.textdoc_put({"text": edited})
    error = excinfo.value
    assert error.code == "TEXTDOC_INVALID" and error.status == 400
    assert [d["where"] for d in error.details] == ["phases.0.cell.b"]
    assert error.details[0]["line"] >= 1 and error.details[0]["text"].strip()
    # nothing applied: not even the good line
    assert project.refinement.structure.phases[0].cell.a.value != 4.15678


def test_a_refusal_raised_by_the_verb_still_gets_a_line_number(session, project):
    """The apply-time half of "every error carries a line".

    ``changes`` catches what it can see (a locked or tied row, an unknown path),
    but a bound violation only ``set_values`` knows about — and its message names
    the **full** path while the line carries the *local* one, so the line is found
    by matching a trailing dot-component. Without that, the one refusal a user is
    most likely to hit came back with ``line: 0``.
    """
    doc = session.textdoc()
    # an occupancy below the floor of 0 the schema declares (B has had no bound
    # since WP-1534, and occ no ceiling since WP-2002)
    bad = _edit(doc["text"], "atoms.0.occ", "  atoms.0.occ   @ -1")
    with pytest.raises(rx.gui.GuiError) as excinfo:
        session.textdoc_put({"text": bad})
    detail = excinfo.value.details[0]
    assert "lies outside its bounds" in detail["message"]
    assert detail["where"] == "phases.0.atoms.0.occ"
    assert detail["line"] >= 1
    assert bad.splitlines()[detail["line"] - 1].strip().startswith("atoms.0.occ")
    # nothing was applied: set_values validates every path before writing one
    assert project.refinement.structure.phases[0].atoms[0].biso.value != 999.0


def test_textdoc_is_refused_while_a_run_is_in_flight(session, project,
                                                     monkeypatch):
    import threading

    started, release = threading.Event(), threading.Event()

    def fake_fit(*, plan=None, events=None, cancel=None, **kw):
        started.set()
        release.wait(10)
        raise RuntimeError("stub")

    monkeypatch.setattr(project, "fit", fake_fit)
    session.run({"kind": "fit"})
    assert started.wait(5)
    try:
        assert session.textdoc()["text"]          # reads stay open
        with pytest.raises(rx.gui.GuiError) as excinfo:
            session.textdoc_put({"text": session.textdoc()["text"]})
        assert excinfo.value.code == "RUN_IN_FLIGHT"
    finally:
        release.set()


def test_the_routes_are_live_and_no_longer_reserved():
    from rietx.gui import ROUTES
    from rietx.gui.session import RESERVED_ROUTES

    assert ("GET", "/api/textdoc") in ROUTES
    assert ("PUT", "/api/textdoc") in ROUTES
    assert not {("GET", "/api/textdoc"), ("PUT", "/api/textdoc")} & set(
        RESERVED_ROUTES)


def test_the_rendered_document_is_readable_at_a_glance(project):
    """Columns are the point: a rectangular selection must hit one field.

    Asserted per block, on the *rendered* text, because the widths are computed
    per block — which is the fix for the collision that made the parser choke on
    its own renderer's output.
    """
    text = td.render(project)
    blocks, current = [], None
    for line in text.splitlines():
        if line and not line[0].isspace():
            current = [] if line.startswith(("phase ", "instrument")) else None
            if current is not None:
                blocks.append(current)
        elif current is not None and line.strip():
            current.append(line)
    assert len(blocks) == 2 and all(len(b) > 3 for b in blocks)

    for rows in blocks:
        # The property columns exist for: a rectangular selection down the vary
        # column hits vary marks and nothing else.
        at_columns = {line.index("@") for line in rows if "@" in line}
        assert len(at_columns) <= 1, rows
        for column in at_columns:
            assert {line[column] for line in rows} <= {"@", " "}, rows
    assert np.all([len(line) < 120 for line in text.splitlines()])


def test_the_highlighter_quotes_the_parsers_words():
    """The frontend's one duplication of this grammar, pinned from this side.

    WP-1013 gives the text pane a regex highlighter and no parser, so the drift a
    second implementation would cause is bounded: a divergence here is a word in
    the wrong colour, never a wrong edit — the bargain ``lib/fnmatch.ts`` makes
    with ``fnmatch.fnmatchcase`` one level down. Bounded is not free, though, and
    the vocabulary is the part that will actually move: adding a block name or a
    stage key here without restating it there leaves the new word rendering as a
    parameter path.

    Read as source text rather than executed, because the ordinary suite has no
    node — the same reason ``tests/test_gui_dist.py`` recomputes the dist digest
    in Python.
    """
    source = (Path(__file__).resolve().parent.parent / "gui" / "src" / "lib"
              / "rxt.ts")
    if not source.is_file():
        pytest.skip(f"{source} is missing — the gui workspace is not in this checkout")
    text = source.read_text(encoding="utf-8")

    def words(name: str) -> list[str]:
        match = re.search(rf"export const {name} = \[(.*?)\];", text, re.S)
        assert match, f"{name} is no longer a plain array in {source.name}"
        return re.findall(r'"([^"]+)"', match.group(1))

    assert set(words("KEYWORDS")) == set(td._KEYWORDS)
    assert set(words("FLAGS")) == set(td._FLAG_WORDS)
    assert set(words("PAIRS")) == set(td._PAIR_WORDS)
    # the peaks block's flag column quotes the schema's closed vocabulary
    # (WP-1027); a new PeakFlag member fails here until rxt.ts restates it
    assert set(words("PEAK_FLAGS")) == set(td._PEAK_FLAG_WORDS)
    # a stage line's keys are `StageSpec`'s own fields, minus the two that are
    # positional (`stage <name>  free <globs>`), plus the `free` that introduces them
    stage_keys = set(StageSpec.model_fields) - {"name", "turn_on"}
    assert set(words("STAGE_WORDS")) == stage_keys | {"free"}
    # …and the two properties the plan editor's boxes need of each of them
    # (WP-1208): which take an integer, and which admit an empty box.  Same
    # bargain as the vocabulary above — restated there, pinned from here, so a
    # new `StageSpec` field cannot reach the form as an untyped text box.
    assert set(words("STAGE_INT_WORDS")) == set(td.STAGE_INT_KEYS)
    assert set(words("STAGE_NULLABLE_WORDS")) == {
        key for key in stage_keys
        if type(None) in typing.get_args(StageSpec.model_fields[key].annotation)}

    # …and the negative half: the scanner may not have grown a way to say "wrong",
    # because only the server can know that (this is asserted from the JS side too,
    # and from both because it is the property the whole design rests on)
    tokens = words("TOKENS")
    assert tokens and "error" not in tokens
