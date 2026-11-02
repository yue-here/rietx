"""``write_topas_inp(free=, scale=)``: what the written file refines, how its
numbers are tied, and the scale in TOPAS's convention (#722, #721 item 3).

A plan *replaces* the vary flags per stage, so after a plan-driven fit the
models carry ``vary=False`` everywhere while the fit's free set lives in
``Refinement.parameters()``. The tests below build that state directly and
check that the file states the free set, the ties and the scale, and that the
default (no new keyword) writes exactly what it wrote before.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.projects.topas import TopasInpError, from_structure
from rietx.io.projects.topas_refined import (
    NEUTRON_SCALE_FACTOR,
    Affine,
    RefinedSet,
    number,
    topas_scale_factor,
)
from tests.topas_export_cases import case_nacl_neutron, nacl

DATA = Path(__file__).parent / "data"


def _pnma():
    """A synthetic Pnma phase: one general and one mirror site, as a plan leaves
    it (every stored flag False)."""
    from rietx.schemas.common import Parameter as P
    from rietx.schemas.structure import Atom, Cell, Phase

    def at(label, sp, xyz):
        return Atom(label=label, species=sp, x=P(value=xyz[0]), y=P(value=xyz[1]),
                    z=P(value=xyz[2]), biso=P(value=0.7, min=0.0, max=25.0))
    return Phase(name="synthetic Pnma", space_group="P n m a",
                 cell=Cell(a=P(value=10.0), b=P(value=6.0), c=P(value=5.0),
                           alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
                 atoms=[at("A1", "Ba", (0.17, 0.02, 0.38)),
                        at("B1", "Fe", (0.10, 0.25, 0.66)),
                        at("B2", "Fe", (0.30, 0.25, 0.16))],
                 scale=P(value=0.01, min=0.0, transform="softplus"))


def _ref():
    ref = rx.Refinement(rx.Structure(phases=[_pnma()]),
                        rx.Instrument.constant_wavelength_neutron(2.4), history=False)
    ref.set_vary(["phases.0.scale", "phases.0.cell.*", "phases.0.atoms.*.dof.*",
                  "phases.0.atoms.*.biso"], True)
    return ref


def _site(text, label):
    return next(ln for ln in text.splitlines() if ln.strip().startswith(f"site {label} "))


def test_a_plan_driven_fit_writes_no_refine_flag_by_default():
    """The gap #722 reports, pinned: the models carry the input's flags."""
    ref = _ref()
    text = from_structure(ref.fitted_structure)
    assert "@" not in text
    assert sum(1 for p in ref.parameters() if p.vary) > 10


def test_free_writes_every_parameter_the_fit_freed():
    ref = _ref()
    text = from_structure(ref.fitted_structure, free=ref)
    free = {r.path for r in ref.parameters() if r.vary}
    assert "phases.0.atoms.0.dof.0" in free
    a1 = _site(text, "A1")
    # a coordinate refined through its site-symmetry DOF is named after itself
    assert re.search(r"\bx A1_x 0\.17\b", a1) and re.search(r"\by A1_y 0\.02\b", a1)
    b1 = _site(text, "B1")
    assert "y ! 0.25" in b1                      # the mirror holds y
    assert "beq B1_biso 0.7 min 0 max 25" in b1  # rietx's bounds travel
    assert re.search(r"scale p0_scale 0\.01\b", text)
    assert re.search(r"\ba p0_cell_a 10\.0\b", text)


def test_a_free_set_of_paths_is_enough_without_ties():
    ref = _ref()
    paths = [r.path for r in ref.parameters() if r.vary]
    text = from_structure(ref.fitted_structure, free=paths)
    assert re.search(r"beq A1_biso 0\.7", text)
    assert "scale p0_scale" in text


def test_tie_equal_is_one_name_written_twice():
    """§ 2.3: 'parameters with names that are the same must have the same value'."""
    ref = _ref()
    ref.tie_equal(["phases.0.atoms.1.biso", "phases.0.atoms.2.biso"])
    text = from_structure(ref.fitted_structure, free=ref)
    assert "beq B1_biso 0.7" in _site(text, "B1")
    assert "beq B1_biso 0.7" in _site(text, "B2")


def test_an_affine_tie_is_an_equation_over_its_source():
    ref = _ref()
    ref.tie("phases.0.atoms.2.biso", "phases.0.atoms.1.biso", scale=2.0, offset=-0.7)
    text = from_structure(ref.fitted_structure, free=ref)
    assert "beq = 2.0*B1_biso - 0.7;" in _site(text, "B2")
    assert "beq B1_biso 0.7" in _site(text, "B1")   # the source, carried where it is


def test_the_default_writes_byte_for_byte_what_it_wrote_before():
    ref = _ref()
    plain = from_structure(ref.fitted_structure)
    assert plain == from_structure(ref.fitted_structure, free=None, scale=None)
    assert "p0_scale" not in plain and "' scale:" not in plain


def test_scale_topas_needs_the_radiation():
    ref = _ref()
    with pytest.raises(ValueError, match="instrument"):
        from_structure(ref.fitted_structure, scale="topas")
    with pytest.raises(ValueError, match="'rietx' or 'topas'"):
        from_structure(ref.fitted_structure, scale="fullprof", free=ref)


def test_the_scale_is_written_in_topas_units_and_says_so():
    ref = _ref()
    text = from_structure(ref.fitted_structure, free=ref, scale="topas",
                          instrument=rx.Instrument.constant_wavelength_neutron(2.4))
    assert re.search(r"scale p0_scale 1\.0\b", text)       # 0.01 × 100
    assert "rietx Phase.scale x 100.0" in text
    rietx_units = from_structure(ref.fitted_structure, free=ref, scale="rietx")
    assert "NOT TOPAS's convention" in rietx_units


def test_the_scale_constants():
    """Restates the implementation's formula, so it **cannot fail** and holds
    nothing: the neutron × 100 is held by the fixture test below, and the X-ray
    × K has no oracle in this tree (taken from the Technical Reference's
    ``LP_Factor`` definition; see ``topas_refined``'s docstring)."""
    assert topas_scale_factor(rx.Instrument.constant_wavelength_neutron(2.0)) == 100.0
    xray = rx.Instrument.bragg_brentano(radiation="CuKa")
    assert topas_scale_factor(xray) == pytest.approx(xray.source.polarization.value)


def test_the_neutron_constant_reproduces_topas_own_intensity():
    """TOPAS-64 v6's Y_calc at zero cycles for our NaCl case
    (``topas_export_cases.case_nacl_neutron``, scale written × 100):
    rietx's ``predict()`` at the rietx scale equals it to 0.06 % in the median
    (TOPAS integrates whole Lorentzian tails where rietx's windows hold 98 % of
    the area). A wrong constant is off by a factor of 100."""
    ref, _ = case_nacl_neutron()
    x, y_topas = np.loadtxt(DATA / "topas_export_nacl_neutron_ycalc.txt", unpack=True)
    y_rietx = np.asarray(ref.predict(x))
    ratio = np.median(y_topas / y_rietx)
    assert abs(ratio - 1.0) < 0.01
    assert NEUTRON_SCALE_FACTOR == 100.0


def test_a_signed_zero_is_written_as_zero():
    assert number(-0.0) == "0" and number(0.0) == "0"
    assert number(0.25) == "0.25"
    with pytest.raises(ValueError, match="does not parse"):
        number(float("nan"))


def test_the_name_of_a_path():
    refined = RefinedSet(None, rx.Structure(phases=[nacl()]))
    assert refined.name("phases.0.atoms.1.biso") == "Cl_biso"
    assert refined.name("phases.0.scale") == "p0_scale"
    assert refined.name("instrument.profile.u") == "prof_u"
    assert refined.name("instrument.geometry.axial_hl") == "geom_axial_hl"


def test_affine_arithmetic():
    a = Affine({"p": 1.0}, 0.5) * 2.0 + Affine({"p": -2.0, "q": 1.0}, 1.0)
    assert a.terms == {"q": 1.0} and a.const == 2.0


# ---------------------------------------------------------------- review of #770

def _stored_flags_phase():
    """The phase as an input file leaves it: the stored flags are the free set."""
    phase = _pnma()
    phase.cell.a.vary = True
    phase.atoms[0].x.vary = True
    phase.atoms[1].biso.vary = True
    phase.scale.vary = True
    return rx.Structure(phases=[phase])


@pytest.mark.parametrize("kwargs", [
    {"scale": "topas", "instrument": rx.Instrument.constant_wavelength_neutron(2.4)},
    {"scale": "rietx"},
    {"instrument": rx.Instrument.constant_wavelength_neutron(2.4)},
], ids=["topas", "rietx", "instrument"])
def test_scale_or_instrument_without_free_keeps_the_stored_flags(kwargs):
    """Review item 1: ``scale=``/``instrument=`` alone took the new path with an
    empty free set and wrote every parameter ``!``, against ``files.md``'s
    'each ``Parameter.vary`` as ``@``/``!``'."""
    text = from_structure(_stored_flags_phase(), **kwargs)
    assert re.search(r"\ba p0_cell_a 10\.0\b", text)
    assert re.search(r"\bx A1_x 0\.17\b", text)
    assert re.search(r"beq B1_biso 0\.7", text)
    assert re.search(r"scale p0_scale ", text)
    assert "b ! 6.0" in text and "y ! 0.02" in text      # held stays held
    assert "free set: each Parameter.vary as stored" in text


def test_a_result_keeps_its_tied_copies_free():
    """Review item 2: a result lists a row iff the fit could move it (it varied,
    or follows one that did, WP-1999), so a ``vary=False`` row is a tied copy,
    which the note says 'refines as its own parameter'."""
    from rietx.schemas.results import RefinedParameter

    class _Result:
        parameters = [
            RefinedParameter(path="phases.0.atoms.1.biso", value=0.7),
            RefinedParameter(path="phases.0.atoms.2.biso", value=0.7, vary=False)]

    text = from_structure(_stored_flags_phase(), free=_Result())
    assert "beq B1_biso 0.7" in _site(text, "B1")
    assert re.search(r"beq B2_biso 0\.7", _site(text, "B2"))
    assert "refines as its own parameter" in text


def test_a_result_writes_a_symmetry_tied_row_from_its_source():
    """Round-2 item 2: ``RefinementResult.parameters`` lists a cubic cell's ``b``
    and ``c`` (``vary=False``, tied), and TOPAS refines a cubic cell as three
    independent lengths if each is a free name of its own."""
    from rietx.schemas.results import RefinedParameter

    structure = rx.Structure(phases=[nacl()])
    ref = rx.Refinement(structure, rx.Instrument.constant_wavelength_neutron(2.4),
                        history=False)
    ref.set_vary(["phases.0.cell.*"], True)
    rows = [r for r in ref.parameters() if r.vary or r.tie is not None]
    assert {"phases.0.cell.b", "phases.0.cell.c"} <= {r.path for r in rows if not r.vary}

    class _Result:
        parameters = [RefinedParameter(path=r.path, value=r.value, vary=r.vary)
                      for r in rows]

    text = from_structure(ref.fitted_structure, free=_Result())
    cell = {m[1]: m[2] for m in re.finditer(r"^\s+(a|b|c) (.+)$", text, re.M)}
    assert cell["a"].startswith("p0_cell_a")
    # an equality tie is spelled as one shared name (§ 2.3)
    assert cell["b"].startswith("p0_cell_a ") and cell["c"].startswith("p0_cell_a ")
    assert "p0_cell_b" not in text and "p0_cell_c" not in text
    # the same file the Refinement itself gives
    assert text.count("p0_cell_a") == from_structure(
        ref.fitted_structure, free=ref).count("p0_cell_a")


def test_p1_expand_beside_the_refined_set_ties_the_copies():
    """Refused in 1.7.0; now every copy is written over the site it copies."""
    text = from_structure(rx.Structure(phases=[_pnma()]), p1_expand=True,
                          free=["phases.0.atoms.0.biso"])
    assert 'space_group "P 1"' in text
    # the general site's eight copies share its one name; the held sites stay held
    assert text.count(" beq A1_biso 0.7") == 8
    assert text.count(" beq ! 0.7") == 8


def test_the_refined_path_spells_the_space_group_as_the_plain_one_does():
    """The refined path wrote ``xhm()`` where main's writer spells TOPAS's own
    ``S`` suffix for origin choice 1 (`F d -3 m:1` stops TOPAS)."""
    structure = rx.Structure(phases=[_pnma()])
    structure.phases[0].space_group = "F d -3 m:1"
    plain = re.search(r'space_group "(.*)"', from_structure(structure)).group(1)
    assert plain == "Fd-3mS"
    refined = from_structure(structure, free=[])
    assert f'space_group "{plain}"' in refined


def _read_back(structure, tmp_path, **kwargs):
    from rietx.io.projects.topas import read_topas_inp, to_structure

    out = tmp_path / "refined.inp"
    out.write_text(from_structure(structure, **kwargs), encoding="utf-8")
    return to_structure(read_topas_inp(out)).phases[0]


def test_the_refined_file_is_read_back_by_this_packages_own_reader(tmp_path):
    """Review item 3: export, re-import, compare field by field. The name-as-flag
    grammar reads back as a refined value, an equation as a held one carrying the
    equation's value, and bounds on the cell travel."""
    ref = _ref()
    ref.tie_equal(["phases.0.atoms.1.biso", "phases.0.atoms.2.biso"])
    ref.tie("phases.0.atoms.0.biso", "phases.0.atoms.1.biso", scale=2.0, offset=-0.7)
    want = ref.fitted_structure.phases[0]
    got = _read_back(ref.fitted_structure, tmp_path, free=ref, scale="rietx")
    for w, g in zip(want.atoms, got.atoms):
        assert g.label == w.label
        for key in ("x", "y", "z", "biso"):
            assert getattr(g, key).value == pytest.approx(getattr(w, key).value, abs=1e-12)
    # the general site refines x, y, z; the mirror sites hold y
    assert [getattr(got.atoms[0], k).vary for k in "xyz"] == [True, True, True]
    for atom in got.atoms[1:]:
        assert [getattr(atom, k).vary for k in "xyz"] == [True, False, True]
    assert got.atoms[0].biso.vary is False                # an equation, not a parameter
    assert got.atoms[1].biso.vary and got.atoms[2].biso.vary
    for key in ("a", "b", "c"):
        assert getattr(got.cell, key).value == pytest.approx(getattr(want.cell, key).value)
    assert got.scale.value == pytest.approx(want.scale.value)


def _moment_ref(vary: bool):
    from tests.test_projects_topas import _magnetic_phase

    phase = _magnetic_phase("oblique", vary=vary)
    ref = rx.Refinement(rx.Structure(phases=[phase]),
                        rx.Instrument.constant_wavelength_neutron(2.4), history=False)
    return ref, phase


def test_a_held_moment_is_read_back(tmp_path):
    ref, phase = _moment_ref(vary=False)
    got = _read_back(ref.fitted_structure, tmp_path, free=ref).atoms[0].moment
    assert got.values() == pytest.approx(phase.atoms[0].moment.values(), rel=1e-12)
    assert not got.crystalaxis_x.vary


def test_a_free_moment_is_written_as_the_equation_the_site_symmetry_gives():
    """The moment branches (``_moment_component_items``, ``Expr``) evaluated, not
    only written: the declared ``prm`` values put into the written ``mlx``/
    ``mly``/``mlz`` equations give the moment back in TOPAS's fractional basis
    (μ_B over the edge)."""
    import math

    ref, phase = _moment_ref(vary=True)
    text = from_structure(ref.fitted_structure, free=ref)
    names = {m[1]: float(m[2]) for m in re.finditer(r"^prm (\S+) (\S+)", text, re.M)}
    assert len(names) == 3                                   # modulus and two angles
    site = _site(text, "Fe1")
    cell = phase.cell
    edges = (cell.a.value, cell.b.value, cell.c.value)
    env = {"Sin": math.sin, "Cos": math.cos, **names}
    for key, edge, want in zip(("mlx", "mly", "mlz"), edges,
                               phase.atoms[0].moment.values()):
        expr = re.search(rf"\b{key} = (.*?);", site).group(1)
        assert eval(expr, {"__builtins__": {}}, env) * edge == pytest.approx(want, rel=1e-9)


@pytest.mark.xfail(strict=True, raises=TopasInpError, reason="this package's reader does not yet read an "
                   "equation for `mlx` (#771): the round trip lands with whichever "
                   "of #770 and #771 merges second")
def test_a_free_moment_is_read_back(tmp_path):
    ref, phase = _moment_ref(vary=True)
    got = _read_back(ref.fitted_structure, tmp_path, free=ref).atoms[0].moment
    assert got.values() == pytest.approx(phase.atoms[0].moment.values(), rel=1e-9)
