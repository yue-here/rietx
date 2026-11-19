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


if __name__ == "__main__":
    if sys.argv[1:2] == ["score"]:
        score()
