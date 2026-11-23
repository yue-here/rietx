"""Magnetic form factors past the range their source fitted them over.

Every ⟨jₙ⟩ row is a least-squares fit over a stated range of s = sinθ/λ
(Brown, ITC Vol. C § 4.4.5 (2004), p. 461; Lisher & Forsyth (1971), p. 548),
and past it the fitted form is not a form factor: Mn²⁺ ⟨j₀⟩ carries
e^(+0.609·s²) and reaches 1.01 at s = 3 Å⁻¹.  These tests pin

* each row's fitted range, read from its source;
* the rows refused past it (a growing exponential), and that every other row
  warns instead;
* that inside the range nothing changes, bit for bit, in the evaluator or in a
  magnetic fit;
* that a fit reaching past a refused row raises before any work, and one
  reaching past a warned row carries ``MAGNETIC_FORM_FACTOR_EXTRAPOLATED``
  once.
"""
from __future__ import annotations

import warnings

import numpy as np
import pytest

from rietx.crystallography.magnetic import form_factor as ff
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Moment, Phase

#: rutile-type MnF₂ / FeF₂, P4₂'/mnm' (BNS 136.499), the moment along c
RUTILE_BNS = "136.499"
MNF2_CELL = (4.8734, 4.8734, 3.3099)
FEF2_CELL = (4.6974, 4.6974, 3.3082)


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
    """A synthetic pattern of ``phase`` at λ on :func:`_grid`, plus a flat
    background.  Compiled through the range check like any fit, so a refused
    row needs a λ inside its range here."""
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


# ============================================================= the table

def test_every_row_carries_its_sources_fitted_range():
    """3d, 4d and actinide rows 1.5 Å⁻¹, rare earths 1.2, Pr³⁺ (Lisher) 1.3."""
    ranges = {ion: ff.fitted_range(ion) for ion in ff.magnetic_ions()}
    assert len(ranges) == 96
    rare_earth = {i for i in ranges if ff._element(i)[0] in ff._RARE_EARTHS}
    assert {ranges[i] for i in rare_earth - {"Pr3+"}} == {1.2}
    assert ranges["Pr3+"] == 1.3
    assert {ranges[i] for i in set(ranges) - rare_earth} == {1.5}
    assert len(rare_earth) == 22
    with pytest.raises(KeyError, match="Ce2\\+"):
        ff.fitted_range("Ce2+")


def test_the_refused_rows_are_the_three_whose_fitted_form_grows():
    """A negative exponent, read off the coefficients: Cr²⁺, Mn²⁺, Mn³⁺ ⟨j₀⟩."""
    assert ff.GROWS_PAST_RANGE == {("Cr2+", 0), ("Mn2+", 0), ("Mn3+", 0)}
    actions = {(ion, n): ff.past_range_action(ion, n)
               for ion in ff.magnetic_ions() for n in (0, 2)}
    assert {k for k, v in actions.items() if v == "refuse"} == ff.GROWS_PAST_RANGE
    assert set(actions.values()) == {"refuse", "warn"}


def test_mn2_j0_at_s_3_is_refused():
    """On main this returned 1.0105: a form factor above its own s = 0 value."""
    assert float(ff._j0_value("Mn2+", 3.0)) == pytest.approx(1.0105, abs=1e-4)
    for call in (lambda: ff.j0("Mn2+", 3.0),
                 lambda: ff.j0("Mn2+", np.array([0.5, 3.0])),
                 lambda: ff.magnetic_form_factor("Mn2+", 3.0)):
        with pytest.raises(ValueError) as err:
            call()
        text = str(err.value)
        for part in ("Mn2+", "⟨j0⟩", "s = sinθ/λ = 3 Å⁻¹", "0–1.5 Å⁻¹",
                     "growing exponential", "1.01", "d ≥ 0.333 Å"):
            assert part in text, (part, text)


def test_a_row_inside_its_range_is_unchanged_bit_for_bit():
    """Up to and at s_max, the checked evaluators return Brown's (or Lisher &
    Forsyth's) expression exactly, and raise or warn nothing."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        for ion in ff.magnetic_ions():
            s = np.linspace(0.0, ff.fitted_range(ion), 61)
            s2 = s * s
            if ion in ff._J0_LISHER:
                (a, aa, b, bb, c), (a2, aa2, b2, bb2, c2) = ff.lisher_coefficients(ion)
                want0 = a * np.exp(-aa * s2) + b * np.exp(-bb * s2) + c
                want2 = s2 * (a2 * np.exp(-aa2 * s2) + b2 * np.exp(-bb2 * s2) + c2)
            else:
                (a, aa, b, bb, c, cc, d), k2 = ff.coefficients(ion)
                want0 = (a * np.exp(-aa * s2) + b * np.exp(-bb * s2)
                         + c * np.exp(-cc * s2) + d)
                a2, aa2, b2, bb2, c2, cc2, d2 = k2
                want2 = s2 * (a2 * np.exp(-aa2 * s2) + b2 * np.exp(-bb2 * s2)
                              + c2 * np.exp(-cc2 * s2) + d2)
            assert np.array_equal(np.asarray(ff.j0(ion, s)), want0), ion
            assert np.array_equal(np.asarray(ff.j2(ion, s)), want2), ion
            assert ff.past_fitted_range(ion, s, g=1.0) == ()


def test_a_decaying_row_past_its_range_warns_and_returns_the_fitted_value():
    with pytest.warns(RuntimeWarning, match=r"Fe3\+ ⟨j0⟩.*0–1.5 Å⁻¹.*extrapolation"):
        v = ff.j0("Fe3+", 2.0)
    assert float(v) == float(ff._j0_value("Fe3+", 2.0))
    # a 4f ion past 1.2 warns on both orders it uses
    recs = ff.past_fitted_range("Ho3+", 1.4, g=1.25)
    assert [(r.order, r.action, r.s_max) for r in recs] == [(0, "warn", 1.2),
                                                            (2, "warn", 1.2)]


# ============================================================= the fit

def test_a_fit_reaching_past_a_growing_row_is_refused_before_any_work():
    """MnF₂ at λ = 0.5 Å to 2θ = 140° reaches s ≈ 1.9 Å⁻¹; Mn²⁺ ⟨j₀⟩ is refused
    at the first stage compile, naming the 2θ to stop at."""
    phase = _rutile("Mn", "Mn2+", MNF2_CELL)
    data = _pattern(phase, 2.4)     # the counts do not matter: compile refuses
    with pytest.raises(ValueError) as err:
        _fit(phase, 0.5, data)
    text = str(err.value)
    for part in ("phase 'MnF2', atom 'Mn'", "Mn2+ ⟨j0⟩", "0–1.5 Å⁻¹",
                 "growing exponential", "2θ = 97.18°", "two_theta_limits"):
        assert part in text, (part, text)


def test_a_fit_reaching_past_a_decaying_row_warns_once():
    """FeF₂ at λ = 0.55 Å reaches s ≈ 1.7 Å⁻¹; Fe²⁺ ⟨j₀⟩ decays there, so the
    fit runs and its result carries one diagnostic, however many stages."""
    phase = _rutile("Fe", "Fe2+", FEF2_CELL)
    data = _pattern(phase, 0.55)
    _ref, result = _fit(phase, 0.55, data)
    hits = [d for d in result.diagnostics
            if d.code == "MAGNETIC_FORM_FACTOR_EXTRAPOLATED"]
    assert len(hits) == 1
    (hit,) = hits
    assert hit.level == "warning"
    assert hit.where == ["phases.0.atoms.0.moment.dof0"]
    assert 1.5 < hit.value < 1.0 / 0.55
    assert "Fe2+ ⟨j0⟩" in hit.message and "fitted to 1.5" in hit.message
    assert "d ≥ 0.333 Å" in hit.suggestion
    assert hit.explanation is not None


def test_a_magnetic_fit_inside_range_is_unchanged(monkeypatch):
    """MnF₂ at λ = 2.4 Å stays below s = 0.4 Å⁻¹: no diagnostic, and the
    compiled pattern is bit-identical to one compiled with no range check."""
    import rietx as rx
    from rietx.crystallography.magnetic import scattering
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    phase = _rutile("Mn", "Mn2+", MNF2_CELL)
    data = _pattern(phase, 2.4)
    _ref, result = _fit(phase, 2.4, data)
    assert not any(d.code == "MAGNETIC_FORM_FACTOR_EXTRAPOLATED"
                   for d in result.diagnostics)

    structure = rx.Structure(phases=[phase])
    instrument = rx.Instrument.constant_wavelength_neutron(2.4)
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    checked = compile_model(structure, instrument, data, mode="rietveld")
    assert checked.phases[0].magnetic.past_range == ()
    y_checked = np.asarray(checked.evaluate(values))
    monkeypatch.setattr(scattering, "past_fitted_range", lambda *a, **k: ())
    unchecked = compile_model(structure, instrument, data, mode="rietveld")
    assert np.array_equal(np.asarray(unchecked.evaluate(values)), y_checked)
