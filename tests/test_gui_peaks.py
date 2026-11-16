"""WP-1027 — the peak picker's verbs and the indexing panel's gate.

Against a **real** server on an ephemeral port, like ``test_gui_server``,
because what this WP adds is wire surface: the verbs must round-trip as HTTP
with their console echoes intact, a stored list must be *refused* against the
wrong pattern at the route (not merely in a docstring), and the adopt gate must
hold at the server so no UI path can leak past it.

The `.rxt` peaks-block fixed point lives in ``test_textdoc`` beside the other
fixed-point properties; the engine's own editing semantics (carry of `origin`
and `excluded` across a refit, group windows, ghost-recompute scoping) are
asserted here through the verbs, which is the only door a client has.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from http.client import HTTPConnection

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.symmetry import generate_reflections
from rietx.gui import GuiSession, build_server
from rietx.gui.session import MAX_CANDIDATE_TICKS
from rietx.indexing.pairs import shift_template
from rietx.indexing.workflow import structure_from_candidate
from rietx.refine import _VERSION
from rietx.schemas.common import Provenance
from rietx.schemas.indexing import (
    INDEX_REFUTING_CAVEATS,
    PEAK_UNUSABLE_FLAGS,
    CellCandidate,
    IndexingResult,
)
from rietx.schemas.instrument import Instrument
from tests.test_project import _write_xye
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("gui-peaks")


# ----------------------------------------------------------------------
# fixtures — one live server over one project, module-scoped
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def pattern_file(tmp_path_factory):
    return _write_xye(tmp_path_factory.mktemp("peaks-data") / "synth.xye",
                      synthesize())


@pytest.fixture(scope="module")
def served(tmp_path_factory, pattern_file):
    structure, instrument = perturbed_models()
    root = tmp_path_factory.mktemp("peaks-proj") / "p.rex"
    project = rx.Project.create(root, pattern=pattern_file,
                                structure=structure, instrument=instrument)
    session = GuiSession(project,
                         state_dir=tmp_path_factory.mktemp("peaks-state"))
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever,
                     kwargs={"poll_interval": 0.02}, daemon=True).start()
    yield session, project, httpd.server_address[1]
    session.close()
    httpd.shutdown()


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def request(self, method: str, path: str, body: dict | None = None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=60)
        payload = None if body is None else json.dumps(body).encode()
        try:
            conn.request(method, path, body=payload,
                         headers={"Host": f"127.0.0.1:{self.port}",
                                  **({"Content-Type": "application/json"}
                                     if payload else {})})
            response = conn.getresponse()
            return response.status, json.loads(response.read() or b"{}")
        finally:
            conn.close()

    def get(self, path: str):
        return self.request("GET", path)

    def post(self, path: str, body: dict | None = None):
        return self.request("POST", path, body or {})


@pytest.fixture(scope="module")
def client(served):
    return Client(served[2])


def _wait_idle(client: Client, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, frame = client.get("/api/run/state")
        if frame["state"] == "idle":
            return frame
        time.sleep(0.05)
    raise AssertionError("run never returned to idle")


# ----------------------------------------------------------------------
# the verbs, through the wire
# ----------------------------------------------------------------------
def test_the_peak_verbs_round_trip_with_their_echoes(served, client):
    _, project, _ = served

    # before any pick: no list, but the raw pattern is there to draw — the
    # state an indexing project starts in
    status, empty = client.get("/api/peaks")
    assert status == 200 and empty["peaks"] is None
    assert len(empty["pattern"]["two_theta"]) > 100
    assert sorted(PEAK_UNUSABLE_FLAGS) == empty["unusable_flags"]

    status, picked = client.post("/api/peaks", {})
    assert status == 200
    assert picked["api_call"] == "session.pick_peaks(shoulders=True)"
    n = picked["n_total"]
    assert n >= 10 and picked["n_usable"] <= n
    assert (project.path / "peaks.json").is_file()
    # every group curve is drawable state: window, fit, residual strip
    assert picked["groups"] and all(
        len(g["two_theta"]) == len(g["y_fit"]) == len(g["delta"])
        for g in picked["groups"])

    # add — between the first two lines, which lands in fresh window territory
    # or an existing group; either way the component is the human's
    tts = [p["two_theta"] for p in picked["peaks"]]
    target = round((tts[0] + tts[1]) / 2, 3)
    status, added = client.post("/api/peaks/add", {"two_theta": target})
    assert status == 200 and added["n_total"] == n + 1
    assert added["api_call"] == f"session.add_peak({target:g})"
    manual = [p for p in added["peaks"] if p["origin"] == "manual"]
    assert len(manual) == 1

    # move — the drag verb; the landed position is fitted, hence *near* the ask
    i = manual[0]["index"]
    ask = manual[0]["two_theta"] + 0.03
    status, moved = client.post("/api/peaks/move",
                                {"index": i, "two_theta": ask})
    assert status == 200
    assert moved["api_call"] == f"session.move_peak({i}, {ask:g})"
    edited = [p for p in moved["peaks"] if p["origin"] == "edited"]
    assert len(edited) == 1
    assert abs(edited[0]["two_theta"] - ask) < 0.05

    # flag off and back on — excluded is the caller's decision, and the
    # overrule direction strips the unusable marks
    status, flagged = client.post("/api/peaks/flag",
                                  {"index": 0, "use_for_indexing": False})
    assert status == 200
    assert flagged["peaks"][0]["flags"] == ["excluded"]
    assert flagged["peaks"][0]["usable"] is False
    assert flagged["n_usable"] == moved["n_usable"] - 1
    _, restored = client.post("/api/peaks/flag",
                              {"index": 0, "use_for_indexing": True})
    assert restored["peaks"][0]["usable"] is True

    # an excluded mark survives its group's refit: the human owns it
    _, flagged = client.post("/api/peaks/flag",
                             {"index": 0, "use_for_indexing": False})
    g0 = flagged["peaks"][0]["group"]
    status, refit = client.post("/api/peaks/refit", {"group": g0})
    assert status == 200
    assert refit["api_call"] == f"session.refit_group({g0})"
    survivors = [p for p in refit["peaks"] if p["group"] == g0]
    assert survivors and "excluded" in survivors[0]["flags"]
    client.post("/api/peaks/flag", {"index": 0, "use_for_indexing": True})

    # remove — back to where the add left off
    j = [p for p in refit["peaks"] if p["origin"] == "edited"][0]["index"]
    status, removed = client.post("/api/peaks/remove", {"index": j})
    assert status == 200 and removed["n_total"] == n
    assert removed["api_call"] == f"session.remove_peak({j})"

    # a bad index is a 404 naming the list's size, not a 500
    status, refused = client.post("/api/peaks/remove", {"index": 10_000})
    assert status == 404 and refused["error"]["code"] == "NOT_FOUND"


def test_a_peak_list_keyed_to_one_pattern_is_refused_against_another(
        served, tmp_path_factory):
    """The `data_fingerprint` key is a refusal, not a decoration."""
    _, project, _ = served
    assert (project.path / "peaks.json").is_file()

    other = synthesize()
    other.intensity = np.asarray(other.intensity) * 1.07 + 3.0
    other_file = _write_xye(tmp_path_factory.mktemp("peaks-b") / "other.xye",
                            other)
    structure, instrument = perturbed_models()
    root = tmp_path_factory.mktemp("peaks-b-proj") / "b.rex"
    b = rx.Project.create(root, pattern=other_file, structure=structure,
                          instrument=instrument)
    shutil.copyfile(project.path / "peaks.json", b.path / "peaks.json")

    session = GuiSession(b, state_dir=tmp_path_factory.mktemp("peaks-b-state"))
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever,
                     kwargs={"poll_interval": 0.02}, daemon=True).start()
    try:
        status, payload = Client(httpd.server_address[1]).get("/api/peaks")
        assert status == 409
        assert payload["error"]["code"] == "PEAKS_WRONG_PATTERN"
        assert "different pattern" in payload["error"]["message"]
    finally:
        session.close()
        httpd.shutdown()


def test_mutating_peak_verbs_refuse_while_a_run_is_in_flight(served, client):
    session, _, _ = served
    with session._cond:
        session._state = "running"
    try:
        status, payload = client.post("/api/peaks/add", {"two_theta": 12.0})
        assert status == 409
        assert payload["error"]["code"] == "RUN_IN_FLIGHT"
        # the read stays open — it serves a project artifact, not the model
        assert client.get("/api/peaks")[0] == 200
    finally:
        with session._cond:
            session._state = "idle"


# ----------------------------------------------------------------------
# indexing: the run machine, the answer, the gate
# ----------------------------------------------------------------------
def test_index_rides_the_run_state_machine(served, client):
    # Flag the list down to four usable lines — below MIN_LINES_PER_DOF in
    # every system — so the quality gate still abstains and the run completes
    # in one poll.  Since WP-1043 a short-but-searchable list (this pattern's
    # 15 usable lines included) is *searched* over the systems its line count
    # supports; that path belongs to the acceptance suite, not to the run
    # machine, and unbudgeted it would outlive every timeout here.
    _, doc = client.get("/api/peaks")
    usable = [p["index"] for p in doc["peaks"] if p["usable"]]
    assert len(usable) > 4
    for i in usable[4:]:
        status, _flagged = client.post(
            "/api/peaks/flag", {"index": i, "use_for_indexing": False})
        assert status == 200

    status, frame = client.post("/api/index", {})
    assert status == 200 and frame["run"]["kind"] == "index"
    frame = _wait_idle(client)
    # the flagged-down list abstains at the quality gate — abstention is a
    # *result*, and the machine must report a completed run, not a failure
    assert frame["run"]["status"] == "completed"
    assert frame["run"]["node_id"] is None  # an indexing run commits no node

    status, answer = client.get("/api/index/result")
    assert status == 200
    assert answer["refuting_caveats"] == sorted(INDEX_REFUTING_CAVEATS)
    assert isinstance(answer["result"]["candidates"], list)
    assert len(answer["adopt"]) == len(answer["result"]["candidates"])

    # nothing to adopt on an abstained result — and the refusal is addressed
    status, refused = client.post("/api/index/adopt", {"candidate": 0})
    assert status in (404, 409)


def _candidate(confidence: str, caveats: list[str]) -> CellCandidate:
    return CellCandidate(
        cell=(4.1568, 4.1568, 4.1568, 90.0, 90.0, 90.0),
        cell_esd=(1e-4,) * 3 + (0.0,) * 3,
        system="cubic", centring="P", lattice_group="P m -3 m",
        volume=71.8, n_indexed=20, n_lines=20,
        confidence=confidence, confidence_caveats=caveats)


def _answer(*candidates: CellCandidate) -> IndexingResult:
    return IndexingResult(
        candidates=list(candidates), engines_run=["dichotomy", "trial_error"],
        systems_searched=["cubic"], validated=True, wavelength=1.5406,
        n_usable_lines=20,
        provenance=Provenance(package_version=_VERSION,
                              created_utc="2026-07-31T00:00:00Z"))


def test_any_candidate_can_be_adopted_and_an_unpicked_one_records_why(
        served, client):
    """Yue's ruling B (2026-11-08, WP-2124): a person may adopt any candidate.

    The medium candidate is the *normal* real-data outcome
    (``shift_allowance_assumed``), and on FAP nothing reaches ``high`` at all,
    so a gate on Adopt left the right cell unreachable.  The gate is still
    asked: the arm says the row is not its pick and why, and the adoption
    writes the same sentence, grade and caveats included, into the node.
    """
    session, project, _ = served
    medium = _candidate("medium", ["shift_allowance_assumed"])
    with session._cond:
        session._index_result = _answer(medium)

    status, answer = client.get("/api/index/result")
    assert status == 200
    why = answer["adopt"][0]["why"]
    assert answer["adopt"] == [{"picked": False, "why": why}]
    assert why == ("not best_or_none()'s pick: grade 'medium' "
                   "(shift_allowance_assumed)")

    status, adopted = client.post("/api/index/adopt", {"candidate": 0})
    assert status == 200, adopted
    assert adopted["picked"] is False
    node = project.history.nodes[adopted["node_id"]]
    assert node.action.kind == "edit_model"
    assert node.label.startswith("adopted indexed cell 4.1568")
    assert node.label.endswith(f"; {why}")

    # two high candidates: no singleton, so neither is the pick, and the
    # sentence says why a `high` row was still not picked
    with session._cond:
        session._index_result = _answer(_candidate("high", []),
                                        _candidate("high", []))
    _, answer = client.get("/api/index/result")
    assert [a["picked"] for a in answer["adopt"]] == [False, False]
    assert answer["adopt"][1]["why"] == (
        "not best_or_none()'s pick: grade 'high'; more than one candidate "
        "reached 'high'")
    status, adopted = client.post("/api/index/adopt", {"candidate": 1})
    assert status == 200 and adopted["picked"] is False
    assert project.history.nodes[adopted["node_id"]].label.endswith(
        answer["adopt"][1]["why"])


def test_adopting_the_one_high_candidate_is_a_model_edit(served, client):
    session, project, _ = served
    with session._cond:
        session._index_result = _answer(_candidate("high", []))

    _, answer = client.get("/api/index/result")
    assert answer["adopt"] == [{"picked": True, "why": ""}]

    head_before = project.refinement._head_id
    status, adopted = client.post("/api/index/adopt", {"candidate": 0})
    assert status == 200
    assert adopted["picked"] is True
    assert adopted["api_call"] == "session.adopt_candidate(0)"
    assert adopted["node_id"] and adopted["node_id"] != head_before
    # a bare cell is a Le Bail scaffold: dummy atom, absence-free group, and
    # the document's mode follows — a Rietveld fit over it is not offered
    assert adopted["mode"] == "lebail"
    phase = adopted["structure"]["phases"][0]
    assert phase["space_group"] == "P m -3 m"
    assert len(phase["atoms"]) == 1
    node = project.history.nodes[adopted["node_id"]]
    assert node.action.kind == "edit_model"
    # the gate's own pick carries no "not picked" sentence
    assert node.label == ("adopted indexed cell 4.1568 4.1568 4.1568 Å "
                          "(cubic, P m -3 m)")


# ----------------------------------------------------------------------
# the extinction screen (WP-1025 served)
# ----------------------------------------------------------------------
def test_extinction_screen_rides_the_run_machine_and_ranks_classes(
        served, client):
    """A real ``determine_extinction_symbol`` run over the wire.

    The injected candidate is the synthetic pattern's **true** cell (LaB6,
    cubic P), so the screen is meaningful and cheap: one profile fit, then one
    Le Bail per cubic-P class.  Deliberately *not* gated on the adopt verdict
    — a screen is how a ``medium`` candidate (the normal real-data outcome)
    gets its space-group question answered before anything is at stake.
    """
    session, _, _ = served
    with session._cond:
        session._index_result = _answer(
            _candidate("medium", ["shift_allowance_assumed"]))
        session._extinction = None

    # nothing has run yet — and the refusal says what to POST
    status, refused = client.get("/api/index/extinction")
    assert status == 409
    assert refused["error"]["code"] == "NO_EXTINCTION_RESULT"

    # a candidate the result does not have is addressed, not silently clamped
    status, refused = client.post("/api/index/extinction", {"candidate": 7})
    assert status == 404

    status, frame = client.post("/api/index/extinction", {"candidate": 0})
    assert status == 200 and frame["run"]["kind"] == "extinction"
    frame = _wait_idle(client, timeout=180.0)
    assert frame["run"]["status"] == "completed"
    assert frame["run"]["node_id"] is None  # a screen commits nothing

    status, answer = client.get("/api/index/extinction")
    assert status == 200
    assert answer["candidate"] == 0
    screen = answer["result"]
    assert screen["n_classes"] >= 2  # cubic P has more than one class
    assert screen["n_screened"] >= 1
    ranked = screen["candidates"]
    assert ranked, "the screen must rank classes, not conclude nothing"
    for cls in ranked:
        # every class lists *all* its space groups — the shape rule: the
        # extinction symbol is measurable, one space group is not
        assert isinstance(cls["space_groups"], list) and cls["space_groups"]
    # the served best is the package's own gate, or None — never a local pick
    if answer["best"] is not None:
        assert 0 <= answer["best"] < len(ranked)
        assert not ranked[answer["best"]]["refuted"]


def test_extinction_screen_is_cleared_when_the_candidates_renumber(
        served, client):
    """A new indexing run renumbers the candidates; a kept screen would be
    served against the wrong cell — the same staleness rule as peaks.json.

    Reads two preconditions off the tests above it — the held screen and the
    picked peak list the search runs on — which is this module's shape: one
    server, one project, tests in order.  A selection that runs it alone
    therefore fails, once on the screen and again on the search's wall clock,
    so a `-k` narrower than the module has to avoid it (WP-1211 met both).
    """
    status, _ = client.get("/api/index/extinction")
    assert status == 200  # the previous test's screen is still there

    status, _ = client.post("/api/index", {})
    assert status == 200
    _wait_idle(client, timeout=120.0)

    status, refused = client.get("/api/index/extinction")
    assert status == 409
    assert refused["error"]["code"] == "NO_EXTINCTION_RESULT"


# ----------------------------------------------------------------------
# one candidate's predicted lines, for the plot overlay (WP-1211)
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def ticks_served(tmp_path_factory):
    """A second server, because the overlay's claims need an instrument and a
    range the module fixture does not have.

    A **doublet**, so "every emission line" is a countable claim rather than a
    sentence; a non-zero ``zero_shift``, so "the instrument's shift is not
    added" is a test that can fail; and a lab-width 5-120° range, because the
    synthetic pattern's 3-24° at λ = 0.4139 Å leaves a corundum cell four
    visible lines to be asserted about.  Nothing here is fitted — the route
    reads the pattern's 2θ extent and the source's wavelengths and no more —
    so the intensities are flat on purpose.
    """
    tt = np.arange(5.0, 120.0, 0.02)
    data = rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.full(len(tt), 100.0).tolist())
    path = _write_xye(tmp_path_factory.mktemp("ticks-data") / "flat.xye", data)
    structure, _ = perturbed_models()
    instrument = Instrument.bragg_brentano(radiation="CuKa")
    instrument.zero_shift.value = 0.05
    root = tmp_path_factory.mktemp("ticks-proj") / "p.rex"
    project = rx.Project.create(root, pattern=path, structure=structure,
                                instrument=instrument)
    session = GuiSession(project,
                         state_dir=tmp_path_factory.mktemp("ticks-state"))
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever,
                     kwargs={"poll_interval": 0.02}, daemon=True).start()
    yield session, project, Client(httpd.server_address[1])
    session.close()
    httpd.shutdown()
    httpd.server_close()


def _corundum() -> CellCandidate:
    """SRM 676a corundum — trigonal R, so the drawn set is a *centred* lattice's
    and a primitive enumeration would be caught."""
    return CellCandidate(
        cell=(4.7587, 4.7587, 12.9929, 90.0, 90.0, 120.0),
        cell_esd=(1e-4, 1e-4, 3e-4, 0.0, 0.0, 0.0),
        system="trigonal", centring="R", lattice_group="R -3 m :H",
        volume=254.8, n_indexed=20, n_lines=20,
        confidence="medium", confidence_caveats=["shift_allowance_assumed"])


def _expected_ticks(project, candidate) -> list[float]:
    """The same question asked of ``generate_reflections`` directly.

    Deliberately *not* a re-implementation of the verb: the range, the symbol
    and the wavelengths are read from the same three places, and what is being
    checked is that the route adds nothing to them.
    """
    cell = tuple(candidate.cell)
    symbol = structure_from_candidate(candidate).phases[0].space_group
    tt_all = np.asarray(project.data.two_theta, dtype=float)
    lo, hi = float(tt_all.min()), float(tt_all.max())
    out: list[float] = []
    for line in project.refinement.instrument.source.lines:
        lam = line.wavelength.value
        refl = generate_reflections(symbol, cell, lam,
                                    two_theta_max=hi, two_theta_min=lo)
        tt = refl.two_theta(cell, lam)
        keep = np.isfinite(tt) & (tt >= lo) & (tt <= hi)
        out.extend(round(float(v), 4) for v in tt[keep])
    return sorted(out)


def test_candidate_ticks_are_generate_reflections_over_the_pattern(
        ticks_served):
    """The route adds nothing to the cell but the emission lines it was given.

    The comparison is against ``generate_reflections`` itself rather than
    against stored numbers: what could go wrong here is a *frame* (an extra
    zero shift, the primary line only, a space group with absences), and each
    of those changes the answer by an amount a stored list would simply have
    been updated to.
    """
    session, project, client = ticks_served
    with session._cond:
        session._index_result = None

    # nothing has run: the refusal says what to POST, and it is the *reading*
    # 409, not the run-in-flight one
    status, refused = client.get("/api/index/ticks?candidate=0")
    assert status == 409
    assert refused["error"]["code"] == "NO_INDEX_RESULT"

    with session._cond:
        session._index_result = _answer(_corundum())

    status, answer = client.get("/api/index/ticks?candidate=0")
    assert status == 200, answer
    # the absence-free lattice group the Le Bail validation was scored against,
    # never a space group carrying reflection conditions
    assert answer["space_group"] == "R -3 m :H"
    expected = _expected_ticks(project, _corundum())
    assert answer["two_theta"] == expected
    assert answer["n_total"] == answer["n_returned"] == len(expected)
    assert len(answer["hkl"]) == len(answer["line"]) == len(expected)

    # both emission lines, in the proportion two lines of one lattice give —
    # the Kα2 half is what stops the overlay reading as an unindexed line per
    # doublet (the rule ``RefinementResult.ticks`` states one rank up)
    assert sorted(set(answer["line"])) == [0, 1]
    assert answer["line"].count(0) == answer["line"].count(1) == len(expected) // 2

    # every drawn line is inside the measured pattern, since that is the axis
    # it will be drawn on
    tt_all = np.asarray(project.data.two_theta, dtype=float)
    assert min(answer["two_theta"]) >= tt_all.min()
    assert max(answer["two_theta"]) <= tt_all.max()

    # hkl are the Laue-unique representatives, so no reflection is drawn twice
    # for one line
    first = [tuple(h) for h, ln in zip(answer["hkl"], answer["line"]) if ln == 0]
    assert len(set(first)) == len(first)


def test_candidate_ticks_carry_the_cell_s_shift_and_not_the_instrument_s(
        ticks_served):
    """Two shifts exist here and exactly one of them belongs on these lines.

    The instrument's ``zero_shift`` does not: indexing fits the metric to the
    peak list's raw 2θ, so the cell already reproduces observed positions and
    adding it would count it twice.  The candidate's own fitted template does:
    ``refine_candidate`` fits to ``2θ_obs − c·T(θ)``, so drawing on the observed
    axis means adding ``c·T`` back on.
    """
    session, project, client = ticks_served
    assert project.refinement.instrument.zero_shift.value == 0.05

    plain = _corundum()
    shifted = _corundum()
    shifted.shift_template = "cos_theta"
    shifted.shift_coefficient = 0.02
    with session._cond:
        session._index_result = _answer(plain, shifted)

    _, a = client.get("/api/index/ticks?candidate=0")
    _, b = client.get("/api/index/ticks?candidate=1")

    # the instrument's 0.05° is nowhere in the unshifted answer
    assert a["shift_template"] is None and a["shift_coefficient"] == 0.0
    assert a["two_theta"] == _expected_ticks(project, plain)

    assert b["shift_template"] == "cos_theta" and b["shift_coefficient"] == 0.02
    base = np.asarray(a["two_theta"])
    moved = base + 0.02 * shift_template("cos_theta", base)
    assert len(b["two_theta"]) == len(base)  # nothing crossed the range edge
    assert b["two_theta"] == pytest.approx(moved, abs=1e-4)
    # and it is a real displacement, not a rounding artefact: cos θ runs from
    # nearly 1 at the low-angle end down towards zero, so the correction shrinks
    assert moved[0] - base[0] > moved[-1] - base[-1] > 0.0


def test_candidate_ticks_are_thinned_by_rank_and_say_so(ticks_served):
    """A cell predicting more lines than can be drawn is sampled, never cut off.

    ``max_d_axis`` admits a 25 Å triclinic candidate, which predicts 92 103
    Laue-unique positions over this 5-120° range at the Cu doublet — megabytes
    of JSON drawn as a solid block of ink.  Thinning by **rank in 2θ** keeps the
    property the picture is read for (a dense stretch keeps proportionally more
    lines than a sparse one) and ``n_total`` is what stops the sample reading as
    coverage.
    """
    session, _project, client = ticks_served
    dense = CellCandidate(
        cell=(25.0, 25.0, 25.0, 88.0, 92.0, 95.0), cell_esd=(0.0,) * 6,
        system="triclinic", centring="P", lattice_group="P -1",
        volume=15551.0, n_indexed=20, n_lines=20)
    with session._cond:
        session._index_result = _answer(dense)

    status, answer = client.get("/api/index/ticks?candidate=0")
    assert status == 200, answer
    assert answer["n_total"] > MAX_CANDIDATE_TICKS
    # the whole budget, not half of it: spacing the picks over the ranks rather
    # than taking every k-th is what keeps 2001 lines from coming back as 1001
    assert answer["n_returned"] == MAX_CANDIDATE_TICKS
    assert len(answer["two_theta"]) == answer["n_returned"]
    assert len(answer["hkl"]) == len(answer["line"]) == answer["n_returned"]

    # the whole range is still covered — a head-of-list truncation would leave
    # the high-angle half empty, which reads as "this cell predicts nothing
    # there" and is the one thing the overlay must not say
    tt = answer["two_theta"]
    assert tt == sorted(tt)
    assert tt[0] < 10.0 and tt[-1] > 115.0


def test_candidate_ticks_past_the_end_are_named_not_clamped(ticks_served):
    """The same 404 every candidate-addressing verb gives, in one sentence."""
    session, _project, client = ticks_served
    with session._cond:
        session._index_result = _answer(_corundum())

    status, refused = client.get("/api/index/ticks?candidate=7")
    assert status == 404
    assert refused["error"]["code"] == "NOT_FOUND"
    assert refused["error"]["where"] == ["candidate"]
    assert "the result has 1" in refused["error"]["message"]

    # and the extinction screen refuses with the same words, because they are
    # now the same sentence
    status, screened = client.post("/api/index/extinction", {"candidate": 7})
    assert status == 404
    assert screened["error"]["message"] == refused["error"]["message"]


# ----------------------------------------------------------------------
# a project with no phase at all (WP-1207)
# ----------------------------------------------------------------------
def test_a_pattern_only_project_picks_peaks_indexes_adopts_and_only_then_fits(
        tmp_path_factory, pattern_file):
    """The whole loop the pattern-only project exists to make reachable.

    A project created with no structure: peak picking works, indexing works,
    adopting a candidate gives it its phase — and only *then* does a fit run.
    Before that the run is refused at the route, by name, rather than started
    and left to converge on the background (the WP-1207 audit measured that
    fit at Rwp 0.9637, reported ``converged``).

    A candidate is injected the way every other adopt test here does it: what
    is under test is the loop, and a real search over this pattern belongs to
    the acceptance suite.
    """
    root = tmp_path_factory.mktemp("blank-proj") / "unknown.rex"
    project = rx.Project.create(root, pattern=pattern_file,
                                instrument=perturbed_models()[1])
    assert project.refinement.structure.phases == []
    session = GuiSession(project,
                         state_dir=tmp_path_factory.mktemp("blank-state"))
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever,
                     kwargs={"poll_interval": 0.02}, daemon=True).start()
    client = Client(httpd.server_address[1])
    try:
        # the document says so, which is what disables Run in the client
        assert client.get("/api/project")[1]["n_phases"] == 0

        # …and the run is refused before it starts, not inside the worker
        status, refused = client.post("/api/run", {"kind": "fit"})
        assert status == 400, refused
        assert refused["error"]["code"] == "NO_PHASES"
        assert client.get("/api/run/state")[1]["state"] == "idle"

        # peak picking needs no phase
        status, doc = client.post("/api/peaks", {})
        assert status == 200, doc
        assert len([p for p in doc["peaks"] if p["usable"]]) > 4

        # nor does the 3D refusal read as a bad index any more
        status, no3d = client.get("/api/structure3d")
        assert status == 404
        assert "no phase to draw yet" in no3d["error"]["message"]

        # the extinction screen needs no phase: it fits its own Le Bail
        # models from the candidate (WP-2124; WP-1207 had refused it here)
        with session._cond:
            session._index_result = _answer(_candidate("high", []))
        status, frame = client.post("/api/index/extinction", {"candidate": 0})
        assert status == 200, frame
        frame = _wait_idle(client, timeout=180.0)
        assert frame["run"]["status"] == "completed", frame
        status, screened = client.get("/api/index/extinction")
        assert status == 200 and screened["result"]["candidates"]

        # adopt the cell an indexing run found
        status, adopted = client.post("/api/index/adopt", {"candidate": 0})
        assert status == 200, adopted
        assert adopted["mode"] == "lebail"
        assert len(adopted["structure"]["phases"]) == 1
        assert client.get("/api/project")[1]["n_phases"] == 1

        # and now it fits
        status, run = client.post("/api/run", {"kind": "fit"})
        assert status == 200, run
        frame = _wait_idle(client, timeout=180.0)
        assert frame["run"]["status"] == "converged", frame
        assert frame["run"]["rwp"] < 0.2, frame
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


# ----------------------------------------------------------------------
# the pick's three options reach the route (WP-2124)
# ----------------------------------------------------------------------
def test_the_pick_route_takes_the_range_and_the_contamination_marks(
        tmp_path_factory, pattern_file):
    """``pick_peaks``'s three options, through the wire, and kept by the list.

    The route took ``shoulders`` alone: the range came from the project's fit
    limits and ``flag_contamination`` was library-only (the GUI port's Pick
    step offers all three).  The list records what it was picked with, and a
    session opened later builds its editor from that record, not from the
    project's limits, so a refit sees the detection the list came from.
    """
    structure, instrument = perturbed_models()
    root = tmp_path_factory.mktemp("pick-opts") / "p.rex"
    project = rx.Project.create(root, pattern=pattern_file,
                                structure=structure, instrument=instrument)
    session = GuiSession(project, state_dir=tmp_path_factory.mktemp("pick-st"))
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever,
                     kwargs={"poll_interval": 0.02}, daemon=True).start()
    client = Client(httpd.server_address[1])
    try:
        # a bad range is refused in the project's own words, and named
        status, refused = client.post("/api/peaks",
                                      {"two_theta_range": [60, 20]})
        assert status == 400, refused
        assert refused["error"]["where"] == ["two_theta_range"]
        assert "inverted" in refused["error"]["message"]
        status, refused = client.post("/api/peaks",
                                      {"two_theta_range": ["a", 20]})
        assert status == 400 and "two numbers" in refused["error"]["message"]
        # a range holding too few channels to pick in is the caller's, not a 500
        status, refused = client.post("/api/peaks",
                                      {"two_theta_range": [500, 600]})
        assert status == 400, refused
        assert refused["error"]["where"] == ["two_theta_range"]
        # a flag is a boolean, never coerced: bool("false") would be True
        for key in ("shoulders", "flag_contamination"):
            status, refused = client.post("/api/peaks", {key: "false"})
            assert status == 400, refused
            assert refused["error"]["where"] == [key]

        status, doc = client.post("/api/peaks", {
            "two_theta_range": [20, 60], "shoulders": False,
            "flag_contamination": False})
        assert status == 200, doc
        assert doc["api_call"] == (
            "session.pick_peaks(shoulders=False, two_theta_range=(20, 60), "
            "flag_contamination=False)")
        assert doc["pick_options"] == {"two_theta_range": [20.0, 60.0],
                                       "shoulders": False,
                                       "flag_contamination": False}
        tts = [p["two_theta"] for p in doc["peaks"]]
        assert tts and 20.0 <= min(tts) and max(tts) <= 60.0
        assert doc["two_theta_min"] >= 20.0 and doc["two_theta_max"] <= 60.0

        # the `.rxt` quotes the same call
        assert doc["api_call"] in client.get("/api/textdoc")[1]["text"]

        # a fresh session (the app reopened) refits under the stored options
        fresh = GuiSession(rx.Project.open(root),
                           state_dir=tmp_path_factory.mktemp("pick-st2"))
        try:
            editor = fresh._peak_editor()
            assert editor.two_theta_range == (20.0, 60.0)
            assert editor.shoulders is False
            assert editor.flag_contamination is False
        finally:
            fresh.close()

        # the defaults still read as they always did
        status, doc = client.post("/api/peaks", {})
        assert doc["api_call"] == "session.pick_peaks(shoulders=True)"
        assert doc["pick_options"]["flag_contamination"] is True
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()
