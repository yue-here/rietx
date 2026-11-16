"""WP-2017 group O: the profile interval's five search constants and the fraction grid's three.

Domains, families and arms were fixed in WP-2017 § What each group inherits, "O, its domains
and arms", and "O, what its bullet left open", before anything ran (2026-11-16).  Each set gets
a stated domain, and the run grades only inside it; a case outside it is reported, never graded.

- ``O1`` — ``schemas.interval.PARAMETER_INTERVAL_MAX_REFITS`` (through ``max_refits``, the
  argument the constant defaults), ``_SETTLE_RUNS``, ``_XTOL``, ``_BRACKET_GROWTH`` and
  ``_CHI2_TOL`` (module globals of ``strategy.parameter_interval``, set on that module for the
  arm).  Each interval is ``strategy.parameter_interval.profile_interval(..., record=False)``,
  the call ``attach_stationary_intervals`` makes.  Families and rows: the two-site Pnma set
  (``test_stationary_moment_angle._fit(0.0, seed=s)``; Mn2's modulus and every angle the fit
  left out with a half-width) on seed 14 and two seeds the ``screen`` step picks; ``fap``
  (``atoms.0.biso``; no width row sits on its floor at the protocol's answer); ``cpd1a``
  (zincite's scale and its ``lor_strain`` on 0).  Arms ``shipped``, ``refits30``,
  ``refits120``, ``settle2``, ``settle8``, ``xtol1e-2``, ``xtol1e-4``, ``growth1.5``,
  ``growth3``, ``chi2tol0.003``, ``chi2tol0.03`` and ``reference`` (``XTOL`` 1e-5,
  ``SETTLE_RUNS`` 8, ``MAX_REFITS`` 200), each on the plain fit and on its noise twin (every
  refinable non-zero start ×(1 + 1e-12)).
- ``O2`` — ``schemas.fraction.FRACTION_PROFILE_N_FWHM``, ``_FWHM_MIN``, ``_FWHM_MAX_SPAN``
  (module globals of ``strategy.fraction_profile``).  Families: ``test_qpa_multimodal``'s
  two-basin fixture (``multimodal``) and its control (``control``), CaF₂ profiled; ``cpd1a``,
  each of its three phases profiled.  Arms ``shipped``, ``n5``, ``n21``, ``min0.003``,
  ``min0.03``, ``span0.3``, ``span0.7``, each on the plain fit and its noise twin.  Every
  refit's diagnostic codes are read (``FROZEN_COMPILE_STALE`` the one the domain names).

    .venv/bin/python docs/wp/2017-batch/group_o.py           # screen, then every task
    .venv/bin/python docs/wp/2017-batch/group_o.py canary    # fap shipped + reference; control shipped
    .venv/bin/python docs/wp/2017-batch/group_o.py summary   # write group_o_summary.md

``WP2017O_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-o``);
``WP2017O_WORKERS`` the pool (default 4).
"""

from __future__ import annotations

import importlib
import json
import os
import platform
import subprocess
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")

from rietx._about import COMPILED_THREADS_ENV  # noqa: E402

os.environ.setdefault(COMPILED_THREADS_ENV, "1")

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402

RAW = Path(os.environ.get("WP2017O_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-o"))
JSONL = RAW / "group_o.jsonl"
SCREEN = RAW / "group_o_screen.json"
SUMMARY = HERE / "group_o_summary.md"
WORKERS = int(os.environ.get("WP2017O_WORKERS", "4"))
NUDGE = 1e-12
TWINS = ("plain", "noise")

MN2 = "phases.0.atoms.1.moment"
#: O1 arms: name -> {constant: value}; ``MAX_REFITS`` goes through ``max_refits``
O1_ARMS = {
    "shipped": {},
    "refits30": {"MAX_REFITS": 30}, "refits120": {"MAX_REFITS": 120},
    "settle2": {"SETTLE_RUNS": 2}, "settle8": {"SETTLE_RUNS": 8},
    "xtol1e-2": {"XTOL": 1e-2}, "xtol1e-4": {"XTOL": 1e-4},
    "growth1.5": {"BRACKET_GROWTH": 1.5}, "growth3": {"BRACKET_GROWTH": 3.0},
    "chi2tol0.003": {"CHI2_TOL": 0.003}, "chi2tol0.03": {"CHI2_TOL": 0.03},
    "reference": {"XTOL": 1e-5, "SETTLE_RUNS": 8, "MAX_REFITS": 200},
}
#: O1 rows on the protocol families (fixed from the protocol's answer before running)
O1_ROWS = {"fap": ["phases.0.atoms.0.biso"],
           "cpd1a": ["phases.1.scale", "phases.1.lor_strain"]}
PNMA_FIXED_SEED = 14
#: the screen's seeds: 0-19 less the fixed one
SCREEN_SEEDS = tuple(s for s in range(20) if s != PNMA_FIXED_SEED)
O2_ARMS = {
    "shipped": {},
    "n5": {"N_FWHM": 5}, "n21": {"N_FWHM": 21},
    "min0.003": {"FWHM_MIN": 0.003}, "min0.03": {"FWHM_MIN": 0.03},
    "span0.3": {"FWHM_MAX_SPAN": 0.3}, "span0.7": {"FWHM_MAX_SPAN": 0.7},
}
O2_FAMILIES = ("multimodal", "control", "cpd1a")
O2_PHASES = {"multimodal": ["CaF2"], "control": ["CaF2"],
             "cpd1a": ["corundum", "zincite", "fluorite"]}


def _error_line(exc: Exception) -> str:
    return importlib.import_module("group_a")._error_line(exc)


def _nudged(ref: rx.Refinement) -> int:
    values = {}
    for row in ref.parameters():
        if not row.refinable or row.value == 0.0:
            continue
        value = row.value * (1.0 + NUDGE)
        if not row.lo <= value <= row.hi:
            value = row.value * (1.0 - NUDGE)
        values[row.path] = value
    ref.set_values(values)
    return len(values)


# -- the fits ------------------------------------------------------------------------------


def _pnma(seed: int, twin: str, intervals: bool = False):
    """``test_stationary_moment_angle._fit(0.0, seed=seed)``, the start nudged on the twin."""
    from rietx.schemas.structure import Moment
    from tests import test_stationary_moment_angle as S

    T = S._solve()
    mag = S._magnetic()
    instrument = T.neutron()
    data = T.simulate(T.two_site(
        m1=Moment.from_values(S._vec(3.5, 0.0), "Mn3+"),
        m2=Moment.from_values((0.7, 0.0, 0.0), "Mn3+"),
        magnetic=mag), instrument, seed=seed)
    start = T.two_site(
        m1=Moment.from_values(S._vec(3.3, 0.04, 0.03), "Mn3+", vary=True),
        m2=Moment.from_values(S._vec(0.75, 0.03, 0.03), "Mn3+", vary=True),
        magnetic=mag)
    ref = rx.Refinement(rx.Structure(phases=[start]), instrument)
    ref._auto_intervals = intervals
    nudged = _nudged(ref) if twin == "noise" else 0
    result = ref.fit(data, plan=S._plan(), telemetry=False)
    return ref, data, result, nudged


def _protocol(family: str, twin: str):
    from tests import test_window_domain as w

    data, st, ins, plan, kw = w._protocol(family)
    ref = rx.Refinement(st, ins, history=False)
    nudged = _nudged(ref) if twin == "noise" else 0
    result = ref.fit(data, plan=plan, **kw)
    return ref, data, result, nudged


def _qpa_fixture(family: str, twin: str):
    from tests import test_qpa_multimodal as Q

    scale, hump = ((Q.TRACE_SCALE, Q.HUMP) if family == "multimodal"
                   else (Q.CONTROL_SCALE, None))
    data = Q._synthesize(scale, hump)
    ref = rx.Refinement(*Q._models(scale, Q.FITTED_BACKGROUND_TERMS))
    nudged = _nudged(ref) if twin == "noise" else 0
    result = ref.fit(data, plan=Q.PLAN, telemetry=False)
    return ref, data, result, nudged


def _passed(result):
    stage = result.stages[-1] if result.stages else None
    return next((t for t in (getattr(stage, "moment_angle_tests", None) or []) if t.zeroed),
                None)


def screen_one(seed: int) -> dict:
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"seed": seed}
    try:
        _ref, _data, result, _ = _pnma(seed, "plain")
        test = _passed(result)
        stage = result.stages[-1]
        tests = getattr(stage, "moment_angle_tests", None) or []
        row.update({"zeroed": test is not None,
                    "statistic": [t.statistic for t in tests],
                    "angles": [] if test is None else list(test.half_widths),
                    "rwp": result.statistics.rwp, "status": result.status})
    except Exception as exc:  # noqa: BLE001
        row["error"] = _error_line(exc)
    return row


def screen() -> list[int]:
    """Fit seeds 0-19 (14 aside) without intervals; the two lowest that pass the test."""
    RAW.mkdir(parents=True, exist_ok=True)
    if SCREEN.exists():
        rows = json.loads(SCREEN.read_text())
    else:
        with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(SCREEN_SEEDS))),
                                 mp_context=get_context("spawn")) as pool:
            rows = [f.result() for f in as_completed(
                [pool.submit(screen_one, s) for s in SCREEN_SEEDS])]
        rows.sort(key=lambda r: r["seed"])
        SCREEN.write_text(json.dumps(rows, indent=1))
    picked = [r["seed"] for r in rows if r.get("zeroed")][:2]
    print("screen", [(r["seed"], r.get("zeroed")) for r in rows], "picked", picked, flush=True)
    return picked


# -- O1 --------------------------------------------------------------------------------------


def _set_interval_arm(arm: str) -> int:
    from rietx.schemas import interval as schema
    from rietx.strategy import parameter_interval as pi

    for name in ("SETTLE_RUNS", "XTOL", "BRACKET_GROWTH", "CHI2_TOL"):
        setattr(pi, f"PARAMETER_INTERVAL_{name}", getattr(schema, f"PARAMETER_INTERVAL_{name}"))
    settings = O1_ARMS[arm]
    for name, value in settings.items():
        if name != "MAX_REFITS":
            setattr(pi, f"PARAMETER_INTERVAL_{name}", value)
    return int(settings.get("MAX_REFITS", schema.PARAMETER_INTERVAL_MAX_REFITS))


def _interval_record(iv, row, half_width) -> dict:
    return {
        "value": iv.value, "stderr": iv.stderr, "plain": row.stderr_uncorrected,
        "half_width": half_width, "at_bound": iv.at_bound, "one_sided": iv.one_sided,
        "lower": iv.lower, "upper": iv.upper, "lower_stop": iv.lower_stop,
        "upper_stop": iv.upper_stop, "cut": iv.delta_chi2_cut, "chi2_fit": iv.chi2_fit,
        "chi2_lowest": iv.chi2_lowest, "fit_is_minimum": iv.fit_is_minimum,
        "n_refits": iv.n_refits,
        "points": [[p.value, p.runs, p.delta_chi2, p.error is not None] for p in iv.points],
    }


def o1_one(task: dict) -> dict:
    from rietx.strategy import parameter_interval as pi

    family, twin, arm = task["family"], task["twin"], task["arm"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"set": "O1", "family": family, "twin": twin, "arm": arm}
    t0 = time.time()
    try:
        if family.startswith("pnma"):
            ref, data, result, nudged = _pnma(int(family[4:]), twin)
            test = _passed(result)
            rows = {p.path: p for p in result.parameters}
            paths = [f"{MN2}.dof0"] + ([] if test is None else
                                       [p for p in test.paths if p in test.half_widths])
            row["zeroed"] = test is not None
        else:
            ref, data, result, nudged = _protocol(family, twin)
            rows = {p.path: p for p in result.parameters}
            paths = list(O1_ROWS[family])
        row.update({"n_nudged": nudged, "rwp": result.statistics.rwp, "status": result.status,
                    "fit_s": round(time.time() - t0, 2)})
        max_refits = _set_interval_arm(arm)
        row["max_refits"] = max_refits
        row["settings"] = {n: getattr(pi, f"PARAMETER_INTERVAL_{n}")
                           for n in ("SETTLE_RUNS", "XTOL", "BRACKET_GROWTH", "CHI2_TOL")}
        intervals = {}
        for path in paths:
            r = rows.get(path)
            if r is None or not r.vary:
                intervals[path] = {"error": "row not free at the answer"}
                continue
            t1 = time.time()
            try:
                iv = pi.profile_interval(ref, data, path, max_refits=max_refits, record=False)
                rec = _interval_record(iv, r, pi._stationary_half_width(result, path))
            except Exception as exc:  # noqa: BLE001
                rec = {"error": _error_line(exc)}
            rec["s"] = round(time.time() - t1, 2)
            intervals[path] = rec
        row["intervals"] = intervals
        _set_interval_arm("shipped")
        if family.startswith("pnma") and twin == "plain" and arm == "shipped":
            # the control: what the fit itself attaches, against the explicit calls above
            _r, _d, auto, _ = _pnma(int(family[4:]), "plain", intervals=True)
            row["auto"] = {p.path: [p.interval.lower, p.interval.upper, p.interval.n_refits]
                           for p in auto.parameters if p.interval is not None}
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = _error_line(exc)
    row["s"] = round(time.time() - t0, 2)
    return row


# -- O2 --------------------------------------------------------------------------------------


def _set_grid_arm(arm: str) -> dict:
    from rietx.schemas import fraction as schema
    from rietx.strategy import fraction_profile as fp

    for name in ("N_FWHM", "FWHM_MIN", "FWHM_MAX_SPAN"):
        setattr(fp, f"FRACTION_PROFILE_{name}", getattr(schema, f"FRACTION_PROFILE_{name}"))
    for name, value in O2_ARMS[arm].items():
        setattr(fp, f"FRACTION_PROFILE_{name}", value)
    return {n: getattr(fp, f"FRACTION_PROFILE_{n}") for n in ("N_FWHM", "FWHM_MIN",
                                                            "FWHM_MAX_SPAN")}


def o2_one(task: dict) -> dict:
    family, twin, arm = task["family"], task["twin"], task["arm"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"set": "O2", "family": family, "twin": twin, "arm": arm}
    t0 = time.time()
    codes: list[list[str]] = []
    original = rx.Refinement.run_stage

    def spy(self, *args, **kwargs):
        r = original(self, *args, **kwargs)
        codes.append(sorted({d.code for d in r.diagnostics}))
        return r

    try:
        if family == "cpd1a":
            ref, data, result, nudged = _protocol(family, twin)
        else:
            ref, data, result, nudged = _qpa_fixture(family, twin)
        row.update({"n_nudged": nudged, "rwp": result.statistics.rwp, "status": result.status,
                    "fractions": {f.name: [f.weight_fraction, f.weight_fraction_stderr]
                                  for f in result.qpa.phases}})
        row["settings"] = _set_grid_arm(arm)
        rx.Refinement.run_stage = spy
        profiles = {}
        for phase in O2_PHASES[family]:
            codes.clear()
            t1 = time.time()
            try:
                p = ref.profile_fraction(data, phase)
                measured = [q for q in p.points if q.chi2 is not None]
                stale = [("FROZEN_COMPILE_STALE" in c) for c in codes]
                profiles[phase] = {
                    "axes": p.axes, "wf": p.weight_fraction, "esd": p.weight_fraction_stderr,
                    "cut": p.delta_chi2_cut, "chi2_fit": p.chi2_fit, "chi2_best": p.chi2_best,
                    "fit_admissible": p.fit_admissible, "range": [p.range_low, p.range_high],
                    "excess": p.excess,
                    "points": [[q.axis, q.fwhm, q.weight_fraction, q.delta_chi2, q.admissible,
                                q.error] for q in p.points],
                    "n_measured": len(measured), "n_spied": len(codes),
                    "stale": stale, "codes": sorted({c for cs in codes for c in cs}),
                }
            except Exception as exc:  # noqa: BLE001
                profiles[phase] = {"error": _error_line(exc)}
            profiles[phase]["s"] = round(time.time() - t1, 2)
        row["profiles"] = profiles
    except Exception as exc:  # noqa: BLE001
        row["error"] = _error_line(exc)
    finally:
        rx.Refinement.run_stage = original
        _set_grid_arm("shipped")
    row["s"] = round(time.time() - t0, 2)
    return row


# -- the sweep -----------------------------------------------------------------------------


def run_one(task: dict) -> dict:
    return o1_one(task) if task["set"] == "O1" else o2_one(task)


def read_rows(path: Path = JSONL) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _meta() -> dict:
    import importlib.metadata as md

    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip() or "unknown"
    return {"head": head, "platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "numpy": md.version("numpy"),
            "kernels": md.version("rietx-kernels"), "workers": WORKERS}


def _key(t: dict) -> tuple:
    return (t["set"], t["family"], t["twin"], t["arm"])


def tasks(seeds: list[int]) -> list[dict]:
    o1 = [f"pnma{s}" for s in (PNMA_FIXED_SEED, *seeds)] + list(O1_ROWS)
    out = [{"set": "O1", "family": f, "twin": tw, "arm": a}
           for f in o1 for tw in TWINS for a in O1_ARMS]
    out += [{"set": "O2", "family": f, "twin": tw, "arm": a}
            for f in O2_FAMILIES for tw in TWINS for a in O2_ARMS]
    # the slowest first: the reference arm and the cpd-1a profiles
    return sorted(out, key=lambda t: (t["arm"] != "reference", t["family"] != "cpd1a"))


def canary_tasks() -> list[dict]:
    return [{"set": "O1", "family": "fap", "twin": "plain", "arm": "shipped"},
            {"set": "O1", "family": "fap", "twin": "plain", "arm": "reference"},
            {"set": "O2", "family": "control", "twin": "plain", "arm": "shipped"}]


def sweep(todo_all: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {_key(r) for r in read_rows() if "error" not in r}
    todo = [t for t in todo_all if _key(t) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(run_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(*_key(row), row.get("error") or f"{row['s']} s", flush=True)


def summary() -> None:
    raise NotImplementedError("written once the rows exist")


def main(argv: list[str]) -> None:
    if argv[:1] == ["summary"]:
        summary()
        return
    if argv[:1] == ["canary"]:
        sweep(canary_tasks())
        return
    sweep(tasks(screen()))


if __name__ == "__main__":
    main(sys.argv[1:])
