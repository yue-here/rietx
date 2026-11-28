"""Regenerate the computed magnetic form-factor curves from their input decks.

For each curve in ``curves.csv`` (or the ``--keys`` given): write its RCN deck
or GRASP2018 inputs, run the code in ``--work``, read the radial functions,
transform them to <j0>, <j2>, <j4> and write the long CSVs that
``write_data_file.py`` reads into ``--out``:

* ``tails_3d.csv``, ``tails_4d.csv``, ``tails_4f.csv``, ``tails_5f.csv``,
  ``neutral_4d.csv`` (label, order, s, value, footing, code, config; s = 0-6
  at 0.01) and ``bare_rows.csv`` (label, verdict);
* ``d32/<ion>_HFR.csv`` for the ten high-charge 4d ions (s = 0-6 at 0.005).

Then, optionally, compare with a data file (``--compare mff_computed.dat``:
max |regenerated - shipped| per curve and order over the block's grid) and
print the footing gate (``footing_gate.py``) for the Brown rows regenerated.

Usage::

    python regenerate.py --rcn <rcn executable> --grasp-bin <dir> \\
        --work <scratch dir> --out <dir> [--keys Mn2+ Ru4+ Gd3+ | --code RCN] \\
        [--compare <mff_computed.dat>] [--gate]
    python regenerate.py --decks-only --work <dir> [--keys ...]

``--rcn`` (or $RCN_EXE) is RCN Mod 36.2.5 built from the unmodified source;
``--grasp-bin`` (or $GRASP_BIN) holds rnucleus, rcsfgenerate, rangular,
rwfnestimate and rmcdhf; ``--lib-path`` is prepended to the dynamic-library
search path for GRASP's LAPACK/BLAS if they are not on it.  A GRASP curve
whose ``start`` is another key runs after it and starts from its rwfn.out;
that key is added to the run when missing.  GRASP runs single-threaded.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mff_lib as L  # noqa: E402

RCN_FOOT = "Cowan RCN Mod 36.2.5, HF/HFR as in curves.csv (irel, corrf, term)"
DF_FOOT = "GRASP2018 Dirac-Fock, average level; <j_n> = int (P^2+Q^2) j_n, j = l-+1/2 by 2j+1"
GRASP_PROGS = ("rnucleus", "rcsfgenerate", "rangular", "rwfnestimate", "rmcdhf")


def _closure(curves: dict, keys: list[str]) -> list[str]:
    want, stack = set(), list(keys)
    while stack:
        k = stack.pop()
        if k not in curves:
            raise SystemExit(f"unknown key {k!r} (see curves.csv)")
        if k not in want:
            want.add(k)
            if curves[k]["code"] == "GRASP" and curves[k]["start"] != "TF":
                stack.append(curves[k]["start"])
    order, seen = [], set()

    def visit(k):  # a GRASP start runs before the curve that starts from it
        if k not in seen:
            seen.add(k)
            if curves[k]["code"] == "GRASP" and curves[k]["start"] != "TF":
                visit(curves[k]["start"])
            order.append(k)

    for k in curves:
        if k in want:
            visit(k)
    return order


def _is_d32(row: dict) -> bool:
    """One of the ten high-charge 4d tables (written on the 0.005 grid)."""
    return row["family"] == "4d" and row["kind"] == "table" and row["key"].endswith("+")


def _fresh(d: Path) -> Path:
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    return d


def run_rcn(row: dict, exe: str, d: Path, decks_only: bool):
    (d / "in36").write_text(L.rcn_deck(row))
    if decks_only:
        return None
    p = subprocess.run([exe], cwd=d, capture_output=True, text=True, timeout=540)
    (d / "stdout.txt").write_text(p.stdout + p.stderr)
    if p.returncode != 0:
        raise RuntimeError(f"RCN failed for {row['key']} (rc {p.returncode}) in {d}")
    if "did not converge" in (d / "out36").read_text(errors="replace").lower():
        raise RuntimeError(f"RCN did not converge for {row['key']} in {d}")
    (res,) = L.read_tape2(d / "tape2n")
    if (res["iz"], res["ion"], res["irel"]) != (int(row["Z"]), int(row["q"]), int(row["irel"])):
        raise RuntimeError(f"{row['key']}: tape2n is for Z={res['iz']} ion={res['ion']}")
    rr, pp = L.fine_radial(res["r"], res["p"][row["shell"]])
    return L.density_transform(rr, pp * pp, s=L.S_D32 if _is_d32(row) else L.S)


def run_grasp(row: dict, gbin: Path, d: Path, env: dict, work: Path, decks_only: bool):
    inputs = L.grasp_inputs(row)
    for prog in GRASP_PROGS:
        (d / f"{prog}.in").write_text(inputs[prog])
    if decks_only:
        return None
    if row["start"] != "TF":
        shutil.copy(work / "grasp" / row["start"] / "rwfn.out", d / "start.w")
    for prog in GRASP_PROGS:
        p = subprocess.run([str(gbin / prog)], input=inputs[prog], cwd=d, capture_output=True,
                           text=True, timeout=540, env=env)
        (d / f"{prog}.stdout").write_text(p.stdout + p.stderr)
        if p.returncode != 0:
            raise RuntimeError(f"{prog} failed for {row['key']} in {d}")
        if prog == "rcsfgenerate":
            shutil.copy(d / "rcsf.out", d / "rcsf.inp")
            got = L.block_sizes(d / "rcsf.inp")
            if got != [int(x) for x in row["blocks"].split()]:
                raise RuntimeError(f"{row['key']}: J blocks {got}, curves.csv says {row['blocks']}")
    out = (d / "rmcdhf.stdout").read_text()
    bad = [m for m in ("Error in SUBROUTINE", "Convergence not obtained",
                       "Maximum iterations in SCF Exceeded") if m in out]
    if bad or "RMCDHF: Execution complete." not in out:
        raise RuntimeError(f"rmcdhf did not converge cleanly for {row['key']}: {bad}")
    spec = L.grasp_spec(row)
    rr, rho = L.shell_density(L.read_rwfn(d / "rwfn.out"), *spec["nl"])
    return L.density_transform(rr, rho)


def _write(out: Path, curves: dict, results: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list] = {}
    for key in (k for k in curves if k in results):  # curves.csv order = the data file's
        row, ints = curves[key], results[key]
        if _is_d32(row):
            d32 = out / "d32"
            d32.mkdir(exist_ok=True)
            with open(d32 / f"{key}_HFR.csv", "w", newline="") as fh:
                fh.write(f"# {row['config']} RCN IREL={row['irel']} CORRF={row['corrf']} "
                         f"configuration average; s = 0-6 at 0.005\n")
                w = csv.writer(fh, lineterminator="\n")
                w.writerow(["s_invA", "j0", "j2", "j4"])
                for k, s in enumerate(L.S_D32):
                    w.writerow([f"{s:.3f}"] + [f"{ints[n][k]:.10e}" for n in (0, 2, 4)])
            continue
        name = "neutral_4d" if key.endswith("0") else f"tails_{row['family']}"
        foot, code = (RCN_FOOT, "RCN") if row["code"] == "RCN" else (DF_FOOT, "GRASP2018")
        rows = groups.setdefault(name, [])
        for o, n in (("j0", 0), ("j2", 2), ("j4", 4)):
            rows += [(key, o, f"{s:.2f}", f"{v:.8f}", foot, code, row["config"])
                     for s, v in zip(L.S, ints[n])]
    for name, rows in groups.items():
        with open(out / f"{name}.csv", "w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["label", "order", "s", "value", "footing", "code", "config"])
            w.writerows(rows)
    with open(out / "bare_rows.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["label", "verdict"])
        w.writerows((k, r["verdict"]) for k, r in curves.items() if r["verdict"])


def read_data_file(path: Path) -> dict:
    """{key: {'s': grid, order: values}} from a data file in rietx's format."""
    out, cur = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("@ "):
            key, _kind, *orders = line[2:].split()
            cur = out[key] = {"orders": orders, "rows": []}
        elif cur is not None and line and line[0].isdigit():
            cur["rows"].append([float(x) for x in line.split()])
    for blk in out.values():
        a = np.array(blk.pop("rows"))
        blk["s"] = a[:, 0]
        for i, o in enumerate(blk.pop("orders")):
            blk[o] = a[:, 1 + i]
    return out


def compare(dat: Path, curves: dict, results: dict) -> float:
    shipped = read_data_file(dat)
    worst = 0.0
    print(f"\nregenerated vs {dat.name}: max |diff| per order on the block's grid")
    for key, ints in results.items():
        if key not in shipped:
            print(f"  {key:6s} (not in the data file: only a start for another curve)")
            continue
        blk = shipped[key]
        grid = L.S_D32 if len(ints[0]) == L.S_D32.size else L.S
        idx = np.searchsorted(grid, blk["s"] - 1e-9)
        diffs = {o: float(np.abs(ints[int(o[1])][idx] - blk[o]).max())
                 for o in ("j0", "j2", "j4") if o in blk}
        worst = max(worst, *diffs.values())
        print(f"  {key:6s} s={blk['s'][0]:.2f}-6  " +
              "  ".join(f"{o} {v:.1e}" for o, v in diffs.items()))
    print(f"  largest: {worst:.1e} (the file's %.7f rounding is 5e-8)")
    return worst


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rcn", default=os.environ.get("RCN_EXE"))
    ap.add_argument("--grasp-bin", type=Path, default=os.environ.get("GRASP_BIN"))
    ap.add_argument("--lib-path", default=None)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--code", choices=("RCN", "GRASP"), help="only this code's curves")
    ap.add_argument("--curves", type=Path, default=L.CURVES_CSV)
    ap.add_argument("--decks-only", action="store_true")
    ap.add_argument("--compare", type=Path)
    ap.add_argument("--gate", action="store_true")
    args = ap.parse_args(argv)

    curves = L.load_curves(args.curves)
    keys = _closure(curves, args.keys or [k for k, r in curves.items()
                                          if args.code in (None, r["code"])])
    codes = {curves[k]["code"] for k in keys}
    if not args.decks_only:
        if "RCN" in codes and not args.rcn:
            ap.error("--rcn (or $RCN_EXE) is required")
        if "GRASP" in codes and not args.grasp_bin:
            ap.error("--grasp-bin (or $GRASP_BIN) is required")
        if not args.out:
            ap.error("--out is required")
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    if args.lib_path:
        for var in ("DYLD_FALLBACK_LIBRARY_PATH", "LD_LIBRARY_PATH"):
            env[var] = os.pathsep.join(x for x in (args.lib_path, env.get(var)) if x)

    results = {}
    for key in keys:
        row = curves[key]
        t0 = time.time()
        if row["code"] == "RCN":
            ints = run_rcn(row, args.rcn, _fresh(args.work / "rcn" / key), args.decks_only)
        else:
            ints = run_grasp(row, args.grasp_bin, _fresh(args.work / "grasp" / key), env,
                          args.work, args.decks_only)
        if ints is not None:
            results[key] = ints
            print(f"{key:6s} {row['code']:5s} {row['config']:40s} {time.time() - t0:6.1f} s",
                  flush=True)
    if args.decks_only:
        print(f"wrote the inputs of {len(keys)} curves under {args.work}")
        return 0
    _write(args.out, curves, results)
    if args.compare:
        compare(args.compare, curves, results)
    if args.gate:
        import footing_gate
        footing_gate.main(["--curves", str(args.out), "--allow-missing"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
