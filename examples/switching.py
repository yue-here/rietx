"""The fluorapatite refinement behind the Switching tab's three pages (WP-1984).

`docs/docs/switching/topas.md`, `gsas2.md` and `fullprof.md` show lines from
the files this script writes and numbers from the objects it reads back, and
none of them is typed from memory.  Every figure a page quotes is asserted
here, so a change that moves one fails `tests/test_examples.py` and the page
is corrected in the same change.  A page prints a long number cut to six
significant figures (`cut`).  The assertion compares each number within
`REL_TOL`, because a fitted value moves in its fifth figure between the
compiled and numpy paths: `th2_offset` by 2.9e-5 relative, measured
2026-10-17 with `RIETX_COMPILED=0`.

Data: the GSAS-II `LabData` tutorial fluorapatite and GSAS's converged fit of
it, `FAP.EXP`, both shipped in `rietx.examples`.  Everything it writes goes
to a temporary directory.
"""

import math
import re
import tempfile
from pathlib import Path

import rietx as rx
from rietx.examples import examples_dir
from rietx.io.projects.topas_ties import TopasConstraints, apply_ties

OXYGENS = ["phases.0.atoms.4.biso", "phases.0.atoms.5.biso", "phases.0.atoms.6.biso"]
LIMITS = (15, 130)

# The lines each page quotes, as the page prints them.
TOPAS_SITES = [
    "site O5 x O5_x 0.32467 y O5_y 0.484898 z ! 0.25 occ O ! 1.0 beq O5_biso 0.366488",
    "site O6 x O6_x 0.591092 y O6_y 0.469105 z ! 0.25 occ O ! 1.0 beq O5_biso 0.366488",
    "site O7 x O7_x 0.339828 y O7_y 0.257684 z O7_z 0.0705402 occ O ! 1.0 beq O5_biso 0.366488",
]
TOPAS_EXCERPT = [
    'xdd "refined.xye" xye_format',
    "  weighting = 1 / SigmaYobs^2;",
    "  bkg @ 152.446 -171.263 124.821 -73.5215 36.6909 -16.1333",
    "  th2_offset ! 0",
    "  th2_offset = -2*Rad*(0.0629551)*Cos(Th)/217.5;",
    "str",
    "  scale p0_scale 0.000469265 min 0",
    "  a p0_cell_a 9.37332",
    "  b p0_cell_a 9.37332",
]
INSTPRM = [
    "Type:PXC", "Lam1:1.54059", "Lam2:1.54443", "Zero:-0.0365586", "I(L2)/I(L1):0.5",
    "Polariz.:0.5", "U:-1.57826", "V:2.76475", "W:2.37759", "X:2.68762", "Y:4.11637",
]
# fullprof.md prints these runs with `...` between them; each run is
# consecutive in the file, so an atom's codeword line is the one under it.
PCR = [
    ["Ca1 CA 0.333333 0.666667 0.001913 0.479979 0.333333",
     "0.0 0.0 0.0 11.0 0.0"],
    ["O7 O 0.33951 0.258126 0.070641 0.530037 1.0",
     "0.0 0.0 21.0 0.0 0.0",
     "1.0 0.0 0.0 0.0 0.0 0.0 0",
     "31.0 0.0 0.0 0.0 0.0 0.0"],
    ["9.3717 9.3717 6.8859 90.0 90.0 120.0",
     "41.0 0.0 51.0 0.0 0.0 0.0"],
]

NUMBER = re.compile(r"-?\d+\.\d+")
REL_TOL = 1e-3      # 34x the measured path-to-path spread (module docstring)


def cut(text: str) -> str:
    """`text` with every number past six significant figures cut to six."""
    def one(match: re.Match) -> str:
        number = match.group()
        digits = number.lstrip("-").replace(".", "").lstrip("0")
        return number if len(digits) <= 6 else f"{float(number):.6g}"
    return NUMBER.sub(one, text)


def lines_of(path: Path) -> list[str]:
    return [cut(line) for line in path.read_text(encoding="utf-8").splitlines()]


def same(quoted: str, line: str) -> bool:
    """Whether a file line reads as the page quotes it: the text equal, and
    each number within `REL_TOL`."""
    if NUMBER.sub("#", quoted) != NUMBER.sub("#", line):
        return False
    return all(math.isclose(float(q), float(f), rel_tol=REL_TOL)
               for q, f in zip(NUMBER.findall(quoted), NUMBER.findall(line)))


def in_order(runs: list[list[str]], lines: list[str]) -> bool:
    """Whether every quoted run is in the file, in the order quoted, with the
    lines of one run consecutive."""
    start = 0
    for run in runs:
        found = next((i for i in range(start, len(lines) - len(run) + 1)
                      if all(map(same, run, lines[i:i + len(run)]))), None)
        if found is None:
            return False
        start = found + len(run)
    return True


def each(quoted: list[str]) -> list[list[str]]:
    """Quoted lines that may sit anywhere after the one before."""
    return [[line] for line in quoted]


def build() -> tuple[rx.PatternData, rx.Refinement]:
    data = rx.read_pattern(examples_dir() / "FAP.XRA")
    structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    instrument.geometry.axial_sl.value = 0.02
    instrument.geometry.axial_hl.value = 0.02
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    return data, rx.Refinement(structure, instrument)


def free_paths(ref: rx.Refinement) -> list[str]:
    return [row.path for row in ref.parameters() if row.vary]


def gsas2_page(out: Path) -> None:
    """A four-stage plan, the counterpart of a GSAS-II refinement recipe, and
    the `.instprm` written from its answer."""
    data, ref = build()
    plan = rx.RefinementPlan(stages=[
        rx.Stage("background", turn_on=["instrument.background.*", "phases.*.scale"]),
        rx.Stage("cell", turn_on=["instrument.zero_shift", "phases.*.cell.*"]),
        rx.Stage("profile", turn_on=["instrument.profile.*"]),
        rx.Stage("atoms", turn_on=["phases.*.atoms.*.dof.*", "phases.*.atoms.*.biso"]),
    ])
    result = ref.fit(data, plan=plan, two_theta_limits=LIMITS)
    assert result.status == "converged"
    assert round(result.statistics.rwp, 4) == 0.0898
    assert [(s.name, len(s.freed)) for s in result.stages] == [
        ("background", 7), ("cell", 3), ("profile", 5), ("atoms", 19), ("closing", 34)]

    path = out / "refined.instprm"
    rx.write_gsas2_instprm(ref.fitted_instrument, path)
    lines = lines_of(path)
    assert in_order([INSTPRM], lines[1:12])
    assert "SH/L:0.04" in lines          # axial_sl + axial_hl, 0.02 each
    u_instprm = next(float(line.split(":")[1])
                     for line in path.read_text(encoding="utf-8").splitlines()
                     if line.startswith("U:"))
    u_rietx = rx.read_gsas2_instprm(path).profile.u.value
    assert same("-0.000875173", cut(repr(u_rietx)))
    assert math.isclose(u_instprm * 8 * math.log(2) * 1e-4, u_rietx, rel_tol=1e-6)


def topas_page(out: Path) -> None:
    """A tie, a hold, and the file rietx writes for TOPAS from the held state."""
    data, ref = build()
    first = ref.fit(data, plan="mccusker_structural", two_theta_limits=LIMITS)
    assert round(first.statistics.rwp, 4) == 0.0898
    a_free = ref.fitted_structure.phases[0].cell.a.value
    ref.tie_equal(OXYGENS)
    ref.set_values({"instrument.zero_shift": 0.0})
    ref.hold(["instrument.zero_shift"])
    held = ref.fit(data, plan="lab_bragg_brentano", two_theta_limits=LIMITS)
    assert "HOLD_BLOCKED_PLAN" in [d.code for d in held.diagnostics]
    final = ref.fit(data, plan="mccusker_structural", two_theta_limits=LIMITS)
    assert round(final.statistics.rwp, 4) == 0.0894
    # topas.md: the held zero moves the cell 111 ppm from the fit with it free.
    a_held = ref.fitted_structure.phases[0].cell.a.value
    assert cut(repr(a_free)) == "9.37228"
    assert round(1e6 * (a_held - a_free) / a_free) == 111

    path = out / "refined.inp"
    rx.write_topas_inp(ref.fitted_structure, path, free=ref, scale="topas",
                       instrument=ref.fitted_instrument, pattern=data)
    lines = lines_of(path)
    # topas.md prints the site lines without the file's indent.
    assert in_order(each(TOPAS_SITES), [line.strip() for line in lines])
    assert in_order(each(TOPAS_EXCERPT), lines)

    notes: list = []
    model = rx.read_project_model(path, diagnostics=notes)
    assert model.format.name == "topas_inp"
    assert model.stated.data_files == ["refined.xye"]
    assert (model.stated.background_terms, model.stated.background_refined) == (6, True)
    cons = TopasConstraints()
    back = rx.Refinement(model.to_structure(scale="rietx", constraints=cons),
                         rx.Instrument.bragg_brentano(radiation="CuKa"))
    apply_ties(back, cons)
    assert free_paths(back)[:4] == [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale", "phases.0.extinction"]
    # The oxygens' shared name came back as a tie: two of the three are not free.
    assert OXYGENS[0] in free_paths(back) and not set(OXYGENS[1:]) & set(free_paths(back))
    assert [d.code for d in model.diagnostics] == ["TOPAS_FEATURES_NOT_IMPORTED"] * 2
    # topas.md quotes this message after the file's own path.
    assert model.diagnostics[0].message.endswith(
        "this import is partial. The file states peak profile (Finger_et_al, peak_type, "
        "pv_fwhm, pv_lor) [fluorapatite]; phase scaling (scale_pks) [fluorapatite], and none "
        "of it reaches the built structure.")


def gsas_exp_page() -> None:
    """The GSAS experiment file, read for its free set."""
    model = rx.read_project_model(examples_dir() / "FAP.EXP")
    assert (model.format.name, model.stated.rwp, model.stated.rp) == ("gsas_exp", 0.1005, 0.0766)
    assert (model.stated.n_variables, model.stated.n_observations) == (28, 5750)
    assert model.stated.profile().refined_names == ("LX", "LY", "shft")
    structure_only = rx.Refinement(model.to_structure(),
                                   rx.Instrument.bragg_brentano(radiation="CuKa"))
    assert len(free_paths(structure_only)) == 21
    assert [d.code for d in model.diagnostics] == ["GSAS_EXP_BACKGROUND_NOT_CARRIED"]
    # gsas2.md quotes this message after the file's own path.
    assert model.diagnostics[0].message.endswith(
        "histogram 1 fitted GSAS background function 5 (reciprocal expansion in Q², for "
        "low-angle air scatter) with 3 terms. The coefficients are on "
        "model.histograms[...].background.")


def fullprof_page(out: Path) -> None:
    """One codeword for each free parameter, and the same free set read back."""
    structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
    phase = structure.phases[0]
    phase.cell.a.vary = phase.cell.c.vary = phase.scale.vary = True
    phase.atoms[0].biso.vary = True
    phase.atoms[6].z.vary = True
    path = out / "flags.pcr"
    rx.write_fullprof_pcr(structure, path)
    assert in_order(PCR, lines_of(path))

    model = rx.read_project_model(path)
    ref = rx.Refinement(model.to_structure(), rx.Instrument.bragg_brentano(radiation="CuKa"))
    expected = [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale", "phases.0.atoms.0.biso",
        "phases.0.atoms.6.dof.0", "phases.0.atoms.6.dof.1", "phases.0.atoms.6.dof.2"]
    assert free_paths(ref) == expected

    # fullprof.md: the reader also accepts b sharing a's codeword, by hand or
    # as FullProf rewrites it (b and gamma on a's).
    text = path.read_text(encoding="utf-8")
    for codes in ("41.0 41.0 51.0 0.0 0.0 0.0", "41.0 41.0 51.0 0.0 0.0 41.0"):
        shared = out / "shared.pcr"
        shared.write_text(text.replace(PCR[-1][-1], codes), encoding="utf-8")
        model = rx.read_project_model(shared)
        back = rx.Refinement(model.to_structure(),
                             rx.Instrument.bragg_brentano(radiation="CuKa"))
        assert free_paths(back) == expected


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        gsas2_page(out)
        topas_page(out)
        gsas_exp_page()
        fullprof_page(out)
    print("every figure the Switching pages quote reproduced")


if __name__ == "__main__":
    main()
