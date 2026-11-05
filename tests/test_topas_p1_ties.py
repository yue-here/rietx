"""``write_topas_inp(p1_expand="auto", free=...)``: a magnetic phase TOPAS cannot
name, in P1 with every copy tied, and a magnetic-only width as a second ``str``
(#721 items 1 and 3; the showcase's M1, M2, M5 and M10).

The magnetic child here is a k = (½, 0, 0) supercell of a synthetic Pbcm parent
(``tests/topas_export_cases.py``): ``write_topas_inp`` refuses it as it stands
(no keyword for the parent k, no tabulated family group), and ``"auto"`` writes
it in P1. Its TOPAS Y_calc at zero cycles is committed
(``topas_export_child_magnetic_ycalc.txt``); rietx's ``predict()`` of the
original child reproduces it, and the model without its magnetic-only width
does not.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from tests.topas_export_cases import case_child_magnetic, pbcm_child

DATA = Path(__file__).parent / "data"
ORACLE_TOL = 1e-2


def _write(tmp_path, **kw):
    ref, pattern = case_child_magnetic()
    path = tmp_path / "child.inp"
    diags = []
    rx.write_topas_inp(ref.fitted_structure, path, free=ref,
                       instrument=ref.fitted_instrument, pattern=pattern,
                       scale="topas", p1_expand="auto", diagnostics=diags, **kw)
    return ref, path.read_text(encoding="utf-8"), diags


def _strs(text):
    return text.split("\nstr\n")[1:]


def test_auto_restates_what_topas_cannot_name_and_says_so(tmp_path):
    ref, text, diags = _write(tmp_path)
    assert [d.code for d in diags if d.code.startswith("TOPAS_PHASE")] == [
        "TOPAS_PHASE_RESTATED_IN_P1"]
    nuclear, magnetic = _strs(text)
    assert 'space_group "P 1"' in nuclear and "mlx" not in nuclear
    assert "mag_space_group 1.1" in magnetic
    assert 'phase_name "synthetic Pbcm (2a,b,c;0,0,0) magnetic part"' in magnetic
    from rietx.crystallography.symmetry import resolve_group, site_orbit
    child = pbcm_child()
    sg = resolve_group(child.space_group, child.symmetry_operations)
    mult = [site_orbit(sg, [a.x.value, a.y.value, a.z.value]).multiplicity
            for a in child.atoms]
    assert nuclear.count("  site ") == sum(mult)        # every atom of the cell
    assert magnetic.count("  site ") == sum(m for m, a in zip(mult, child.atoms)
                                             if a.moment is not None)
    assert all(ln.rstrip().endswith("mag_only") for ln in magnetic.splitlines()
               if ln.strip().startswith("site "))


def test_auto_leaves_a_phase_topas_can_name_alone(tmp_path):
    from tests.topas_export_cases import case_nacl_neutron
    ref, pattern = case_nacl_neutron()
    path = tmp_path / "n.inp"
    rx.write_topas_inp(ref.fitted_structure, path, free=ref, p1_expand="auto")
    assert 'space_group "F m -3 m"' in path.read_text(encoding="utf-8")


def test_every_copy_is_tied_to_the_parameter_it_copies(tmp_path):
    ref, text, _ = _write(tmp_path)
    nuclear, magnetic = _strs(text)
    # one B per parent site: one name on every copy
    b_names = set(re.findall(r"beq (\w+) ", nuclear))
    assert b_names == {"Fe_1_biso", "O_1_biso"}
    # one moment: a prm in μ_B, every component an equation over it
    assert re.search(r"^prm Fe_1_moment_dof0 3\.0$", text, re.M)
    comps = re.findall(r"mlz = (-?[\d.e-]+)\*Fe_1_moment_dof0;", magnetic)
    assert len(comps) == magnetic.count("  site ")
    assert {np.sign(float(c)) for c in comps} == {-1.0, 1.0}   # the anti-translation
    assert len({abs(float(c)) for c in comps}) == 1
    # the cell stays held, the coordinates the plan held are held
    assert "a ! 10.0" in nuclear and "x = " not in nuclear


def test_the_copies_predict_what_the_original_does():
    """TOPAS's Y_calc for the written file against rietx's own model."""
    ref, _ = case_child_magnetic()
    x, y_topas = np.loadtxt(DATA / "topas_export_child_magnetic_ycalc.txt", unpack=True)
    y = np.asarray(ref.predict(x))
    assert np.abs(y_topas - y).max() / y.max() < ORACLE_TOL
    s = ref.fitted_structure.model_copy(deep=True)
    s.phases[0].magnetic_lor_strain.value = 0.0             # positive arm
    y0 = np.asarray(rx.Refinement(s, ref.fitted_instrument, history=False).predict(x))
    assert np.abs(y_topas - y0).max() / y.max() > 2 * ORACLE_TOL


def test_the_magnetic_part_carries_the_magnetic_widths(tmp_path):
    _, text, _ = _write(tmp_path)
    nuclear, magnetic = _strs(text)
    assert "p0_magnetic_lor_strain" in magnetic and "p0_magnetic_lor_strain" not in nuclear
    assert re.search(r"^prm p0_magnetic_lor_strain 0\.3 min 0$", text, re.M)
    assert re.search(r"^prm !p0_magnetic_lor_size 0$", text, re.M)


def test_without_the_instrument_a_magnetic_width_is_named(tmp_path):
    """No profile to add it to: one str, and TOPAS_FIELD_NOT_WRITTEN names it."""
    ref, _ = case_child_magnetic()
    diags = []
    rx.write_topas_inp(ref.fitted_structure, tmp_path / "x.inp", free=ref,
                       p1_expand="auto", diagnostics=diags)
    assert len(_strs((tmp_path / "x.inp").read_text(encoding="utf-8"))) == 1
    named = [d for d in diags if d.code == "TOPAS_FIELD_NOT_WRITTEN"]
    assert named and "phases.0.magnetic_lor_strain" in named[0].where


def test_true_without_free_is_the_held_list(tmp_path):
    """p1_expand=True with no free set: every copy written, every value held."""
    path = tmp_path / "held.inp"
    rx.write_topas_inp(rx.Structure(phases=[pbcm_child()]), path, p1_expand=True)
    text = path.read_text(encoding="utf-8")
    assert "@" not in text and "mag_space_group 1.1" in text


# ---------------------------------------------------------- review of #912, round 1

def _child_structure(**phase_update):
    child = pbcm_child()
    return rx.Structure(phases=[child.model_copy(update=phase_update)]) if phase_update \
        else rx.Structure(phases=[child])


def test_p1_expand_accepts_only_false_true_and_auto(tmp_path):
    """A truthy 1 or np.True_ is no longer taken for True on one route and ignored on the other."""
    s = _child_structure()
    for bad in (1, np.True_, "yes", None):
        for kw in ({}, {"scale": "rietx"}):
            with pytest.raises(ValueError, match="p1_expand must be"):
                rx.write_topas_inp(s, tmp_path / "x.inp", p1_expand=bad, **kw)
    rx.write_topas_inp(s, tmp_path / "x.inp", p1_expand=True)      # positive arm


def test_bare_auto_writes_the_plain_form_when_no_phase_needs_p1(tmp_path):
    from tests.topas_export_cases import case_nacl_neutron
    ref, _ = case_nacl_neutron()
    s = ref.fitted_structure
    rx.write_topas_inp(s, tmp_path / "auto.inp", p1_expand="auto")
    rx.write_topas_inp(s, tmp_path / "false.inp", p1_expand=False)
    assert (tmp_path / "auto.inp").read_text(encoding="utf-8") == (tmp_path / "false.inp").read_text(encoding="utf-8")


def test_bare_auto_restates_the_phase_that_needs_it(tmp_path):
    diags = []
    rx.write_topas_inp(_child_structure(), tmp_path / "x.inp", p1_expand="auto",
                       diagnostics=diags)
    text = (tmp_path / "x.inp").read_text(encoding="utf-8")
    assert "mag_space_group 1.1" in text
    assert any(d.code == "TOPAS_PHASE_RESTATED_IN_P1" for d in diags)


def test_auto_does_not_swallow_a_refusal_p1_does_not_fix(tmp_path):
    """No site moment, and a phase's own k: P 1 carries neither, so they still raise."""
    child = pbcm_child()
    bare = [a.model_copy(update={"moment": None}) for a in child.atoms]
    with pytest.raises(ValueError, match="no site moment"):
        rx.write_topas_inp(_child_structure(atoms=bare), tmp_path / "a.inp",
                           p1_expand="auto", scale="rietx")
    with pytest.raises(ValueError, match="propagation vector"):
        rx.write_topas_inp(_child_structure(propagation_vector=("1/2", "0", "0")),
                           tmp_path / "b.inp", p1_expand="auto", scale="rietx")
    rx.write_topas_inp(_child_structure(), tmp_path / "c.inp",       # positive arm
                       p1_expand="auto", scale="rietx")


def test_p1_copy_labels_are_unique(tmp_path):
    """`Fe` on a general position of P -1 writes Fe_1, Fe_2; a one-image `Fe_1` beside it is not a repeat."""
    child = pbcm_child()
    base = child.atoms[0].model_copy(update={"moment": None, "species": "Fe"})

    def site(label, xyz):
        return base.model_copy(update={
            "label": label, **{k: base.x.model_copy(update={"value": v})
                               for k, v in zip("xyz", xyz)}})
    phase = child.model_copy(update={
        "space_group": "P -1", "magnetic_symmetry": None,
        "atoms": [site("Fe", (0.1, 0.2, 0.3)), site("Fe_1", (0.0, 0.0, 0.0))]})
    rx.write_topas_inp(rx.Structure(phases=[phase]), tmp_path / "x.inp",
                       p1_expand=True, scale="rietx")
    labels = re.findall(r"^  site (\S+)", (tmp_path / "x.inp").read_text(encoding="utf-8"), re.M)
    assert len(labels) == 3 and len(set(labels)) == 3, labels


def test_a_magnetic_width_with_extinction_is_refused(tmp_path):
    ref, pattern = case_child_magnetic()
    s = ref.fitted_structure.model_copy(deep=True)
    s.phases[0].extinction = 5.0
    with pytest.raises(ValueError, match="extinction"):
        rx.write_topas_inp(s, tmp_path / "x.inp", p1_expand="auto", free=ref,
                           instrument=ref.fitted_instrument, pattern=pattern,
                           scale="topas")
    _write(tmp_path)                                                 # positive arm


def test_run_control_needs_a_pattern_as_well_as_an_instrument(tmp_path):
    ref, pattern = case_child_magnetic()
    kw = dict(free=ref, instrument=ref.fitted_instrument, scale="topas", p1_expand="auto")
    rx.write_topas_inp(ref.fitted_structure, tmp_path / "i.inp", **kw)
    assert "r_wp 0" not in (tmp_path / "i.inp").read_text(encoding="utf-8")
    rx.write_topas_inp(ref.fitted_structure, tmp_path / "p.inp", pattern=pattern, **kw)
    assert "r_wp 0" in (tmp_path / "p.inp").read_text(encoding="utf-8")
