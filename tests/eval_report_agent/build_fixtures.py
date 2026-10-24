"""Build the round-3 eval episode fixtures and their scorer-side truth tree.

Protocol 2.0 (WP-1064): every expected answer is a **measurement made before
registration** (PROTOCOL.md § Episodes carries the rows; the landing states
are pinned by ``test_landing_states.py``).  Nine episodes in four dataset
groups, each group built only when asked for:

- synthetic (``E1``, ``E8p``, ``J1P``/``J1S``) — WP-1052's ``_truth()`` and
  the WP-1057 pore proxy, cheap;
- real SRM 660c (``N1``, ``C1``, ``R2``) — cost one ~1.5 s baseline fit;
- real 11-BM NAC (``W1``) — 59.5k channels, so a multi-MB ``episode.json``
  and ~1.5 s fits; no fit at build;
- real IUCr CPD qarr (``W2``) — the Cu Kα doublet data under a deliberately
  single-line source declaration; no fit at build.

Each episode dir holds the fixed request core (``episode.json``:
task/structure/instrument/pattern, pydantic round-trip by design) and the
prompt (``prompt.md``).  The condition marker is a **sibling of the episode
dir** (``<eid>.condition.json``), not a member: the workspace must carry no
condition bit, or an ``ls`` tells an ``off`` agent it is in a withholding
experiment (the round-2 leak, PROTOCOL.md 2.0 § Conditions).  Ground truth —
planted path, tolerance, expected verdict, the registered ``next_action``
set, the declared deliverable — goes to a **separate** tree the agent is
never pointed at.

Usage::

    python -m tests.eval_report_agent.build_fixtures \
        --episodes DIR --truth DIR --condition report --only N1 C1 W1 W2
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import rietx as rx
from tests.eval_report_agent.scorer import NEXT_ACTIONS, VERDICTS
from tests.test_fitreport_layers import _pore_proxy_data, _truth

REPO_ROOT = Path(__file__).resolve().parents[2]

#: versions the whole runner protocol (prompt text, overlay contract, answer
#: schema, scoring rules) — bump on any change that alters comparability.
#: 1.0 (WP-1053): the 48-run pilot.  1.1 (WP-1058/1059): trajectory delivery,
#: the delivery/instruction condition split, the real pair R1/R2.
#: 2.0 (WP-1064): episode set, answer schema, scoring rules and condition
#: axis all move at once — measured epistemic rows, ``next_action`` +
#: ``assumption_wrong``, the python arm, the condition marker out of the
#: workspace — so a 2.0 run is poolable with nothing earlier, ``off``
#: included (the v2 answer contract is in every prompt).
#: 2.1 (WP-1065): prompt content only — ``assumption_wrong`` stops naming
#: refinable geometry (round 3's ``off__sonnet``/C1 recovered the knocked
#: displacement and then answered ``assumption_wrong``, invited by "the
#: geometry" in the glossary) and gains the explicit exclusion; the package
#: under test carries THRESHOLDS_VERSION 0.9's license sentence.  Episode
#: fixtures, answer schema and scorer v2 are unchanged, so landing-state
#: bands hold — but prompts changed, so a 2.1 cell pools with nothing at 2.0.
#: 2.2 (WP-1107): answer contract v3 — ``report_with_caveat`` leaves
#: ``next_action`` (the WP-1107 archaeology: the one delivery-stance token in
#: a remedial vocabulary, an unfalsifiable hedge sink on real data) and the
#: unscored ``caveats`` list takes the delivery stance; the
#: ``assumption_wrong`` exclusion names both target verdicts with equal
#: weight (2.1's "converge it, or say the data cannot" is the N=1 suspect
#: for all four ``off`` verdicts flipping to ``converged``); two shim
#: projections land (``license_placement``, ``include_execution``, both
#: marker-declared).  Episode fixtures unchanged, landing states re-measured
#: 2026-08-19; contract + prompts changed, so no 2.2 cell pools with 2.1
#: 2.3 (WP-2037 Decision 3): the condition axis is the package build — two
#: non-editable installs, each workspace carrying its build's skill — and
#: cells launch as ``claude -p`` (``launch.py``) rather than Workflow
#: agents, so user-level skills stay out.  Prompt, contract, episodes and
#: scorer unchanged; a 2.3 cell pools with no earlier python cell, the
#: launch route and the skill both having moved
PROTOCOL_VERSION = "2.3"

#: shim-enforced hard stop on refinement calls per episode — a runaway guard
#: (tests/CLAUDE.md), never a timer; the prompt advertises 6
MAX_CALLS = 8

#: the four dataset groups; a selection pays only for the groups it names
SYNTHETIC_IDS = ("E1", "E8p", "J1P", "J1S")
SRM_IDS = ("N1", "C1", "R2")
NAC_IDS = ("W1",)
QARR_IDS = ("W2",)
#: protocol order: the core matrix rows first (PROTOCOL.md § The matrix)
EPISODE_IDS = ("N1", "C1", "W1", "W2", "E8p", "J1P", "J1S", "E1", "R2")

#: N1's window, applied to the pattern arrays in ``episode.json`` itself —
#: nothing to widen into; the overlay can only narrow.  Measured 2026-08-13
#: on this window: the zero/displacement rivals tie at χ² ratio 1.0075
#: (registered band [0.99, 1.01]) and the exchange clause fires at the
#: default-plan landing state and both single-rival states
N1_MAX_TWO_THETA = 56.0

#: C1's restored tolerance: the swap state passes (measured recovery 1.4e-07
#: from truth), the ridge fails (disp −0.1202, off by 0.0401) and the
#: zero-absorber state fails (never freed) — the tolerance is what keeps a
#: zero-absorbed ``converged`` from passing (PROTOCOL.md § Episodes)
C1_DISP_TOL = 0.005

#: W2's specimen: the single-phase corundum pattern (doubles as the SRM 676a
#: cell anchor, tests/data/README.md)
W2_SAMPLE = "corundum"


@dataclass(frozen=True)
class Condition:
    """One cell of the JSON-arm condition axis.

    Every switch is enforced by the shim rather than by the prompt:
    ``report`` is the converged-state FitReport and ``trajectory`` is
    WP-1058's per-stage delivery of it.  ``sections`` names the
    skill excerpts the prompt quotes.  The 1.1 instruction axis
    (§9: ``prompt``/``both``) is retired — round 2 measured zero bootstrap
    calls under it, so no 2.0 prompt quotes §9.

    The 2.2 projections (PROTOCOL.md 2.2) are response-shape, not
    withholding: ``license_placement`` says where the identifiability clause
    sits (``"summary"`` — the status quo — or ``"statistics"``, injected as
    ``result.statistics["identifiability_clause"]`` and excised from the
    summary), and ``execution`` says whether delivered actions keep their
    ``execution`` field.  Both are inert when the report is withheld.
    """

    report: bool
    trajectory: bool
    sections: tuple[str, ...]
    license_placement: str = "summary"
    execution: bool = True


#: the JSON-arm matrix (2.0 base + the 2.2 projection arms).  The python arm
#: is not a row here: it has no shim, no condition marker and its own
#: workspace builder (``python_arm``)
CONDITIONS: dict[str, Condition] = {
    "off": Condition(report=False, trajectory=False, sections=()),
    "report": Condition(report=True, trajectory=False, sections=("5.", "6.")),
    "surface": Condition(report=True, trajectory=True, sections=("5.", "6.")),
    # 2.2 placement arm: same delivery as ``report``, the clause moved beside
    # the statistics keys the miners proved agents grep (PROTOCOL.md 2.2)
    "report_stat": Condition(report=True, trajectory=False,
                             sections=("5.", "6."),
                             license_placement="statistics"),
    # 2.2 execution arm: same delivery as ``report``, the WP-1106
    # ``execution`` field popped from every delivered action
    "report_noexec": Condition(report=True, trajectory=False,
                               sections=("5.", "6."), execution=False),
}

#: mutually-substitutable cause families (test_report_loop.py's action
#: families, projected onto parameter dot-paths).  Used by the scorer to
#: count wrong-frees on recovery episodes; ``instrument.background.*`` is
#: always legitimate and lives in scorer.ALWAYS_LEGIT.
POSITION_FAMILY = [
    "instrument.zero_shift",
    "instrument.geometry.sample_displacement",
    "instrument.geometry.sample_transparency",
    "phases.*.cell.*",
]
WIDTH_FAMILY = [
    "instrument.profile.*",
    "phases.*.lor_size",
    "phases.*.lor_strain",
    "phases.*.gauss_size",
    "phases.*.gauss_strain",
]
SCALE_FAMILY = [
    "phases.*.scale",
    "phases.*.atoms.*.biso",
]

#: the deliverable declarations (PROTOCOL.md § Episodes, J1's sub-rows —
#: §4b run as an episode: one state, two correct answers, decided by the
#: declared purpose).  Keys are the ``deliverable`` tokens truth rows carry;
#: the text states the purpose and never hints at the answer.
DELIVERABLES = {
    "phase_id": (
        "Your deliverable is **phase identification**: decide whether this "
        "phase, as a phase, is the right identification of the crystalline "
        "material in the specimen.  Grade your verdict against that purpose."),
    "structure": (
        "Your deliverable is **structure quality**: decide whether the "
        "refined structural parameters (coordinates, occupancies, "
        "displacement parameters) are trustworthy as publishable values.  "
        "Grade your verdict against that purpose."),
}


def _request_core(structure, instrument, pattern, **extra) -> dict:
    """The fixed request core — everything the agent must not touch.

    ``extra`` admits protocol-level request fields (W1 carries the 11-BM
    protocol's ``two_theta_limits``); the agent's overlay may still override
    an overlay-sanctioned key, which for a limits key means narrowing or
    widening over data that exists — N1's truncation is in the *arrays*
    precisely because there an override must have nothing to widen into.
    """
    return {
        "task": "refine",
        "structure": structure.model_dump(mode="json"),
        "instrument": instrument.model_dump(mode="json"),
        "pattern": pattern.model_dump(mode="json"),
        "mode": "rietveld",
        **extra,
    }


def build_episodes() -> dict[str, dict]:
    """The synthetic group: E1, E8p, J1P/J1S.

    Truth values are read from the unperturbed models, never hard-coded.
    E8p is E8′ in PROTOCOL.md — E2's displacement plant on E8's short
    window, replacing retired E8 (whose planted zero the default plan freed,
    landing correctly quiet: the 1.1 defect).  J1P/J1S share one pore-proxy
    core and differ only in the declared deliverable.
    """
    structure, ins, data = _truth()
    zero_truth = ins.zero_shift.value

    episodes: dict[str, dict] = {}

    e1_ins = ins.model_copy(deep=True)
    e1_ins.zero_shift.value = 0.008
    episodes["E1"] = {
        "core": _request_core(structure, e1_ins, data),
        "truth": {
            "episode": "E1",
            "expected_verdict": "converged",
            "next_action": ["none"],
            "planted": {"path": "instrument.zero_shift", "start": 0.008,
                        "truth": zero_truth, "tol": {"abs": 0.002}},
            "family": POSITION_FAMILY,
            "notes": "0.008 deg zero error; solvable control (kept from 1.1 "
                     "so `underclaimed` means something) — the default "
                     "plan's zero stage frees the planted parameter.",
        },
    }

    s8, ins8, data8 = _truth(lo=20.0, hi=56.0, seed=23)
    e8_ins = ins8.model_copy(deep=True)
    e8_ins.geometry.sample_displacement.value = -0.02
    episodes["E8p"] = {
        "core": _request_core(s8, e8_ins, data8),
        "truth": {
            "episode": "E8p",
            "expected_verdict": "ambiguous",
            "next_action": None,
            "planted": {"path": "instrument.geometry.sample_displacement",
                        "start": -0.02,
                        "truth": ins8.geometry.sample_displacement.value,
                        "tol": None},
            "family": None,
            "watch": {"cause": ["instrument.geometry.sample_displacement"],
                      "absorber": ["instrument.zero_shift"]},
            "notes": "-0.02 mm displacement planted in the start over "
                     "20-56 deg; no mccusker_default stage frees "
                     "displacement, so the lazy path absorbs it into "
                     "zero_shift (measured 2026-08-13: zero -0.0112, "
                     "Rwp 0.01265) and the exchange clause fires at that "
                     "converged state.  The aberration is in the starting "
                     "model, so the rivals tie exactly (chi2 ratio 1.0001, "
                     "band [0.99, 1.01]) — this row can only ever answer "
                     "'tie', which is its job (PROTOCOL.md 2.0 § Episode "
                     "validity).",
        },
    }

    j1_structure, j1_ins, j1_data = _pore_proxy_data()
    j1_core = _request_core(j1_structure, j1_ins, j1_data)
    j1_notes = ("the WP-1057 pore proxy: LaB6 + a guest scatterer in the "
                "data only.  Re-measured 2026-08-13: converges at "
                "Rwp 0.04048, GoF 2.970; lebail_gap ratio 2.381 (>2); the "
                "alternating-sign contents clause fires; the action list is "
                "empty (honest silence).  One state, two correct answers, "
                "decided by the declared deliverable (the agent skill §4b).")
    episodes["J1P"] = {
        "core": j1_core,
        "truth": {
            "episode": "J1P",
            "expected_verdict": "converged",
            "next_action": ["none"],
            "deliverable": "phase_id",
            "planted": None,
            "family": None,
            "notes": j1_notes,
        },
    }
    episodes["J1S"] = {
        "core": j1_core,
        "truth": {
            "episode": "J1S",
            "expected_verdict": "ambiguous",
            "next_action": ["chemistry_or_contents"],
            "deliverable": "structure",
            "planted": None,
            "family": None,
            "notes": j1_notes,
        },
    }

    return episodes


def build_real_episodes() -> dict[str, dict]:
    """The SRM 660c trio: N1, C1, R2 — off the NIST protocol's converged state.

    One baseline fit (~1.5 s, 5332 channels, CuKα doublet, the file's own esd
    column) supplies all three starts and the truth values, which are read
    from it rather than hard-coded (baseline, measured 2026-08-13:
    Rwp 0.08661, χ² 3.4921, displacement −0.0800986).

    - **C1** (R1's successor, tolerance restored) knocks the fitted
      displacement to −0.02 on the **full** window.  The lazy path absorbs it
      into ``zero_shift`` (Rwp 0.09127, zero +0.0317, the clause firing) —
      but the data chooses: disp-only χ² 3.4894 against zero-only 4.0753,
      ratio 1.1679 (decisive band ≥ 1.10), and the swap recovers the
      displacement to 1.4e-07.  Expected ``converged`` **with** the
      tolerance: the ridge (−0.1202) and the zero-absorber state both fail
      it.  R1 — same knock, expected ``ambiguous`` — was retired by this
      measurement (PROTOCOL.md 2.0 § Episode validity).
    - **N1** is the same knock on a window that genuinely cannot tell: the
      pattern truncated to ≤ ``N1_MAX_TWO_THETA`` **in the arrays** (1258 of
      5332 channels, 20.30–54.90°), where the rivals tie at 1.0075 and the
      exchange clause fires at every reachable state.  Expected
      ``ambiguous`` + ``extend_range_or_calibrate`` — the aberration is in
      the *data* (the specimen is genuinely displaced), so no default stage
      can free it away (E8's failure mode cannot recur).
    - **R2** takes scale ×0.90 — separable, the default plan recovers it;
      the solvable control kept from 1.1.
    """
    from tests.test_acceptance_srm660c import (
        DATA,
        _nist_calibrated_plan,
        build_srm_inputs,
    )

    if not (DATA / "nist_srm660c_100a.cif").exists():
        raise FileNotFoundError(
            "SRM 660c dataset not present; N1/C1/R2 cannot be built "
            "(tests/data/README.md)")

    data, structure, instrument = build_srm_inputs()
    ref = rx.Refinement(structure, instrument)
    ref.fit(data, plan=_nist_calibrated_plan())
    base_s = ref.fitted_structure.model_copy(deep=True)
    base_i = ref.fitted_instrument.model_copy(deep=True)
    disp_truth = base_i.geometry.sample_displacement.value
    scale_truth = base_s.phases[0].scale.value

    knocked_i = base_i.model_copy(deep=True)
    knocked_i.geometry.sample_displacement.value = -0.02

    tt = np.asarray(data.two_theta)
    mask = tt <= N1_MAX_TWO_THETA
    n1_data = rx.PatternData(
        two_theta=tt[mask].tolist(),
        intensity=np.asarray(data.intensity)[mask].tolist(),
        sigma=(np.asarray(data.sigma)[mask].tolist()
               if data.sigma is not None else None))

    r2_structure = base_s.model_copy(deep=True)
    r2_structure.phases[0].scale.value = scale_truth * 0.90

    watch = {"cause": ["instrument.geometry.sample_displacement"],
             "absorber": ["instrument.zero_shift"]}
    return {
        "N1": {
            "core": _request_core(base_s, knocked_i, n1_data),
            "truth": {
                "episode": "N1",
                "expected_verdict": "ambiguous",
                "next_action": ["extend_range_or_calibrate"],
                "planted": {"path": "instrument.geometry.sample_displacement",
                            "start": -0.02, "truth": disp_truth, "tol": None},
                "family": POSITION_FAMILY,
                "watch": watch,
                "notes": "real SRM 660c truncated to <=56 deg in the arrays "
                         "(1258 of 5332 channels) — nothing to widen into; "
                         "displacement knocked -0.0801 -> -0.02.  Measured "
                         "2026-08-13: rivals tie at chi2 ratio 1.0075 (band "
                         "[0.99, 1.01]) and the exchange clause fires at the "
                         "default-plan landing state and both single-rival "
                         "states — no reachable state is correctly quiet.  "
                         "The planted value is recorded, never graded.",
            },
        },
        "C1": {
            "core": _request_core(base_s, knocked_i, data),
            "truth": {
                "episode": "C1",
                "expected_verdict": "converged",
                "next_action": ["none"],
                "planted": {"path": "instrument.geometry.sample_displacement",
                            "start": -0.02, "truth": disp_truth,
                            "tol": {"abs": C1_DISP_TOL}},
                "family": POSITION_FAMILY,
                "watch": watch,
                "notes": "real SRM 660c, full window, displacement knocked "
                         "-0.0801 -> -0.02.  Measured 2026-08-13: disp-only "
                         "chi2 3.4894 against zero-only 4.0753 (ratio "
                         "1.1679, decisive band >= 1.10); the swap recovers "
                         "to 1.4e-07, the ridge lands at -0.1202 (off by "
                         "0.0401) and the zero-absorber state never frees "
                         "the path — the tolerance is what discriminates "
                         "the three.  Declining is wrong here: the direct "
                         "test of the 0.8 clause.",
            },
        },
        "R2": {
            "core": _request_core(r2_structure, base_i, data),
            "truth": {
                "episode": "R2",
                "expected_verdict": "converged",
                "next_action": ["none"],
                "planted": {"path": "phases.0.scale",
                            "start": scale_truth * 0.90, "truth": scale_truth,
                            "tol": {"rel": 0.02}},
                "family": SCALE_FAMILY,
                "notes": "real SRM 660c, scale x0.90 — the separable "
                         "solvable control kept from 1.1; the default plan "
                         "recovers it.",
            },
        },
    }


def build_nac_episode() -> dict[str, dict]:
    """W1 — wrong assumption: phase list.  Real 11-BM NAC data, NAC-only model.

    The CaF₂ impurity is real and unmodelled.  The pattern is the whole
    59,498-channel file (0.50–59.99°), so ``episode.json`` is multi-MB and
    every fit costs ~1.5 s — the prompt's do-not-read-it-whole warning is
    load-bearing here.  The core carries the acceptance protocol's
    ``two_theta_limits`` (2–24°) and the QPA suite's deterministic scale
    seeding; no fit runs at build.

    Measured 2026-08-13 at the default-plan landing state (Rwp 0.14025,
    χ² 28.2766, a 10.25121): ``add_impurity_phase`` active at 0.9 in the
    **converged** report (the Layer-2 decidability precondition), 5 of 6
    strong CaF₂ lines under ``unmatched_obs`` entries (three at ~110σ), the
    trajectory confidence climbing 0.3 → 0.6 → 0.9 (WP-1058's signal — the
    ``report_trajectory`` default is decided on this row), and the
    with-CaF₂ refit decisive at χ² ratio 2.2702 (band ≥ 1.10).
    """
    from tests.test_acceptance_nac import DATA, LIMITS, build_nac_inputs
    from tests.test_acceptance_qpa_roundrobin import seed_scales

    if not (DATA / "11BM_NAC.fxye").exists():
        raise FileNotFoundError(
            "11-BM NAC dataset not present; W1 cannot be built "
            "(tests/data/README.md)")

    data, structure, instrument = build_nac_inputs()
    seed_scales(structure, instrument, data)
    return {
        "W1": {
            "core": _request_core(structure, instrument, data,
                                  two_theta_limits=list(LIMITS)),
            "truth": {
                "episode": "W1",
                "expected_verdict": "impurity_suspected",
                "next_action": ["add_phase"],
                "planted": None,
                "family": None,
                "notes": "real 11-BM NAC with its real CaF2 impurity; the "
                         "model is NAC only.  Measured 2026-08-13: NAC-only "
                         "landing Rwp 0.14025 / chi2 28.2766 with "
                         "add_impurity_phase at 0.9 in the converged "
                         "report, strong unmatched_obs at the CaF2 lines "
                         "(7.52/12.30/14.44 deg at ~110 sigma), trajectory "
                         "confidence climbing 0.3 -> 0.6 -> 0.9; with-CaF2 "
                         "refit chi2 12.4553, decisive ratio 2.2702.",
            },
        },
    }


def build_qarr_episode() -> dict[str, dict]:
    """W2 — wrong assumption: instrument.  Real qarr corundum, single-line lie.

    The data was measured with the Cu Kα doublet; the episode's source
    declares Kα1 **only** — every Kα2 satellite then reads impurity-shaped,
    and the correct reading is the instrument model.  JSON arms cannot edit
    the instrument (the overlay admits plan/mode/limits only) and must
    reason from the satellites' shape; the python arm can run the source
    experiment — the asymmetry is part of what hypothesis (c) measures.

    Measured 2026-08-13: single-line landing Rwp 0.23335 / χ² 6.7901 with 46
    ``unmatched_obs``, 31 of them at predicted Kα2 positions, and the
    designed trap live — ``add_impurity_phase`` served at 0.9; the doublet
    refit lands Rwp 0.14627 / χ² 2.6680 (decisive ratio 2.5450, band
    ≥ 1.10) with **zero** unmatched entries at Kα2 positions (the vanishing
    criterion — an impurity's peaks would survive a source fix).
    """
    from tests.test_acceptance_qpa_roundrobin import (
        DATA,
        corundum_phase,
        qarr_instrument,
        seed_scales,
    )

    if not (DATA / f"{W2_SAMPLE}.prn").exists():
        raise FileNotFoundError(
            "IUCr QPA round-robin dataset not present; W2 cannot be built "
            "(tests/data/README.md)")

    data = rx.read_pattern(DATA / f"{W2_SAMPLE}.prn")
    instrument = qarr_instrument()
    instrument.source.lines = [
        instrument.source.lines[0].model_copy(deep=True)]
    structure = rx.Structure(phases=[corundum_phase()])
    seed_scales(structure, instrument, data)
    return {
        "W2": {
            "core": _request_core(structure, instrument, data),
            "truth": {
                "episode": "W2",
                "expected_verdict": "assumption_wrong",
                "next_action": ["fix_instrument_model"],
                "planted": None,
                "family": None,
                "notes": "real qarr corundum (Cu Ka doublet in the data), "
                         "source declared single-line.  Measured "
                         "2026-08-13: single-line landing Rwp 0.23335 / "
                         "chi2 6.7901, 31 unmatched_obs at predicted Ka2 "
                         "positions, add_impurity_phase served at 0.9 (the "
                         "designed Layer-0 trap); doublet refit chi2 "
                         "2.6680 (decisive ratio 2.5450) with zero "
                         "unmatched at Ka2 — an impurity's peaks would "
                         "survive a source fix, which is the discriminator.",
            },
        },
    }


# ----------------------------------------------------------------------
# prompt
# ----------------------------------------------------------------------
SKILL_TREE = REPO_ROOT / "docs" / "skill" / "rietx"


def _protocol_excerpt(heading: str) -> str:
    """One numbered section of the agent skill, verbatim.

    The document ships with the feature, so the excerpt is extracted live
    rather than copied, and a rewritten section reaches the prompt by itself.

    WP-1304 made the document a *directory*, and the two sections this renders
    (§5, §6) are now whole reference files under their promoted ``#`` heading,
    holding the same text the single document carried.  **The reference files
    are searched first for exactly that reason**: the body's §6 is a condensed
    rule list pointing at the table, so a body-first search would quietly
    shorten a registered condition's prompt.

    The section text itself did not change.  What is skipped is the two lines
    each reference file gained — the "load it when" blurb and the back-link —
    which are navigation for an agent browsing the tree and noise in a prompt.

    Fence-aware, because ``SKILL.md``'s worked example is python whose comments
    begin with ``#``: a naive scan matches ``# 5. numbers, not pixels`` inside
    the code block and returns four lines of someone else's example.
    """
    candidates = [*sorted((SKILL_TREE / "references").glob("*.md")),
                  SKILL_TREE / "SKILL.md"]
    for path in candidates:
        lines = path.read_text(encoding="utf-8").splitlines()
        headings = _headings(lines)
        start = next((i for i in headings
                      if re.match(rf"^#{{1,2}} {re.escape(heading)}", lines[i])), None)
        if start is None:
            continue
        rank = len(lines[start]) - len(lines[start].lstrip("#"))
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].startswith("---")
                    or (i in headings and re.match(rf"^#{{1,{rank}}} ", lines[i]))),
                   len(lines))
        body = []
        for line in lines[start + 1:end]:
            if line.startswith(("Load it when", "*A reference file")):
                continue
            body.append(line)
        while body and not body[0].strip():  # the blanks those two lines sat in
            body.pop(0)
        return "\n".join([lines[start], "", *body]).rstrip()
    raise KeyError(f"no section {heading!r} anywhere in {SKILL_TREE}")


def _headings(lines: list[str]) -> set[int]:
    """Indices of real markdown headings — never a ``#`` inside a code fence."""
    out, fence = set(), None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if fence is None and stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        if line.startswith("#"):
            out.add(i)
    return out


#: the glossaries the prompt renders.  Keys are checked against the scorer's
#: closed vocabularies at render time — the grader is the authority on what
#: it grades, and a token without a meaning (or a meaning without a token)
#: must fail the build, not confuse an agent.  The impurity/assumption line
#: is drawn explicitly: without it two tokens are defensible on one row and
#: the closed vocabulary stops protecting anyone (PROTOCOL.md 2.0).
VERDICT_MEANINGS = {
    "converged": (
        "the refinement reached a satisfactory fit; your **last** call is "
        "graded as your answer state."),
    "impurity_suspected": (
        "the pattern contains intensity the given **phase list** cannot "
        "account for (an impurity / extra phase); say so rather than "
        "fitting through it."),
    "assumption_wrong": (
        "a **declared, non-refinable input** — the source's emission lines, "
        "the geometry *type* (capillary vs flat plate), the radiation — "
        "disagrees with the data; fixing that declaration, not refining "
        "more parameters, is the answer.  (This is about the "
        "instrument/measurement description; a missing phase is "
        "`impurity_suspected`, and a **refinable parameter at a wrong "
        "starting value** — a zero, a displacement — is never this: that is "
        "`converged` when the data chooses its value, and `ambiguous` when "
        "this data cannot.)"),
    "abstain": (
        "the starting model is too far from the data for any refinement "
        "reachable from here to be trustworthy; no answer."),
    "ambiguous": (
        "more than one physical cause explains the misfit and this data "
        "range cannot separate them; naming one confident cause would be "
        "wrong."),
}
NEXT_ACTION_MEANINGS = {
    "none": (
        "no further remedial action is needed (a limitation you would "
        "attach to the delivered result goes in `caveats`)."),
    "extend_range_or_calibrate": (
        "the measured angular window (or a calibration on it) is what "
        "limits the answer: remeasure wider, or fix zero/displacement "
        "against a standard."),
    "add_phase": (
        "identify and add a phase for intensity the current phase list "
        "cannot account for."),
    "fix_instrument_model": (
        "correct the declared instrument (emission lines, the geometry "
        "*type*) before refining further."),
    "collect_better_data": (
        "counting statistics or resolution are what limits the answer."),
    "chemistry_or_contents": (
        "the question needs chemical/contents information diffraction "
        "alone cannot supply."),
}


def _glossary(meanings: dict[str, str], vocabulary: tuple[str, ...]) -> str:
    if set(meanings) != set(vocabulary):
        raise ValueError(
            f"glossary/vocabulary mismatch: {sorted(meanings)} vs "
            f"{sorted(vocabulary)}")
    return "\n".join(f"- `{token}` — {meanings[token]}"
                     for token in vocabulary)


_PROMPT = """\
# Episode {eid} — powder XRD refinement

You are operating the `rietx` Rietveld refinement package through one JSON
call, the shim command below.  This directory is your workspace:

- `episode.json` — the fixed request core (structure, instrument, pattern).
  Read-only: the shim merges your overlay onto it; you never edit it.  It is
  mostly bulk pattern arrays — do not read it whole; if you need a metadata
  field (phase, wavelength), query it selectively (e.g. `jq`/`head`).
- `overlay.json` — yours to write.  Allowed keys, each optional:
  - `"plan"`: a preset name, or an explicit stage list
    `{{"stages": [{{"name": "...", "turn_on": ["<path glob>", ...]}}, ...]}}`
    (stages accumulate: each stage frees its `turn_on` globs on top of the
    previous stages' — dot-paths like `instrument.zero_shift`,
    `phases.*.cell.*`).  Omitted = the `mccusker_default` preset.
  - `"mode"`: `"rietveld"` (default) | `"lebail"` | `"pawley"`.
  - `"two_theta_limits"`: `[lo, hi]` — fit only this range (legitimate for
    excluding a contaminated region; the exclusion is recorded).
  Any other key is refused by the shim.
- To run one refinement — every call starts from the same fixed starting
  values; calls do not chain — run, from the repository root:

      {python} -m tests.eval_report_agent.run_refine {episode_dir}

  The response prints to stdout (bulk curve arrays elided; every parameter,
  statistic and diagnostic{report_clause} is intact) and is appended to
  `calls.jsonl`.  A call usually returns in seconds, but a refinement that
  diverges can take 2-3 minutes before it fails — allow a 5-minute timeout.
  A failed call returns `{{"ok": false, "error": ...}}`; that is information,
  not a harness bug.
- Budget: plan on at most 6 calls; the shim hard-stops at {max_calls}.  Make
  at least one call — an answer with no refinement behind it scores zero.
{deliverable_section}
When you are done, write `answer.json` in this directory:

    {{"verdict": "<one of the five below>",
      "next_action": "<one of the six below>",
      "caveats": ["<zero or more short statements of limitations you would
                   attach to the delivered result>"],
      "summary": "<a few sentences: what you concluded and why>"}}

Verdict meanings — pick exactly one:

{verdict_glossary}

Next-action meanings — the single best next step, pick exactly one:

{next_action_glossary}

Work from the numbers in the response.  A good fit is necessary but not
sufficient: parameters compensating for each other can look converged, so
prefer the verdict the evidence supports over the one that ends the episode.
{report_section}"""

_REPORT_SECTION = """
## Reading the FitReport

Each response carries `report` — the three-layer FitReport.  The governing
sections of the package manual are quoted verbatim below.
{notice}
{sections}
"""

#: the trajectory-stripped arm needs this or it hunts for a key the §5
#: excerpt promises: a factual statement about the *response shape*, never an
#: instruction — reaching an earlier state some other way is an operator
#: skill the prompt must not teach (1.1's rule, kept)
_NO_TRAJECTORY_NOTICE = """
This run's responses carry the converged report only: the per-stage
`trajectory` §5 points to is stripped by the harness and will not appear.
"""

_DELIVERABLE_SECTION = """
## Deliverable

{text}
"""


def render_prompt(eid: str, episode_dir: Path, *, condition: str,
                  python: str = ".venv/bin/python",
                  deliverable: str | None = None) -> str:
    """The one shared prompt (PROTOCOL.md pins it; no per-model tuning).

    Report arms get the skill excerpts their condition declares —
    the manual ships with the feature, so §5/§6 track the report; ``off``
    gets neither the report nor the manual.  Every arm gets the v2 answer
    contract, which is why no 2.0 cell — ``off`` included — is readable
    against a 1.x grid.  ``deliverable`` names a :data:`DELIVERABLES` entry
    (J1's sub-rows); everything else omits the section.
    """
    spec = CONDITIONS[condition]
    if spec.report:
        report_clause = ", and the full FitReport,"
        report_section = _REPORT_SECTION.format(
            notice="" if spec.trajectory else _NO_TRAJECTORY_NOTICE,
            sections="\n\n".join(_protocol_excerpt(name)
                                 for name in spec.sections))
    else:
        report_clause = ""
        report_section = ""
    deliverable_section = ""
    if deliverable is not None:
        deliverable_section = _DELIVERABLE_SECTION.format(
            text=DELIVERABLES[deliverable])
    return _PROMPT.format(
        eid=eid, episode_dir=episode_dir, python=python, max_calls=MAX_CALLS,
        report_clause=report_clause, report_section=report_section,
        deliverable_section=deliverable_section,
        verdict_glossary=_glossary(VERDICT_MEANINGS, VERDICTS),
        next_action_glossary=_glossary(NEXT_ACTION_MEANINGS, NEXT_ACTIONS))


# ----------------------------------------------------------------------
# writer
# ----------------------------------------------------------------------
def condition_marker_path(episodes_dir: Path, eid: str) -> Path:
    """The sibling marker — beside the episode dir, never inside it.

    The workspace must carry no condition bit (the round-2 leak): the marker
    is what the shim enforces from, and the prompt never names it.
    """
    return episodes_dir / f"{eid}.condition.json"


def assemble_episodes(wanted: tuple[str, ...]) -> dict[str, dict]:
    """The selected episodes, building each dataset group only when the
    selection names one of its members — a synthetic-only selection stays as
    cheap as it was at 1.0.  Shared by both workspace writers (this module's
    JSON-arm fixtures and ``python_arm``'s), so the lazy-group rule has one
    authority."""
    unknown = sorted(set(wanted) - set(EPISODE_IDS))
    if unknown:
        raise ValueError(f"unknown episode id(s): {', '.join(unknown)}")
    episodes = build_episodes()
    if any(eid in SRM_IDS for eid in wanted):
        episodes.update(build_real_episodes())
    if any(eid in NAC_IDS for eid in wanted):
        episodes.update(build_nac_episode())
    if any(eid in QARR_IDS for eid in wanted):
        episodes.update(build_qarr_episode())
    return episodes


def write_fixtures(episodes_dir: Path, truth_dir: Path, *, condition: str,
                   python: str = ".venv/bin/python",
                   only: list[str] | None = None) -> list[Path]:
    """Write episode dirs + sibling markers + truth tree; returns the dirs."""
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of "
                         f"{'|'.join(CONDITIONS)}, got {condition!r}")
    spec = CONDITIONS[condition]
    wanted = tuple(only or EPISODE_IDS)
    episodes = assemble_episodes(wanted)
    episodes_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for eid in wanted:
        ep = episodes[eid]
        edir = episodes_dir / eid
        edir.mkdir(exist_ok=True)
        (edir / "episode.json").write_text(
            json.dumps(ep["core"], indent=1) + "\n", encoding="utf-8")
        condition_marker_path(episodes_dir, eid).write_text(json.dumps({
            "protocol_version": PROTOCOL_VERSION,
            "condition": condition,
            "include_report": spec.report,
            "include_trajectory": spec.trajectory,
            "license_placement": spec.license_placement,
            "include_execution": spec.execution,
            "prompt_sections": list(spec.sections),
            "max_calls": MAX_CALLS,
        }, indent=1) + "\n", encoding="utf-8")
        (edir / "prompt.md").write_text(
            render_prompt(eid, edir, condition=condition, python=python,
                          deliverable=ep["truth"].get("deliverable")),
            encoding="utf-8")
        (truth_dir / f"{eid}.json").write_text(
            json.dumps(ep["truth"], indent=1) + "\n", encoding="utf-8")
        written.append(edir)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=Path, required=True,
                        help="directory to write episode dirs into")
    parser.add_argument("--truth", type=Path, required=True,
                        help="scorer-side truth tree (keep it outside the "
                             "agent's workspace)")
    parser.add_argument("--condition", required=True,
                        choices=sorted(CONDITIONS))
    parser.add_argument("--python", default=".venv/bin/python",
                        help="interpreter the prompt tells the agent to use")
    parser.add_argument("--only", nargs="*", choices=EPISODE_IDS,
                        help="subset of episodes (default: all nine)")
    args = parser.parse_args(argv)
    written = write_fixtures(args.episodes, args.truth,
                             condition=args.condition, python=args.python,
                             only=args.only)
    for edir in written:
        print(edir)


if __name__ == "__main__":
    main()
