"""Footing gate: is each computed tail on the footing of the Brown row it
continues?

For every Brown row rietx carries (``_J0``/``_J2`` of
``rietx.crystallography.magnetic.form_factor``) and each order j0, j2:

    ratio = 100 * rms(Brown fit - computed curve) / e

over Brown's own fitting grid (``mff_lib.BROWN_GRID``: 0-1.5 at 0.05 for
3d/4d; 0-0.5 at 0.05 then 0.1 to 1.2 for rare earths, to 1.5 for actinides),
with e Brown's printed fit error for that row and order
(``brown_fit_errors.csv``; ITC Vol. C sec. 4.4.5, Tables 4.4.5.1-8).  A curve
computed on the footing Brown fitted reproduces his fit to about his e, so a
ratio near 1 is expected and **ratio > 1.5 flags a footing mismatch** (the
configuration, term or code is not the one behind the row).  The distance of
the fit from the curve at s_end alone is not a gate: a 7-parameter fit can
end 2-4 e off a curve it matches everywhere else.

The gate needs the whole computed curve on 0-s_end, which the data file does
not carry for a tail; ``--curves`` names a directory of the long CSVs that
``regenerate.py`` writes (or the original ``tails_*.csv``).

Usage::

    python footing_gate.py --curves <dir> [--threshold 1.5] [--csv out.csv]

Exits 1 when a row is missing (unless ``--allow-missing``); flags are
reported, not failed, since four are known (README.md, "Footing gate").
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mff_lib as L  # noqa: E402


def brown_rows():
    """rietx's Brown coefficients: ({ion: j0 coef}, {ion: j2 coef})."""
    from rietx.crystallography.magnetic import form_factor as ff
    return ff._J0, ff._J2


def gate(curves: dict, errors: dict, threshold: float):
    j0, j2 = brown_rows()
    rows, missing = [], []
    for ion in j0:
        fam = L.family_of(ion)
        if ion not in curves:
            missing.append(ion)
            continue
        idx = np.rint(L.BROWN_GRID[fam] * 100).astype(int)
        rec = dict(ion=ion, family=fam)
        for order, coef in (("j0", j0[ion]), ("j2", j2[ion])):
            fit = L.brown7(coef, L.BROWN_GRID[fam], int(order[1]))
            comp = curves[ion][order][idx]
            e = errors[(ion, order)]
            rec[order] = 100.0 * float(np.sqrt(np.mean((fit - comp) ** 2))) / e
        rec["flag"] = "FOOTING?" if max(rec["j0"], rec["j2"]) > threshold else ""
        rows.append(rec)
    return rows, missing


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--curves", type=Path, required=True)
    ap.add_argument("--errors", type=Path, default=L.ERRORS_CSV)
    ap.add_argument("--threshold", type=float, default=1.5)
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--allow-missing", action="store_true")
    args = ap.parse_args(argv)

    curves = L.read_long(p for f in L.S_END if (p := args.curves / f"tails_{f}.csv").exists())
    with open(args.errors, newline="") as fh:
        errors = {(r["key"], r["order"]): float(r["e"]) for r in csv.DictReader(fh)}
    rows, missing = gate(curves, errors, args.threshold)
    flagged = [r for r in rows if r["flag"]]
    ratios = [r[o] for r in rows for o in ("j0", "j2")]
    print(f"\nfooting gate: 100 rms(fit - computed) / e on Brown's grid, flag > {args.threshold}")
    print(f"  {len(rows)} Brown rows, median ratio {np.median(ratios):.2f}; "
          f"{len(flagged)} flagged" + (f"; {len(missing)} without a curve" if missing else ""))
    for r in sorted(flagged, key=lambda r: -max(r["j0"], r["j2"])):
        print(f"  {r['ion']:6s} {r['family']}  j0 {r['j0']:5.2f}  j2 {r['j2']:5.2f}  {r['flag']}")
    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["ion", "family", "j0", "j2", "flag"],
                               lineterminator="\n")
            w.writeheader()
            w.writerows({**r, "j0": f"{r['j0']:.2f}", "j2": f"{r['j2']:.2f}"} for r in rows)
    if missing and not args.allow_missing:
        print(f"  no curve for: {' '.join(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
