"""A magnetic structure: state it, refine it, report what the powder cannot see.

WP-1327.  Everything here is synthetic — no vendored pattern, no vendored
magnetic structure file.  Published moments appear as *numbers*, each cited to
the original paper in the row that uses it, exactly as ``tests/
test_magnetic_operators.py`` does; MAGNDATA is named as the record a
transcription was checked against and never as the source of a number.

The tests worth having are the ones a *plausible wrong* implementation fails,
so each block below turns on something specific:

* the axial action is ε·det(R)·R and the guard is a **span** test, never a
  dimension count — and the span controls run on a **hexagonal** structure,
  because M-5 measured that R and Rᵀ give a different allowed subspace only
  inside space groups 149-194 (YMnO₃ is in the blind region's *complement*:
  it is one of the three published fixtures that can see the trap at all);
* ⟨j₂⟩ carries an **s²** factor, so f(0) = 1 whatever g is;
* the form factor is evaluated at **s = sinθ/λ = 1/2d**, the argument the
  nuclear structure factor already computes;
* |m| on oblique axes uses the **cosine metric** — (1, 1, 0) on hexagonal
  axes is 1 μ_B, not √2;
* p = 2.695 fm per μ_B against a Sears b in fm, so one scale multiplies both;
* the powder average is over the **Laue orbit**, not one representative times
  a multiplicity — which is what makes a cubic collinear structure's intensity
  direction-independent and its direction DOFs unmeasured;
* a moment reaches ``neutron_cw`` histograms and **nothing else**.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from rietx.crystallography.magnetic.form_factor import (
    J0_ONLY,
    approximation_name,
    assumed_ion_for_element,
    assumed_lande_g,
    coefficients,
    has_ion,
    has_j2,
    j0,
    j2,
    lande_g,
    magnetic_form_factor,
    magnetic_ions,
    needs_explicit_g,
    resolve_assumed_ion,
    resolve_g,
)
from rietx.crystallography.magnetic.operators import (
    MagneticGroup,
    in_span,
    magnetic_group,
    moment_magnitude,
)
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    MOMENT_MODEL_FIELDS,
    Atom,
    Cell,
    MagneticSymmetry,
    Moment,
    Phase,
)

# --------------------------------------------------------------------- helpers

def cell(a, b, c, alpha=90.0, beta=90.0, gamma=90.0) -> Cell:
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=alpha), beta=Parameter(value=beta),
                gamma=Parameter(value=gamma))


def atom(label, species, xyz, *, moment=None, biso=0.5, occ=1.0) -> Atom:
    x, y, z = xyz
    return Atom(label=label, species=species,
                x=Parameter(value=x), y=Parameter(value=y), z=Parameter(value=z),
                occ=Parameter(value=occ), biso=Parameter(value=biso, unit="A^2"),
                moment=moment)


#: YMnO₃, hexagonal P 6₃ c m, BNS 185.197 (type I).  Mn on (0.32080, 0, 0);
#: published moment (1.68, 3.36, 0) μ_B in crystal-axis components — Brown &
#: Chatterji (2006), *Phys. Rev. B* **74**, 184433, transcribed from the
#: MAGNDATA record for entry #0.6 and checked against it.  **This is the
#: structure the span controls need**: M-5 measured that a transposed,
#: determinant-dropped or ε-dropped axial action changes the allowed subspace
#: only inside space groups 149-194, and YMnO₃'s Mn span is [1 2 0] under the
#: right action and [0 1 0] under Rᵀ — the same dimension either way.
YMNO3_BNS = "185.197"
YMNO3_SITE = (0.32080, 0.0, 0.0)
YMNO3_MOMENT = (1.68, 3.36, 0.0)
YMNO3_CELL = (6.1387, 6.1387, 11.4071, 90.0, 90.0, 120.0)

#: ScMnO₃, P 6₃ c m, BNS 185.201 (type III); Mn on (0.33160, 0, 0), published
#: moment (−3.03, 0, 0) μ_B — Muñoz *et al.* (2000), *Chem. Mater.* **12**,
#: 1497, via MAGNDATA #0.7.  A second hexagonal row, with the moment along a
#: different allowed direction, so the span control is not one structure's luck.
SCMNO3_BNS = "185.201"
SCMNO3_SITE = (0.33160, 0.0, 0.0)
SCMNO3_MOMENT = (-3.03, 0.0, 0.0)


# ===================================================== the form-factor table

def test_j0_is_one_at_the_origin_for_every_ion():
    """⟨j₀⟩(0) = A + B + C + D = 1, which is the table's own normalisation.

    Brown's coefficients are a least-squares fit rather than an exactly
    normalised one, so the sum is 1 to about ±0.003 and not to roundoff — the
    tolerance below is the *fit's*, measured over all 96 rows (worst: Cr¹⁺ at
    0.0023).  It is still the check that catches a mistranscribed leading
    digit, which is the failure mode a transcription actually has.
    """
    worst = max((abs(float(j0(ion, 0.0)) - 1.0), ion) for ion in magnetic_ions())
    assert worst[0] < 3e-3, worst
    assert len(magnetic_ions()) == 96


def test_j2_carries_its_s_squared_factor():
    """⟨j₂⟩(0) = 0 exactly, so f(0) = ⟨j₀⟩(0) whatever g is.

    Forgetting the s² factor is the classic error in this expression and it is
    invisible in a fit: it multiplies the rare-earth form factor by roughly
    1/s² near the origin, which the scale absorbs, and leaves the *shape*
    wrong.  Two statements pin it — the value at the origin, and the leading
    behaviour ⟨j₂⟩ ∝ s² as s → 0.
    """
    assert float(j2("Ho3+", 0.0)) == 0.0
    small = np.array([1e-3, 2e-3])
    v = np.asarray(j2("Ho3+", small), dtype=np.float64)
    # doubling s quadruples <j2> to better than a part in 10^4 at this s
    assert abs(v[1] / v[0] - 4.0) < 1e-4

    f0 = float(magnetic_form_factor("Ho3+", 0.0, g=1.25))
    assert abs(f0 - float(j0("Ho3+", 0.0))) < 1e-15


def test_the_dipole_coefficient_is_two_over_g_minus_one():
    """f = ⟨j₀⟩ + (2/g − 1)⟨j₂⟩, not (1 − 2/g)⟨j₂⟩.

    The two differ in sign, both vanish at g = 2, and only one is right:
    L + 2S = gJ and L = (2 − g)J for a J multiplet, so the normalised dipole
    amplitude is ⟨j₀⟩ + ((2 − g)/g)⟨j₂⟩.  ``periodictable``'s module docstring
    writes the other one — which is why only its ⟨jₙ⟩ coefficients are
    transcribed and the combination is computed here.  Ho³⁺ has g = 5/4, so
    the coefficient is +0.6 and the ⟨j₂⟩ term *adds*.
    """
    s = 0.4
    g = 1.25
    expected = float(j0("Ho3+", s)) + (2.0 / g - 1.0) * float(j2("Ho3+", s))
    assert float(magnetic_form_factor("Ho3+", s, g=g)) == pytest.approx(expected, rel=1e-15)
    assert (2.0 / g - 1.0) == pytest.approx(0.6)
    # and the wrong sign would be a visibly different number, not a rounding
    wrong = float(j0("Ho3+", s)) + (1.0 - 2.0 / g) * float(j2("Ho3+", s))
    assert abs(expected - wrong) > 0.05


@pytest.mark.parametrize("ion, published", [
    # Fe³⁺ ⟨j₀⟩, all seven coefficients, as printed in the YFeO₃ inelastic
    # neutron study (arXiv:1309.3683), which cites Dianoux & Lander,
    # *Neutron Data Booklet* (OCP Science, 2003) for them.
    ("Fe3+", (0.3972, 13.2442, 0.6295, 4.9034, -0.0314, 0.3496, 0.0044)),
    # Mn²⁺ ⟨j₀⟩, all seven, as printed in the 2025 MnF₂ polarised-neutron
    # study of altermagnetism.
    ("Mn2+", (0.4220, 17.684, 0.5948, 6.005, 0.0043, -0.609, -0.0219)),
])
def test_j0_coefficients_match_a_published_row(ion, published):
    """The transcription, checked against a paper rather than against its source.

    The risk a transcription carries is a digit, and the only test for a digit
    is a second printing of the same number.  These two rows are the ones I
    could find printed in full in a citable paper; the ⟨j₂⟩ table has no such
    check here (see the report), which is why ⟨j₂⟩ is pinned by its structural
    properties above instead.
    """
    got, _ = coefficients(ion)
    assert got == pytest.approx(published, abs=0.0, rel=0.0)


@pytest.mark.parametrize("ion, j0_published, j2_published", [
    # 2026-09-18 audit (issue-magnetic-form-factor-gaps): five rows checked
    # coefficient by coefficient against two independent transcriptions of
    # Brown's ITC Vol. C table -- P. J. Brown's own data file (signed "Jane
    # Brown"), mirrored at http://www2.cpfs.mpg.de/~rotter/homepage_mcphase/
    # manual/node137.html (accessed 2026-09-18), and GSAS-II's
    # GSASII/atmdata.py MagFF table (accessed 2026-09-18 from
    # AdvancedPhotonSource/GSAS-II on GitHub), whose own docstring names
    # "Intl. Tables for Cryst, Vol. C" for these coefficients. ill.eu's
    # "ffacts" pages -- the brief's named primary route -- return HTTP 404
    # as of this date; both mirrors agree with this module's existing rows
    # to the precision each carries, so no disagreement was found.
    ("Fe3+", (0.3972, 13.2442, 0.6295, 4.9034, -0.0314, 0.3496, 0.0044),
             (1.3602, 11.998, 1.5188, 5.003, 0.4705, 1.991, 0.0038)),
    ("Mn2+", (0.4220, 17.684, 0.5948, 6.005, 0.0043, -0.609, -0.0219),
             (2.0515, 15.556, 1.8841, 6.063, 0.4787, 2.232, 0.0027)),
    ("Nd3+", (0.0540, 25.0293, 0.3101, 12.1020, 0.6575, 4.7223, -0.0216),
             (0.6751, 18.342, 1.6272, 7.26, 0.9644, 2.602, 0.015)),
    ("Sm3+", (0.0288, 25.2068, 0.2973, 11.8311, 0.6954, 4.2117, -0.0213),
             (0.4707, 18.43, 1.4261, 7.034, 0.9574, 2.439, 0.0182)),
    ("Dy3+", (0.1157, 15.0732, 0.3270, 6.7991, 0.5821, 3.0202, -0.0249),
             (0.2523, 18.517, 1.0914, 6.736, 0.9345, 2.208, 0.025)),
])
def test_the_2026_09_18_audit_rows_match_both_mirrors(ion, j0_published, j2_published):
    """Two 3d rows and three 4f rows, re-verified against a live source.

    Distinct from :func:`test_j0_coefficients_match_a_published_row` above:
    that test pins two rows against a *paper*; this one pins five rows
    (⟨j₀⟩ **and** ⟨j₂⟩) against the *table this module claims to transcribe*,
    re-opened independently rather than trusted from the module's own
    history. The tolerance is exact because both mirrors carry these
    particular rows to at least 4 decimal places, matching what this table
    stores.
    """
    got_j0, got_j2 = coefficients(ion)
    assert got_j0 == pytest.approx(j0_published, abs=0.0, rel=0.0)
    assert got_j2 == pytest.approx(j2_published, abs=0.0, rel=0.0)


def test_pr3_j2_gap_is_still_not_papered_over_after_the_2026_09_18_audit():
    """The 2026-09-18 audit's Stage 2 outcome: a documented gap, not a fix.

    Two other transcriptions of "the same" Brown table (McPhase's mirror of
    P. J. Brown's own data file, and GSAS-II's ``GSASII/atmdata.py``) both
    carry a Pr³⁺ ⟨j₂⟩ row and agree with each other -- a transcription
    cross-check passing, not a primary-source reading (Michael's guidance,
    2026-09-18: a mirror agreeing with another mirror never licenses
    entering a row; only reading it from its primary publication does).
    Tracing GSAS-II's own comment on this one row ("really Pr+3 - from
    J2K") further finds "J2K" used elsewhere in GSAS-II's own git history for
    unrelated deformation-density machinery, so the row's actual primary
    source is unidentified, not merely unread (module docstring, "2026-09-18
    audit"). It is not added, for two independent reasons: no primary source
    was read for it, and ``ATTRIBUTION.md`` separately already rules out
    copying a magnetic-form-factor number from either mirror for this exact
    table (GSAS-II's grant-back clause; McPhase's GPL). The row stays absent
    pending a source this project can actually cite from
    (``checks/agent_reports/form-factor-publication-REQUEST.md``).
    """
    assert not has_j2("Pr3+")
    assert all(has_j2(i) for i in magnetic_ions() if i != "Pr3+")
    with pytest.raises(ValueError, match="4f/5f ion"):
        magnetic_form_factor("Pr3+", 0.3)
    with pytest.raises(KeyError, match=r"no ⟨j2⟩"):
        magnetic_form_factor("Pr3+", 0.3, g=0.8)


def test_the_form_factor_argument_is_sin_theta_over_lambda():
    """s = 1/2d, the same argument f₀ and the Debye-Waller factor take.

    Not Q, and not Q/4π in someone else's unit: a factor of 4π in s puts the
    form factor at the wrong angle and shows up as a wrong moment, because the
    moment is whatever makes the low-angle intensity right.  Pinned against a
    hand-evaluated exponential at one d.
    """
    d = 2.0
    s = 1.0 / (2.0 * d)
    a0, a1, b0, b1, c0, c1, dd = coefficients("Cr3+")[0]
    by_hand = (a0 * np.exp(-a1 * s * s) + b0 * np.exp(-b1 * s * s)
               + c0 * np.exp(-c1 * s * s) + dd)
    assert float(j0("Cr3+", s)) == pytest.approx(by_hand, rel=1e-14)
    # and it falls off: a magnetic form factor at d = 1 Å is well under its
    # value at d = 4 Å
    assert float(j0("Cr3+", 1.0 / 8.0)) > float(j0("Cr3+", 0.5)) > 0.0


def test_an_absent_ion_is_refused_by_name_never_mapped_to_a_neighbour():
    """Issue #202's rule on a new data table, and the reason for it.

    Fe²⁺ and Fe³⁺ are visibly different form factors, so silently serving one
    for the other returns a wrong moment with a small esd — the worst kind of
    answer.  The refusal names the ion asked for *and* the ions of that
    element the table does carry, which is the reply someone who typed
    ``Fe7+`` or ``Mn3`` needs.
    """
    with pytest.raises(KeyError, match=r"Fe, Fe1\+, Fe2\+, Fe3\+, Fe4\+"):
        coefficients("Fe7+")
    with pytest.raises(KeyError, match="no Xx at all"):
        coefficients("Xx3+")
    with pytest.raises(ValueError, match="not a magnetic-ion spelling"):
        coefficients("iron three plus")
    # the two Fe ions really are different, which is what makes the refusal
    # worth having rather than pedantic
    assert abs(float(j0("Fe2+", 0.3)) - float(j0("Fe3+", 0.3))) > 0.02


def test_a_bare_lanthanide_or_actinide_defaults_to_its_majority_magnetic_ion():
    """WP-1327 D1 / issue-magnetic-form-factor option (b): a bare element
    symbol this table cannot resolve *neutrally* (every lanthanide and
    actinide it carries — only ionic ⟨jₙ⟩ curves exist for them) falls back
    one step further, to the majority oxidation state that is *magnetic*.

    This is the table-level unit test; :mod:`tests.test_magcif`'s
    ``test_a_bare_lanthanide_with_no_neutral_row_defaults_to_its_majority_ion``
    is the same fallback exercised through a magCIF read and its diagnostic.
    """
    assert has_ion("Mn") and not has_ion("Dy") and not has_ion("Ce3+")

    # the plain Ln3+ rule
    for element, ion in (("Pr", "Pr3+"), ("Nd", "Nd3+"), ("Sm", "Sm3+"),
                         ("Gd", "Gd3+"), ("Tb", "Tb3+"), ("Dy", "Dy3+"),
                         ("Ho", "Ho3+"), ("Er", "Er3+"), ("Tm", "Tm3+")):
        got_ion, reason = resolve_assumed_ion(element)
        assert got_ion == ion
        assert has_ion(got_ion)

    # the two elements whose *magnetic* majority ion is not the plain 3+ one
    assert resolve_assumed_ion("Eu") == (
        "Eu2+", "Eu3+ is 4f6 (J=0, non-magnetic); Eu2+ (4f7, S=7/2) is the "
                "state reported for magnetically ordered Eu compounds "
                "(EuO, EuS, EuTe and similar)")
    assert resolve_assumed_ion("Yb")[0] == "Yb3+"

    # the actinides this table's own <j0> rows carry a majority ion for
    assert resolve_assumed_ion("U")[0] == "U4+"
    assert resolve_assumed_ion("Np")[0] == "Np4+"
    assert resolve_assumed_ion("Pu")[0] == "Pu3+"

    # an element already resolving neutrally is untouched: no default is
    # declared for the 3d/4d block this table carries a neutral row for
    assert resolve_assumed_ion("Mn") is None
    assert resolve_assumed_ion("Cr") is None

    # an element with no table entry at all (neutral or ionic) has no
    # sensible default either, and stays exactly as unresolved as before
    assert resolve_assumed_ion("Re") is None
    assert resolve_assumed_ion("Ga") is None


def test_ce_declares_a_default_that_does_not_currently_resolve():
    """Ce is declared as Ce3+ (Ce4+ is 4f0, non-magnetic) for the same reason
    every other lanthanide is, but this table's own coefficients (Brown, ITC
    Vol C) carry Ce2+ only. A designed-but-unavailable default must come back
    exactly like "no default" — never silently substitute a different ion
    than the one the table declares as the reason."""
    declared_ion, reason = assumed_ion_for_element("Ce")
    assert declared_ion == "Ce3+"
    assert not has_ion(declared_ion)
    assert resolve_assumed_ion("Ce") is None


def test_assumed_lande_g_matches_the_free_ion_hunds_rule_value():
    """WP-1327 D-lande-g: derive each (S, L, J) independently here — never
    trust a hand-typed g, in the implementation *or* the design brief. The
    brief's own Pu3+ entry (8/11) is a worked example of exactly that risk:
    it is the Nd3+/Np4+ value, not Pu3+'s own 5f5 ⁶H5/2 term, which shares
    Sm3+'s (S, L, J) and gives 2/7 instead — the brief said to check it, and
    checking is this test.

    g_J = 1 + [J(J+1) + S(S+1) - L(L+1)] / [2J(J+1)] (Ashcroft & Mermin, ch.
    31); ground terms from Hund's rules on each ion's 4fⁿ/5fⁿ configuration.
    """
    from fractions import Fraction as Fr

    # (ion, S, L, J, g_J as an exact fraction) — every quantum number here is
    # re-derived from the electron configuration, not copied from
    # form_factor._ASSUMED_ION_SLJ.
    cases = [
        ("Ce3+", Fr(1, 2), 3, Fr(5, 2), Fr(6, 7)),      # 4f1,  2F5/2
        ("Pr3+", 1, 5, 4, Fr(4, 5)),                     # 4f2,  3H4
        ("Nd3+", Fr(3, 2), 6, Fr(9, 2), Fr(8, 11)),      # 4f3,  4I9/2
        ("Sm3+", Fr(5, 2), 5, Fr(5, 2), Fr(2, 7)),       # 4f5,  6H5/2
        ("Eu2+", Fr(7, 2), 0, Fr(7, 2), 2),              # 4f7,  8S7/2
        ("Gd3+", Fr(7, 2), 0, Fr(7, 2), 2),              # 4f7,  8S7/2
        ("Tb3+", 3, 3, 6, Fr(3, 2)),                     # 4f8,  7F6
        ("Dy3+", Fr(5, 2), 5, Fr(15, 2), Fr(4, 3)),      # 4f9,  6H15/2
        ("Ho3+", 2, 6, 8, Fr(5, 4)),                     # 4f10, 5I8
        ("Er3+", Fr(3, 2), 6, Fr(15, 2), Fr(6, 5)),      # 4f11, 4I15/2
        ("Tm3+", 1, 5, 6, Fr(7, 6)),                     # 4f12, 3H6
        ("Yb3+", Fr(1, 2), 3, Fr(7, 2), Fr(8, 7)),       # 4f13, 2F7/2
        # 5f^n actinide ions: the same shell degeneracy as the isoelectronic
        # 4f^n ion above, so Hund's rules place them at the identical term.
        ("U4+", 1, 5, 4, Fr(4, 5)),                      # 5f2,  3H4
        ("Np4+", Fr(3, 2), 6, Fr(9, 2), Fr(8, 11)),      # 5f3,  4I9/2
        ("Pu3+", Fr(5, 2), 5, Fr(5, 2), Fr(2, 7)),       # 5f5,  6H5/2
    ]
    for ion, S, L, J, g_fraction in cases:
        g_expected = float(g_fraction)
        g_from_formula = lande_g(float(S), float(L), float(J))
        assert g_from_formula == pytest.approx(g_expected, abs=1e-12)
        # the module's declared table must reproduce the same number: this
        # checks the implementation's (S, L, J) triple is the physically
        # correct one, not merely that its formula is coded correctly
        assert assumed_lande_g(ion) == pytest.approx(g_expected, abs=1e-12)

    # Pu3+ specifically: assert it is the *different* one of the two values
    # the brief flagged as confusable, by more than rounding could explain
    assert abs(assumed_lande_g("Pu3+") - 8 / 11) > 0.1


def test_lande_g_raises_on_a_nonmagnetic_j_equals_zero_ground_state():
    """Sm2+ and Eu3+ (both 4f6) are J = 0 — no orbital-plus-spin moment, so
    g_J is undefined rather than some fallback number. This is also *why*
    neither is ever the assumed ion for Sm/Eu (`_ASSUMED_ION` picks Sm3+ and
    Eu2+, the states with an unpaired-electron ground term), so
    :func:`assumed_lande_g` never needs to raise this in practice — it is
    checked directly here rather than through a caller."""
    with pytest.raises(ValueError, match="J = 0"):
        lande_g(3.0, 3.0, 0.0)
    assert assumed_lande_g("Sm2+") is None
    assert assumed_lande_g("Eu3+") is None


def test_assumed_lande_g_is_declared_only_for_ions_the_ion_default_can_produce():
    """The g table's keys are exactly the ions :func:`resolve_assumed_ion`
    can hand back (plus ``Ce3+``, declared for D3's "if it ever resolves"
    the same way the ion table itself declares ``Ce3+`` for an ion that does
    not currently resolve) — never wider, since a g declared for an ion
    nothing ever assumes would be dead code no caller exercises. And every
    one of them genuinely needs an explicit g, or this default would never
    fire at all."""
    produced = {resolve_assumed_ion(e)[0] for e in
               ("Pr", "Nd", "Sm", "Gd", "Tb", "Dy", "Ho", "Er", "Tm",
                "Eu", "Yb", "U", "Np", "Pu")}
    assert produced == {"Pr3+", "Nd3+", "Sm3+", "Gd3+", "Tb3+", "Dy3+",
                        "Ho3+", "Er3+", "Tm3+", "Eu2+", "Yb3+",
                        "U4+", "Np4+", "Pu3+"}
    for ion in produced:
        assert assumed_lande_g(ion) is not None
        assert needs_explicit_g(ion)
    assert assumed_lande_g("Ce3+") is not None       # D3's declared ion
    assert assumed_lande_g("Mn3+") is None           # not a 4f/5f default at all
    assert assumed_lande_g("Sc2+") is None           # a 3d/4d ion never needs one


def test_g_defaults_to_two_for_3d_and_is_refused_absent_for_4f():
    """Issue #257 A5: a silent g = 2 on a rare earth drops the ⟨j₂⟩ term.

    For a 3d or 4d ion the spin-only g = 2 makes the coefficient exactly zero
    and ⟨j₂⟩ is not evaluated at all, so the default is the physics.  For a 4f
    or 5f ion it is not, and the difference is tens of percent at high angle —
    so the absent g raises rather than defaulting.
    """
    assert resolve_g("Cr3+", None) == 2.0
    assert not needs_explicit_g("Cr3+")
    assert approximation_name("Cr3+", None) == J0_ONLY

    assert needs_explicit_g("Ho3+") and needs_explicit_g("U4+")
    with pytest.raises(ValueError, match="4f/5f ion"):
        resolve_g("Ho3+", None)
    with pytest.raises(ValueError, match="4f/5f ion"):
        magnetic_form_factor("Ho3+", 0.4)
    assert "g = 1.25" in approximation_name("Ho3+", 1.25)

    # how much the silent default would have cost, measured rather than
    # asserted: Ho³⁺ at s = 0.5 Å⁻¹
    with_j2 = float(magnetic_form_factor("Ho3+", 0.5, g=1.25))
    without = float(j0("Ho3+", 0.5))
    assert abs(with_j2 - without) / without > 0.25


def test_a_bad_g_is_refused():
    for bad in (0.0, -2.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="Landé factor"):
            resolve_g("Cr3+", bad)


# ================================================================ the schema

def _ymno3_phase(moment=YMNO3_MOMENT, *, vary=False, ion="Mn3+",
                 g=None, aniso=None) -> Phase:
    return Phase(
        name="YMnO3", space_group="P 63 c m", cell=cell(*YMNO3_CELL),
        atoms=[atom("Mn", "Mn", YMNO3_SITE,
                    moment=None if moment is None
                    else Moment.from_values(moment, ion, g=g, vary=vary)),
               atom("O", "O", (0.0, 0.0, 0.25))],
        magnetic_symmetry=YMNO3_BNS)


def test_a_number_resolves_to_the_operator_list_and_the_list_is_the_model():
    """Issue #257 A4: a UNI/BNS/OG number is an alternative *input*.

    What is stored is always the operator list — decision D-4 — with the
    numbers as metadata beside it, so a phase built from ``"185.197"`` and one
    built from the strings are the same object.  Resolution is M-5's
    ``magnetic_group``; no second database lookup exists here.
    """
    phase = _ymno3_phase()
    ms = phase.magnetic_symmetry
    assert ms.bns_number == "185.197"
    assert ms.uni_number == magnetic_group("185.197").uni_number
    assert "x,y,z,+1" in ms.operations

    by_strings = MagneticSymmetry(operations=ms.operations,
                                  centerings=ms.centerings)
    assert by_strings.group().all_operations() == ms.group().all_operations()
    # a UNI int is the third spelling of the same input
    assert MagneticSymmetry.model_validate(ms.uni_number).operations == ms.operations


def test_a_candidate_from_the_isotropy_engine_loads_unchanged():
    """Decision D-4's other half: M-7 *generates*, 1327 *refines*.

    A candidate magnetic model built by the isotropy engine hands back an MSG
    operator list; that list must be loadable as ``Phase.magnetic_symmetry``
    with nothing rewritten in between, or the two halves of the track do not
    meet.  Run on LaMnO₃'s Γ candidates, which M-7 measured are exactly four.
    """
    from rietx.crystallography.magnetic.isotropy import candidates

    found = candidates("P n m a", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    assert len(found) == 4
    for cand in found:
        ops, cent = cand.group.xyz_strings()
        block = MagneticSymmetry(operations=list(ops), centerings=list(cent))
        assert block.group().all_operations() == cand.group.all_operations()


def test_a_moment_outside_the_allowed_subspace_is_refused_by_name():
    """The stated structure and the stated group must agree, and this is where.

    YMnO₃'s Mn allows only the [1 2 0] crystal-axis direction, so a moment
    along c is not a starting guess to be symmetrised — it says the two
    declarations disagree.  The message names the allowed basis.
    """
    with pytest.raises(ValidationError, match=r"allows only \[\[1, 2, 0\]\]"):
        _ymno3_phase(moment=(0.0, 0.0, 3.0))


def test_a_moment_needs_a_magnetic_symmetry():
    """Without an operator list there is no allowed subspace and no orbit."""
    with pytest.raises(ValidationError, match="declares no magnetic_symmetry"):
        Phase(name="x", space_group="P 63 c m", cell=cell(*YMNO3_CELL),
              atoms=[atom("Mn", "Mn", YMNO3_SITE,
                          moment=Moment.from_values(YMNO3_MOMENT, "Mn3+"))])


def test_a_moment_free_at_exactly_zero_is_refused():
    """|F_m|² ∝ m², so the column vanishes at the origin and cannot move.

    The same trap ``StephensStrain`` refuses for an all-zero S block, and the
    same remedy: seed a physical estimate.  Declaring a zero moment *fixed* is
    fine — it is a record, not a dead parameter.
    """
    with pytest.raises(ValidationError, match="free and exactly zero"):
        _ymno3_phase(moment=(0.0, 0.0, 0.0), vary=True)
    assert _ymno3_phase(moment=(0.0, 0.0, 0.0), vary=False) is not None


def test_a_moment_on_an_anisotropic_site_is_refused_by_name():
    """The magnetic orbit sum has no per-image U^ij shape in this version."""
    from rietx.schemas.structure import AnisoU

    with pytest.raises(ValidationError, match="anisotropic displacement block"):
        Phase(name="x", space_group="P 63 c m", cell=cell(*YMNO3_CELL),
              atoms=[Atom(label="Mn", species="Mn",
                          x=Parameter(value=YMNO3_SITE[0]),
                          y=Parameter(value=0.0), z=Parameter(value=0.0),
                          biso=Parameter(value=0.5, vary=False),
                          aniso=AnisoU.from_values((0.01,) * 3 + (0.0,) * 3),
                          moment=Moment.from_values(YMNO3_MOMENT, "Mn3+"))],
              magnetic_symmetry=YMNO3_BNS)


def test_an_unknown_ion_or_a_missing_g_is_refused_at_the_schema():
    with pytest.raises(ValidationError, match="no magnetic form factor"):
        _ymno3_phase(ion="Mn9+")
    with pytest.raises(ValidationError, match="4f/5f ion"):
        _ymno3_phase(ion="Ho3+")
    assert _ymno3_phase(ion="Ho3+", g=1.25) is not None


def test_a_moment_model_beside_a_propagation_vector_is_refused():
    """WP-1326's declared hook, live: the field name is in the tuple.

    A commensurate magnetic structure is stated *either* by k on the nuclear
    cell with no moments — 1326's hypothesis test — *or* by a magnetic space
    group with moments in the magnetic supercell.  Both on one phase is the
    same physics twice with nothing to reconcile them.
    """
    assert MOMENT_MODEL_FIELDS == ("magnetic_symmetry",)
    with pytest.raises(ValidationError, match="same thing"):
        Phase(name="x", space_group="P 63 c m", cell=cell(*YMNO3_CELL),
              propagation_vector=("0", "0", "1/2"),
              atoms=[atom("Mn", "Mn", YMNO3_SITE,
                          moment=Moment.from_values(YMNO3_MOMENT, "Mn3+"))],
              magnetic_symmetry=YMNO3_BNS)


def test_an_operator_list_that_is_not_a_group_is_refused_at_the_schema():
    """Closure is arithmetic on the strings; nothing later can rescue it."""
    with pytest.raises(ValidationError, match="not closed"):
        MagneticSymmetry(operations=["x,y,z,+1", "-x,y,z,+1", "x,-y,z,-1"])
    with pytest.raises(ValidationError, match="no identity"):
        MagneticSymmetry(operations=["-x,-y,-z,+1"])
    with pytest.raises(ValidationError, match="is empty"):
        MagneticSymmetry(operations=[])


def test_a_moment_serialises_and_reloads_unchanged():
    """A JSON round trip is bit-identical, moment and operator list alike."""
    phase = _ymno3_phase(vary=True)
    again = Phase.model_validate(phase.model_dump())
    assert again.atoms[0].moment.values() == phase.atoms[0].moment.values()
    assert again.magnetic_symmetry.operations == phase.magnetic_symmetry.operations
    assert again.model_dump_json() == phase.model_dump_json()


def test_a_phase_declaring_no_moment_is_untouched():
    """``None`` is exactly off — the field cannot perturb a structure without it."""
    plain = Phase(name="x", space_group="P 63 c m", cell=cell(*YMNO3_CELL),
                  atoms=[atom("Mn", "Mn", YMNO3_SITE)])
    assert plain.magnetic_symmetry is None
    assert plain.atoms[0].moment is None
    dumped = plain.model_dump()
    assert dumped["magnetic_symmetry"] is None
    assert dumped["atoms"][0]["moment"] is None


# ============================================== the span controls (hexagonal)

@pytest.mark.parametrize("bns, site, moment, source", [
    (YMNO3_BNS, YMNO3_SITE, YMNO3_MOMENT,
     "Brown & Chatterji (2006) Phys. Rev. B 74, 184433"),
    (SCMNO3_BNS, SCMNO3_SITE, SCMNO3_MOMENT,
     "Muñoz et al. (2000) Chem. Mater. 12, 1497"),
])
def test_a_published_moment_lies_in_the_derived_span(bns, site, moment, source):
    """The positive arm: the group allows the moment the paper reports.

    A *span* test, not a dimension count — the whole reason M-5 exposes
    ``in_span``.  ``source`` is carried so the row says where its number came
    from; the MAGNDATA entry it was checked against is named in this module's
    header, never cited as the source.
    """
    group = magnetic_group(bns)
    assert in_span(group.allowed_moment_basis(site), moment), source


#: Which wrong axial action each hexagonal fixture actually catches, written
#: down as data and asserted exactly — M-5's ``WRONG_ACTION_BITES`` shape, and
#: for its reason: a fixture that quietly stops discriminating is a control
#: that cannot fail, and the only way to notice is to pin what it does catch.
#: YMnO₃'s 185.197 is **type I**, so every ε is +1 and dropping ε changes
#: nothing there; ScMnO₃'s 185.201 is type III and catches all three.
WRONG_ACTION_BITES = {
    YMNO3_BNS: ("transpose", "use_determinant"),
    SCMNO3_BNS: ("transpose", "use_determinant", "use_time_reversal"),
}


@pytest.mark.parametrize("wrong", ["transpose", "use_determinant", "use_time_reversal"])
@pytest.mark.parametrize("bns, site, moment", [
    (YMNO3_BNS, YMNO3_SITE, YMNO3_MOMENT),
    (SCMNO3_BNS, SCMNO3_SITE, SCMNO3_MOMENT),
])
def test_each_wrong_axial_action_puts_the_published_moment_outside_the_span(
        wrong, bns, site, moment):
    """The three negative controls, on a **hexagonal** structure.

    Rᵀ instead of R, det(R) dropped, ε dropped: each is a group too, each
    leaves the *dimension* of the allowed subspace unchanged in every crystal
    system, and each moves the subspace.  M-5 measured that the transposed
    action differs from the right one only inside space groups 149-194, which
    is why both rows here are P 6₃ c m and why a rutile-, perovskite- or
    spinel-shaped control would prove nothing at all.

    Between the two structures every wrong action is caught; per structure it
    is :data:`WRONG_ACTION_BITES`, asserted rather than assumed.
    """
    from rietx.crystallography.magnetic.operators import allowed_moment_basis

    group = magnetic_group(bns)
    stab = group.site_stabilizer(site)
    right = allowed_moment_basis(stab)
    bad = allowed_moment_basis(stab, **{wrong: wrong == "transpose"})
    assert in_span(right, moment)
    bites = not in_span(bad, moment)
    assert bites == (wrong in WRONG_ACTION_BITES[bns]), (wrong, bad.tolist())
    if bites:
        # the dimension is unchanged or identical, which is the whole point:
        # a degrees-of-freedom count passes with the wrong action
        assert len(bad) == len(right) or wrong != "transpose"


def test_the_magnitude_of_a_hexagonal_moment_uses_the_cosine_metric():
    """|(1, 1, 0)| on hexagonal axes is 1 μ_B, not √2 (issue #257 A6 iii).

    The magCIF ``crystalaxis`` basis is unit vectors along the cell edges, so
    the metric has ones on the diagonal and cos γ = −½ off it; the Euclidean
    norm is simply the wrong function, and it is wrong by 41 % here.
    """
    hexagonal = YMNO3_CELL
    assert moment_magnitude((1.0, 1.0, 0.0), hexagonal) == pytest.approx(1.0, abs=1e-12)
    assert abs(np.linalg.norm([1.0, 1.0, 0.0]) - 1.0) > 0.4
    # YMnO₃'s published moment, in the same metric
    assert moment_magnitude(YMNO3_MOMENT, hexagonal) == pytest.approx(2.9098, abs=5e-4)


def test_moment_crystal_axis_to_cartesian_and_back_is_bit_identical():
    """Issue #257 A6 (ii), on a hexagonal cell where the basis is oblique."""
    from rietx.crystallography.magnetic.operators import (
        moment_from_cartesian,
        moment_to_cartesian,
    )

    for m in (YMNO3_MOMENT, SCMNO3_MOMENT, (0.7, -1.3, 2.1)):
        there = moment_to_cartesian(m, YMNO3_CELL)
        back = moment_from_cartesian(there, YMNO3_CELL)
        assert np.allclose(back, m, atol=1e-12)
    # and the conversion is not the identity on these axes, or the round trip
    # above is empty.  It *is* the identity on a moment along a alone (a is the
    # Cartesian x by convention), which is why the check needs a b component.
    assert not np.allclose(moment_to_cartesian(YMNO3_MOMENT, YMNO3_CELL),
                           YMNO3_MOMENT, atol=1e-6)
    assert np.allclose(moment_to_cartesian(SCMNO3_MOMENT, YMNO3_CELL),
                       SCMNO3_MOMENT, atol=1e-12)


def test_a_published_structure_identifies_to_its_published_bns_number():
    """Issue #257 A6 (i): strings → ``Phase.magnetic_symmetry`` → M-5 → the BNS.

    The round trip a user's magCIF takes: the operator strings go in, the
    schema stores them, and the identification comes back with the number the
    published record carries.
    """
    group = magnetic_group(YMNO3_BNS)
    ops, cent = group.xyz_strings()
    block = MagneticSymmetry(operations=list(ops), centerings=list(cent))
    assert block.group().identify().bns_number == YMNO3_BNS
    assert MagneticGroup.from_xyz(block.operations, block.centerings).order == group.order


# =============================================== the DOFs: modulus and angles

def test_the_frame_is_orthonormal_in_the_unit_vector_metric():
    """E·G·Eᵀ = I on a hexagonal cell, where G is not the identity.

    The frame is Gram-Schmidt in the magCIF metric rather than the Euclidean
    one, and on hexagonal axes those differ by cos γ = −½ — so this assertion
    is empty on a cubic cell and is the whole point on this one.
    """
    from rietx.crystallography.magnetic.moments import moment_frame, unit_metric

    g = unit_metric(YMNO3_CELL)
    assert abs(g[0, 1] + 0.5) < 1e-12          # cos 120°
    basis = magnetic_group(SCMNO3_BNS).allowed_moment_basis(SCMNO3_SITE)
    e = moment_frame(basis, YMNO3_CELL)
    assert np.allclose(e @ g @ e.T, np.eye(len(e)), atol=1e-12)
    # and the rows still span what the basis spanned
    for row in np.asarray(basis, dtype=np.float64):
        assert in_span(e, row)


@pytest.mark.parametrize("bns, site, moment, n_expected", [
    (YMNO3_BNS, YMNO3_SITE, YMNO3_MOMENT, 1),
    (SCMNO3_BNS, SCMNO3_SITE, SCMNO3_MOMENT, 2),
])
def test_the_dof_parametrisation_reproduces_a_published_moment(
        bns, site, moment, n_expected):
    """Seed → DOFs → components is the identity on a moment in the subspace.

    The positive arm of the span control, run through the *parameterisation*
    rather than through the basis: the modulus that comes back is |m| in the
    cosine metric, and rebuilding the components from (μ, angles) gives the
    published numbers back to roundoff.
    """
    from rietx.crystallography.magnetic.moments import (
        dofs_from_moment,
        moment_frame,
        moment_from_dofs,
    )

    basis = magnetic_group(bns).allowed_moment_basis(site)
    frame = moment_frame(basis, YMNO3_CELL)
    assert len(frame) == n_expected
    dofs = dofs_from_moment(frame, YMNO3_CELL, moment)
    assert abs(dofs[0]) == pytest.approx(moment_magnitude(moment, YMNO3_CELL),
                                         abs=1e-12)
    assert np.allclose(moment_from_dofs(frame, dofs), moment, atol=1e-12)


@pytest.mark.parametrize("wrong", ["transpose", "use_determinant", "use_time_reversal"])
def test_a_wrong_axial_action_cannot_carry_the_published_moment(wrong):
    """The three negative controls, through the DOF parametrisation.

    ScMnO₃ (P 6₃ c m, BNS 185.201, type III) is the row that catches all three
    — see :data:`WRONG_ACTION_BITES` — and it is hexagonal, which M-5 measured
    is the only place any of them is visible.  Under the wrong action the
    frame spans a different plane, so the round trip through (μ, φ) comes back
    at a **different moment**: the parameterisation cannot express the
    published one at all, which is a stronger statement than the basis-level
    span test and the one a refinement would actually hit.
    """
    from rietx.crystallography.magnetic.moments import (
        dofs_from_moment,
        moment_frame,
        moment_from_dofs,
    )
    from rietx.crystallography.magnetic.operators import allowed_moment_basis

    assert wrong in WRONG_ACTION_BITES[SCMNO3_BNS]
    stab = magnetic_group(SCMNO3_BNS).site_stabilizer(SCMNO3_SITE)
    bad = allowed_moment_basis(stab, **{wrong: wrong == "transpose"})
    frame = moment_frame(bad, YMNO3_CELL)
    back = moment_from_dofs(frame, dofs_from_moment(frame, YMNO3_CELL, SCMNO3_MOMENT))
    assert not np.allclose(back, SCMNO3_MOMENT, atol=1e-6), (wrong, back)
    # the right action does carry it, in the same call sequence
    right = moment_frame(allowed_moment_basis(stab), YMNO3_CELL)
    assert np.allclose(
        moment_from_dofs(right, dofs_from_moment(right, YMNO3_CELL, SCMNO3_MOMENT)),
        SCMNO3_MOMENT, atol=1e-12)


def test_a_three_dimensional_subspace_takes_a_modulus_and_two_angles():
    """A cubic site leaves the direction entirely free: (μ, θ, φ).

    And the round trip still reproduces an arbitrary direction, which is what
    makes the spherical branch worth having rather than a special case nobody
    exercises.
    """
    from rietx.crystallography.magnetic.moments import (
        DOF_NAMES,
        dofs_from_moment,
        moment_frame,
        moment_from_dofs,
    )

    # BNS 15.90 on the NiO magnetic cell has a 3-D allowed subspace on a
    # general position; simplest exhibit is the trivially free case P 1 + 1
    group = MagneticGroup.from_xyz(["x,y,z,+1"])
    frame = moment_frame(group.allowed_moment_basis((0.1, 0.2, 0.3)),
                         (4.0, 4.0, 4.0, 90.0, 90.0, 90.0))
    assert len(frame) == 3
    assert DOF_NAMES[3] == ("modulus", "polar", "azimuth")
    m = (1.1, -2.3, 0.7)
    dofs = dofs_from_moment(frame, (4.0, 4.0, 4.0, 90.0, 90.0, 90.0), m)
    assert dofs[0] == pytest.approx(np.linalg.norm(m))
    assert np.allclose(moment_from_dofs(frame, dofs), m, atol=1e-12)


def test_the_analytic_dof_derivative_matches_finite_differences():
    """``d_moment_d_dofs`` is the chain rule the analytic branch will need."""
    from rietx.crystallography.magnetic.moments import (
        d_moment_d_dofs,
        moment_frame,
        moment_from_dofs,
    )

    cubic = (4.0, 4.0, 4.0, 90.0, 90.0, 90.0)
    frame = moment_frame(np.eye(3, dtype=np.int64), cubic)
    dofs = np.array([2.5, 0.8, -1.2])
    exact = d_moment_d_dofs(frame, dofs)
    h = 1e-6
    for k in range(3):
        step = np.zeros(3)
        step[k] = h
        fd = (moment_from_dofs(frame, dofs + step)
              - moment_from_dofs(frame, dofs - step)) / (2 * h)
        assert np.allclose(exact[k], fd, atol=1e-7), k


def test_a_site_that_forbids_a_moment_contributes_no_dofs():
    """A grey group forbids every moment, so the subspace is empty.

    The schema refuses the declaration itself; this pins the layer below —
    an empty basis makes an empty frame and no DOFs, rather than three DOFs
    that all do nothing.
    """
    from rietx.crystallography.magnetic.moments import (
        DOF_NAMES,
        moment_frame,
        moment_from_dofs,
        n_dofs,
    )

    grey = MagneticGroup.from_xyz(["x,y,z,+1", "x,y,z,-1"])
    basis = grey.allowed_moment_basis((0.1, 0.2, 0.3))
    assert len(basis) == 0 and grey.is_grey
    frame = moment_frame(basis, YMNO3_CELL)
    assert n_dofs(frame) == 0 and DOF_NAMES[0] == ()
    assert np.array_equal(moment_from_dofs(frame, []), np.zeros(3))


# ==================================================== the DOFs in the θ vector

def _table(phase):
    import rietx as rx
    from rietx.params.vector import ParameterTable

    return ParameterTable(rx.Structure(phases=[phase]),
                          rx.Instrument.constant_wavelength_neutron(2.4067))


def test_the_moment_reaches_theta_as_dofs_and_the_components_are_locked():
    """``…moment.dof<k>`` is free; ``…moment.crystalaxis_*`` is a locked record.

    The components are not tied — the map is not affine — so they carry no
    ``C`` row and no esd, and the esd of the block is the modulus's.  They are
    still collected, because a path that does not exist cannot be globbed,
    exported or written back.
    """
    table = _table(_ymno3_phase(vary=True))
    paths = {e.path: e for e in table.entries}
    dof = paths["phases.0.atoms.0.moment.dof0"]
    assert dof.vary and dof.tie is None and not dof.locked
    assert dof.value == pytest.approx(moment_magnitude(YMNO3_MOMENT, YMNO3_CELL))
    assert "phases.0.atoms.0.moment.dof1" not in paths   # a 1-D subspace
    for name in ("crystalaxis_x", "crystalaxis_y", "crystalaxis_z"):
        e = paths[f"phases.0.atoms.0.moment.{name}"]
        assert e.locked and not e.vary and e.tie is None
    assert "phases.0.atoms.0.moment.dof0" in table.free_paths


def test_a_fixed_moment_block_contributes_no_free_column():
    table = _table(_ymno3_phase(vary=False))
    assert not any(".moment." in p for p in table.free_paths)
    assert "phases.0.atoms.0.moment.dof0" in {e.path for e in table.entries}


def test_the_components_follow_the_dofs_through_a_commit_and_a_write_back():
    """Doubling the modulus doubles the components, in the model and the table.

    This is the write-back path a stage takes: the DOFs move, ``commit``
    derives the components from them, and ``apply_to_models`` puts them on the
    pydantic model so the *next* stage's compile sees the refined moment
    rather than the declared one.
    """
    import rietx as rx

    phase = _ymno3_phase(vary=True)
    structure = rx.Structure(phases=[phase])
    instrument = rx.Instrument.constant_wavelength_neutron(2.4067)
    from rietx.params.vector import ParameterTable

    table = ParameterTable(structure, instrument)
    theta = table.x0()
    k = table.free_paths.index("phases.0.atoms.0.moment.dof0")
    theta[k] *= 2.0
    table.commit(theta)

    values = {e.path: e.value for e in table.entries}
    assert values["phases.0.atoms.0.moment.crystalaxis_x"] == pytest.approx(2 * 1.68)
    assert values["phases.0.atoms.0.moment.crystalaxis_y"] == pytest.approx(2 * 3.36)
    assert values["phases.0.atoms.0.moment.crystalaxis_z"] == pytest.approx(0.0, abs=1e-12)

    table.apply_to_models(structure, instrument)
    got = structure.phases[0].atoms[0].moment.values()
    assert got[0] == pytest.approx(2 * 1.68) and got[1] == pytest.approx(2 * 3.36)
    # and the model still validates: the doubled moment is in the same subspace
    assert rx.Structure.model_validate(structure.model_dump()) is not None


def test_a_structure_with_no_moment_gains_no_entries():
    """The whole block is opt-in: no moment, no paths, no frames."""
    plain = Phase(name="x", space_group="P 63 c m", cell=cell(*YMNO3_CELL),
                  atoms=[atom("Mn", "Mn", YMNO3_SITE)])
    table = _table(plain)
    assert not any(".moment" in e.path for e in table.entries)
    assert table.moment_frames() == {}


# ================================================ the magnetic structure factor

MNF2_CELL = (4.8734, 4.8734, 3.3099, 90.0, 90.0, 90.0)
#: MnF₂, rutile P 4₂/mnm, BNS 136.499 (type III, P4₂'/mnm').  Mn on 2a with the
#: moment along c: 4.6 μ_B — Erickson (1953), *Phys. Rev.* **90**, 779, via
#: MAGNDATA #0.2.  The textbook case for this rung: its strongest magnetic
#: reflection, (1 0 0), is **systematically absent** in P 4₂/mnm, so it is not
#: in the nuclear reflection list at all.
MNF2_BNS = "136.499"
LAMBDA_CW = 2.4


def _mnf2(moment=(0.0, 0.0, 4.6), *, vary=True, biso=0.0,
          space_group="P 42/m n m", bns=MNF2_BNS) -> Phase:
    return Phase(
        name="MnF2", space_group=space_group, cell=cell(*MNF2_CELL),
        atoms=[atom("Mn", "Mn", (0.0, 0.0, 0.0), biso=biso,
                    moment=None if moment is None
                    else Moment.from_values(moment, "Mn2+", vary=vary)),
               atom("F", "F", (0.3050, 0.3050, 0.0), biso=biso)],
        magnetic_symmetry=None if moment is None else bns)


def _grid(lo=10.0, hi=140.0, step=0.05):
    return np.arange(lo, hi, step)


def _compiled(phase, *, neutron=True, mode="rietveld", y=None):
    import rietx as rx
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure = rx.Structure(phases=[phase])
    instrument = (rx.Instrument.constant_wavelength_neutron(LAMBDA_CW) if neutron
                  else rx.Instrument.bragg_brentano())
    tt = _grid()
    pattern = rx.PatternData(
        two_theta=tt.tolist(),
        intensity=(np.ones_like(tt) if y is None else np.asarray(y)).tolist())
    model = compile_model(structure, instrument, pattern, mode=mode)
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    return model, table, values, structure, instrument


def _cell_of(values, ip=0):
    return tuple(values[f"phases.{ip}.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))


def test_the_magnetic_reflections_are_the_ones_the_nuclear_factor_forbids():
    """A k = 0 magnetic group puts intensity where a glide or screw kills |F_N|².

    Measured on Cr₂WO₆'s cell and wavelength, which is where WP-1326 saw it in
    real data: the two strongest 4 K residual peaks are (0 0 1) at 15.62° and
    (1 0 2) at 44.45°, both systematically absent in P 4₂/mnm and therefore
    both **missing from the nuclear reflection list**.  A magnetic phase that
    did not add them would simply not compute its own strongest peaks.
    """
    from rietx.crystallography.lattice import two_theta_deg
    from rietx.crystallography.magnetic.scattering import magnetic_reflections
    from rietx.crystallography.symmetry import generate_reflections

    cr2wo6 = (4.5754, 4.5754, 8.8538, 90.0, 90.0, 90.0)
    lam = 2.4067
    nuclear = generate_reflections("P 42/m n m", cr2wo6, lam, 150.0)
    extra = magnetic_reflections("P 42/m n m", cr2wo6, lam, 150.0)
    assert len(nuclear) == 35 and len(extra) == 14

    tt = two_theta_deg(extra.d, lam)
    rows = {tuple(map(int, h)): float(t) for h, t in zip(extra.hkl, tt, strict=True)}
    assert rows[(0, 0, 1)] == pytest.approx(15.62, abs=0.01)
    assert rows[(1, 0, 2)] == pytest.approx(44.45, abs=0.01)
    # and they really are absent: no nuclear row carries either index
    nuclear_index = {tuple(map(int, h)) for h in nuclear.hkl}
    assert (0, 0, 1) not in nuclear_index and (1, 0, 2) not in nuclear_index
    # centring conditions *are* applied, so the two sets are disjoint and their
    # union is the whole lattice in range
    assert not (set(rows) & nuclear_index)


def _colourless_group(symbol):
    """The type-I magnetic group of a space group: every operation unprimed."""
    import gemmi

    ops = [o.triplet() + ",+1" for o in gemmi.SpaceGroup(symbol).operations()]
    return MagneticGroup.from_xyz(ops)


@pytest.mark.parametrize("symbol, forbids", [
    ("F m -3 m", lambda h, k, ell: len({h % 2, k % 2, ell % 2}) > 1),
    ("I m -3 m", lambda h, k, ell: (h + k + ell) % 2 == 1),
    ("I 41/a m d", lambda h, k, ell: (h + k + ell) % 2 == 1),
])
def test_an_ordinary_magnetic_group_keeps_the_parents_centring(symbol, forbids):
    """A centred parent with an unprimed centring adds no lattice-forbidden row.

    Review of #433, finding 1: skipping gemmi's absence test to keep the glide
    and screw rows skipped the centring test with it, so a symmorphic F or I
    parent gained a row for every lattice-forbidden hkl in range — zero
    intensity under an ordinary group, but a row in the frozen windows, the
    FCJ node counts and the observation count all the same.  The two
    symmorphic parents must now add **nothing** (they have no glide or screw
    to lift); ``I 4₁/a m d`` still gains its glide rows, and every one of them
    obeys the I centring.
    """
    from rietx.crystallography.magnetic.scattering import magnetic_reflections

    cell = ((4.0, 4.0, 4.0, 90.0, 90.0, 90.0) if "m -3 m" in symbol
            else (3.8, 3.8, 9.5, 90.0, 90.0, 90.0))
    for group in (None, _colourless_group(symbol)):
        extra = magnetic_reflections(symbol, cell, 2.4, 150.0,
                                     magnetic_group=group)
        assert not [h for h in extra.hkl.tolist() if forbids(*h)]
        if "m -3 m" in symbol:
            assert len(extra) == 0
        else:
            assert len(extra) > 0


def test_a_black_white_lattice_keeps_the_rows_its_anti_centring_lights():
    """A BNS type-IV group puts its intensity exactly on the centring absences.

    The nuclear structure is body-centred (``I m -3 m``); the magnetic group is
    ``P m -3 m`` with the body centring *primed*, (½,½,½)′, so the moment
    reverses on translation and |F_m|² lives at h + k + l odd — every row the
    nuclear centring forbids.  Those rows must be generated, and only those:
    the h + k + l even ones are already nuclear rows.
    """
    import gemmi

    from rietx.crystallography.magnetic.scattering import magnetic_reflections

    primitive = [o.triplet() + ",+1"
                 for o in gemmi.SpaceGroup("P m -3 m").operations()]
    group = MagneticGroup.from_xyz(primitive,
                                   ["x,y,z,+1", "x+1/2,y+1/2,z+1/2,-1"])
    extra = magnetic_reflections("I m -3 m", (4.0, 4.0, 4.0, 90.0, 90.0, 90.0),
                                 2.4, 150.0, magnetic_group=group)
    rows = extra.hkl.tolist()
    assert rows and all(sum(h) % 2 == 1 for h in rows)
    assert [1, 0, 0] in rows and [1, 1, 1] in rows


def test_the_nuclear_term_is_exactly_zero_on_a_magnetic_only_row():
    """The mask is the absence condition, not a tolerance.

    MnF₂'s (1 0 0) is a screw absence of P 4₂/mnm, so |F_N|² there is
    identically zero by symmetry and the mask that sets it so is exact
    arithmetic rather than a threshold anyone chose.
    """
    model, _table, values, *_ = _compiled(_mnf2())
    cp = model.phases[0]
    d = np.asarray(cp.reflections.d)
    nuclear = np.asarray(model._nuclear_f2(0, d, values, _cell_of(values)))
    magnetic = np.asarray(model._magnetic_f2(0, d, values, _cell_of(values)))
    row = next(i for i, h in enumerate(cp.reflections.hkl) if tuple(h) == (1, 0, 0))
    assert cp.nuclear_mask[row] == 0.0
    assert nuclear[row] == 0.0                 # exactly, not to a tolerance
    assert magnetic[row] > 100.0               # and it is the strongest one
    assert row == int(np.argmax(magnetic))


def test_a_moment_parallel_to_q_scatters_nothing():
    """|F_⊥|² = |F|² − |Q̂·F|², so Q ‖ m gives exactly zero.

    MnF₂'s moment is along c, and (0 0 1) is a reciprocal-lattice point of the
    magnetic list — so it is in the reflection list *and* carries identically
    zero magnetic intensity.  Dropping the perpendicular projection would put
    the second-strongest magnetic peak of this structure there, which is a
    thing a person would notice in a pattern and a test would not.
    """
    model, _table, values, *_ = _compiled(_mnf2())
    cp = model.phases[0]
    d = np.asarray(cp.reflections.d)
    magnetic = np.asarray(model._magnetic_f2(0, d, values, _cell_of(values)))
    row = next(i for i, h in enumerate(cp.reflections.hkl) if tuple(h) == (0, 0, 1))
    assert magnetic[row] == 0.0
    # the projection is doing the work: without it that row would be the
    # largest |F_m|² in the list, since (0 0 1) is the lowest-angle row of all
    assert magnetic[int(np.argmax(magnetic))] > 0.0


def test_p_is_2695_fm_and_shares_the_scale_with_a_sears_b():
    """Issue #257 A6 (iv): p·m and b are the same unit, so one scale serves both.

    At s → 0 the form factor is ⟨j₀⟩(0), which Brown's fit puts within 3e-4 of
    1 rather than exactly at it — so the statement "a 1 μ_B moment and a
    b = 2.695 fm nucleus give equal magnitudes at s = 0" is true to the
    *table's own* normalisation, and that is the tolerance quoted here rather
    than a chosen one.  The exact statement, which needs no tolerance, is the
    second assertion: a moment of b/(p·⟨j₀⟩(0)) μ_B gives |F_m|² = |F_N|².
    """
    from rietx.crystallography.magnetic.scattering import P_MAGNETIC_FM
    from rietx.crystallography.neutron import b_coh

    assert P_MAGNETIC_FM == 2.695
    b = b_coh("Mn")                       # fm, Sears (1992) via crystallography.neutron
    assert b < 0.0                        # Mn's is negative; |F_N| is |b|
    f0_at_zero = float(j0("Mn2+", 0.0))

    # a moment along a, probed at a reflection along c: perpendicular, so the
    # projection keeps all of it.  ``d`` is passed in, so s → 0 is reachable
    # exactly where the form factor is normalised.
    phase = Phase(
        name="one", space_group="P 1", cell=cell(4.0, 4.0, 4.0),
        atoms=[atom("Mn", "Mn", (0.0, 0.0, 0.0), biso=0.0,
                    moment=Moment.from_values((1.0, 0.0, 0.0), "Mn2+"))],
        magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))
    model, _table, values, *_ = _compiled(phase)
    cp = model.phases[0]
    row = next(i for i, h in enumerate(cp.reflections.hkl) if tuple(h) == (0, 0, 1))
    d = np.full(len(cp.reflections), 1e7)          # s = 5e-8: the s → 0 limit
    magnetic = np.asarray(model._magnetic_f2(0, d, values, _cell_of(values)))
    nuclear = np.asarray(model._nuclear_f2(0, d, values, _cell_of(values)))

    assert np.sqrt(magnetic[row]) == pytest.approx(P_MAGNETIC_FM * f0_at_zero, rel=1e-9)
    assert np.sqrt(nuclear[row]) == pytest.approx(abs(b), rel=1e-12)
    # 1 μ_B against a 2.695 fm nucleus.  The gap is *exactly* the table's own
    # normalisation error for this ion — ⟨j₀⟩(0) = 0.9992 for Mn²⁺, Brown's
    # fit not being constrained to sum to one — so the tolerance is derived
    # from it rather than chosen, and it is 8×10⁻⁴ relative here.
    gap = abs(np.sqrt(magnetic[row]) - 2.695) / 2.695
    assert gap == pytest.approx(abs(1.0 - f0_at_zero), rel=1e-6)
    assert gap < 1e-3


def test_a_cubic_collinear_structure_averages_to_a_direction_independent_intensity():
    """Shirane (1959), measured: the orbit average kills the direction, to fp64.

    A ferromagnetic moment on the single site of a cubic cell, with the
    magnetic symmetry stated as translation alone so that all three direction
    DOFs are free.  ⟨(Q̂·m̂)²⟩ over a cubic Laue orbit is ⅓ for *every* m̂ — the
    average of Q̂Q̂ᵀ over a cubic point group is isotropic — so the
    orbit-averaged intensity is ⅔·|p·f·m|² whatever the direction.

    This is the test the naive shortcut fails: "one representative times the
    multiplicity" would leave |F_⊥|² a function of the direction on every row,
    because it never averages over the orbit at all.
    """
    def f2_of(moment):
        phase = Phase(
            name="cubic", space_group="P m -3 m", cell=cell(4.0, 4.0, 4.0),
            atoms=[atom("M", "Mn", (0.0, 0.0, 0.0), biso=0.0,
                        moment=Moment.from_values(moment, "Mn2+", vary=True))],
            magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))
        model, _t, values, *_ = _compiled(phase)
        d = np.asarray(model.phases[0].reflections.d)
        return (model.phases[0],
                np.asarray(model._magnetic_f2(0, d, values, _cell_of(values))))

    cp, base = f2_of((3.0, 0.0, 0.0))
    assert len(base) >= 9 and base.min() > 0.0
    r3 = float(np.sqrt(3.0))
    for direction in [(0.0, 3.0, 0.0), (0.0, 0.0, 3.0), (r3, r3, r3), (1.0, 2.0, 2.0)]:
        _cp, other = f2_of(direction)
        assert np.max(np.abs(other - base) / base) < 8e-15, direction

    # and the value is the ⅔ the argument above predicts, on the first row
    from rietx.crystallography.magnetic.scattering import P_MAGNETIC_FM

    s = 1.0 / (2.0 * cp.reflections.d[0])
    predicted = (2.0 / 3.0) * (P_MAGNETIC_FM * 3.0 * float(j0("Mn2+", s))) ** 2
    assert base[0] == pytest.approx(predicted, rel=1e-12)


def test_the_orbit_average_is_not_one_representative():
    """The shortcut that survives a cubic test, and the row that catches it.

    On a **uniaxial** structure with an in-plane moment the members of one Laue
    orbit have genuinely different |F_⊥|²: (1 0 0) and (0 1 0) coincide in a
    powder and sit at different angles to a moment along **a**.  So the orbit
    average differs from the representative's own value, and it differs by a
    factor of order one rather than by roundoff.  Measured, so that a future
    "optimisation" back to one representative fails here rather than in
    somebody's moment.
    """
    from rietx.crystallography.magnetic.scattering import magnetic_f2

    phase = Phase(
        name="uniaxial", space_group="P 4/m m m", cell=cell(4.0, 4.0, 6.0),
        atoms=[atom("M", "Mn", (0.0, 0.0, 0.0), biso=0.0,
                    moment=Moment.from_values((3.0, 0.0, 0.0), "Mn2+"))],
        magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))
    model, _table, values, *_ = _compiled(phase)
    cp = model.phases[0]
    d = np.asarray(cp.reflections.d)
    averaged = np.asarray(model._magnetic_f2(0, d, values, _cell_of(values)))
    # the same call with each reflection reduced to its representative
    reps = cp.reflections.hkl.astype(np.int64)
    single = magnetic_f2(reps, np.arange(len(reps)), np.ones(len(reps)),
                         1.0 / (2.0 * d), cp.magnetic, _cell_of(values),
                         *model._site_values(0, values, _cell_of(values))[:3],
                         model._moment_dofs(0, values))
    disagree = np.abs(single - averaged) > 1e-9 * np.maximum(averaged, 1.0)
    assert disagree.sum() >= 3, (averaged.tolist(), single.tolist())


# ======================================= dispatch, bit-identity, the Jacobian

def test_a_phase_with_no_moment_is_bit_identical():
    """The acceptance line, measured rather than argued.

    Every number a fixture pins — the calculated profile, the reflection list,
    the tick positions — is byte-identical to the same phase compiled before
    this WP existed, because ``magnetic`` and ``nuclear_mask`` are ``None``
    there and the additions never happen.  ``None`` is not an array of ones:
    the multiply does not occur, so the arithmetic is the arithmetic that ran
    before, in the same order.
    """
    import hashlib

    model, _t, values, *_ = _compiled(_mnf2(moment=None))
    cp = model.phases[0]
    assert cp.magnetic is None and cp.nuclear_mask is None
    assert cp.mag_members is None
    y = np.asarray(model.evaluate(values), dtype=np.float64)
    assert model._magnetic_f2(0, np.asarray(cp.reflections.d), values,
                              _cell_of(values)) is None
    digest = hashlib.sha256(y.tobytes()).hexdigest()

    # a second compile of the same declaration reproduces it byte for byte
    model2, _t2, values2, *_ = _compiled(_mnf2(moment=None))
    y2 = np.asarray(model2.evaluate(values2), dtype=np.float64)
    assert hashlib.sha256(y2.tobytes()).hexdigest() == digest
    assert y.tobytes() == y2.tobytes()


def test_qpa_is_bit_identical_with_and_without_a_moment_block():
    """``phase_zmv`` reads species, occupancy and multiplicity — never a moment.

    That is the whole argument for a moment being a *site attribute* rather
    than FullProf's separate magnetic phase, which doubles the specimen's mass
    unless excluded by hand.  The trap is unreachable here, and this measures
    it on a two-phase fixture: identical weight fractions, bit for bit.
    """
    import rietx as rx
    from rietx.optimize.qpa import phase_zmv, weight_fractions

    other = Phase(name="NaCl", space_group="F m -3 m", cell=cell(5.64, 5.64, 5.64),
                  atoms=[atom("Na", "Na", (0.0, 0.0, 0.0)),
                         atom("Cl", "Cl", (0.5, 0.5, 0.5))])

    def fractions(first):
        structure = rx.Structure(phases=[first, other])
        k = [phase_zmv(p.space_group, p.cell.lengths_angles(),
                       [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
                        for a in p.atoms]).zmv
             for p in structure.phases]
        return weight_fractions(k, [1.0, 2.5])[0]

    with_moment = fractions(_mnf2())
    without = fractions(_mnf2(moment=None))
    assert np.asarray(with_moment).tobytes() == np.asarray(without).tobytes()


def test_the_term_reaches_a_neutron_histogram_and_nothing_else():
    """Radiation dispatch: ``neutron_cw`` only, X-ray identically zero.

    On an X-ray histogram the magnetic block is not built at all — not built
    and evaluated to zero — so the phase's X-ray arithmetic is untouched and
    the moment has no gradient anywhere, which is the state the hold rule
    reports as never observed.
    """
    from rietx.model.forward import magnetic_wanted

    phase = _mnf2()
    model, _t, values, _s, instrument = _compiled(phase, neutron=False)
    assert not magnetic_wanted(phase, instrument.source)
    cp = model.phases[0]
    assert cp.magnetic is None and cp.nuclear_mask is None
    assert model._magnetic_f2(0, np.asarray(cp.reflections.d), values,
                              _cell_of(values)) is None

    neutron_model, _t2, _v2, _s2, neutron = _compiled(phase)
    assert magnetic_wanted(phase, neutron.source)
    assert neutron_model.phases[0].magnetic is not None
    # a phase with no moment answers False on either radiation
    assert not magnetic_wanted(_mnf2(moment=None), neutron.source)


def test_an_unknown_source_is_refused_by_name():
    """The dispatch is by *radiation*, and it refuses rather than guessing.

    A source that is neither neutron nor X-ray must be refused: a dispatch that
    guessed would put a magnetic term on a radiation nobody has checked,
    silently.  The X-ray row beside it is the control that keeps the refusal
    from being "everything is refused".
    """
    from rietx.model.forward import magnetic_wanted

    class _Xray:
        kind = "xray_cw"

    class _Electron:
        kind = "electron_cw"

    assert magnetic_wanted(_mnf2(), _Xray()) is False
    with pytest.raises(ValueError, match="refuses any other source by name"):
        magnetic_wanted(_mnf2(), _Electron())
    # and a phase with no moment answers False whatever the source
    assert magnetic_wanted(_mnf2(moment=None), _Xray()) is False
    assert magnetic_wanted(_mnf2(moment=None), _Electron()) is False


def test_the_moment_column_of_the_jacobian_matches_a_whole_model_finite_difference():
    """The moment rides the peak chain, and the chain is exact for it.

    A moment DOF moves the per-peak **intensity** and nothing else — no
    position, no width — so ``_peak_chain_column``'s analytic profile bases
    carry it exactly and only the intensity is finite-differenced.  Checked
    against a whole-model FD of the residual, which is the fallback the WP
    names and the thing the chain has to agree with.

    The failure this guards is specific and silent: if the |F|² memo were not
    keyed on the moment DOFs, the perturbed ``phase_peaks`` would return the
    unperturbed intensity and the column would come back **identically zero** —
    a moment that cannot refine, with no error anywhere.
    """
    import rietx as rx
    from rietx.optimize.least_squares import _make_jacobian

    phase = _mnf2(moment=(0.0, 0.0, 3.0), biso=0.4)
    model, table, values, structure, instrument = _compiled(phase)
    y = np.asarray(model.evaluate(values), dtype=np.float64)
    model, table, _v, structure, instrument = _compiled(phase, y=y + 30.0)
    table.set_vary(["phases.0.scale", "phases.0.atoms.*.moment.dof*"], True)
    theta = table.x0()
    col = table.free_paths.index("phases.0.atoms.0.moment.dof0")

    jac = _make_jacobian(model, table)(theta)
    analytic = np.asarray(jac[: len(model.tt), col], dtype=np.float64)

    sqrt_w = 1.0 / np.asarray(model.sigma, dtype=np.float64)
    h = 1e-6 * max(1.0, abs(theta[col]))
    up, dn = theta.copy(), theta.copy()
    up[col] += h
    dn[col] -= h
    fd = -sqrt_w * (np.asarray(model.evaluate(table.decode(up)))
                    - np.asarray(model.evaluate(table.decode(dn)))) / (2 * h)

    scale = max(float(np.abs(fd).max()), 1e-12)
    assert float(np.abs(analytic - fd).max()) / scale < 1e-5
    # and it is not the trivially-passing zero column
    assert scale > 1e-6
    assert rx is not None


def test_a_seeded_moment_refines_back_to_the_moment_that_made_the_pattern():
    """The end-to-end statement: state it, refine it, get it back.

    A synthetic MnF₂ pattern is generated at 3.0 μ_B, the model is seeded at
    1.0, and the fit recovers it.  Nuclear and magnetic share one scale — the
    scale is refined alongside and there is no second one to refine.
    """
    import rietx as rx

    truth = _mnf2(moment=(0.0, 0.0, 3.0), biso=0.4)
    model, _t, values, *_ = _compiled(truth)
    y = np.asarray(model.evaluate(values), dtype=np.float64) + 25.0

    start = _mnf2(moment=(0.0, 0.0, 1.0), biso=0.4)
    structure = rx.Structure(phases=[start])
    instrument = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    data = rx.PatternData(two_theta=_grid().tolist(), intensity=y.tolist())
    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*"]),
    ]))
    rows = {p.path: p for p in result.parameters}
    modulus = rows["phases.0.atoms.0.moment.dof0"]
    assert abs(modulus.value) == pytest.approx(3.0, abs=0.05), modulus.value
    assert modulus.stderr is not None and modulus.stderr < 0.1
    fitted = ref.fitted_structure.phases[0].atoms[0].moment.values()
    assert abs(fitted[2]) == pytest.approx(3.0, abs=0.05)
    assert fitted[0] == pytest.approx(0.0, abs=1e-9)


def test_the_direction_a_powder_cannot_see_measures_nothing():
    """The flat direction, measured — and why it is not *bitwise* flat.

    On the cubic collinear structure the orbit-averaged intensity is
    independent of the moment direction to fp64, so the two angle DOFs are
    flat directions of θ.  What comes back is an esd **ten orders of magnitude
    larger** than the modulus's, because their Jacobian column is not exactly
    zero: it is the finite-difference of a quantity that cancels analytically,
    so it sits at ~1e-10 of the modulus's column rather than at 0.

    That matters, because ``ParameterTable.unmeasured_free`` — the package's
    "this measured nothing" mechanism — fires on a column with **no gradient
    at all** (``normal_covariance``: ``d > 0.0``), and roundoff is a gradient.
    So the WP's acceptance sentence, "the direction DOFs come back in
    ``unmeasured_rows`` with no esd", is not reachable through that route for
    an *analytically* flat direction.  What this rung does instead is hold
    them: see ``test_a_flat_moment_direction_is_held_and_named``, where the
    same structure comes back with the angles held and no esd at all.
    """
    import rietx as rx

    def cubic(moment):
        return Phase(
            name="cubic", space_group="P m -3 m", cell=cell(4.0, 4.0, 4.0),
            atoms=[atom("M", "Mn", (0.0, 0.0, 0.0), biso=0.3,
                        moment=Moment.from_values(moment, "Mn2+", vary=True))],
            magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))

    model, table, values, *_ = _compiled(cubic((3.0, 0.0, 0.0)))
    table.set_vary(["phases.0.scale", "phases.0.atoms.*.moment.dof*"], True)
    theta = table.x0()
    columns = {}
    for c, path in enumerate(table.free_paths):
        h = 1e-6 * max(1.0, abs(theta[c]))
        up, dn = theta.copy(), theta.copy()
        up[c] += h
        dn[c] -= h
        col = (np.asarray(model.evaluate(table.decode(up)))
               - np.asarray(model.evaluate(table.decode(dn)))) / (2 * h)
        columns[path] = float(np.linalg.norm(col))

    modulus = columns["phases.0.atoms.0.moment.dof0"]
    assert modulus > 1e3
    for k in (1, 2):
        angle = columns[f"phases.0.atoms.0.moment.dof{k}"]
        assert angle / modulus < 1e-9, (k, angle, modulus)
    assert rx is not None


# ================================================ the hold, and what it reports

def _cubic_phase(moment, *, vary=True, biso=0.3) -> Phase:
    return Phase(
        name="cubic", space_group="P m -3 m", cell=cell(4.0, 4.0, 4.0),
        atoms=[atom("M", "Mn", (0.0, 0.0, 0.0), biso=biso,
                    moment=Moment.from_values(moment, "Mn2+", vary=vary))],
        magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))


def _fit(truth_phase, start_phase, *, background=20.0, stages=None):
    import rietx as rx

    model, _t, values, *_ = _compiled(truth_phase)
    y = np.asarray(model.evaluate(values), dtype=np.float64) + background
    structure = rx.Structure(phases=[start_phase])
    instrument = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    data = rx.PatternData(two_theta=_grid().tolist(), intensity=y.tolist())
    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=stages or [
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*"]),
    ]))
    return ref, result


def test_a_flat_moment_direction_is_held_and_named():
    """The WP's rule for a direction the powder cannot determine.

    On the cubic collinear structure the orbit-averaged intensity does not
    depend on the moment direction, so both angle DOFs come back **held** —
    absent from the free set, therefore with no esd at all rather than a small
    one — while the modulus refines and carries its esd.  The report names
    them, so a reader is told what the measurement could not see instead of
    being handed a direction nobody measured.
    """
    ref, result = _fit(_cubic_phase((3.0, 0.0, 0.0)),
                       _cubic_phase((2.0, 0.5, 0.5)))
    rows = {p.path: p for p in result.parameters}
    modulus = rows["phases.0.atoms.0.moment.dof0"]
    assert abs(modulus.value) == pytest.approx(3.0, abs=0.1), modulus.value
    assert modulus.stderr is not None
    for k in (1, 2):
        assert f"phases.0.atoms.0.moment.dof{k}" not in rows

    held = set(result.stages[-1].held)
    assert held == {"phases.0.atoms.0.moment.dof1",
                    "phases.0.atoms.0.moment.dof2"}, held

    report = ref.report()
    assert len(report.magnetic) == 1
    row = report.magnetic[0]
    assert row.supported and row.ion == "Mn2+"
    assert row.unmeasured_directions == ["polar", "azimuth"]
    assert row.free_directions == ["polar", "azimuth"]
    assert "does not determine" in row.note
    assert row.magnitude == pytest.approx(abs(modulus.value), rel=1e-12)
    assert row.magnitude_from_components == pytest.approx(row.magnitude, rel=1e-9)
    assert row.approximation == J0_ONLY
    # and it round-trips through JSON with the new section
    again = type(report).model_validate_json(report.model_dump_json())
    assert again.magnetic[0].unmeasured_directions == ["polar", "azimuth"]


def test_a_moment_the_phase_hold_took_stays_held_with_its_phase():
    """A modulus held because its *phase* is invisible is not released as a direction.

    Review of #433, finding 2.  The phase hold (WP-1301) takes every free
    structural path of a phase the data cannot see, ``moment.dof0`` included.
    Read back by name, those paths went to the direction probe, which skips
    ``dof0`` by construction and so released it after the first solve — and the
    second solve walked the modulus of a still-invisible phase from 2.12 to
    −1.73 μ_B (measured on this fixture before the fix).  The moment DOFs
    must stay held, with their phase, at the values they started from.
    """
    import rietx as rx

    nuclear = Phase(name="nuc", space_group="P m -3 m", cell=cell(4.1, 4.1, 4.1),
                    atoms=[atom("Cs", "Cs", (0.0, 0.0, 0.0)),
                           atom("Cl", "Cl", (0.5, 0.5, 0.5))])
    model, _t, values, *_ = _compiled(nuclear)
    y = np.asarray(model.evaluate(values), dtype=np.float64) + 20.0
    invisible = _cubic_phase((2.0, 0.5, 0.5)).model_copy(
        update={"scale": Parameter(value=1e-10, min=0.0)})
    ref = rx.Refinement(rx.Structure(phases=[nuclear, invisible]),
                        rx.Instrument.constant_wavelength_neutron(LAMBDA_CW))
    result = ref.fit(
        rx.PatternData(two_theta=_grid().tolist(), intensity=y.tolist()),
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
            rx.Stage("moment", ["phases.*.atoms.*.moment.dof*"]),
        ]))
    moment = {f"phases.1.atoms.0.moment.dof{k}" for k in range(3)}
    assert moment <= set(result.stages[-1].held), result.stages[-1].held
    assert not moment & {p.path for p in result.parameters}
    assert ref.structure.phases[1].atoms[0].moment.values() == pytest.approx(
        (2.0, 0.5, 0.5), abs=1e-12)


def test_a_determinable_direction_is_not_held():
    """The control the hold needs, or it is a rule that cannot fail.

    A uniaxial structure *does* determine the angle between the moment and its
    unique axis — that is the other half of Shirane's statement — so the polar
    DOF of a moment on a tetragonal cell is measured and stays free.  Without
    this row the hold above would be indistinguishable from "hold every
    direction always".
    """
    def uniaxial(moment):
        return Phase(
            name="uniaxial", space_group="P 4/m m m", cell=cell(4.0, 4.0, 6.5),
            atoms=[atom("M", "Mn", (0.0, 0.0, 0.0), biso=0.3,
                        moment=Moment.from_values(moment, "Mn2+", vary=True))],
            magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))

    ref, result = _fit(uniaxial((1.5, 0.0, 2.6)), uniaxial((1.0, 0.0, 2.0)))
    held = set(result.stages[-1].held)
    assert "phases.0.atoms.0.moment.dof1" not in held        # the polar angle
    rows = {p.path: p for p in result.parameters}
    polar = rows["phases.0.atoms.0.moment.dof1"]
    assert polar.stderr is not None
    # the azimuth, which the uniaxial powder cannot see, is held
    assert "phases.0.atoms.0.moment.dof2" in held
    report = ref.report()
    assert report.magnetic[0].unmeasured_directions == ["azimuth"]


def test_the_null_test_reports_the_moment_unsupported_rather_than_small():
    """A pattern with no magnetic intensity: held at the floor, not fitted.

    The same model refined against a purely nuclear pattern — the synthetic
    stand-in for Cr₂WO₆ at 150 K, above its ordering temperature.  |F_m|² ∝ m²,
    so the least-squares problem's only way to reduce χ² is to drive the
    modulus to nothing, and the honest report of the answer is "the data does
    not support a moment here", not a small number with a small esd.
    """
    nuclear_only = _mnf2(moment=None)
    start = _mnf2(moment=(0.0, 0.0, 2.0), biso=0.0)
    ref, result = _fit(nuclear_only, start)

    rows = {p.path: p for p in result.parameters}
    modulus = rows["phases.0.atoms.0.moment.dof0"]
    assert abs(modulus.value) < 1e-2, modulus.value

    report = ref.report()
    row = report.magnetic[0]
    assert not row.supported, (row.magnitude, row.note)
    assert "unsupported, not as a small moment" in row.note
    assert "at its floor" in row.note
    assert row.magnitude < 1e-2


def test_supported_is_a_ratio_and_not_only_a_floor():
    """The null test on real data does not land at zero — it lands inside its esd.

    Measured on the Cr₂WO₆ tutorial data: refined against the 150 K pattern,
    above the ordering temperature, one stage list brought the modulus back at
    0.067 μ_B with an esd of 0.395 — **six times larger** — and the shipped
    acceptance protocol (``test_acceptance_magnetic.py``) at 0.067 ± 1.02. An
    absolute floor calls either supported. The honest reading is |m|/σ, and
    that is what ``MomentEvidence.supported`` tests, so the two arms are
    checked here on the numbers that motivated the rule.
    """
    from rietx.report.schemas import MOMENT_SUPPORT_SIGMA, MomentEvidence

    assert MOMENT_SUPPORT_SIGMA == 3.0

    def supported(magnitude, sigma):
        # the same expression ``report.magnetic`` applies, exercised directly
        from rietx.schemas.structure import MOMENT_FLOOR_MU_B

        if sigma is None:
            return None
        return not (magnitude <= MOMENT_FLOOR_MU_B
                    or magnitude <= MOMENT_SUPPORT_SIGMA * sigma)

    assert supported(0.0666, 0.3947) is False   # Cr₂WO₆ at 150 K: 0.17σ
    assert supported(2.010, 0.046) is True      # Cr₂WO₆ at 4 K: 44σ
    assert supported(0.0670, 1.022) is False    # the shipped null: 0.07σ
    assert supported(2.125, 0.060) is True      # the shipped 4 K fit: 35σ
    assert supported(1e-9, 1e-6) is False       # the floor arm
    # no esd, nothing tested: ``None``, never an answer (review of #433,
    # finding 5) — at the floor or not
    assert supported(1e-9, None) is None
    assert supported(2.0, None) is None         # a fixed block that never refined
    assert MomentEvidence(phase="p", atom="a", ion="Cr3+", magnitude=2.0,
                          magnitude_from_components=2.0, crystalaxis=[0, 0, 2],
                          approximation="x").supported is None


def test_a_stated_and_held_moment_is_not_tested_rather_than_supported():
    """The writer's half of finding 5: a modulus with no esd reports ``None``.

    A moment stated with ``vary=False`` and a plan that never frees it does
    not refine, so it has no esd and no ratio to take.  The row must say "not tested", not ``True`` with an empty
    note — the defaulted answer WP-1076 names.
    """
    import rietx as rx

    ref, _result = _fit(_cubic_phase((3.0, 0.0, 0.0)),
                        _cubic_phase((2.5, 0.0, 0.0), vary=False),
                        stages=[rx.Stage("scale", ["phases.*.scale",
                                                   "instrument.background.c*"])])
    row = ref.report().magnetic[0]
    assert row.magnitude_esd is None
    assert row.supported is None
    assert "not tested" in row.note


def test_the_report_names_the_approximation_per_ion():
    """"Which f(s) did you use" is a question a report has to be able to answer.

    A 4f ion refines under ⟨j₀⟩ + (2/g − 1)⟨j₂⟩ with g named; a 3d one under
    ⟨j₀⟩ alone.  The two are FullProf's ``JHO3`` and ``MHO3`` for the same
    element, and a fit that does not say which is not checkable.
    """
    phase = Phase(
        name="two-ions", space_group="P 4/m m m", cell=cell(4.0, 4.0, 6.5),
        atoms=[atom("Mn", "Mn", (0.0, 0.0, 0.0), biso=0.3,
                    moment=Moment.from_values((0.0, 0.0, 3.0), "Mn2+")),
               atom("Ho", "Ho", (0.5, 0.5, 0.5), biso=0.3,
                    moment=Moment.from_values((0.0, 0.0, 8.0), "Ho3+", g=1.25))],
        magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))
    model, _t, values, structure, _i = _compiled(phase)
    from rietx.report.magnetic import analyse_moments

    rows = analyse_moments(model, values, structure)
    assert [r.ion for r in rows] == ["Mn2+", "Ho3+"]
    assert rows[0].approximation == J0_ONLY
    assert rows[1].approximation == "dipole, <j0> + (2/g - 1)<j2>, g = 1.25"
    assert model.phases[0].magnetic.named_approximations() == {
        "Mn2+": rows[0].approximation, "Ho3+": rows[1].approximation}


def test_the_report_arm_is_empty_for_cause_without_a_magnetic_model():
    """Three ways to be empty, none of them "no moment was found"."""
    from rietx.report.magnetic import analyse_moments

    assert analyse_moments(None, {}) == []
    model, _t, values, structure, _i = _compiled(_mnf2(moment=None))
    assert analyse_moments(model, values, structure) == []
    xray, _t2, values2, structure2, _i2 = _compiled(_mnf2(), neutron=False)
    assert analyse_moments(xray, values2, structure2) == []


def test_a_coordinate_stage_does_not_free_the_moment():
    """Why the DOF paths are ``moment.dof0`` and not ``moment.dof.k``.

    The built-in staged plan frees coordinates with
    ``phases.*.atoms.*.dof.*``, and ``fnmatch``'s ``*`` crosses dots — so a
    path spelled ``phases.0.atoms.0.moment.dof.0`` **matches that glob** and
    every coordinate stage in the package would silently free every moment in
    the model.  Measured here rather than argued, in both directions: the
    coordinate glob claims the coordinate DOFs and nothing else, and the
    moment glob claims the moment DOFs and nothing else.

    This is the one place this rung deviates from the WP's spelling of the
    path, and the deviation is what makes the WP's own design work.
    """
    from fnmatch import fnmatchcase

    table = _table(_ymno3_phase(vary=True))
    paths = [e.path for e in table.entries]
    coords = [p for p in paths if fnmatchcase(p, "phases.*.atoms.*.dof.*")]
    moments = [p for p in paths if fnmatchcase(p, "phases.*.atoms.*.moment.dof*")]
    assert moments == ["phases.0.atoms.0.moment.dof0"]
    assert not set(coords) & set(moments)
    assert all(".moment." not in p for p in coords)
    # the collision the spelling avoids, stated as the fact it is
    assert fnmatchcase("phases.0.atoms.0.moment.dof.0", "phases.*.atoms.*.dof.*")
    assert not fnmatchcase("phases.0.atoms.0.moment.dof0", "phases.*.atoms.*.dof.*")


def test_the_capability_flag_is_derived_from_the_fields():
    """``capabilities()`` reports the moment model, from the schema not a literal.

    The version literal is **re-pinned, never relaxed**: what this asserts is
    that somebody noticed, and a test accepting any version would assert
    nothing.
    """
    import rietx as rx

    caps = rx.capabilities()
    assert caps.features["magnetic_moments"] is True
    # ``Atom.moment`` and ``Phase.magnetic_symmetry`` landed together with
    # WP-1327, on the rung after #431's 0.27.  WP-1454 took the next, 0.29;
    # ``Phase.symmetry_operations`` (the operation-list phase, #448) took 0.30;
    # the supercell's ``MagneticSymmetry.propagation_vector_parent`` took 0.31,
    # and WP-1326's ``Phase.propagation_vector`` the one after, 0.32.
    assert caps.schema_version == "0.32"


def test_every_moment_dof_has_a_help_entry():
    """A parameter a person can free is a parameter the registry describes."""
    from rietx.help import help_for

    table = _table(_ymno3_phase(vary=True))
    for entry in table.entries:
        if ".moment." not in entry.path:
            continue
        got = help_for(entry.path)
        assert got is not None, entry.path
        assert "μ_B" in (got.unit or "") or "modulus" in got.description


#: A trirutile, the Cr₂WO₆ shape: P 4₂/mnm with the magnetic ion on 4e and an
#: orthorhombic type-III magnetic subgroup (BNS 58.395) that leaves the whole
#: ab-plane open at the site.  Four moments related by the group, so the
#: in-plane *angle* changes the pattern — unlike a single-site structure, where
#: the tetragonal orbit average makes it flat.  Synthetic: the cell is
#: Cr₂WO₆'s, nothing else is.
TRIRUTILE_BNS = "58.395"
TRIRUTILE_CELL = (4.5754, 4.5754, 8.8538, 90.0, 90.0, 90.0)


def _trirutile(moment) -> Phase:
    return Phase(
        name="trirutile", space_group="P 42/m n m", cell=cell(*TRIRUTILE_CELL),
        atoms=[atom("Cr", "Cr", (0.0, 0.0, 0.333), biso=0.3,
                    moment=Moment.from_values(moment, "Cr3+", vary=True)),
               atom("W", "W", (0.0, 0.0, 0.0), biso=0.3)],
        magnetic_symmetry=TRIRUTILE_BNS)


def test_the_flat_direction_probe_reads_curvature_and_not_only_a_gradient():
    """The defect a derivative-scale probe has, and the fix, measured.

    The intensity as a function of a moment's azimuth is **stationary** at
    every direction the symmetry fixes, so its first derivative vanishes there
    even when the angle is perfectly well determined.  A probe at
    finite-difference scale therefore reads a *determined* direction sitting at
    its own optimum as flat, and the hold would report it as something the
    powder could not see — the one thing this rung must not do.

    Measured on the trirutile above, with the moment along **a**, which is the
    optimum of the in-plane angle: a 1e-6 step reads 7e-7 of the modulus's
    response — under the hold's floor — and a 0.1 rad rotation reads 6e-2,
    four orders above it.  At 45° to **a**, where the derivative does not
    vanish, both read order one.  So the probe rotates by
    ``MOMENT_PROBE_ANGLE_RAD`` and the two cases stop looking alike.
    """
    from rietx.refine import MOMENT_DIRECTION_SUPPORT, MOMENT_PROBE_ANGLE_RAD

    assert MOMENT_PROBE_ANGLE_RAD == 0.1

    def ratio(moment, step):
        model, table, values, *_ = _compiled(_trirutile(moment))
        y0 = np.asarray(model.evaluate(values), dtype=np.float64)

        def resp(path, delta):
            v = dict(values)
            v[path] = values[path] + delta
            return float(np.linalg.norm(
                np.asarray(model.evaluate(v), dtype=np.float64) - y0))

        base = "phases.0.atoms.0.moment"
        mu = abs(values[f"{base}.dof0"])
        return resp(f"{base}.dof1", step) / resp(f"{base}.dof0", step * mu)

    along_a = (3.0, 0.0, 0.0)
    at_45 = (2.1213, 2.1213, 0.0)
    # the trap: at the optimum the *gradient* vanishes
    assert ratio(along_a, 1e-6) < MOMENT_DIRECTION_SUPPORT
    # and the curvature does not
    assert ratio(along_a, MOMENT_PROBE_ANGLE_RAD) > 1e3 * MOMENT_DIRECTION_SUPPORT
    # away from the optimum both read order one, which is the control: the
    # first assertion is about a stationary point, not about a small number
    assert ratio(at_45, 1e-6) > 0.5
    assert ratio(at_45, MOMENT_PROBE_ANGLE_RAD) > 0.5


def test_a_determined_in_plane_angle_at_its_own_optimum_is_not_held():
    """The same statement through the refinement, which is where it matters."""
    ref, result = _fit(_trirutile((3.0, 0.0, 0.0)), _trirutile((2.5, 0.0, 0.0)))
    held = set(result.stages[-1].held)
    assert "phases.0.atoms.0.moment.dof1" not in held, held
    report = ref.report()
    assert report.magnetic[0].unmeasured_directions == []
    rows = {p.path: p for p in result.parameters}
    assert rows["phases.0.atoms.0.moment.dof1"].stderr is not None


def test_the_structure_factor_against_an_independent_expression():
    """An oracle arm: the same |F_⊥|², written out by hand from M-5's orbit.

    The forward model builds F_m from the *nuclear* operation subset with an
    axial matrix looked up per image, batches it over a flattened Laue orbit
    and segment-averages.  This writes the same quantity the way the equation
    reads — take M-5's ``site_orbit``, which returns the positions and the
    moments it carries and knows nothing of the forward model; convert each
    moment to Cartesian; sum the plane waves; project out the component along
    Q̂; average over the orbit members — and requires the two to agree.

    That is a check on the *plumbing*, which is where this rung's arithmetic
    could be wrong without any test of the physics noticing: the operation
    subset, the image-to-axial-matrix lookup, the batching, the segment
    average and the p² factor all have to be right for these to meet.
    """
    from rietx.crystallography.magnetic.operators import (
        moment_to_cartesian,
    )
    from rietx.crystallography.magnetic.scattering import (
        P_MAGNETIC_FM,
        reciprocal_cartesian_basis,
    )

    phase = _trirutile((2.4, 0.0, 0.0))
    model, _t, values, *_ = _compiled(phase)
    cp = model.phases[0]
    cell_now = _cell_of(values)
    got = np.asarray(model._magnetic_f2(0, np.asarray(cp.reflections.d),
                                        values, cell_now))

    group = phase.magnetic_symmetry.group()
    site = (0.0, 0.0, 0.333)
    positions, moments = group.site_orbit(site, phase.atoms[0].moment.values())
    assert len(positions) == 4                      # Cr on 4e
    bstar = reciprocal_cartesian_basis(cell_now)
    m_cart = np.array([moment_to_cartesian(m, cell_now) for m in moments])

    want = np.empty(len(cp.reflections))
    for i in range(len(cp.reflections)):
        s = 1.0 / (2.0 * cp.reflections.d[i])
        f = float(j0("Cr3+", s)) * np.exp(-0.3 * s * s)
        total = 0.0
        members = cp.mag_members[cp.mag_seg == i]
        for h in members:
            fm = np.zeros(3, dtype=complex)
            for pos, mc in zip(positions, m_cart, strict=True):
                fm = fm + mc * np.exp(2j * np.pi * float(h @ pos))
            fm = P_MAGNETIC_FM * f * fm
            q = bstar @ np.asarray(h, dtype=float)
            qhat = q / np.linalg.norm(q)
            perp = np.vdot(fm, fm).real - abs(np.dot(qhat, fm)) ** 2
            total += perp
        want[i] = total / len(members)

    assert np.allclose(got, want, rtol=1e-10, atol=1e-12), (
        got[:5].tolist(), want[:5].tolist())
    # and the quantity is not trivially zero everywhere
    assert float(got.max()) > 1.0
