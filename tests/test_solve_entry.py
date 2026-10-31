"""The solve entry point, its answer type, its events and #998's checkpoint (#562 S2b).

Two cases, both synthetic or public: the acridine-shaped rigid fragment of
``tests/test_solve_engine.py`` (P2₁/n, simulated Cu Kα₁,₂ pattern) for the
mechanics, and NAC (11-BM, public) from its Pawley intensities for the
assignment race, which places the composition on every site-class assignment
and never reads the deposited one.

The resume acceptance is #998's, as the issue accepted it on 2026-10-16: a run
stopped by its cancel token at a deterministic point (a ``solve_step`` of a
named unit, never the wall clock) and resumed from its checkpoint returns the
uninterrupted run's candidates and records, compared as the serialised
:class:`~rietx.solve.solution.SolutionResult` (``comparable_json``: all of it
but the wall clock and the provenance).
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import sys
import typing
import urllib.request
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import runs
from rietx.history.events import KIND_SINCE, EventKind, EventRecord, read_events
from rietx.optimize.cancel import CancelToken
from rietx.solve import cluster as cl
from rietx.solve import engines as en
from rietx.solve import workflow as wf
from rietx.solve.chemistry import PriorWeights, SolvePriors
from rietx.solve.cost import SolveCost
from rietx.solve.engines import SolveSpec
from rietx.solve.moves import FragmentUnit, SearchSpace
from rietx.solve.solution import SolutionResult, SolveSpecSpec

sys.path.insert(0, str(Path(__file__).parent))
from test_acceptance_nac import build_nac_inputs  # noqa: E402
from test_solve_engine import (  # noqa: E402
    CLUSTER_TOL,
    EXCHANGE,
    N_RANDOM,
    NAC_COMPOSITION,
    NAC_LIMITS,
    POLISH_ITER,
    REPLICAS,
    SPAN,
    STEP,
    SWAP_EVERY,
    _acr_phase,
    _acr_truth,
    _priors,
    _simulate,
    acridine,
)

pytestmark = pytest.mark.xdist_group("solve-entry")

#: Every search setting, stated: the engine chooses none (``solve.engines``'
#: docstring).  The ladder, move and clustering values are the ones S2a's tests
#: declare beside their measurements (``tests/test_solve_engine.py``).
SETTINGS = dict(engine="tempering", replicas=REPLICAS, race_sweeps=2000, span=SPAN, step=STEP,
                swap_every=SWAP_EVERY, exchange=EXCHANGE, n_random=N_RANDOM,
                cluster_tol=CLUSTER_TOL, polish_maxiter=POLISH_ITER, seed=0)
#: The NAC biso the composition's free sites are placed with (Å²).
NAC_BISO = 1.0


def _spec(**kw) -> SolveSpec:
    return SolveSpec(**{**SETTINGS, **kw})


#: The mechanics run: two seeds and one control seed of 2 000 sweeps, so every
#: unit crosses one rebuild boundary (tempering.REFRESH_EVERY = 1000) inside it.
ACR_SPEC = _spec(seeds=(0, 1), control_seeds=(0,), sweeps=2000, heartbeat_sweeps=250,
                 checkpoint_every_s=0.0)
GROUP = "P 1 21/n 1"


# ===================================================================================
# fixtures
# ===================================================================================
class Acr:
    def __init__(self):
        space = SearchSpace([FragmentUnit(acridine(), biso=3.0)], _acr_phase())
        u = _acr_truth(space)
        self.ins = rx.Instrument.bragg_brentano(radiation="CuKa")
        self.ins.source.dispersion = None
        model, v = _simulate(space.search_phase(space.xyz(u)[0]), self.ins)
        self.cost = SolveCost.from_model(model, v)
        self.phase = _acr_phase()
        self.truth = space.xyz(u)[0]

    def solve(self, spec=ACR_SPEC, **kw):
        kw.setdefault("telemetry", False)
        return wf.solve_structure(self.cost, self.phase, instrument=self.ins, priors=_priors(),
                                  units=[FragmentUnit(acridine(), biso=3.0)], spec=spec, **kw)


@pytest.fixture(scope="module")
def acr():
    return Acr()


@pytest.fixture(scope="module")
def acr_run(acr, tmp_path_factory):
    """The uninterrupted run, recorded (``rietx watch``'s directory) and streamed."""
    root = tmp_path_factory.mktemp("acr_runs")
    events: list[dict] = []
    was = runs.set_enabled(True)
    try:
        res = acr.solve(events=events.append, telemetry=root, label="acr")
    finally:
        runs.set_enabled(was)
    return res, events, root


def _cancel_at(token, unit_prefix: str, sweep: int):
    def cb(event):
        d = event["data"]
        if (event["kind"] == "solve_step" and d["unit"].startswith(unit_prefix)
                and d["sweep"] == sweep):
            token.cancel()
    return cb


class Nac:
    def __init__(self):
        from rietx.crystallography.site_classes import site_assignments, site_classes
        from rietx.crystallography.symmetry import resolve_group, site_orbit

        data, st, ins = build_nac_inputs()
        ref = rx.Refinement(st, ins, history=False)
        res = ref.fit(data, mode="pawley", two_theta_limits=NAC_LIMITS, telemetry=False)
        assert res.status == "converged"
        self.cost = SolveCost.from_pawley(ref, data)
        self.phase = ref.fitted_structure.phases[0]
        self.ins = ref.fitted_instrument
        group = resolve_group(self.phase.space_group, self.phase.symmetry_operations)
        classes = site_classes(group)
        truth = {a.label: np.array([a.x.value, a.y.value, a.z.value]) for a in self.phase.atoms}
        want = sorted((a.species, next(i for i, c in enumerate(classes) if c.multiplicity
                                       == site_orbit(group, truth[a.label]).multiplicity))
                      for a in self.phase.atoms)
        self.deposited = [i for i, s in enumerate(site_assignments(classes, NAC_COMPOSITION))
                          if sorted(s.sites) == want]
        self.truth = [(a.species, truth[a.label]) for a in self.phase.atoms]

    def solve(self, spec, **kw):
        kw.setdefault("telemetry", False)
        return wf.solve_structure(self.cost, self.phase, instrument=self.ins, priors=_priors(),
                                  composition=NAC_COMPOSITION, spec=spec, biso=NAC_BISO, **kw)

    def rmsd(self, cand) -> float:
        pool: dict[str, list] = {}
        for s, x in self.truth:
            pool.setdefault(s, []).append(x)
        xt = np.array([pool[s].pop(0) for s in cand.species])
        eq = wf._equivalence(self.phase, self.phase.space_group)
        return cl.align(eq, xt, np.array(cand.xyz), list(cand.species)).rmsd


@pytest.fixture(scope="module")
def nac():
    return Nac()


# ===================================================================================
# the answer type
# ===================================================================================
def test_the_answer_carries_no_structure_and_no_grade(acr_run):
    res = acr_run[0]
    assert "structure" not in SolutionResult.model_fields
    assert not hasattr(res, "structure")
    assert res.candidates and all(c.structure.phases[0].atoms for c in res.candidates)
    # machinery only (yue-here/rietx#1224): no grade, no verdict, no singleton accessor
    fields = set(SolutionResult.model_fields) | set(type(res.candidates[0]).model_fields)
    assert not fields & {"confidence", "confidence_caveats", "grade", "caveats",
                         "thresholds_version", "preset"}
    assert not hasattr(res, "best_or_none")


def test_the_candidates_carry_the_engines_evidence(acr, acr_run):
    """The positive arm (two seeds reach the truth), then the same records
    with one seed's dropped: the evidence moves with them, nothing judges."""
    res = acr_run[0]
    lead = res.candidates[0]
    assert lead.n_finders == 2 and lead.seeds == [0, 1]
    assert cl.align(wf._equivalence(acr.phase, GROUP), acr.truth, np.array(lead.xyz),
                    lead.species).rmsd < 0.10
    assert lead.chi2_ratio == pytest.approx(lead.chi2_data / res.chi2_floor, rel=1e-15)
    # the control arm ran: its best reads within the clustering tolerance here
    assert lead.control_chi2_data is not None and lead.control_rmsd_ang is not None
    assert lead.control_rmsd_ang < SETTINGS["cluster_tol"]
    assert not lead.partial and not res.partial
    assert res.spec.to_spec() == ACR_SPEC                     # the result records the spec
    one = wf._assemble(
        phase=res.phase, spec=res.spec.to_spec(), n_reflections=res.n_reflections,
        floor=res.chi2_floor, groups=res.space_groups_searched, races=res.races,
        layouts=res.layouts, records=[r for r in res.records if r.seed_index == 0
                                      or r.kind == "control"], status="done",
        units_not_run=[], timings={}, resumed=False, provenance=res.provenance)
    assert one.candidates[0].n_finders == 1 and one.candidates[0].seeds == [0]


def test_a_run_with_no_control_seeds_reports_no_control_evidence(acr):
    res = acr.solve(_spec(seeds=(0,), control_seeds=(), sweeps=1000))
    assert res.candidates
    assert all(c.control_rmsd_ang is None and c.control_chi2_data is None
               for c in res.candidates)
    assert all(c.n_finders == 1 for c in res.candidates)


def test_the_control_seeds_run_prior_off_and_feed_the_rank(acr, acr_run, monkeypatch):
    """The control units run with every prior at zero weight, and their
    clusters reach ``rank(control=…)``: a planted control leader that is
    structurally different and better reads as such in the candidate's
    evidence, and nothing caps or grades it."""
    res = acr_run[0]
    ctrl = [r for r in res.records if r.kind == "control"]
    assert [r.seed_index for r in ctrl] == [0] and all(r.polished for r in ctrl)
    seen = {}
    real = cl.rank

    def spy(clusters, **kw):
        seen["control"] = kw.get("control")
        return real(clusters, **kw)

    monkeypatch.setattr(cl, "rank", spy)
    lead = res.candidates[0]
    moved = np.array(lead.xyz) + np.array([0.11, 0.0, 0.0])      # not an equivalent copy
    fake = [r.model_copy(update={"polished": [p.model_copy(update={
        "xyz": moved.tolist(), "chi2": 0.5 * lead.chi2_data, "j": 0.0}) for p in r.polished]})
        if r.kind == "control" else r for r in res.records]
    got = wf._assemble(
        phase=res.phase, spec=res.spec.to_spec(), n_reflections=res.n_reflections,
        floor=res.chi2_floor, groups=res.space_groups_searched, races=res.races,
        layouts=res.layouts, records=fake, status="done", units_not_run=[], timings={},
        resumed=False, provenance=res.provenance)
    assert seen["control"] and seen["control"][0].seeds == (0,)
    c0 = got.candidates[0]
    assert c0.control_chi2_data == pytest.approx(0.5 * lead.chi2_data, rel=1e-12)
    assert c0.control_rmsd_ang > SETTINGS["cluster_tol"]
    assert c0.xyz == lead.xyz and c0.rank == 1                # the evidence moved, nothing else
    # the control problem's clash term is weighted zero, the prior-on one's is not
    searches = wf._searches(acr.cost, acr.phase, acr.ins, _priors(), [GROUP], None,
                            [FragmentUnit(acridine(), biso=3.0)], ACR_SPEC, 1.0)
    assert searches[0].problem.clash.weight > 0.0 == searches[0].control.clash.weight


def test_the_entry_point_chooses_no_search_setting(acr):
    """Every search setting is required (no default anywhere: the spec, its
    request chair, the entry point), and an impossible one is refused by
    name before any unit runs."""
    required = {f.name for f in dataclasses.fields(SolveSpec)
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING}
    assert required == set(SETTINGS) | {"seeds", "control_seeds", "sweeps"}
    assert required >= {"span", "step", "swap_every", "exchange", "n_random", "cluster_tol",
                        "polish_maxiter"}
    full = {**SETTINGS, "seeds": (0,), "control_seeds": (), "sweeps": 1000}
    for name in sorted(required):
        with pytest.raises(TypeError, match=name):
            SolveSpec(**{k: v for k, v in full.items() if k != name})
        assert SolveSpecSpec.model_fields[name].is_required()
    # the three defaulted fields are the off state of something that computes nothing
    assert {f.name: f.default for f in dataclasses.fields(SolveSpec) if f.name not in required} \
        == {"heartbeat_sweeps": None, "checkpoint_every_s": 0.0, "total_budget_seconds": None}
    sig = inspect.signature(wf.solve_structure)
    assert sig.parameters["spec"].default is inspect.Parameter.empty
    with pytest.raises(TypeError, match="spec"):
        wf.solve_structure(acr.cost, acr.phase, instrument=acr.ins, priors=_priors(),
                           units=[FragmentUnit(acridine(), biso=3.0)])
    with pytest.raises(wf.SolveRefused, match="biso"):
        wf.solve_structure(acr.cost, acr.phase, instrument=acr.ins, priors=_priors(),
                           composition={"C": 4}, spec=SolveSpec(**full))
    bad = {"span": 1.0, "step": (0.0, 1.0), "swap_every": 0, "exchange": 1.5, "n_random": 1,
           "cluster_tol": 0.0, "polish_maxiter": 0, "replicas": 1, "sweeps": 0,
           "race_sweeps": 0}
    for name, value in bad.items():
        with pytest.raises(ValueError, match=name if name != "replicas" else "two replicas"):
            SolveSpec(**{**full, name: value})


def test_every_stated_setting_reaches_the_engine(acr, monkeypatch):
    """Odd values for every search setting, and each engine call receives the
    spec's own: the entry point substitutes none."""
    from rietx.solve import tempering as tp

    spec = _spec(seeds=(0,), control_seeds=(0,), sweeps=1000, replicas=4, span=17.0,
                 step=(0.07, 0.9), swap_every=7, exchange=0.25, n_random=11, cluster_tol=0.29,
                 polish_maxiter=13)
    seen: dict[str, set] = {}

    def spy(mod, name, keys):
        real = getattr(mod, name)

        def f(*a, **kw):
            for k in keys:
                seen.setdefault(f"{name}.{k}", set()).add(
                    tuple(kw[k]) if isinstance(kw[k], (tuple, list)) else kw[k])
            return real(*a, **kw)
        monkeypatch.setattr(mod, name, f)

    spy(tp, "random_spread", ["n"])
    spy(tp, "temper", ["swap_every", "exchange"])
    spy(tp, "polish", ["maxiter"])
    spy(cl, "cluster", ["tol"])
    real_planned = tp.Ladder.planned

    def planned(t_top, n_par, n_replicas, **kw):
        seen.setdefault("planned", set()).add((n_replicas, kw["span"], tuple(kw["step"])))
        return real_planned(t_top, n_par, n_replicas, **kw)
    monkeypatch.setattr(tp.Ladder, "planned", staticmethod(planned))
    acr.solve(spec)
    assert seen == {"random_spread.n": {11}, "temper.swap_every": {7}, "temper.exchange": {0.25},
                    "polish.maxiter": {13}, "cluster.tol": {0.29},
                    "planned": {(4, 17.0, (0.07, 0.9))}}


def test_the_spec_and_its_request_chair_are_each_others_inverse():
    assert ACR_SPEC.to_spec_spec().to_spec() == ACR_SPEC
    assert SolveSpecSpec.model_validate_json(ACR_SPEC.to_spec_spec().model_dump_json()
                                             ).to_spec() == ACR_SPEC
    odd = _spec(seeds=(3, 1), control_seeds=(), sweeps=7, total_budget_seconds=9.0, seed=5)
    assert odd.to_spec_spec().to_spec() == odd
    assert odd.seeds == (1, 3)
    assert set(SolveSpecSpec.model_fields) == {f.name for f in dataclasses.fields(SolveSpec)}


def test_solve_field_defaults_are_the_schemas_own():
    from rietx.help import SOLVE_FIELD_HELP

    wrong = []
    for name, field in SolveSpecSpec.model_fields.items():
        value = None if field.is_required() else field.get_default(call_default_factory=True)
        quoted = None if value is None else json.dumps(value)
        if SOLVE_FIELD_HELP[name].default != quoted:
            wrong.append((name, SOLVE_FIELD_HELP[name].default, quoted))
    assert not wrong


def test_engines_and_capabilities_quote_the_live_registry():
    from rietx.capabilities import Capabilities, capabilities
    from rietx.help import SOLVE_FIELD_HELP

    caps = capabilities()
    assert [e.name for e in caps.solve_engines] == list(en.engine_names()) == ["tempering"]
    assert set(SOLVE_FIELD_HELP) == set(SolveSpecSpec.model_fields)
    # no preset and no grade contract: those are the heuristic's (#1224)
    assert not {n for n in Capabilities.model_fields if n.startswith("solve_")} - {"solve_engines"}


# ===================================================================================
# events
# ===================================================================================
def test_the_stream_carries_the_run_its_units_and_the_heartbeat(acr_run):
    res, events, _root = acr_run
    kinds = [e["kind"] for e in events]
    assert kinds[0] == "solve_start" and kinds[-1] == "solve_end"
    starts = [e["data"]["stage"] for e in events if e["kind"] == "stage_start"]
    ends = [e["data"]["stage"] for e in events if e["kind"] == "stage_end"]
    units = [r.unit for r in res.records]
    assert starts == ends == units + [f"consensus:{GROUP}"]
    for uid in units:
        sweeps = [e["data"]["sweep"] for e in events
                  if e["kind"] == "solve_step" and e["data"]["unit"] == uid]
        # at least every heartbeat_sweeps: no gap longer than that, from 0 to the end
        assert np.max(np.diff([0] + sweeps)) <= ACR_SPEC.heartbeat_sweeps
        assert sweeps[-1] == ACR_SPEC.sweeps
    cons = [e for e in events if e["kind"] == "stage_end"][-1]["data"]
    assert cons["candidates"] == [r.model_dump(mode="json") for r in res.evidence()]
    end = events[-1]["data"]
    assert end["status"] == "done" and end["n_candidates"] == len(res.candidates)
    # the ladder is indexed: index runs 1..n and n_stages is the run's unit count
    idx = [e["data"]["index"] for e in events if e["kind"] == "stage_end"]
    assert idx == list(range(1, len(idx) + 1))
    assert {e["data"]["n_stages"] for e in events if e["kind"] == "stage_end"} == {len(idx)}


def test_read_events_validates_the_version_against_the_kind(tmp_path, acr_run):
    assert set(KIND_SINCE) == set(typing.get_args(EventKind))
    root = acr_run[2]
    (run,) = runs.discover(root)
    got = read_events(run.path / runs.EVENTS_FILE)
    assert {e.kind for e in got} >= {"solve_start", "solve_step", "solve_end"}
    assert {e.v for e in got} == {"4"}
    with pytest.raises(ValueError, match="arrived in version 4"):
        EventRecord.model_validate({"v": "3", "t": 1.0, "kind": "solve_step"})
    with pytest.raises(ValueError, match="whole number"):
        EventRecord.model_validate({"v": "four", "t": 1.0, "kind": "fit_start"})
    EventRecord.model_validate({"v": "2", "t": 1.0, "kind": "fit_start"})   # older logs read
    bad = tmp_path / "old.jsonl"
    bad.write_text(json.dumps({"record": "event", "v": "3", "t": 1.0, "kind": "solve_end",
                               "data": {}}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_events(bad)


def test_rietx_watch_renders_a_recorded_runs_ladder(acr_run):
    from rietx.watch import serve

    res, _events, root = acr_run
    server = serve(root, port=0, block=False)
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        (row,) = json.loads(urllib.request.urlopen(base + "/api/runs", timeout=5).read())["runs"]
        tail = json.loads(urllib.request.urlopen(
            base + f"/api/run/{row['run_id']}/events", timeout=5).read())
    finally:
        server.shutdown()
        server.server_close()
    st = row["status"]
    n = len(res.records) + 1
    assert (st["state"], st["stage"], st["index"], st["n_stages"]) == (
        "done", f"consensus:{GROUP}", n, n)
    assert row["label"] == "acr"
    kinds = {e.get("kind") for e in tail["events"]}
    assert {"solve_start", "stage_start", "solve_step", "stage_end", "solve_end"} <= kinds


def test_a_stop_from_watch_returns_what_the_run_has(acr, tmp_path):
    """The run directory's stop request reaches the solve through the token
    ``runs.attach_cancel`` hands it: the run returns its best-so-far."""
    asked = {}

    def cb(event):
        if event["kind"] == "solve_step" and not asked:
            (run,) = runs.discover(tmp_path)
            asked["dir"] = runs.request_cancel(run.path, who="test").parent
    was = runs.set_enabled(True)
    try:
        res = acr.solve(events=cb, telemetry=tmp_path)
    finally:
        runs.set_enabled(was)
    assert res.status == "cancelled" and res.partial
    assert res.records[0].stopped == "cancelled" and res.records[0].polished
    assert res.candidates and all(c.partial for c in res.candidates)
    assert res.units_not_run
    (run,) = runs.discover(tmp_path)
    assert run.status.state == "cancelled" and run.status.cancelled_by == "test"


# ===================================================================================
# #998: checkpoint, resume, partial
# ===================================================================================
@pytest.mark.parametrize("unit, sweep", [("seed:", 1500), ("control:", 1000)],
                         ids=["mid-period", "on-a-boundary"])
def test_an_interrupted_run_resumes_byte_identical(acr, acr_run, tmp_path, unit, sweep):
    """#998's acceptance: stopped by the cancel token at a named sweep of a
    named unit, resumed from the checkpoint, the same bytes as the
    uninterrupted run."""
    whole = acr_run[0]
    ck = tmp_path / "solve.ckpt"
    token = CancelToken()
    target = f"{unit}{GROUP}:s1" if unit == "seed:" else f"{unit}{GROUP}:s0"
    cut = acr.solve(checkpoint=ck, cancel=token, events=_cancel_at(token, target, sweep))
    assert cut.status == "cancelled" and cut.partial
    assert any(r.stopped == "cancelled" for r in cut.records)
    assert cut.candidates and all(c.partial for c in cut.candidates)
    saved = json.loads(ck.read_text(encoding="utf-8"))
    assert saved["current"]["unit"] == target
    assert saved["current"]["state"]["done"] == (sweep // 1000) * 1000
    again = acr.solve(checkpoint=ck)
    assert again.resumed and again.status == "done"
    assert again.comparable_json() == whole.comparable_json()


def test_a_finished_checkpoint_returns_the_run_without_running_it(acr, acr_run, tmp_path):
    ck = tmp_path / "done.ckpt"
    first = acr.solve(_spec(seeds=(0,), control_seeds=(), sweeps=1000, heartbeat_sweeps=250),
                      checkpoint=ck)
    events: list[dict] = []
    again = acr.solve(_spec(seeds=(0,), control_seeds=(), sweeps=1000, heartbeat_sweeps=250),
                      checkpoint=ck, events=events.append)
    assert again.comparable_json() == first.comparable_json()
    assert not [e for e in events if e["kind"] == "solve_step"]


def test_a_mismatched_checkpoint_is_refused_by_name(acr, tmp_path):
    spec = _spec(seeds=(0,), control_seeds=(), sweeps=1000)
    ck = tmp_path / "m.ckpt"
    acr.solve(spec, checkpoint=ck)
    # the cost: one reflection's b moved
    other = SolveCost(**{**acr.cost.__dict__, "b": acr.cost.b * (1 + 1e-9)})
    with pytest.raises(wf.CheckpointMismatch) as err:
        wf.solve_structure(other, acr.phase, instrument=acr.ins, priors=_priors(),
                           units=[FragmentUnit(acridine(), biso=3.0)], spec=spec,
                           checkpoint=ck, telemetry=False)
    assert err.value.field == "cost"
    # the spec: another sweep count, another search setting, and another prior
    with pytest.raises(wf.CheckpointMismatch) as err:
        acr.solve(_spec(seeds=(0,), control_seeds=(), sweeps=2000), checkpoint=ck)
    assert err.value.field == "spec"
    with pytest.raises(wf.CheckpointMismatch) as err:
        acr.solve(_spec(seeds=(0,), control_seeds=(), sweeps=1000, exchange=0.2), checkpoint=ck)
    assert err.value.field == "spec"
    with pytest.raises(wf.CheckpointMismatch) as err:
        wf.solve_structure(acr.cost, acr.phase, instrument=acr.ins,
                           priors=SolvePriors(weights=PriorWeights(coordination=0.0),
                                              sigma=0.2, fraction=0.8),
                           units=[FragmentUnit(acridine(), biso=3.0)], spec=spec,
                           checkpoint=ck, telemetry=False)
    assert err.value.field == "spec"
    # the version
    bumped = tmp_path / "v.ckpt"
    payload = json.loads(ck.read_text(encoding="utf-8"))
    payload["package_version"] = "0.0.0-other"
    bumped.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(wf.CheckpointMismatch) as err:
        acr.solve(spec, checkpoint=bumped)
    assert err.value.field == "version"
    # what decides only when the run writes, talks or stops may change
    acr.solve(_spec(seeds=(0,), control_seeds=(), sweeps=1000, heartbeat_sweeps=100,
                    checkpoint_every_s=5.0, total_budget_seconds=1e6), checkpoint=ck)


def test_a_killed_checkpoint_write_leaves_the_last_one_whole(tmp_path, monkeypatch):
    ck = tmp_path / "a.ckpt"
    wf.write_checkpoint(ck, {"n": 1, "pad": "x" * 5000})
    before = ck.read_bytes()

    def torn(obj, fh):
        fh.write(json.dumps(obj)[:100])
        raise KeyboardInterrupt("killed mid-write")

    monkeypatch.setattr(wf.json, "dump", torn)
    with pytest.raises(KeyboardInterrupt):
        wf.write_checkpoint(ck, {"n": 2, "pad": "y" * 5000})
    assert ck.read_bytes() == before
    assert json.loads(before)["n"] == 1
    assert [p.name for p in tmp_path.iterdir()] == ["a.ckpt"]


def test_the_assignment_race_resumes_byte_identical(nac, tmp_path):
    """A stop inside the race's third round, which continues each chain from
    its second-round state, resumes to the same bytes."""
    spec = _spec(seeds=(0,), control_seeds=(), sweeps=1000, race_sweeps=1000,
                 heartbeat_sweeps=500)
    events: list[dict] = []
    whole = nac.solve(spec, events=events.append)
    assert len(whole.races[0].rounds) == 3
    third = whole.races[0].rounds[2]
    assert third.sweeps == 4000 and len(third.ran) == 2
    # a round continues each chain from where the last stopped, never from a new start
    for k, start in ((1, 1000), (2, 2000)):
        for a in whole.races[0].rounds[k].ran:
            uid = f"race:{nac.phase.space_group}:a{a}:r{k}"
            first = min(e["data"]["sweep"] for e in events
                        if e["kind"] == "solve_step" and e["data"]["unit"] == uid)
            assert first == start + spec.heartbeat_sweeps
    ck = tmp_path / "race.ckpt"
    token = CancelToken()
    target = f"race:{nac.phase.space_group}:a{third.ran[1]}:r2"
    cut = nac.solve(spec, checkpoint=ck, cancel=token,
                    events=_cancel_at(token, target, 3500))
    assert cut.status == "cancelled" and cut.races[0].winner is None
    assert json.loads(ck.read_text(encoding="utf-8"))["current"]["state"]["done"] == 3000
    again = nac.solve(spec, checkpoint=ck)
    assert again.comparable_json() == whole.comparable_json()


# ===================================================================================
# seeds as processes
# ===================================================================================
def test_merged_seed_results_equal_the_in_process_run(acr, acr_run, tmp_path):
    whole = acr_run[0]
    paths = []
    for seeds, controls in (((0,), ()), ((1,), ()), ((), (0,))):
        r = acr.solve(_spec(seeds=seeds, control_seeds=controls, sweeps=2000,
                            heartbeat_sweeps=250))
        p = tmp_path / f"part{len(paths)}.json"
        p.write_text(r.model_dump_json(), encoding="utf-8")
        paths.append(p)
    merged = wf.merge_seed_results(paths)
    assert merged.comparable_json() == whole.comparable_json()
    with pytest.raises(ValueError, match="not seeds of one run"):
        wf.merge_seed_results([paths[0], whole.model_copy(update={"chi2_floor": 1.0})])


# ===================================================================================
# the assignment race on NAC: the composition alone
# ===================================================================================
@pytest.mark.slow
def test_nac_is_solved_from_its_composition_through_the_race(nac):
    """The race over NAC's six site-class assignments, with no deposited
    assignment, at settings stated here: its winner is the deposited
    assignment and the leader lies within 0.10 Å of the deposited structure.
    Measured at these settings (S2b's 2026-10-23 run, the settings then the
    module defaults): the deposited assignment won and the leader was 0.017 Å
    from it, found by all four seeds, in 8 of 8 spec seeds, against this
    test's one."""
    assert len(nac.deposited) == 1
    res = nac.solve(_spec(seeds=(0, 1, 2, 3), control_seeds=(0, 1), sweeps=20000,
                          race_sweeps=2000, heartbeat_sweeps=1000))
    race = res.races[0]
    assert race.n_assignments == 6 and [len(r.ran) for r in race.rounds] == [6, 3, 2]
    assert race.winner == nac.deposited[0]
    lead = res.candidates[0]
    assert nac.rmsd(lead) < 0.10
