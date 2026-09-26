"""The TOPAS ``.inp`` project reader.

Every fixture here is written inline, per ``io/CLAUDE.md``: a text format's
lines are self-describing, so a literal in the test says more than a writer
that shares constants with the parser could.

The site-line forms are not invented. Each one below was taken from a real file
in a 606-``.inp`` archive, and the comment on each says what reading it wrong
cost — because the failure mode this reader exists to prevent is not a crash but
a *wrong number with nothing raised*. Two of them were measured: a phase
fraction read as 0.596 wt% when the file said 11.596, and one read as 0.931 when
the file said 60.931.
"""

import re
from pathlib import Path

import pytest

import rietx as rx
from rietx.crystallography.symmetry import get_spacegroup
from rietx.io.projects import coverage
from rietx.io.projects.topas import (
    _CELL_MACROS,
    TopasInpError,
    _cell_search_text,
    _masked,
    from_structure,
    normalize_space_group,
    normalize_species,
    read_topas_inp,
    refined,
    resolve_ifdefs,
    strip_comments,
    symbol_table,
    to_structure,
    write_topas_inp,
)


def _inp(directory: Path, name: str, text: str) -> Path:
    """Write a fixture .inp. One writer, so the encoding is named once."""
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


# ----------------------------------------------------------------- rule 1, 2


def test_dead_text_outnumbers_live_text():
    """A wavelength read without stripping comments picks the disabled block.

    Real files carry several instrument blocks and disable all but one, so this
    is the difference between the refinement's own λ and a leftover.
    """
    text = strip_comments("""
        /* la 1 lo 0.7093 */
        ' la 1 lo 1.78897
        la 1 lo 0.41368
    """)
    assert "0.41368" in text
    assert "0.7093" not in text
    assert "1.78897" not in text


def test_ifdef_gates_content():
    live = resolve_ifdefs("#define A\n#ifdef A\nkeep\n#else\ndrop\n#endif\n"
                          "#ifdef B\ndrop2\n#else\nkeep2\n#endif")
    assert "keep" in live and "keep2" in live
    assert "drop" not in live and "drop2" not in live


def test_define_after_use_is_still_defined():
    """TOPAS permits it, so symbols are collected before the walk."""
    assert "keep" in resolve_ifdefs("#ifdef LATER\nkeep\n#endif\n#define LATER")


# -------------------------------------------------------------------- rule 4


@pytest.mark.parametrize("written, iucr", [
    ("Cu+1", "Cu1+"),   # TOPAS's sign-first spelling
    ("O-2", "O2-"),
    ("Y+3", "Y3+"),
    ("Cu1+", "Cu1+"),   # already IUCr order, left alone
    ("Co", "Co"),
])
def test_species_are_normalised_to_iucr_order(written, iucr):
    assert normalize_species(written) == iucr


@pytest.mark.parametrize("written, expected", [
    ("Pn-3mZ", "Pn-3m:2"),   # Z = Zentrum = origin choice 2
    ("P63mcZ", "P63mc:2"),
    ("R-3cH", "R-3c:H"),
    ("R-3cR", "R-3c:R"),
    ("Fm-3m", "Fm-3m"),      # a final letter that is part of the symbol
    ("Pnma", "Pnma"),
    ("P1", "P1"),
])
def test_origin_and_axis_suffixes_are_translated_not_dropped(written, expected):
    """Dropping the letter selects the *other* origin with nothing raised —
    for #224 a bare ``Pn-3m`` is choice 1, and Cu2O is conventionally choice 2.
    """
    assert normalize_space_group(written) == expected


# ----------------------------------------- the repairs are visible on a channel

def test_diagnostics_surface_the_species_and_origin_repairs(tmp_path):
    """Both repairs reach `model.phases` but a caller reading it back cannot tell
    them from a stated value, so `read_topas_inp(diagnostics=[])` records them —
    the same channel `structure_from_cif` and `read_pattern` take. One diagnostic
    per distinct rewrite (two `La+3` sites → one, carrying both atom paths), not
    one per atom."""
    inp = _inp(tmp_path, "cu2o.inp",
               'str\nphase_name "cu2o"\nspace_group "Pn-3mZ"\nCubic_(lpa 4.27)\n'
               'site La1 x 0 y 0 z 0 occ La+3 1. beq !b 0.5\n'
               'site La2 x 0.5 y 0.5 z 0.5 occ La+3 1. beq !b 0.5\n'
               'site Cu1 x 0.25 y 0.25 z 0.25 occ Cu+1 1. beq !c 0.5\n')
    diags = []
    model = read_topas_inp(inp, diagnostics=diags)

    origin = [d for d in diags if d.code == "TOPAS_ORIGIN_TRANSLATED"]
    codes = sorted(d.code for d in diags)
    # La+3 (two sites, deduped) and Cu+1 (one) → two species diagnostics + one origin
    assert codes == ["TOPAS_ORIGIN_TRANSLATED",
                     "TOPAS_SPECIES_NORMALISED", "TOPAS_SPECIES_NORMALISED"]
    by_raw = {("La3+" in d.message): d for d in diags
              if d.code == "TOPAS_SPECIES_NORMALISED"}
    la = by_raw[True]
    assert "La+3" in la.message and "La3+" in la.message
    assert la.where == ["phases.0.atoms.0.species", "phases.0.atoms.1.species"]
    assert origin[0].where == ["phases.cu2o.space_group"]
    assert "Pn-3mZ" in origin[0].message and "Pn-3m:2" in origin[0].message
    assert all(d.level == "info" for d in diags)
    # the model carries the repaired values regardless
    assert model.phases[0].space_group == "Pn-3m:2"
    assert [s.species for s in model.phases[0].sites] == ["La3+", "La3+", "Cu1+"]


def test_the_repairs_are_made_with_or_without_the_channel(tmp_path):
    """`diagnostics` makes the repairs *visible*, it does not change what is
    built: the model is identical whether or not a list is passed, and a file
    that needs no repair leaves an empty list."""
    inp = _inp(tmp_path, "cu2o.inp",
               'str\nphase_name "cu2o"\nspace_group "Pn-3mZ"\nCubic_(lpa 4.27)\n'
               'site Cu1 x 0.25 y 0.25 z 0.25 occ Cu+1 1. beq !c 0.5\n')
    with_channel = read_topas_inp(inp, diagnostics=[])
    without = read_topas_inp(inp)
    assert with_channel.phases[0].space_group == without.phases[0].space_group
    assert ([s.species for s in with_channel.phases[0].sites]
            == [s.species for s in without.phases[0].sites])

    clean = _inp(tmp_path, "clean.inp",
                 'str\nphase_name "P"\nspace_group "Pm-3m"\nCubic_(lpa 4.16)\n'
                 'site A1 x 0 y 0 z 0 occ La 1. beq !b 0.5\n')
    diags = []
    read_topas_inp(clean, diagnostics=diags)
    assert diags == []


def test_the_skipped_block_reports_through_the_channel_but_still_refuses_at_build(tmp_path):
    """The report arm of "report or refuse, never drop": a `str` block stating a
    cell and a site but no `phase_name`/`space_group` is recorded on
    `model.skipped_blocks` whether or not a list is passed, and reports one
    `TOPAS_BLOCK_SKIPPED` when one is. Reporting it does not turn it into a silent
    drop — building a `Structure` while a named phase also builds still refuses,
    because dropping the cell-bearing block would unbalance the weight fractions,
    and that refusal must hold whether or not a caller passed a list."""
    inp = _inp(tmp_path, "nameless.inp",
               'str\nphase_name "P"\nspace_group "Pm-3m"\nCubic_(lpa 4.16)\n'
               'site A1 x 0 y 0 z 0 occ La 1. beq !b 0.5\n'
               'str\na 4.0\nb 4.0\nc 4.0\n'
               'site B1 x 0 y 0 z 0 occ La 1. beq !b 0.5\n')
    diags = []
    model = read_topas_inp(inp, diagnostics=diags)

    skipped = [d for d in diags if d.code == "TOPAS_BLOCK_SKIPPED"]
    assert len(skipped) == 1
    assert skipped[0].level == "warning"
    assert skipped[0].where == ["skipped_blocks.0"]
    assert "no phase_name" in skipped[0].message
    assert "site line" in skipped[0].message
    assert "a cell" in skipped[0].message

    # Recorded whether or not a list is passed — the read never drops it silently.
    assert len(model.skipped_blocks) == 1
    assert len(read_topas_inp(inp).skipped_blocks) == 1
    assert [p.name for p in model.phases] == ["P"]

    # Report at read; refuse at build; drop never.
    with pytest.raises(TopasInpError, match="weight fractions"):
        to_structure(model)


# -------------------------------------------------------------------- rule 3

#: One site line per real spelling found in the archive, with the value the
#: file states. The parametrisation is the point: a parser that handles four of
#: these and drops the fifth produces a structure that is wrong in one atom,
#: which is a wrong structure factor and a *better* Rwp than the right model.
SITE_LINES = [
    # plain literals
    ("site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5", (0.0, 0.0, 0.0), 1.0, 0.5),
    # equation for a special position
    ("site A1 x = 1/3; y = 2/3; z 0.25 occ Na+1 1 beq b 0.5",
     (1 / 3, 2 / 3, 0.25), 1.0, 0.5),
    # a *named* refined value, backtick marker
    ("site A1 x nx 0.4938` y ny 0.24625` z nz 0.25` occ Na+1 1 beq b 0.8`",
     (0.4938, 0.24625, 0.25), 1.0, 0.8),
    # `!` fix flag BEFORE the name, and an `_esd` suffix on the number
    ("site A1 x 0 y 0 z !ph1_cr1_z 0.33489_0.00003 occ Cr+3 1. beq !bcr 1",
     (0.0, 0.0, 0.33489), 1.0, 1.0),
    # `@,` — a refined value TOPAS did not name
    ("site A1 x @, 0.19776` y 0.5 z 0.5 occ B 1. beq @, 0.5884`",
     (0.19776, 0.5, 0.5), 1.0, 0.5884),
    # name then equation
    ("site A1 x Zr1_x =1/2; y Zr1_y =1/2; z Zr1_z =1/3; occ Zr 1.0 beq 1",
     (0.5, 0.5, 1 / 3), 1.0, 1.0),
    # the A1/A2/A3 coordinate macro, flag inside the parenthesis
    ("site A1 A1(!xO3, 0.00143 , 0.00143) A2(!yO3, 0.03550 , 0.03550) "
     "A3(!zO3, 0.21526 , 0.21526) occ O 1.0 beq !bval 0",
     (0.00143, 0.03550, 0.21526), 1.0, 0.0),
    # occupancy OMITTED — TOPAS defaults to full, and reading the token after
    # the species as a number picked up the word "beq" and raised ValueError
    ("site A1 x 0.5 y 0. z 0.5 occ Sr+2 beq 0.7650`",
     (0.5, 0.0, 0.5), 1.0, 0.7650),
    # a partial occupancy with a flag and a name, carrying `vcocc`
    ("site A1 x 0.5 y 0.5 z 0.5 occ Na+1 !occ_A1 0.5 vcocc beq bval1 1.5",
     (0.5, 0.5, 0.5), 0.5, 1.5),
]


@pytest.mark.parametrize("line, xyz, occ, beq", SITE_LINES)
def test_every_real_site_spelling_reads(tmp_path, line, xyz, occ, beq):
    inp = _inp(tmp_path, "s.inp", f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    (site,) = read_topas_inp(inp).phases[0].sites
    assert (site.x, site.y, site.z) == pytest.approx(xyz)
    assert site.occupancy == pytest.approx(occ)
    assert site.beq == pytest.approx(beq)


def test_an_equation_referencing_another_parameter_resolves(tmp_path):
    """``y = ph1_O1_x;`` is how a tetragonal oxygen says y is tied to x.

    Refusing it cost 14 archive files, the tier-1 references among them.
    """
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "Trirutile"\nspace_group "P42/mnm"\na 4.58\n'
                   'site O1 x ph1_O1_x 0.29935` y = ph1_O1_x; z 0 occ O-2 1. '
                   'beq ph1_beq_o1 0.34174`\n')
    (site,) = read_topas_inp(inp).phases[0].sites
    assert site.x == pytest.approx(0.29935)
    assert site.y == pytest.approx(0.29935)


def test_topas_own_evaluated_value_is_preferred_over_the_expression(tmp_path):
    """``= expr;: value`` — the ``;:`` tail is what the converged fit used.

    Taking it means the expression's whole symbol chain never has to be walked,
    which is what made the WISH parametric files readable.
    """
    inp = _inp(tmp_path, "s.inp", 'prm Fe1_x = 1/4 + Fe1_dx;:  0.25733\n'
                   'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
                   'scale =scph1*scb1;:  0.0844868572`\n'
                   'site Fe1 x = Fe1_x; y 0 z 0 occ Fe 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert model.phases[0].scale == pytest.approx(0.0844868572)
    assert model.phases[0].sites[0].x == pytest.approx(0.25733)


def test_symbol_table_binds_the_evaluated_value(tmp_path):
    assert symbol_table("prm Fe1_x = 1/4 + Fe1_dx;:  0.25733")["Fe1_x"] == \
        pytest.approx(0.25733)


def test_an_unresolvable_coordinate_raises_naming_file_phase_and_line(tmp_path):
    """A dropped site is a wrong structure factor, so this is a hard error.

    The measured cost of the alternative: an earlier parser demanded a bare
    number, silently dropped Y1 and Ba1 from YBaCo4O7 (5 of 7 sites) and
    produced a 98 wt% phase-fraction error with a *better* Rwp than the correct
    model — 0.02370 against 0.02353.
    """
    inp = _inp(tmp_path, "broken.inp", 'str\nphase_name "Unreadable"\nspace_group "P1"\na 5.0\n'
                   'site A1 x 0 y 0 z = 1-nothing_defined; occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "broken.inp" in str(exc.value)
    assert "Unreadable" in str(exc.value)
    assert "cannot read z" in str(exc.value)


def test_a_token_with_no_number_never_escapes_as_a_bare_valueerror(tmp_path):
    """Root CLAUDE.md: a reader raises naming the file, never its parser's
    exception. Three archive files reached ``ValueError('beq')`` this way."""
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
                   'site A1 x 0 y 0 z 0 occ Na+1 !occ_A1 beq b 0.5\n')
    model = read_topas_inp(inp)          # must not raise ValueError
    assert model.phases[0].sites[0].occupancy == pytest.approx(1.0)


# ------------------------------------------------ the nameless-value bug class


@pytest.mark.parametrize("line, expected", [
    # both nameless forms are real lines from one PbPdO2 file, and both were
    # read with their integer part eaten: 0.596 and 0.931
    ("weight_percent  11.596`", 11.596),
    ("weight_percent  60.931`", 60.931),
    ("weight_percent perc_PbPdO2  17.407`", 17.407),
    ("weight_percent !ph3_wtpct  100.000`", 100.0),
    ("weight_percent @  31.610`", 31.610),
    ("weight_percent cBN_wtpct  0.000`", 0.0),   # a phase refined to absent
])
def test_a_nameless_value_keeps_its_integer_part(tmp_path, line, expected):
    """``(?:\\w+\\s+)?`` in front of a value eats digits, because ``\\w``
    matches one. That is how ``weight_percent 97.9`` came back 0.9."""
    inp = _inp(tmp_path, "s.inp", f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    assert read_topas_inp(inp).phases[0].weight_percent == pytest.approx(expected)


@pytest.mark.parametrize("line, expected", [
    ("scale @, 0.00135564312`", 0.00135564312),
    ("scale !cBN_scale  1e-15", 1e-15),
    ("scale ph2_scale  5.17632205e-006_3.88e-006_LIMIT_MIN_1e-015", 5.17632205e-06),
    ("scale ph1_scale  8.3652308e-006", 8.3652308e-06),
])
def test_scale_is_read_not_silently_defaulted(tmp_path, line, expected):
    """A scale read as absent is replaced by ``to_structure``'s 1e-4 default,
    which is a made-up number standing where the file had a measured one."""
    inp = _inp(tmp_path, "s.inp", f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    assert read_topas_inp(inp).phases[0].scale == pytest.approx(expected)


def test_arithmetic_is_not_eval(tmp_path):
    """The charset gate that preceded the ``ast`` walk admitted ``**``, so a
    malformed file could put an unbounded computation inside a reader."""
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
                   'site A1 x = 9**9**9; y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError):
        read_topas_inp(inp)


# ------------------------------------------------------------------- the model


def test_cell_limits_are_read_and_a_contradicting_one_is_dropped(tmp_path):
    """The file's own ``min``/``max`` are part of the author's model — a phase
    the data cannot see is a flat direction without them. But TOPAS writes the
    converged value back, so value and bound can end up on opposite sides, and
    handing pydantic both raised a validation error out of a reader.
    """
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "P"\nspace_group "P1"\n'
                   'a lpa 6.2977` min 6.26 max 6.29\nc lpc 10.2458`\n'
                   'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell_limits["a"] == (6.26, 6.29)
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert cell.a.value == pytest.approx(6.2977)
    assert cell.a.min == pytest.approx(6.26)     # the bound that holds is kept
    assert cell.a.max == float("inf")            # the one it contradicts is not


def test_a_disabled_phase_is_not_in_the_model(tmp_path):
    inp = _inp(tmp_path, "s.inp", '#ifdef NEVER\nstr\nphase_name "ghost"\nspace_group "P1"\n'
                   'a 99.0\n#endif\n'
                   'str\nphase_name "real"\nspace_group "P1"\na 5.0\n'
                   'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert [p.name for p in read_topas_inp(inp).phases] == ["real"]


def test_the_emission_macro_is_reported_never_expanded(tmp_path):
    """ATTRIBUTION.md's fence: TOPAS is closed, so its macro library is not
    reproduced. Only the anode is reported; wavelengths come from rietx's own
    table."""
    inp = _inp(tmp_path, "s.inp", "CuKa5(0.0001)\nRadius(217.5)\n")
    model = read_topas_inp(inp)
    assert (model.anode, model.emission_macro) == ("CuKa", "CuKa5")
    assert model.wavelength is None
    assert model.goniometer_radius_mm == pytest.approx(217.5)


def test_to_structure_builds_a_refinable_structure(tmp_path):
    """``beq`` is TOPAS's B and ``biso`` is also B — no 8π² conversion."""
    inp = _inp(tmp_path, "s.inp", 'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
                   'Cubic_(lpa 4.15689)\nscale ph_scale 0.000225160497\n'
                   'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n'
                   'site B1 x !bx 0.19895 y 0.5 z 0.5 occ B 1. beq !bb 0.3076\n')
    (phase,) = to_structure(read_topas_inp(inp)).phases
    assert phase.space_group == "Pm-3m"
    assert phase.cell.a.value == pytest.approx(4.15689)
    assert phase.cell.b.value == pytest.approx(4.15689)   # Cubic_ fills b and c
    assert [a.species for a in phase.atoms] == ["La", "B"]
    assert phase.atoms[1].x.value == pytest.approx(0.19895)
    assert phase.atoms[0].biso.value == pytest.approx(0.4389)
    assert phase.scale.value == pytest.approx(0.000225160497)


def test_the_converged_figures_of_merit_are_recovered(tmp_path):
    """The reason the format is worth reading: it carries a *validated* answer.

    The numbers are the NIST SRM 660b LaB6 + cBN reference refinement
    (APS 11-BM run 3095), whose certified cell is 4.15689 Å.
    """
    inp = _inp(tmp_path, "s.inp", 'r_wp 8.04733245 gof 1.52039055\n'
                   'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
                   'Cubic_(lpa 4.15689)\nweight_percent ph_lab6_wtpct 17.907\n'
                   'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n'
                   'str\nphase_name "cubic_BN"\nspace_group "F-43m"\n'
                   'Cubic_(cbn 3.616466)\nweight_percent cBN_wtpct 82.093\n'
                   'site N1 x 0 y 0 z 0 occ N 1. beq !bn 0.30441\n')
    model = read_topas_inp(inp)
    assert model.r_wp == pytest.approx(8.04733245)
    assert model.gof == pytest.approx(1.52039055)
    assert [p.weight_percent for p in model.phases] == pytest.approx([17.907, 82.093])
    assert model.phases[0].cell["a"] == pytest.approx(4.15689)


def test_a_missing_file_raises_naming_it(tmp_path):
    with pytest.raises(TopasInpError, match="absent.inp"):
        read_topas_inp(tmp_path / "absent.inp")


# ------------------------------------------------- the refine flags (WP-1118)

@pytest.mark.parametrize("line, expected", [
    ("a lp 4.15689`", True),      # backtick: TOPAS wrote it back after refining
    ("a @ 4.15689", True),        # explicitly refined
    ("a @, 4.15689", True),
    ("a !lp 4.15689", False),     # explicitly held
    ("a !lp 4.15689`", False),    # `!` outranks the backtick
    ("a 4.15689", None),          # the file says nothing either way
])
def test_the_refine_flag_is_read_as_a_tri_state(tmp_path, line, expected):
    """A control file's refine flags are the payload, not its numbers.

    They are the part a person cannot reconstruct from a CIF plus a pattern,
    and the part that decides whether a cross-code comparison means anything.
    ``None`` is a third state on purpose: a file that says nothing is not a
    file that said "held", and collapsing the two is what would let a reader
    hand back a confident wrong protocol.
    """
    inp = _inp(tmp_path, "s.inp", f'str\nphase_name "P"\nspace_group "P1"\n{line}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert read_topas_inp(inp).phases[0].vary.get("a") == expected


def test_a_site_carries_its_own_flags():
    """One site, mixed: a refined coordinate, a held B, an untouched occupancy."""
    line = "site B1 x @, 0.19776` y 0.5 z 0.5 occ B 1. beq !bb 0.3076"
    assert refined("x", line) is True
    assert refined("beq", line) is False
    assert refined("y", line) is None


def test_the_certified_standards_protocol_survives_the_round_trip(tmp_path):
    """The NIST SRM 660b protocol: the certified cell is **held**, and that is
    the fact a transcription loses.

    This is the whole argument for reading the flags. Both phases' scales were
    refined and cBN's cell was refined; LaB6's was not, because 4.15689 Å is
    the certificate's number and holding it is what decorrelates zero and
    displacement from the cell. A reader that returned only the values would
    hand back a model that looks identical and refines to a different answer.
    """
    inp = _inp(tmp_path, "srm660b.inp",
               'r_wp 8.04733245 gof 1.52039055\n'
               'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
               'scale ph1_scale  0.000225160497`\na 4.15689\n'
               'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n'
               'site B1  x @, 0.19895` y 0.5 z 0.5 occ B 1. beq @, 0.3076`\n'
               'str\nphase_name "cubic_BN"\nspace_group "F-43m"\n'
               'scale ph2_scale  0.00321777397`\na lp_bn  3.616466`\n'
               'site N1 x 0 y 0 z 0 occ N 1. beq @, 0.30441`\n')
    lab6, cbn = to_structure(read_topas_inp(inp)).phases

    assert lab6.cell.a.value == pytest.approx(4.15689)
    assert lab6.cell.a.vary is False          # certified, held
    assert cbn.cell.a.vary is True            # the internal standard, refined
    assert lab6.scale.vary is True and cbn.scale.vary is True
    assert lab6.atoms[0].biso.vary is False   # `!bla`
    assert lab6.atoms[1].x.vary is True       # `@, 0.19895``


# ------------------------------------------- report or refuse, never drop

def test_mag_space_group_is_not_read_as_the_nuclear_one(tmp_path):
    """`mag_space_group` must not reach `space_group`, and the pin outlives the
    refusal that used to hide the question.

    Found by compiling every structure the reader returns: `mag_space_group
    62.448` matched an unanchored `space_group` and arrived as the *symbol*
    "62.448", which gemmi then refused a long way from the cause. Until
    WP-1328 a read-time raise on `mag_space_group` masked that — the keyword
    could not reach a built phase at all. Now the magnetic construct is read
    (WP-1327 gave the package a magnetic model, and `coverage`'s
    `magnetic space group` row is the declared stance), so the collision is a
    live question again and this is the only thing asserting the answer: `\\b`
    is what keeps the two apart, since `mag_space_group` offers no word
    boundary before `space`.
    """
    inp = _inp(tmp_path, "mag.inp",
               'str\nphase_name "LaMnO3_mag"\nspace_group "P n m a"\n'
               'mag_space_group 62.448\na 5.7 b 7.6 c 5.5\n'
               'site Mn1 x 0 y 0 z 0 occ Mn+3 1 beq b 0.5 mlx 3.4\n')
    model = read_topas_inp(inp)
    (phase,) = model.phases
    assert phase.space_group == "P n m a"
    assert phase.mag_space_group == "62.448"
    assert phase.sites[0].moment == {"mlx": 3.4}
    # ... and the keyword is *read* (a number is the group), so nothing about
    # it is left to report.
    assert not model.coverage.reported
    assert coverage.stance("mag_space_group") is coverage.Stance.READ


def test_a_magnetic_phase_takes_its_bns_number_and_refuses_a_bare_symbol(
        tmp_path):
    """A `mag_space_group` number is the group; a symbol still is not.

    Reading a magnetic `.inp` does not raise — the moments are on the model —
    and a BNS number resolves on its own (spglib, the standard setting), so
    `to_structure` builds with no caller spec and says where the group came
    from. A Shubnikov *symbol* gives no operator list, so the refusal stays at
    `to_structure`, naming the phase, the sites and the symbol.
    """
    text = ('str\nphase_name "LaMnO3_mag"\nspace_group "P n m a"\n'
            'mag_space_group 62.448\na 5.7 b 7.6 c 5.5\n'
            'site Mn1 x 0 y 0 z 0 occ Mn+3 1 beq b 0.5 mlx 0.6\n')
    built_diags: list = []
    built = to_structure(read_topas_inp(_inp(tmp_path, "mag.inp", text)),
                         diagnostics=built_diags)
    assert built.phases[0].magnetic_symmetry.bns_number == "62.448"
    assert built.phases[0].space_group == "P n m a"
    # mlx is fractional: 0.6 of a 5.7 Å edge is 3.42 mu_B along a
    assert built.phases[0].atoms[0].moment.values() == pytest.approx(
        (0.6 * 5.7, 0.0, 0.0))
    (read,) = [d for d in built_diags if d.code == "TOPAS_MAGNETIC_GROUP_READ"]
    assert "'62.448'" in read.message
    assert read.where == ["phases.0.magnetic_symmetry"]

    symbol = read_topas_inp(_inp(tmp_path, "sym.inp", text.replace(
        "mag_space_group 62.448", "mag_space_group \"P n' m a'\"")))
    with pytest.raises(TopasInpError, match="Shubnikov") as excinfo:
        to_structure(symbol)
    assert "P n' m a'" in str(excinfo.value)
    assert "'Mn1'" in str(excinfo.value)
    built = to_structure(symbol, magnetic_symmetry="62.448")
    assert built.phases[0].magnetic_symmetry.bns_number == "62.448"


def test_an_inp_with_no_structural_phase_refuses_naming_the_file(tmp_path):
    """A Pawley or indexing-only `.inp` legitimately has no cell to build from.

    It must still not reach the caller as a pydantic `ValidationError`: a
    reader raises naming the file, and pydantic's report names a field.
    """
    inp = _inp(tmp_path, "pawley.inp", 'r_wp 3.2\nxdd "sample.xy"\n')
    model = read_topas_inp(inp)
    assert model.phases == []
    with pytest.raises(TopasInpError, match="pawley.inp"):
        to_structure(model)


def test_a_phase_whose_sites_were_all_disabled_refuses_naming_the_phase(tmp_path):
    inp = _inp(tmp_path, "gated.inp",
               'str\nphase_name "p21n"\nspace_group "P21/n"\na 5.0\n'
               '#ifdef NEVER\nsite A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n#endif\n')
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp))
    assert "gated.inp" in str(exc.value) and "p21n" in str(exc.value)


# ------------------------------------------- one grammar, on the cell too

#: The cell had its own regex once, and it admitted three of these six. The
#: numbers are `archive file 7`'s monoclinic `p21n` lattice parameter, which
#: that file writes as an equation with TOPAS's evaluated tail — measured: the
#: three equation spellings left `a` out of `phase.cell`, so `to_structure`
#: dropped the phase, and across the archive that lost **320 phases in 15
#: files**, 107 patterns of `archive file 7` among them.
CELL_SPELLINGS = [
    ("a 7.301139", 7.301139, None),
    # a *name* is itself the refine flag — Technical Reference 2.1, "A parameter
    # is flagged for refinement by giving it a name".
    ("a lpa 7.301139", 7.301139, True),
    ("a @ 7.301139", 7.301139, True),
    ("a !lpa 7.301139`", 7.301139, False),
    ("a =mlpa;:7.301139`", 7.301139, True),
    ("a = 7.3;", 7.3, None),
    # An equation resolved through a *declared* parameter inherits that
    # parameter's refine state, because the edge is dependent on it and the
    # edge itself has no flag to read. `prm mlpa 7.30114` names the parameter
    # and so refines it — Technical Reference 2.2, where `prm b1 0.2` is
    # described as a new parameter that will be refined and `prm !b1 0.2` as
    # the held form. This row read `None` for as long as the inheritance was
    # missing, which is a file that refined its cell arriving as one that held
    # it.
    ("a = mlpa;", 7.30114, True),
]


@pytest.mark.parametrize("line, expected, vary", CELL_SPELLINGS)
def test_a_cell_edge_reads_in_every_spelling_the_one_grammar_admits(
        tmp_path, line, expected, vary):
    """The cell is read through the same grammar as every other scalar.

    A second regex for the cell is the failure this PR is about one rank down:
    it disagreed with `_field` on the `= expr;: value` tail, and a phase whose
    `a` is missing is silently absent from the `Structure` while its
    `weight_percent` still reports.
    """
    inp = _inp(tmp_path, "cell.inp",
               f'prm mlpa 7.30114\nstr\nphase_name "p21n"\nspace_group "P121/n1"\n'
               f'{line}\nb 7.5\nc 7.7\nbe 99.1\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell["a"] == pytest.approx(expected)
    assert phase.vary.get("a") == vary
    (built,) = to_structure(read_topas_inp(inp)).phases
    assert built.cell.a.value == pytest.approx(expected)


def test_a_cell_min_max_still_reads_when_the_value_is_named(tmp_path):
    """Routing the cell through the one grammar must not lose the window that
    keeps a phase the data cannot see from running away."""
    inp = _inp(tmp_path, "cell.inp",
               'str\nphase_name "P"\nspace_group "P1"\n'
               'a lp_bn 3.616466` min 3.61 max 3.63\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell_limits["a"] == (3.61, 3.63)
    assert phase.vary["a"] is True


# --------------------------------------------------------- the lattice macros

#: Every spelling of a lattice macro that a real archive file contains, with
#: the file it came from. A macro is a *specification fact* (io/CLAUDE.md's
#: rule 2), so the argument order is read off these lines and never guessed.
LATTICE_MACROS = [
    # Cubic_ with a named argument — the one form that already worked. Naming
    # the argument refines it: the reference's own macro chapter gives the three
    # spellings side by side (19.1) — `Cubic(4.50671)`, `Cubic(a_lp 4.50671)`,
    # `Cubic(!a_lp 4.50671)` — and 2.1 says which of them is free.
    ("Cubic_(lpa 4.15689)", (4.15689,) * 3 + (90.0,) * 3, True),
    # nameless: `\w*` in front of the value ate the integer part and gave
    # a = 0.15689, the same class as `weight_percent 11.596` → 0.596.
    ("Cubic(10)", (10.0,) * 3 + (90.0,) * 3, None),              # archive file 14:37
    ("Cubic_( 4.15689)", (4.15689,) * 3 + (90.0,) * 3, None),
    # flag with no name: the whole cell came back empty, so the phase vanished.
    ("Cubic(@  4.15692`)", (4.15692,) * 3 + (90.0,) * 3, True),  # archive file 8:54
    ("Cubic_(!lpa 4.15689)", (4.15689,) * 3 + (90.0,) * 3, False),
    # TOPAS's own evaluated tail, inside the macro's parenthesis.
    # an *equation* is a constraint (2.4), not an independent parameter, so a
    # name on one is not the refine flag — only its write-back tick is.
    ("Cubic(=a1;:  5.43416_0.00012)",                            # archive file 9:139
     (5.43416,) * 3 + (90.0,) * 3, None),
    ("Cubic(aLP  11.000000`)",                                   # archive file 10:69
     (11.000000,) * 3 + (90.0,) * 3, True),
    # a = b, c, and γ = 90 — TOPAS writes the two independent lengths in order.
    ("Tetragonal(@  4.500000`, @  2.900000`)",                   # archive file 11:38
     (4.500000, 4.500000, 2.900000, 90.0, 90.0, 90.0), True),
    # a = b, c, and γ = **120**.
    ("Hexagonal(@  3.500000`, @  12.000000`)",                   # archive file 12:87
     (3.500000, 3.500000, 12.000000, 90.0, 90.0, 120.0), True),
    ("Trigonal(  12.500000,   37.500000)",                       # archive file 18:90
     (12.500000, 12.500000, 37.500000, 90.0, 90.0, 120.0), None),
    ("Trigonal(@  12.50000`_0.00010,  @  37.50000`_0.00056)",    # archive file 32:51
     (12.50000, 12.50000, 37.50000, 90.0, 90.0, 120.0), True),
]


@pytest.mark.parametrize("macro, cell, vary", LATTICE_MACROS)
def test_a_lattice_macro_fills_the_cell_it_states(tmp_path, macro, cell, vary):
    """A lattice macro is as much a statement of the cell as an ``a`` line.

    Before this, only ``Cubic_(<name> <value>)`` was read: every other macro
    left ``phase.cell`` empty and ``to_structure`` then *dropped the phase*
    while ``weight_percent`` went on reporting for it, so a QPA table looked
    complete with a phase missing from the `Structure`.
    """
    inp = _inp(tmp_path, "macro.inp",
               f'str\nphase_name "P"\nspace_group "P1"\n{macro}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert tuple(phase.cell[k] for k in ("a", "b", "c", "al", "be", "ga")) == \
        pytest.approx(cell)
    assert phase.vary.get("a") == vary
    assert len(to_structure(read_topas_inp(inp)).phases) == 1


def test_the_rhombohedral_macro_takes_an_edge_and_an_angle(tmp_path):
    """`Rhombohedral(a_cv, al_cv)` — the argument-order question, answered.

    The reference's lattice-parameter list prints the argument names, and its
    naming convention says a `cv` suffix means "name and/or value", so the stem
    is the cell key: `a_cv` is the edge and `al_cv` the angle. All three edges
    follow the first, all three angles the second — the rhombohedral setting,
    which is the only cell shape one edge and one angle can describe.

    The order was the whole risk. Read the other way round this phase would come
    back with a 55 Å edge and three right angles, which is not a cell any data
    would fit and is exactly the wrong-number-with-nothing-raised this reader
    exists to prevent. It appears in **no** archive file in live text — it is in
    `archive file 17` only inside a `'` comment — so nothing here corroborates it and
    nothing here contradicts it either; the citation is the whole evidence.
    """
    inp = _inp(tmp_path, "rhomb.inp",
               'str\nphase_name "P"\nspace_group "R-3m:R"\n'
               'Rhombohedral(@ 5.4, @ 55.3)\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert tuple(phase.cell[k] for k in ("a", "b", "c")) == \
        pytest.approx((5.4, 5.4, 5.4))
    assert tuple(phase.cell[k] for k in ("al", "be", "ga")) == \
        pytest.approx((55.3, 55.3, 55.3))
    # Unlike every other macro here, the angle *is* an argument, so it carries
    # its own flag rather than being fixed by the symmetry.
    assert phase.vary["a"] is True and phase.vary["al"] is True
    assert len(to_structure(read_topas_inp(inp)).phases) == 1


@pytest.mark.parametrize("macro", [
    "Orthorhombic(@ 5.4, @ 6.1, @ 7.2)",
    "Monoclinic(@ 5.4, @ 6.1, @ 7.2, @ 99.1)",
    "Triclinic(@ 5.4, @ 6.1, @ 7.2, @ 88, @ 99, @ 101)",
])
def test_a_cell_shaped_macro_this_format_does_not_define_is_refused_by_name(
        tmp_path, macro):
    """Guessing a macro's argument order is worse than declining to read it.

    These three are not cell macros of this format at all: the reference's
    lattice-parameter list has exactly four entries and none is among them, and
    across the whole manual the words occur only as English — crystal-system
    labels, and an `Orthorhombic_Bipyramide` bond-length restraint, which is not
    a cell. They occur in no archive file either, live or commented.

    So a file invoking one invokes a macro somebody defined themselves, and
    nothing states which key each argument carries. A wrong order is a wrong
    cell with nothing raised, so the name is refused rather than parsed. The
    enumerated list is the bound: a new name earns support with its own
    citation, never by analogy with the four already there.
    """
    inp = _inp(tmp_path, "undefined.inp",
               f'str\nphase_name "P"\nspace_group "P1"\n{macro}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "undefined.inp" in str(exc.value)
    assert macro.split("(")[0] in str(exc.value)


def test_a_cell_macro_whose_arity_disagrees_is_refused_by_name(tmp_path):
    """Arity is part of what the reference states, so a `Cubic` handed two
    arguments is not a `Cubic` — and *saying so* is the other half.

    The table this replaced took "the first and last argument that parsed",
    which read `Cubic(4.1, 9.9)` as a = b = 4.1 with c = 9.9 — a tetragonal cell
    out of the macro whose entire meaning is that there is one edge. Declining
    to read it is right; `continue`-ing past it was not, because an empty
    `phase.cell` is the *absent* fact, and `to_structure` then said "phase
    states no cell, so it cannot be built". The phase did not state no cell. It
    stated a cell macro this reader will not read, and the message sent the
    reader of it looking for a missing line instead of at the `Cubic` two lines
    up. The stated-but-unreadable `a` line and the sibling `Orthorhombic(...)`
    both refuse by name; this is the same question and now has the same answer.
    """
    inp = _inp(tmp_path, "arity.inp",
               'str\nphase_name "P"\nspace_group "Pm-3m"\nCubic(4.1, 9.9)\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    msg = str(exc.value)
    assert "arity.inp" in msg
    # The call is quoted, so the message points at the line that is wrong.
    assert "Cubic(4.1, 9.9)" in msg
    assert "1 argument" in msg and "1 arguments" not in msg
    # And it is *not* the absent-cell message, which would be a different fact.
    assert "states no cell" not in msg


def test_the_undefined_macro_refusal_lists_the_macros_this_reader_reads(tmp_path):
    """A refusal's job is to say what the author may write *here*.

    The message used to enumerate four names — the reference's §19.3.2 list —
    while the reader reads five: `Trigonal` is in the table on §1.3's authority.
    The sentence was true about the reference and false about the reader, and
    the reader is what the author is talking to. Derived from `_CELL_MACROS` so
    the two cannot drift; the citation for each stays where a claim about the
    reference belongs, in that table's comment and in `ATTRIBUTION.md`.
    """
    inp = _inp(tmp_path, "enum.inp",
               'str\nphase_name "P"\nspace_group "P1"\n'
               'Orthorhombic(@ 5.4, @ 6.1, @ 7.2)\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    msg = str(exc.value)
    for name in _CELL_MACROS:
        assert name in msg, f"{name} is read but the refusal does not offer it"
    assert "Trigonal" in msg          # the one the four-name sentence dropped
    assert "the reference defines" not in msg
    # The message is templated over the macro name, so the article has to agree
    # with the name it is given rather than with the one it was written for.
    assert "an Orthorhombic" in msg and "a Orthorhombic" not in msg


def test_a_lattice_macro_beside_an_explicit_cell_is_not_needed(tmp_path):
    """An `hkl_Is` Pawley block's macro must not overwrite the `str` phase's own
    cell: the archive's `Hexagonal(` occurrences all sit in such a block, in the
    same chunk as a `str` phase that states a, b, c itself."""
    inp = _inp(tmp_path, "both.inp",
               'str\nphase_name "LiAlCl4"\nspace_group "P121/c1"\n'
               'a 7.018696\nb 6.520921\nc 13.019527\nal 90\nbe 93.32175\nga 90\n'
               'site Al1 x 0.70588 y 0.32198 z 0.89924 occ Al+3 1.\n'
               'hkl_Is\nphase_name "hexagonal from Dicvol"\n'
               'Hexagonal(@  3.500000`, @  12.000000`)\nspace_group "P-6m2"\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell["a"] == pytest.approx(7.018696)
    assert phase.cell["c"] == pytest.approx(13.019527)


def test_a_str_block_that_produced_no_cell_refuses_rather_than_dropping(tmp_path):
    """Report or refuse, never drop — and `weight_percent` is why.

    A phase whose cell could not be read used to be skipped by `to_structure`
    with nothing said, while `model.phases` still carried its weight fraction.
    The QPA numbers then look complete with a phase missing from the
    `Structure`, which is worse than the dropped-*site* case this reader
    already makes a hard error.
    """
    inp = _inp(tmp_path, "nocell.inp",
               'str\nphase_name "real"\nspace_group "P1"\na 5.0\n'
               'weight_percent ph1_wtpct 40.0`\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'str\nphase_name "cell_less"\nspace_group "P4/mmm"\n'
               'weight_percent ph2_wtpct 60.0`\n'
               'site Sr1 x 0 y 0 z 0 occ Sr+2 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert [p.weight_percent for p in model.phases] == pytest.approx([40.0, 60.0])
    with pytest.raises(TopasInpError) as exc:
        to_structure(model)
    assert "nocell.inp" in str(exc.value) and "cell_less" in str(exc.value)


# ------------------------------------------------------------ the encoding

#: One realistic file, written in five encodings. The three a byte-order mark
#: names are read; the two it does not are refused.
_ENCODED = ('r_wp 8.04733245 gof 1.52039055\n'
            'xdd "srm660b.xy"\nCuKa5(0.0001)\n'
            'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
            'Cubic_(lpa 4.15689)\nscale ph1_scale 0.000225160497`\n'
            'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n')


@pytest.mark.parametrize("codec", ["utf-8", "utf-8-sig", "utf-16"])
def test_a_byte_order_mark_is_decoded_not_read_as_utf8(tmp_path, codec):
    """`read_text(encoding="utf-8")` on a UTF-16 file gives zero phases, and
    `to_structure` then says "a Pawley or indexing-only .inp is legal and has
    none" — a confident wrong diagnosis of a *decode* failure.

    `io.formats.base.decode` is the seam that already answers this, shared with
    `head()` rather than duplicated. All 606 archive files are BOM-free, so
    this is latent rather than measured.
    """
    inp = tmp_path / "enc.inp"
    inp.write_bytes(_ENCODED.encode(codec))
    model = read_topas_inp(inp)
    assert [p.name for p in model.phases] == ["LaB6"]
    assert model.r_wp == pytest.approx(8.04733245)
    assert model.data_files == ["srm660b.xy"]
    assert to_structure(model).phases[0].cell.a.value == pytest.approx(4.15689)


def test_a_bom_immediately_before_the_first_str_still_splits(tmp_path):
    """U+FEFF is category Cf, not `\\s`, so `^\\s*str\\s*$` misses a `str` the
    mark is glued to — the one place a UTF-8 BOM actually breaks this reader."""
    inp = tmp_path / "bomfirst.inp"
    inp.write_bytes(('str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
                     'Cubic_(lpa 4.15689)\n'
                     'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n')
                    .encode("utf-8-sig"))
    assert [p.name for p in read_topas_inp(inp).phases] == ["LaB6"]


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
def test_a_utf16_file_with_no_mark_is_refused_naming_the_file(tmp_path, codec):
    """`io/CLAUDE.md`'s `xy` row settles this: a NUL is refused by name *unless*
    behind a BOM, because ASCII-range UTF-16LE is valid UTF-8 with interleaved
    NULs and no byte-order mark says which of LE and BE it is. Guessing is a
    repair this reader cannot say it made, so it refuses instead."""
    inp = tmp_path / f"{codec}.inp"
    inp.write_bytes(_ENCODED.encode(codec))
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert f"{codec}.inp" in str(exc.value)


# ---------------------------------------- the flag grammar, off the one match

def test_the_coordinate_macros_own_flag_is_read(tmp_path):
    """`A1(@xO3, …)` carries its flag *inside* the parenthesis.

    The value grammar was unified and the flag grammar was not, so `refined`'s
    separate regex never looked inside the macro and returned None — which
    `rx.Parameter` then defaults to `vary=False`, i.e. **held**. The tri-state
    this reader argues for collapsed to "held" at the one boundary where the
    file was explicit.
    """
    line = ("site O3 A1(@xO3, 0.00143, 0.00143) A2(!yO3, 0.03550, 0.001) "
            "A3(@zO3, 0.21526, 0.001) occ O 1.0 beq !bval 0.5")
    assert refined("x", line) is True
    assert refined("y", line) is False
    assert refined("z", line) is True
    inp = _inp(tmp_path, "macroflags.inp",
               f'str\nphase_name "P"\nspace_group "P1"\na 5.0\n{line}\n')
    (atom,) = to_structure(read_topas_inp(inp)).phases[0].atoms
    assert (atom.x.vary, atom.y.vary, atom.z.vary) == (True, False, True)


def test_a_write_back_backtick_after_an_evaluated_tail_is_read_as_refined(tmp_path):
    """`scale =scph1*scb1;:  0.0844868572\\`` — the backtick sits after the `;:`
    tail, where the flag regex could not reach it. The value was read
    correctly and the flag was lost, which is the same tri-state error one
    field over."""
    inp = _inp(tmp_path, "tail.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'scale =scph1*scb1;:  0.0844868572`\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.scale == pytest.approx(0.0844868572)
    assert phase.vary["scale"] is True
    assert to_structure(read_topas_inp(inp)).phases[0].scale.vary is True


# ------------------------------------------------------ occ carries a species

@pytest.mark.parametrize("occ, expected", [
    ("occ Ca+2 @ 0.6", True),        # charged and flagged
    ("occ Ca @ 0.6", True),          # uncharged — the one that worked, by luck
    ("occ Ca+2 !n 0.6", False),
    ("occ Ca !n 0.6", False),        # uncharged but *named*: also lost
    ("occ Si !ph1_Si 0.8000", False),        # archive file 13
    ("occ Na+1 !occ_A1 0.5 vcocc", False),   # named and flagged, plus `vcocc`
    ("occ Na+1 1", None),            # the file says nothing
])
def test_an_occupancys_flag_is_read_whatever_the_species(occ, expected):
    """The grammar has **one** name slot and on an `occ` line the species
    consumes it, so `occ Ca @ 0.6` worked by accident and everything else
    returned None. Widening `_NAME` to admit `+`/`-` is not the fix — it is
    load-bearing everywhere else — so `occ` reads past its species first.

    Incidence: 38 real site lines. `occ Si !ph1_Si 0.8000` is a Si/Ge solid
    solution deliberately **held** at 0.8/0.2, arriving as held-by-default
    rather than held-by-file — and a default cannot be told from a decision.
    """
    assert refined("occ", f"site A1 x 0 y 0 z 0 {occ} beq b 0.5") is expected


def test_a_held_occupancy_reaches_the_structure_as_held(tmp_path):
    inp = _inp(tmp_path, "sige.inp",
               'str\nphase_name "SiGe"\nspace_group "Fd-3m:2"\na 5.45\n'
               'site Si1_Si x 0. y 0. z 0. occ Si !ph1_Si 0.8000 beq b 0.5\n'
               'site Si1_Ge x 0. y 0. z 0. occ Ge @ph1_Ge 0.2000 beq b 0.5\n')
    si, ge = to_structure(read_topas_inp(inp)).phases[0].atoms
    assert (si.occ.value, si.occ.vary) == (pytest.approx(0.8), False)
    assert (ge.occ.value, ge.occ.vary) == (pytest.approx(0.2), True)


# -------------------------------------------------- a stated zero is a value

def test_a_stated_zero_scale_is_not_replaced_by_the_default(tmp_path):
    """`ph.scale or 1e-4` substitutes a made-up default for a measured zero.

    A phase refined to absent is a state this repo already recognises — the
    `weight_percent cBN_wtpct 0.000` case above — and 20 real phases across 9
    files state `scale 0`. `or` also destroys the difference between "the file
    stated zero" and "the file said nothing", which is the F3 error again.
    """
    inp = _inp(tmp_path, "off.inp",
               'str\nphase_name "cBN_refined_to_absent"\nspace_group "F-43m"\n'
               'a 3.616466\nscale !ph_off 0\n'
               'site N1 x 0 y 0 z 0 occ N 1. beq !bn 0.30441\n')
    model = read_topas_inp(inp)
    assert model.phases[0].scale == 0.0
    scale = to_structure(model).phases[0].scale
    assert scale.value == 0.0
    assert scale.vary is False


def test_a_phase_stating_no_scale_still_gets_the_seed(tmp_path):
    """The other half of the tri-state: absent is still the 1e-4 seed."""
    inp = _inp(tmp_path, "noscale.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert model.phases[0].scale is None
    assert to_structure(model).phases[0].scale.value == pytest.approx(1e-4)


# ------------------------------------------------- a keyword is not a symbol

#: A realistic file, whose only *declarations* are the two `prm`s and the named
#: values. Measured on the old sweep: 21 symbols bound from these 30 lines,
#: including `beq`, `bkg`, `gof`, `min`, `max`, `r_wp`, `x`, `y`, `z` and the
#: element symbols `B`, `La`, `N` — each bound to an occupancy of 1.0, so a
#: `prm B` would have silently got boron's occupancy.
_REALISTIC = '''r_wp 8.04733245 gof 1.52039055
xdd "srm660b.xy"
    CuKa5(0.0001)
    Radius(217.5)
    bkg @ 128.4 -33.9 12.6 -4.1 1.9
prm scph1 1.0
prm scb1 0.0844868572
str
    phase_name "LaB6"
    space_group "Pm-3m"
    Cubic_(lpa 4.15689)
    scale ph1_scale 0.000225160497`
    weight_percent ph1_wtpct 17.907`
    CS_L(csl1, 210.4)
    site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389
    site B1  x @, 0.19895` y 0.5 z 0.5 occ B 1. beq @, 0.3076`
str
    phase_name "cubic_BN"
    space_group "F-43m"
    a lp_bn 3.616466` min 3.61 max 3.63
    scale ph2_scale 0.00321777397`
    weight_percent cBN_wtpct 82.093`
    site N1 x 0 y 0 z 0 occ N 1. beq @, 0.30441`
'''


@pytest.mark.parametrize("keyword", [
    "a", "b", "c", "x", "y", "z", "beq", "occ", "scale", "weight_percent",
    "bkg", "min", "max", "r_wp", "gof", "site", "prm", "Radius",
])
def test_a_keyword_is_never_bound_as_a_symbol(keyword):
    """The sweep took any `<name> <number>` pair, so every keyword with a bare
    value became a named parameter. Nothing raises when one is then
    substituted into an equation: `_arith` returns a plausible number."""
    assert keyword not in symbol_table(strip_comments(_REALISTIC))


@pytest.mark.parametrize("species", ["La", "B", "N"])
def test_a_species_is_never_bound_as_a_symbol(species):
    """`occ La 1.` puts the species where the grammar's name slot is, so the
    old sweep bound `La` to 1.0 — and a `prm La` would then have lost to it."""
    assert species not in symbol_table(strip_comments(_REALISTIC))


@pytest.mark.parametrize("declared", [
    "scph1", "scb1", "lpa", "ph1_scale", "ph1_wtpct", "bla", "lp_bn",
    "ph2_scale", "cBN_wtpct", "csl1",
])
def test_every_real_declaration_is_still_bound(declared):
    """The narrowing must not cost a name an equation could reach: a `prm`, a
    `local`, the name slot of a keyword's value, and a macro's named argument
    are all declarations."""
    assert declared in symbol_table(strip_comments(_REALISTIC))


def test_a_prm_outranks_an_earlier_sites_coordinate(tmp_path):
    """`setdefault` means the first binding wins, so a real `prm x 0.9999` lost
    to whatever earlier line happened to write `x <number>` — silently, because
    `_resolve` substitutes and `_arith` returns a number."""
    inp = _inp(tmp_path, "collide.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0.1111 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'prm x 0.9999\n'
               'site A2 x = x; y 0 z 0 occ Na+1 1 beq b 0.5\n')
    a1, a2 = read_topas_inp(inp).phases[0].sites
    assert a1.x == pytest.approx(0.1111)
    assert a2.x == pytest.approx(0.9999)


def test_an_equation_reaching_a_keyword_refuses_rather_than_inventing(tmp_path):
    """`y = x;` names no parameter this file declares — `x` is a keyword, not a
    symbol — and the old sweep resolved it to the *first* site's x. Refusing is
    the only honest answer: inventing a coordinate is the one outcome worse
    than declining to read the file."""
    inp = _inp(tmp_path, "keyword_ref.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0.3333 y 0.6667 z 0 occ Na+1 1 beq b 0.5\n'
               'site A2 x 0.1 y = x; z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "keyword_ref.inp" in str(exc.value) and "cannot read y" in str(exc.value)


# ------------------------------------------------ a quote is not a comment

@pytest.mark.parametrize("line", [
    r'''xdd "C:\data\o'brien.xy"''',
    r'''phase_name "d'Alembert phase"''',
])
def test_an_apostrophe_inside_a_quoted_string_is_not_a_comment(line):
    """Cutting at the first `'` truncated the string it sat in: a data file
    became `C:\\data\\o` and a phase became `d`. A silently mislabelled phase
    is a wrong answer with nothing raised; incidence in the archive is 0, so
    this is latent."""
    assert strip_comments(line) == line


def test_a_truncated_string_does_not_reach_the_model(tmp_path):
    inp = _inp(tmp_path, "quoted.inp",
               'r_wp 3.2\nxdd "C:\\data\\o\'brien.xy"\n'
               'str\nphase_name "d\'Alembert"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert model.data_files == ["C:\\data\\o'brien.xy"]
    assert [p.name for p in model.phases] == ["d'Alembert"]


def test_a_real_trailing_comment_is_still_cut(tmp_path):
    """The other side of the same test: a `'` outside a string still opens a
    comment, which is what rule 1 exists for."""
    assert strip_comments('xdd "sample.xy" \' a real comment') == 'xdd "sample.xy" '
    assert strip_comments("str ' don't") == "str "


# ----------------------------------------------- the geometry is a declaration

@pytest.mark.parametrize("line, geometry", [
    # what actually declares a capillary, quoted from the archive
    ("capillary_u_cm_inv @, 36.0187505", "debye_scherrer"),
    ("capillary_diameter_mm 0.5", "debye_scherrer"),
    ("capillary_parallel_beam", "debye_scherrer"),
    ("Cylindrical_2Th_Correction(@, 0.91181`)", "debye_scherrer"),
    ("Cylindrical_I_Correction(2.64)", "debye_scherrer"),
    # and what does not: a name, a path and a parameter are not declarations
    ('phase_name "Debye_test_material"', "bragg_brentano"),
    ('xdd "C:/data/debye_run3.xy"', "bragg_brentano"),
    ("prm capillary_diam 0.7", "bragg_brentano"),
    ('phase_name "MgO_cylindrical_ref"', "bragg_brentano"),
])
def test_the_geometry_is_decided_by_a_declaration_not_by_a_name(
        tmp_path, line, geometry):
    """The sniff matched `Cylindrical_|capillary|Debye` case-insensitively over
    the whole file, so a phase called `Debye_test_material` flipped a file
    carrying `Radius(217.5)` and `LP_Factor(26.4)` — unambiguously
    Bragg-Brentano — to `debye_scherrer`.

    A geometry is declared by a *statement*, so the token has to open a line.
    Incidence in the archive is 0, so this is latent; what the archive does
    show is that `Debye` appears in **no** file, while the tokens above are how
    the 26 capillary files actually say it.
    """
    inp = _inp(tmp_path, "geom.inp",
               f'r_wp 4.1\nRadius(217.5)\nCuKa5(0.0001)\nLP_Factor(26.4)\n{line}\n'
               'str\nphase_name "LaB6"\nspace_group "Pm-3m"\n'
               'Cubic_(lpa 4.15689)\n'
               'site La1 x 0 y 0 z 0 occ La 1. beq !bla 0.4389\n')
    assert read_topas_inp(inp).geometry == geometry


# ------------------------------ a stated key that cannot be read refuses

@pytest.mark.parametrize("key, line", [
    ("a", "a = a*1.0;"),
    ("c", "c = a*1.633;"),
    ("al", "al = nothing_defined;"),
    ("be", "be = 90+nothing_defined;"),
    # `b =Get(a);` used to sit here and is now read — see
    # `test_a_coupled_edge_written_with_get_reads_the_edge_it_names`. `Get`
    # resolves against the keys already read for *this* phase, and this fixture
    # states no `al`, so this row survives for the right reason: the name is out
    # of scope, not the built-in unevaluated. What refuses is `ga` — the key the
    # phase states — and not the `al` it merely references.
    ("ga", "ga =Get(al);"),
])
def test_a_stated_cell_key_that_cannot_be_read_refuses_naming_it(
        tmp_path, key, line):
    """Whether the cell is right must not turn on whether the author *named*
    the edge, which no caller can see.

    Measured: `a 3.000` + `c = a*1.633;` + `ga 120` built c = 3.0 for a stated
    4.899 — 63 % low — because `a` is a keyword and not a symbol, so the
    equation is unresolvable, the key was `continue`d and `to_structure`
    substituted `c["a"]`. The same substitution on an angle makes an
    unresolvable `be = …;` read 90.0, so a monoclinic phase arrives
    orthorhombic with nothing raised. `a` already refused (in `to_structure`,
    for want of a cell); the other five now refuse symmetrically, at read,
    where the line can be named.
    """
    base = "" if key == "a" else "a 3.0\n"
    inp = _inp(tmp_path, "silent.inp",
               f'str\nphase_name "P"\nspace_group "P1"\n{base}{line}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "silent.inp" in str(exc.value)
    assert f"cannot read {key}" in str(exc.value)
    assert line.strip() in str(exc.value)


def test_naming_the_edge_is_what_made_the_difference(tmp_path):
    """The measured pair, side by side: the same cell, written twice.

    `c = lpa*1.633;` resolves because `a lpa 3.000` *declares* `lpa`, so this
    half always worked. Nothing about the file says which spelling the author
    would use, which is why the other half may not answer.
    """
    inp = _inp(tmp_path, "named.inp",
               'str\nphase_name "P"\nspace_group "P63/mmc"\n'
               'a lpa 3.000\nc = lpa*1.633;\nga 120\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell["c"] == pytest.approx(4.899)
    assert to_structure(read_topas_inp(inp)).phases[0].cell.c.value == \
        pytest.approx(4.899)


# ---------------------------- a coupled edge, written with the Get built-in

def test_a_coupled_edge_written_with_get_reads_the_edge_it_names(tmp_path):
    """`Get(a)` is the one spelling in which a cell edge may name another edge.

    The reference documents the built-in in its own right — the value of the
    name, searched for locally and then outward — and gives the reason it
    exists: a bare name in an equation reaches a *parameter*, and a cell keyword
    is not one. So this is not a macro being expanded; it is a documented
    function applied to the scope the cell keys already form.

    The archive's own form, from 4 files (the PbPdO2/PdO fits): a tetragonal
    phase writes `a`, then couples `b` to it. Refusing it used to cost the whole
    file, because a stated-but-unreadable key refuses rather than defaulting.
    """
    inp = _inp(tmp_path, "coupled.inp",
               'str\nphase_name "PdO"\nspace_group "P42/mmc"\n'
               'a @ 3.042155`\nb =Get(a);\nc @ 5.337079`\n'
               'site Pd x 0 y 0 z 0 occ Pd 1. beq 0.3\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell["a"] == pytest.approx(3.042155)
    assert phase.cell["b"] == pytest.approx(3.042155)
    assert phase.cell["c"] == pytest.approx(5.337079)
    # The coupled edge is a *dependent* parameter, not a second refined one:
    # `a` carries the flag and `b` states an equation, so `b` gets no `vary`.
    assert phase.vary["a"] is True and "b" not in phase.vary
    built = to_structure(read_topas_inp(inp)).phases[0].cell
    assert built.b.value == pytest.approx(3.042155)


def test_get_couples_all_three_edges_of_a_cubic_phase(tmp_path):
    """Both edges of a cubic phase written longhand — the archive's cBN phase,
    which came back with a = 3.615 and nothing else readable."""
    inp = _inp(tmp_path, "cbn.inp",
               'str\nphase_name "cubic_BN"\nspace_group "F-43m"\n'
               'a @ 3.615081`\nb =Get(a);\nc =Get(a);\n'
               'site B x 0 y 0 z 0 occ B 1. beq 0.3\n')
    cell = read_topas_inp(inp).phases[0].cell
    assert (cell["a"], cell["b"], cell["c"]) == \
        pytest.approx((3.615081, 3.615081, 3.615081))


def _coupling_diags(inp):
    """The `TOPAS_CELL_COUPLING_DROPPED` records one read leaves behind."""
    diags = []
    read_topas_inp(inp, diagnostics=diags)
    return [d for d in diags if d.code == "TOPAS_CELL_COUPLING_DROPPED"]


_COUPLED = ('str\nphase_name "P"\nspace_group "%s"\n'
            'a @ 5.0\nb =Get(a);\nc @ 7.0\nal 90\nbe 90\nga 90\n'
            'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')


def test_a_dropped_cell_coupling_is_reported_not_dropped_in_silence(tmp_path):
    """`Get` resolution copies the **value**; the constraint does not travel.

    Before this round the four archive files that write `b = Get(a);` refused
    outright, so reading them is a repair — and root `CLAUDE.md`'s rule is that
    a reader may repair a file only where it can say that it did. In `P 1`
    nothing ties `b` to `a`: the built model frees `a` and holds `b` at the 5.0
    it was handed, which is a third thing neither the file (they move together)
    nor rietx unaided (both free) would have produced. The channel exists and
    three codes already go down it, so this one does too.
    """
    inp = _inp(tmp_path, "p1.inp", _COUPLED % "P 1")
    diags = _coupling_diags(inp)
    assert len(diags) == 1
    only = diags[0]
    assert only.level == "warning"
    assert only.where == ["phases.P.cell.b"]
    # It names the *pair*, not just "a coupling was lost".
    assert "b" in only.message and "Get(a)" in only.message
    assert "P 1" in only.message           # and the symmetry it asked
    # The value still arrives: this reports the repair, it does not undo it.
    assert read_topas_inp(inp).phases[0].cell["b"] == pytest.approx(5.0)


@pytest.mark.parametrize("sg", ["P 4/m m m", "P42/mmc", "Fm-3m", "P63/mmc"])
def test_a_coupling_the_phases_symmetry_reproduces_is_not_reported(tmp_path, sg):
    """The half that makes the code a fact rather than a reflex.

    Under any of these rietx ties `b <- a` itself through `cell_constraints`, so
    the built model states exactly what the file stated and nothing was dropped.
    Reporting anyway would fire on **every** coupled file in the corroborating
    archive — all 11 couplings across those 4 PbPdO2/PdO fits are tetragonal,
    hexagonal or cubic — and a warning that is always on tells a caller nothing.
    """
    inp = _inp(tmp_path, "sym.inp", _COUPLED % sg)
    assert _coupling_diags(inp) == []


def test_a_coupling_is_followed_to_its_tie_root_before_being_reported(tmp_path):
    """A tie table names one representative, not every pair.

    Cubic ties `b -> a` and `c -> a`, so `c = Get(b);` *is* reproduced even
    though no entry reads `c -> b`. Comparing the two keys against each other
    rather than against their roots would report this one, on a phase whose
    symmetry holds all three edges equal by construction.
    """
    inp = _inp(tmp_path, "root.inp",
               'str\nphase_name "P"\nspace_group "Pm-3m"\n'
               'a @ 4.0\nb =Get(a);\nc =Get(b);\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert _coupling_diags(inp) == []
    assert read_topas_inp(inp).phases[0].cell["c"] == pytest.approx(4.0)


def test_an_unresolvable_symbol_reports_the_coupling_rather_than_assuming_it(
        tmp_path):
    """Not being able to *show* the model carries the tie is not showing it does.

    A symbol this package cannot turn into constraints gets the reported answer,
    because silence here is the claim "rietx ties these anyway" and that claim
    needs a space group behind it. `_symmetry_reproduces` returns False on any
    lookup failure for exactly this reason.
    """
    inp = _inp(tmp_path, "odd.inp", _COUPLED % "not a space group")
    assert len(_coupling_diags(inp)) == 1


def test_the_coupling_record_comes_from_the_keys_own_equation(tmp_path):
    """TOPAS is whitespace-insensitive, so one line may state several keys.

    `a @ 5.0 b =Get(a); c @ 7.0` is three keys on one line. Scanning the *line*
    for `Get(` would attribute `b`'s equation to `a` and to `c` as well and
    report three couplings where the file wrote one — which is why the
    expression travels on the `_Read` that was computed from it.
    """
    inp = _inp(tmp_path, "oneline.inp",
               'str\nphase_name "P"\nspace_group "P 1"\n'
               'a @ 5.0 b =Get(a); c @ 7.0\nal 90 be 90 ga 90\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    diags = _coupling_diags(inp)
    assert [d.where for d in diags] == [["phases.P.cell.b"]]


def test_a_get_reference_is_not_a_statement_of_the_key_it_names(tmp_path):
    """The trap the two mask views exist for.

    `b = Get(a);` *states* `b` and only *references* `a`. If the scan that
    locates a key saw the referenced name, a phase would be reported as stating
    an edge it never wrote — and on an angle it is worse than cosmetic: this
    fixture states no `al`, so a located-but-unreadable `al` would refuse the
    whole file with a message naming a key the author never typed.
    """
    inp = _inp(tmp_path, "ref.inp",
               'str\nphase_name "P"\nspace_group "P4/mmm"\n'
               'a 3.0\nb =Get(a);\nc 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert sorted(phase.cell) == ["a", "b", "c"]
    assert "al" not in phase.cell and "ga" not in phase.cell


def test_a_get_naming_nothing_in_scope_still_refuses(tmp_path):
    """Widening what can be read has not widened what can be guessed: a name in
    neither the phase's own keys nor the file's symbols resolves to nothing, and
    the key that states it refuses exactly as any other unresolvable value."""
    inp = _inp(tmp_path, "oos.inp",
               'str\nphase_name "P"\nspace_group "P1"\n'
               'a 3.0\nb =Get(never_declared);\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "cannot read b" in str(exc.value)


def test_get_reaches_the_files_own_symbols_as_the_outer_scope(tmp_path):
    """"…if not found it searches its parent's scope": a `Get` naming a declared
    `prm` resolves through the symbol table, which is this reader's flat stand-in
    for the enclosing scopes."""
    inp = _inp(tmp_path, "prm.inp",
               'prm lp 4.0\nstr\nphase_name "P"\nspace_group "Pm-3m"\n'
               'a =Get(lp);\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq 0.5\n')
    assert read_topas_inp(inp).phases[0].cell["a"] == pytest.approx(4.0)


def test_a_forward_get_reference_refuses_rather_than_reading_zero(tmp_path):
    """The keys are read in a/b/c/al/be/ga order, so `b = Get(c);` above a
    stated `c` cannot resolve. That refuses — the honest answer — rather than
    silently coming back with whatever the partial scope held."""
    inp = _inp(tmp_path, "fwd.inp",
               'str\nphase_name "P"\nspace_group "P4/mmm"\n'
               'a 3.0\nb =Get(c);\nc 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "cannot read b" in str(exc.value)


def test_the_mask_still_hides_every_other_macro_argument(tmp_path):
    """The `Get` exemption is an exact match, so it did not reopen the hole the
    argument blanking closed: a named `lpa` inside `Cubic_(lpa …)` is still the
    macro's argument and not an `a` line, on both views of the mask."""
    chunk = 'Cubic_(lpa 4.15689)\nOut_X_Ycalc("site.xy")\n'
    for keep in (False, True):
        scan = _cell_search_text(chunk, keep_get=keep)
        assert "lpa" not in scan
        assert "site" not in scan
    # …and the one name a `Get` holds survives only on the view that asks for it.
    assert "Get(a)" in _cell_search_text("b =Get(a);\n", keep_get=True)
    assert "Get(a)" not in _cell_search_text("b =Get(a);\n")


def test_a_cell_key_the_phase_never_states_still_keeps_its_default(tmp_path):
    """The other half of the rule, and it stays unchanged: an **absent** line is
    a different fact from an unreadable one. A cubic phase writes `a` alone."""
    inp = _inp(tmp_path, "cubic.inp",
               'str\nphase_name "W"\nspace_group "Im-3m"\na 3.158949\n'
               'site W1 x 0 y 0 z 0 occ W 1. beq 0.3\n')
    phase = read_topas_inp(inp).phases[0]
    assert list(phase.cell) == ["a"]
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert (cell.b.value, cell.c.value) == pytest.approx((3.158949, 3.158949))
    assert (cell.alpha.value, cell.gamma.value) == pytest.approx((90.0, 90.0))


# ---------------------------- a str chunk ends at the next block opener

def test_a_trailing_pawley_block_lends_the_phase_above_nothing(tmp_path):
    """`re.split(r"^\\s*str\\s*$")` ends a chunk only at the next `str`, so a
    trailing `hkl_Is` belonged to the phase above it and `_read`/`_field` swept
    the whole thing — three of the neighbour's numbers, silently.

    Measured on the real file: `archive file 4` gave
    tungsten b = 3.814 and c = 19.299 off the Nb2O5 block's
    `load hkl_m_d_th2 I` table, where 3.814 is a **d-spacing** column read as a
    cell edge. It is F1's failure mode moved from the cell regex to the block
    splitter, and it reaches the scale and the weight percent too.
    """
    inp = _inp(tmp_path, "bleed.inp",
               'str\n'
               '  phase_name "structural"\n  space_group "Fm-3m"\n  a 4.0\n'
               '  scale @ 0.001\n'
               '  site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'hkl_Is\n'
               '  a 3.1\n  c 19.3\n  scale @ 0.00987\n  weight_percent 61.4\n')
    (phase,) = read_topas_inp(inp).phases
    assert phase.cell == {"a": pytest.approx(4.0)}
    assert phase.scale == pytest.approx(0.001)
    assert phase.weight_percent is None
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert (cell.a.value, cell.c.value) == pytest.approx((4.0, 4.0))


@pytest.mark.parametrize("opener", [
    "hkl_Is",           # 139 line-initial occurrences in the archive
    "xo_Is",            # 277
    "xdd \"next.xye\"",  # 609 — a new dataset ends the phase too
    "fit_obj",          # 2
    "str",              # the one it already ended at
])
def test_every_block_opener_ends_the_phase_above_it(tmp_path, opener):
    """A `.inp` has no closing brace, so a phase's text runs to the next block
    opener — of *any* kind, not to the next `str`. The counts are the archive's,
    line-initial and after comment stripping. `macro` is deliberately **not**
    here: it is excised as a definition, not treated as an opener (see
    `test_a_macro_definition_inside_a_str_block_does_not_truncate_the_phase`)."""
    inp = _inp(tmp_path, "openers.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               f'{opener}\nweight_percent 61.4\nc 19.3\n')
    (phase,) = read_topas_inp(inp).phases
    assert phase.weight_percent is None
    assert "c" not in phase.cell


def test_a_phase_after_a_pawley_block_is_still_read(tmp_path):
    """The splitter must not lose a `str` that follows another block."""
    inp = _inp(tmp_path, "after.inp",
               'str\nphase_name "first"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'hkl_Is\nphase_name "pawley"\na 3.1\n'
               'str\nphase_name "second"\nspace_group "P1"\na 5.0\n'
               'site B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert [p.name for p in model.phases] == ["first", "second"]
    assert [p.cell["a"] for p in model.phases] == pytest.approx([4.0, 5.0])


def test_a_str_block_with_no_phase_name_is_recorded_not_passed_over(tmp_path):
    """Measured, on `archive file 6`: a `str` block stating a cell and two
    sites and **no** `phase_name` used to arrive named "CaO" with scale 1.0 —
    both read off the `hkl_Is` block below it. That is finding 2 on a real file.

    Ending the chunk at the `hkl_Is` removes the wrong name, and then the
    reader must not go quiet about the block: answering "a Pawley or
    indexing-only .inp is legal and has none" about a file carrying a cell and
    two sites is the same confident wrong diagnosis a UTF-16 decode used to
    get. The block cannot be *named* — taking the neighbour's name is the bug —
    so it is recorded and the refusal quotes it.
    """
    inp = _inp(tmp_path, "unnamed.inp",
               'str\n  a 4.8152\n  space_group "Fm-3m"\n'
               '  site Ca1 x 0 y 0 z 0 occ Ca+2 1. beq 0.019\n'
               '  site O1 x 0.5 y 0.5 z 0.5 occ O-2 1. beq 0.016\n'
               '#ifdef phase_1_\nhkl_Is\n  phase_name "CaO"\n  scale nb_scale 1`\n'
               '  a 4.8152\n#endif\n')
    model = read_topas_inp(inp)
    assert model.phases == []
    (sb,) = model.skipped_blocks
    # It records what it lacked *and* what it carried (finding 4): the cell it
    # states is exactly what makes it a phase in all but its name.
    assert (sb.lacked, sb.n_sites, sb.cell) == ("phase_name", 2, {"a": 4.8152})
    assert str(sb) == ("a `str` block stating 2 site lines but no phase_name, "
                       "carrying a cell (a)")
    with pytest.raises(TopasInpError) as exc:
        to_structure(model)
    assert "2 site lines but no phase_name" in str(exc.value)
    assert "indexing-only" not in str(exc.value)


# ------------------------------------------- STR(...) is refused by name

def test_a_phase_opening_with_the_STR_macro_is_refused_by_name(tmp_path):
    """`STR(R-3)` expands to a whole `str` block from a macro library this
    reader does not have and may not reproduce.

    Such a file returned **zero** phases and `to_structure` then answered "A
    Pawley or indexing-only .inp is legal and has none" — a confident wrong
    diagnosis about a file that plainly contains `STR(`. Seven archive files
    are affected (`archive file 14`, `archive file 15`, `archive file 16`, `archive file 17` and
    three variants of archive file 18), all returning no phase at all.
    Expanding the macro can wait; answering wrongly about it cannot.
    """
    inp = _inp(tmp_path, "strmacro.inp",
               'r_wp 3.2\nxdd "sample.xye"\n'
               'STR(R-3)\nphase_name "corundum"\n'
               'STR(Fm-3m)\nphase_name "silicon"\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "strmacro.inp" in str(exc.value)
    assert "STR(R-3)" in str(exc.value) and "2 phases" in str(exc.value)


# --------------------------------------- beq: refused, never moved or leaked

def test_a_negative_beq_is_refused_naming_the_site_never_clamped(tmp_path):
    """`max(s.beq, 0.0)` moved a stated −0.42 to 0.0 with nothing said.

    A slightly negative refined B is an ordinary outcome of a converged
    refinement — the column absorbs absorption and normalisation error, and 75
    sites across 11 archive files state one — so this is the reader repairing
    where it cannot say that it did, the rule its own tri-state argument rests
    on. Moving it changes every high-Q intensity, so it is a contradiction
    rather than a deviation a reader may repair, and the sibling `.pcr` reader
    refuses the same value: one story whichever code wrote the file. The number
    stays readable on `model.phases`.
    """
    inp = _inp(tmp_path, "negb.inp",
               'str\nphase_name "Co10Ge3O16"\nspace_group "P1"\na 8.3\n'
               'site GE1 x 0 y 0 z 0 occ Ge+4 1 beq bge -0.42`\n')
    model = read_topas_inp(inp)
    assert model.phases[0].sites[0].beq == pytest.approx(-0.42)
    with pytest.raises(TopasInpError) as exc:
        to_structure(model)
    assert "negb.inp" in str(exc.value) and "GE1" in str(exc.value)
    assert "-0.42" in str(exc.value)


def test_a_schema_refusal_from_the_cell_or_the_atoms_is_still_converted(tmp_path):
    """`rx.Cell(...)` and the `atoms` comprehension sat **outside** the try that
    exists to convert a schema report into a reader's refusal — one line above
    it — so only the `rx.Phase(...)` call was covered and `beq bA 26.0` reached
    the caller as a raw `pydantic_core.ValidationError`.

    The truncation pin cannot catch this class: a ragged cut rarely leaves a
    well-formed line carrying an out-of-range number, so it is tested directly.
    26 Å² is outside the [0, 25] window `Atom.biso` itself declares, which is
    where the bound comes from — the reader quotes it rather than inventing it.
    """
    inp = _inp(tmp_path, "outofrange.inp",
               'str\nphase_name "hot"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq bA 26.0\n')
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp))
    assert "outofrange.inp" in str(exc.value) and "hot" in str(exc.value)


# ------------------------------------------------------------ the robustness pin

def test_a_truncated_inp_never_escapes_as_anything_but_a_topas_error(tmp_path):
    """`io/CLAUDE.md`'s refusal rule, pinned: a reader raises `TopasInpError`
    naming the file, never its parser's exception.

    This is the `test_readers_robust.py` arm one subtree over, and the reason
    it is written down is that the rule is easy to lose — a ragged cut through
    a site line or a macro argument is exactly where a bare `ValueError` or an
    `IndexError` gets out. Bounded to ~200 offsets on purpose: the same sweep
    at every byte offset of seven real archive files (~57 700 truncations) also
    passes, and it is not a test anyone should wait for.
    """
    raw = _REALISTIC.encode("utf-8")
    target = tmp_path / "cut.inp"
    offsets = sorted({round(i * len(raw) / 199) for i in range(200)})
    for n in offsets:
        target.write_bytes(raw[:n])
        try:
            to_structure(read_topas_inp(target))
        except TopasInpError:
            pass
        except Exception as exc:            # noqa: BLE001 — the point of the test
            raise AssertionError(
                f"truncation at {n} of {len(raw)} bytes escaped as "
                f"{type(exc).__name__}: {exc}") from exc


# ============================================================ round-three review
# The grammar is unified per keyword; the scan was still per line, and TOPAS is
# whitespace-insensitive — so a cell or a second site packed onto one line was
# read wrong or dropped. Each reproduction below is the reviewer's own.

# ---------------------------- finding 1: a cell packed onto one line

@pytest.mark.parametrize("cell_line, expected", [
    # `a 5.4 b 6.1 c 7.2` read only `a` and built a=b=c — orthorhombic arrived
    # cubic with nothing raised.
    ("a 5.4 b 6.1 c 7.2", {"a": 5.4, "b": 6.1, "c": 7.2}),
    # the same with parameter names, so `b` is not the line's first token.
    ("a lpa 5.4 b lpb 6.1 c lpc 7.2", {"a": 5.4, "b": 6.1, "c": 7.2}),
    # `al 90 be 90 ga 120` read only `al`, so `ga` defaulted to 90.
    ("a 5.4\nal 90 be 90 ga 120", {"a": 5.4, "al": 90.0, "be": 90.0, "ga": 120.0}),
])
def test_a_cell_packed_onto_one_line_reads_every_key(tmp_path, cell_line, expected):
    """The stated-key refusal was gated on `re.match(rf"\\s*{key}\\b", ln)`, a
    line anchor, so a cell key mid-line was invisible to both the read and the
    refusal. The scan is token-oriented now, after `_cell_search_text` blanks
    the macro parentheses the anchor existed to protect."""
    inp = _inp(tmp_path, "packed.inp",
               f'str\nphase_name "P"\nspace_group "P1"\n{cell_line}\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    for key, value in expected.items():
        assert phase.cell[key] == pytest.approx(value)


def test_an_orthorhombic_cell_on_one_line_does_not_arrive_cubic(tmp_path):
    """`a 5.4 b 6.1 c 7.2` built a=b=c=5.4 and an orthorhombic phase arrived
    cubic with nothing raised — the reviewer's first example, through the
    build."""
    inp = _inp(tmp_path, "ortho.inp",
               'str\nphase_name "ortho"\nspace_group "Pmmm"\n'
               'a 5.4 b 6.1 c 7.2\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert (cell.a.value, cell.b.value, cell.c.value) == \
        pytest.approx((5.4, 6.1, 7.2))


def test_a_hexagonal_gamma_on_a_packed_angle_line_is_not_ninety(tmp_path):
    """`al 90 be 90 ga 120` read `ga` as 90, so a P6/mmm built with gamma 90 and
    the eventual refusal was ParameterTable's, naming the cell rather than the
    file. Read correctly, gamma is 120 and no refusal follows."""
    inp = _inp(tmp_path, "hex.inp",
               'str\nphase_name "hex"\nspace_group "P6/mmm"\n'
               'a 3.6 b 3.6 c 5.9\nal 90 be 90 ga 120\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    cell = to_structure(read_topas_inp(inp)).phases[0].cell
    assert cell.gamma.value == pytest.approx(120.0)


def test_a_named_macro_argument_is_not_read_as_a_cell_line(tmp_path):
    """The line anchor kept `lpa` inside `Cubic_(lpa …)` off the `a` scan; the
    token scan keeps that by blanking macro parentheses, so even a macro whose
    argument is *literally* `a` is the macro's, not an `a` line."""
    inp = _inp(tmp_path, "namedarg.inp",
               'str\nphase_name "P"\nspace_group "Pm-3m"\n'
               'Cubic_(a 4.15689)\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    cell = read_topas_inp(inp).phases[0].cell
    assert cell["a"] == pytest.approx(4.15689)   # from the macro, filling b, c
    assert cell["b"] == pytest.approx(4.15689)


# ---------------------------- finding 2: a second site on one line

def test_a_second_site_on_one_line_is_a_second_atom(tmp_path):
    """`site A1 … beq b 0.5 site B1 x 0.5 …` gave one atom, nothing raised — the
    per-line scan matched the line once, and the count guard `len(sites) !=
    len(site_lines)` counted lines, so the missing site was never a line.
    `_SITE_KEYWORDS` already lists `site` as an occupancy terminator, so the
    grammar half knew; the sites are split token-wise now (finding 2)."""
    inp = _inp(tmp_path, "twosite.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq bA 0.5 '
               'site B1 x 0.5 y 0.5 z 0.5 occ Cl-1 1 beq bB 0.8\n')
    sites = read_topas_inp(inp).phases[0].sites
    assert [s.label for s in sites] == ["A1", "B1"]
    assert (sites[1].x, sites[1].y, sites[1].z) == pytest.approx((0.5, 0.5, 0.5))
    assert sites[1].beq == pytest.approx(0.8)
    atoms = to_structure(read_topas_inp(inp)).phases[0].atoms
    assert [a.label for a in atoms] == ["A1", "B1"]


# ---------------------- finding 2: a mixed site keeps every species

def test_a_mixed_site_with_several_occ_tokens_builds_one_atom_per_species(tmp_path):
    """`occ Al+3 0.9 occ Cr+3 0.1` on one line is a mixed site — the two-`site`-
    line spelling already builds two atoms, and this maps to the same
    representation (round-five finding 2). The predecessor returned Al alone,
    silently, and the phase's Z·M was then that of the wrong composition. Three
    occ tokens, same."""
    inp = _inp(tmp_path, "mixed.inp",
               'str\nphase_name "M"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0.1 y 0.2 z 0.3 occ Al+3 0.9 occ Cr+3 0.1 beq b 0.5\n')
    sites = read_topas_inp(inp).phases[0].sites
    assert [(s.species, s.occupancy) for s in sites] == [("Al3+", 0.9), ("Cr3+", 0.1)]
    # the label, coordinates and B are shared, exactly as the two-line form
    assert all(s.label == "A1" for s in sites)
    assert all((s.x, s.y, s.z) == pytest.approx((0.1, 0.2, 0.3)) for s in sites)
    assert all(s.beq == pytest.approx(0.5) for s in sites)
    atoms = to_structure(read_topas_inp(inp)).phases[0].atoms
    assert [a.species for a in atoms] == ["Al3+", "Cr3+"]


def test_three_occ_tokens_on_one_site_build_three_atoms(tmp_path):
    inp = _inp(tmp_path, "tri.inp",
               'str\nphase_name "M"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Al+3 0.8 occ Cr+3 0.1 occ Fe+3 0.1 beq b 0.5\n')
    sites = read_topas_inp(inp).phases[0].sites
    assert [(s.species, s.occupancy) for s in sites] == \
        [("Al3+", 0.8), ("Cr3+", 0.1), ("Fe3+", 0.1)]


def test_a_dropped_second_species_is_a_wrong_cell_mass(tmp_path):
    """The QPA cost the reviewer measured, pinned as a Z·M (= cell_mass): the
    mixed site's second species carries mass, and dropping it changes the
    phase's Z·M and so its Hill-Howard weight fraction. On a constructed two-
    phase mixture the reviewer measured Z·M 147.986 (both species) against
    89.874 (the first alone), a 10.2 wt% error. The construction here is an
    Fm-3m 4a site half Al half Cr: Z·M 157.9553 with both species against
    53.9631 with Al alone."""
    from rietx.optimize.qpa import phase_zmv

    def _zm(line):
        st = to_structure(read_topas_inp(_inp(
            tmp_path, "zm.inp",
            'str\nphase_name "M"\nspace_group "Fm-3m"\na 4.2\n' + line + "\n")))
        ph = st.phases[0]
        return phase_zmv(ph.space_group, ph.cell.lengths_angles(),
                         [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
                          for a in ph.atoms]).cell_mass

    both = _zm('site A1 x 0 y 0 z 0 occ Al+3 0.5 occ Cr+3 0.5 beq b 0.5')
    al_only = _zm('site A1 x 0 y 0 z 0 occ Al+3 0.5 beq b 0.5')
    assert both == pytest.approx(157.9553, abs=1e-3)
    assert al_only == pytest.approx(53.9631, abs=1e-3)
    assert both > al_only            # the dropped species was mass, not noise


# ------------------ finding 3: species and occupancy travel together

def test_a_species_takes_its_own_value_not_the_next_occs(tmp_path):
    """`occ Al+3 occ Cr+3 0.1` — the predecessor read the species off match one
    and the value off match two, so **Al** arrived at 0.1, Cr's value (round-
    five finding 3). Each occ token is read once now: Al states no value and
    keeps the format's own 1.0, Cr states 0.1 and keeps it."""
    inp = _inp(tmp_path, "pair.inp",
               'str\nphase_name "M"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Al+3 occ Cr+3 0.1 beq b 0.5\n')
    sites = read_topas_inp(inp).phases[0].sites
    assert [(s.species, s.occupancy) for s in sites] == [("Al3+", 1.0), ("Cr3+", 0.1)]


# ---------------------------- finding 3: the splitter's own guard is blind

def test_a_macro_definition_inside_a_str_block_does_not_truncate_the_phase(tmp_path):
    """A `macro dummy { 1 }` DEFINITION inside a `str` block truncated the phase
    (one atom, `weight_percent None`, silent) because `macro` was treated as a
    block opener, and the per-phase count guard was blind by construction — both
    its numbers came off the same truncated chunk. A macro is excised as a
    definition now, so the phase continues past it (finding 3)."""
    inp = _inp(tmp_path, "macrodef.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'macro dummy { 1 }\n'
               'weight_percent wp 42.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'site B1 x 0.5 y 0.5 z 0.5 occ Cl-1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert [s.label for s in phase.sites] == ["A1", "B1"]
    assert phase.weight_percent == pytest.approx(42.0)


def test_the_file_level_site_guard_counts_over_the_whole_file(tmp_path):
    """The per-phase guard is computed from the splitter's own output, so it
    cannot see a splitter error. The file-level guard counts `site` tokens over
    `active`, independent of the split (finding 3): a `site` the reader neither
    parsed into a phase nor recorded on a skipped block is refused, naming the
    file."""
    inp = _inp(tmp_path, "guard.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'hkl_Is\nphase_name "pawley"\n'
               'site STRAY x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "guard.inp" in str(exc.value) and "site` tokens" in str(exc.value)


# ---------------------------- finding 4: a skipped phase dropped while one builds

def test_a_nameless_phase_that_carries_a_cell_is_not_dropped_while_another_builds(
        tmp_path):
    """`to_structure` quoted `skipped_blocks` only in the zero-phase branch, so
    a nameless second phase (60 wt%) vanished when the first phase read and the
    totals no longer summed (finding 4). It refuses instead — the choice
    consistent with io/CLAUDE.md's "report or refuse, never drop" where there is
    no diagnostics channel — and the skipped block records the cell, scale and
    weight_percent it carried, not only its site count."""
    inp = _inp(tmp_path, "twophase.inp",
               'str\nphase_name "A"\nspace_group "P1"\na 5.0\n'
               'weight_percent wpA 40.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'str\nspace_group "Fm-3m"\na 4.2\n'
               'scale scB 0.01\nweight_percent 60.0\n'
               'site B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert [p.name for p in model.phases] == ["A"]
    (sb,) = model.skipped_blocks
    assert sb.lacked == "phase_name"
    assert sb.cell["a"] == pytest.approx(4.2)
    assert sb.scale == pytest.approx(0.01)
    assert sb.weight_percent == pytest.approx(60.0)
    with pytest.raises(TopasInpError) as exc:
        to_structure(model)
    assert "twophase.inp" in str(exc.value)
    assert "no longer summing" in str(exc.value)


# ---------------------------- finding 5: beq's 0.5 seed is a builder's, not a fact

def test_a_site_that_states_no_beq_is_none_on_the_model_and_seeded_at_build(tmp_path):
    """`beq` substituted 0.5 where the site line stated none, and a caller could
    not tell it from a stated value though `TopasModel` is "what a .inp states"
    (finding 5). `beq` is `None` on the model now; the 0.5 seed moves to
    `to_structure`. `occ` defaulting to 1.0 is the format's own default and is
    left alone."""
    inp = _inp(tmp_path, "nobeq.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1\n')
    site = read_topas_inp(inp).phases[0].sites[0]
    assert site.beq is None
    assert site.occupancy == pytest.approx(1.0)
    biso = to_structure(read_topas_inp(inp)).phases[0].atoms[0].biso
    assert biso.value == pytest.approx(0.5)


def test_a_stated_beq_is_kept_verbatim_and_not_confused_with_the_seed(tmp_path):
    """The other half: a *stated* beq — including a stated 0.5 — is the file's,
    read as-is, and distinguishable from the absent case above only because the
    absent one is `None`."""
    inp = _inp(tmp_path, "yesbeq.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert read_topas_inp(inp).phases[0].sites[0].beq == pytest.approx(0.5)


# ------------- round-five finding 1: a stated tensor is carried, built on
# opt-in, and never silently replaced by the isotropic seed

ADP_TAIL = 'u11 0.013 u22 0.013 u33 0.013 u12 0 u13 0 u23 0'


@pytest.mark.parametrize("line", [
    'site Na1 x 0 y 0 z 0 occ Na+1 1 adps ' + ADP_TAIL,
    'site Na1 x 0 y 0 z 0 occ Na+1 1 ' + ADP_TAIL,   # bare u11…, no `adps`
])
def test_a_stated_adp_tensor_is_carried_on_the_model(tmp_path, line):
    """`u11 0.013 …` came back with no tensor and `beq` None, and `to_structure`
    then seeded biso 0.5 — for NaCl at U = 0.013 that is B_eq = 8π²·0.013 =
    1.026 read as 0.5, which the reviewer measured at max |ΔI|/I_max 3.6 % and
    +34.7 % on the strongest 90-140° peak, nothing raised (round-five finding
    1). The tensor is carried now, `adps` keyword or not. Convention: TOPAS's
    u_ij are U^ij in Å² — the CIF `_atom_site_aniso_U_ij` convention `AnisoU`
    holds — so the numbers transfer unchanged."""
    inp = _inp(tmp_path, "adp.inp",
               'str\nphase_name "NaCl"\nspace_group "Fm-3m"\na 5.64\n' + line + "\n")
    site = read_topas_inp(inp).phases[0].sites[0]
    assert site.adps == {"u11": 0.013, "u22": 0.013, "u33": 0.013,
                         "u12": 0.0, "u13": 0.0, "u23": 0.0}
    assert site.beq is None


def test_a_stated_tensor_the_caller_did_not_ask_for_is_refused_not_seeded(tmp_path):
    """The hard constraint: what the build may not do is seed 0.5 in silence.
    `to_structure` without `aniso=True` refuses a tensor-stating site by name,
    the same opt-in shape as `structure_from_cif(aniso=...)`."""
    inp = _inp(tmp_path, "adp.inp",
               'str\nphase_name "NaCl"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 ' + ADP_TAIL + "\n")
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp))
    msg = str(exc.value)
    assert "'Na1'" in msg and "anisotropic" in msg and "aniso=True" in msg


def test_the_opt_in_builds_the_tensor_in_the_cif_u_convention(tmp_path):
    """`aniso=True` builds the `AnisoU` block; biso becomes the schema's inert
    record (vary False), valued at the file's beq where stated, else 8π²·U_eq
    from the trace — the CIF path's own fallback — never the 0.5 seed."""
    import math

    inp = _inp(tmp_path, "adp.inp",
               'str\nphase_name "NaCl"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 ' + ADP_TAIL + "\n")
    atom = to_structure(read_topas_inp(inp), aniso=True).phases[0].atoms[0]
    assert atom.aniso is not None
    assert atom.aniso.u11.value == pytest.approx(0.013)
    assert atom.aniso.u23.value == pytest.approx(0.0)
    assert atom.biso.value == pytest.approx(8 * math.pi ** 2 * 0.013)  # 1.026
    assert atom.biso.vary is False


def test_a_beq_beside_the_tensor_keeps_both_numbers(tmp_path):
    """`beq` beside the tensor used to keep B and silently drop the anisotropy.
    Both are the file's: the tensor builds, and the stated beq is the inert
    isotropic record."""
    inp = _inp(tmp_path, "adpbeq.inp",
               'str\nphase_name "NaCl"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 beq b 0.7 ' + ADP_TAIL + "\n")
    model = read_topas_inp(inp)
    assert model.phases[0].sites[0].beq == pytest.approx(0.7)
    assert model.phases[0].sites[0].adps["u11"] == pytest.approx(0.013)
    atom = to_structure(model, aniso=True).phases[0].atoms[0]
    assert atom.aniso.u11.value == pytest.approx(0.013)
    assert atom.biso.value == pytest.approx(0.7)


def test_a_tensor_free_site_is_untouched_by_the_opt_in(tmp_path):
    """A mixed file yields a mixed structure, exactly as the CIF path: the
    opt-in changes nothing for a site that states no tensor."""
    inp = _inp(tmp_path, "mixadp.inp",
               'str\nphase_name "P"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 ' + ADP_TAIL + "\n"
               'site Cl1 x 0.5 y 0.5 z 0.5 occ Cl-1 1 beq b 1.2\n')
    na, cl = to_structure(read_topas_inp(inp), aniso=True).phases[0].atoms
    assert na.aniso is not None
    assert cl.aniso is None and cl.biso.value == pytest.approx(1.2)


def test_an_adp_components_refine_flag_travels_with_its_value(tmp_path):
    inp = _inp(tmp_path, "adpflag.inp",
               'str\nphase_name "P"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 '
               'u11 @ 0.013 u22 0.013 u33 !u33f 0.013 u12 0 u13 0 u23 0\n')
    atom = to_structure(read_topas_inp(inp), aniso=True).phases[0].atoms[0]
    assert atom.aniso.u11.vary is True
    assert atom.aniso.u33.vary is False


def test_a_stated_tensor_component_the_reader_cannot_resolve_refuses(tmp_path):
    """Finding 4's rule reaches the tensor: a stated u_ij that cannot be read
    refuses naming the component and the line, rather than becoming a 0."""
    inp = _inp(tmp_path, "adpbad.inp",
               'str\nphase_name "P"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 u11 =mystery; u22 0.01 u33 0.01\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "cannot read u11" in str(exc.value)


def test_a_partial_tensor_with_a_missing_diagonal_is_refused(tmp_path):
    """An off-diagonal the file omits is 0 by the format's convention; a
    *diagonal* it omits has no default this reader may invent."""
    inp = _inp(tmp_path, "adppart.inp",
               'str\nphase_name "P"\nspace_group "Fm-3m"\na 5.64\n'
               'site Na1 x 0 y 0 z 0 occ Na+1 1 u11 0.013 u22 0.013\n')
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp), aniso=True)
    assert "partial anisotropic tensor" in str(exc.value)


# The archive's live anisotropic spelling is the six-slot positional
# `ADPs { u11 u22 u33 u12 u13 u23 }` brace block (6 files), not the named
# form. The slot order is archive-evidenced: `archive file 2:187` names its
# slots `A1_u11 … A1_u23` in exactly that order, and `archive file 3:73`
# names slots 1, 2, 3 and 6 `u11A`/`u22A`/`u33A`/`u23A` with the two zeros
# in the u12/u13 positions. Each fixture below is a real file's spelling.

def test_the_positional_adps_brace_block_reads_in_slot_order(tmp_path):
    """`archive file 2`'s spelling: named slots, each with a `min … max=…;`
    window (inert on AnisoU, skipped) and `_LIMIT_*` annotations."""
    inp = _inp(tmp_path, "named_adps.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0.21111 y 0.18888 z 0 occ Na 1.0 ADPs { '
               'A1_u11  0.02000` min 0.0001 max=0.1; '
               'A1_u22  0.00700` min 0.0001 max=0.1; '
               'A1_u33  0.00800` min 0.0001 max=0.1; '
               'A1_u12  0.00300`_LIMIT_MIN_0.0001 min 0.0001 max=0.1; '
               'A1_u13  0.01500` min 0.0001 max=0.1; '
               'A1_u23  0.00100`_LIMIT_MIN_0.0001 min 0.0001 max=0.1; }\n')
    site = read_topas_inp(inp).phases[0].sites[0]
    assert site.adps == pytest.approx({"u11": 0.02000, "u22": 0.00700,
                                       "u33": 0.00800, "u12": 0.00300,
                                       "u13": 0.01500, "u23": 0.00100})
    assert site.vary["u11"] is True          # the write-back backtick


def test_a_positional_slot_carries_its_own_flag_and_evaluated_tail(tmp_path):
    """`archive file 3`'s second spelling: `=u11A;: 0.00600` evaluated
    tails, bare `0 0` for the u12/u13 slots, and a named sixth slot."""
    inp = _inp(tmp_path, "tailed_adps.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A2 x 0.25 y 0.55555 z 0.25 occ Na 1 ADPs { '
               '=u11A;:  0.00600`_0.00040 =u22A;:  0.00000`_0.00035 '
               '=u33A;:  0.00200`_0.00035 0 0 u23A -0.00150`_0.00059 }\n')
    site = read_topas_inp(inp).phases[0].sites[0]
    assert site.adps == pytest.approx({"u11": 0.00600, "u22": 0.0,
                                       "u33": 0.002, "u12": 0.0,
                                       "u13": 0.0, "u23": -0.00150})


def test_an_adps_slot_this_reader_cannot_resolve_refuses(tmp_path):
    """One archive spelling ties `ADPs` slots with `= Get(u33);`, a
    TOPAS function this reader does not have — a stated slot it cannot resolve,
    refused by finding 4's rule rather than substituted."""
    inp = _inp(tmp_path, "tied_adps.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site O1 x 0.5 y 0 z 0 occ O-2 1 ADPs { '
               'o1_u11  0.01800`_0.00053 = Get(u33); o1_u33  0.06000`_0.00046 '
               '= 0; = 0; = 0; }\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "ADPs block" in str(exc.value)


def test_an_adps_block_that_is_not_six_slots_refuses(tmp_path):
    inp = _inp(tmp_path, "five.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site X1 x 0 y 0 z 0 occ O 1 ADPs { 0.01 0.01 0.01 0 0 }\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "ADPs block" in str(exc.value)


def test_a_bare_adps_keyword_with_no_readable_components_refuses(tmp_path):
    """`ADPs` alone tells TOPAS to generate the tensor at run time: the file
    says "anisotropic" and states no numbers this reader could carry."""
    inp = _inp(tmp_path, "bare.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site X1 x 0 y 0 z 0 occ O 1 adps\n')
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    assert "no tensor components" in str(exc.value)


# ------------- round-five finding 4: a stated occ/beq that cannot be read refuses

@pytest.mark.parametrize("line, key", [
    ('site A1 x 0 y 0 z 0 occ Na+1 =mystery; beq b 0.5', "occ"),
    ('site A1 x 0 y 0 z 0 occ Na+1 1 beq =mystery;', "beq"),
])
def test_a_stated_occ_or_beq_the_reader_cannot_resolve_refuses(tmp_path, line, key):
    """`x =mystery;` already refuses, naming the line; `occ =mystery;` returned
    1.0 and `beq =mystery;` returned None → seeded 0.5, both silently (round-five
    finding 4). The established rule — a stated key that could not be read refuses
    naming the key and the line, an absent key keeps its default — now reaches
    occ and beq."""
    inp = _inp(tmp_path, "unresolvable.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n' + line + "\n")
    with pytest.raises(TopasInpError) as exc:
        read_topas_inp(inp)
    msg = str(exc.value)
    assert "unresolvable.inp" in msg
    assert f"cannot read {key}" in msg
    assert line in msg                       # the offending line, named


def test_an_absent_occ_or_beq_still_keeps_its_default_not_a_refusal(tmp_path):
    """The other side of the same rule: a site that *omits* beq keeps the None
    that seeds 0.5, and an occupancy the file omits keeps 1.0 — an absent key is
    the file's own claim, not a value the reader could not read."""
    inp = _inp(tmp_path, "absent.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1\n')     # no beq, no occ value
    site = read_topas_inp(inp).phases[0].sites[0]
    assert site.beq is None and site.occupancy == pytest.approx(1.0)


# ---------------------------- finding 6: an absent writer is not a claim

def test_the_negative_beq_docstring_does_not_claim_a_pcr_reader_exists():
    """WP-1076: a declared name is a claim. The sibling `.pcr` reader lives on a
    *different* open PR (#111, `fullprof-pcr-reader`), not this tree, so
    `to_structure`'s docstring must state the rule a future/sibling reader keeps,
    not claim a file on this tree refuses the value (finding 6). The sentence
    becomes true when #111 merges."""
    doc = to_structure.__doc__
    assert "the sibling `.pcr` reader refuses the same value" not in doc
    assert "WP-1076" in doc


# ---------------------------- the `'/*` idiom (coordinator finding)

def test_strip_comments_apostrophe_delimiters_are_not_block_comments():
    """A `/*` or `*/` preceded on its line by an unquoted `'` is comment text,
    not a delimiter — the `'/*` idiom comments out the block-comment delimiter
    itself, so the text between `'/*` and `'*/` is live. Stripping `/* */` first
    deleted it; the one-pass scan sees the `'` first."""
    out = strip_comments("'/*\nkeepme\n'*/")
    assert "keepme" in out
    # a real /* */ block is still removed, and a real trailing ' still cuts
    assert "gone" not in strip_comments("/* gone */\nkeepme")
    assert strip_comments('"/*not a comment*/"') == '"/*not a comment*/"'


def test_the_apostrophe_block_comment_idiom_keeps_the_phase_active(tmp_path):
    """Built from a minimal reproduction of the archive idiom, where `'/*` and
    `'*/` hold three refinements in one input and enable one of them.
    `strip_comments` removed `/* */` first and deleted the active phase; the fix
    reads it."""
    inp = _inp(tmp_path, "idiom.inp",
               "' a header\n"
               "/* la 1 lo 0.7093 */\n"          # a real block comment: dead
               "'/*\n"
               'str\nphase_name "trigonal phase"\nspace_group "R-3cH"\n'
               'a 5.0`\nb 5.0`\nc 13.0`\nal 90 be 90 ga 120\n'
               'site A1 x 0 y 0 z 0.25 occ Na+1 .5 beq bl 1.0\n'
               "'*/\n")
    model = read_topas_inp(inp)
    assert [p.name for p in model.phases] == ["trigonal phase"]
    assert model.wavelength is None          # the real /* */ block was stripped
    assert model.phases[0].cell["c"] == pytest.approx(13.0)


# ============================================================= round-four review
# The token scan put the whole safety of the scan onto the mask, and the mask was
# line-wise while the scan was token-wise — this round's own asymmetry one level
# down. One masked text is built once and every token scan reads it; the tests
# here pin what survives it, and the three regressions the hole let through.
# Each reproduction is the reviewer's own, measured against round two `2a69f76`.


# ---------------------------- the mask, pinned directly

def test_the_mask_blanks_the_space_group_value_so_a_letter_is_not_a_cell_key():
    """The invariant is the mask now, so it is pinned without a whole file: an
    unquoted Hermann-Mauguin symbol's value is blanked over the same span the
    reader's `space_group` regex reads, so `/c 1` is never a `c` token — while
    the real `a`/`b`/`c` lines and the `site` token survive for the scans that
    need them."""
    chunk = ('phase_name x\nspace_group P 1 21/c 1\n'
             'a 5.0\nb 6.0\nc 7.0\nsite A1 x 0 y 0 z 0 occ Na+1 1\n')
    base = _masked(chunk)
    assert "21/c" not in base                       # the symbol's value is gone
    assert "\na 5.0\n" in "\n" + base + "\n"         # real cell lines survive
    assert "b 6.0" in base and "c 7.0" in base
    assert "site A1" in base                         # the site token survives


def test_the_cell_mask_blanks_a_site_segment_not_a_site_line():
    """A site whose fields continue on the next line has the whole *segment*
    blanked for the cell scan — the `b` naming `beq`'s value is gone — but a real
    `b`/`c` line resuming below the site block is not, because the segment ends
    where the edges resume at a line start."""
    chunk = ('site A1 x 0 y 0 z 0 occ Na+1 1\n     beq b 0.5\n'
             'a 5.0\nb 6.0\nc 7.0\n')
    cell = _cell_search_text(chunk)
    assert "beq" not in cell                          # the continuation is gone
    assert "b 6.0" in cell and "c 7.0" in cell        # the cell resuming survives
    # but the base mask keeps the site token, for the split and the count
    assert "site A1" in _masked(chunk)


def test_the_mask_blanks_the_word_site_in_a_path_or_macro_but_keeps_a_real_one():
    """A `site` inside a quoted path or a macro argument is not a site token, so
    neither the file-level count nor the split may see it; a real one must."""
    base = _masked('xdd "C:\\data\\site\\run1.xy"\nOut_X_Ycalc("site.xy")\n'
                   'site A1 x 0 y 0 z 0 occ Na+1 1\n')
    assert len(re.findall(r"\bsite\b", base)) == 1    # only the real one


# ---------------------------- finding 1: an unquoted Hermann-Mauguin symbol

@pytest.mark.parametrize("sg, key, value", [
    # the full monoclinic spellings TOPAS and GSAS write out carry a lattice
    # letter immediately followed by a number, so `/c 1` read c = 1.0 and `/a 1`
    # read a = 1.0 — every d-spacing wrong, nothing raised.
    ("P 1 21/c 1", "c", 7.0),
    ("P 1 21/a 1", "a", 5.0),
])
def test_an_unquoted_hermann_mauguin_symbol_is_not_read_as_a_cell_key(
        tmp_path, sg, key, value):
    """`space_group P 1 21/c 1` read `/c 1` as c = 1.0: the symbol sits above the
    cell and the loop takes the first line that reads, so it won. The mask blanks
    the value over the span the reader's own regex consumes, so the real `c 7.0`
    line is the first `c` left (finding 1)."""
    inp = _inp(tmp_path, "hm.inp",
               f'str\nphase_name x\nspace_group {sg}\n'
               'a 5.0\nb 6.0\nc 7.0\nbe 99.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert phase.cell[key] == pytest.approx(value)
    assert phase.space_group == sg                # the symbol itself is preserved


def test_a_quoted_hermann_mauguin_symbol_stays_safe(tmp_path):
    """Quoted symbols were already safe, because strings are blanked; keep it."""
    inp = _inp(tmp_path, "hmq.inp",
               'str\nphase_name x\nspace_group "P21/a"\n'
               'a 5.0\nb 6.0\nc 7.0\nbe 99.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    phase = read_topas_inp(inp).phases[0]
    assert (phase.cell["a"], phase.cell["c"]) == pytest.approx((5.0, 7.0))


# ---------------------------- finding 2: a site declaration continues past the line

def test_a_beq_name_on_a_continuation_line_is_not_read_as_a_cell_edge(tmp_path):
    """`beq b 0.5` on its own line left the `b` naming the parameter exposed, and
    a cubic phase — which states no `b` line for the real value to win with —
    read b = 0.5 as a cell edge. Blanked as a site *segment*, `b` stays tied to
    `a` (finding 2)."""
    inp = _inp(tmp_path, "cont_b.inp",
               'str\nphase_name cubic\nspace_group Fm-3m\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1\n     beq b 0.5\n')
    model = read_topas_inp(inp)
    assert "b" not in model.phases[0].cell        # not stated; not leaked
    assert to_structure(model).phases[0].cell.b.value == pytest.approx(4.0)


def test_a_beq_name_ga_on_a_continuation_line_is_not_read_as_an_angle(tmp_path):
    """The same for `beq ga 0.5` on a gallium site: `ga` stayed 90°, not 0.5°."""
    inp = _inp(tmp_path, "cont_ga.inp",
               'str\nphase_name cubic\nspace_group Fm-3m\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Ga+3 1\n     beq ga 0.5\n')
    model = read_topas_inp(inp)
    assert "ga" not in model.phases[0].cell
    assert to_structure(model).phases[0].cell.gamma.value == pytest.approx(90.0)


def test_a_site_block_above_the_cell_lines_does_not_leak_into_the_cell(tmp_path):
    """The site block sits *above* the cell here, so `beq b 0.5` was read as
    b = 0.5 before the real `b 6.0` below it. The segment ends where the edges
    resume at a line start, so `b` is 6.0 — the one place "blank to block end"
    would have blanked the real cell and defaulted it (finding 2)."""
    inp = _inp(tmp_path, "above.inp",
               'str\nphase_name ortho\nspace_group Pmmm\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1\n     beq b 0.5\n'
               'a 5.0\nb 6.0\nc 7.0\n')
    phase = read_topas_inp(inp).phases[0]
    assert (phase.cell["a"], phase.cell["b"], phase.cell["c"]) == \
        pytest.approx((5.0, 6.0, 7.0))
    assert phase.sites[0].beq == pytest.approx(0.5)   # still read as the site's B


# ---------------------------- finding 3: the other scans must use the mask too

def test_a_path_containing_site_above_a_block_does_not_trigger_the_count(tmp_path):
    """`xdd "C:\\data\\site\\run1.xy"` above the block had the file-level guard
    count a `site` token the file never stated and refuse a file that dropped no
    site — the confident wrong diagnosis with its sign flipped. The count reads
    the mask now, so the word in the path is gone (finding 3)."""
    inp = _inp(tmp_path, "pathsite.inp",
               'xdd "C:\\data\\site\\run1.xy"\n'
               'str\nphase_name P\nspace_group P1\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)                    # no refusal
    assert [s.label for s in model.phases[0].sites] == ["A1"]


def test_a_macro_string_containing_site_inside_a_block_is_not_split_as_a_site(
        tmp_path):
    """`Out_X_Ycalc("site.xy")` inside the block had the split cut a bogus segment
    and raise "no label/occ in site: 'site.xy\\")'". The split takes its
    boundaries off the mask, where the macro's string is blanked, so only the
    real site is a site (finding 3)."""
    inp = _inp(tmp_path, "macrostr.inp",
               'str\nphase_name P\nspace_group P1\na 5.0\n'
               'Out_X_Ycalc("site.xy")\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)                    # no refusal
    assert [s.label for s in model.phases[0].sites] == ["A1"]


# ---------------------------- housekeeping: the refusal agrees with itself

@pytest.mark.parametrize("second_blocks, n_carrying, n_building, singular", [
    # one nameless block carrying a cell, one named phase building: both singular.
    ('str\nspace_group "Fm-3m"\na 4.2\nsite B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n',
     1, 1, True),
    # two nameless blocks carrying a cell: the noun and the verb both pluralise.
    ('str\nspace_group "Fm-3m"\na 4.2\nsite B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n'
     'str\nspace_group "Im-3m"\na 3.9\nsite C1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n',
     2, 1, False),
])
def test_the_dropped_block_refusal_agrees_in_number(
        tmp_path, second_blocks, n_carrying, n_building, singular):
    """The refusal pluralised its nouns but not its verbs — "1 `str` block here
    state a cell" and "1 other phase build" — and, once the verbs were fixed,
    still not its pronouns: "1 block … so **they** cannot be built — and
    dropping **them**". All three agree now, singular and plural."""
    inp = _inp(tmp_path, "agree.inp",
               'str\nphase_name "A"\nspace_group "P1"\na 5.0\n'
               'weight_percent wpA 40.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n' + second_blocks)
    with pytest.raises(TopasInpError) as exc:
        to_structure(read_topas_inp(inp))
    msg = str(exc.value)
    if singular:
        assert "block here states a cell" in msg
        assert "so it cannot be built" in msg
        assert "dropping it while" in msg
        assert "other phase builds would" in msg
    else:
        assert "blocks here state a cell" in msg
        assert "so they cannot be built" in msg
        assert "dropping them while" in msg
        assert "other phase builds would" in msg


# ------------- round-six: the grammar's own `site` keyword list (F5)


@pytest.mark.parametrize("tail, occupancy", [
    # the measured case that put `beq` on the list in the first place
    ("occ Sr+2 beq 0.765", 1.0),
    # the twelve the technical reference names and this reader did not:
    # `[mlx E] [mly E] [mlz E] [mg E]`
    ("occ Fe+3 mlx 2.5 mly 0 mlz 0", 1.0),
    # `Tmin_max_r` — `[min_r #] [max_r #]`
    ("occ Na+1 min_r 1.2", 1.0),
    # `[occ $atom E [beq E] [scale_occ E]]` — scale_occ is occ's own child
    ("occ Ca+2 scale_occ 0.5", 1.0),
    # `[adps_scale E]`, and `[inter !E #]`, `[track !E]`, `[layer $layer]`
    ("occ O-2 adps_scale 2.0", 1.0),
    ("occ O-2 inter 3.0", 1.0),
    ("occ O-2 track 1", 1.0),
    # `[g !N] [q E] [s E]` and `[co #]` — one letter each, and each a number
    ("occ Cl-1 q 0.5", 1.0),
    ("occ Cl-1 co 6", 1.0),
    # a stated occupancy still reads, in front of every one of them
    ("occ Sr+2 0.75 mlx 2.5", 0.75),
    ("occ Sr+2 0.75 min_r 1.2", 0.75),
])
def test_a_site_keyword_the_grammar_names_never_becomes_the_occupancy(
        tmp_path, tail, occupancy):
    """A site keyword missing from the terminator set is read as the
    occupancy's value — the failure `beq` already had, generalised.

    The list is the technical reference's `Tstr_details` `site` node, not a set
    collected from the archive: every site in the 606 files states its
    occupancy, so none of these misreads there and the archive could never have
    found them. The format's own 1.0 default is what an `occ` stating no value
    keeps (established in round two); the wrong answer is the neighbour's number
    arriving in its place, silently, on a site the reader then builds.
    """
    inp = _inp(tmp_path, "sitekw.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               f'site A1 x 0 y 0 z 0 {tail}\n')
    (phase,) = read_topas_inp(inp).phases
    (site,) = phase.sites
    assert site.occupancy == pytest.approx(occupancy)


def test_the_ADPs_spelling_still_terminates_an_occupancy(tmp_path):
    """`adps` carries a scoped case-insensitive flag rather than two entries,
    because the archive spells it both ways — six files, `adps` and `ADPs`. A
    case-sensitive list would have re-opened exactly the hole it closed."""
    inp = _inp(tmp_path, "adpscase.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Ca+2 ADPs { 0.01 0.01 0.01 0 0 0 }\n')
    (phase,) = read_topas_inp(inp).phases
    (site,) = phase.sites
    assert site.occupancy == pytest.approx(1.0)
    assert site.adps["u11"] == pytest.approx(0.01)


# ------------- round-six: the emission profile's reference line (F6)


def test_the_reference_wavelength_is_the_largest_la_not_the_first(tmp_path):
    """`Tcomm_2`'s `[la E lo E [lh E] | [lg E] [lo_ref]]...` is an array, and
    the reference says which line `Lam` takes: "the emission profile line with
    the largest `la` value".

    The archive writes a CuKα doublet largest-first, so reading `lo[0]` was
    right there by accident. Written the other way round — legal, and nothing in
    the format forbids it — `lo[0]` is the Kα2 wavelength, a 2.5e-3 Å error that
    moves every d-spacing and raises nothing.
    """
    inp = _inp(tmp_path, "kalpha.inp",
               'lam ymin_on_ymax 0.001\n'
               '  la 0.3395 lo 1.544426 lh 0.5\n'
               '  la 0.6605 lo 1.540598 lh 0.5\n'
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert [ln.wavelength for ln in model.emission_lines] == pytest.approx(
        [1.544426, 1.540598])
    assert model.wavelength == pytest.approx(1.540598)


def test_lo_ref_outranks_the_largest_la(tmp_path):
    """"`lo_ref` marks a specific line's `lo` as the one to use as the reference
    wavelength instead" — so a file that marks one has settled the question and
    the area no longer decides."""
    inp = _inp(tmp_path, "loref.inp",
               'lam\n  la 0.6605 lo 1.540598 lh 0.5\n'
               '  la 0.3395 lo 1.544426 lh 0.5 lo_ref\n'
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert read_topas_inp(inp).wavelength == pytest.approx(1.544426)


@pytest.mark.parametrize("profile", [
    "la !la1 0.6605 lo !lo1 1.540598",     # named and held
    "la @ 0.6605 lo @ 1.540598",           # refined
    "la 0.6605` lo 1.540598`",             # written back after refining
    "la = 1 - 0.3395;: 0.6605 lo = 1.540598;: 1.540598",   # evaluated tails
])
def test_an_emission_line_reads_in_every_spelling_of_the_one_grammar(
        tmp_path, profile):
    """`la` and `lo` are ordinary parameters, so they take every spelling the
    one grammar admits. The predecessor demanded a *bare number* for `la` and so
    saw none of these: **16 of the 606 archive files** state an emission profile
    and came back `wavelength=None`, which a caller cannot tell from a file that
    states no profile at all."""
    inp = _inp(tmp_path, "spell.inp",
               f'lam\n  {profile} lh 0.5\n'
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert read_topas_inp(inp).wavelength == pytest.approx(1.540598)


def test_an_la_inside_a_quoted_path_is_not_an_emission_line(tmp_path):
    """Located on THE masked text, so the `la` in a filename is not a line —
    the same invariant that keeps `site` out of `Out_X_Ycalc("site.xy")`."""
    inp = _inp(tmp_path, "quoted.inp",
               'xdd "C:\\data\\la lo runs\\scan1.xy"\n'
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert model.emission_lines == []
    assert model.wavelength is None


# ---- round-six: the scope model has a dataset level (Technical Reference 5.1)


def test_a_phase_carries_the_dataset_it_belongs_to(tmp_path):
    """`[xdd $file ...]...` whose children are `[str | dummy_str]...`: a phase
    is a fact about one pattern, not about the file."""
    inp = _inp(tmp_path, "two.inp",
               'xdd "a.xye"\n'
               'str\nphase_name "A"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'xdd "b.xye"\n'
               'str\nphase_name "B"\nspace_group "P1"\na 5.0\n'
               'site B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert model.n_datasets == 2
    assert [ph.dataset for ph in model.phases] == [0, 1]


def test_two_datasets_phases_are_not_concatenated_into_one_structure(tmp_path):
    """The measured shape of getting this wrong: the archive's multi-dataset
    files state weight-percent sums of 189, 300, 400 and 600 % — N specimens'
    fractions added together — and every one of them built a `Structure`.

    `io/CLAUDE.md`'s pattern-reader rule one rank up: a multi-range file's
    ranges are scans **selected by** `scan=`, never concatenated. Here the
    selector is `dataset=` and the refusal names it.
    """
    inp = _inp(tmp_path, "twobuild.inp",
               'xdd "a.xye"\n'
               'str\nphase_name "A"\nspace_group "P1"\na 4.0\n'
               'weight_percent wa 100.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'xdd "b.xye"\n'
               'str\nphase_name "B"\nspace_group "P1"\na 5.0\n'
               'weight_percent wb 100.0\n'
               'site B1 x 0 y 0 z 0 occ Cl-1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    with pytest.raises(TopasInpError) as exc:
        to_structure(model)
    assert "2 datasets" in str(exc.value)
    assert "dataset=N" in str(exc.value)
    # the selector builds one of them, and only its phases
    assert [p.name for p in to_structure(model, dataset=0).phases] == ["A"]
    assert [p.name for p in to_structure(model, dataset=1).phases] == ["B"]


def test_a_dataset_that_holds_no_phase_is_named_not_silently_empty(tmp_path):
    inp = _inp(tmp_path, "nodata.inp",
               'xdd "a.xye"\n'
               'str\nphase_name "A"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    with pytest.raises(TopasInpError, match="no phase belongs to dataset 4"):
        to_structure(read_topas_inp(inp), dataset=4)


def test_the_runs_own_r_wp_is_the_one_stated_at_top_level(tmp_path):
    """`Tr_wp` hangs off `Ttop` *and* `Txdd`, so a file states the run's own
    figure of merit and one per dataset. Measured on
    `archive file 5`: 4.408 above the `xdd`, 14.188 inside it. The
    first match is the run's only because of where it sits, not because it is
    first."""
    inp = _inp(tmp_path, "fom.inp",
               'r_wp 4.408 gof 1.18\n'
               'xdd "a.xye"\nr_wp 14.188 gof 3.90\n'
               'str\nphase_name "A"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    model = read_topas_inp(inp)
    assert model.r_wp == pytest.approx(4.408)
    assert model.gof == pytest.approx(1.18)
    assert model.r_wp_all == pytest.approx([4.408, 14.188])
    assert model.gof_all == pytest.approx([1.18, 3.90])


def test_a_per_dataset_r_wp_is_never_quoted_as_the_runs_own(tmp_path):
    """Six banks, six `r_wp`, no top-level one — the WISH files' shape. The
    converged r_wp is the reason this format is worth reading, so one of six
    reported as *the* answer is the confident wrong singleton; it is withheld
    and all six are carried."""
    inp = _inp(tmp_path, "banks.inp",
               'xdd "b1.xye"\nr_wp 9.14\n'
               'str\nphase_name "A"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'xdd "b2.xye"\nr_wp 3.33\n')
    model = read_topas_inp(inp)
    assert model.r_wp is None
    assert model.r_wp_all == pytest.approx([9.14, 3.33])


def test_one_dataset_still_reports_its_r_wp(tmp_path):
    """A file with no top-level statement and exactly one dataset states one
    number, and there is nothing to be ambiguous about."""
    inp = _inp(tmp_path, "one.inp",
               'xdd "a.xye"\nr_wp 7.7\n'
               'str\nphase_name "A"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    assert read_topas_inp(inp).r_wp == pytest.approx(7.7)


# ---- round-six: a name IS the refine flag (Technical Reference 2.1)


@pytest.mark.parametrize("line, expected", [
    # the reference's own three spellings, verbatim from 2.1:
    ("site Zr x 0 y 0 z 0 occ Zr+4 1 beq b1 0.5", True),
    ("site Zr x 0 y 0 z 0 occ Zr+4 1 beq !b1 0.5", False),
    ("site Zr x 0 y 0 z 0 occ Zr+4 1 beq @ 0.5", True),
    ("site Zr x 0 y 0 z 0 occ Zr+4 1 beq @b1 0.5", True),
    # and the fourth, which the reference calls a constant: nothing is claimed
    ("site Zr x 0 y 0 z 0 occ Zr+4 1 beq 0.5", None),
])
def test_a_name_is_itself_the_refine_flag(tmp_path, line, expected):
    """"A parameter is flagged for refinement by giving it a name" — Technical
    Reference 2.1, which then prints exactly these spellings.

    This reader read a name as *no statement*, so `beq b1 0.5` arrived as
    "the file said nothing" and built `vary=False`. **3891 named-but-unflagged
    values across 89 archive files** were reported held when the file said
    free. No sweep could have found it: a wrong `vary` raises nothing, moves no
    parsed number, and only a reader of the specification can see it.

    The bare-value row stays `None` rather than becoming `False`. The reference
    calls it a constant and `rx.Parameter` fixes it either way, but the
    tri-state's caution is worth keeping where the file wrote no flag at all.
    """
    inp = _inp(tmp_path, "flag.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n' + line + "\n")
    (phase,) = read_topas_inp(inp).phases
    (site,) = phase.sites
    assert site.vary.get("beq") is expected


def test_a_named_equation_is_a_constraint_not_a_refined_parameter(tmp_path):
    """Section 2.4 makes an equation a *constraint*: a named one is a dependent
    parameter, not an independent refined one, so the name is not the flag
    there. Its write-back backtick still is."""
    inp = _inp(tmp_path, "eqn.inp",
               'str\nphase_name "P"\nspace_group "P1"\n'
               'a lpa = 5.0;\nb lpb = 6.0;: 6.0`\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n')
    (phase,) = read_topas_inp(inp).phases
    assert phase.vary.get("a") is None      # named equation: no claim
    assert phase.vary.get("b") is True      # written back: it moved


def test_the_named_flag_reaches_the_structure(tmp_path):
    """The point of reading a flag is that a plan inherits it, so the rule has
    to survive the build and not only the model."""
    inp = _inp(tmp_path, "reach.inp",
               'str\nphase_name "P"\nspace_group "P1"\na lpa 5.0\n'
               'scale sc 0.001\n'
               'site A1 x xA 0.25 y 0 z 0 occ Na+1 1 beq !bA 0.5\n')
    (phase,) = to_structure(read_topas_inp(inp)).phases
    assert phase.cell.a.vary is True
    assert phase.scale.vary is True
    assert phase.atoms[0].x.vary is True
    assert phase.atoms[0].biso.vary is False


# ---- round-six: the pre-processor decides what the text is (Tech Ref 1.2, 19)


def test_a_conditional_is_a_token_not_a_line(tmp_path):
    """TOPAS is whitespace-insensitive, so a directive is wherever it is
    written. `#else #ifdef X` on one line occurs in **283 of the 606 archive
    files**: a line-anchored resolver saw the `#else`, missed the `#ifdef`, and
    the nested `#endif` then popped the *enclosing* frame — so the dead branch
    and everything after it came back live, with no count moving."""
    inp = _inp(tmp_path, "tok.inp",
               '#define want_b\n'
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               '#ifndef want_b\n'
               'site DEAD x 0 y 0 z 0 occ Xx 1 beq b 0.5\n'
               '#else #ifdef want_b\n'
               'site LIVE x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               '#endif #endif\n')
    (phase,) = read_topas_inp(inp).phases
    assert [s.label for s in phase.sites] == ["LIVE"]


def test_a_conditional_inside_a_site_line_still_gates_it(tmp_path):
    """`archive file 10` gates a site's `beq` with an
    `#ifdef` written *inside the site line*. A line anchor cannot see it."""
    inp = _inp(tmp_path, "insite.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 #ifdef pdf beq bad 9.0 #endif\n')
    (phase,) = read_topas_inp(inp).phases
    assert phase.sites[0].beq is None      # `pdf` is not defined: the beq is dead


def test_a_define_and_an_ifdef_agree_on_what_a_symbol_is(tmp_path):
    """`#define ABO3-x_fit` bound `ABO3` under `\\w+` while
    `#ifdef ABO3-x_fit` asked for the whole token — two spellings of one name,
    disagreeing in silence (5 archive files). One charset, both sides."""
    inp = _inp(tmp_path, "sym.inp",
               '#define ABO3-x_fit\n'
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               '#ifdef ABO3-x_fit\n'
               'site LIVE x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               '#endif\n')
    (phase,) = read_topas_inp(inp).phases
    assert [s.label for s in phase.sites] == ["LIVE"]


def test_a_block_comment_nests(tmp_path):
    """"a block comment is delimited by `/*` and `*/` and **may be nested**" —
    Technical Reference 1.2. A boolean `in_block` ended the outer comment at the
    inner `*/` and read its tail as live input. No archive file nests one, so
    only the specification could close this."""
    text = "a /* outer /* inner */ still comment */ b"
    assert strip_comments(text).split() == ["a", "b"]


@pytest.mark.parametrize("line, needle", [
    ('#if (Run_Number == 0)\nview_structure\n#endif\n', "tests an equation"),
    ('#ifdef !old_version\nsite X x 0 y 0 z 0 occ Na+1 1\n#endif\n',
     "describes no `!` form"),
    ('#include "other.inc"\n', "pulls text from another file"),
    ('#undef want\n', "un-defines names"),
    ('#delete_macros { LP_Factor }\n', "un-defines names"),
    ('#endif\n', "with no `#ifdef` open"),
    ('#ifdef want\n', "never closed by an `#endif`"),
])
def test_a_directive_this_reader_cannot_evaluate_refuses_by_name(
        tmp_path, line, needle):
    """The reference lists the whole pre-processor in section 19; this reader
    evaluates one family of it. Where it does not, the text it is holding is
    not the text TOPAS parsed, and that is refused as a class rather than
    patched per spelling — which is what five rounds of doing the opposite
    earned."""
    inp = _inp(tmp_path, "pp.inp",
               'str\nphase_name "P"\nspace_group "P1"\na 5.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n' + line)
    with pytest.raises(TopasInpError, match=re.escape(needle)):
        read_topas_inp(inp)


# ---- round-six: a card attaches where it is written (Tech Ref 2.20-2.23, 5.1)


def test_a_for_loop_over_content_this_reader_reads_is_refused(tmp_path):
    """"`for $object_type { ... }` is a pre-processor loop that expands its body
    once for every existing instance of the given object type."

    The block model — `_BLOCK` slicing between openers — *is* the assumption
    that a card belongs to the block it sits inside, and the reference licenses
    it only in the absence of these verbs. The ``archive file 27`` series and
    `archive file 1` declare a whole phase inside
    `for xdds { for strs 1 to 1 { ... } }`: `for strs` is not a line-initial
    `str`, so the phase is invisible to the split, and where a real `str`
    exists elsewhere its cell and sites are swept into *that* one instead.
    """
    inp = _inp(tmp_path, "for.inp",
               'xdd "a.xye"\n'
               'for strs 1 to 1 {\n'
               '  phase_name "A"\n  space_group "P1"\n  a 4.0\n'
               '  site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               '}\n')
    with pytest.raises(TopasInpError, match="pre-processor loop"):
        read_topas_inp(inp)


def test_a_for_loop_over_nothing_this_reader_reads_is_left_alone(tmp_path):
    """Ten archive files loop over output records only. A loop that moves
    nothing this reader would have got wrong is not a reason to refuse a file —
    the refusal is about *attachment*, not about the keyword."""
    inp = _inp(tmp_path, "forout.inp",
               'str\nphase_name "A"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'for strs { r_bragg 0 }\n')
    (phase,) = read_topas_inp(inp).phases
    assert phase.cell["a"] == pytest.approx(4.0)


def test_load_of_a_keyword_this_reader_reads_is_refused(tmp_path):
    """`load { }` "allows keywords of the same type to be entered once instead
    of repeated", so the brace body is a list of that keyword's values. This
    reader reads a keyword where it is written and would take one and drop the
    rest. The five spellings the archive actually uses — `load out_record`,
    `hkl_m_d_th2`, `sh_Cij_prm`, `xo`, `index_th2` — load none it reads, which
    is why 276 files carry a `load` and none of them refuses."""
    inp = _inp(tmp_path, "load.inp",
               'str\nphase_name "A"\nspace_group "P1"\na 4.0\n'
               'load site { A1 0 0 0  A2 0.5 0.5 0.5 }\n')
    with pytest.raises(TopasInpError, match=re.escape("`load site`")):
        read_topas_inp(inp)


def test_a_load_this_reader_does_not_read_is_left_alone(tmp_path):
    inp = _inp(tmp_path, "loadok.inp",
               'str\nphase_name "A"\nspace_group "P1"\na 4.0\n'
               'site A1 x 0 y 0 z 0 occ Na+1 1 beq b 0.5\n'
               'load out_record { out_eqn = Get(r_wp); out_fmt "%11.5f" }\n')
    assert read_topas_inp(inp).phases[0].cell["a"] == pytest.approx(4.0)


# ---------------------------------------------- the coverage registry (WP-1118)

#: A phase with nothing in it but what this reader builds. Every coverage test
#: below adds one construct to this, so what fires is attributable to the line
#: that was added rather than to the fixture.
_PLAIN = ('str\nphase_name "P"\nspace_group "P 1"\n'
          'a 5.0 b 6.0 c 7.0 al 90 be 90 ga 90\nscale @ 0.001\n'
          'site A1 x 0 y 0 z 0 occ Ca+2 1 beq 0.5\n')


def test_every_phase_scope_keyword_has_exactly_one_stance():
    """The completeness oracle, and the reason the registry is a mechanism
    rather than a list.

    A construct with no stance is one that is dropped in silence, which is the
    single shape all nine review rounds of this reader found. Partitioned both
    ways: a keyword in the scope without a stance fails, and a stance naming a
    keyword outside the scope fails — so support for a new construct is a row
    that moves, and the test says whether anything was left behind.
    """
    seen: dict[str, str] = {}
    for feat in coverage.FEATURES:
        assert feat.keywords, f"{feat.name} declares no keyword"
        assert feat.stance in coverage.Stance
        for kw in feat.keywords:
            assert kw not in seen, (
                f"{kw!r} is claimed by both {seen[kw]!r} and {feat.name!r}; a "
                f"keyword has one stance or the stance is not a fact about it")
            seen[kw] = feat.name
    assert set(seen) == set(coverage.PHASE_SCOPE)
    # A refusal has to say what building without it would misrepresent, and a
    # report what the caller loses. An unargued refusal is a rule nobody can
    # check against a file.
    for feat in coverage.FEATURES:
        if feat.stance in (coverage.Stance.REFUSED, coverage.Stance.REPORTED):
            assert feat.why, f"{feat.name} takes a stance without an argument"


def test_scanned_is_exactly_the_stances_that_produce_an_outcome():
    """`READ` and `IGNORED` cost a scan and answer nothing, and several of them
    are one character long. The registry still carries them because the oracle
    above is the whole scope."""
    assert coverage.SCANNED == {
        kw for feat in coverage.FEATURES
        if feat.stance in (coverage.Stance.REPORTED, coverage.Stance.REFUSED)
        for kw in feat.keywords}
    assert not coverage.SCANNED.intersection({"a", "b", "c", "x", "y", "z"})


def test_a_file_this_reader_fully_understands_reports_nothing(tmp_path):
    """The silence has an argument behind it, which is what the registry is for:
    every construct in this file is `READ`."""
    diags = []
    model = read_topas_inp(_inp(tmp_path, "plain.inp", _PLAIN), diagnostics=diags)
    assert model.coverage.partial is False
    assert model.coverage.reported == () and model.coverage.refused == ()
    assert [d.code for d in diags] == ["TOPAS_SPECIES_NORMALISED"]


def test_a_construct_the_import_drops_is_named_as_a_partial_import(tmp_path):
    """`REPORTED`: the structure built is right as far as it goes, and one
    diagnostic says how far. It still builds — a dropped peak shape does not
    make the atoms wrong."""
    inp = _inp(tmp_path, "profile.inp",
               _PLAIN + "lor_fwhm = 0.1;\npush_peak 0.01\n")
    diags = []
    model = read_topas_inp(inp, diagnostics=diags)
    assert model.coverage.partial is True
    (hit,) = model.coverage.reported
    assert hit.feature.name == "peak profile"
    assert hit.keywords == ("lor_fwhm", "push_peak")
    assert hit.phases == ("P",)
    (report,) = [d for d in diags if d.code == "TOPAS_FEATURES_NOT_IMPORTED"]
    assert "peak profile" in report.message and "lor_fwhm" in report.message
    # The keywords named are the ones the file wrote, not the feature's whole
    # list: a message naming every convolution TOPAS has is one nobody reads.
    assert "axial_conv" not in report.message
    assert to_structure(model).phases[0].cell.a.value == pytest.approx(5.0)


@pytest.mark.parametrize("line, feature_name", [
    ("rigid\n   point_for_site A1 ux 0 uy 0 uz 0\n   rotate @ 0 qx 1\n",
     "rigid body"),
    ('occ_merge "A1" occ_merge_radius 0.5\n', "merged occupancies"),
    ("generate_stack_sequences { number_of_sequences 20 }\n", "stacking faults"),
])
def test_a_construct_whose_absence_would_misrepresent_the_file_refuses(
        tmp_path, line, feature_name):
    """`REFUSED`, and refused at *build* rather than at read.

    The split is the skipped-block one: the model is an honest account of the
    text either way, so reading it is how a caller finds out what the file
    states; `to_structure` is where a claim about a refinement is made, and that
    is where a claim this reader cannot support has to stop.
    """
    inp = _inp(tmp_path, "refused.inp", _PLAIN + line)
    diags = []
    model = read_topas_inp(inp, diagnostics=diags)          # reads
    (hit,) = model.coverage.refused
    assert hit.feature.name == feature_name
    assert model.phases[0].cell["a"] == pytest.approx(5.0)  # and states the cell
    assert [d.code for d in diags].count("TOPAS_FEATURE_REFUSED") == 1
    with pytest.raises(TopasInpError, match=re.escape(feature_name)) as exc:
        to_structure(model)
    # The refusal carries its argument, not just its verdict.
    assert hit.feature.why[:40] in str(exc.value)


def test_a_refused_construct_in_another_dataset_does_not_block_this_one(
        tmp_path):
    """Filtered to the phases actually being built, so `dataset=` selecting the
    specimen without the rigid body builds — the same discrimination
    `to_structure` already makes about which phases are one specimen's."""
    two = ('xdd "a.xy"\n' + _PLAIN
           + 'xdd "b.xy"\nstr\nphase_name "Q"\nspace_group "P 1"\n'
             "a 8.0 b 8.0 c 8.0 al 90 be 90 ga 90\n"
             "site B1 x 0 y 0 z 0 occ Na+1 1 beq 0.5\n"
             "rigid\n   point_for_site B1 ux 0 uy 0 uz 0\n")
    model = read_topas_inp(_inp(tmp_path, "two.inp", two))
    (hit,) = model.coverage.refused
    assert hit.phases == ("Q",)
    assert to_structure(model, dataset=0).phases[0].name == "P"
    with pytest.raises(TopasInpError, match="rigid body"):
        to_structure(model, dataset=1)


def test_the_coverage_scan_reads_the_mask_and_not_the_text(tmp_path):
    """A `rotate` inside a quoted path is a path, and `prm hat 0.1` names a
    parameter. The scan is the reader's for exactly this reason — the mask is
    what makes a token scan safe, and the registry does not own it."""
    inp = _inp(tmp_path, "masked.inp",
               _PLAIN + 'out "C:\\data\\rotate\\run1.txt"\nprm hat 0.1\n')
    model = read_topas_inp(inp)
    assert model.coverage.partial is False


def test_coverage_is_on_the_model_without_a_diagnostics_list(tmp_path):
    """A fact about the answer does not depend on the caller having asked for
    messages — `skipped_blocks`' rule, and for the same reason."""
    inp = _inp(tmp_path, "nochannel.inp", _PLAIN + "lor_fwhm = 0.1;\n")
    assert read_topas_inp(inp).coverage.partial is True


# ------------------------------------- a cell edge coupled through a parameter


def _cell_of(tmp_path, name, head, cell, sg="P 1"):
    inp = _inp(tmp_path, name,
               f'{head}\nstr\nphase_name "P"\nspace_group "{sg}"\n{cell}\n'
               "site A1 x 0 y 0 z 0 occ Ca+2 1 beq 0.5\n")
    diags = []
    return read_topas_inp(inp, diagnostics=diags).phases[0], diags


def test_a_cell_edge_resolved_through_a_parameter_inherits_its_refine_flag(
        tmp_path):
    """The file refines `edge`, so it refines the edge that names it.

    Reading only the number made `prm edge @ 5.0` and `prm !edge 5.0` produce
    byte-identical models with every edge held — a Structure saying "this cell
    was not refined" about a fit that refined it. Technical Reference 2.2 is
    what settles the bare form: `prm b1 0.2` declares a parameter that will be
    refined, and `prm !b1 0.2` is the held one.
    """
    for head, expected in (("prm edge @ 5.0", True),
                           ("prm edge 5.0", True),
                           ("prm !edge 5.0", None)):
        phase, _ = _cell_of(tmp_path, "inherit.inp", head,
                            "a = edge;\n   b 6.0\n   c @ 7.0")
        assert phase.cell["a"] == pytest.approx(5.0)
        assert phase.vary.get("a") is expected, head


def test_two_edges_naming_one_parameter_report_the_dropped_coupling(tmp_path):
    """The format's *other* coupled-edge idiom. `Get(a)` was reported and this
    was not, though the loss is identical: the value is copied, the tie is not,
    and the two edges are independent in the built model."""
    phase, diags = _cell_of(tmp_path, "shared.inp", "prm edge @ 5.0",
                            "a = edge;\n   b = edge;\n   c @ 7.0")
    assert phase.cell["a"] == phase.cell["b"] == pytest.approx(5.0)
    assert phase.vary["a"] is True and phase.vary["b"] is True
    (drop,) = [d for d in diags if d.code == "TOPAS_CELL_COUPLING_DROPPED"]
    assert "`edge`" in drop.message and drop.where == ["phases.P.cell.b"]


def test_the_shared_parameter_coupling_stays_silent_where_symmetry_ties_it(
        tmp_path):
    """The same discrimination the `Get` arm already makes, reached by the
    second route: under `P 4/m m m` rietx ties b to a itself, so the built model
    states what the file stated and there is nothing to report. The inherited
    refine flag is absorbed by the tie rather than making a second free
    column."""
    phase, diags = _cell_of(tmp_path, "tied.inp", "prm edge @ 5.0",
                            "a = edge;\n   b = edge;\n   c @ 7.0",
                            sg="P 4/m m m")
    assert not [d for d in diags if d.code == "TOPAS_CELL_COUPLING_DROPPED"]
    assert phase.vary["a"] is True and phase.vary["b"] is True


def test_one_edge_from_a_parameter_is_not_a_coupling(tmp_path):
    """A coupling is two keys reaching one parameter. One key reaching one
    parameter is an ordinary equation, and reporting it would be the noise that
    makes a real report unreadable."""
    _, diags = _cell_of(tmp_path, "single.inp", "prm edge @ 5.0",
                        "a = edge;\n   b 6.0\n   c @ 7.0")
    assert not [d for d in diags if d.code == "TOPAS_CELL_COUPLING_DROPPED"]


def test_the_get_arm_is_unchanged(tmp_path):
    """`b = Get(a);` still copies `a`'s value, still leaves `b` without a flag
    of its own, and still reports. The two idioms differ in what carries the
    refinement — under `Get` it lives on `a`, which is a cell key and stays
    free; under a shared parameter it lives on a name the phase has no room
    for, which is why only that one inherits."""
    phase, diags = _cell_of(tmp_path, "get.inp", "",
                            "a @ 5.0\n   b = Get(a);\n   c @ 7.0")
    assert phase.cell["b"] == pytest.approx(5.0)
    assert phase.vary.get("b") is None
    (drop,) = [d for d in diags if d.code == "TOPAS_CELL_COUPLING_DROPPED"]
    assert "`Get(a)`" in drop.message


# ------------------------- the origin the file did not state (issue #101)

_SPINEL_INP = """
xdd "spinel.xy"
   str
      phase_name "spinel"
      space_group "{symbol}"
      a  8.0806  b  8.0806  c  8.0806  al 90 be 90 ga 90
      site Mg x 0.125  y 0.125  z 0.125  occ Mg 1 beq 0.5
      site Al x 0.5    y 0.5    z 0.5    occ Al 1 beq 0.5
      site O  x 0.2624 y 0.2624 z 0.2624 occ O  1 beq 0.5
      scale 0.0001
"""


def test_a_bare_two_setting_symbol_is_reported_at_read(tmp_path):
    """TOPAS's trailing ``Z`` says which origin; a bare symbol says nothing.

    `.inp` carries no operator list, so nothing in the file can settle it and
    the reader reports the assumption rather than making it silently — the
    composition being the discriminator (issue #101, issue #217).
    """
    path = _inp(tmp_path, "bare.inp", _SPINEL_INP.format(symbol="Fd-3m"))
    diagnostics: list = []
    model = read_topas_inp(path, diagnostics=diagnostics)
    assert model.phases[0].space_group == "Fd-3m"
    found = [d for d in diagnostics
             if d.code == "SPACE_GROUP_SETTING_ASSUMED"]
    assert len(found) == 1
    # by phase name, which is how this reader addresses a phase in every
    # other row it writes, `TOPAS_ORIGIN_TRANSLATED` included
    assert found[0].where == ["phases.spinel.space_group"]
    assert "F d -3 m:1 → Al8 Mg16 O32" in found[0].message
    assert "F d -3 m:2 → Al16 Mg8 O32" in found[0].message


def test_the_suffix_that_states_the_origin_is_translated_not_assumed(tmp_path):
    """``Fd-3mZ`` is TOPAS saying ``:2``, so the file settled it and the
    assumption report must not also fire."""
    path = _inp(tmp_path, "suffixed.inp", _SPINEL_INP.format(symbol="Fd-3mZ"))
    diagnostics: list = []
    model = read_topas_inp(path, diagnostics=diagnostics)
    assert model.phases[0].space_group == "Fd-3m:2"
    codes = [d.code for d in diagnostics]
    assert "TOPAS_ORIGIN_TRANSLATED" in codes
    assert "SPACE_GROUP_SETTING_ASSUMED" not in codes


def test_a_symbol_the_tables_hold_once_says_nothing(tmp_path):
    path = _inp(tmp_path, "single.inp", _SPINEL_INP.format(symbol="Pnma"))
    diagnostics: list = []
    read_topas_inp(path, diagnostics=diagnostics)
    assert [d for d in diagnostics if "SETTING" in d.code] == []


# --------------------------------------------------- the writer (WP-1118, #148)
#
# `from_structure` is the inverse of `to_structure`, so its test is a round
# trip through the *reader* this module already carries — the cheapest
# adversarial test a writer can get, and the WP's own acceptance for it. Every
# `Structure` below is built by hand rather than loaded from a fixture, since
# nothing here needs a `.inp` at all until the writer produces one.


def _cubic_al(*, a_vary=True, biso_vary=True):
    cell = rx.Cell.cubic(4.0495, vary=a_vary)
    atom = rx.Atom(
        label="Al1", species="Al",
        x=rx.Parameter(value=0.0, vary=False), y=rx.Parameter(value=0.0, vary=False),
        z=rx.Parameter(value=0.0, vary=False), occ=rx.Parameter(value=1.0, vary=False),
        biso=rx.Parameter(value=0.55, vary=biso_vary, min=0.0, max=25.0, unit="A^2"))
    phase = rx.Phase(name="Al", space_group="Fm-3m", cell=cell, atoms=[atom],
                     scale=rx.Parameter(value=0.0123, vary=True, min=0.0))
    return rx.Structure(phases=[phase])


def _assert_parameter_equal(a: rx.Parameter, b: rx.Parameter):
    assert a.value == b.value and a.vary == b.vary


def test_write_topas_inp_round_trips_cell_atoms_and_refine_flags(tmp_path):
    """A structure exported and re-imported is the same structure — values
    exactly (``repr`` is the shortest decimal that reads back to the same
    double) and every ``vary`` flag (the payload, per this reader's own
    headline claim)."""
    cell = rx.Cell(a=rx.Parameter(value=8.123, vary=True),
                   b=rx.Parameter(value=5.234, vary=False),
                   c=rx.Parameter(value=9.345, vary=True),
                   alpha=rx.Parameter(value=90.0, vary=False),
                   beta=rx.Parameter(value=105.41, vary=True),
                   gamma=rx.Parameter(value=90.0, vary=False))
    fe = rx.Atom(label="Fe1", species="Fe3+",
                 x=rx.Parameter(value=-0.123, vary=True),
                 y=rx.Parameter(value=0.25, vary=False),
                 z=rx.Parameter(value=0.04512345678, vary=True),
                 occ=rx.Parameter(value=0.75, vary=True),
                 biso=rx.Parameter(value=0.9123456789, vary=True,
                                   min=0.0, max=25.0, unit="A^2"))
    phase = rx.Phase(name="Fe phase", space_group="P21/c", cell=cell,
                     atoms=[fe], scale=rx.Parameter(value=1.5e-5, vary=True, min=0.0))
    structure = rx.Structure(phases=[phase, _cubic_al().phases[0]])

    out = tmp_path / "round_trip.inp"
    rx.write_topas_inp(structure, out)
    back = to_structure(read_topas_inp(out))

    assert len(back.phases) == 2
    for orig, built in zip(structure.phases, back.phases):
        assert built.name == orig.name
        assert (get_spacegroup(built.space_group).xhm()
               == get_spacegroup(orig.space_group).xhm())
        for key in ("a", "b", "c", "alpha", "beta", "gamma"):
            _assert_parameter_equal(getattr(orig.cell, key), getattr(built.cell, key))
        _assert_parameter_equal(orig.scale, built.scale)
        assert len(built.atoms) == len(orig.atoms)
        for oa, ba in zip(orig.atoms, built.atoms):
            assert ba.label == oa.label
            assert ba.species == oa.species
            for key in ("x", "y", "z", "occ", "biso"):
                _assert_parameter_equal(getattr(oa, key), getattr(ba, key))


def test_write_topas_inp_round_trips_anisotropic_adps(tmp_path):
    """A stated tensor comes back the same tensor, each component's own
    ``vary`` intact, and ``biso`` — the schema's inert record for an
    anisotropic site — held regardless of what the source structure gave it,
    matching what :func:`to_structure` itself always builds."""
    cell = rx.Cell.cubic(5.62)
    na = rx.Atom(
        label="Na1", species="Na1+",
        x=rx.Parameter(value=0.0, vary=False), y=rx.Parameter(value=0.0, vary=False),
        z=rx.Parameter(value=0.0, vary=False), occ=rx.Parameter(value=1.0, vary=False),
        biso=rx.Parameter(value=1.026, vary=False, min=0.0, max=25.0, unit="A^2"),
        aniso=rx.AnisoU(
            u11=rx.Parameter(value=0.013, vary=True, unit="A^2"),
            u22=rx.Parameter(value=0.013, vary=False, unit="A^2"),
            u33=rx.Parameter(value=0.013, vary=False, unit="A^2"),
            u12=rx.Parameter(value=0.0007, vary=True, unit="A^2"),
            u13=rx.Parameter(value=0.0, vary=False, unit="A^2"),
            u23=rx.Parameter(value=0.0, vary=False, unit="A^2")))
    phase = rx.Phase(name="NaCl", space_group="Fm-3m", cell=cell, atoms=[na],
                     scale=rx.Parameter(value=1e-3, vary=True, min=0.0))
    structure = rx.Structure(phases=[phase])

    out = tmp_path / "aniso.inp"
    write_topas_inp(structure, out)
    back = to_structure(read_topas_inp(out), aniso=True)

    ba = back.phases[0].atoms[0]
    assert ba.aniso is not None
    for key in ("u11", "u22", "u33", "u12", "u13", "u23"):
        _assert_parameter_equal(getattr(na.aniso, key), getattr(ba.aniso, key))
    assert ba.biso.value == na.biso.value
    assert ba.biso.vary is False


def test_write_topas_inp_writes_the_resolved_setting_not_the_bare_symbol(tmp_path):
    """`Fd-3m` is one of the 40 symbols the tables hold in two settings
    (issue #101); the writer must emit ``get_spacegroup(...).xhm()`` rather
    than the phase's own stored spelling, so a setting this build already
    resolved is not laundered back into an ambiguous symbol on export — the
    obligation this WP's own file banks against the writers task."""
    resolved = get_spacegroup("Fd-3m").xhm()
    assert ":" in resolved     # this symbol *is* one of the ambiguous ones
    cell = rx.Cell.cubic(8.0806)
    atom = rx.Atom(label="Mg1", species="Mg",
                   x=rx.Parameter(value=0.125), y=rx.Parameter(value=0.125),
                   z=rx.Parameter(value=0.125))
    phase = rx.Phase(name="spinel", space_group=resolved, cell=cell, atoms=[atom])
    structure = rx.Structure(phases=[phase])

    out = tmp_path / "spinel.inp"
    write_topas_inp(structure, out)
    text = out.read_text(encoding="utf-8")
    assert resolved in text

    diagnostics: list = []
    model = read_topas_inp(out, diagnostics=diagnostics)
    # already-resolved on the way out, so the way back in states nothing to
    # assume: `normalize_space_group` passes a colon-suffixed symbol through
    # unrecognised, and the assumption diagnostic never fires on a phase that
    # was never ambiguous to begin with.
    assert model.phases[0].space_group == resolved
    assert [d for d in diagnostics if "SETTING" in d.code] == []


def test_write_topas_inp_refuses_a_phase_name_with_a_double_quote(tmp_path):
    """A quote in the name would close ``phase_name "..."`` early and hand the
    rest of the line to the reader as garbage — refused naming the phase,
    never written and left for the reader to mis-parse."""
    structure = _cubic_al()
    structure.phases[0].name = 'Weird"Name'
    with pytest.raises(ValueError, match="double quote"):
        from_structure(structure)


def test_write_topas_inp_refuses_a_label_or_species_with_whitespace(tmp_path):
    """A `site` line is space-separated, so an embedded space in the label or
    species would be read back as an extra, silently dropped token."""
    structure = _cubic_al()
    structure.phases[0].atoms[0].label = "Al 1"
    with pytest.raises(ValueError, match="whitespace"):
        from_structure(structure)


def test_write_topas_inp_refuses_a_negative_biso(tmp_path):
    """`to_structure` itself refuses a negative beq on the way in, so writing
    one would only fail later, at the read, with the file already on disk."""
    atom = rx.Atom(label="Al1", species="Al", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                   biso=rx.Parameter(value=-0.1, min=-1.0, max=25.0))
    structure = rx.Structure(phases=[rx.Phase(
        name="Al", space_group="Fm-3m", cell=rx.Cell.cubic(4.0495), atoms=[atom])])
    with pytest.raises(ValueError, match="negative"):
        from_structure(structure)


def test_write_topas_inp_refuses_a_single_quote_in_a_label(tmp_path):
    """Unlike `phase_name`, a `site` line's label and species are not
    quoted, so an unquoted `'` would open a TOPAS line comment and silently
    drop x/y/z/occ/beq for that site rather than surviving as a character."""
    structure = _cubic_al()
    structure.phases[0].atoms[0].label = "O'Brien"
    with pytest.raises(ValueError, match="single quote"):
        from_structure(structure)


def test_write_topas_inp_is_reachable_at_the_top_level():
    assert rx.write_topas_inp is write_topas_inp


def test_write_topas_inp_refuses_a_non_finite_value():
    """`Parameter` does not forbid `inf` and a converged fit cannot reach one,
    but `repr` spells it `inf` and TOPAS does not parse that — so the file
    would be written and fail in someone else's program. Surfaced by the review
    pass on this writer's own branch and left as a design question; the answer
    is the same for all three foreign-format writers (WP-1118)."""
    structure = _cubic_al()
    structure.phases[0].cell.a.max = float("inf")
    structure.phases[0].cell.a.value = float("inf")
    with pytest.raises(ValueError, match="does not parse"):
        from_structure(structure)


def test_an_anisotropic_sites_beq_is_refused_non_finite_too():
    """The one number this writer spells without a tail.

    An anisotropic site's ``beq`` is forced held whatever its ``vary`` says, so
    it goes out as a bare ``repr`` rather than through :func:`_tail` — which is
    why the refusal lives one rank down, in ``_number``.  Carried by ``_tail``
    alone, this is exactly the value that would have escaped it: ``biso``'s own
    ``< 0`` guard passes ``inf``, and ``beq ! inf`` is a file TOPAS cannot
    read.
    """
    cell = rx.Cell.cubic(5.62)
    atom = rx.Atom(
        label="Na1", species="Na1+",
        x=rx.Parameter(value=0.0), y=rx.Parameter(value=0.0),
        z=rx.Parameter(value=0.0), occ=rx.Parameter(value=1.0),
        biso=rx.Parameter(value=1.026, min=0.0, max=25.0, unit="A^2"),
        aniso=rx.AnisoU(
            u11=rx.Parameter(value=0.013, unit="A^2"),
            u22=rx.Parameter(value=0.013, unit="A^2"),
            u33=rx.Parameter(value=0.013, unit="A^2"),
            u12=rx.Parameter(value=0.0, unit="A^2"),
            u13=rx.Parameter(value=0.0, unit="A^2"),
            u23=rx.Parameter(value=0.0, unit="A^2")))
    structure = rx.Structure(phases=[rx.Phase(
        name="NaCl", space_group="Fm-3m", cell=cell, atoms=[atom])])
    atom.biso.max = float("inf")
    atom.biso.value = float("inf")
    with pytest.raises(ValueError, match="does not parse"):
        from_structure(structure)


def test_write_topas_inp_refuses_a_line_break_in_a_phase_name():
    """An `.inp` is read line by line, so a break makes the name come back cut
    at it — a silent rename rather than a failure — and hands the remainder to
    the reader as a keyword line of its own. `write_record` refuses the same
    accident one format over."""
    structure = _cubic_al()
    structure.phases[0].name = "apa\ntite"
    with pytest.raises(ValueError, match="line break"):
        from_structure(structure)
