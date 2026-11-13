"""The transcription of Hill (1992) Tables 7, 8 and 9 checks itself (WP-1943).

``tests/data/hill1992_pbso4_round_robin.json`` carries the IUCr CPD round
robin's published reference values — the participants' range, weighted mean and
σ_ext for every PbSO₄ parameter — which ``test_acceptance_pbso4_round_robin.py``
asserts a fit against.  A wrong digit there would move a gate without anyone
seeing it, so the transcription is held to relations **the paper itself states**,
each with a planted error showing the check can fail
(memory ``controls-need-a-positive-arm``; the digitisation protocol's § 3):

1. **Every weighted mean lies inside its own range** (Table 7, both arms;
   Table 9's neutron rows).  A mean outside the span of the values it averages
   is a misread digit or a shifted row.
2. **Table 7's parenthesised esd is Table 8's σ_ext rounded to the mean's last
   printed digit.**  Table 8 prints σ_ext to two or three figures on its own
   scale (×10⁶ Å for the cell, ×10⁶ for Pb, ×10⁵ for S and O, ×10³ Å² for B);
   Table 7 prints the same number as an esd in the mean's last place.  Two
   tables, one quantity, so a slip in either shows.
3. **ℜ = (σ_ext/σ_int)²** (Hill eqs 2-4, pp. 601-603), within what Table 8's
   rounding allows: both σ columns are printed as integers, ±0.5 of their unit.
4. **The row counts are the page's**: 19 rows in Table 7 (a, b, c, eleven
   coordinates, five B), 22 in Table 9.

An independent lineage for the numbers themselves does not exist in this repo
(the single-crystal paper, Miyake et al. 1978, is not held), so (5) bounds the
transcription against GSAS-II's own converged fit of the same two patterns,
``tests/data/gsas2_pbso4.gpx``: it cannot prove a value, but it catches a
decimal slip or a swapped row, which is the error shape a scan produces.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"
FIXTURE = DATA / "hill1992_pbso4_round_robin.json"


@pytest.fixture(scope="module")
def tables():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _means_outside_range(doc) -> list[str]:
    bad = []
    for row in doc["table7"]:
        for arm in ("xray", "neutron"):
            lo, hi = row[arm]["range"]
            if not lo <= row[arm]["mean"] <= hi:
                bad.append(f"T7 {row['key']} {arm}")
    for row in doc["table9"]:
        lo, hi = row["neutron"]["range"]
        if not lo <= row["neutron"]["mean"] <= hi:
            bad.append(f"T9 {row['atom']} b{row['ij']}")
    return bad


def _esd_disagreements(doc) -> list[str]:
    """Table 7's ``(n)`` against Table 8's σ_ext at the mean's last digit."""
    bad = []
    for row in doc["table7"]:
        for arm in ("xray", "neutron"):
            printed = row[arm]["mean_as_printed"]          # e.g. "0.06490 (17)"
            value, esd = printed.split(" (")
            esd = int(esd.rstrip(")"))
            decimals = len(value.split(".")[1])
            unit = 10.0 ** -decimals
            sext = row[arm]["sigma_ext"]
            # Table 8 is the more precise; Table 7 rounds it to its own unit,
            # half-up or half-even, so allow the half-unit either way
            if abs(sext / unit - esd) > 0.5 + 1e-9:
                bad.append(f"{row['key']} {arm}: {printed} vs σ_ext {sext:g}")
    return bad


def _variance_ratio_disagreements(doc) -> list[str]:
    """ℜ = (σ_ext/σ_int)² with both σ printed to ±½ of Table 8's unit."""
    def unit(key: str) -> float:
        if key.endswith("biso"):
            return 1e-3
        return 1e-6 if key.startswith(("cell.", "Pb.")) else 1e-5

    bad = []
    rows = [(f"T7 {r['key']} {arm}", r[arm], unit(r["key"]))
            for r in doc["table7"] for arm in ("xray", "neutron")]
    rows += [(f"T9 {r['atom']} b{r['ij']}", r["neutron"], 1e-5) for r in doc["table9"]]
    for name, entry, unit in rows:
        sext, sint, ratio = entry["sigma_ext"], entry["sigma_int"], entry["variance_ratio"]
        lo = ((sext - 0.5 * unit) / (sint + 0.5 * unit)) ** 2
        hi = ((sext + 0.5 * unit) / (sint - 0.5 * unit)) ** 2
        # ℜ itself is printed to 2-3 figures: half its last place either way
        slack = 0.05 if ratio < 100 else 0.5
        if not lo - slack <= ratio <= hi + slack:
            bad.append(f"{name}: ℜ {ratio} outside [{lo:.3g}, {hi:.3g}]")
    return bad


def test_the_row_counts_are_the_pages(tables):
    assert len(tables["table7"]) == 19
    assert len(tables["table9"]) == 22
    assert [r["key"] for r in tables["table7"]][:3] == ["cell.a", "cell.b", "cell.c"]
    # Table 9 prints X-ray ranges for the Pb and S rows only
    assert {r["atom"] for r in tables["table9"] if r["xray_range"]} == {"Pb", "S"}


def test_every_mean_lies_inside_its_range(tables):
    assert _means_outside_range(tables) == []


def test_table7_esds_are_table8s_sigma_ext(tables):
    assert _esd_disagreements(tables) == []


def test_the_variance_ratio_is_the_square_of_the_esd_ratio(tables):
    assert _variance_ratio_disagreements(tables) == []


@pytest.mark.parametrize("plant,check", [
    (lambda d: d["table7"][7]["neutron"].__setitem__("mean", 0.98057),
     _means_outside_range),                   # O1 x, one digit misread
    (lambda d: d["table9"][13]["neutron"].__setitem__("mean", 0.0128),
     _means_outside_range),                   # O2 β22, 2↔8 confusion
    (lambda d: d["table7"][5]["neutron"].__setitem__("sigma_ext", 71e-5),
     _esd_disagreements),                     # S x, Table 8's 17 read as 71
    (lambda d: d["table7"][0]["xray"].__setitem__("mean_as_printed", "8.4804 (9)"),
     _esd_disagreements),                     # a, Table 7's 4 read as 9
    (lambda d: d["table7"][14]["xray"].__setitem__("variance_ratio", 48.7),
     _variance_ratio_disagreements),          # B Pb, a decimal slip
    (lambda d: d["table9"][11]["neutron"].__setitem__("sigma_int", 3e-5),
     _variance_ratio_disagreements),          # O1 β13, 9 read as 3
])
def test_each_check_catches_a_planted_error(tables, plant, check):
    doc = copy.deepcopy(tables)
    assert check(doc) == []
    plant(doc)
    assert check(doc) != []


def test_the_transcription_sits_near_gsas2s_own_fit_of_the_same_data(tables):
    """A gross-slip bound, not a proof: GSAS-II's converged joint fit of the two
    round-robin patterns (the vendored tutorial project) lands within 0.004 of
    every neutron mean coordinate and within 0.3 % of every cell edge — a
    decimal slip or a swapped row in the transcription moves by far more."""
    from rietx.io.projects.gsas2 import read_gsas2_gpx, to_structure

    phase = to_structure(read_gsas2_gpx(DATA / "gsas2_pbso4.gpx")).phases[0]
    labels = {"Pb": "Pb1", "S": "S2", "O1": "O3", "O2": "O4", "O3": "O5"}
    atoms = {a.label: a for a in phase.atoms}
    for row in tables["table7"]:
        key, mean = row["key"], row["neutron"]["mean"]
        if key.startswith("cell."):
            got = getattr(phase.cell, key.split(".")[1]).value
            assert math.isclose(got, mean, rel_tol=3e-3), (key, got, mean)
        elif not key.endswith("biso"):
            atom, axis = key.split(".")
            got = getattr(atoms[labels[atom]], axis).value
            # a lattice translation is the same site: GSAS-II stores O1 at x − 1
            assert abs((got - mean + 0.5) % 1.0 - 0.5) < 4e-3, (key, got, mean)
