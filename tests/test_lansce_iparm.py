"""The legacy LANSCE ``.iparm`` bolt-on, :func:`rietx.io.legacy.read_lansce_iparm`.

Synthetic files written column by column with the strict reader's own fixture
helpers (``tests/test_instrument_tof.py``), so a record here is laid out
exactly as a spec-legal one is and differs only by the deviation under test.
No real instrument file is vendored: the end-to-end case at the bottom builds
one file carrying all three deviations from the same helpers.  The slot
destinations these tests pin were measured against GSAS-II v5.8.2 run as a
black box; the run is recorded in the module docstring of
:mod:`rietx.io.legacy.lansce_iparm`, and GSAS-II is not needed to run them.
"""

from __future__ import annotations

import math

import pytest

from rietx.io.instrument_tof import (
    _INSTPRM_PROFILE,
    _PRCF_TO_PROFILE,
    read_gsas_tof_iparm,
)
from rietx.io.legacy import read_lansce_iparm
from rietx.io.legacy.lansce_iparm import (
    GSAS2_PRCF1_DESTINATIONS,
    LEGACY_PRCF1_SLOT_NAMES,
)
from rietx.model.tof_spectrum import incident_spectrum
from tests.test_instrument_tof import (
    TYPE1,
    bank,
    iparm,
    prcf,
    rec,
    spectrum_records,
    write,
)

#: A distinct number in each of the first seven slots; slot 8 is ``s1ec``, an
#: anisotropic term the strict body refuses non-zero, so it stays 0 here.
SENTINELS = [0.0011, 0.2222, 0.0333, 0.0044, 5.5, 666.0, 77.0, 0.0]
EXPECTED = {"alpha0": 0.0011, "alpha1": 0.2222, "beta0": 0.0333,
            "beta1": 0.0044, "sig0": 5.5, "sig1": 666.0, "sig2": 77.0}


def legacy_bank(b=1, slots=SENTINELS, spectrum=()):
    return bank(b, profile=prcf(b, 1, 1, slots), spectrum=spectrum)


def profile_values(instrument) -> dict[str, float]:
    p = instrument.source.profile_tof
    return {k: getattr(p, k).value for k in EXPECTED}


# ------------------------------------------------ deviation 1: the PRCF block
def test_an_eight_slot_type_one_block_lands_under_the_confirmed_names(tmp_path):
    """Each slot of the 8-coefficient block lands under the documented name of
    the same slot of the twelve; one ``GSAS_IPARM_LEGACY_LAYOUT`` per file,
    level info, naming every bank that carried the block."""
    notes = []
    banks = read_lansce_iparm(write(tmp_path, iparm(legacy_bank(1), legacy_bank(2))),
                              diagnostics=notes)
    assert sorted(banks) == [1, 2]
    for b in (1, 2):
        assert profile_values(banks[b]) == EXPECTED
        assert not any(getattr(banks[b].source.profile_tof, k).vary for k in EXPECTED)
    (legacy,) = [n for n in notes if n.code == "GSAS_IPARM_LEGACY_LAYOUT"]
    assert legacy.level == "info"
    assert legacy.where == ["bank 1", "bank 2", "PRCF1"]
    assert "slots 1, 5, 8 under no name" in legacy.message


def test_the_slot_names_agree_with_gsas2s_destinations_through_both_readers():
    """The oracle's table, crossed against the package's two readers: every slot
    GSAS-II places, it places under the ``.instprm`` key the strict reader maps
    onto the same ``ProfileTOF`` field as the slot's documented name; the three
    it places nowhere are ``alp-0``, ``sig-0`` and ``s1ec``."""
    assert LEGACY_PRCF1_SLOT_NAMES == ("alp-0", "alp-1", "bet-0", "bet-1",
                                       "sig-0", "sig-1", "sig-2", "s1ec")
    assert len(GSAS2_PRCF1_DESTINATIONS) == len(LEGACY_PRCF1_SLOT_NAMES)
    unplaced = []
    for name, dest in zip(LEGACY_PRCF1_SLOT_NAMES, GSAS2_PRCF1_DESTINATIONS):
        if dest is None:
            unplaced.append(name)
        else:
            assert _INSTPRM_PROFILE[dest] == _PRCF_TO_PROFILE[1][name], name
    assert unplaced == ["alp-0", "sig-0", "s1ec"]


def test_the_eighth_slot_is_s1ec_and_a_nonzero_one_is_refused(tmp_path):
    """Restated, slot 8 is ``s1ec``: the strict body's anisotropic-term refusal
    applies to it unchanged."""
    slots = SENTINELS[:7] + [0.5]
    with pytest.raises(ValueError, match="s1ec = 0.5 is non-zero"):
        read_lansce_iparm(write(tmp_path, iparm(legacy_bank(1, slots=slots))))


def test_a_legacy_block_in_any_other_record_shape_is_refused(tmp_path):
    """The observed layout is two coefficient records, PRCF11 and PRCF12; one
    record, or a third, is not that layout and is refused rather than
    restated."""
    short = prcf(1, 1, 1, SENTINELS[:4], ncof=8)
    with pytest.raises(ValueError, match=r"records \[1\]; the legacy LANSCE layout"):
        read_lansce_iparm(write(tmp_path, iparm(bank(1, profile=short))))
    long = prcf(1, 1, 1, SENTINELS + [0.0] * 4, ncof=8)
    with pytest.raises(ValueError, match=r"records \[1, 2, 3\]"):
        read_lansce_iparm(write(tmp_path, iparm(bank(1, profile=long))))


def test_a_legacy_block_keeps_the_strict_column_checks(tmp_path):
    """The restated records go through the strict body, so a coefficient that
    runs across a field boundary is refused exactly as it is in a documented
    file."""
    b = legacy_bank(1)
    i = next(k for k, line in enumerate(b) if line.startswith("INS  1PRCF12"))
    b[i] = rec("INS  1PRCF12", (13, f"{5.5:15.6E}"), (26, "666.000"))
    with pytest.raises(ValueError, match="runs across the boundary"):
        read_lansce_iparm(write(tmp_path, iparm(b)))


# --------------------------------------------- deviation 2: the fifth ICOFF pair
@pytest.mark.parametrize("itype", [1, 2])
def test_a_nonzero_fifth_pair_is_read_and_reported(tmp_path, itype):
    """The pair passes through as written, lands as P10/P11 and is reported
    once, naming the bank."""
    coeffs = [4.5, 787.5, 0.11, 895.4, 0.0045, 0.0, 0.0, 0.0, 0.0, 5.0, 1e-3]
    text = iparm(bank(1, spectrum=spectrum_records(1, itype, coeffs)))
    notes = []
    banks = read_lansce_iparm(write(tmp_path, text), diagnostics=notes)
    sp = banks[1].source.incident_spectrum
    assert sp.itype == itype
    assert [c.value for c in sp.coefficients] == coeffs
    (fifth,) = [n for n in notes if n.code == "GSAS_IPARM_LEGACY_LAYOUT"]
    assert fifth.level == "info" and fifth.where == ["bank 1", "ICOFF3"]
    assert f"bank 1 ITYP {itype}: P10 = 5.0, P11 = 0.001" in fifth.message
    # what the message says a fit does with the pair, checked against the
    # evaluator rather than against a copy of the sentence: the fifth term is
    # P10·exp(−P11·T⁵) with T in ms, and nothing else moves when it is added
    assert "a fit evaluates it as P10·exp(−P11·T⁵), T in ms" in fifth.message
    t_us = [2000.0, 5000.0, 10000.0]
    without = incident_spectrum(itype, coeffs[:9] + [0.0, 0.0], t_us)
    with_pair = incident_spectrum(itype, [c.value for c in sp.coefficients], t_us)
    for t, a, b in zip(t_us, without, with_pair):
        assert b - a == pytest.approx(5.0 * math.exp(-1e-3 * (t / 1000.0) ** 5),
                                      rel=1e-12)
    with pytest.raises(ValueError, match="prints no exponent for the fifth"):
        read_gsas_tof_iparm(write(tmp_path, text))


def test_a_file_with_a_fifth_pair_is_still_refused_for_any_other_reason(tmp_path):
    """Passing the pair through changes nothing else: a file wrong in some
    other way is refused by the strict body for that reason."""
    coeffs = [1.0] + [0.0] * 8 + [5.0, 1e-3]
    text = iparm(legacy_bank(1, spectrum=spectrum_records(1, 1, coeffs)), htype="PNCR")
    with pytest.raises(ValueError, match="HTYPE 'PNCR'"):
        read_lansce_iparm(write(tmp_path, text))


def test_the_chebyshev_types_slots_ten_and_eleven_are_not_a_deviation(tmp_path):
    """ITYP 3's P10/P11 are ordinary Chebyshev coefficients the strict reader
    reads, so the bolt-on hands the file to it unchanged and reports nothing."""
    coeffs = [0.7, -0.2, 0.05, 0.3, -0.1, 0.02, 0.01, -0.03, 0.004, 0.002,
              -0.001, 0.0005]
    path = write(tmp_path, iparm(bank(1, spectrum=spectrum_records(1, 3, coeffs))))
    notes = []
    legacy = read_lansce_iparm(path, diagnostics=notes)
    assert legacy[1].model_dump_json() == read_gsas_tof_iparm(path)[1].model_dump_json()
    assert not [n for n in notes if n.code == "GSAS_IPARM_LEGACY_LAYOUT"]


# ------------------------------------------ deviation 3: a BNKPAR field overrun
def overrun_bank(b=1, text="61.20", col=30):
    lines = bank(b)
    lines[1] = rec(f"INS {b:2d}BNKPAR", (13, f"{2.5:10.4f}"), (col, text))
    return lines


def test_a_bnkpar_value_across_a_boundary_is_token_read_and_reported(tmp_path):
    """TTHETA written one field too wide (columns 30-34, the legacy layout's
    shape): the strict reader refuses it, the bolt-on re-reads that record by
    tokens, takes 61.2, and says so with the record, its raw text and the
    value."""
    path = write(tmp_path, iparm(overrun_bank(1), bank(2)))
    with pytest.raises(ValueError, match="runs across the boundary between TTHETA"):
        read_gsas_tof_iparm(path)
    notes = []
    banks = read_lansce_iparm(path, diagnostics=notes)
    assert banks[1].source.two_theta_bank_deg == 61.2
    assert banks[1].source.l2_m == 2.5
    (legacy,) = [n for n in notes if n.code == "GSAS_IPARM_LEGACY_LAYOUT"]
    assert legacy.level == "info" and legacy.where == ["bank 1", "BNKPAR"]
    assert "record 4 ('INS  1BNKPAR    2.5000       61.20')" in legacy.message
    assert "DIST = 2.5, TTHETA = 61.2" in legacy.message
    # the rest of the file is what the strict reader makes of it
    strict_two = read_gsas_tof_iparm(write(tmp_path, iparm(bank(1))))[1]
    assert banks[2].source.profile_tof == strict_two.source.profile_tof


@pytest.mark.parametrize(("text", "col"), [("61.20", 21), ("61.2x0", 21),
                                           ("61.20 1 2 3 4 5 6", 30)])
def test_a_bnkpar_record_the_tokens_cannot_read_stays_the_strict_readers(
        tmp_path, text, col):
    """Two numbers run together, a non-number, or more tokens than BNKPAR has
    fields: the token read declines, and the strict reader's own column
    refusal is what the caller sees."""
    path = write(tmp_path, iparm(overrun_bank(1, text=text, col=col)))
    with pytest.raises(ValueError, match="runs across the boundary"):
        read_lansce_iparm(path)


def test_only_bnkpar_is_token_read(tmp_path):
    """An ICONS value across a boundary is not one of the three deviations:
    both readers refuse it with the strict message."""
    b = bank(1)
    b[0] = rec("INS  1 ICONS", (13, "   5123.45"), (23, "0 -1.23"))
    for reader in (read_gsas_tof_iparm, read_lansce_iparm):
        with pytest.raises(ValueError, match="runs across the boundary between DIFC"):
            reader(write(tmp_path, iparm(b)))


# ------------------------------------------------- pass-through and the opt-in
@pytest.mark.parametrize("profile", ["type3", "type1_12", "spectrum"])
def test_a_spec_legal_file_reads_identically_through_both_readers(tmp_path, profile):
    """Anything the strict reader accepts, the bolt-on hands to it: the same
    ``Instrument``s, serialised byte for byte, and the same diagnostics."""
    if profile == "type3":
        banks = [bank(1), bank(2)]
    elif profile == "type1_12":
        banks = [bank(1, profile=prcf(1, 1, 1, TYPE1))]
    else:
        coeffs = [4.5, 787.5, 0.11, 895.4, 0.0045, 1086.2, 5.2e-4, -1397.0, 3.4e-4]
        banks = [bank(1, spectrum=spectrum_records(1, 1, coeffs, esds=[0.1] * 9))]
    path = write(tmp_path, iparm(*banks))
    strict_notes, legacy_notes = [], []
    strict = read_gsas_tof_iparm(path, diagnostics=strict_notes)
    legacy = read_lansce_iparm(path, diagnostics=legacy_notes)
    assert strict.keys() == legacy.keys()
    for b in strict:
        assert legacy[b].model_dump_json() == strict[b].model_dump_json()
    assert [n.model_dump() for n in legacy_notes] == [n.model_dump() for n in strict_notes]


def test_without_the_bolt_on_the_strict_refusal_stands(tmp_path):
    """Off by default: the strict reader refuses the legacy block, and its one
    added sentence names the reader that accepts it."""
    with pytest.raises(ValueError, match="with 8 coefficients") as err:
        read_gsas_tof_iparm(write(tmp_path, iparm(legacy_bank(1))))
    assert str(err.value).endswith(
        "An 8-coefficient type-1 block is the legacy LANSCE layout, read on "
        "request by rietx.io.legacy.read_lansce_iparm")


# ------------------------------------------------ all three in one file
def test_one_file_carrying_all_three_deviations_reads_end_to_end(tmp_path):
    """A synthetic four-bank file in the legacy layout: every bank's PRCF set 1
    is the 8-slot block, banks 1 and 2 carry a non-zero fifth ICOFF pair, and
    bank 1's TTHETA runs across the field boundary.  Refused by the strict
    reader, read by the bolt-on, and each deviation reported once by its
    role."""
    fifth = [4.5, 787.5, 0.11, 895.4, 0.0045, 0.0, 0.0, 0.0, 0.0, -2.0e3, 5.0e-5]
    banks_text = []
    for b in (1, 2, 3, 4):
        lines = legacy_bank(b, spectrum=spectrum_records(b, 1, fifth)
                            if b in (1, 2) else ())
        if b == 1:
            lines[1] = rec("INS  1BNKPAR", (13, f"{2.5:10.4f}"), (30, "61.20"))
        banks_text.append(lines)
    path = write(tmp_path, iparm(*banks_text))
    with pytest.raises(ValueError, match=r"'61\.20' in columns 30-34"):
        read_gsas_tof_iparm(path)
    notes = []
    banks = read_lansce_iparm(path, diagnostics=notes)
    assert sorted(banks) == [1, 2, 3, 4]
    assert banks[1].source.two_theta_bank_deg == 61.2
    two = banks[2].source.incident_spectrum
    assert two.itype == 1
    assert [c.value for c in two.coefficients][9:] == [-2.0e3, 5.0e-5]
    assert all(profile_values(banks[b]) == EXPECTED for b in banks)
    legacy = {n.where[-1]: n for n in notes if n.code == "GSAS_IPARM_LEGACY_LAYOUT"}
    assert sorted(legacy) == ["BNKPAR", "ICOFF3", "PRCF1"]
    assert all(n.level == "info" for n in legacy.values())
    assert legacy["BNKPAR"].where == ["bank 1", "BNKPAR"]
    assert "TTHETA = 61.2" in legacy["BNKPAR"].message
    assert legacy["PRCF1"].where == ["bank 1", "bank 2", "bank 3", "bank 4", "PRCF1"]
    assert legacy["ICOFF3"].where == ["bank 1", "bank 2", "ICOFF3"]
