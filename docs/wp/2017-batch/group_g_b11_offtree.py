"""WP-2017 group G part B (PR #1577): the two off-tree 11-BM cases, loaded by ``group_g_b11.py``.

- ``cr2wo6``: Cr2WO6 with Cr2O3 under 1 wt %, the 295 K APS 11-BM pattern of the 3-minute SPS
  pellet (sample mg141).  Data from M. W. Gaultois, M. C. Kemei, J. K. Harada and R. Seshadri,
  J. Appl. Phys. 117, 014105 (2015), doi:10.1063/1.4905486.  Reference: the authors' TOPAS
  refinement, 0.957 wt % Cr2O3.
- ``geco``: GeCo2O4 at 6.6 K with Co10Ge3O16, APS 11-BM.  Data from P. T. Barton, M. C. Kemei,
  M. W. Gaultois, S. L. Moffitt, L. E. Darago, R. Seshadri, M. R. Suchomel and B. C. Melot,
  Phys. Rev. B 90, 064105 (2014), doi:10.1103/PhysRevB.90.064105.  The start is the authors'
  GSAS ``.EXP`` (origin choice 2); reference: their TOPAS refinement, 1.374 wt % Co10Ge3O16.

The patterns are not in the tree; put the three files named below in ``WP2017G_EXT``.  The
structures of ``cr2wo6`` are written here from the authors' refinement.
"""
import tempfile
from pathlib import Path

import rietx as rx
from rietx.schemas.instrument import BackgroundChebyshev

BASES = ("cr2wo6", "geco")
MINOR = {"cr2wo6": "Cr2O3", "geco": "Co10Ge3O16"}
REF_WT = {"cr2wo6": 0.957, "geco": 1.374}

MG141 = "mg141_cr2wo6_sps_3min.fxye"
GECO_XYE = "GeCo2O4_6_6K.xye"
GECO_EXP = "GECO2O4_RECIPROCAL_BKGRND_KEMEI.EXP"
FILES = (MG141, GECO_XYE, GECO_EXP)

_CR2WO6 = """data_Cr2WO6
_cell_length_a 4.579277
_cell_length_b 4.579277
_cell_length_c 8.866342
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 42/m n m'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_B_iso_or_equiv
Cr1 Cr3+ 0 0 0.33487 0.134
W1 W6+ 0 0 0 0.207
O1 O2- 0.29893 0.29893 0 0.347
O2 O2- 0.30601 0.30601 0.34010 0.257
"""
_CR2O3 = """data_Cr2O3
_cell_length_a 4.959422
_cell_length_b 4.959422
_cell_length_c 13.594640
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 120
_symmetry_space_group_name_H-M 'R -3 c :H'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_B_iso_or_equiv
Cr1 Cr3+ 0 0 0.34656 0.3
O1 O2- 0.30999 0 0.25 0.5
"""


def available(ext: Path) -> bool:
    """True when every off-tree file is in ``ext``."""
    return all((ext / name).is_file() for name in FILES)


def _11bm(prm: Path, wavelength: float) -> rx.Instrument:
    ins = rx.read_gsas_prm(prm)
    ins.source.lines[0].wavelength.value = wavelength
    ins.background = BackgroundChebyshev.with_terms(8)
    return ins


def _from_cifs(texts: list[str], names: list[str]) -> rx.Structure:
    with tempfile.TemporaryDirectory() as td:
        phases = []
        for text, name in zip(texts, names):
            path = Path(td) / f"{name}.cif"
            path.write_text(text, encoding="utf-8")
            ph = rx.Structure.from_cif(path).phases[0]
            ph.name = name
            phases.append(ph)
    return rx.Structure(phases=phases)


def database_start(base, g, EXT):
    """(data, structure, instrument, plan, fit kwargs) for ``base``; ``g`` is ``group_g``."""
    prm = g.CUCR / "OH_00.prm"  # the 11-BM instrument file the CuCr2O4 ramp uses
    if base == "cr2wo6":
        st = _from_cifs([_CR2WO6, _CR2O3], ["Cr2WO6", "Cr2O3"])
        st.phases[0].scale.value, st.phases[1].scale.value = 1.0, 0.01
        data = rx.read_pattern(EXT / MG141)
        return (data, st, _11bm(prm, 0.413682), rx.RefinementPlan.mccusker_default(),
                {"two_theta_limits": (5.1, 28.0)})
    if base == "geco":
        from rietx.io.projects.gsas import to_structure
        from tests.test_acceptance_qpa_roundrobin import seed_scales
        model = rx.read_gsas_exp(EXT / GECO_EXP)
        st = to_structure(model, phase=1)
        st.phases = list(st.phases) + list(to_structure(model, phase=2).phases)
        st.phases[0].space_group = "I 41/a m d :2"
        for atom in st.phases[0].atoms:
            for c in (atom.x, atom.y, atom.z):
                c.vary = False
        data = rx.read_pattern(EXT / GECO_XYE)
        ins = _11bm(prm, 0.4131730)
        seed_scales(st, ins, data)
        st.phases[1].scale.value = st.phases[0].scale.value * 1.44e-3
        return (data, st, ins, rx.RefinementPlan.mccusker_default(),
                {"two_theta_limits": (4.001, 43.996)})
    raise KeyError(base)
