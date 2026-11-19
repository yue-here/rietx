"""WP-2017 group F, part B (PR #1577): a second real hump near ``HUMP_TRIGGER`` (0.05).

Registered in WP-2017's handover log ("2026-11-19 (part B ...: registered before any run)")
before anything here ran.  ``score`` reads every measured powder pattern in ``tests/data/``
but the held-out family (``mg090``, Nd2Ru2O7) and the empty capillary itself, and records
``auto_background``'s ``amorphous_hump_score`` and ``air_scatter_gain`` over the file's own
range.  A pattern is eligible as a *real hump* when it has a known amorphous contributor: an
APS 11-BM pattern measured in a Kapton capillary, whose empty capillary
(``11BM_Kapton.xy``, run 4736) is the measured blank.  Si SRM 640c is the first hump and is
not eligible.  The band is 0.035-0.065; the eligible pattern nearest 0.05 is taken, the
CuCr2O4 ramp's frames counting as one family (its nearest frame).

    python docs/wp/2017-batch/group_f_b2.py score     # writes $WP2017F_RAW/scores.json
    python docs/wp/2017-batch/group_f_b2.py run       # the arms on the picked pattern
    python docs/wp/2017-batch/group_f_b2.py summary   # write group_f_b2_summary.md

The pick (scored 2026-11-19 on pearl): ``11BM_LaB6_cBN_mg2044.xye``, NIST SRM 660b LaB6 with
cubic BN in a Kapton capillary, 0.0484.  Its arms, under ``test_acceptance_lab6_cbn``'s shipped
protocol (``PLAN_SHARED`` over 5.1-50°, LaB6's cell held at its certificate, zero held):
``pick`` (the instrument's 16 Chebyshev terms replaced by ``auto_background(data,
two_theta_limits=LIMITS)``'s pick), ``knot_flip`` (``HUMP_TRIGGER`` moved just across that
score, so the other knot step is taken), ``noise`` (``pick``, every free start that is not zero
× (1 + 1e-12)) and ``blank``: the measured empty capillary (run 4736) held under three Chebyshev
terms at a refined scale, as group F's Si arm.  Read every row against ``blank`` and ``pick`` in
plain esd over the larger esd, at the grounds' 0.8 bar, past ``noise``; Rwp, status, the codes,
and both scores (the file's range and the fit's).
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import rietx as rx  # noqa: E402
from rietx.background import auto  # noqa: E402

DATA = ROOT / "tests" / "data"
RAW = Path(os.environ.get("WP2017F_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-f"))
BAND = (0.035, 0.065)
HELD_OUT = ("mg090",)
SKIP = ("11BM_Kapton.xy",)
SUFFIXES = (".xy", ".xye", ".fxye", ".dat", ".prn", ".gsas", ".gda", ".xrdml", ".raw",
            ".brml", ".XRA")
#: 11-BM patterns in a Kapton capillary: the eligible set (Si 640c is the first hump)
KAPTON_11BM = ("11BM_NAC.fxye", "11BM_LaB6_660a.fxye", "11BM_LaB6_cBN_mg2044.xye")


def candidates() -> list[Path]:
    out = []
    for p in sorted(DATA.rglob("*")):
        if not p.is_file() or p.suffix not in SUFFIXES or p.name.startswith("._"):
            continue
        if any(h in p.name for h in HELD_OUT) or p.name in SKIP or "PLANTED" in p.name:
            continue
        out.append(p)
    return out


def eligible(p: Path) -> bool:
    return p.name in KAPTON_11BM or p.parent.name == "seqrefine_cucr2o4"


def score() -> None:
    warnings.simplefilter("ignore")
    RAW.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in candidates():
        row = {"file": str(p.relative_to(DATA)), "eligible": eligible(p)}
        try:
            data = rx.read_pattern(p)
            choice = auto.auto_background(data)
            row.update(hump=choice.amorphous_hump_score, air=choice.air_scatter_gain,
                       knot=choice.knot_step_deg, n=len(data.two_theta),
                       range=[float(data.two_theta[0]), float(data.two_theta[-1])])
        except Exception as exc:  # noqa: BLE001  a file that does not read is recorded
            row["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"
        rows.append(row)
        print(json.dumps(row), flush=True)
    (RAW / "scores.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    inband = [r for r in rows if r.get("eligible") and "hump" in r
              and BAND[0] <= r["hump"] <= BAND[1]]
    best = min(inband, key=lambda r: abs(r["hump"] - 0.05)) if inband else None
    near = min((r for r in rows if r.get("eligible") and "hump" in r),
               key=lambda r: abs(r["hump"] - 0.05), default=None)
    print("PICK", json.dumps(best), "NEAREST", json.dumps(near), flush=True)


ARMS = ("pick", "knot_flip", "noise", "blank")
JSONL = RAW / "group_f_b2.jsonl"
SUMMARY = Path(__file__).resolve().parent / "group_f_b2_summary.md"
BAR = 0.8


def fit_one(arm: str) -> dict:
    import importlib

    from rietx.model import compiled
    from rietx.schemas.instrument import BackgroundFixedPlusChebyshev
    from tests import test_acceptance_lab6_cbn as lc
    from tests import test_window_domain as w

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    gf = importlib.import_module("group_f")
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"pattern": "mg2044", "arm": arm}
    try:
        data = rx.read_pattern(lc.PATTERN)
        st, ins = lc._inputs()
        plan = lc.PLAN_SHARED
        if arm == "blank":
            from tests.test_acceptance_si640c import BLANK
            blank = rx.read_pattern(BLANK)
            ins.background = BackgroundFixedPlusChebyshev.from_pattern(
                blank, n_terms=3, vary_scale=True, scale=1.0,
                source="APS 11-BM run 4736, empty Kapton capillary")
            row["choice"] = None
        else:
            base = auto.auto_background(data, two_theta_limits=lc.LIMITS)
            hump = auto.HUMP_TRIGGER
            if arm == "knot_flip":
                hump = gf._across(base.amorphous_hump_score, base.hump_trigger)
            with gf.triggers(hump, auto.AIR_SCATTER_TRIGGER):
                choice = auto.auto_background(data, two_theta_limits=lc.LIMITS)
            ins.background = choice.background
            row["choice"] = {"knot_step_deg": choice.knot_step_deg,
                             "air_scatter": choice.air_scatter,
                             "hump_score": choice.amorphous_hump_score,
                             "air_gain": choice.air_scatter_gain, "hump_trigger": hump,
                             "pick_knot": base.knot_step_deg}
        ref = rx.Refinement(st, ins, history=False)
        if arm == "noise":
            row["n_nudged"] = gf._nudged(ref)
        result = ref.fit(data, plan=plan, two_theta_limits=lc.LIMITS)
        row.update({
            "rows": {k: list(v) for k, v in w._rows(result).items()},
            "rwp": result.statistics.rwp, "status": result.status,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "codes": sorted({d.code for d in result.diagnostics}),
            "wt": {q.name: [100 * q.weight_fraction,
                            None if q.weight_fraction_stderr is None
                            else 100 * q.weight_fraction_stderr]
                   for q in result.qpa.phases} if result.qpa else None,
        })
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
    return row


def run() -> None:
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context

    RAW.mkdir(parents=True, exist_ok=True)
    print("rietx", rx.__file__, flush=True)
    with ProcessPoolExecutor(max_workers=4, mp_context=get_context("spawn")) as pool:
        for row in pool.map(fit_one, ARMS):
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["arm"], row.get("status"), row.get("rwp"), row.get("error", ""), flush=True)


def summary() -> None:
    from tests import test_window_domain as w

    rows = {}
    for line in JSONL.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        rows[r["arm"]] = r
    out = ["# WP-2017 group F part B: the second real hump, 11-BM LaB6 + cBN (mg2044)", "",
           "Written by `group_f_b2.py summary`; the raw rows are not committed.", "",
           "| arm | knot step | hump score (fit range) | trigger | Rwp | status | evals "
           "| largest shift vs blank | vs pick | codes |", "|---|---|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        r = rows.get(arm)
        if r is None or "error" in r:
            out.append(f"| {arm} | error: {None if r is None else r['error']} | | | | | | | | |")
            continue
        ch = r["choice"] or {}
        vs = []
        for other in ("blank", "pick"):
            o = rows.get(other)
            if o is None or "error" in o or o is r:
                vs.append("—")
                continue
            sh, path = w._shift(r["rows"], o["rows"], background=False)
            vs.append(f"{sh:.3g} {path}")
        out.append(f"| {arm} | {ch.get('knot_step_deg', 'blank')} | "
                   f"{ch.get('hump_score', float('nan')):.4f} | {ch.get('hump_trigger', '—')} | "
                   f"{r['rwp']:.5f} | {r['status']} | {r['n_eval']} | {vs[0]} | {vs[1]} | "
                   f"{', '.join(r['codes']) or 'none'} |")
    blank = rows.get("blank")
    if blank and "error" not in blank:
        out += ["", "Per row, each arm against `blank` in plain esd over the larger esd:", ""]
        keys = [k for k in blank["rows"] if not k.startswith("instrument.background.")]
        out.append("| row | blank | " + " | ".join(a for a in ARMS if a != "blank") + " |")
        out.append("|---|---|" + "---|" * (len(ARMS) - 1))
        for k in keys:
            v0, e0 = blank["rows"][k]
            cells = []
            for arm in ARMS:
                if arm == "blank":
                    continue
                r = rows.get(arm)
                if r is None or "error" in r or k not in r["rows"]:
                    cells.append("—")
                    continue
                sh, _ = w._shift({k: r["rows"][k]}, {k: blank["rows"][k]}, background=False)
                cells.append(f"{r['rows'][k][0]:.6g} ({sh:.2f})")
            out.append(f"| {k} | {v0:.6g}({'—' if e0 is None else f'{e0:.2g}'}) | "
                       + " | ".join(cells) + " |")
        out += ["", "Weight fractions (wt %): " + "; ".join(
            f"{a}: " + ", ".join(f"{n} {v[0]:.3f}({'—' if v[1] is None else f'{v[1]:.3f}'})"
                                 for n, v in (rows[a].get("wt") or {}).items())
            for a in ARMS if a in rows and "error" not in rows[a])]
    SUMMARY.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(SUMMARY)


if __name__ == "__main__":
    if sys.argv[1:2] == ["score"]:
        score()
    elif sys.argv[1:2] == ["run"]:
        run()
    elif sys.argv[1:2] == ["summary"]:
        summary()
