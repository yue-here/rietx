"""WP-1326 acceptance: the satellite arm found blind, its null, and a k = 0 case.

Three measurements, each with the arm that could fail written down first:

* **A synthetic k = (0, 0, ½) satellite set, under Poisson noise.**  A nuclear
  model that knows nothing of any k is fitted to a pattern carrying intensity
  at the satellites of (0, 0, ½); the report arm must rank (0, 0, ½) first.
  If a noise peak could out-score the true k, or the runner-up tied it, the
  ranking would mean nothing.
* **The null: the same fit with no satellite intensity in the data.**  The arm
  must abstain — no unexplained peak, no candidate scored.  Noise is what
  makes this a control: on a noiseless pattern a converged fit leaves no
  residual at all and the null passes by construction.
* **Cr₂WO₆, a published k = 0 structure** (GSAS-II tutorial *Magnetic-II*,
  HB-2A, 4 K and 150 K; vendored per ``tests/data/README.md``).  The 4 K
  pattern against the nuclear model refined from it must show the k = 0
  signature — residual peaks on reciprocal-lattice points the nuclear
  structure factor forbids — and name k = 0; the 150 K pattern, above the
  ordering temperature, must show none.  What this case does **not** assert
  is the WP's "no candidate scores": measured, the best zone-boundary
  candidates index 2 of the 6 leftover 4 K peaks, and 2 of 5 on the 150 K
  null — the same chance level, because the ranking has no chance baseline.
  That is a design question for the arm, not a threshold to tune here.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable

# ====================================================== synthetic, under noise

LAMBDA = 2.4067
CELL = (4.0, 5.0, 6.0, 90.0, 90.0, 90.0)


def _phase(k=None) -> rx.Phase:
    P = rx.Parameter
    a, b, c, al, be, ga = CELL
    return rx.Phase(
        name="Fe", space_group="P m m m",
        cell=rx.Cell(a=P(value=a), b=P(value=b), c=P(value=c),
                     alpha=P(value=al), beta=P(value=be), gamma=P(value=ga)),
        atoms=[rx.Atom(label="Fe", species="Fe", x=P(value=0.0),
                       y=P(value=0.0), z=P(value=0.0), biso=P(value=0.4))],
        scale=P(value=1.0), propagation_vector=k)


def _pattern(y=None) -> rx.PatternData:
    tt = np.arange(10.0, 110.0, 0.02)
    if y is None:
        y = np.ones_like(tt)
    return rx.PatternData(two_theta=tt.tolist(), intensity=np.asarray(y).tolist())


def _values(structure, instrument):
    table = ParameterTable(structure, instrument)
    return table.decode(table.x0())


@pytest.fixture(scope="module")
def synthetic():
    """Nuclear and satellite-only profiles, drawn through the model itself."""
    instrument = rx.Instrument.constant_wavelength_neutron(LAMBDA, fwhm_deg=0.3)
    plain = rx.Structure(phases=[_phase(None)])
    with_k = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    nuclear = np.asarray(compile_model(plain, instrument, _pattern()).evaluate(
        _values(plain, instrument)), dtype=np.float64)
    seed = compile_model(with_k, instrument, _pattern(), mode="lebail")
    cp = seed.phases[0]
    cp.hkl_intensity = np.where(cp.reflections.is_satellite, 900.0, 0.0)
    magnetic = np.asarray(seed.evaluate(_values(with_k, instrument)),
                          dtype=np.float64)
    return instrument, plain, nuclear, magnetic


def _arm(instrument, plain, y):
    ref = rx.Refinement(plain, instrument, history=False)
    ref.fit(_pattern(y), plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"])]))
    arms = ref.report().satellites
    assert len(arms) == 1
    return arms[0]


@pytest.mark.xdist_group("satellites-synthetic")
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_a_k_00half_satellite_set_is_found_blind_under_noise(synthetic, seed):
    """Positive arm: (0, 0, ½) ranks first and the runner-up is far behind.

    Measured over seeds 0-9: 21-22 of 31-41 unexplained peaks matched by
    (0, 0, ½), the runner-up at most 5.  The extra unexplained peaks are noise
    at the report's 5σ default and are what the true k must beat.
    """
    instrument, plain, nuclear, magnetic = synthetic
    rng = np.random.default_rng(seed)
    arm = _arm(instrument, plain,
               rng.poisson(nuclear + magnetic + 200.0).astype(float))
    top, runner_up = arm.candidates[0], arm.candidates[1]
    assert top.vector == "(0, 0, 1/2)", [(c.vector, c.matched)
                                         for c in arm.candidates]
    assert top.matched >= 20, arm.note
    assert runner_up.matched * 3 < top.matched, arm.note
    # P m m m forbids nothing, so no peak can be the k = 0 signature here
    assert arm.excess_on_absent_lattice_lines == 0


@pytest.mark.xdist_group("satellites-synthetic")
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_the_null_abstains_under_noise(synthetic, seed):
    """Null arm: no satellite intensity, so nothing unexplained and nothing scored."""
    instrument, plain, nuclear, _magnetic = synthetic
    rng = np.random.default_rng(seed)
    arm = _arm(instrument, plain, rng.poisson(nuclear + 200.0).astype(float))
    assert arm.n_unexplained == 0, arm.note
    assert all(c.matched == 0 for c in arm.candidates), arm.note
    assert "nothing to index" in arm.note


# ============================================================ Cr₂WO₆, k = 0
#
# Real data, so ``slow``; and the nuclear fits are the session's
# (``conftest.cr2wo6_nuclear``), the same two files from the same trirutile
# start that WP-1327's moment acceptance refines, so the test joins that
# fixture's group rather than fitting them a second time.


@pytest.fixture(scope="module")
def cr2wo6(cr2wo6_nuclear):
    return (cr2wo6_nuclear["ref4"].report().satellites[0],
            cr2wo6_nuclear["ref150"].report().satellites[0])


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-cr2wo6")
def test_cr2wo6_4k_shows_the_k_zero_signature_and_150k_does_not(cr2wo6):
    """The positive k = 0 statement at 4 K, and its absence above T_N.

    Measured: 4 residual peaks on forbidden reciprocal-lattice points at 4 K
    (the (0 0 1) and (1 0 2) regions near 15.8° and 44.7° among them), 0 at
    150 K.  The 150 K arm is the control: a nuclear model refined on a pattern
    with no magnetic order must put no residual on a systematic absence.
    """
    arm4, arm150 = cr2wo6
    assert arm4.radiation == "neutron"
    assert arm4.excess_on_absent_lattice_lines >= 2, arm4.note
    assert "k = 0" in arm4.note
    assert arm150.excess_on_absent_lattice_lines == 0, arm150.note
    # the chance-level best at 150 K is named with what judges it
    if arm150.candidates and arm150.candidates[0].matched:
        assert "runner-up" in arm150.note, arm150.note
        assert "satellite position(s) in range" in arm150.note
