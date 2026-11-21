"""WP-1314 — the Jana ``.m50``/``.m40``/``.m41`` reader, on synthetic sets.

No licence-clean Jana file exists to vendor: Jana2020's licence covers the
program and its documentation and says nothing about example data, the
Jana2000 manual's example archives state no terms, and a bounded sweep of the
private archive found no m-file at all (the WP's Context).  So every set here
is **synthesized from the specification** (Jana98 manual Table 9 and Table 10,
Jana2000 manual pp. 50-54) by the writer below, which spells the layout out
literally rather than importing anything from the reader.

The structures are invented for the test: a Pbam phase whose four sites sit on
Wyckoff 2a, 4g, 4h and 8i (so ai = 1/4, 1/2, 1/2 and 1 for a full site), and
rock-salt NaCl in Fm-3m.
"""

from __future__ import annotations

import gemmi
import pytest

from rietx.io.projects import jana
from rietx.schemas.common import Diagnostic

PBAM_OPS = ["x y z", "x y -z", "1/2-x 1/2+y z", "1/2-x 1/2+y -z"]


def _num(v: float) -> str:
    """Jana's value field as the manuals' listings show it: nine characters,
    as many decimals as fit, a positive keeping one blank in front (``90.00000``)
    and a negative filling the field, so it fuses (``0.500000-0.063340``)."""
    room = 9 if v < 0 else 8
    for d in range(6, -1, -1):
        text = f"{v:.{d}f}"
        if len(text) <= room:
            return text.rjust(9)
    raise ValueError(v)


def _keyed(values, keys: str) -> str:
    return "".join(_num(v) for v in values).ljust(60) + keys


def _fm3m_ops() -> list[str]:
    """Fm-3m's operators without centring or inversion, as Jana lists them."""
    sg = gemmi.SpaceGroup("F m -3 m")
    seen, out = set(), []
    for op in sg.operations().sym_ops:
        rot = tuple(map(tuple, op.rot))
        neg = tuple(tuple(-c for c in row) for row in op.rot)
        if rot in seen or neg in seen:
            continue
        seen.add(rot)
        out.append(op.triplet().replace(",", " "))
    return out


def m50(*, extra_global: str = "", extra_phase: str = "", refine: str = "autkeys 0",
        two_phase: bool = True) -> str:
    lines = ["title synthetic WP-1314 set",
             "lambda 1.5406 radtype 1 lpfactor 1 monangle 0",
             extra_global,
             "-" * 40,
             "phase Alpha" if two_phase else "",
             "cell 8.1 9.2 4.3 90 90 90",
             "esdcell 0 0 0 0 0 0",
             "spgroup Pbam 55 3",
             "centro",
             "lattice P"]
    lines += [f"symmetry {op}" for op in PBAM_OPS]
    lines += ["unitsnumb 4", "chemform Ba1Ti2O6",
              "atom Ba", "atweight 137.33 f' -0.2 f\" 2.0",
              "atom Ti", "atweight 47.867",
              "atom O", "atweight 15.999",
              extra_phase]
    if two_phase:
        lines += ["-" * 40, "phase NaCl", "cell 5.64 5.64 5.64 90 90 90",
                  "spgroup Fm-3m 225 7", "centro", "lattice F"]
        lines += [f"symmetry {op}" for op in _fm3m_ops()]
        lines += ["atom Na", "atom Cl"]
    lines += ["end", "*" * 60, "refine", refine, "end"]
    return "\n".join(line for line in lines if line is not None) + "\n"


def m40(*, two_phase: bool = True, header_a: str = "    4    0    0    0",
        ba_line: str | None = None, ti_adp: str | None = None) -> str:
    lines = [header_a]
    if two_phase:
        lines.append("    2    0    0    0")
    lines += [_keyed([0.84, 0, 0, 0, 0, 0.16], "100001"),
              _num(0.0),
              _keyed([0] * 6, "000000"),
              _keyed([0] * 6, "000000")]
    # Ba on 2a (site order 4, ai 1/4), half occupied: ai = 0.125
    lines.append(ba_line or ("Ba1       1  1     " + "".join(
        _num(v) for v in (0.125, 0.0, 0.0, 0.0))))
    lines.append(_keyed([0.010, 0, 0, 0, 0, 0], "1111100000"))
    # Ti on 4g (x, y, 0; site order 2): ai = 0.5, anisotropic
    lines.append("Ti1       2  2     " + "".join(
        _num(v) for v in (0.5, 0.21, -0.36, 0.0)))
    lines.append(ti_adp or _keyed([0.011, 0.012, 0.013, 0.001, 0, 0], "0110111100"))
    # O on 4h (x, y, 1/2): ai = 0.5; negative coordinates fuse
    lines.append("O1        3  1     " + "".join(
        _num(v) for v in (0.5, -0.063340, -0.320221, 0.5)))
    lines.append(_keyed([0.02, 0, 0, 0, 0, 0], "0110100000"))
    # O on 8i, the general position: ai = 1
    lines.append("O2        3  1     " + "".join(
        _num(v) for v in (1.0, 0.11, 0.27, 0.23)))
    lines.append(_keyed([0.02, 0, 0, 0, 0, 0], "0111100000"))
    if two_phase:
        lines += ["Na1       1  1     " + "".join(_num(v) for v in (1 / 48, 0, 0, 0)),
                  _keyed([0.015, 0, 0, 0, 0, 0], "0000100000"),
                  "Cl1       2  1     " + "".join(_num(v) for v in (1 / 48, .5, .5, .5)),
                  _keyed([0.016, 0, 0, 0, 0, 0], "0000100000")]
    return "\n".join(lines) + "\n"


def m41(*, two_phase: bool = True) -> str:
    lines = ["bckgtype 1 bckgnum 3 manbckg 0 wtlebail 0",
             "phase Alpha" if two_phase else "",
             "proffun 3 asymm 0 strain 0 cutoff 8",
             "end", "*" * 60,
             "# Shift parameters - zero, sycos, sysin",
             _keyed([0.01, 0, 0], "100"),
             "# Background parameters",
             _keyed([100.0, -20.0, 3.0], "111")]
    blocks = [("Alpha", [8.11, 9.21, 4.31, 90, 90, 90], "111000")]
    if two_phase:
        blocks.append(("NaCl", [5.641, 5.641, 5.641, 90, 90, 90], "100000"))
    for name, cell, keys in blocks:
        if two_phase:
            lines.append(f"### phase {name}")
        lines += ["# Cell parameters - a,b,c,alpha,beta,gamma", _keyed(cell, keys),
                  "# Gaussian parameters - U,V,W,P", _keyed([30, -10, 20, 0], "1110")]
    return "\n".join(line for line in lines if line != "") + "\n"


def write_set(tmp_path, stem="syn", **kw):
    two = kw.pop("two_phase", True)
    texts = {".m50": kw.pop("m50", None) or m50(two_phase=two),
             ".m40": kw.pop("m40", None) or m40(two_phase=two),
             ".m41": kw.pop("m41", None) or m41(two_phase=two)}
    for suffix, text in texts.items():
        (tmp_path / f"{stem}{suffix}").write_text(text, encoding="utf-8")
    return tmp_path / f"{stem}.m50"


# --------------------------------------------------------------- reading

def test_a_two_phase_set_reads_what_the_files_state(tmp_path):
    model = jana.read_jana(write_set(tmp_path))
    assert [p.name for p in model.phases] == ["Alpha", "NaCl"]
    alpha = model.phases[0]
    assert alpha.space_group == "Pbam" and alpha.space_group_number == 55
    assert alpha.centro and alpha.symmetry[2] == "1/2-x,1/2+y,z"
    assert [t.symbol for t in alpha.atom_types] == ["Ba", "Ti", "O"]
    assert alpha.atom_types[0].values == {"atweight": 137.33, "f'": -0.2, 'f"': 2.0}
    assert model.wavelength == 1.5406 and model.radtype == 1 and model.autkeys == 0
    o1 = model.atoms[0][2]
    assert o1.xyz == (-0.06334, -0.320221, 0.5)  # fused negatives split
    assert o1.keys == (False, True, True, False, True) + (False,) * 5
    assert model.scale.values[-1] == 0.16 and model.scale.keys[0]
    assert model.m41_common["Background parameters"].values == [100.0, -20.0, 3.0]
    assert model.m41_phases[1].name == "NaCl"
    assert model.m41_phases[0].sections["Gaussian parameters - U,V,W,P"].values \
        == [30.0, -10.0, 20.0, 0.0]
    assert model.experiment == {"lpfactor": "1", "monangle": "0"}


@pytest.mark.parametrize("path", ["syn.m40", "syn.m41", "syn"])
def test_any_member_or_the_stem_opens_the_set(tmp_path, path):
    write_set(tmp_path)
    assert len(jana.read_jana(tmp_path / path).phases) == 2


def test_a_set_missing_its_m41_is_refused_by_name(tmp_path):
    write_set(tmp_path)
    (tmp_path / "syn.m41").unlink()
    with pytest.raises(jana.JanaError, match=r"needs \.m41"):
        jana.read_jana(tmp_path / "syn.m50")


def test_keywords_may_be_abbreviated_while_unique(tmp_path):
    text = m50().replace("unitsnumb 4", "units 4").replace("esdcell", "esdc")
    model = jana.read_jana(write_set(tmp_path, m50=text))
    assert model.phases[0].other["unitsnumb"] == "4"


# --------------------------------------------------------------- converting

def test_the_structure_carries_occupancy_symmetry_and_flags(tmp_path):
    model = jana.read_jana(write_set(tmp_path))
    diags: list[Diagnostic] = []
    s = jana.to_structure(model, phase="Alpha", diagnostics=diags)
    phase = s.phases[0]
    assert gemmi.SpaceGroup(phase.space_group).number == 55
    atoms = {a.label: a for a in phase.atoms}
    # ai x general multiplicity / site multiplicity (M98 p. 116)
    assert atoms["Ba1"].occ.value == pytest.approx(0.5)
    assert atoms["Ti1"].occ.value == pytest.approx(1.0)
    assert atoms["O1"].occ.value == pytest.approx(1.0)
    assert atoms["O2"].occ.value == pytest.approx(1.0)
    assert atoms["Ba1"].occ.vary and not atoms["O1"].occ.vary
    # Ba on 2a is fully fixed: its key is set, the coordinate is held
    assert not atoms["Ba1"].x.vary
    assert atoms["O2"].x.vary and atoms["O2"].z.vary
    assert atoms["Ba1"].biso.value == pytest.approx(0.010 * jana.EIGHT_PI_SQUARED)
    assert atoms["Ba1"].biso.vary
    assert atoms["Ti1"].aniso is not None and atoms["Ti1"].aniso.u12.value == 0.001
    assert atoms["Ti1"].aniso.u11.vary and not atoms["Ti1"].biso.vary
    cell = phase.cell
    assert [getattr(cell, n).value for n in ("a", "b", "c", "alpha", "beta", "gamma")] \
        == [8.11, 9.21, 4.31, 90.0, 90.0, 90.0]
    assert (cell.a.vary, cell.c.vary, cell.alpha.vary) == (True, True, False)
    (info,) = [d for d in diags if d.code == "JANA_NOT_CARRIED"]
    assert "Ba1" in info.message and "Gaussian parameters" in info.message
    assert "phase volume fractions" in info.message
    assert "f'" in info.message and 'f"' in info.message
    assert "the .m50 cell [8.1" in info.message
    assert "phases.0.atoms.0.x" in info.where


def test_the_cubic_phase_reads_its_setting_from_the_operators(tmp_path):
    s = jana.to_structure(jana.read_jana(write_set(tmp_path)), phase=1)
    phase = s.phases[0]
    assert gemmi.SpaceGroup(phase.space_group).number == 225
    # ai = 1/48 printed to six decimals: 0.020833 x 48 = 0.999984 lies within
    # 48 x 5e-7 of a full site, so it is read as full (and reported)
    assert [a.occ.value for a in phase.atoms] == [1.0, 1.0]
    assert phase.cell.a.vary and phase.cell.a.value == 5.641


def test_a_single_phase_set_needs_no_phase_lines(tmp_path):
    model = jana.read_jana(write_set(tmp_path, two_phase=False))
    assert [p.name for p in model.phases] == [None]
    s = jana.to_structure(model)
    assert s.phases[0].cell.a.value == 8.11 and s.phases[0].cell.a.vary


def test_several_phases_and_none_chosen_is_refused(tmp_path):
    with pytest.raises(jana.JanaError, match="pass phase="):
        jana.to_structure(jana.read_jana(write_set(tmp_path)))


def test_a_number_the_operators_contradict_is_refused(tmp_path):
    text = m50().replace("spgroup Pbam 55 3", "spgroup Pbam 62 3")
    with pytest.raises(jana.JanaError, match="its operators are"):
        jana.to_structure(jana.read_jana(write_set(tmp_path, m50=text)), phase=0)


# --------------------------------------------------------------- diagnostics

def test_automatic_keys_are_reported_unless_stated_off(tmp_path):
    diags: list[Diagnostic] = []
    jana.read_jana(write_set(tmp_path, m50=m50(refine="autkeys 1")), diagnostics=diags)
    assert [d.code for d in diags] == ["JANA_KEYS_MAY_BE_IGNORED"]
    diags.clear()
    jana.read_jana(write_set(tmp_path, stem="b", m50=m50(refine="")), diagnostics=diags)
    assert [d.code for d in diags] == ["JANA_KEYS_MAY_BE_IGNORED"]
    diags.clear()
    jana.read_jana(write_set(tmp_path, stem="c"), diagnostics=diags)
    assert diags == []


def test_constraint_commands_are_reported_not_carried(tmp_path):
    diags: list[Diagnostic] = []
    text = m50(refine="autkeys 0\nrestric O1 1\nequation : x[O1]=x[O2]")
    model = jana.read_jana(write_set(tmp_path, m50=text), diagnostics=diags)
    assert len(model.constraints) == 2
    assert [d.code for d in diags] == ["JANA_CONSTRAINTS_NOT_CARRIED"]


# --------------------------------------------------------------- refusals

@pytest.mark.parametrize("extra, match", [
    ("ndim 4", "modulated"),
    ("qi 0.1 0 0", "modulation vector"),
    ("commen 2 1 1", "commensurate modulated"),
    ("ncomp 2", "composite"),
    ("wmatrix", "composite matrices"),
    ("twin 2", "twin domains"),
    ("magnetic 1", "not in the Jana98"),
])
def test_the_refusal_list_is_refused_by_name(tmp_path, extra, match):
    with pytest.raises(jana.JanaError, match=match):
        jana.read_jana(write_set(tmp_path, m50=m50(extra_global=extra)))


def test_a_superspace_symbol_is_refused(tmp_path):
    text = m50().replace("spgroup Pbam 55 3", "spgroup Pbam(00g)0s0 55 3")
    with pytest.raises(jana.JanaError, match="superspace"):
        jana.read_jana(write_set(tmp_path, m50=text))


def test_a_four_component_operator_is_refused(tmp_path):
    text = m50().replace("symmetry x y z\n", "symmetry x1 x2 x3 x4\n", 1)
    with pytest.raises(jana.JanaError, match="three-dimensional"):
        jana.read_jana(write_set(tmp_path, m50=text))


@pytest.mark.parametrize("kw, match", [
    (dict(header_a="    4    1    0    0"), "rigid-body"),
    (dict(header_a="    4    0    1    0"), "beta form"),
    (dict(header_a="    4    0    0"), "Nat Nmol Itemp Irot"),
    (dict(ba_line="Ba1       1  3     " + "".join(_num(v) for v in (0.125, 0, 0, 0))),
     "anharmonic"),
    (dict(ba_line="Ba1       1  0     " + "".join(_num(v) for v in (0.125, 0, 0, 0))),
     "TLS"),
    (dict(ba_line="Ba1       1  1     " + "".join(_num(v) for v in (0.125, 0, 0, 0))
          + "      000  0  2  2"), "modulation waves"),
    (dict(ti_adp=_keyed([0.011, 0.012, 0.013, 0.001, 0, 0], "")), "no refinement key"),
    (dict(ti_adp=_keyed([0.011, 0.012, 0.013, 0.001, 0, 0], "0110")), "4 refinement key"),
    (dict(ti_adp="".join(_num(v) for v in (0.011, 0.012)) + "*********" + " 0110111100"),
     "unreadable field"),
])
def test_m40_constructs_outside_the_layout_are_refused(tmp_path, kw, match):
    with pytest.raises(jana.JanaError, match=match):
        jana.read_jana(write_set(tmp_path, m40=m40(**kw)))


def test_an_m40_commands_section_is_refused(tmp_path):
    with pytest.raises(jana.JanaError, match="commands section"):
        jana.read_jana(write_set(tmp_path, m40="commands\nmaxsc 12\nend\n" + m40()))


def test_an_atom_type_index_past_the_m50_list_is_refused(tmp_path):
    line = "Ba1       9  1     " + "".join(_num(v) for v in (0.125, 0, 0, 0))
    with pytest.raises(jana.JanaError, match="names atom type 9"):
        jana.read_jana(write_set(tmp_path, m40=m40(ba_line=line)))


# --------------------------------------------------------------- perturbation

def test_every_truncation_raises_naming_the_file_or_reads(tmp_path):
    """io/CLAUDE.md § Refusals' discipline on the synthetic set: never a parser exception."""
    full = {".m50": m50(), ".m40": m40(), ".m41": m41()}
    for target, text in full.items():
        for cut in range(0, len(text), max(1, len(text) // 25)):
            files = dict(full, **{target: text[:cut]})
            stem = f"t{target[1:]}_{cut}"
            for suffix, body in files.items():
                (tmp_path / f"{stem}{suffix}").write_text(body, encoding="utf-8")
            try:
                model = jana.read_jana(tmp_path / f"{stem}.m50")
                for index in range(len(model.phases)):
                    jana.to_structure(model, phase=index)
            except jana.JanaError as exc:
                assert str(tmp_path) in str(exc), exc


# --------------------------------------------------------------- review findings

def test_a_positive_value_run_into_its_neighbour_is_refused(tmp_path):
    text = m41().replace(" 8.110000 9.210000", " 8.1100009.210000")
    with pytest.raises(jana.JanaError, match="run together"):
        jana.read_jana(write_set(tmp_path, m41=text))


def test_a_non_finite_value_is_refused_naming_the_file(tmp_path):
    text = m40().replace(" 0.840000", "1.0E999  ", 1)
    with pytest.raises(jana.JanaError, match="non-finite") as info:
        jana.read_jana(write_set(tmp_path, m40=text))
    assert "syn.m40" in str(info.value)


def test_a_form_factor_table_is_read_past_across_lines(tmp_path):
    text = m50().replace("atom O\n", "atom O\nformtab -4\n 8.0 7.5\n 7.0 6.5 atweight 15.999\n")
    assert len(jana.read_jana(write_set(tmp_path, m50=text)).phases[0].atom_types) == 3


def test_an_operator_listed_and_generated_is_one_operation(tmp_path):
    text = m50().replace("symmetry x y z\n", "symmetry x y z\nsymmetry -x -y -z\n", 1)
    s = jana.to_structure(jana.read_jana(write_set(tmp_path, m50=text)), phase=0)
    assert gemmi.SpaceGroup(s.phases[0].space_group).number == 55


def test_rows_after_the_declared_atoms_are_counted_and_named(tmp_path):
    text = m40() + " 0.001000 0.000000 0.000000 0.000000 0.000000 0.000000\n"
    model = jana.read_jana(write_set(tmp_path, m40=text))
    assert model.m40_trailing == 1
    diags: list[Diagnostic] = []
    jana.to_structure(model, phase=0, diagnostics=diags)
    assert "after the declared atoms" in diags[-1].message


@pytest.mark.parametrize("which", [".m50", ".m41"])
def test_a_keyword_part_without_its_end_is_refused(tmp_path, which):
    texts = {".m50": m50(), ".m41": m41()}
    texts[which] = texts[which].replace("\nend\n", "\n")  # every one
    with pytest.raises(jana.JanaError, match="no 'end' line"):
        jana.read_jana(write_set(tmp_path, m50=texts[".m50"], m41=texts[".m41"]))


def test_a_phase_keyword_before_the_first_phase_is_refused(tmp_path):
    text = m50().replace("phase Alpha\n", "centro\nphase Alpha\n")
    with pytest.raises(jana.JanaError, match="before the first 'phase'"):
        jana.read_jana(write_set(tmp_path, m50=text))


def test_an_occupancy_past_one_is_refused_and_a_full_site_is_full(tmp_path):
    line = "Ba1       1  1     " + "".join(_num(v) for v in (1.0, 0, 0, 0))
    model = jana.read_jana(write_set(tmp_path, m40=m40(ba_line=line)))
    with pytest.raises(jana.JanaError, match="symmetry order 4"):
        jana.to_structure(model, phase=0)
    s = jana.to_structure(jana.read_jana(write_set(tmp_path, stem="b")), phase=1)
    assert [a.occ.value for a in s.phases[0].atoms] == [1.0, 1.0]


def test_a_phase_with_no_operator_is_refused(tmp_path):
    text = m50(two_phase=False)
    text = "\n".join(x for x in text.splitlines() if not x.startswith("symmetry"))
    model = jana.read_jana(write_set(tmp_path, m50=text + "\n", two_phase=False))
    with pytest.raises(jana.JanaError, match="no symmetry operator"):
        jana.to_structure(model)


def test_a_tensor_outside_its_site_symmetry_is_refused_naming_the_file(tmp_path):
    adp = _keyed([0.011, 0.012, 0.013, 0.001, 0.003, 0], "0110111111")
    model = jana.read_jana(write_set(tmp_path, m40=m40(ti_adp=adp)))
    with pytest.raises(jana.JanaError, match="syn.m50"):
        jana.to_structure(model, phase=0)


def test_an_ambiguous_abbreviation_is_refused(tmp_path):
    text = m50().replace("atweight 47.867", "f 47.867")
    with pytest.raises(jana.JanaError, match="'f' is not in"):
        jana.read_jana(write_set(tmp_path, m50=text))


def test_abbreviated_refine_commands_are_still_read(tmp_path):
    diags: list[Diagnostic] = []
    text = m50(refine="autk 0\nrestr O1 1").replace("\nrefine\n", "\nref\n")
    model = jana.read_jana(write_set(tmp_path, m50=text), diagnostics=diags)
    assert model.autkeys == 0 and model.constraints == ["restr O1 1"]
    assert [d.code for d in diags] == ["JANA_CONSTRAINTS_NOT_CARRIED"]


def test_a_stated_automatic_mode_is_said_plainly(tmp_path):
    diags: list[Diagnostic] = []
    jana.read_jana(write_set(tmp_path, m50=m50(refine="autkeys 1")), diagnostics=diags)
    assert "are not the set" in diags[0].message


# --------------------------------------------------------------- second review (PR #1627)

def _p63mmc_set(tmp_path, u: tuple[float, ...], stem: str = "hex", *,
                ai_text: str | None = None, u_text: list[str] | None = None):
    """Mg on 2c (1/3, 2/3, 1/4) of P6_3/mmc, anisotropic: ai = 2/24 = 1/12, and
    the site's 3m symmetry ties U22 = U11, U12 = U11/2, U13 = U23 = 0."""
    sg = gemmi.SpaceGroup("P 63/m m c")
    seen, ops = set(), []
    for op in sg.operations().sym_ops:
        rot = tuple(map(tuple, op.rot))
        neg = tuple(tuple(-c for c in row) for row in op.rot)
        if rot in seen or neg in seen:
            continue
        seen.add(rot)
        ops.append(op.triplet().replace(",", " "))
    text50 = "\n".join(
        ["title hexagonal", "lambda 1.5406 radtype 1", "-" * 40,
         "cell 3.21 3.21 5.21 90 90 120", "spgroup P63/mmc 194 6", "centro",
         "lattice P"] + [f"symmetry {op}" for op in ops]
        + ["atom Mg", "end", "*" * 60, "refine", "autkeys 0", "end"]) + "\n"
    ai = (ai_text or _num(1 / 12)).rjust(9)
    keyed_u = (_keyed(u, "0000111100") if u_text is None else
               "".join(t.rjust(9) for t in u_text).ljust(60) + "0000111100")
    text40 = "\n".join([
        "    1    0    0    0",
        _keyed([1.0, 0, 0, 0, 0, 0], "100000"), _num(0.0),
        _keyed([0] * 6, "000000"), _keyed([0] * 6, "000000"),
        "Mg1       1  2     " + ai + "".join(_num(v) for v in (1 / 3, 2 / 3, 0.25)),
        keyed_u]) + "\n"
    text41 = "\n".join([
        "bckgtype 1 bckgnum 3", "end", "*" * 60,
        "# Cell parameters - a,b,c,alpha,beta,gamma",
        _keyed([3.21, 3.21, 5.21, 90, 90, 120], "101000")]) + "\n"
    return write_set(tmp_path, stem=stem, m50=text50, m40=text40, m41=text41,
                     two_phase=False)


def test_a_tied_tensor_rounded_in_its_last_digit_is_read_on_the_site(tmp_path):
    """U12 = U11/2 = 0.0061735 prints 0.006174: the file's rounding, not a
    contradiction of the 2c site's symmetry, so it is read on the site and said."""
    model = jana.read_jana(_p63mmc_set(tmp_path, (0.012347, 0.012347, 0.015,
                                                  0.006174, 0, 0)))
    diags: list[Diagnostic] = []
    s = jana.to_structure(model, diagnostics=diags)
    aniso = s.phases[0].atoms[0].aniso
    assert aniso.u12.value == pytest.approx(aniso.u11.value / 2, abs=1e-12)
    assert abs(aniso.u12.value - 0.006174) <= 5e-7 + 1e-12
    assert abs(aniso.u11.value - 0.012347) <= 5e-7 + 1e-12
    assert aniso.u13.value == 0.0 and aniso.u33.value == 0.015
    (info,) = [d for d in diags if d.code == "JANA_NOT_CARRIED"]
    assert "Uij of Mg1" in info.message
    assert any(w.startswith("phases.0.atoms.0.aniso.") for w in info.where)
    # the snapped ai (1/12 printed 0.083333) points at the occupancy
    assert "phases.0.atoms.0.occ" in info.where


def test_a_tied_tensor_off_by_more_than_its_print_is_still_refused(tmp_path):
    model = jana.read_jana(_p63mmc_set(tmp_path, (0.012347, 0.012347, 0.015,
                                                  0.006180, 0, 0)))
    with pytest.raises(jana.JanaError, match="hex.m50"):
        jana.to_structure(model)


def test_m41_phase_blocks_are_matched_by_name(tmp_path):
    alpha, nacl = m41().split("### phase NaCl\n")
    head, alpha = alpha.split("### phase Alpha\n")
    swapped = head + "### phase NaCl\n" + nacl + "### phase Alpha\n" + alpha
    model = jana.read_jana(write_set(tmp_path, m41=swapped))
    s = jana.to_structure(model, phase="Alpha")
    assert s.phases[0].cell.a.value == 8.11
    assert jana.to_structure(model, phase="NaCl").phases[0].cell.a.value == 5.641


def test_m41_phase_names_that_differ_from_the_m50_are_refused(tmp_path):
    text = m41().replace("### phase NaCl", "### phase Halite")
    with pytest.raises(jana.JanaError, match=r"syn\.m41.*Halite.*syn\.m50"):
        jana.read_jana(write_set(tmp_path, m41=text))


def test_commands_on_the_refine_line_are_read(tmp_path):
    diags: list[Diagnostic] = []
    text = m50(refine="").replace("\nrefine\n", "\nrefine restric O1 1\n")
    model = jana.read_jana(write_set(tmp_path, m50=text), diagnostics=diags)
    assert model.constraints == ["restric O1 1"]
    assert "JANA_CONSTRAINTS_NOT_CARRIED" in [d.code for d in diags]
    diags.clear()
    text = m50(refine="").replace("\nrefine\n", "\nrefine autkeys 0\n")
    model = jana.read_jana(write_set(tmp_path, stem="b", m50=text), diagnostics=diags)
    assert model.autkeys == 0 and diags == []


# --------------------------------------------------------------- third review (PR #1627)

def _info(diags):
    (info,) = [d for d in diags if d.code == "JANA_NOT_CARRIED"]
    return info


def test_a_uij_key_on_some_components_is_reported_as_merged(tmp_path):
    """Ti1 on 4g allows U11, U22, U33 and U12; a key on U11 alone is read by
    ParameterTable as one flag for all four: said, as the xyz merge is."""
    ti = _keyed([0.011, 0.012, 0.013, 0.001, 0, 0], "0110100000")
    diags: list[Diagnostic] = []
    jana.to_structure(jana.read_jana(write_set(tmp_path, m40=m40(ti_adp=ti))),
                      phase="Alpha", diagnostics=diags)
    info = _info(diags)
    assert "per-component Uij keys of Ti1" in info.message
    assert "phases.0.atoms.1.aniso.u11" in info.where


def test_a_uij_key_on_every_allowed_component_reports_no_merge(tmp_path):
    """The default fixture keys U11, U22, U33 and U12 and leaves the two the
    4g symmetry fixes at zero: that is the whole allowed set, not a merge."""
    ti = _keyed([0.011, 0.012, 0.013, 0.001, 0, 0], "0110111100")
    diags: list[Diagnostic] = []
    jana.to_structure(jana.read_jana(write_set(tmp_path, m40=m40(ti_adp=ti))),
                      phase="Alpha", diagnostics=diags)
    assert "Uij keys" not in _info(diags).message


def test_a_nonzero_origin_shift_is_refused_and_a_zero_one_read(tmp_path):
    """No page of M98 says the listed operators include the shift, so a nonzero
    one could land the structure at the wrong origin without a signal."""
    shifted = m50(extra_phase="sgshift 0.5 0 0")
    model = jana.read_jana(write_set(tmp_path, m50=shifted))
    assert model.phases[0].sgshift == (0.5, 0.0, 0.0)
    with pytest.raises(jana.JanaError, match=r"syn\.m50.*origin shift"):
        jana.to_structure(model, phase="Alpha")
    zero = m50(extra_phase="sgshift 0 0 0")
    jana.to_structure(jana.read_jana(write_set(tmp_path, stem="z", m50=zero)),
                      phase="Alpha")


def test_a_stated_form_factor_table_is_reported_not_carried(tmp_path):
    with_table = m50(extra_phase="formtab 4\n 1.0 2.0 3.0 4.0")
    diags: list[Diagnostic] = []
    jana.to_structure(jana.read_jana(write_set(tmp_path, m50=with_table)),
                      phase="Alpha", diagnostics=diags)
    assert "formtab" in _info(diags).message
    diags = []
    jana.to_structure(jana.read_jana(write_set(tmp_path, stem="b")),
                      phase="Alpha", diagnostics=diags)
    assert "formtab" not in _info(diags).message


def test_ai_is_read_to_its_own_last_printed_digit(tmp_path):
    """1/12 printed 0.083 is 0.996 of a full 2c site, inside half a unit of
    its own last digit (5e-4 x the order 12): full, and said. Six-decimal
    printing, which the first slice assumed for every file, would leave 0.996."""
    diags: list[Diagnostic] = []
    s = jana.to_structure(jana.read_jana(_p63mmc_set(
        tmp_path, (0.012347, 0.012347, 0.015, 0.006174, 0, 0), ai_text="0.083")),
        diagnostics=diags)
    assert s.phases[0].atoms[0].occ.value == 1.0
    assert "phases.0.atoms.0.occ" in _info(diags).where


def test_a_uij_is_moved_within_its_own_last_printed_digit(tmp_path):
    """U11 = 0.0123 with U12 printed 0.0062 (the tie wants 0.00615): 5e-5 off,
    half a unit of a four-decimal token, so read on the site; the same offset
    on six-decimal tokens (U12 0.006180) is refused above."""
    model = jana.read_jana(_p63mmc_set(
        tmp_path, (0, 0, 0, 0, 0, 0),
        u_text=["0.0123", "0.0123", "0.0150", "0.0062", "0.0000", "0.0000"]))
    s = jana.to_structure(model)
    aniso = s.phases[0].atoms[0].aniso
    assert aniso.u12.value == pytest.approx(aniso.u11.value / 2, abs=1e-12)
    assert abs(aniso.u12.value - 0.0062) <= 5e-5 + 1e-12
