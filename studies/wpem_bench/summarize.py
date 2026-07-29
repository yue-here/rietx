"""Collect ``results/*.json`` into the tables REPORT.md quotes.

Run after every case has been run:  .venv/bin/python studies/wpem_bench/summarize.py
"""

from __future__ import annotations

import json

from bench import RESULTS

ORDER = ["pbso4", "tb2bacoo5", "nacl_li2co3_10", "nacl_li2co3_40",
         "nacl_li2co3_50", "ti15nb", "egypt", "mnru", "insitu"]
TITLES = {
    "pbso4": "PbSO4 (Fig. 2a)",
    "tb2bacoo5": "Tb2BaCoO5 (Fig. 2b)",
    "nacl_li2co3_10": "NaCl/Li2CO3 90 wt% (Fig. 2e)",
    "nacl_li2co3_40": "NaCl/Li2CO3 40 wt% (Fig. 2e)",
    "nacl_li2co3_50": "NaCl/Li2CO3 50 wt% (Fig. 2e)",
    "ti15nb": "Ti-15Nb 3-phase (Fig. 2d)",
    "egypt": "Egyptian make-up (Fig. 4)",
    "mnru": "(Mn,Ru)2O3 (Fig. 3b)",
    "insitu": "operando LixNiyO2 (Fig. 3a)",
}


def load_all() -> dict[str, dict]:
    out = {}
    for key in ORDER:
        path = RESULTS / f"{key}.json"
        if path.exists():
            out[key] = json.loads(path.read_text())
    return out


def fmt(value, spec="6.3f"):
    return "—" if value is None else format(value, spec)


def agreement_table(cases: dict[str, dict]) -> str:
    rows = ["| case | pts | pxrdref Rwp | WPEM Rwp | pxrdref Rp | WPEM Rp | "
            "pxrdref n_free | GoF | s |",
            "|---|---|---|---|---|---|---|---|---|"]
    for key, rec in cases.items():
        if key == "insitu":
            continue
        ref = rec.get("reference", {})
        rows.append(
            f"| {TITLES[key]} | {rec['n_points']} | "
            f"{rec['rwp'] * 100:.3f}% | {fmt(ref.get('rwp_percent'), '.3f')}% | "
            f"{rec['rp'] * 100:.3f}% | {fmt(ref.get('rp_percent'), '.3f')}% | "
            f"{rec['n_free']} | {rec['gof']:.2f} | {rec['seconds']:.0f} |")
    return "\n".join(rows)


def lebail_table(cases: dict[str, dict]) -> str:
    rows = ["| case | pxrdref Le Bail Rwp | n_free | WPEM Rwp | WPEM method |",
            "|---|---|---|---|---|"]
    for key, rec in cases.items():
        lb = rec.get("reference", {}).get("lebail")
        if not lb:
            continue
        ref = rec["reference"]
        rows.append(f"| {TITLES[key]} | {lb['rwp_percent']:.3f}% | "
                    f"{lb['n_free']} | {fmt(ref.get('rwp_percent'), '.3f')}% | "
                    f"per-reflection free shapes |")
    return "\n".join(rows)


def qpa_table(cases: dict[str, dict]) -> str:
    rows = ["| mixture | weighed NaCl wt% | pxrdref | error | WPEM | error |",
            "|---|---|---|---|---|---|"]
    for key in ("nacl_li2co3_10", "nacl_li2co3_40", "nacl_li2co3_50"):
        rec = cases.get(key)
        if not rec:
            continue
        nominal = rec["reference"]["nominal_nacl_percent"]
        wpem = rec["reference"]["wpem_nacl_percent"]
        ours = rec["weight_fractions"].get("NaCl", float("nan")) * 100
        sigma = rec["weight_fraction_esds"].get("NaCl")
        ours_txt = (f"{ours:.2f}%" if sigma is None
                    else f"{ours:.2f} ± {sigma * 100:.2f}%")
        rows.append(f"| {nominal:.0f} wt% | {nominal:.1f} | {ours_txt} | "
                    f"{ours - nominal:+.2f} | {wpem:.2f}% | {wpem - nominal:+.2f} |")
    return "\n".join(rows)


def cell_table(cases: dict[str, dict]) -> str:
    rows = ["| case | phase | axis | pxrdref | WPEM | Δ (ppm) |",
            "|---|---|---|---|---|---|"]
    plans = [
        ("pbso4", "PbSO4_pnma", ("a", "b", "c"), lambda r: r["reference"]),
        ("tb2bacoo5", "Tb2BaCoO5", ("a", "b", "c"), lambda r: r["reference"]),
    ]
    for key, phase, axes, refget in plans:
        rec = cases.get(key)
        if not rec or phase not in rec["cells"]:
            continue
        ref = refget(rec)
        for axis in axes:
            ours = rec["cells"][phase][axis]
            theirs = ref.get(axis)
            if theirs is None:
                continue
            rows.append(f"| {TITLES[key]} | {phase} | {axis} | {ours:.5f} | "
                        f"{theirs:.5f} | {(ours / theirs - 1) * 1e6:+.0f} |")
    for key, refkey in (("ti15nb", "cells"), ("egypt", "paper_cells")):
        rec = cases.get(key)
        if not rec:
            continue
        for phase, ref_cell in rec["reference"].get(refkey, {}).items():
            if phase not in rec["cells"]:
                continue
            for axis, theirs in ref_cell.items():
                ours = rec["cells"][phase][axis]
                rows.append(f"| {TITLES[key]} | {phase} | {axis} | {ours:.5f} | "
                            f"{theirs:.5f} | {(ours / theirs - 1) * 1e6:+.0f} |")
    return "\n".join(rows)


def egypt_table(cases: dict[str, dict]) -> str:
    rec = cases.get("egypt")
    if not rec:
        return "_(not run)_"
    rows = ["| phase | pxrdref wt% | paper wt% | shipped CASES wt% |",
            "|---|---|---|---|"]
    for name, paper in rec["reference"]["paper_mass_percent"].items():
        ours = rec["weight_fractions"].get(name)
        sigma = rec["weight_fraction_esds"].get(name)
        ours_txt = ("—" if ours is None else
                    (f"{ours * 100:.2f}" if sigma is None
                     else f"{ours * 100:.2f} ± {sigma * 100:.2f}"))
        cases_pct = rec["reference"]["cases_mass_percent"][name]
        rows.append(f"| {name} | {ours_txt} | {paper:.2f} | {cases_pct:.2f} |")
    return "\n".join(rows)


def main() -> None:
    cases = load_all()
    missing = [k for k in ORDER if k not in cases]
    print(f"# loaded {len(cases)} cases; missing: {missing or 'none'}\n")
    for heading, table in (
            ("Agreement factors", agreement_table(cases)),
            ("Structure-free comparison (Le Bail vs WPEM decomposition)",
             lebail_table(cases)),
            ("QPA against weighed truth", qpa_table(cases)),
            ("Lattice parameters", cell_table(cases)),
            ("Egyptian make-up mass fractions", egypt_table(cases))):
        print(f"## {heading}\n")
        print(table, "\n")
    insitu = cases.get("insitu")
    if insitu:
        c = insitu.get("c_expand_then_collapse") or {}
        print("## operando series\n")
        print(f"- {insitu['n_patterns']} patterns in {insitu['seconds']:.0f} s "
              f"({insitu['seconds_per_pattern']:.2f} s each), "
              f"median Rwp {insitu['rwp_median'] * 100:.2f}%")
        if c:
            print(f"- c axis {c['start']:.4f} → max {c['max']:.4f} Å at pattern "
                  f"{c['max_at_pattern']} → {c['end']:.4f} Å")
        print(f"- forward/backward path-dependent parameters: "
              f"{len(insitu['path_dependent'])}")


if __name__ == "__main__":
    main()
