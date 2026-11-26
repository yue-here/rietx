"""Write ``src/rietx/data/mff_computed.dat`` from the computed curves.

The data file holds every magnetic form-factor curve rietx computed for itself
rather than transcribed from a publication:

* **tables**: ⟨j₀⟩, ⟨j₂⟩ and ⟨j₄⟩ on s = sinθ/λ = 0-6 Å⁻¹ at 0.01, for the ions
  served from a computed curve over their whole range (the ten high-charge 4d
  ions of rietx issue #1691, the neutral Mo, Tc, Ru, Rh and Pd atoms, Pr³⁺
  and Pu³⁺);
* **tails**: ⟨j₀⟩ and ⟨j₂⟩ from the end of the range Brown fitted a row over
  (s_end = 1.5 Å⁻¹ for 3d, 4d and actinide rows, 1.2 for rare earths) to
  s = 6, for every other row rietx carries in Brown's analytic form.

Usage::

    python write_data_file.py --curves <dir> --d32 <dir> --out mff_computed.dat

``--curves`` holds the long-format CSVs that ``regenerate.py`` writes
(``tails_3d.csv``, ``tails_4d.csv``, ``tails_4f.csv``, ``tails_5f.csv``,
``neutral_4d.csv``, ``bare_rows.csv``); ``--d32`` holds the ten
``<ion>_HFR.csv`` tables it writes on a 0.005 Å⁻¹ grid (its ``d32/``), of
which every second point is taken.

Every value is written ``%.7f``: rounding moves it by at most 5 × 10⁻⁸, under
the 1 × 10⁻⁷ the curves are checked to. Nothing here computes a curve; it only
selects, checks and formats.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

#: The s grid every curve is on (ruled on 2026-11-23, https://github.com/yue-here/rietx/issues/1691#issuecomment-7095775367).
STEP = 0.01
S_LAST = 6.0
N_FULL = 601

#: Where Brown's fitted range ends, per family (ITC Vol. C § 4.4.5, p. 461).
S_END = {"3d": 1.5, "4d": 1.5, "4f": 1.2, "5f": 1.5}

#: The ten high-charge 4d ions proposed in https://github.com/yue-here/rietx/issues/1691 (2026-11-18).
D32_IONS = ("Ru3+", "Ru4+", "Ru5+", "Ru6+", "Rh4+", "Tc4+", "Mo3+", "Mo4+",
            "Mo5+", "Nb4+")
D32_CONFIG = {"Ru3+": "4d5", "Ru4+": "4d4", "Ru5+": "4d3", "Ru6+": "4d2",
              "Rh4+": "4d5", "Tc4+": "4d3", "Mo3+": "4d3", "Mo4+": "4d2",
              "Mo5+": "4d1", "Nb4+": "4d1"}

#: Neutral 4d rows: data-file key -> public label.
NEUTRAL = {"Mo0": "Mo", "Tc0": "Tc", "Ru0": "Ru", "Rh0": "Rh", "Pd0": "Pd"}

#: A neutral row not in its ground configuration, and what its configuration
#: line says instead of "neutral ground configuration".  Pd's ground 4d10 1S
#: has no open shell to carry a moment; the row is the lowest magnetic
#: configuration, as Brown's bare Nb and Sc rows are excited configurations
#: (https://github.com/yue-here/rietx/issues/1691#issuecomment-7098289449;
#: https://github.com/yue-here/rietx/pull/1806#issuecomment-7115570833).
NEUTRAL_EXCITED = {"Pd0": "neutral, excited configuration; ground 4d10 1S"}

#: Rows served from a whole computed table instead of a Brown row
#: (rietx issue #1804 for Pu3+; Pr3+ replaces Lisher & Forsyth's row).
WHOLE_FROM_TAILS = {"Pu3+": "5f", "Pr3+": "4f"}

#: Brown's bare rows not carried: each is a singly charged ion's curve, and the
#: bare label is served from its neutral table (NEUTRAL) instead.
DROPPED = {"Mo", "Tc", "Ru", "Rh", "Pd"}

RCN = "Cowan RCN Mod 36.2.5"
GRASP = "GRASP2018"

#: The note each bare (neutral-labelled) row carries into approximation_name,
#: from the configuration scan (bare_rows.csv verdicts).
BARE_NOTE = {
    "Sc": "neutral Sc in an excited configuration, 3d2 4s 4F (ground 3d 4s2 2D)",
    "Ti": "neutral Ti ground configuration 3d2 4s2 in the non-Hund term 1G (ground term 3F)",
    "V": "neutral V ground configuration 3d3 4s2, configuration average",
    "Cr": "footing not identified (no configuration scanned matches the row)",
    "Mn": "neutral Mn ground configuration 3d5 4s2, configuration average",
    "Fe": "neutral Fe ground configuration 3d6 4s2, configuration average",
    "Co": "neutral Co ground configuration 3d7 4s2, configuration average",
    "Ni": "footing not identified (no configuration scanned matches the row)",
    "Cu": "neutral Cu ground configuration 3d10 4s, configuration average",
    "Y": "neutral Y ground configuration 4d 5s2, configuration average",
    "Zr": "neutral Zr ground configuration 4d2 5s2 3F",
    "Nb": "neutral Nb in an excited configuration, 4d3 5s2 4F (ground 4d4 5s 6D)",
}

#: The verdict bare_rows.csv must carry for each bare row the note above
#: states, so a rerun of the scan that moves a verdict stops this writer.
BARE_VERDICT = {
    "Sc": "NEUTRAL excited configuration 3d2 4s1 4F",
    "Ti": "NEUTRAL ground configuration, non-Hund term 1G",
    "V": "NEUTRAL ground configuration, configuration average",
    "Cr": "UNMATCHED",
    "Mn": "NEUTRAL ground configuration, configuration average",
    "Fe": "NEUTRAL ground configuration, configuration average",
    "Co": "NEUTRAL ground configuration, configuration average",
    "Ni": "UNMATCHED",
    "Cu": "NEUTRAL ground configuration",
    "Y": "NEUTRAL ground configuration",
    "Zr": "NEUTRAL ground configuration",
    "Nb": "NEUTRAL excited configuration 4d3 5s2 4F",
}

HEADER = """\
# mff_computed.dat -- magnetic form-factor radial integrals <j_n>(s) computed
# for rietx.
#
# STATUS: COMPUTED FOR RIETX, NOT PEER-REVIEWED. Every number below was
# computed for this package from free-ion radial wavefunctions, with Cowan's
# RCN (Hartree-Fock or Hartree-Fock-relativistic) or with GRASP2018
# (Dirac-Fock). None is transcribed from a publication, and no publication has
# reviewed them. Each block's header names its code, its footing and its
# configuration. The input decks and the scripts that regenerate and check
# every number are in the rietx repository under tools/magnetic_form_factors/
# (not shipped in the wheel); the codes themselves are not part of rietx.
#
# CODES:  R. D. Cowan, RCN Mod 36.2.5 (Cowan, The Theory of Atomic Structure
#         and Spectra, University of California Press, 1981,
#         doi:10.1525/9780520906150). C. Froese Fischer, G. Gaigalas,
#         P. Jonsson & J. Bieron, GRASP2018, Comput. Phys. Commun. 237,
#         184-187 (2019), doi:10.1016/j.cpc.2018.10.032.
#
# CHECKS (the numbers are in tools/magnetic_form_factors/README.md):
#   - the 3d/4d curves reproduce Brown's ITC Vol. C sec. 4.4.5 rows to his
#     printed fit error (median 100 x rms / e = 1.03 over his grid);
#   - the 4f curves reproduce Freeman & Desclaux (1979) Table 7, 1508 of 1511
#     cells within 0.6e-4, and the 5f curves Desclaux & Freeman (1978)
#     Table 6, U3+/U4+ 167 of 168 cells within 1.23e-4 and Pu3+ 84 of 84
#     within 5.3e-5;
#   - every curve is converged to about 1e-8.
#
# A FREE-ION CURVE. Beyond about s = 1.2 A^-1 a crystal's form factor departs
# from any free-ion curve (covalency, the aspherical <j4> term); the manual's
# section on the dipole approximation states the size.
#
# FORMAT. s = sin(theta)/lambda in A^-1. <j0>(0) = 1; <j2> and <j4> are the
# full radial integrals (<j_n>(0) = 0 for n >= 2), not Brown's s^-2-stripped
# fits. Blocks, each opened by
#   @ <key> <kind> <orders...>
#   % footing: <code and footing>
#   % configuration: <the configuration computed>
#   % row: <what a bare (neutral-labelled) row is>          (bare rows only)
# and followed by one line per s, "s v_1 v_2 [v_3]", s from the block's first
# point to 6.00 in steps of 0.01. <kind> is
#   table -- the whole curve, s = 0-6; it serves the ion on its own;
#   tail  -- s = s_end-6, the computed curve past the range Brown fitted the
#            row over (s_end = 1.5 for 3d, 4d and actinide rows, 1.2 for rare
#            earths); rietx blends Brown's row onto it over s_end to
#            s_end + 0.2.
# A key ending in 0 (Mo0, Tc0, Ru0, Rh0, Pd0) is the neutral atom in the
# configuration its block names: the ground configuration, except Pd0, the
# excited 4d9 5s 3D (ground 4d10 1S has no open shell). rietx serves it under
# the bare symbol. Values are %.7f.
"""


def _fmt(v: float) -> str:
    out = f"{v:.7f}"
    return "0.0000000" if out == "-0.0000000" else out


def _grid(first: float) -> list[str]:
    k0 = round(first / STEP)
    return [f"{k * STEP:.2f}" for k in range(k0, N_FULL)]


def _long(path: Path) -> dict[str, dict]:
    """label -> {order: [(s, value)], 'footing', 'code', 'config'}."""
    out: dict[str, dict] = defaultdict(lambda: defaultdict(list))
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            rec = out[r["label"]]
            rec[r["order"]].append((r["s"], float(r["value"])))
            for k in ("footing", "code", "config"):
                prev = rec.get(k)
                if prev is not None and not isinstance(prev, list) and prev != r[k]:
                    raise ValueError(f"{path.name}: {r['label']} changes {k} mid-curve")
                rec[k] = r[k]
    return out


def _check_curve(label: str, order: str, pts) -> list[float]:
    s = [p[0] for p in pts]
    if s != _grid(0.0):
        raise ValueError(f"{label} {order}: not on s = 0-6 at 0.01")
    v = [p[1] for p in pts]
    if order == "j0" and abs(v[0] - 1.0) > 5e-9:
        raise ValueError(f"{label} j0(0) = {v[0]}, not 1")
    if order != "j0" and v[0] != 0.0:
        raise ValueError(f"{label} {order}(0) = {v[0]}, not 0")
    if not all(math.isfinite(x) for x in v):
        raise ValueError(f"{label} {order}: non-finite value")
    return v


def _footing_rcn(config: str, label: str) -> str:
    if config.endswith(" avg"):
        return f"{RCN}, Hartree-Fock (IREL=0, CORRF=0), configuration average"
    if label == "Ti":
        return f"{RCN}, Hartree-Fock (IREL=0, CORRF=0), LS term 1G (non-Hund)"
    return f"{RCN}, Hartree-Fock (IREL=0, CORRF=0), Hund's-rule LS term"


def _footing_grasp() -> str:
    return (f"{GRASP}, Dirac-Fock, average level (EOL over every level of every "
            f"J block, standard weights)")


def _block(key, kind, orders, first, columns, footing, config, row=None) -> list[str]:
    lines = [f"@ {key} {kind} {' '.join(orders)}", f"% footing: {footing}",
             f"% configuration: {config}"]
    if row:
        lines.append(f"% row: {row}")
    for i, s in enumerate(_grid(first)):
        lines.append(" ".join([s] + [_fmt(col[i]) for col in columns]))
    return lines


def _d32(path: Path, ion: str) -> list[list[float]]:
    """The ten D32 tables: s = 0-6 at 0.005, every second point taken."""
    rows = []
    with open(path) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    reader = csv.DictReader(lines)
    for r in reader:
        rows.append(r)
    if len(rows) != 2 * (N_FULL - 1) + 1:
        raise ValueError(f"{path.name}: {len(rows)} rows, expected 1201")
    take = rows[::2]
    want = [f"{k * STEP:.3f}" for k in range(N_FULL)]
    if [r["s_invA"] for r in take] != want:
        raise ValueError(f"{path.name}: the even rows are not s = 0, 0.01, ..., 6")
    cols = [[float(r[o]) for r in take] for o in ("j0", "j2", "j4")]
    if cols[0][0] != 1.0:
        raise ValueError(f"{ion} j0(0) = {cols[0][0]}, not 1")
    return cols


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--curves", type=Path, required=True)
    ap.add_argument("--d32", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    bare = {r["label"]: r for r in csv.DictReader(open(args.curves / "bare_rows.csv"))}
    for label, want in BARE_VERDICT.items():
        if not bare[label]["verdict"].startswith(want):
            raise ValueError(f"bare_rows.csv: {label} verdict {bare[label]['verdict']!r}")

    out = HEADER.splitlines()
    # whole tables: D32 ions, neutral 4d, Pr3+, Pu3+
    for ion in D32_IONS:
        cols = _d32(args.d32 / f"{ion}_HFR.csv", ion)
        out += [""] + _block(
            ion, "table", ("j0", "j2", "j4"), 0.0, cols,
            f"{RCN}, Hartree-Fock-relativistic (HFR), configuration average "
            f"(IREL=1, CORRF=1)", f"{ion} {D32_CONFIG[ion]}")
    neutral = _long(args.curves / "neutral_4d.csv")
    for key in NEUTRAL:
        rec = neutral[key]
        cols = [_check_curve(key, o, rec[o]) for o in ("j0", "j2", "j4")]
        cfg = rec["config"].split(" (")[0].replace("5s1", "5s")
        state = NEUTRAL_EXCITED.get(key, "neutral ground configuration")
        out += [""] + _block(key, "table", ("j0", "j2", "j4"), 0.0, cols,
                             f"{RCN}, Hartree-Fock (IREL=0, CORRF=0), Hund's-rule LS term",
                             f"{cfg} ({state})")
    families = {f: _long(args.curves / f"tails_{f}.csv") for f in S_END}
    for ion, fam in WHOLE_FROM_TAILS.items():
        rec = families[fam][ion]
        cols = [_check_curve(ion, o, rec[o]) for o in ("j0", "j2", "j4")]
        out += [""] + _block(ion, "table", ("j0", "j2", "j4"), 0.0, cols,
                             _footing_grasp(), rec["config"])
    # tails: every other Brown row, j0 and j2 from s_end
    for fam, recs in families.items():
        k0 = round(S_END[fam] / STEP)
        for label, rec in recs.items():
            if label in WHOLE_FROM_TAILS or label in DROPPED:
                continue
            cols = [_check_curve(label, o, rec[o])[k0:] for o in ("j0", "j2")]
            footing = (_footing_rcn(rec["config"], label) if fam in ("3d", "4d")
                       else _footing_grasp())
            out += [""] + _block(label, "tail", ("j0", "j2"), S_END[fam], cols,
                                 footing, rec["config"], BARE_NOTE.get(label))
    args.out.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
