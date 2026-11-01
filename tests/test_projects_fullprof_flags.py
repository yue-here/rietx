"""The ``.pcr`` control-line flags read at every value the FullProf manual defines.

``Nor``, ``Dum``, ``Opt`` and ``Nre`` (Rodríguez-Carvajal, *An Introduction to
the Program FullProf 2000*, July 2001, pp. 68-70), the analytic backgrounds
``Nba = 0, -1, -3, -4, -5`` (pp. 69-70, 85-86 and FullProf's release notes),
and the two line widths the manual states and FullProf's own example files
write (LINE 8's nine reals, LINE 30's six under ``Npr != 7``). Every fixture is
``test_projects_fullprof``'s, with the one field under test changed, so each
case is a **twin**: a file that differs from one that already reads in that
field alone must read to the same :class:`~rietx.schemas.Structure` apart from
what the field states. The negative arm of each is a planted value the manual
does not define, or a count the file does not satisfy, refused by name.
"""

import re

import pytest

from rietx.io.projects.fullprof import (
    FullProfPcrError,
    read_fullprof_pcr,
    to_structure,
)
from tests.test_projects_fullprof import _PHASE_SITES, _RANGE, _pcr, _phase

_CONTROL = ("job npr nph nba nex nsc nor dum iwg ilo ias res ste nre cry uni "
            "cor opt aut").split()

#: The fixture's two background points (corpus file 2's, cut to two).
_POINTS = ("        12.9000       952.8345         91.00\n"
           "        16.4000       977.2739        101.00\n")

#: The fixture's zero-shift line, after which LINE 17 sits.
_ZERO = " -0.03994  601.0  0.00000    0.0  0.00000    0.0 2.370100    0.00   0\n"


def _coefficients(n: int, first: int = 9) -> str:
    """``n`` LINE-17 groups: six values, then their six codewords, each line.

    The first group's codewords refine parameters ``first`` …, so the
    background coefficients carry parameter numbers like the points they
    replace (9 and 10 in the twin)."""
    lines = []
    for g in range(n):
        lines.append("  " + "  ".join(f"{100.0 * g + j + 1:10.3f}" for j in range(6)))
        codes = [f"{10.0 * (first + j) + 1:10.2f}" if g == 0 and j < 2 else
                 f"{0.0:10.2f}" for j in range(6)]
        lines.append("  " + "  ".join(codes))
    return "\n".join(lines) + "\n"


def _file(tmp_path, name="flags.pcr", *, phase=None, trailing=_RANGE,
          background=None, **control):
    """The fixture with ``control`` fields set by name and LINE 17 inserted."""
    path = _pcr(tmp_path, name, phase or _phase(), trailing=trailing)
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith("!Job Npr"))
    fields = dict(zip(_CONTROL, lines[at + 1].split(), strict=True))
    fields.update({k: str(v) for k, v in control.items()})
    lines[at + 1] = "   " + "   ".join(fields[k] for k in _CONTROL)
    text = "\n".join(lines)
    if background is not None:
        text = text.replace(_POINTS, "").replace(_ZERO, _ZERO + background)
    path.write_text(text, encoding="utf-8")
    return path


def _structure(path, **kw):
    return to_structure(read_fullprof_pcr(path), **kw)


def _dump(structure) -> dict:
    return structure.model_dump(mode="json")


# ------------------------------------------------------------- Dum and Opt


@pytest.mark.parametrize("field, value", [
    ("dum", 1), ("dum", 2), ("dum", 3), ("opt", 1)])
def test_a_flag_with_no_model_effect_is_recorded_and_moves_nothing(
        tmp_path, field, value):
    """``Dum`` (p. 68: convergence and R_Bragg bookkeeping) and ``Opt`` (p. 68:
    faster code paths) add no line and change no model. The twin reads to the
    same Structure, and the value is on the model."""
    twin = _dump(_structure(_file(tmp_path, "zero.pcr")))
    model = read_fullprof_pcr(_file(tmp_path, **{field: value}))
    assert model.control[field] == value
    assert _dump(to_structure(model)) == twin


@pytest.mark.parametrize("field, value", [
    ("dum", 4), ("dum", -1), ("opt", 2), ("nor", 2), ("nor", -1)])
def test_a_value_the_manual_does_not_define_is_refused_by_name(
        tmp_path, field, value):
    with pytest.raises(FullProfPcrError,
                       match=f"{field.capitalize()} = {value}.*defines"):
        read_fullprof_pcr(_file(tmp_path, **{field: value}))


# --------------------------------------------------------------------- Nor


def _pref(pref1="0.00000", pref2="0.00000", code1="0.00", code2="0.00") -> str:
    return _phase().replace(
        "  0.00000  0.00000  0.02000  0.00000  0.00000  0.00000  0.03000  0.03000\n"
        "     0.00     0.00    81.00",
        f"  {pref1}  {pref2}  0.02000  0.00000  0.00000  0.00000  0.03000  0.03000\n"
        f"     {code1}     {code2}    81.00")


def test_nor_0_at_g1_zero_held_reads_as_no_orientation(tmp_path):
    """The positive arm of the refused refine flag: G1 = 0 held, P = 1."""
    twin = _dump(_structure(_file(tmp_path, "nor0.pcr")))
    assert _dump(_structure(_file(tmp_path, nor=0, phase=_pref()))) == twin


def test_nor_1_at_its_identity_reads_as_the_nor_0_twin(tmp_path):
    """G1 = 1 is "no preferred orientation" under Nor = 1 as G1 = 0 is under
    Nor = 0 (manual p. 112), so the two files are one structure."""
    twin = _dump(_structure(_file(tmp_path, "nor0.pcr")))
    assert _dump(_structure(_file(tmp_path, nor=1, phase=_pref("1.00000")))) == twin


@pytest.mark.parametrize("code, vary", [("0.00", False), ("111.00", True)])
def test_nor_1_is_march_dollase_with_r_g1(tmp_path, code, vary):
    """Eq. 3.32 at G2 = 0 is the March-Dollase factor with r = G1: the twin's
    Structure plus exactly that block, on the phase's Pr1 Pr2 Pr3 axis
    (0 0 1 in the fixture) and with Pref1's own refine flag."""
    twin = _dump(_structure(_file(tmp_path, "nor0.pcr")))
    built = _dump(_structure(_file(tmp_path, nor=1,
                                   phase=_pref("0.85000", code1=code))))
    po = built["phases"][0].pop("preferred_orientation")
    twin["phases"][0].pop("preferred_orientation")
    assert built == twin
    assert tuple(po["axis"]) == (0, 0, 1)
    assert po["r"]["value"] == 0.85
    assert po["r"]["vary"] is vary


@pytest.mark.parametrize("nor, pref1, pref2, match", [
    # G2, the untextured fraction, has no rietx term.
    (1, "0.85000", "0.20000", "Pref2 = 0.2.*untextured"),
    # The exponential function rietx does not have: before this reader read
    # Nor, a non-zero Pref1 under Nor = 0 was built without it, in silence.
    (0, "0.30000", "0.00000", "Nor = 0 with Pref1 = 0.3.*exponential"),
    # G1 = 0 is P = 1, but a refine flag on it reaches nothing rietx builds.
    (0, "0.00000", "0.00000", "Nor = 0 with Pref1 = 0 refined.*exponential"),
    # G1 divides eq. 3.32; the schema would clamp it onto its pole guard.
    (1, "-0.5000", "0.00000", "Pref1 = -0.5.*positive"),
])
def test_a_preferred_orientation_rietx_cannot_state_is_refused(
        tmp_path, nor, pref1, pref2, match):
    # The G1 = 0 row carries the refine flag; the others state it held.
    code1 = "111.00" if (nor, pref1) == (0, "0.00000") else "0.00"
    path = _file(tmp_path, nor=nor, phase=_pref(pref1, pref2, code1=code1))
    with pytest.raises(FullProfPcrError, match=match):
        _structure(path)


#: FullProf 8.20 (fp2k, run as a black box on this fixture, Job 3, March-Dollase
#: r = G1 = 0.6) intensity of each reflection under ``Nor = 1`` over the same
#: file's ``Nor = 0`` intensity, i.e. P(hkl) as FullProf applied it, to the
#: five digits the profile file prints. The 50 reflections above 100
#: counts agree with the orbit-averaged P below to 1.1e-4 for the axes
#: (1 0 0), (0 0 1), (1 1 0) and (1 0 1); the representative-only P is off by
#: 0.8 to 1.9 on the first, third and fourth, and (1 0 1) read as a direct-space
#: direction is off by 1.9.
_FULLPROF_P = {
    (1, 0, 0): {(0, 0, 2): 0.46477, (1, 0, 1): 1.14782, (1, 1, 0): 0.98033,
                (2, 1, 0): 1.32102, (1, 1, 3): 0.60812, (3, 1, 0): 1.7174,
                (2, 2, 3): 0.77845, (1, 0, 5): 0.50005},
    (1, 0, 1): {(0, 0, 2): 0.63156, (1, 0, 1): 1.57414, (1, 1, 0): 0.79279,
                (2, 1, 0): 0.89983, (1, 1, 3): 0.82662, (3, 1, 0): 0.99781,
                (2, 2, 3): 0.86908, (1, 0, 5): 0.70434},
}


@pytest.mark.parametrize("axis", sorted(_FULLPROF_P))
def test_nor_1_reproduces_the_preferred_orientation_fullprof_applied(
        tmp_path, axis):
    """The mapping Pref1 -> r and Pr1 Pr2 Pr3 -> axis, measured against the
    program rather than read from the manual's eq. 3.32. The two things the
    manual does not show are whether FullProf averages P over a reflection's
    symmetry equivalents, as rietx does, and in which basis it reads the axis:
    (2 1 0) and (3 1 0) sit in orbits whose members make different angles to
    (1 0 0), and (1 0 1) is a different direction in the reciprocal lattice
    than in the direct one when a != c (here 5.0 and 9.0 A)."""
    import numpy as np

    from rietx.crystallography.lattice import reciprocal_metric_tensor
    from rietx.crystallography.symmetry import reflection_orbits
    from rietx.model.preferred_orientation import march_dollase_factors, orbit_layout

    phase = _pref("0.60000").replace(
        " 0.0 0.0 1.0 ", " %.1f %.1f %.1f " % tuple(map(float, axis)))
    built = _structure(_file(tmp_path, nor=1, phase=phase)).phases[0]
    po = built.preferred_orientation
    assert tuple(po.axis) == axis and po.r.value == 0.6
    cell = built.cell
    gstar = reciprocal_metric_tensor(cell.a.value, cell.b.value, cell.c.value,
                                     90.0, 90.0, 90.0)
    reps = np.array(sorted(_FULLPROF_P[axis]))
    members, seg, counts = orbit_layout(
        reflection_orbits(str(built.space_group), reps))
    p = march_dollase_factors(members, seg, counts, np.array(axis, float),
                              gstar, po.r.value)
    expected = [_FULLPROF_P[axis][tuple(h)] for h in reps]
    np.testing.assert_allclose(p, expected, rtol=5e-4)


def test_a_non_integral_preferred_orientation_axis_is_refused(tmp_path):
    phase = _pref("0.85000").replace(" 0.0 0.0 1.0 ", " 0.5 0.0 1.0 ")
    with pytest.raises(FullProfPcrError, match="Pr1 Pr2 Pr3.*not integral"):
        _structure(_file(tmp_path, nor=1, phase=phase))


# --------------------------------------------------------------------- Nre

#: LINE 47 (p. 126): NUMPAR LowLIMIT HighLIMIT Step IBOUND NAMPAR. Parameters 7
#: (the scale) and 2 (U) are refined by the fixture's codewords.
_LIMITS = ("! Limits for selected parameters:\n"
           "   7      1.0000     10.0000      0.0000   0  Scale_ph1\n"
           "   2     -1.0000      1.0000      0.0000   0  U_ph1\n")


def test_nre_limits_are_read_and_reported_not_applied(tmp_path):
    """Neither of the fixture's two limits maps, so the Structure is the
    twin's and each limit is said once, with its reason: a scale is never in
    FullProf's units, and U builds no entry (no instrument from a .pcr)."""
    twin = _dump(_structure(_file(tmp_path, "nre0.pcr")))
    model = read_fullprof_pcr(_file(tmp_path, nre=2, trailing=_LIMITS + _RANGE))
    assert [(lim.number, lim.low, lim.high, lim.ibound, lim.name)
            for lim in model.parameter_limits] == [
        (7, 1.0, 10.0, 0, "Scale_ph1"), (2, -1.0, 1.0, 0, "U_ph1")]
    assert model.fitted_range == (9.0, 157.0, 1.0)
    diagnostics: list = []
    assert _dump(to_structure(model, diagnostics=diagnostics)) == twin
    scale, u = [d for d in diagnostics if d.code == "FULLPROF_LIMITS_NOT_APPLIED"]
    assert (scale.level, scale.where, scale.value) == ("info", ["phases.0.scale"], 5.0)
    assert "[1, 10] on parameter 7 (Scale_ph1)" in scale.message
    assert "phase 1 Scale = 5" in scale.message
    assert "scale never maps" in scale.message
    assert (u.level, u.where, u.value) == ("info", [], 0.4)
    assert "[-1, 1] on parameter 2 (U_ph1)" in u.message
    assert "builds no entry" in u.message


def _limit(number: int, low: float, high: float, ibound: int = 0,
           name: str = "P") -> str:
    """One LINE-47 line under the comment FullProf writes above them."""
    return ("! Limits for selected parameters:\n"
            f"  {number:2d}  {low:10.4f}  {high:10.4f}      0.0000   {ibound}  {name}\n")


def _sites(**codes) -> str:
    """The fixture's four sites with the named sites' codeword lines
    (``x y z Biso Occ``) replaced; every other site stays held."""
    lines = _PHASE_SITES.split("\n")
    for i in range(0, len(lines), 2):
        label = lines[i].split()[0]
        if label in codes:
            lines[i + 1] = "        " + "".join(
                f"{float(c):9.2f}" for c in codes[label].split())
    return "\n".join(lines)


def _with_and_without(tmp_path, limit: str, *, phase=None, **control):
    """The file read with one limit, and the same file with none: its twin."""
    twin = _dump(_structure(_file(tmp_path, "twin.pcr", phase=phase, **control)))
    diagnostics: list = []
    built = _structure(_file(tmp_path, nre=1, phase=phase, trailing=limit + _RANGE,
                             **control), diagnostics=diagnostics)
    found = [d for d in diagnostics if "LIMIT" in d.code]
    return twin, built, found


def _entry(dump: dict, path: str) -> dict:
    for part in path.split("."):
        dump = dump[int(part)] if part.isdigit() else dump[part]
    return dump


_CR_BISO = _sites(Cr="0 0 0 111 0")

#: (the limit, the file's own changes, the entry it bounds). Each value is the
#: first from the top carrying its parameter number, at multiplier +1, in
#: FullProf's own units.
_MAPPED = [
    # cell a, parameter 5 (51.00 on a and b): b is rietx's tie under P 42/m n m.
    (_limit(5, 4.9, 5.1), {}, "phases.0.cell.a"),
    # c = 9.0 on its own upper limit: applied, and FullProf's answer rested on it.
    (_limit(6, 8.5, 9.0), {}, "phases.0.cell.c"),
    # Biso is B in both programs, no 8pi^2.
    (_limit(11, 0.1, 0.5), {"phase": _phase(atoms=_CR_BISO)},
     "phases.0.atoms.0.biso"),
    # March r is Pref1 under Nor = 1.
    (_limit(11, 0.5, 2.0), {"nor": 1, "phase": _pref("0.85000", code1="111.00")},
     "phases.0.preferred_orientation.r"),
]


@pytest.mark.parametrize("limit, changes, path", _MAPPED,
                         ids=["cell-a", "cell-c-on-limit", "biso", "march-r"])
def test_a_limit_fullprof_maps_is_the_entry_s_bound(tmp_path, limit, changes, path):
    """FullProf's manual, p. 126: the limit belongs to the first value from the
    top with the parameter's codeword, at a positive unit multiplier. The
    Structure is its twin's but for that one entry's min and max, and nothing
    is reported. On main the limit set no bound."""
    twin, built, found = _with_and_without(tmp_path, limit, **changes)
    low, high = (float(x) for x in limit.split("\n")[1].split()[1:3])
    dump = _dump(built)
    entry = _entry(dump, path)
    assert (entry["min"], entry["max"]) == (low, high)
    # the twin with that one entry bounded, and nothing else moved
    expected = _entry(twin, path)
    expected["min"], expected["max"] = low, high
    assert dump == twin
    assert found == []


def test_a_limit_goes_to_the_first_value_carrying_its_number(tmp_path):
    """Cr and W share parameter 11 on Biso (a +1 tie rietx reports and does
    not carry). Cr is first from the top, so its Biso takes the limit and W's
    does not; and where the first carries multiplier 2, no value takes it,
    though a later one carries +1."""
    from rietx.io.projects.fullprof import limit_readings

    limit = _limit(11, 0.1, 0.5)
    _, built, found = _with_and_without(
        tmp_path, limit, phase=_phase(atoms=_sites(Cr="0 0 0 111 0", W="0 0 0 111 0")))
    cr, w = built.phases[0].atoms[0].biso, built.phases[0].atoms[1].biso
    assert (cr.min, cr.max) == (0.1, 0.5)
    assert (w.min, w.max) == (-float("inf"), float("inf"))
    assert found == []

    path = _file(tmp_path, "second.pcr", nre=1, trailing=limit + _RANGE,
                 phase=_phase(atoms=_sites(Cr="0 0 0 112 0", W="0 0 0 111 0")))
    [reading] = limit_readings(read_fullprof_pcr(path))
    assert reading.label == "phase 1 atom 'Cr' biso"
    assert not reading.applied and "multiplier +2" in reading.reason


#: (the limit, the file's own changes, the reason's words, the where path).
_NOT_MAPPED = [
    # Root CLAUDE.md's bound rule: March r has a pole at 0 ...
    (_limit(11, 0.0, 2.0), {"nor": 1, "phase": _pref("0.85000", code1="111.00")},
     "March r's pole at 0", ["phases.0.preferred_orientation.r"]),
    # ... and W at 0 puts Gamma_G^2 under its clamp, the U, V, W columns zero.
    (_limit(4, 0.0, 1.0), {}, "Caglioti W at 0", []),
    # The file's Occ is multiplicity-scaled; the built occ is a fraction.
    (_limit(11, 0.4, 0.6), {"phase": _phase(atoms=_sites(Cr="0 0 0 0 111"))},
     "occupancy never maps", ["phases.0.atoms.0.occ"]),
    # A coordinate refines through its site's DOFs; a bound on x binds nothing.
    (_limit(11, 0.3, 0.4), {"phase": _phase(atoms=_sites(O1="111 111 0 0 0"))},
     "displacement DOFs", ["phases.0.atoms.2.x"]),
    # The manual's mapping needs a unit multiplier.
    (_limit(11, 0.1, 0.5), {"phase": _phase(atoms=_sites(Cr="0 0 0 112 0"))},
     "multiplier +2", ["phases.0.atoms.0.biso"]),
    # A periodic boundary is not a box, and FullProf's least squares under it
    # is unmeasured.
    (_limit(5, 4.9, 5.1, ibound=1), {}, "periodic", ["phases.0.cell.a"]),
    # FullProf refines b on its own number; rietx ties b to a under P 42/m n m.
    (_limit(12, 4.9, 5.1), {"phase": _phase(
        cell_codes="   51.00000  121.00000   61.00000    0.00000    0.00000    0.00000")},
     "ties cell b to cell a", ["phases.0.cell.b"]),
    # A background point builds no entry.
    (_limit(9, 900.0, 1000.0), {}, "builds no entry", []),
]


@pytest.mark.parametrize("limit, changes, why, where", _NOT_MAPPED, ids=[
    "r-at-0", "w-at-0", "occ", "coordinate", "multiplier", "ibound-1",
    "symmetry-tied-b", "background-point"])
def test_a_limit_that_does_not_map_is_reported_with_its_reason(
        tmp_path, limit, changes, why, where):
    """Not applied, the Structure is its twin's, and the limit is said once at
    info with the reason, since the file's own value is inside it. On main one
    diagnostic listed every limit and gave no reason."""
    twin, built, found = _with_and_without(tmp_path, limit, **changes)
    assert _dump(built) == twin
    [d] = found
    assert (d.code, d.level, d.where) == ("FULLPROF_LIMITS_NOT_APPLIED", "info", where)
    assert why in d.message


#: (the limit, the file's own changes, the reason's words, the file's value).
_BINDING = [
    # The scale is 5.0, on the limit's upper end: never maps, and the file's
    # answer rested on the limit.
    (_limit(7, 1.0, 5.0), {}, "scale never maps", 5.0),
    # W is 0.1, on its lower end; no instrument is built from a .pcr.
    (_limit(4, 0.1, 1.0), {}, "builds no entry", 0.1),
    # a = 5.0 below the limit: the file was not refined under it, and a bound
    # there would refuse the value itself.
    (_limit(5, 5.1, 5.2), {}, "lies outside it", 5.0),
]


@pytest.mark.parametrize("limit, changes, why, value", _BINDING,
                         ids=["scale", "w", "outside"])
def test_a_limit_the_file_s_value_sits_on_is_a_warning(
        tmp_path, limit, changes, why, value):
    """FullProf clamps in least squares (fp2k 8.20 on its own ce1.pcr held cell
    a at 5.40500 A, its limit, against an unlimited 5.41222; docs/practice.md),
    so a value on its limit is an answer that rested on it. Not carrying that
    limit is a warning, under its own code, since one code has one level. On
    main it was the one info diagnostic."""
    twin, built, found = _with_and_without(tmp_path, limit, **changes)
    assert _dump(built) == twin
    [d] = found
    assert (d.code, d.level, d.value) == (
        "FULLPROF_BINDING_LIMIT_NOT_APPLIED", "warning", value)
    assert why in d.message and "sits on that limit" in d.message


@pytest.mark.parametrize("nre, trailing, match", [
    # One line short: the fitted-range line is read as the third limit, and its
    # interval (157, 1) is inverted.
    (3, _LIMITS + _RANGE, "Nre = 3.*inverted"),
    # One line over: the second limit is then a second fitted range.
    (1, _LIMITS + _RANGE, "2 fitted-range lines"),
    # A limit on a parameter no codeword refines limits nothing.
    (1, "  33      0.0000      1.0000      0.0000   0  X\n" + _RANGE,
     "parameter 33, which no codeword"),
    # One line short with no range line after it: the count itself is short.
    (3, _LIMITS, "Nre = 3 declares 3 parameter-limit lines.*the file has 2"),
])
def test_an_nre_count_the_file_does_not_satisfy_is_refused(
        tmp_path, nre, trailing, match):
    with pytest.raises(FullProfPcrError, match=match):
        read_fullprof_pcr(_file(tmp_path, nre=nre, trailing=trailing))


def test_a_negative_nre_is_refused(tmp_path):
    with pytest.raises(FullProfPcrError, match="Nre = -1 — a parameter-limit"):
        read_fullprof_pcr(_file(tmp_path, nre=-1))


# --------------------------------------------------------------------- Nba


@pytest.mark.parametrize("nba, groups, kind", [
    (0, {"back": 6}, "polynomial_6"),
    (-1, {"back": 6, "bc": 6, "d": 6}, "polynomial_6_debye"),
    (-3, {"back": 12}, "polynomial_12"),
    (-4, {"back": 18}, "fourier_cosine_18"),
    (-5, {"back": 24}, "chebyshev_24"),
])
def test_an_analytic_background_is_read_after_the_zero_line(
        tmp_path, nba, groups, kind):
    """LINE 17 sits after LINE 14, six values then six codewords per group;
    the coefficients and their codewords are on the model, the parameter
    numbers they refine are the file's, and the structure is the
    interpolated-point twin's — no background is built from a ``.pcr``."""
    twin = _dump(_structure(_file(tmp_path, "nba2.pcr")))
    n = sum(groups.values()) // 6
    model = read_fullprof_pcr(_file(tmp_path, nba=nba,
                                    background=_coefficients(n)))
    assert model.background_kind == kind
    assert model.background == []
    assert {k: len(v) for k, v in model.background_coefficients.items()} == groups
    first = model.background_coefficients["back"]
    assert [v.value for v in first[:2]] == [1.0, 2.0]
    assert [v.code.number for v in first[:2]] == [9, 10]
    assert {9, 10} <= model.parameter_numbers
    assert _dump(to_structure(model)) == twin


def test_the_interpolated_points_keep_their_kind(tmp_path):
    model = read_fullprof_pcr(_file(tmp_path))
    assert model.background_kind == "linear_interpolation"
    assert model.background_coefficients == {}
    assert len(model.background) == 2


def test_a_background_line_of_the_wrong_width_is_refused(tmp_path):
    short = _coefficients(1).replace("     6.000\n", "\n", 1)
    with pytest.raises(FullProfPcrError, match="expected 6 numbers, found 5"):
        read_fullprof_pcr(_file(tmp_path, nba=0, background=short))


def test_a_twelve_term_fourier_background_is_refused_at_its_third_group(tmp_path):
    """The 2001 release note gives Nba = -4 twelve terms, and FullProf 8.20
    writes eighteen in every example file; a file of the first count meets the
    phase's name where the third group should be, and is refused there."""
    with pytest.raises(FullProfPcrError, match=r"group 3 of 3"):
        read_fullprof_pcr(_file(tmp_path, nba=-4, background=_coefficients(2)))


# ------------------------------------------------- the manual's line widths


def test_a_nine_field_lambda_line_reads(tmp_path):
    """LINE 8 is "9 reals" (p. 75); ``2nd-muR`` is a later tenth field."""
    path = _file(tmp_path)
    text = path.read_text(encoding="utf-8").replace(
        "160.00    0.0000  0.2160\n", "160.00    0.0000\n")
    path.write_text(text, encoding="utf-8")
    model = read_fullprof_pcr(path)
    assert "mur2" not in model.pattern
    assert model.lambda1 == 2.0771
    assert _dump(to_structure(model)) == _dump(_structure(_file(tmp_path, "t.pcr")))


def test_a_negative_wavelength_ratio_is_refused_by_name(tmp_path):
    path = _file(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace(
        "2.077100  0.50000", "2.077100 -0.50000"), encoding="utf-8")
    with pytest.raises(FullProfPcrError, match="Ratio = -0.5.*LINE 32"):
        read_fullprof_pcr(path)


def test_a_six_value_pref_asy_line_reads_under_a_non_fcj_profile(tmp_path):
    """LINE 30 is six reals, plus S_L and D_L only for Npr = 7 (p. 109)."""
    phase = _phase().replace("963.500   0   7   0", "963.500   0   5   0").replace(
        "0.00000  0.03000  0.03000\n     0.00     0.00    81.00     0.00     0.00"
        "     0.00     0.00     0.00",
        "0.00000\n     0.00     0.00    81.00     0.00     0.00     0.00")
    model = read_fullprof_pcr(_file(tmp_path, phase=phase))
    profile = model.phases[0].profile
    assert profile["asy1"].value == 0.02 and profile["asy1"].code.number == 8
    assert "s_l" not in profile


@pytest.mark.parametrize("npr", [4, 8])
def test_a_profile_adding_a_shape_line_is_refused(tmp_path, npr):
    phase = _phase().replace("963.500   0   7   0", f"963.500   0   {npr}   0")
    with pytest.raises(FullProfPcrError, match=f"Npr = {npr}.*LINE 33"):
        read_fullprof_pcr(_file(tmp_path, phase=phase))


def test_a_strain_model_adding_lines_is_refused(tmp_path):
    phase = _phase().replace("0.00000   0.00000       0\n",
                             "0.00000   0.00000      11\n", 1)
    with pytest.raises(FullProfPcrError, match="Strain-Model = 11"):
        read_fullprof_pcr(_file(tmp_path, phase=phase))


# --------------------------------------------- still refused: the negative arm


@pytest.mark.parametrize("field, value, match", [
    ("cry", 1, "Cry = 1"), ("res", 1, "Res = 1"), ("uni", 1, "Uni = 1"),
    ("job", -1, "Job = -1"), ("nba", 1, "Nba = 1.*CODFIL.bac"),
    # The manual's p. 69: 3 is pattern calculation, not time of flight.
    ("job", 3, r"Job = 3 \(pattern calculation, neutron constant wavelength\)")])
def test_what_stays_out_of_scope_is_still_refused_by_name(
        tmp_path, field, value, match):
    with pytest.raises(FullProfPcrError, match=match):
        read_fullprof_pcr(_file(tmp_path, **{field: value}))


def test_the_fixture_header_is_the_one_these_twins_edit():
    """Guards the string surgery above: if the shared fixture moves, these
    tests must fail here rather than pass on an unedited file."""
    from tests.test_projects_fullprof import _HEADER
    assert _POINTS in _HEADER and _ZERO in _HEADER
    assert re.search(r"2\.077100 2\.077100  0\.50000", _HEADER)
