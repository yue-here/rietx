"""WP-1005 — the project container: create, open, save, and what may not drift.

Most of these are cheap (no refinement): what a project has to get right is the
*bindings* — bytes, parsed numbers, reader call, history tree — and every one of
them is checkable without solving anything.  One module-scoped fit exists to
prove the interesting half, that reopening resumes mid-history at the head.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import Parameter
from rietx.project import PROJECT_JSON, fitted_mask
from tests.test_refine_synthetic import perturbed_models, synthesize

OUT = Path(__file__).parent / "output"

pytestmark = pytest.mark.xdist_group("project")

#: The real preset rather than a two-stage stub, because the fixture's PNG is the
#: visual gate this suite's numbers cannot be (CLAUDE.md, Tests).  A partial plan
#: converges to a *bad* fit by design — dropping the zero-shift stage alone leaves
#: a derivative-shaped residual on every peak — and a picture that always looks
#: wrong cannot show that something is.  It costs well under a second here.
SHORT = rx.PLAN_PRESETS["mccusker_default"]()

DATA = Path(__file__).parent / "data"


def _write_xye(path: Path, data: rx.PatternData, *, with_sigma: bool = True) -> Path:
    """The synthetic pattern as a file, since a project copies bytes not objects.

    ``repr`` of a float round-trips exactly, so the parsed arrays are
    bit-identical to ``data`` and the fingerprints must agree.

    The esd column is deliberately **not** √max(y,1): an esd equal to the Poisson
    fallback would make "the file's weights survived the copy" untestable, since
    losing the column entirely would produce the same numbers.  1.3× stands for
    any of the ordinary reasons a measured esd is not raw counting statistics
    (monitor normalisation, merged frames, a detector gain).
    """
    sig = 1.3 * np.sqrt(np.maximum(np.asarray(data.intensity), 1.0))
    rows = (f"{float(t)!r} {float(y)!r} {float(s)!r}" if with_sigma
            else f"{float(t)!r} {float(y)!r}"
            for t, y, s in zip(data.two_theta, data.intensity, sig))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture(scope="module")
def pattern_file(tmp_path_factory, pattern):
    return _write_xye(tmp_path_factory.mktemp("data") / "synth.xye", pattern)


def _create(root: Path, pattern_file: Path, **kw) -> rx.Project:
    structure, ins = perturbed_models()
    return rx.Project.create(root, pattern=pattern_file, structure=structure,
                             instrument=ins, **kw)


@pytest.fixture(scope="module")
def fitted_project(tmp_path_factory, pattern_file):
    """One real refinement inside a project, shared by the resume tests."""
    project = _create(tmp_path_factory.mktemp("fitted") / "sample.rex", pattern_file)
    result = project.fit(plan=SHORT)
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / "project_container.png"))
    return project, result


# ------------------------------------------------------------------ holds
def test_a_hold_survives_reopening_the_project(tmp_path, pattern_file):
    """A promise that expires on reopen is worse than no promise (WP-1435).

    The register rides on the history node rather than in ``project.json``,
    which is the split working as designed: a hold is model state, the
    document holds settings, and the head *is* the working state. So the
    assertion is on what the reopened refinement enforces, not on a field.
    """
    project = _create(tmp_path / "held.rex", pattern_file)
    assert project.refinement.hold("phases.0.cell.a") == ["phases.0.cell.a"]
    project.save()

    reopened = rx.Project.open(project.path)
    row = {r.path: r for r in reopened.refinement.parameters()}["phases.0.cell.a"]
    assert row.held and not row.refinable

    # and it is still enforced, not merely remembered
    result = reopened.fit(plan=SHORT)
    blocked = {s.name: s.blocked_by_hold for s in result.stages if s.blocked_by_hold}
    # the closing stage frees every glob the plan freed, the cell's too
    assert blocked == {"cell": ["phases.0.cell.a"], "closing": ["phases.0.cell.a"]}
    assert reopened.refinement.structure.phases[0].cell.a.value == \
        project.refinement.structure.phases[0].cell.a.value


# ------------------------------------------------------------------ layout
def test_create_writes_the_documented_layout(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file, ui={"disclosure": "simple"})

    assert sorted(p.name for p in project.path.iterdir()) == [
        "exports", "history.jsonl", "live", "project.json", "synth.xye"]
    assert project.live_dir.is_dir() and project.exports_dir.is_dir()
    # the pattern is a byte-for-byte copy, not a re-serialisation
    assert (project.path / "synth.xye").read_bytes() == pattern_file.read_bytes()
    # the root node is the as-created model, so "undo everything" has a target
    assert len(project.history) == 1
    assert project.history.root.action.kind == "root"
    assert project.refinement._head_id == project.history.head


def test_create_refuses_to_write_over_a_project(tmp_path, pattern_file):
    _create(tmp_path / "s.rex", pattern_file)
    with pytest.raises(FileExistsError, match="open it instead"):
        _create(tmp_path / "s.rex", pattern_file)


def test_missing_pattern_file_is_named(tmp_path):
    structure, ins = perturbed_models()
    with pytest.raises(FileNotFoundError, match="pattern file not found"):
        rx.Project.create(tmp_path / "s.rex", pattern=tmp_path / "nope.xy",
                          structure=structure, instrument=ins)


# --------------------------------------------------------------- round trip
def test_document_round_trip_including_infinite_bounds(tmp_path, pattern_file):
    """±inf bounds must survive JSON, and the project's own document too.

    The bounds live in the history node here, not in ``project.json`` — which is
    the point of the split — so this exercises both files in one open.
    """
    project = _create(tmp_path / "s.rex", pattern_file, plan="mccusker_default",
                      mode="rietveld", two_theta_limits=(4.0, 22.0),
                      excluded_regions=[(7.5, 8.0)], ui={"panels": ["plot", "params"]})
    project.save()

    raw = json.loads((project.path / PROJECT_JSON).read_text(encoding="utf-8"))
    assert raw["format_version"] == "1.5"   # WP-2002 B1: the plan's phase_support_sigma
    assert raw["patterns"][0]["reader"] == "xy"

    reopened = rx.Project.open(project.path)
    assert reopened.doc.model_dump() == project.doc.model_dump()
    assert reopened.doc.ui == {"panels": ["plot", "params"]}
    assert reopened.doc.two_theta_limits == (4.0, 22.0)
    assert reopened.doc.excluded_regions == [(7.5, 8.0)]
    # the exclusion reaches the data, not just the document
    assert reopened.data.excluded_regions == [(7.5, 8.0)]
    assert reopened.data.in_range_mask().sum() < len(reopened.data.two_theta)
    # the plan is a PlanSpec and rebuilds the preset it names
    assert [s.name for s in reopened.doc.plan.to_plan().stages] == \
           [s.name for s in rx.PLAN_PRESETS["mccusker_default"]().stages]

    x = reopened.refinement.parameters()
    unbounded = [r for r in x if math.isinf(r.hi)]
    assert unbounded, "some parameters are genuinely unbounded above"
    assert all(math.isinf(r.hi) for r in unbounded)


def test_a_user_tie_survives_the_round_trip_without_a_save(tmp_path, pattern_file):
    """The constraint is model state, so the log carries it and ``save`` is idle.

    One authority per fact: ``history.jsonl`` holds the model state and its head
    *is* the working state, so a tie is on disk the moment it is declared —
    exactly as ``set_vary`` is.  Reopening must come back with the same
    parameter count, not merely the same values: a project that dropped the
    constraint would refine one parameter more than the protocol it recorded,
    and every esd it quoted afterwards would be the wrong one.
    """
    project = _create(tmp_path / "tied.rex", pattern_file)
    bisos = ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"]
    project.refinement.tie_equal(bisos)
    project.refinement.set_vary(["phases.0.atoms.*.biso"])

    reopened = rx.Project.open(project.path)
    rows = {r.path: r for r in reopened.parameters()}
    assert rows[bisos[1]].tie is not None and rows[bisos[1]].tie.user
    assert rows[bisos[1]].tie.sources == [bisos[0]]
    assert rows[bisos[0]].vary and not rows[bisos[1]].vary
    # and it is still the user's to release after the round trip
    assert reopened.refinement.untie(bisos[1]) == [bisos[1]]


def test_open_accepts_the_document_path(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    assert rx.Project.open(project.path / PROJECT_JSON).path == project.path


def test_save_never_rewrites_the_pattern_or_the_log(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    before = {p.name: p.read_bytes() for p in project.path.iterdir() if p.is_file()}
    project.doc.ui["zoom"] = [10.0, 20.0]
    project.save()
    after = {p.name: p.read_bytes() for p in project.path.iterdir() if p.is_file()}

    assert after["synth.xye"] == before["synth.xye"]
    assert after["history.jsonl"] == before["history.jsonl"]
    assert after[PROJECT_JSON] != before[PROJECT_JSON]
    assert not list(project.path.glob("*.tmp")), "the atomic write left no debris"


# ------------------------------------------------------------- the bindings
def test_esd_column_survives_the_copy(tmp_path, pattern, pattern_file):
    """The file's esds are the weights; the Poisson fallback is *not* equivalent.

    Read the copy the project made and compare the weights it yields against the
    original file's — the reason the pattern is copied verbatim rather than
    re-serialised (CLAUDE.md, Weights).
    """
    project = _create(tmp_path / "s.rex", pattern_file)
    original = rx.read_pattern(pattern_file)
    copied = project.data

    assert project.data_ref.has_sigma is True
    assert copied.sigma is not None
    np.testing.assert_array_equal(copied.sig(), original.sig())
    # and they are not the Poisson fallback in disguise
    poisson = rx.PatternData(two_theta=copied.two_theta, intensity=copied.intensity)
    assert not np.allclose(copied.sig(), poisson.sig())


def test_a_pattern_without_esds_says_so(tmp_path, tmp_path_factory, pattern):
    plain = _write_xye(tmp_path_factory.mktemp("plain") / "noesd.xy", pattern,
                       with_sigma=False)
    project = _create(tmp_path / "s.rex", plain)
    assert project.data_ref.has_sigma is False
    assert project.data.sigma is None


def test_edited_pattern_file_is_refused(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    copied = project.path / project.data_ref.filename
    copied.write_text(copied.read_text(encoding="utf-8") + "99.0 1.0 1.0\n",
                      encoding="utf-8")
    with pytest.raises(ValueError, match="file has changed"):
        rx.Project.open(project.path)


def test_same_bytes_parsed_differently_is_reported_as_a_reader_change(
        tmp_path, pattern_file):
    """The two digests answer different questions, and the message says which.

    Editing the recorded fingerprint while leaving the sha256 alone is exactly
    the state a reader change would produce: the bytes are what they always
    were, the numbers are not.
    """
    project = _create(tmp_path / "s.rex", pattern_file)
    doc_path = project.path / PROJECT_JSON
    raw = json.loads(doc_path.read_text(encoding="utf-8"))
    raw["patterns"][0]["fingerprint"] = "0" * 32
    doc_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="parses them differently"):
        rx.Project.open(project.path)


def test_history_recorded_against_another_pattern_is_refused(
        tmp_path, tmp_path_factory, pattern):
    """A container may not silently rebind a tree to different data.

    ``refine.replay`` enforces this per node; a project that opened anyway would
    be the same failure one level up, and permanent rather than per call.
    """
    mine = _write_xye(tmp_path_factory.mktemp("mine") / "a.xye", pattern)
    other = _write_xye(tmp_path_factory.mktemp("other") / "b.xye",
                       synthesize(noise_seed=99))
    project = _create(tmp_path / "s.rex", mine)
    stranger = _create(tmp_path / "t.rex", other)

    (project.path / "history.jsonl").write_bytes(
        (stranger.path / "history.jsonl").read_bytes())
    with pytest.raises(ValueError, match="recorded against a different pattern"):
        rx.Project.open(project.path)


def test_missing_history_log_is_refused(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    (project.path / "history.jsonl").unlink()
    with pytest.raises(FileNotFoundError, match="holds the model state"):
        rx.Project.open(project.path)


#: What ``model_dump_json`` wrote for a caller's ``Parameter(value=...)`` on a
#: field that declared a range, before its class inherited it (issue #204).
_BARE = {"min": "-Infinity", "max": "Infinity", "unit": None, "transform": "identity"}


def _age_log(project: rx.Project, schema: str | None, edit=None) -> Path:
    """Rewrite a project's log as a release at ``schema`` would have left it.

    ``edit`` touches each node's state dict; ``schema=None`` drops the header's
    stamp altogether.  Every node loses its own stamp, which no release before
    0.35 wrote.  The shape is the one issue #209 verified on the #206
    tree: every key present, the bounds spelled as JSON strings.
    """
    log = project.path / project.doc.history_file
    lines = []
    for line in log.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec["record"] == "header":
            if schema is None:
                rec["header"].pop("schema_version")
            else:
                rec["header"]["schema_version"] = schema
        elif rec["record"] == "node":
            rec["node"].pop("schema_version", None)   # no release before 0.35 wrote one
            if edit is not None:
                edit(rec["node"]["state"])
        lines.append(json.dumps(rec))
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log


def _bare_biso(value: float | None = None):
    def edit(state):
        biso = state["structure"]["phases"][0]["atoms"][1]["biso"]
        biso.update(_BARE)
        if value is not None:
            biso["value"] = value
    return edit


def _bare_occ(value: float | None = None):
    """``_bare_biso`` on the occupancy, whose declared floor of 0 is what these
    repairs restore since WP-1534 left ``Atom.biso`` with a unit only (and
    WP-2002 left ``occ`` with no ceiling)."""
    def edit(state):
        occ = state["structure"]["phases"][0]["atoms"][1]["occ"]
        occ.update(_BARE)
        if value is not None:
            occ["value"] = value
    return edit


def test_a_log_written_before_206_opens_with_its_declared_bounds_back(
        tmp_path, pattern_file):
    """Issue #209's fixture: a pre-#206 document carrying an unbounded
    parameter its schema declares a range for (``biso`` then, ``occ`` since
    WP-1534).

    ``model_dump`` wrote the dropped bounds out explicitly, so on load the
    keys are all present, construction inherits nothing, and the fit would run
    unbounded again.  The reader restores the declared range and says so once
    per parameter, naming the atom and both ranges; the value stays put.
    """
    project = _create(tmp_path / "s.rex", pattern_file)
    project.refinement.set_values({"phases.0.atoms.1.occ": 0.7})   # a second node
    _age_log(project, "0.16", _bare_occ())

    reopened = rx.Project.open(project.path)
    occ = reopened.refinement.structure.phases[0].atoms[1].occ
    assert (occ.value, occ.min, occ.max) == (0.7, 0.0, float("inf"))
    for node in reopened.history.nodes.values():
        stored = node.state.structure.phases[0].atoms[1].occ
        assert (stored.min, stored.max) == (0.0, float("inf"))

    [note] = reopened.history_diagnostics
    assert (note.code, note.level, note.where) == (
        "DECLARED_RANGE_RESTORED", "warning", ["phases.0.atoms.1.occ"])
    assert "(atom B)" in note.message
    assert "[-inf, inf]" in note.message
    assert "[0.0, inf]" in note.message
    assert "this history (2: n0000, n0001)" in note.message and "schema 0.17" in note.message
    assert reopened.data_diagnostics == []   # the pattern's channel stays the pattern's


def test_a_log_within_its_declared_bounds_is_untouched_byte_for_byte(
        tmp_path, pattern_file):
    """The repair walks an old log and finds nothing: no note, and every node
    re-serialises to the very line it was read from.  A log this release
    wrote is not walked at all."""
    project = _create(tmp_path / "s.rex", pattern_file)
    project.refinement.set_values({"phases.0.scale": 1e-3})
    for schema in ("0.16", rx.schemas.common.SCHEMA_VERSION):
        log = _age_log(project, schema)
        notes: list = []
        tree = rx.RefinementTree.load(log, diagnostics=notes)
        assert notes == []
        lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        nodes = [rec["node"] for rec in lines if rec["record"] == "node"]
        assert len(nodes) == len(tree.order) == 2
        for stored, nid in zip(nodes, tree.order):
            # exclude_unset: an aged line has no node stamp, and the field's
            # default re-serialising as null is not a change the reader made
            assert json.loads(tree.nodes[nid].model_dump_json(exclude_unset=True)) == stored


def test_an_unbounded_biso_written_after_206_is_a_choice_and_kept(
        tmp_path, pattern_file):
    """From 0.17 on, an explicit ``min=-inf`` wins at construction, so a bare
    attribute in a log written then was meant: no repair, no note."""
    project = _create(tmp_path / "s.rex", pattern_file)
    _age_log(project, "0.17", _bare_biso())
    reopened = rx.Project.open(project.path)
    biso = reopened.refinement.structure.phases[0].atoms[1].biso
    assert (biso.min, biso.max, biso.unit) == (float("-inf"), float("inf"), None)
    assert reopened.history_diagnostics == []


#: The keys of a stored ``Parameter`` since schema 0.46, which dropped
#: ``transform`` (WP-1938); every release before wrote that key too.
_PARAMETER_KEYS = {"value", "vary", "min", "max", "expr", "unit", "stderr"}


def _stamp_transforms(obj) -> None:
    """Give every stored ``Parameter`` the ``transform`` key a 0.45 log wrote."""
    if isinstance(obj, dict):
        if set(obj) == _PARAMETER_KEYS:
            obj["transform"] = "identity"
        for value in obj.values():
            _stamp_transforms(value)
    elif isinstance(obj, list):
        for value in obj:
            _stamp_transforms(value)


def test_a_log_written_with_transforms_opens_unchanged_in_meaning(
        tmp_path, pattern_file):
    """WP-1938 task 2: a history written at schema 0.45, when every stored
    ``Parameter`` carried ``transform``, opens with each word folded into the
    box the table already built from it.  No value moves, no repair note
    fires, and every other parameter reads exactly as it was written."""
    project = _create(tmp_path / "s.rex", pattern_file)
    want = project.refinement.structure.phases[0].model_dump()

    def edit(state):
        _stamp_transforms(state)
        phase = state["structure"]["phases"][0]
        phase["scale"].update(transform="softplus", min=0.0)
        phase["atoms"][0]["occ"].update(transform="logit", min=-1.0, max=2.0)
        phase["cell"]["a"].update(transform="exp")

    log = _age_log(project, "0.45", edit)
    text = log.read_text(encoding="utf-8")
    assert all(f'"transform": "{k}"' in text
               for k in ("softplus", "logit", "exp", "identity"))

    reopened = rx.Project.open(project.path)
    assert reopened.history_diagnostics == []
    got = reopened.refinement.structure.phases[0]
    assert (got.scale.min, got.scale.max) == (0.0, math.inf)
    assert (got.atoms[0].occ.min, got.atoms[0].occ.max) == (0.0, 1.0)
    assert got.cell.a.min == max(want["cell"]["a"]["min"], 0.0)
    want["atoms"][0]["occ"].update(min=0.0, max=1.0)
    want["cell"]["a"]["min"] = max(want["cell"]["a"]["min"], 0.0)
    assert got.model_dump() == want      # every value, and every other bound
    rows = {r.path: r for r in reopened.refinement.parameters()}
    assert (rows["phases.0.atoms.0.occ"].lo, rows["phases.0.atoms.0.occ"].hi) == (0.0, 1.0)


def test_a_unit_declared_later_is_no_range_to_restore(tmp_path, pattern_file):
    """WP-1451 declared extinction's unit, µm², after ``Phase`` inherited at
    0.35.  A log written before both holds that parameter's declared range and
    no unit: nothing is unbounded, so nothing is restored and no note blames
    issue #204 for a label no release before it could write."""
    def unitless_extinction(state):
        state["structure"]["phases"][0]["extinction"]["unit"] = None
    project = _create(tmp_path / "s.rex", pattern_file)
    _age_log(project, "0.34", unitless_extinction)
    reopened = rx.Project.open(project.path)
    ext = reopened.refinement.structure.phases[0].extinction
    assert (ext.min, ext.unit) == (0.0, None)
    assert reopened.history_diagnostics == []


def test_a_log_that_never_stamped_its_schema_reads_as_the_oldest(
        tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    _age_log(project, None, _bare_occ())
    notes: list = []
    rx.RefinementTree.load(project.path / project.doc.history_file, diagnostics=notes)
    assert [n.code for n in notes] == ["DECLARED_RANGE_RESTORED"]


def test_each_class_is_repaired_from_its_own_version(tmp_path, pattern_file):
    """``Phase`` inherited at 0.35, ``Atom`` at 0.17.  A log written at 0.34
    with both left bare holds one defect and one choice: the scale gets its
    floor back, the biso is left as it was declared."""
    project = _create(tmp_path / "s.rex", pattern_file)

    def edit(state):
        _bare_biso()(state)
        state["structure"]["phases"][0]["scale"].update(_BARE)

    _age_log(project, "0.34", edit)
    reopened = rx.Project.open(project.path)
    phase = reopened.refinement.structure.phases[0]
    assert phase.scale.min == 0.0
    assert phase.atoms[1].biso.min == float("-inf")
    [note] = reopened.history_diagnostics
    assert note.where == ["phases.0.scale"] and "schema 0.35" in note.message


def test_a_stored_value_outside_the_declared_range_is_left_and_reported(
        tmp_path, pattern_file):
    """No value ever moves, and no record is refused: a range restored under a
    value it does not hold would refuse the log, and the declared box is not
    physics for every instrument (a coarse neutron line's Caglioti ``u`` sits
    far outside the X-ray one).  So the parameter is left as stored, still
    unbounded, and the note says so, naming the node and the value."""
    project = _create(tmp_path / "s.rex", pattern_file)
    # below the floor of 0 (an occupancy has had no ceiling since WP-2002)
    _age_log(project, "0.16", _bare_occ(-2.0))
    reopened = rx.Project.open(project.path)
    occ = reopened.refinement.structure.phases[0].atoms[1].occ
    assert (occ.value, occ.min, occ.max) == (-2.0, float("-inf"), float("inf"))
    [note] = reopened.history_diagnostics
    assert (note.code, note.level, note.where, note.value) == (
        "DECLARED_RANGE_NOT_RESTORED", "warning", ["phases.0.atoms.1.occ"], -2.0)
    assert "-2.0 in n0000" in note.message and "[0.0, inf]" in note.message


def test_a_parameter_is_restored_in_every_node_or_in_none(tmp_path, pattern_file):
    """One node inside the declared range and one outside it: restoring the
    first alone would hand a checkout of it a range the other refutes, so
    neither is restored and the note counts both."""
    project = _create(tmp_path / "s.rex", pattern_file)
    project.refinement.set_values({"phases.0.atoms.1.occ": 0.7})
    values = iter([0.5, -3.0])

    def edit(state):
        _bare_occ(next(values))(state)

    _age_log(project, "0.16", edit)
    notes: list = []
    tree = rx.RefinementTree.load(project.path / project.doc.history_file,
                                  diagnostics=notes)
    for node in tree.nodes.values():
        assert node.state.structure.phases[0].atoms[1].occ.min == float("-inf")
    [note] = notes
    assert note.code == "DECLARED_RANGE_NOT_RESTORED"
    assert "this history (2: n0000, n0001)" in note.message and "-3.0 in n0001" in note.message


def test_a_node_this_release_appends_to_an_old_log_is_read_at_its_own_version(
        tmp_path, pattern_file):
    """The header stamps a log's creation, and a log outlives the release that
    began it.  A node appended now carries its own stamp, so an explicit
    unbounded occupancy chosen today is a choice tomorrow, while the old node
    beside it is still repaired."""
    project = _create(tmp_path / "s.rex", pattern_file)
    _age_log(project, "0.16", _bare_occ())
    reopened = rx.Project.open(project.path)
    reopened.refinement.structure.phases[0].atoms[1].occ = Parameter(
        value=0.6, min=float("-inf"), max=float("inf"), unit=None,
        transform="identity")
    reopened.refinement.set_values({"phases.0.atoms.1.occ": 0.6})

    again = rx.Project.open(project.path)
    old, new = (again.history.nodes[n] for n in again.history.order)
    assert new.schema_version == rx.schemas.common.SCHEMA_VERSION
    assert old.schema_version is None
    # the declared range is [0, inf) since WP-2002, so the floor is what tells
    # the repaired node from the chosen one
    assert old.state.structure.phases[0].atoms[1].occ.min == 0.0
    assert new.state.structure.phases[0].atoms[1].occ.min == float("-inf")
    [note] = again.history_diagnostics
    assert "this history (n0000)" in note.message


def test_an_instrument_profile_is_the_other_read_point(tmp_path):
    """A saved profile carries an instrument too, so it is repaired by the
    same rule, gated on the stamp the writer now adds, restored or left per
    parameter.  A profile this release writes loads with nothing to say."""
    ins = rx.Instrument.debye_scherrer(wavelength=0.4139)
    path = tmp_path / "cal.json"
    rx.save_instrument_profile(ins, path)
    notes: list = []
    rx.load_instrument_profile(path, diagnostics=notes)
    assert notes == []

    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.pop("schema_version")
    # V, whose declared box is the 2θ axis's mirror pair since WP-2002
    # (2026-10-23); zero_shift's box went (2026-10-20) and U, V and Y lost
    # their chosen floors, so the X left unrestored is one under its floor
    doc["instrument"]["profile"]["v"].update(_BARE)
    doc["instrument"]["profile"]["x"].update({**_BARE, "value": -0.1})
    path.write_text(json.dumps(doc), encoding="utf-8")
    loaded = rx.load_instrument_profile(path, diagnostics=notes)
    assert (loaded.profile.v.min, loaded.profile.v.max, loaded.profile.v.unit) == (
        -180.0 ** 2, 180.0 ** 2, "deg^2")
    assert loaded.profile.x.min == -float("inf") and loaded.profile.x.value == -0.1
    by_code = {n.code: n for n in notes}
    assert by_code["DECLARED_RANGE_RESTORED"].where == ["instrument.profile.v"]
    left = by_code["DECLARED_RANGE_NOT_RESTORED"]
    assert (left.where, left.value) == (["instrument.profile.x"], -0.1)
    assert "the profile cal.json" in left.message


def test_every_declared_range_read_point_exists_and_repairs():
    """``DECLARED_RANGE_READ_POINTS`` is a claim, checked the way
    ``READ_POINTS`` is (WP-1076): each names a reader that exists and that
    calls the one repair, so a moved reader cannot leave the tuple describing
    a reader that is gone or one that stopped repairing."""
    import importlib
    import inspect

    from rietx.schemas.migrate import DECLARED_RANGE_READ_POINTS

    assert len(DECLARED_RANGE_READ_POINTS) >= 2
    for dotted in DECLARED_RANGE_READ_POINTS:
        parts = dotted.split(".")
        for i in range(len(parts), 1, -1):
            try:
                target = importlib.import_module(".".join(parts[:i]))
            except ModuleNotFoundError:
                continue
            break
        for part in parts[i:]:
            target = getattr(target, part)
        assert "restore_declared_ranges(" in inspect.getsource(target), dotted


def test_a_future_format_version_is_refused_by_name(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    doc_path = project.path / PROJECT_JSON
    raw = json.loads(doc_path.read_text(encoding="utf-8"))
    raw["format_version"] = "2"
    doc_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="another version of rietx"):
        rx.Project.open(project.path)


def test_a_project_written_before_the_bump_still_opens(tmp_path, pattern_file):
    """The compatibility direction: old files must always open (WP-1207).

    The 1.2 → 1.3 bump added no key — what grew is the set of legal documents,
    since a project may now hold no phase. So a 1.2 document is a 1.3 document
    that happens to have one, and it must open unchanged rather than be
    migrated: the major gate is what refuses, and it still opens every 1.x.
    """
    project = _create(tmp_path / "s.rex", pattern_file)
    doc_path = project.path / PROJECT_JSON
    raw = json.loads(doc_path.read_text(encoding="utf-8"))
    raw["format_version"] = "1.2"
    doc_path.write_text(json.dumps(raw), encoding="utf-8")

    reopened = rx.Project.open(project.path)
    assert reopened.doc.format_version == "1.2"     # read back, not rewritten
    assert len(reopened.refinement.structure.phases) == 1
    # …and 1.0, the version every earlier project carries
    raw["format_version"] = "1.0"
    doc_path.write_text(json.dumps(raw), encoding="utf-8")
    assert rx.Project.open(project.path).doc.format_version == "1.0"


def test_a_pattern_only_project_is_created_saved_and_reopened(tmp_path, pattern_file):
    """``structure=None`` is a project, not an unfinished one (WP-1207).

    It round-trips through the directory like any other, its parameter table
    holds the instrument and the background, and the refusal is on the verb:
    ``fit`` raises before a stage compiles, while ``predict`` — which refines
    nothing — still answers.
    """
    project = rx.Project.create(tmp_path / "unknown.rex", pattern=pattern_file,
                                instrument=perturbed_models()[1])
    assert project.refinement.structure.phases == []
    project.save()

    reopened = rx.Project.open(project.path)
    assert reopened.refinement.structure.phases == []
    paths = [row.path for row in reopened.refinement.parameters()]
    assert paths and all(p.startswith("instrument.") for p in paths)
    assert not any(p.startswith("phases.") for p in paths)

    with pytest.raises(rx.NoPhasesError, match="needs at least one phase") as exc:
        reopened.fit()
    assert exc.value.code == "NO_PHASES"
    # evaluating the background as it stands is not a refinement
    assert len(reopened.refinement.predict(reopened.data)) == len(reopened.data.two_theta)


def test_multi_pattern_projects_are_refused_not_truncated(tmp_path, pattern_file):
    """The ``patterns`` list is the multi-histogram seam, not a feature yet."""
    project = _create(tmp_path / "s.rex", pattern_file)
    doc_path = project.path / PROJECT_JSON
    raw = json.loads(doc_path.read_text(encoding="utf-8"))
    raw["patterns"].append(dict(raw["patterns"][0]))
    doc_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="single-pattern projects only"):
        rx.Project.open(project.path)


# ------------------------------------------------------- the reader *call*
def test_the_pdcif_block_is_recorded_and_replayed(tmp_path):
    """Re-opening must reproduce the reader call, not merely the file.

    The NIST SRM 660c certification file carries both a measured and a
    calculated block with identical tags, and the default read takes the first
    that parses — so a project that recorded only the path would come back with
    a different pattern, and (because the fingerprint would then disagree) as a
    hard error rather than a wrong answer.  Recording ``block`` is what makes it
    open at all.
    """
    cif = DATA / "nist_srm660c_100a.cif"
    structure, ins = perturbed_models()
    project = rx.Project.create(tmp_path / "cert.rex", pattern=cif,
                                structure=structure, instrument=ins,
                                reader_options={"block": "_calc"})

    assert project.data_ref.reader == "pdcif"
    assert project.data_ref.options == {"block": "_calc"}
    assert "calc" in project.data.metadata["block"]

    reopened = rx.Project.open(project.path)
    assert reopened.data.metadata["block"] == project.data.metadata["block"]
    # …and the default read really does pick a different block, so this matters
    assert rx.read_pattern(cif).metadata["block"] != project.data.metadata["block"]


# --------------------------------------------------------------- the session
def test_settings_drive_the_convenience_verbs(tmp_path, pattern_file):
    """``project.fit()`` runs the project's own plan, mode and limits."""
    one = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                 max_iter=5)])
    project = _create(tmp_path / "s.rex", pattern_file, plan=one,
                      two_theta_limits=(4.0, 20.0))
    result = project.fit()

    assert [s.name for s in result.stages] == ["scale_bkg", "closing"]
    assert project.refinement._two_theta_limits == (4.0, 20.0)


def test_run_stage_uses_the_documents_mode_before_any_fit(tmp_path, pattern_file):
    """A Le Bail project driven one stage at a time must not start in Rietveld.

    ``Refinement.run_stage`` defaults ``mode`` to the value it carries, which
    before the first run is the ``"rietveld"`` default — so the mode a project
    selected has to be passed explicitly, and this is the test that says so.
    """
    project = _create(tmp_path / "s.rex", pattern_file, mode="lebail")
    result = project.run_stage(
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                 max_iter=5))
    assert result.mode == "lebail"
    assert project.history[project.history.head].state.mode == "lebail"


def test_run_stage_takes_the_stored_plans_hold_threshold(tmp_path, pattern_file,
                                                        monkeypatch):
    """A stage driven by hand (the GUI's stage verb) reads the threshold the
    project's plan stores, or a hold the caller switched off comes back at the
    default for every stage run one at a time (WP-2002, B1).  A caller's own
    keyword still wins."""
    project = _create(tmp_path / "s.rex", pattern_file, plan="mccusker_default")
    seen = []
    monkeypatch.setattr(project.refinement, "run_stage",
                        lambda data, stage, **kw: seen.append(kw))
    stage = rx.Stage("scale_bkg", ["phases.*.scale"])

    project.run_stage(stage)
    assert seen[-1]["phase_support_sigma"] == 3.0
    project.doc.plan = project.doc.plan.model_copy(update={"phase_support_sigma": None})
    project.run_stage(stage)
    assert seen[-1]["phase_support_sigma"] is None
    project.run_stage(stage, phase_support_sigma=5.0)
    assert seen[-1]["phase_support_sigma"] == 5.0
    # and the correlation guard, the plan's other setting a stage reads
    assert seen[-1]["correlation_guard"] == 0.98
    project.doc.plan = project.doc.plan.model_copy(update={"correlation_guard": 0.9})
    project.run_stage(stage)
    assert seen[-1]["correlation_guard"] == 0.9


def test_set_excluded_regions_updates_document_and_data(tmp_path, pattern_file):
    project = _create(tmp_path / "s.rex", pattern_file)
    project.set_excluded_regions([(6.0, 6.5)])
    assert project.doc.excluded_regions == [(6.0, 6.5)]
    assert project.data.excluded_regions == [(6.0, 6.5)]
    project.save()
    assert rx.Project.open(project.path).data.excluded_regions == [(6.0, 6.5)]


def test_a_pattern_and_a_fit_refuse_an_inverted_interval_as_the_document_does():
    """WP-1986: `PatternData` took `(31, 30)` and masked nothing, and an
    inverted `two_theta_limits` failed as "fewer than 10 points remain"."""
    from pydantic import ValidationError

    tt = [10.0 + 0.1 * i for i in range(40)]
    data = rx.PatternData(two_theta=tt, intensity=[100.0] * 40)
    with pytest.raises(ValidationError, match=r"\(11\.0, 10\.5\) is inverted"):
        data.excluded_regions = [(11.0, 10.5)]
    with pytest.raises(ValidationError, match=r"\(11\.0, 11\.0\) is empty"):
        rx.PatternData(two_theta=tt, intensity=[100.0] * 40,
                       excluded_regions=[(11.0, 11.0)])
    # a list mutated in place reaches no validator, so the mask asks again
    data.excluded_regions.append((11.0, 10.5))
    with pytest.raises(ValueError, match=r"\(11\.0, 10\.5\) is inverted"):
        data.in_range_mask()
    data.excluded_regions.clear()
    with pytest.raises(ValueError, match=r"\(13\.0, 11\.0\) is inverted"):
        fitted_mask(data, (13.0, 11.0))

    from rietx.model.forward import compile_model
    structure, instrument = perturbed_models()
    with pytest.raises(ValueError, match=r"two_theta_limits must run low to "
                                         r"high: \(13\.0, 11\.0\) is inverted"):
        compile_model(structure, instrument, data, two_theta_limits=(13.0, 11.0))


def test_an_unrun_edit_is_in_the_log_before_any_save(tmp_path, pattern_file):
    """Nothing has to be saved for work to be durable.

    The tree exists from ``create``, so ``set_vary``/``set_values`` commit a node
    immediately — which is what settles the WP-1004 question of whether a project
    edited without running anything has state no history node describes.
    """
    project = _create(tmp_path / "s.rex", pattern_file)
    project.refinement.set_vary("instrument.zero_shift", True)
    project.refinement.set_values({"phases.0.cell.a": 4.16})

    reopened = rx.Project.open(project.path)  # no save() in between
    assert [n.action.kind for n in reopened.history.nodes.values()] == \
           ["root", "set_vary", "set_value"]
    assert reopened.refinement.fitted_structure.phases[0].cell.a.value == 4.16
    assert "instrument.zero_shift" in reopened.refinement._free_paths


def test_reopen_mid_history_resumes_at_head(fitted_project, pattern):
    project, result = fitted_project
    assert result.node_id == project.history.head

    reopened = rx.Project.open(project.path)
    assert len(reopened.history) == 1 + len(SHORT.run_stages())
    assert reopened.refinement._head_id == project.history.head
    # the working state is the fitted one, not the as-created one
    fitted_a = project.refinement.fitted_structure.phases[0].cell.a.value
    assert reopened.refinement.fitted_structure.phases[0].cell.a.value == fitted_a
    assert reopened.refinement._free_paths == project.refinement._free_paths
    # and it can be continued: a new stage lands as a child of the head
    reopened.run_stage(rx.Stage("zero", ["instrument.zero_shift"], max_iter=5))
    assert reopened.history[reopened.history.head].parents == [result.node_id]


def test_a_reopened_project_can_replay_its_head(fitted_project):
    """The reopened tree and the reopened data are compatible in both directions.

    ``replay`` is the strictest check available: it refuses a pattern whose
    fingerprint does not match the tree, then recompiles the node's state from
    scratch.  Agreement with the node's cached metrics is close but not exact —
    those are *as-optimised*, measured on a model frozen at the values the stage
    started from (see ``NodeMetrics``).
    """
    project, _ = fitted_project
    reopened = rx.Project.open(project.path)

    replayed = rx.replay(reopened.history, "head", reopened.data)
    cached = reopened.history[reopened.history.head].metrics.statistics.rwp
    assert replayed.statistics.rwp == pytest.approx(cached, rel=1e-3)
    assert len(reopened.refinement.parameters()) == \
           len(project.refinement.parameters())


def test_a_project_reopens_on_the_scan_it_was_created_from(tmp_path):
    """The reader *call* is part of the reference, not just the bytes.

    A multi-scan file's sha256 and its parsed-array fingerprint say nothing
    about *which* scan was read, so ``scan`` has to be recorded beside ``block``
    — and recorded as the **effective** option, which is what re-opening
    replays.
    """
    structure, ins = perturbed_models()
    proj = rx.Project.create(tmp_path / "high.rex",
                             pattern=DATA / "rigaku_multiscan.ras",
                             structure=structure, instrument=ins,
                             reader_options={"scan": 1})

    ref = proj.doc.patterns[0]
    assert ref.reader == "ras"
    assert ref.options == {"scan": "1"}                # dict[str, str] on disk
    assert proj.data.two_theta == [20.0, 20.5, 21.0]

    reopened = rx.Project.open(tmp_path / "high.rex")
    assert reopened.data.two_theta == [20.0, 20.5, 21.0]
    assert reopened.doc.patterns[0].fingerprint == ref.fingerprint
