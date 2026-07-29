"""Shared harness for the WPEM benchmark (arXiv 2602.16372).

The one thing this module exists to guarantee is that **the agreement factors
are comparable**.  WPEM computes them in ``EMBraggSolver.up_parameter``:

    Rp  = Σ|y_calc − y_obs| / Σ y_obs
    Rwp = sqrt( Σ (y_calc − y_obs)² / max(y_obs,1)  /  Σ y_obs )

where ``y_obs`` is the **raw** pattern (``i_obser = in_data.intensity``, the
original file, background included) and ``y_calc = bac + peaks``.  Substituting
Poisson weights w = 1/max(y_obs,1) into the textbook definition gives
Σ w y_obs² = Σ y_obs, so WPEM's Rwp *is* the conventional Rietveld Rwp and our
``Statistics.rwp`` is the same number — provided we also weight by Poisson
counting statistics and also evaluate on the raw pattern with the background
in.  Both hold: these CSVs carry no esd column, so ``read_pattern`` falls back
to √max(y,1), and ``pxrdref`` never subtracts a background.

What is *not* comparable without saying so is the model behind the number, and
that is the point of ``n_free``: WPEM refines a per-reflection (γ, σ, Δ, w)
quadruple, so its parameter count scales with the reflection list, while a
Rietveld model spends a handful of profile terms plus a structure.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

import pxrdref as pr

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CIFS = ROOT / "cifs"
OUT = ROOT / "output"
RESULTS = ROOT / "results"


@dataclass
class CaseRecord:
    """One benchmark case, serialized to results/<case>.json."""

    case: str
    dataset: str
    n_points: int
    two_theta_range: tuple[float, float]
    wavelengths: list[float]
    mode: str
    rwp: float
    rp: float
    rexp: float
    gof: float
    chi2: float
    n_free: int
    status: str
    seconds: float
    cells: dict[str, dict[str, float]] = field(default_factory=dict)
    cell_esds: dict[str, dict[str, float]] = field(default_factory=dict)
    weight_fractions: dict[str, float] = field(default_factory=dict)
    weight_fraction_esds: dict[str, float] = field(default_factory=dict)
    parameters: dict[str, dict] = field(default_factory=dict)
    diagnostics: list[dict] = field(default_factory=list)
    reference: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def save(self) -> Path:
        RESULTS.mkdir(parents=True, exist_ok=True)
        path = RESULTS / f"{self.case}.json"
        path.write_text(json.dumps(asdict(self), indent=2, default=float))
        return path


def load(rel: str) -> pr.PatternData:
    """Read one of the downloaded WPEM CASES patterns."""
    return pr.read_pattern(DATA / rel)


_SPECIES_RE = re.compile(r"^([A-Za-z]{1,2})(\d*[+-])?$")


def normalize_cif_species(structure: pr.Structure) -> list[str]:
    """Repair ``_atom_site_type_symbol`` values that are really site *labels*.

    Several of these COD entries (AMCSD-derived ones especially) put ``O1``,
    ``O2``, ``Cl1`` in the type-symbol column where the CIF dictionary wants an
    element with an optional ionic charge.  ``pxrdref`` reads them verbatim, and
    since v1.0 turned anomalous dispersion on by default, ``dispersion.resolve``
    raises ``cannot read an element symbol from species 'O1'`` at stage compile.
    Strip the site index and report what changed, so the substitution is visible
    rather than silent.
    """
    changed = []
    for phase in structure.phases:
        for atom in phase.atoms:
            if _SPECIES_RE.match(atom.species.strip()):
                continue
            fixed = re.sub(r"\d+$", "", atom.species.strip())
            if not _SPECIES_RE.match(fixed):
                raise ValueError(f"cannot normalise species {atom.species!r}")
            changed.append(f"{atom.species} -> {fixed}")
            atom.species = fixed
    return changed


def cif(stem: str) -> pr.Structure:
    """Load a fetched COD structure by filename stem prefix, species repaired."""
    hits = sorted(CIFS.glob(f"{stem}_cod*.cif"))
    if not hits:
        raise FileNotFoundError(f"no CIF for {stem!r} — run fetch_cifs.py")
    structure = pr.Structure.from_cif(str(hits[0]))
    fixed = normalize_cif_species(structure)
    if fixed:
        print(f"    [cif] {hits[0].name}: species relabelled {', '.join(fixed)}")
    return structure


def cell_dict(phase) -> dict[str, float]:
    c = phase.cell
    return {k: float(getattr(c, k).value)
            for k in ("a", "b", "c", "alpha", "beta", "gamma")}


def cell_esd_dict(result, index: int) -> dict[str, float]:
    out = {}
    for k in ("a", "b", "c", "alpha", "beta", "gamma"):
        try:
            p = result.parameter(f"phases.{index}.cell.{k}")
        except Exception:  # noqa: BLE001 - path absent when tied/locked
            continue
        if p is not None and p.stderr is not None:
            out[k] = float(p.stderr)
    return out


def record(case: str, dataset: str, data: pr.PatternData, result,
           structure: pr.Structure, *, mode: str, seconds: float,
           reference: dict | None = None,
           notes: list[str] | None = None) -> CaseRecord:
    tt = np.asarray(data.two_theta)
    st = result.statistics
    rec = CaseRecord(
        case=case, dataset=dataset, n_points=int(len(tt)),
        two_theta_range=(float(tt[0]), float(tt[-1])),
        wavelengths=[], mode=mode,
        rwp=float(st.rwp), rp=float(st.rp), rexp=float(st.rexp),
        gof=float(st.gof), chi2=float(st.chi2),
        n_free=int(st.n_free_parameters), status=str(result.status),
        seconds=round(seconds, 1),
        reference=reference or {}, notes=notes or [],
    )
    for i, ph in enumerate(structure.phases):
        rec.cells[ph.name] = cell_dict(ph)
        esd = cell_esd_dict(result, i)
        if esd:
            rec.cell_esds[ph.name] = esd
    qpa = getattr(result, "qpa", None)
    for q in (qpa.phases if qpa is not None else []):
        rec.weight_fractions[q.name] = float(q.weight_fraction)
        if getattr(q, "weight_fraction_stderr", None) is not None:
            rec.weight_fraction_esds[q.name] = float(q.weight_fraction_stderr)
    # Every refined parameter, so the degenerate {zero, displacement, cell}
    # triple of AGENT_PROTOCOL §3 can be audited after the fact rather than
    # trusted.  Background coefficients are dropped: they are numerous, they
    # dominate the JSON, and none of them is a physical claim.
    for p in result.parameters:
        if not p.vary or p.path.startswith("instrument.background."):
            continue
        rec.parameters[p.path] = {"value": float(p.value),
                                  "stderr": None if p.stderr is None else float(p.stderr)}
    rec.diagnostics = [{"level": d.level, "code": d.code, "message": d.message}
                       for d in result.diagnostics]
    return rec


def plot(result, case: str, *, zooms: list[tuple[float, float]] | None = None) -> None:
    """Obs/calc/diff PNG plus zooms — Rwp hides locally-bad fits."""
    OUT.mkdir(parents=True, exist_ok=True)
    result.plot(path=str(OUT / f"{case}_full.png"))
    for lo, hi in zooms or []:
        result.plot(path=str(OUT / f"{case}_zoom_{lo:g}-{hi:g}.png"),
                    two_theta_range=(lo, hi))


def lab_plan(*, structural: bool = True, sample_profile: bool = True,
             preferred_orientation: bool = True,
             displacement: bool = False) -> pr.RefinementPlan:
    """``lab_bragg_brentano`` continued into ``mccusker_structural``.

    Every WPEM case except the Egyptian synchrotron one is lab Cu Kα
    Bragg-Brentano data, so the doublet ratio and the FCJ axial-divergence
    ratios are real refinable physics that neither stock plan carries together
    with the structure.  Order follows AGENT_PROTOCOL §2: widths after
    positions, W before U/V/X/Y, intensity-rescaling corrections last.

    ``displacement`` defaults to **off**, against ``lab_bragg_brentano``'s own
    stage list, because nothing in these datasets pins the {zero (const),
    displacement (cosθ), cell (tanθ)} triple from outside the fit — no
    certified standard, no declared zero.  Freeing both members was tried on
    Tb2BaCoO5 and came back zero = 0.232(220)°, displacement = 0.391(392) mm:
    two parameters whose esds equal their own values, which is one parameter
    reported twice (AGENT_PROTOCOL §3).
    """
    position = ["instrument.zero_shift"]
    if displacement:
        position.append("instrument.geometry.sample_displacement")
    stages = [
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("zero_disp", position),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
        pr.Stage("lines_axial", ["instrument.source.lines.*.weight",
                                 "instrument.geometry.axial_sl",
                                 "instrument.geometry.axial_hl"]),
    ]
    if sample_profile:
        stages.append(pr.Stage(
            "sample_profile",
            ["phases.*.lor_size", "phases.*.lor_strain",
             "phases.*.gauss_size", "phases.*.gauss_strain"]))
    if structural:
        stages += [
            pr.Stage("coordinates", ["phases.*.atoms.*.dof.*"]),
            pr.Stage("biso", ["phases.*.atoms.*.biso",
                              "phases.*.atoms.*.adp.*"]),
        ]
    if preferred_orientation:
        stages.append(pr.Stage("preferred_orientation",
                               ["phases.*.preferred_orientation.r"]))
    return pr.RefinementPlan(stages=stages)


def fit_to_fixed_point(ref: pr.Refinement, data: pr.PatternData, *,
                       mode: str = "lebail", plan="profile_only",
                       max_passes: int = 6, tol: float = 2e-4,
                       label: str = "") -> tuple[object, int]:
    """Re-run the whole staged plan until Rwp stops moving.

    Le Bail needs this and a single ``fit()`` does not provide it.  The
    extracted per-hkl intensities are frozen inside each least-squares run (the
    frozen-per-stage discreteness invariant), so profile and intensities can
    only converge *jointly* by alternating: one pass of ``profile_only`` on
    PbSO4 stops at Rwp = 20.8 % with an unphysical V = +0.062, and three more
    passes take it to 10.2 % with the profile in a sane place.  Measured, not
    assumed — see REPORT.md.  Rietveld does not need it, but running the same
    loop costs one extra no-op pass and keeps the two protocols identical.
    """
    best = None
    best_node = None
    previous = float("inf")
    passes = 0
    for _ in range(max_passes):
        result = ref.fit(data, mode=mode, plan=plan)
        passes += 1
        rwp = result.statistics.rwp
        if best is None or rwp < best.statistics.rwp:
            best, best_node = result, result.node_id
        if label:
            marker = "" if result is best else "  (worse — discarded)"
            print(f"      {label} pass {passes}: Rwp={rwp * 100:.3f}%{marker}")
        if previous - rwp < tol:
            break
        previous = rwp
    # A pass can land *worse* than its predecessor: the Le Bail partition and
    # the profile are alternating, not descending a single objective, so the
    # loop is not monotone.  Rewind the working state to the best node rather
    # than reporting whichever pass happened to be last.
    if best_node is not None and ref.result_ is not best:
        ref.checkout(best_node)
    return best, passes


def diag_summary(result) -> str:
    """Counts by code — the raw list runs to >1000 entries on a P-spline."""
    from collections import Counter
    counts = Counter(d.code for d in result.diagnostics)
    return ", ".join(f"{k}x{v}" for k, v in counts.most_common())


def show_report(result, *, model=None, top: int = 6) -> None:
    """Print the Layer 0/1/2 lines an agent should act on."""
    report = pr.build_report(result)
    print(f"    report: {report.summary}")
    if report.abstained_reason:
        print(f"    layer1 abstained: {report.abstained_reason}")
    for region in report.regions[:top]:
        print(f"      region {region.two_theta_lo:6.2f}-{region.two_theta_hi:6.2f} "
              f"localRwp={region.local_rwp:.3f} chi2share={region.chi2_share:.1%} "
              f"max|d/s|={region.max_abs_delta_over_sigma:.1f}")
    for unmatched in report.unmatched[:top]:
        print(f"      unmatched obs peak at {unmatched.two_theta:.3f} deg")
    for action in report.suggested_actions[:top]:
        flag = "" if action.active else f"  (vetoed: {action.vetoed_by})"
        print(f"      action {action.kind} conf={action.confidence:.2f}: "
              f"{action.rationale[:120]}{flag}")


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self.t0
        return False


def show(result, label: str) -> None:
    st = result.statistics
    print(f"  {label:22s} status={result.status:10s} "
          f"Rwp={st.rwp * 100:6.3f}%  Rp={st.rp * 100:6.3f}%  "
          f"GoF={st.gof:5.2f}  nfree={st.n_free_parameters}")
    codes = diag_summary(result)
    if codes:
        print(f"      diagnostics: {codes}")
    for d in result.diagnostics:
        if d.code != "HIGH_CORRELATION":
            print(f"      [{d.level}] {d.code}: {d.message[:150]}")
