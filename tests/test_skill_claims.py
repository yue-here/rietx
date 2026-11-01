"""The skill body's numbers and formulas, each held to what it quotes (WP-1907).

`tests/test_skill.py` pins the skill's *names*: a renamed attribute or a
vanished export fails there.  Nothing pinned a *value*.  WP-1904 checked the
body by hand and found a width seed contradicting the package's Caglioti form;
this file's first pass found two more — rule 14 called ``chi2_ratio`` "loser
over winner" where the package orders it held over partner (so a held winner
reads below 1 and an agent comparing it to 1.10 would call a settled pair
unresolved), and rule 7 said "0.98 or more" for a guard that fires strictly
above.

Two halves, the manual's partition (`tests/test_manual_api.py`) one document
over:

- **`CLAIMS`** maps a fragment of the body to a check against the package
  attribute, function or documented contract it quotes.  The fragment must
  still be in the body, so a rewrite that drops a claim drops its row.
- **Every number in the body is a claim or declared not one.**  A number
  outside every fragment of `CLAIMS` and `NOT_CLAIMS` fails, so a new constant
  typed into the body is classified the day it lands.  Section and rule
  references, headings and rule numbers are stripped first, and the fenced
  worked default is `test_skill.py`'s (held line for line to
  `examples/skill_worked_default.py`, which runs).

A formula with no digit in it (`N/f²`, `Γ_G² = U·tan²θ + V·tanθ + W`) cannot
be found by the scan, so it is a `CLAIMS` row by hand; the scan guarantees
only that no *number* escapes.
"""
from __future__ import annotations

import inspect
import math
import re
import tomllib
from collections.abc import Callable

import numpy as np
import pytest

import rietx as rx
from tests.skill_caps import ROOT, SKILL

TEXT = SKILL.read_text(encoding="utf-8")


# ------------------------------------------------------------------ the checks
def _python_floor():
    spec = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert spec["project"]["requires-python"] == ">=3.11"


def _anodes():
    from rietx.schemas.instrument import _RADIATIONS

    anodes = ("CrKa", "FeKa", "CoKa", "CuKa", "MoKa", "AgKa")
    assert set(_RADIATIONS) == {*anodes, *(a + "1" for a in anodes)}
    for anode in anodes:
        lines = rx.Instrument.bragg_brentano(radiation=anode + "1").source.lines
        assert len(lines) == 1, f"{anode}1 is not a single Kα1 line"


def _caglioti():
    from rietx.model.profiles.caglioti import gaussian_fwhm

    theta = np.array([5.0, 20.0, 45.0, 70.0])
    u, v, w = 0.02, -0.01, 0.004
    t = np.tan(np.radians(theta))
    assert gaussian_fwhm(theta, u, v, w) == pytest.approx(
        np.sqrt(u * t**2 + v * t + w), rel=1e-14)


def _w_default():
    from rietx.schemas.instrument import TCHZ_DEFAULTS

    assert TCHZ_DEFAULTS["w"] == 1e-3
    profile = rx.Instrument.bragg_brentano(radiation="CuKa").profile
    assert profile.w.value == 1e-3
    assert round(math.sqrt(profile.w.value), 2) == 0.03   # the "0.03° line"


def _width_seed():
    """W = (0.6·H)² and X = 0.6·H are the low-angle Gaussian and Lorentzian
    FWHMs, and the package's TCH combination of the two lands near H."""
    from rietx.model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
    from rietx.model.profiles.pseudovoigt import tch_gamma_eta

    h = 0.2
    theta0 = np.array([1e-9])
    assert gaussian_fwhm(theta0, 0.0, 0.0, (0.6 * h) ** 2)[0] == pytest.approx(0.6 * h)
    assert lorentzian_fwhm(theta0, 0.6 * h, 0.0)[0] == pytest.approx(0.6 * h)
    gamma, _ = tch_gamma_eta(np.array([0.6 * h]), np.array([0.6 * h]))
    assert gamma[0] == pytest.approx(h, rel=0.05)          # measured 0.981·H


def _size_strain_signatures():
    from rietx.model.profiles.caglioti import lorentzian_fwhm

    theta = np.array([10.0, 30.0, 60.0])
    c, t = np.cos(np.radians(theta)), np.tan(np.radians(theta))
    assert lorentzian_fwhm(theta, 0.1, 0.0) * c == pytest.approx(0.1)
    assert lorentzian_fwhm(theta, 0.0, 0.1) / t == pytest.approx(0.1)


def _pattern():
    tt = np.linspace(10.0, 80.0, 1400)
    return rx.PatternData(two_theta=tt, intensity=200.0 + 50.0 * np.exp(-((tt - 40) / 0.1) ** 2))


def _background_zero():
    data = _pattern()
    assert inspect.signature(rx.auto_background).parameters["kind"].default == "pspline"
    for kind in ("chebyshev", "pspline"):
        bg = rx.auto_background(data, kind=kind).background
        assert [c.value for c in bg.coefficients] == [0.0] * len(bg.coefficients), kind


def _correlation_guard():
    """Defaults only: the comparison is strict (``abs(ρ) > guard`` in
    `strategy/staged.py` and `multi.py`), which is why the body says
    "above"; a stub of the guard's inputs would test the stub."""
    from rietx.schemas.plan import PlanSpec

    assert rx.RefinementPlan.mccusker_default().correlation_guard == 0.98
    assert PlanSpec().correlation_guard == 0.98


def _complementary_occupancy():
    from tests.test_refine_synthetic import perturbed_models

    ref = rx.Refinement(*perturbed_models())
    ref.set_values({"phases.0.atoms.0.occ": 0.7})
    ref.tie("phases.0.atoms.1.occ", "phases.0.atoms.0.occ", scale=-1, offset=1)
    assert ref.structure.phases[0].atoms[1].occ.value == pytest.approx(0.3)


def _shift_band():
    from rietx.optimize.statistics import MAX_SHIFT_CONVERGED

    assert MAX_SHIFT_CONVERGED == 0.1


def _rival_ratio():
    """The orientation is measured on a real fit by
    `test_fitreport_layers.test_chi2_ratio_orientation_is_held_over_partner`;
    here the schema's statement of it and the band's value."""
    from rietx.report.schemas import RivalComparison

    assert rx.report.RIVAL_DECISIVE_MIN_CHI2_RATIO == 1.10
    assert "``rivals[0].chi2 / rivals[1].chi2``" in RivalComparison.__doc__
    assert "index 0 frees the finding's **held** candidate" in RivalComparison.__doc__


def _lebail_gap_orientation():
    from rietx.report import layer0

    assert "ratio=float(rwp_rietveld / max(rwp_lb" in inspect.getsource(layer0)


def _effective_sample_size():
    from rietx.optimize.statistics import effective_sample_size

    assert effective_sample_size(1000, 2.0) == pytest.approx(250.0)


#: fragment of the body -> the check holding it to the package.
CLAIMS: dict[str, Callable[[], None]] = {
    "Python 3.11+": _python_floor,
    '`"CrKa"`, `"FeKa"`, `"CoKa"`, `"CuKa"`, `"MoKa"`, `"AgKa"`, suffix `1` for Kα1 only':
        _anodes,
    "Γ_G² = U·tan²θ + V·tanθ + W": _caglioti,
    "Its default, 1e-3 deg², is a 0.03° synchrotron line": _w_default,
    "Seed `W ≈ (0.6·H)²`, `X ≈ 0.6·H`": _width_seed,
    "Gaussian and Lorentzian halves of 0.6·H combine to about H": _width_seed,
    "| size · strain | 1/cosθ · tanθ |": _size_strain_signatures,
    "or the default P-spline": _background_zero,
    "Unseeded, every coefficient is 0.0": _background_zero,
    "Above a correlation of 0.98 (`HIGH_CORRELATION`)": _correlation_guard,
    "(`occ₁ = 1 − occ₀` is `scale=-1, offset=1`)": _complementary_occupancy,
    "Above 0.1 under `converged`": _shift_band,
    "If max(r, 1/r) of its `chi2_ratio` r (held over partner) is at least "
    "`rx.report.RIVAL_DECISIVE_MIN_CHI2_RATIO` (1.10)": _rival_ratio,
    "Rietveld Rwp over Le Bail Rwp: ≫ 1": _lebail_gap_orientation,
    "ΔBIC at N/f² with f = `esd_inflation`": _effective_sample_size,
}

#: fragment of the body -> why its number is not the package's to pin.
NOT_CLAIMS: dict[str, str] = {
    "The starting cell is within ~1 %": "a rule of thumb for the fixed peak windows; no package constant",
    "The starting width is within ×2": "a tolerance the agent applies; no package constant",
    "McCusker et al. 1999, *J. Appl. Cryst.* **32**, 36": "a citation",
    "`lebail_passes` (say 8)": "a suggested value, not a default (the default is 1)",
    "plan.lebail_passes = 8": "the same suggested value, in code",
    "no occupancy above 1": "physics, not a package setting",
}


# ------------------------------------------------------------------ the scan
#: Stripped (blanked to the same length, so positions survive) before the
#: number scan: references to sections and rules, heading and rule numbers,
#: the fenced worked default, the frontmatter's version (`test_skill.py`'s),
#: and notation.
_NOT_NUMBERS = [
    re.compile(r"```.*?```", re.S),
    re.compile(r"^  version: .*$", re.M),
    re.compile(r"^#+ \d+[a-z]?\.", re.M),
    re.compile(r"^\d+\. ", re.M),
    re.compile(r"§\s?(?:rules?\s)?\d+[a-z]?(?:[./-]\d*[a-z]?)*"),
    re.compile(r"\brules?\s\d+(?:-\d+)?"),
    re.compile(r"Layer \d(?:/\d)*"),
    re.compile(r"2θ"),
]
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:e-?\d+)?")


def _unclassified(text: str, fragments: list[str]) -> list[str]:
    blank = text
    for pattern in _NOT_NUMBERS:
        blank = pattern.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), blank)
    covered = np.zeros(len(text), dtype=bool)
    for fragment in fragments:
        for m in re.finditer(re.escape(fragment), text):
            covered[m.start():m.end()] = True
    return [f"{text[max(0, m.start() - 40):m.end() + 20]!r}"
            for m in _NUMBER.finditer(blank) if not covered[m.start():m.end()].all()]


# ------------------------------------------------------------------ the tests
@pytest.mark.parametrize("fragment", [*CLAIMS, *NOT_CLAIMS])
def test_every_classified_fragment_is_still_in_the_body(fragment: str):
    assert fragment in TEXT, (
        f"{fragment!r} is no longer in SKILL.md: re-quote the row from the "
        "body's new text, or delete it if the claim went")


@pytest.mark.parametrize("fragment", list(CLAIMS))
def test_every_claim_holds_against_the_package(fragment: str):
    CLAIMS[fragment]()


def test_every_number_in_the_body_is_a_claim_or_declared_not_one():
    stray = _unclassified(TEXT, [*CLAIMS, *NOT_CLAIMS])
    assert not stray, (
        "a number in SKILL.md is neither a CLAIMS row (checked against the "
        "package) nor a NOT_CLAIMS row (with its reason):\n" + "\n".join(stray))


def test_the_scan_finds_a_new_number_and_skips_a_reference():
    fragments = [*CLAIMS, *NOT_CLAIMS]
    assert _unclassified(TEXT + "\nSet the window to 7.5 FWHM.\n", fragments)
    assert not _unclassified(TEXT + "\nSee §8.11 and rule 16.\n", fragments)
