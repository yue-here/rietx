"""Reading a TOPAS file's constraints back as rietx ties (#721 item 4, showcase M6).

The files here are written by hand in the forms ``write_topas_inp`` writes and
TOPAS echoes into its ``.out`` (Technical Reference § 2.3): a parameter name
written at several values, and an equation affine in names. Read without
``constraints=``, every copy comes back an independent number, which is the
model with its constraints dropped.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.io.projects import topas
from rietx.io.projects.topas_ties import TopasConstraints, TopasTie, affine_of, apply_ties

CELL = "  a ! 5.0\n  b ! 6.0\n  c ! 7.0\n  al ! 90\n  be ! 90\n  ga ! 90\n"


def _read(tmp_path, text, **kw):
    path = tmp_path / "t.inp"
    path.write_text(text, encoding="utf-8")
    cons = TopasConstraints()
    s = topas.to_structure(topas.read_topas_inp(path), constraints=cons, **kw)
    return s, cons


NUCLEAR = f'''str
  phase_name "t"
  space_group "P 1"
  scale s1 0.5
{CELL}  site A1 x ! 0.1 y ! 0.2 z ! 0.3 occ Ba ! 1 beq bA 0.7
  site A2 x ! 0.6 y ! 0.7 z ! 0.8 occ Ba ! 1 beq bA 0.7
  site A3 x ! 0.3 y ! 0.1 z ! 0.9 occ Ba ! 1 beq = 2*bA - 0.4;
  site A4 x ! 0.9 y ! 0.4 z ! 0.2 occ Ba ! 1 beq = 0.5*bQ + 0.1;
'''


def test_a_shared_name_is_one_parameter(tmp_path):
    s, cons = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    ties = {t.path: t for t in cons.ties}
    assert ties["phases.0.atoms.1.biso"].terms == [("phases.0.atoms.0.biso", 1.0)]
    assert cons.free["phases.0.atoms.0.biso"] is True


def test_an_affine_equation_is_a_tie_on_the_value_carrying_its_name(tmp_path):
    s, cons = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    ties = {t.path: t for t in cons.ties}
    t = ties["phases.0.atoms.2.biso"]
    assert t.terms == [("phases.0.atoms.0.biso", 2.0)] and t.const == pytest.approx(-0.4)
    assert s.phases[0].atoms[2].biso.value == pytest.approx(2 * 0.7 - 0.4)


def test_a_name_no_value_carries_is_carried_by_its_first_equation(tmp_path):
    """``bQ`` is only declared (``prm``): A4's equation carries it, nothing
    else uses it, so it is A4's own free parameter, not a tie."""
    s, cons = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    assert "phases.0.atoms.3.biso" not in {t.path for t in cons.ties}
    assert cons.free["phases.0.atoms.3.biso"] is True


def test_without_constraints_the_numbers_are_unchanged(tmp_path):
    path = tmp_path / "t.inp"
    path.write_text("prm bQ 1.2\n" + NUCLEAR, encoding="utf-8")
    plain = topas.to_structure(topas.read_topas_inp(path))
    tied, _ = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    assert plain == tied


def test_an_equation_that_is_not_affine_is_read_as_its_value_and_said(tmp_path):
    text = "prm bQ 1.2\n" + NUCLEAR.replace("= 0.5*bQ + 0.1;", "= bQ*bQ;")
    s, cons = _read(tmp_path, text)
    assert any("not affine" in m for m in cons.skipped)
    assert s.phases[0].atoms[3].biso.value == pytest.approx(1.44)


@pytest.mark.parametrize("expr, terms, const", [
    ("2*a - 0.4", {"a": 2.0}, -0.4),
    ("-a", {"a": -1.0}, 0.0),
    ("a/9.0 + b*3 + 1", {"a": 1 / 9.0, "b": 3.0}, 1.0),
    ("0.25", {}, 0.25),
])
def test_affine_of(expr, terms, const):
    t, c = affine_of(expr)
    assert t == pytest.approx(terms) and c == pytest.approx(const)


def test_a_product_of_names_is_not_affine():
    with pytest.raises(ValueError):
        affine_of("a*b")


def _magnetic(part_sites: str, extra: str = "") -> str:
    return f'''neutron_data
LP_Factor(90)
prm m1 3.0
prm p0_magnetic_lor_strain 0.2 min 0
prm !p0_magnetic_lor_size 0
{extra}str
  phase_name "m"
  space_group "P 1"
  scale s1 2.0
{CELL}  site Fe1 x ! 0.1 y ! 0.2 z ! 0.3 occ Fe+3 ! 1 beq bF 0.5
  site Fe2 x ! 0.6 y ! 0.7 z ! 0.8 occ Fe+3 ! 1 beq bF 0.5
  site O1 x ! 0.3 y ! 0.4 z ! 0.5 occ O ! 1 beq ! 0.9
str
  phase_name "m magnetic part"
  mag_space_group 1.1
  scale s1 2.0
{CELL}{part_sites}'''


PART = ("  site Fe1 x ! 0.1 y ! 0.2 z ! 0.3 occ Fe+3 ! 1 beq bF 0.5 mlx ! 0 "
        "mly = 0.16666666666666666*m1; mlz ! 0 mag_only\n"
        "  site Fe2 x ! 0.6 y ! 0.7 z ! 0.8 occ Fe+3 ! 1 beq bF 0.5 mlx ! 0 "
        "mly = -0.16666666666666666*m1; mlz ! 0 mag_only\n")


def test_the_magnetic_part_is_merged_back_into_its_phase(tmp_path):
    s, _ = _read(tmp_path, _magnetic(PART))
    assert len(s.phases) == 1
    ph = s.phases[0]
    assert ph.magnetic_symmetry is not None
    fe1, fe2, o1 = ph.atoms
    assert fe1.moment.values() == pytest.approx((0.0, 3.0, 0.0))     # mly × b
    assert fe2.moment.values() == pytest.approx((0.0, -3.0, 0.0))
    assert o1.moment is None and fe1.moment.ion == "Fe3+"
    assert ph.magnetic_lor_strain.value == 0.2 and ph.magnetic_lor_strain.vary
    assert ph.magnetic_lor_size.vary is False


def test_a_part_that_is_not_all_mag_only_stays_refused(tmp_path):
    with pytest.raises(topas.TopasInpError, match="mag_only"):
        _read(tmp_path, _magnetic(PART.replace(" mag_only\n", "\n", 1)
                                  .replace("mlz ! 0\n", "mlz ! 0 mag_only\n", 0)
                                  + "  site O1 x ! 0.3 y ! 0.4 z ! 0.5 occ O ! 1 "
                                    "beq ! 0.9 mag_only\n"))


def test_one_moment_name_is_one_moment_parameter(tmp_path):
    s, cons = _read(tmp_path, _magnetic(PART))
    moment = [t for t in cons.ties if ".moment." in t.path]
    assert {t.path for t in moment} == {f"phases.0.atoms.1.moment.dof{k}" for k in range(3)}
    assert cons.free["phases.0.atoms.0.moment.dof0"] is True
    assert cons.free["phases.0.atoms.0.moment.dof1"] is False
    ref = rx.Refinement(s, rx.Instrument.constant_wavelength_neutron(2.4), history=False)
    grid = np.arange(10.0, 100.0, 0.05)
    before = np.asarray(ref.predict(grid))
    apply_ties(ref, cons)
    assert np.abs(np.asarray(ref.predict(grid)) - before).max() < 1e-9 * before.max()
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.1.moment.dof0"].tie is not None
    assert rows["phases.0.atoms.1.biso"].tie is not None
    free = sorted(r.path for r in ref.parameters() if r.vary and r.tie is None
                  and not r.path.startswith("instrument."))
    assert free == ["phases.0.atoms.0.biso", "phases.0.atoms.0.moment.dof0",
                    "phases.0.magnetic_lor_strain", "phases.0.scale"]


def test_scale_rietx_takes_out_topas_constant(tmp_path):
    s, _ = _read(tmp_path, _magnetic(PART), scale="rietx")
    assert s.phases[0].scale.value == pytest.approx(0.02)            # ÷ 100
    xray = "LP_Factor(0)\nprm bQ 1.2\n" + NUCLEAR
    s, _ = _read(tmp_path, xray, scale="rietx")
    assert s.phases[0].scale.value == pytest.approx(1.0)             # ÷ K = 0.5
    with pytest.raises(topas.TopasInpError, match="neither"):
        _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR, scale="rietx")
    s, _ = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    assert s.phases[0].scale.value == 0.5                            # the default


def test_the_extinction_is_read_back_by_the_writers_name(tmp_path):
    s, _ = _read(tmp_path, "prm !p0_extinction 8.5\nprm bQ 1.2\n" + NUCLEAR)
    assert s.phases[0].extinction.value == 8.5 and not s.phases[0].extinction.vary


# ----------------------------------------------------------- review of #771

def _diags(tmp_path, text, **kw):
    path = tmp_path / "t.inp"
    path.write_text(text, encoding="utf-8")
    diags = []
    s = topas.to_structure(topas.read_topas_inp(path), diagnostics=diags, **kw)
    return s, {d.code: d for d in diags}


def test_a_name_stated_at_two_values_is_refused(tmp_path):
    text = NUCLEAR.replace("site A2 x ! 0.6 y ! 0.7 z ! 0.8 occ Ba ! 1 beq bA 0.7",
                           "site A2 x ! 0.6 y ! 0.7 z ! 0.8 occ Ba ! 1 beq bA 0.8")
    with pytest.raises(topas.TopasInpError, match="two values"):
        _read(tmp_path, "prm bQ 1.2\n" + text)
    _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)          # the agreeing arm still reads


def test_apply_ties_says_what_it_did_not_apply(tmp_path):
    s, cons = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    ref = rx.Refinement(s, rx.Instrument.constant_wavelength_neutron(2.4), history=False)
    ref.tie("phases.0.atoms.1.biso", {"phases.0.atoms.3.biso": 1.0})   # already tied
    cons.ties.append(TopasTie("phases.9.scale", [("phases.0.scale", 1.0)]))
    n = len(cons.skipped)
    apply_ties(ref, cons)
    said = " ".join(cons.skipped[n:])
    assert "phases.0.atoms.1.biso" in said and "already tied" in said
    assert "phases.9.scale" in said and "no such parameter" in said


def test_a_part_that_states_another_scale_cell_or_site_is_refused(tmp_path):
    base = _magnetic(PART)
    other_scale = base.replace('mag_space_group 1.1\n  scale s1 2.0', 'mag_space_group 1.1\n  scale s9 3.0')
    with pytest.raises(topas.TopasInpError, match="scale"):
        _read(tmp_path, other_scale)
    other_cell = base.replace('mag_space_group 1.1\n  scale s1 2.0\n  a ! 5.0',
                              'mag_space_group 1.1\n  scale s1 2.0\n  a ! 5.5')
    with pytest.raises(topas.TopasInpError, match="cell 'a'"):
        _read(tmp_path, other_cell)
    moved = PART.replace("x ! 0.1 y ! 0.2 z ! 0.3", "x ! 0.15 y ! 0.2 z ! 0.3")
    with pytest.raises(topas.TopasInpError, match="x of site 'Fe1'"):
        _read(tmp_path, _magnetic(moved))
    _read(tmp_path, base)                                  # the agreeing arm still merges


def test_a_part_site_with_no_nuclear_counterpart_is_refused(tmp_path):
    stray = PART + ("  site Fe9 x ! 0.4 y ! 0.4 z ! 0.4 occ Fe+3 ! 1 beq ! 0.5 "
                    "mlx ! 0 mly ! 1 mlz ! 0 mag_only\n")
    with pytest.raises(topas.TopasInpError, match="Fe9"):
        _read(tmp_path, _magnetic(stray))


def test_the_merge_is_reported(tmp_path):
    _, codes = _diags(tmp_path, _magnetic(PART))
    assert "TOPAS_MAGNETIC_PART_MERGED" in codes
    assert "equal" in codes["TOPAS_MAGNETIC_PART_MERGED"].message


def test_a_refusal_the_part_states_is_not_lifted_by_the_merge(tmp_path):
    """Only the `mag_only` that makes it a part is lifted: a `scale_occ` inside
    the part is still refused."""
    scaled = PART.replace("mlz ! 0 mag_only\n", "mlz ! 0 mag_only scale_occ 1\n", 1)
    with pytest.raises(topas.TopasInpError, match="scaled occupancy"):
        _read(tmp_path, _magnetic(scaled))
    with pytest.raises(topas.TopasInpError, match="mag_only"):
        # a part that *is* merged (every site `mag_only` and magnetic) and
        # also states the other keyword: only the `mag_only` alone is lifted
        _read(tmp_path, _magnetic(PART.replace("mag_only\n", "mag_only mag_only_for_mag_sites\n", 1)))


def test_each_reserved_phase_term_read_is_reported(tmp_path):
    _, codes = _diags(tmp_path, "prm !p0_extinction 8.5\nprm bQ 1.2\n" + NUCLEAR)
    assert "p0_extinction" in codes["TOPAS_PHASE_TERM_READ"].message
    _, codes = _diags(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    assert "TOPAS_PHASE_TERM_READ" not in codes


# ----------------------------------------------------------- round 2 of #771

def test_apply_ties_names_a_held_path_instead_of_aborting(tmp_path):
    s, cons = _read(tmp_path, "prm bQ 1.2\n" + NUCLEAR)
    ref = rx.Refinement(s, rx.Instrument.constant_wavelength_neutron(2.4), history=False)
    ref.hold("phases.0.atoms.0.biso")
    n = len(cons.skipped)
    tied = apply_ties(ref, cons)                       # raised ValueError before
    said = " ".join(cons.skipped[n:])
    assert "phases.0.atoms.0.biso" in said and "holds it" in said
    assert "phases.0.atoms.1.biso" in tied             # the ties were still declared


def test_a_moment_name_stated_at_two_values_is_refused(tmp_path):
    two = (PART.replace("mly = 0.16666666666666666*m1;", "mly mA 3")
               .replace("mly = -0.16666666666666666*m1;", "mly mA 4"))
    with pytest.raises(topas.TopasInpError, match="two values"):
        _read(tmp_path, _magnetic(two))
    same = (PART.replace("mly = 0.16666666666666666*m1;", "mly mA 3")
                .replace("mly = -0.16666666666666666*m1;", "mly mA 3"))
    _read(tmp_path, _magnetic(same))                   # the agreeing arm still reads


def test_a_small_scale_is_compared_relative_to_itself(tmp_path):
    """TOPAS scales live near 1e-6; an absolute floor of 1 called 1e-6 and
    1.5e-6 equal, for a shared name and for the merge's scale check."""
    small = NUCLEAR.replace("beq bA 0.7\n  site A2", "beq bA 1e-6\n  site A2")
    small = small.replace("occ Ba ! 1 beq bA 0.7\n  site A3", "occ Ba ! 1 beq bA 1.5e-6\n  site A3")
    with pytest.raises(topas.TopasInpError, match="two values"):
        _read(tmp_path, "prm bQ 1.2\n" + small)
    base = _magnetic(PART).replace("scale s1 2.0", "scale s1 1e-6", 1)
    with pytest.raises(topas.TopasInpError, match="scale"):
        _read(tmp_path, base.replace("mag_space_group 1.1\n  scale s1 2.0",
                                     "mag_space_group 1.1\n  scale s9 1.5e-6"))
    _read(tmp_path, base.replace("mag_space_group 1.1\n  scale s1 2.0",
                                 "mag_space_group 1.1\n  scale s1 1e-6"))


def test_a_mergeable_part_is_not_warned_about_as_refused(tmp_path):
    path = tmp_path / "t.inp"
    path.write_text(_magnetic(PART), encoding="utf-8")
    diags = []
    model = topas.read_topas_inp(path, diagnostics=diags)
    assert not model.coverage.refused
    assert "TOPAS_FEATURE_REFUSED" not in {d.code for d in diags}
    # the positive arms: any other use of the keyword is still refused, at read
    path.write_text(_magnetic(PART.replace("mag_only\n", "mag_only_for_mag_sites\n", 1)),
                    encoding="utf-8")
    assert topas.read_topas_inp(path).coverage.refused
    path.write_text(_magnetic(PART.replace(" mag_only\n", "\n", 1)), encoding="utf-8")
    assert topas.read_topas_inp(path).coverage.refused


# ---- a dependent parameter is written out to the names it depends on

#: Two Bs over one refined ``k`` through equation ``prm``s with no ``: value``
#: tail — the form TOPAS leaves where the input did not ask for one (Technical
#: Reference §2.5). Invented numbers.
CHAIN = f'''prm {{held}}k 1.7
prm bA = 0.5*k;
prm bB = 0.25*k;
str
  phase_name "t"
  space_group "P 1"
  scale ! 0.5
{CELL}  site A1 x ! 0.1 y ! 0.2 z ! 0.3 occ Ba ! 1 beq =bA;
  site A2 x ! 0.6 y ! 0.7 z ! 0.8 occ Ba ! 1 beq =bB;
'''


@pytest.mark.parametrize("held, free", [("", True), ("!", False)])
def test_a_chain_affine_in_one_name_is_a_tie_over_that_name(tmp_path, held, free):
    """``bA`` and ``bB`` are dependent parameters (§2.6): the name that is
    refined, and that both Bs move with, is ``k``. So A1's B carries ``k`` with
    ``k``'s own flag and A2's is tied to it at 0.25/0.5 — not two unrelated
    names, each one nothing refines."""
    s, cons = _read(tmp_path, CHAIN.format(held=held))
    assert s.phases[0].atoms[0].biso.value == pytest.approx(0.85)
    assert s.phases[0].atoms[1].biso.value == pytest.approx(0.425)
    assert cons.free == {"phases.0.atoms.0.biso": free}
    [tie] = cons.ties
    assert tie.path == "phases.0.atoms.1.biso"
    assert tie.terms == [("phases.0.atoms.0.biso", pytest.approx(0.5))]
    assert tie.const == pytest.approx(0.0) and tie.names == ("k",)
    assert cons.skipped == []


def test_a_chain_that_is_not_affine_is_reported_written_out(tmp_path):
    """``u = f*k`` over ``f = c*(T + 273.15) - d`` is a product of two names, so
    its value is read and the record says so, in the form that shows why."""
    text = ("prm T 300\nprm k 1.1\nprm f = 4.8e-5*(T+273.15) - 1.5e-2;\n"
            "prm u = f*k;\nprm bQ 1.2\n" + NUCLEAR.replace("beq bA 0.7\n", "beq =u;\n", 1))
    s, cons = _read(tmp_path, text)
    assert s.phases[0].atoms[0].biso.value == pytest.approx(
        (4.8e-5 * 573.15 - 1.5e-2) * 1.1)
    [msg] = [m for m in cons.skipped if m.startswith("phases.0.atoms.0.biso")]
    assert "'= u;'" in msg and "(4.8e-5*(T+273.15) - 1.5e-2)*k" in msg
    assert "not affine" in msg


def test_an_anisotropic_component_stated_as_an_equation_is_a_statement(tmp_path):
    """``u11 = 0.006*k;`` names ``k`` as surely as ``beq = 0.5*k;`` does; it was
    left off the site's record, so no tie or free flag ever reached it."""
    text = CHAIN.format(held="").replace(
        "beq =bA;", "u11 =0.006*k; u22 =0.006*k; u33 =0.006*k;")
    path = tmp_path / "t.inp"
    path.write_text(text, encoding="utf-8")
    cons = TopasConstraints()
    topas.to_structure(topas.read_topas_inp(path), constraints=cons, aniso=True)
    assert cons.free["phases.0.atoms.0.u11"] is True
    ties = {t.path: t for t in cons.ties}
    assert ties["phases.0.atoms.0.u22"].terms == [("phases.0.atoms.0.u11", 1.0)]
    # A2's B is over the same `k`, so it is tied to the carrier too.
    assert ties["phases.0.atoms.1.biso"].terms == [
        ("phases.0.atoms.0.u11", pytest.approx(0.25 / 0.006))]
