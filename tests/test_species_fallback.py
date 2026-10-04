"""The neutral-atom species fallback, made to speak (issue #202).

``crystallography.scattering.normalize_species`` falls back to the bare
neutral element when an ion is absent from the Waasmaier-Kirfel table.  The
fallback is deliberate — refusing would break files that currently refine —
but it used to be silent: nothing recorded that the model's scattering power
was not the one the species label claimed, and ``f0(stol=0)`` is the electron
count, so the substitution is a physically wrong occupancy hiding behind an
Rwp the substitution barely moves (the model simply rescales).

Two layers are tested, matching the two functions the fix adds:

* :func:`~rietx.crystallography.scattering.detect_fallback` — the pure,
  per-species detector (the "sibling to ``normalize_species``" the issue
  asks for), tested table-driven, directly against ``gemmi``'s Z and each
  ion's own formal charge, so nothing here hard-codes an electron count.
* :func:`~rietx.refine._species_fallback_diagnostics` — the collector that
  walks a whole ``Structure`` and turns each substitution into a
  ``SPECIES_FALLBACK_NEUTRAL`` ``Diagnostic``, exercised the same way
  ``tests/test_dispersion.py`` exercises its sibling ``_dispersion_diagnostics``:
  called directly against ``Refinement.structure``/``.instrument``, no fit run.

**A flagged discrepancy with the issue's own numbers.**  Issue #202 asserts a
111-member reference list of "chemically-real oxidation states" of which 99
resolve correctly and 12 do not; the 12 are reproduced exactly below (their
percentages match the issue's table to the decimal place).  The 99 "correct"
side of that partition is the issue author's own private working list, which
is not recoverable from this repository, so it is *not* what
``test_every_tabulated_ion_is_silent`` below tests — that test instead uses
the ion entries the X-ray table itself carries (111 Waasmaier-Kirfel rows and
one *International Tables* row, verified by
``test_the_table_carries_112_ion_entries``), a different but independently
checkable set. Every one of those really
is "correct" by construction (the table has it verbatim), which is the
property this test needs; whether it is the *same* 99-of-111 the issue
counted is not verified and is flagged here rather than assumed.

WP-1527 took two labels off the fallback list.  ``Y3+``, one of the twelve,
has a row from ITC Vol. C Table 6.1.1.4.  A one-charge ion written without its
digit (``Na+``, ``Cl-``) reads as the tabulated ion (``Na1+``, ``Cl1-``),
where through 1.6 it read as the neutral atom.
"""

from __future__ import annotations

import re
from importlib import resources

import gemmi
import numpy as np
import pytest

from rietx._about import DATA_PACKAGE
from rietx.crystallography.scattering import (
    _ITC_IONS,
    SpeciesFallback,
    _load_table,
    detect_fallback,
    f0,
    normalize_species,
    xray_scatterer,
)
from rietx.refine import SPECIES_FALLBACK_MIN_DELTA_FRAC, _species_fallback_diagnostics
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import Geometry, NeutronSource
from rietx.schemas.structure import Atom, Cell, Phase, Structure


def _atom(label: str, species: str, x: float = 0.0) -> Atom:
    return Atom(label=label, species=species, x=Parameter(value=x),
               y=Parameter(value=0.0), z=Parameter(value=0.0),
               biso=Parameter(value=0.5))


def _structure(*species: str) -> Structure:
    """One phase, one atom per requested species -- P1, no symmetry to fuss
    over, because these tests never compile a reflection list."""
    atoms = [_atom(f"a{i}", s, x=0.1 * i) for i, s in enumerate(species)]
    return Structure(phases=[Phase(
        name="synthetic", space_group="P 1",
        cell=Cell(a=Parameter(value=5.0), b=Parameter(value=5.0),
                  c=Parameter(value=5.0), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=atoms)])


def _xray_instrument():
    import rietx as rx
    return rx.Instrument.bragg_brentano(radiation="CuKa")


def _neutron_instrument():
    import rietx as rx
    return rx.Instrument(source=NeutronSource(wavelength=1.5),
                         geometry=Geometry(kind="bragg_brentano",
                                          goniometer_radius_mm=200.0))


# ----------------------------------------------------------------------
# detect_fallback: the table-driven centrepiece
# ----------------------------------------------------------------------

#: issue #202's own reproduction: species -> (true e-, returned e-, % error),
#: transcribed from its table so the assertions below are checking *against*
#: the issue, not restating it.
KNOWN_AFFECTED = {
    "C4+": (2, "+200"), "B3+": (2, "+150"), "S6+": (10, "+60"),
    "P5+": (10, "+50"), "N3-": (10, "-30"), "As5+": (28, "+17.8"),
    "S2-": (18, "-11.1"), "As3+": (30, "+10.0"), "Y3+": (36, "+8.3"),
    "Se2-": (36, "-5.6"), "Re4+": (71, "+5.6"), "Te2-": (54, "-3.7"),
}

#: issue #202's twelve less ``Y3+``, which WP-1527 tabulated from ITC Vol. C
#: Table 6.1.1.4 (``test_y3plus_is_no_longer_a_fallback`` below)
STILL_AFFECTED = sorted(set(KNOWN_AFFECTED) - {"Y3+"})

_LABEL_RE = re.compile(r"^([A-Za-z]{1,2})(\d*)([+-])$")


def _z_and_charge(species: str) -> tuple[int, int]:
    """Z and signed formal charge, derived independently of
    ``scattering._ION_RE`` (a separate regex, so a bug shared by both would
    not hide) -- this is the "Z and the charge" the brief asks the expected
    electron counts come from, not a transcribed magic number."""
    elem, digits, sign = _LABEL_RE.match(species).groups()
    charge = int(digits or "1") * (1 if sign == "+" else -1)
    return gemmi.Element(elem.capitalize()).atomic_number, charge


@pytest.mark.parametrize("species", STILL_AFFECTED)
def test_the_known_affected_ions_are_detected(species):
    """Every species issue #202 lists as silently wrong is now caught, with
    an electron count derived from Z and the charge -- not transcribed from
    the issue's own printed percentages, which are only used to cross-check
    the result at the end."""
    z, charge = _z_and_charge(species)
    true_electrons = float(z - charge)
    fb = detect_fallback(species)
    assert fb is not None, f"{species}: expected a fallback, got none"
    assert isinstance(fb, SpeciesFallback)
    assert fb.charge == charge
    assert fb.true_electrons == pytest.approx(true_electrons)
    # returned_electrons comes off the same f0 table a real refinement reads,
    # not off Z: the WK fit reproduces the sum rule to ~1e-4, not exactly.
    assert fb.returned_electrons == pytest.approx(
        float(f0(fb.element, np.array([0.0]))[0]))

    expected_pct = float(KNOWN_AFFECTED[species][1])
    # tolerance covers the issue's own rounding (whole percent for the large
    # errors) against the WK fit's ~1e-4 departure from the exact sum rule;
    # largest observed gap is 0.14 pp (C4+)
    assert fb.delta_frac * 100 == pytest.approx(expected_pct, abs=0.2), (
        f"{species}: delta {fb.delta_frac:.4%} does not match issue #202's "
        f"reported {expected_pct}%"
    )


#: the boundary the 12 cases above never reach: every one of them has
#: charge < Z, so none exercises the branch where the ion's own electron
#: count -- the denominator of delta_frac -- is itself zero.  ``H1+`` is the
#: ICSD's own spelling (ICSD-exported CIFs write ``_atom_site_type_symbol``
#: this way throughout); ``H+`` is the same ion without the explicit "1";
#: ``He2+`` is the next element up where charge can still equal Z (found by
#: running detect_fallback, not by reading it -- PR #208 review, item 1).
CHARGE_EQUALS_Z = ["H+", "H1+", "He2+"]


@pytest.mark.parametrize("species", CHARGE_EQUALS_Z)
def test_charge_equal_to_z_does_not_raise(species):
    """A bare proton (or He2+) has true_electrons == 0.0, so delta_frac's own
    division would be by zero.  ``None`` is the contract's existing answer
    for "no single number, which is not zero" (``Diagnostic.value``,
    schemas.common) -- not a ``ZeroDivisionError`` three frames from
    ``Refinement.fit``, which calls the collector unconditionally."""
    z, charge = _z_and_charge(species)
    assert z == charge, f"{species}: fixture no longer at the charge == Z boundary"
    fb = detect_fallback(species)
    assert fb is not None, f"{species}: expected a fallback, got none"
    assert fb.true_electrons == 0.0
    assert fb.delta_frac is None  # must not raise ZeroDivisionError


def test_the_table_carries_112_ion_entries():
    """Sizes the corpus the next test checks against, so a change to the
    bundled WK table (a version bump, a re-export) is visible here rather
    than silently changing what 'every tabulated ion' means.

    111 come from the DABAX file, read here from its own ``#S`` lines, and
    one from ``_ITC_IONS``.  An ITC row never shadows a DABAX one."""
    text = (resources.files(DATA_PACKAGE) / "f0_WaasKirf.dat").read_text(
        encoding="utf-8")
    dabax = {line.split()[2] for line in text.splitlines()
             if line.startswith("#S") and len(line.split()) >= 3}
    assert len([k for k in dabax if k[-1] in "+-"]) == 111, (
        "f0_WaasKirf.dat changed; re-check whether the known-affected "
        "species are still absent from it")
    assert set(_ITC_IONS) == {"Y3+"}
    assert not set(_ITC_IONS) & dabax
    ions = [k for k in _load_table() if k[-1] in "+-"]
    assert len(ions) == 112


def test_every_tabulated_ion_is_silent():
    """The no-false-positive side: every ion the table carries verbatim
    resolves to itself, so none of them should ever look like a fallback.

    See the module docstring for why this corpus (111 ions the table itself
    carries) stands in for issue #202's own "99 correct" set rather than
    reproducing it exactly.
    """
    ions = [k for k in _load_table() if k[-1] in "+-"]
    false_positives = [s for s in ions if detect_fallback(s) is not None]
    assert false_positives == []


def test_bare_elements_and_malformed_labels_are_not_fallbacks():
    """Out of scope for this function, on purpose: a bare element has no ion
    to have lost, and a malformed label (sign-first charge, gibberish) is
    ``normalize_species``'s job to reject loudly, not this function's job to
    describe quietly."""
    assert detect_fallback("Fe") is None            # bare element
    assert detect_fallback("LA") is None             # case only, no ion
    assert detect_fallback("O2-") is None            # tabulated ion, no loss
    assert detect_fallback("NOTANELEMENT") is None   # malformed
    assert detect_fallback("Y+3") is None            # sign-first, malformed


def test_same_element_different_charge_are_judged_independently():
    """Cr3+ is tabulated, Cr6+ (chromate's oxidation state) is not -- the two
    must not be merged by element, only by the exact label, or a structure
    carrying both would either miss the real fallback or falsely flag the
    good ion."""
    assert detect_fallback("Cr3+") is None
    fb = detect_fallback("Cr6+")
    assert fb is not None and fb.element == "Cr" and fb.charge == 6


def test_a_detector_blind_to_the_resolved_form_over_fires():
    """The rejected alternative, made to fail on purpose.

    A detector that flags every *input* carrying a charge sign -- without
    checking whether resolution actually dropped it -- is the naive design
    the ``resolved != elem`` check in ``detect_fallback`` exists to avoid.
    Proven here because the parent commit emits nothing for a real fallback
    either (there is no earlier passing behaviour to regress against): the
    naive detector below over-fires on every one of the 111 ions this table
    tabulates in full, which is exactly the false-positive failure mode
    ``test_every_tabulated_ion_is_silent`` guards against and would have
    caught had ``detect_fallback`` been built this way.
    """
    ions = [k for k in _load_table() if k[-1] in "+-"]

    def naive_fires_on_any_charge(species: str) -> bool:
        return _LABEL_RE.match(species) is not None

    naive_flags = [s for s in ions if naive_fires_on_any_charge(s)]
    assert naive_flags == ions, "the naive detector should flag every ion here"

    real_flags = [s for s in ions if detect_fallback(s) is not None]
    assert real_flags == [], (
        "detect_fallback must stay silent on every tabulated ion -- the "
        "naive alternative above does not"
    )


# ----------------------------------------------------------------------
# _species_fallback_diagnostics: collection and the SPECIES_FALLBACK_NEUTRAL
# Diagnostic
# ----------------------------------------------------------------------

def test_diagnostics_fires_for_an_untabulated_ion():
    # As3+ (issue #202's +10.0 %); this was Y3+ (+8.3 %) until WP-1527
    # tabulated it
    structure = _structure("As3+")
    diags = _species_fallback_diagnostics(structure, _xray_instrument())
    assert len(diags) == 1
    d = diags[0]
    assert d.code == "SPECIES_FALLBACK_NEUTRAL"
    assert d.level == "warning"
    assert d.where == ["phases.0.atoms.0.species"]
    assert d.value == pytest.approx(0.0996, abs=1e-3)
    assert "As3+" in d.message and "As" in d.message


def test_diagnostics_silent_for_a_tabulated_ion():
    structure = _structure("O2-")
    assert _species_fallback_diagnostics(structure, _xray_instrument()) == []


@pytest.mark.parametrize("species", CHARGE_EQUALS_Z)
def test_diagnostics_reports_charge_equal_to_z_without_raising(species):
    """The collector ``Refinement.fit`` calls unconditionally must not raise
    for a structure carrying a bare-proton-like site -- that would be a
    structure going from refining today to raising, the regression PR #208's
    review found (item 1).  ``value`` is ``None`` (undefined, not zero) but
    the message still names the substitution, same as every other row."""
    structure = _structure(species)
    diags = _species_fallback_diagnostics(structure, _xray_instrument())
    assert len(diags) == 1
    d = diags[0]
    assert d.code == "SPECIES_FALLBACK_NEUTRAL"
    assert d.value is None
    assert species in d.message


def test_diagnostics_silent_for_a_neutron_source():
    """Neutron phases resolve species through crystallography.neutron, a
    different table with a different fallback story -- widening this
    diagnostic to cover it would be a second defect, not this one."""
    structure = _structure("As3+")
    assert _species_fallback_diagnostics(structure, _neutron_instrument()) == []


def test_diagnostics_groups_repeats_of_the_same_species_into_one_row():
    structure = _structure("As3+", "As3+")
    diags = _species_fallback_diagnostics(structure, _xray_instrument())
    assert len(diags) == 1
    assert sorted(diags[0].where) == [
        "phases.0.atoms.0.species", "phases.0.atoms.1.species"]


def test_diagnostics_treats_different_ions_of_one_element_separately():
    structure = _structure("Cr3+", "Cr6+")
    diags = _species_fallback_diagnostics(structure, _xray_instrument())
    assert len(diags) == 1, "Cr3+ is tabulated and must not appear at all"
    assert diags[0].where == ["phases.0.atoms.1.species"]
    assert "Cr6+" in diags[0].message


def test_lookup_failure_never_blocks_this_diagnostic():
    """A species compile will refuse outright (unknown symbol) must not be
    able to break the diagnostic pass that runs before it -- same contract
    ``_dispersion_diagnostics`` gives its own lookup failures."""
    structure = _structure("As3+", "Zz9+")   # "Zz" is not an element at all
    diags = _species_fallback_diagnostics(structure, _xray_instrument())
    assert len(diags) == 1 and diags[0].message.count("As3+") >= 1


def test_the_threshold_is_a_named_constant_yues_call_by_default_any():
    """``SPECIES_FALLBACK_MIN_DELTA_FRAC`` is 0.0 -- fires on any
    substitution -- and is a one-line change away from a minimum size, which
    is exactly what issue #202 leaves open."""
    assert SPECIES_FALLBACK_MIN_DELTA_FRAC == 0.0


def test_raising_the_threshold_is_a_one_line_change(monkeypatch):
    """Demonstrates the lever the constant provides, without changing its
    shipped default: Te2- (issue #202's smallest error, 3.7%) is dropped
    once the threshold passes it, while C4+ (200%) still fires."""
    # ``rietx.refine`` (the package attribute) is shadowed by the top-level
    # ``refine()`` convenience function ``rietx/__init__.py`` re-exports, so
    # ``import rietx.refine as m; m.CONST`` resolves to the wrong object;
    # patching the function's own ``__globals__`` reaches the real module
    # namespace ``_species_fallback_diagnostics`` actually reads from.
    structure = _structure("Te2-", "C4+")
    monkeypatch.setitem(_species_fallback_diagnostics.__globals__,
                        "SPECIES_FALLBACK_MIN_DELTA_FRAC", 0.10)
    diags = _species_fallback_diagnostics(structure, _xray_instrument())
    assert len(diags) == 1
    assert "phases.0.atoms.1.species" in diags[0].where   # C4+, not Te2-


# ----------------------------------------------- an isotope is its element ---
@pytest.mark.parametrize("species, scatterer", [
    ("D", "H"), ("T", "H"), ("2H", "H"), ("D1+", "H1+"),
    ("7Li", "Li"), ("7Li1+", "Li1+"), ("157Gd", "Gd"), ("60Ni2+", "Ni2+"),
    # element symbols that start with D or T are not isotopes
    ("Dy", "Dy"), ("Ti", "Ti"), ("Tb3+", "Tb3+"), ("Zr4+", "Zr4+"), ("H", "H"),
])
def test_an_isotope_is_its_element_to_every_xray_lookup(species, scatterer):
    """Issue #552: X-rays scatter from the electrons, so ``2H`` is ``H``.

    Every X-ray lookup has to agree, f₀ and f′/f″ alike: a structure that
    resolves in one table and not the other fails at compile, whichever pass
    reaches it first.
    """
    from rietx.crystallography.dispersion import normalize_element

    assert xray_scatterer(species) == scatterer
    assert normalize_species(species) == normalize_species(scatterer)
    assert normalize_element(species) == normalize_element(scatterer)
    stol = np.linspace(0.0, 1.5, 7)
    assert np.array_equal(f0(species, stol), f0(scatterer, stol))


@pytest.mark.parametrize("label", ["1Cu", "999Fe", "89Y"])
def test_a_mass_number_no_nuclide_carries_is_not_stripped(label):
    """The two radiations accept the same isotope labels: a mass number the
    neutron table has no row for (``89Y`` included, yttrium being listed only
    as the element) is left alone, and fails both X-ray lookups as before."""
    from rietx.crystallography.dispersion import normalize_element

    assert xray_scatterer(label) == label
    with pytest.raises(KeyError):
        normalize_species(label)
    with pytest.raises(KeyError):
        normalize_element(label)


def test_an_isotope_ion_reports_the_fallback_its_element_would():
    """``13C4+`` has no ionic row, exactly as ``C4+`` has none (#202), so the
    fallback is reported, naming the label as written and the neutral element
    substituted."""
    plain, isotope = detect_fallback("C4+"), detect_fallback("13C4+")
    assert plain is not None and isotope is not None
    assert isotope.species == "13C4+"
    assert (isotope.element, isotope.charge, isotope.true_electrons) == \
        (plain.element, plain.charge, plain.true_electrons)


# ------------------------------- a one-charge ion written without its 1 ---
#: every one-charge ion the table carries, as (digitless label, table key)
_ONE_CHARGE = sorted(
    (m.group(1) + m.group(2), key) for key in _load_table()
    if (m := re.fullmatch(r"([A-Z][a-z]?)1([+-])", key)))


def test_the_one_charge_corpus_holds_the_labels_measured():
    """The labels WP-1527 measured falling back are all in it."""
    labels = {label for label, _ in _ONE_CHARGE}
    assert {"Na+", "K+", "Li+", "Ag+", "Cu+", "Cl-", "F-"} <= labels


@pytest.mark.parametrize("label, key", _ONE_CHARGE)
def test_a_digitless_one_charge_ion_reads_as_the_tabulated_ion(label, key):
    """``Na+`` is ``Na1+``: the table writes the 1 and pymatgen does not.

    Through 1.6 ``normalize_species`` tried ``Na+`` and then ``Na``, so the
    label computed the neutral atom and ``SPECIES_FALLBACK_NEUTRAL`` called
    the ion untabulated (WP-1527)."""
    assert normalize_species(label) == key
    assert detect_fallback(label) is None
    stol = np.linspace(0.0, 2.0, 9)
    assert np.array_equal(f0(label, stol), f0(key, stol))
    element = key[:-2]
    assert not np.array_equal(f0(label, stol), f0(element, stol))


def test_the_acceptance_labels():
    assert normalize_species("Na+") == "Na1+"
    assert normalize_species("Cl-") == "Cl1-"
    assert normalize_species("Cu+") == "Cu1+"
    assert normalize_species("7Li+") == "Li1+"     # an isotope's ion too


@pytest.mark.parametrize("label", ["Fe+", "Al+"])
def test_a_digitless_ion_no_table_carries_still_falls_back(label):
    """No table has ``Fe1+``, so ``Fe+`` is still neutral Fe, and both
    functions say so."""
    element = label[:-1]
    assert normalize_species(label) == element
    fb = detect_fallback(label)
    assert fb is not None
    assert (fb.element, fb.charge) == (element, 1)


def test_the_diagnostic_stops_firing_on_a_digitless_tabulated_ion():
    structure = _structure("Na+", "Cl-", "Fe+")
    diags = _species_fallback_diagnostics(structure, _xray_instrument())
    assert [d.where for d in diags] == [["phases.0.atoms.2.species"]]
    assert "Fe+" in diags[0].message


# ------------------------------------------------- Y3+ from ITC Vol. C ---
#: Y3+ from ITC Vol. C (2004) Table 6.1.1.3, p. 570: (s, f) at seven of its
#: 56 grid points.  Independent of Table 6.1.1.4, which ``_ITC_IONS`` carries.
Y3_TABULATED = [(0.00, 36.000), (0.10, 34.425), (0.25, 28.567),
                (0.50, 20.382), (1.00, 11.340), (1.50, 7.008), (2.00, 5.443)]


def test_y3plus_is_no_longer_a_fallback():
    assert normalize_species("Y3+") == "Y3+"
    assert detect_fallback("Y3+") is None
    assert _species_fallback_diagnostics(_structure("Y3+"),
                                         _xray_instrument()) == []


def test_y3plus_carries_36_electrons():
    """Z = 39 less the charge.  The coarsest printed digit is a4's third
    decimal (−33.108), so the sum rule holds to 1e-3; neutral Y is 39."""
    assert f0("Y3+", np.array([0.0]))[0] == pytest.approx(36.0, abs=1e-3)
    assert f0("Y", np.array([0.0]))[0] == pytest.approx(39.0, abs=0.05)


def test_y3plus_reproduces_the_tabulated_scattering_factor():
    """Table 6.1.1.4 states a maximum fit error of 0.005 e over s ≤ 2 Å⁻¹.
    A dropped minus sign on a4 or b4 (the OCR'd copy drops both) misses by
    66 e at s = 0 or 3.5 e at s = 2."""
    s, tabulated = (np.array(v) for v in zip(*Y3_TABULATED))
    assert np.abs(f0("Y3+", s) - tabulated).max() <= 0.005


def test_an_itc_row_reads_through_the_same_eleven_slots():
    """Four Gaussians, stored with a5 = b5 = 0."""
    row = _load_table()["Y3+"]
    a, b, c = _ITC_IONS["Y3+"]
    assert row.shape == (11,)
    assert list(row) == [*a, 0.0, c, *b, 0.0]
