"""Shared helpers for refining the guillemot hackathon example patterns."""
from __future__ import annotations

import os
from pathlib import Path

import pxrdref as pr
from pxrdref.schemas.structure import PreferredOrientation, StephensStrain  # noqa: F401

HERE = Path(__file__).resolve().parent

#: The guiLLeMot patterns are NOT vendored here — they belong to another
#: project (MIT, datalab-org/guillemot).  Clone it and point this at its
#: examples/ directory:
#:
#:     git clone --depth 1 https://github.com/datalab-org/guillemot
#:     export GUILLEMOT_EXAMPLES=$PWD/guillemot/examples
EX = Path(os.environ.get("GUILLEMOT_EXAMPLES", HERE / "guillemot" / "examples"))
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)


def require_data() -> Path:
    if not EX.is_dir():
        raise SystemExit(
            f"guiLLeMot example patterns not found at {EX}.\n"
            "  git clone --depth 1 https://github.com/datalab-org/guillemot\n"
            "  export GUILLEMOT_EXAMPLES=$PWD/guillemot/examples")
    return EX

P = pr.Parameter


def hex_cell(a: float, c: float) -> pr.Cell:
    return pr.Cell(a=P(value=a, min=0.1), b=P(value=a, min=0.1), c=P(value=c, min=0.1),
                   alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=120.0))


def rhomb_hex_cell(a: float, c: float) -> pr.Cell:
    return hex_cell(a, c)


def cubic_cell(a: float) -> pr.Cell:
    return pr.Cell.cubic(a)


def atom(label, species, x, y, z, biso=0.5, occ=1.0) -> pr.Atom:
    return pr.Atom(label=label, species=species,
                   x=P(value=x), y=P(value=y), z=P(value=z),
                   occ=P(value=occ, min=0.0, max=1.5),
                   biso=P(value=biso, min=-1.0, max=10.0, unit="A^2"))


def summarise(name: str, result, ref: pr.Refinement, extra: dict | None = None) -> str:
    """One text block per refinement: statistics, parameters, diagnostics."""
    st = result.statistics
    lines = [f"===== {name} =====",
             f"status={result.status}  Rwp={st.rwp * 100:.3f}%  Rp={st.rp * 100:.3f}%  "
             f"Rexp={st.rexp * 100:.3f}%  GoF={st.gof:.3f}  DW={st.durbin_watson:.3f}",
             f"points fitted={st.n_points}  free params={st.n_free_parameters}  "
             f"esd inflation (Berar-Lelann)={st.esd_inflation:.2f}"]
    for ph in ref.fitted_structure.phases:
        c = ph.cell
        lines.append(f"  phase {ph.name!r}: a={c.a.value:.6f} b={c.b.value:.6f} "
                     f"c={c.c.value:.6f} A, gamma={c.gamma.value:.2f} deg, "
                     f"scale={ph.scale.value:.6g}")
        for i, at in enumerate(ph.atoms):
            lines.append(f"      {at.label:5s} {at.species:5s} "
                         f"({at.x.value:.5f},{at.y.value:.5f},{at.z.value:.5f}) "
                         f"occ={at.occ.value:.4f} Biso={at.biso.value:+.4f}")
        lines.append(f"      lor_size={ph.lor_size.value:.5f} lor_strain={ph.lor_strain.value:.5f} "
                     f"gauss_size={ph.gauss_size.value:.5f} gauss_strain={ph.gauss_strain.value:.5f}")
        if ph.preferred_orientation is not None:
            po = ph.preferred_orientation
            lines.append(f"      March-Dollase r={po.r.value:.4f} about {po.axis}")
    inst = ref.fitted_instrument
    lines.append(f"  instrument: zero={inst.zero_shift.value:+.5f} deg  "
                 f"displ={inst.geometry.sample_displacement.value:+.5f} mm")
    lines.append(f"      U={inst.profile.u.value:.5f} V={inst.profile.v.value:.5f} "
                 f"W={inst.profile.w.value:.5f} X={inst.profile.x.value:.5f} "
                 f"Y={inst.profile.y.value:.5f}")
    if len(inst.source.lines) > 1:
        lines.append(f"      Ka2/Ka1 = {inst.source.lines[1].weight.value:.4f}")
    lines.append(f"      FCJ S/L={inst.geometry.axial_sl.value:.4f} "
                 f"H/L={inst.geometry.axial_hl.value:.4f}")
    if result.qpa is not None and len(result.qpa.phases) > 1:
        lines.append("  QPA weight fractions: " + ", ".join(
            f"{p.name}={p.weight_fraction * 100:.2f}"
            f"{'' if p.weight_fraction_stderr is None else f'({p.weight_fraction_stderr * 100:.2f})'}%"
            for p in result.qpa.phases))
    if result.absorption is not None:
        ab = result.absorption
        lines.append(f"  absorption: {ab.method} muR/mut={ab.mu_r:.4f} ({ab.mu_r_source}), "
                     f"equivalent dBiso={ab.equivalent_delta_biso:+.5f} A^2")
    seen = {}
    for d in result.diagnostics:
        seen.setdefault((d.level, d.code), []).append(d.message)
    for (level, code), msgs in seen.items():
        n = f" (x{len(msgs)})" if len(msgs) > 1 else ""
        lines.append(f"  [{level}] {code}{n}: {msgs[0]}")
    for k, v in (extra or {}).items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def esd(result, path):
    p = result.parameter(path)
    return None if p is None else p.stderr
