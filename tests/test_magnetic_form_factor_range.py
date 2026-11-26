"""Magnetic form factors over s = 0-6 Å⁻¹: Brown's rows, their computed tails, the computed tables.

Every Brown ⟨jₙ⟩ row is a least-squares fit over a stated range of s = sinθ/λ (Brown, ITC Vol. C § 4.4.5 (2004),
p. 461), and past it the fitted form is not a form factor: Mn²⁺ ⟨j₀⟩ carries e^(+0.609·s²) and returned 1.0105 at
s = 3 Å⁻¹ and 1.43 × 10⁷ at s = 6 (rietx #1796).  Since rietx #1691 (rulings D46, D56) each Brown row is his
analytic form inside his range, blended over 0.2 Å⁻¹ onto a computed free-ion tail, and the tail to s = 6;
seventeen ions are served from computed tables over the whole range, neutral ``Pd0`` among them (rulings on #1806 of 2026-11-23 and 2026-11-24);
and past s = 6 every row is refused.  These tests pin

* inside every Brown row's range, the evaluator is his formula bit for bit, and so is a magnetic fit there;
* the blend reproduces the curve-builder's own blend to 1e-7, and fails when the width or the start is wrong;
* the tables reproduce their source curves at the grid points and interpolate within the measured spline bound;
* the user-visible numbers of #1796, #1804 and #1691 (Mn²⁺ past range, Pu³⁺, ``Ru0`` and ``Pd0``, ``Ru4+``);
* the refusal, before any work, at every entry point: s past 6, direct and in a fit;
* one ``MAGNETIC_FORM_FACTOR_COMPUTED_TAIL`` per fit past Brown's range, none inside;
* ``approximation_name`` naming each row's footing.

The reference values are in ``tests/data/magnetic_form_factor_reference.csv``, copied from the curves the data file
was written from (``tools/magnetic_form_factors/``), so they are not this evaluator's own output.
"""
from __future__ import annotations

import csv
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest

from rietx.crystallography.magnetic import form_factor as ff
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Moment, Phase

#: rutile-type MnF₂ / FeF₂, P4₂'/mnm' (BNS 136.499), the moment along c
RUTILE_BNS = "136.499"
MNF2_CELL = (4.8734, 4.8734, 3.3099)
FEF2_CELL = (4.6974, 4.6974, 3.3082)

_REF = Path(__file__).parent / "data" / "magnetic_form_factor_reference.csv"
D32_IONS = ("Ru3+", "Ru4+", "Ru5+", "Ru6+", "Rh4+", "Tc4+", "Mo3+", "Mo4+", "Mo5+", "Nb4+")


def _reference() -> dict:
    """``{kind: {(key, order): (s array, value array)}}`` from the reference file."""
    out: dict = defaultdict(lambda: defaultdict(list))
    with open(_REF, encoding="utf-8") as fh:
        for r in csv.DictReader(line for line in fh if not line.startswith("#")):
            out[r["kind"]][(r["key"], r["order"])].append((float(r["s"]), float(r["value"])))
    return {kind: {k: tuple(np.array(c) for c in zip(*v)) for k, v in rows.items()}
            for kind, rows in out.items()}


REF = _reference()


def _cell(a, b, c) -> Cell:
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))


def _atom(label, species, xyz, *, moment=None) -> Atom:
    x, y, z = xyz
    return Atom(label=label, species=species,
                x=Parameter(value=x), y=Parameter(value=y), z=Parameter(value=z),
                occ=Parameter(value=1.0), biso=Parameter(value=0.4, unit="A^2"),
                moment=moment)


def _rutile(metal, ion, cell, moment=3.0) -> Phase:
    return Phase(
        name=f"{metal}F2", space_group="P 42/m n m", cell=_cell(*cell),
        atoms=[_atom(metal, metal, (0.0, 0.0, 0.0),
                     moment=Moment.from_values((0.0, 0.0, moment), ion, vary=True)),
               _atom("F", "F", (0.3050, 0.3050, 0.0))],
        magnetic_symmetry=RUTILE_BNS)


def _grid():
    return np.arange(10.0, 140.0, 0.05)


def _pattern(phase, lam):
    """A synthetic pattern of ``phase`` at λ on :func:`_grid`, plus a flat background."""
    import rietx as rx
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure = rx.Structure(phases=[phase])
    instrument = rx.Instrument.constant_wavelength_neutron(lam)
    tt = _grid()
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = np.asarray(model.evaluate(table.decode(table.x0())), dtype=np.float64) + 25.0
    return rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist())


def _fit(phase, lam, data):
    import rietx as rx

    ref = rx.Refinement(rx.Structure(phases=[phase]),
                        rx.Instrument.constant_wavelength_neutron(lam))
    return ref, ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*"]),
    ]))


def _brown(ion: str, order: int, s: np.ndarray) -> np.ndarray:
    """Brown's analytic form as printed, written out here, never through the module."""
    c = (ff._J0 if order == 0 else ff._J2)[ion]
    s2 = s * s
    v = c[0] * np.exp(-c[1] * s2) + c[2] * np.exp(-c[3] * s2) + c[4] * np.exp(-c[5] * s2) + c[6]
    return s2 * v if order else v


# ============================================================= the rows and their ranges

def test_the_table_serves_brown_rows_and_seventeen_computed_tables():
    """89 Brown rows with a tail each, 17 tables (the ten D32 ions, neutral Mo/Tc/Ru/Rh/Pd, Pr³⁺, Pu³⁺), the data
    file's blocks exactly those, and every D32 ion listed (#1689's ``Ru4+`` KeyError gone)."""
    curves = ff.computed_curves()
    assert len(ff._J0) == 89 and len(ff._TABLE_KEY) == 17
    assert {k for k, c in curves.items() if c.kind == "tail"} == set(ff._J0)
    assert {k for k, c in curves.items() if c.kind == "table"} == set(ff._TABLE_KEY.values())
    assert set(ff.magnetic_ions()) == {ff._public(k) for k in set(ff._J0) | set(ff._TABLE_KEY)}
    assert set(D32_IONS) <= set(ff.magnetic_ions())
    assert float(ff.magnetic_form_factor("Ru4+", 0.2)) == pytest.approx(
        float(np.interp(0.2, *REF["grid"][("Ru4+", "j0")])), abs=1e-7)
    for c in curves.values():
        assert c.stol[-1] == ff.TABLE_S_MAX
        if c.kind == "table":
            assert c.stol[0] == 0.0 and abs(c.values["j0"][0] - 1.0) < 1e-7 and set(c.values) == {"j0", "j2", "j4"}
        else:
            assert c.stol[0] == ff.fitted_range(ff._public(c.key)) and set(c.values) == {"j0", "j2"}


def test_every_brown_row_carries_browns_fitted_range_and_a_table_has_none():
    ranges = {ion: ff.fitted_range(ff._public(ion)) for ion in ff._J0}
    rare_earth = {i for i in ranges if ff._element(i)[0] in ff._RARE_EARTHS}
    assert {ranges[i] for i in rare_earth} == {1.2} and len(rare_earth) == 21
    assert {ranges[i] for i in set(ranges) - rare_earth} == {1.5}
    assert {ff.fitted_range(ff._public(i)) for i in ff._TABLE_KEY} == {None}
    with pytest.raises(KeyError, match="Ce2\\+"):
        ff.fitted_range("Ce2+")


def test_inside_its_range_a_brown_row_is_his_formula_bit_for_bit():
    """Up to and at s_end the evaluators return Brown's expression exactly, warn nothing, and the forward model's
    unchecked evaluators agree; the blend never engages."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for ion in ff._J0:
            label = ff._public(ion)
            s = np.linspace(0.0, ff.fitted_range(label), 61)
            for order, f, f_hot in ((0, ff.j0, ff._j0_value), (2, ff.j2, ff._j2_value)):
                want = _brown(ion, order, s)
                assert np.array_equal(np.asarray(f(label, s)), want), (ion, order)
                assert np.array_equal(np.asarray(f_hot(label, s)), want), (ion, order)
            assert ff.past_fitted_range(label, s, g=1.0) == ()


# ============================================================= the blend and the tables against their sources

def _blend_error(width: float | None = None, shift: float = 0.0) -> float:
    """Largest |evaluator − the curve-builder's blend| over the reference points, with the blend width or every
    row's s_end optionally wrong: the positive arm of the test below."""
    saved = (ff.TAIL_BLEND_WIDTH, dict(ff._FITTED_RANGE))
    try:
        if width is not None:
            ff.TAIL_BLEND_WIDTH = width
        if shift:
            ff._FITTED_RANGE.update({k: v + shift for k, v in ff._FITTED_RANGE.items()})
        worst = 0.0
        for (ion, order), (s, v) in REF["blend"].items():
            got = np.asarray(ff._value(ff._public(ion), int(order[1]), s))
            worst = max(worst, float(np.max(np.abs(got - v))))
        return worst
    finally:
        ff.TAIL_BLEND_WIDTH, fitted = saved
        ff._FITTED_RANGE.clear()
        ff._FITTED_RANGE.update(fitted)


def test_the_blend_reproduces_the_curve_builders_blend_and_a_wrong_one_does_not():
    """Every Brown row, ⟨j₀⟩ and ⟨j₂⟩, at s_end + 0 … 0.3, 1.0, 3.0 and 6: within 1e-7 (the data file's %.7f
    rounding is 5e-8).  The arm: a blend 0.15 wide, or starting 0.05 late, misses by far more."""
    assert len(REF["blend"]) == 2 * 89
    assert _blend_error() <= 1e-7
    assert _blend_error(width=0.15) > 1e-5
    assert _blend_error(shift=0.05) > 1e-5


def test_each_table_reproduces_its_source_and_interpolates_within_the_spline_bound():
    """At the grid points the spline returns the source value to the file's rounding (5e-8); between them, against
    the D32 ions' own 0.005 Å⁻¹ curves, it stays inside the measured cubic-spline bound, 1.5e-6 on 0-1.5 Å⁻¹, plus
    that rounding."""
    seen = set()
    for (ion, order), (s, v) in REF["grid"].items():
        public = ff._public({v: k for k, v in ff._TABLE_KEY.items()}[ion])
        got = np.asarray(ff._value(public, int(order[1]), s)) if order != "j4" else \
            ff._spline(ion, "j4")(s)
        assert np.max(np.abs(got - v)) <= 5.1e-8, (ion, order)
        seen.add(ion)
    assert seen == set(ff._TABLE_KEY.values())
    for (ion, order), (s, v) in REF["mid"].items():
        assert s.min() > 0.0 and s.max() < 1.5
        err = np.max(np.abs(np.asarray(ff._value(ff._public(ion), int(order[1]), s)) - v))
        assert err <= 1.5e-6 + 1e-7, (ion, order, err)


# ============================================================= the numbers a user sees

def test_mn2_j0_past_its_range_is_its_computed_tail():
    """#1796: on main Mn²⁺ ⟨j₀⟩ was 1.0105 at s = 3 and 1.43 × 10⁷ at s = 6; now it is the computed tail there."""
    tail = ff.computed_curves()["Mn2+"]
    for s in (3.0, 6.0):
        want = float(tail.values["j0"][np.searchsorted(tail.stol, s)])
        assert float(ff.j0("Mn2+", s)) == pytest.approx(want, abs=1e-12)
        assert abs(want) < 1e-3
    assert float(_brown("Mn2+", 0, np.array(3.0))) == pytest.approx(1.0105, abs=1e-4)


def test_pu3_and_pr3_are_their_dirac_fock_tables_and_the_bare_symbols_follow():
    """#1804: Pu³⁺ ⟨j₀⟩(0.2) is the Dirac-Fock 0.574, not Brown's Pu⁵⁺-curve 0.627.  Pr³⁺ likewise, from its DF
    table, not Lisher & Forsyth's fit, and bare ``Pr`` reads as it (#1806 ruling: Pr³⁺ is the ICSD census's Pr ion; bare
    ``Pu`` reads as Pu⁴⁺, the census's)."""
    assert ff.read_bare_label("Pu").ion == "Pu4+"
    for ion, bare in (("Pu3+", None), ("Pr3+", "Pr")):
        s, v = REF["grid"][(ion, "j0")]
        want = float(v[np.isclose(s, 0.2)][0])
        assert float(ff.j0(ion, 0.2)) == pytest.approx(want, abs=5.1e-8)
        assert bare is None or ff.read_bare_label(bare).ion == ion
        assert ion in ff._TABLE_KEY and ion not in ff._J0
    assert float(ff.j0("Pu3+", 0.2)) == pytest.approx(0.574, abs=5e-4)
    assert abs(float(ff.j0("Pu3+", 0.2)) - 0.6267) > 0.05


def test_neutral_ru_is_the_neutral_atom_not_the_ru1_curve():
    """#1691: ``Ru0`` ⟨j₀⟩(0.2) is the neutral 4d⁷5s ⁵F table's 0.4163, not Brown's old bare M⁺ row's 0.4907; and it
    differs from ``Ru1+`` (0.4268) too, so the bare row was dropped, not relabelled.  A bare ``Ru`` is Ru⁴⁺ (#1806 ruling)."""
    s, v = REF["grid"][("Ru0", "j0")]
    want = float(v[np.isclose(s, 0.2)][0])
    assert float(ff.j0("Ru0", 0.2)) == pytest.approx(want, abs=5.1e-8)
    assert float(ff.j0("Ru0", 0.2)) == pytest.approx(0.4163, abs=1e-4)
    assert abs(float(ff.j0("Ru1+", 0.2)) - 0.4268) < 1e-4
    assert float(ff.j0("Ru", 0.2)) == float(ff.j0("Ru4+", 0.2))
    for bare in ("Mo", "Tc", "Ru", "Rh", "Pd"):
        assert bare in ff._TABLE_KEY and bare not in ff._J0
        assert not ff.needs_explicit_g(bare + "0")


def test_neutral_pd_is_the_named_neutral_curve_at_every_direct_entry_point():
    """The 2026-11-23 ruling (#1806, comment of 22:17Z): a closed 4d¹⁰ shell still has ⟨jₙ⟩ curves, so neutral Pd is served like Nb and Sc, as the
    computed neutral atom in a named configuration, 4d⁹5s ³D, the lowest one with an open shell to carry a moment.
    Since the #1806 ruling (2026-11-24) it is stated ``"Pd0"``; a bare ``"Pd"`` reads as the census's Pd²⁺, which has no row, and is refused."""
    s, v = REF["grid"][("Pd0", "j0")]
    want = float(v[np.isclose(s, 0.2)][0])
    got = float(ff.j0("Pd0", 0.2))
    assert got == pytest.approx(want, abs=5.1e-8) and got == pytest.approx(0.4965, abs=1e-4)
    assert abs(got - 0.4646) > 0.02  # the 4d10 1S ground-state curve, computed the same way
    assert abs(got - 0.5528) > 0.02  # Brown's old bare row, a Pd+ 4d7 5s2 curve
    assert abs(got - float(ff.j0("Pd1+", 0.2))) > 5e-3
    assert float(ff.magnetic_form_factor("Pd0", 0.2)) == got
    assert float(ff.j2("Pd0", 0.2)) == pytest.approx(float(REF["grid"][("Pd0", "j2")][1][np.isclose(s, 0.2)][0]),
                                                     abs=5.1e-8)
    assert ff.has_ion("Pd0") and "Pd0" in ff.magnetic_ions() and ff._TABLE_KEY["Pd"] == "Pd0"
    assert not ff.has_ion("Pd") and "Pd" not in ff.magnetic_ions()
    assert ff.fitted_range("Pd0") is None and ff.past_fitted_range("Pd0", 2.0) == ()
    with pytest.raises(KeyError, match="computed table"):
        ff.coefficients("Pd0")
    name = ff.approximation_name("Pd0", None)
    assert name.startswith(ff.J0_ONLY + "; computed table (Cowan RCN Mod 36.2.5, Hartree-Fock, Hund's-rule LS term")
    assert "Pd 4d9 5s 3D (neutral, excited configuration; ground 4d10 1S)" in name
    assert ff.COMPUTED_LABEL in name and ff.footing_name("Pd0") in name
    with pytest.raises(ValueError, match=r"Pd2\+ .*no magnetic form factor.*'Pd0'"):
        ff.j0("Pd", 0.2)


def test_neutral_pd_builds_a_phase_reads_from_a_magcif_and_is_picked_by_the_solver(tmp_path):
    """Where a fit, a reader and the solver take an ion, ``Pd0`` resolves to the neutral table: the phase builds,
    the magCIF override takes, and the solver's site pick keys it ``Pd0``.  A bare ``Pd`` named as a magnetic site
    is refused with the ions to state (#1806 ruling)."""
    from rietx.crystallography.cif import structure_from_cif
    from rietx.strategy.magnetic import _magnetic_sites
    from tests.test_magcif import _fixture

    assert _rutile("Pd", "Pd0", MNF2_CELL).atoms[0].moment.ion == "Pd0"
    read = structure_from_cif(str(_fixture(tmp_path, "LaMnO3")), moment_ions={"Mn1": "Pd0"})
    assert [a.moment.ion for a in read.phases[0].atoms if a.moment is not None] == ["Pd0"]
    phase = _rutile("Mn", "Mn2+", MNF2_CELL).model_copy(update={"atoms": [
        _atom("Pd1", "Pd", (0.0, 0.0, 0.0)), _atom("F", "F", (0.3050, 0.3050, 0.0))],
        "magnetic_symmetry": None})
    assert _magnetic_sites(phase, None, ["Pd"], "Pd0")[0] == [(0, "Pd1", "Pd0")]
    with pytest.raises(ValueError, match="named as a magnetic site.*Pd2\\+"):
        _magnetic_sites(phase, None, ["Pd"], None)


# ============================================================= refusals, before any work

@pytest.fixture
def no_work(monkeypatch):
    """Make any evaluation or data read raise, so a refusal is proved to come first."""
    def boom(*a, **k):
        raise AssertionError("work ran before the refusal")
    monkeypatch.setattr(ff, "_value", boom)
    monkeypatch.setattr(ff, "_jn", boom)
    monkeypatch.setattr(ff, "_spline", boom)
    monkeypatch.setattr(ff, "computed_curves", boom)


def test_past_s_6_every_row_is_refused_before_any_work(no_work):
    """Rule 4's second misuse: a form factor asked for past the table's end.  A Brown row, a table and a call
    through the dipole combination each raise, naming the ion, the s and d ≥ 1/12 Å."""
    for call in (lambda: ff.j0("Fe3+", 6.5), lambda: ff.j2("Ru4+", np.array([0.1, 6.01])),
                 lambda: ff.magnetic_form_factor("Ho3+", 7.0, g=1.25)):
        with pytest.raises(ValueError) as err:
            call()
        text = str(err.value)
        for part in ("past s = 6 Å⁻¹", "s ≤ 6 Å⁻¹", "d ≥ 0.08333 Å"):
            assert part in text, (part, text)


def test_a_fit_reaching_past_s_6_is_refused_at_compile():
    """MnF₂ at λ = 0.15 Å to 2θ = 140° reaches s ≈ 6.3 Å⁻¹; the first stage compile raises, naming the 2θ at
    which the table ends (2 asin(0.15 × 6) = 128.32°) and the argument that ends the data there."""
    phase = _rutile("Mn", "Mn2+", MNF2_CELL)
    data = _pattern(phase, 2.4)
    with pytest.raises(ValueError) as err:
        _fit(phase, 0.15, data)
    text = str(err.value)
    for part in ("phase 'MnF2', atom 'Mn'", "Mn2+", "past s = 6 Å⁻¹", "2θ = 128.32°", "two_theta_limits"):
        assert part in text, (part, text)



def test_the_refusals_quoted_2theta_compiles():
    """#1806 review, item 1: the fix the refusal quotes is itself accepted.  FeF₂ Fe²⁺ at λ = 0.15 Å over
    10-140° is refused; compiled again with the fitted data ended at the quoted 2θ, it compiles, and its list's top
    s is at most 6 Å⁻¹.  The control is the quote before the fix, the table's end less the 0.5° margin
    (127.82°): it left out the generator's d slack, and the same compile is refused at s ≈ 6.01 Å⁻¹."""
    import re

    import rietx as rx
    from rietx.crystallography.lattice import d_spacings
    from rietx.model.forward import compile_model

    structure = rx.Structure(phases=[_rutile("Fe", "Fe2+", FEF2_CELL)])
    instrument = rx.Instrument.constant_wavelength_neutron(0.15)
    tt = np.arange(10.0, 140.0, 0.01)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())
    with pytest.raises(ValueError, match="past s = 6") as err:
        compile_model(structure, instrument, blank, mode="rietveld")
    (quoted,) = re.findall(r"End the fitted data at 2θ ≤ ([0-9.]+)°", str(err.value))
    end = float(quoted)
    model = compile_model(structure, instrument, blank, mode="rietveld", two_theta_limits=(10.0, end))
    cell = structure.phases[0].cell.lengths_angles()
    top_s = 0.5 / float(np.min(d_spacings(model.phases[0].reflections.index, *cell)))
    assert 5.99 < top_s <= 6.0, top_s

    with pytest.raises(ValueError, match="past s = 6"):
        compile_model(structure, instrument, blank, mode="rietveld", two_theta_limits=(10.0, 127.82))
    assert end < 127.82

# ============================================================= the diagnostic

def test_a_fit_past_browns_range_carries_one_diagnostic():
    """FeF₂ at λ = 0.55 Å reaches s ≈ 1.7 Å⁻¹, onto Fe²⁺ ⟨j₀⟩'s blend: the fit runs and carries one
    ``MAGNETIC_FORM_FACTOR_COMPUTED_TAIL``, however many stages, as ``info`` (the #1806 ruling: past Brown's range f² is
    under 1 % of its low-angle value, so nothing is owed and the advice to cut the data is gone)."""
    phase = _rutile("Fe", "Fe2+", FEF2_CELL)
    data = _pattern(phase, 0.55)
    _ref, result = _fit(phase, 0.55, data)
    hits = [d for d in result.diagnostics if d.code == "MAGNETIC_FORM_FACTOR_COMPUTED_TAIL"]
    assert len(hits) == 1
    (hit,) = hits
    assert hit.level == "info"
    assert hit.where == ["phases.0.atoms.0.moment.dof0"]
    assert 1.5 < hit.value < 1.0 / 0.55
    assert "Fe2+ ⟨j0⟩" in hit.message and "Brown's fit ends at 1.5" in hit.message
    assert "not peer-reviewed" in hit.message
    assert "Nothing to do" in hit.suggestion and "d ≥" not in hit.suggestion
    assert hit.explanation is not None


def test_a_table_ion_past_browns_ranges_carries_no_diagnostic():
    """A computed table is computed on its whole range: Ru⁴⁺ at λ = 0.55 Å reaches s ≈ 1.7 with no diagnostic."""
    import rietx as rx
    from rietx.model.forward import compile_model
    from rietx.refine import _form_factor_range_diagnostics

    phase = _rutile("Ru", "Ru4+", FEF2_CELL)
    tt = _grid()
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())
    model = compile_model(rx.Structure(phases=[phase]), rx.Instrument.constant_wavelength_neutron(0.55), blank,
                          mode="rietveld")
    assert model.phases[0].magnetic.past_range == ()
    assert _form_factor_range_diagnostics(model) == []


def test_a_magnetic_fit_inside_range_is_browns_alone_bit_for_bit(monkeypatch):
    """MnF₂ at λ = 2.4 Å stays below s = 0.4 Å⁻¹: no diagnostic, and the compiled pattern is bit-identical to one
    whose form factor is Brown's bare formula with no tail anywhere, i.e. main's evaluation."""
    import rietx as rx
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    phase = _rutile("Mn", "Mn2+", MNF2_CELL)
    data = _pattern(phase, 2.4)
    _ref, result = _fit(phase, 2.4, data)
    assert not any(d.code == "MAGNETIC_FORM_FACTOR_COMPUTED_TAIL" for d in result.diagnostics)

    structure = rx.Structure(phases=[phase])
    instrument = rx.Instrument.constant_wavelength_neutron(2.4)
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    model = compile_model(structure, instrument, data, mode="rietveld")
    assert model.phases[0].magnetic.past_range == ()
    y = np.asarray(model.evaluate(values))
    monkeypatch.setattr(ff, "_value", lambda ion, order, s: ff._jn(
        (ff._J0 if order == 0 else ff._J2)[ion], np.asarray(s) * np.asarray(s), stol2_factor=order > 0))
    assert np.array_equal(np.asarray(compile_model(structure, instrument, data, mode="rietveld").evaluate(values)),
                          y)


# ============================================================= approximation_name

def test_approximation_name_names_every_rows_footing():
    """Yue, #1691 (2026-11-21): every result that uses a computed row names its footing; D56 call 3: a bare row
    that is not the neutral ground state says what it is, and Cr/Ni say their footing is not identified."""
    name = ff.approximation_name
    assert name("Mn2+", None).startswith(ff.J0_ONLY + "; Brown ITC Vol. C § 4.4.5 to s = 1.5 Å⁻¹, computed tail")
    assert "Hartree-Fock" in name("Mn2+", None) and ff.COMPUTED_LABEL in name("Mn2+", None)
    assert "s = 1.2 Å⁻¹" in name("Ho3+", 1.25) and "GRASP2018, Dirac-Fock" in name("Ho3+", 1.25)
    assert "g = 1.25" in name("Ho3+", 1.25)
    assert name("Ru4+", None).startswith(
        ff.J0_ONLY + "; computed table (Cowan RCN Mod 36.2.5, Hartree-Fock-relativistic, configuration average")
    assert "4d7 5s 5F (neutral ground configuration)" in name("Ru0", None)
    assert "bare 'Ru' read as Ru4+, the most common Ru oxidation state in the ICSD" in name("Ru", None)
    for ion in ("Pu3+", "Pr3+"):
        assert "computed table (GRASP2018, Dirac-Fock" in name(ion, 0.8) and "Brown" not in name(ion, 0.8)
    assert "row: neutral Sc in an excited configuration, 3d2 4s 4F" in name("Sc0", None)
    assert "row: neutral Nb in an excited configuration, 4d3 5s2 4F" in name("Nb0", None)
    assert "Pd 4d9 5s 3D (neutral, excited configuration; ground 4d10 1S)" in name("Pd0", None)
    assert "non-Hund term 1G" in name("Ti0", None)
    for ion in ("Cr0", "Ni0"):
        assert "row: footing not identified" in name(ion, None)
    for ion in ("V0", "Mn0", "Fe0", "Co0", "Cu0", "Y0"):
        assert "configuration average" in name(ion, None).split("row: ")[1]
    for ion in ff.magnetic_ions():
        assert ff.COMPUTED_LABEL in name(ion, 1.0)
