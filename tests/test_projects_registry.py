"""The model-format registry: dispatch, the arm, and the claims it declares.

Three classes of test, and the third is the one worth arguing for.

**Dispatch** — a file reaches the format that can read it, and one nothing here
reads is refused by a message naming what this build *does* open.  No ``.inp`` or
``.pcr`` may be vendored (``ATTRIBUTION.md``'s fence), so every fixture is
synthesized — the ``.inp`` ones below, shaped after the lines
``projects/topas.py``'s comments quote from named archive files, and the ``.pcr``
ones through ``test_projects_fullprof``'s own builders rather than a second
writer of this format's layout.

**The arm** — ``capabilities().project_formats`` is the registry, member for
member and in order.  The same rule ``reader_formats`` is held to: a member
missing from its arm fails.

**The declarations** — ``ProjectFormat`` states three things about a format that
nothing else checks, and each is a claim a reader could drift away from in
silence.  ``reports_at`` says which call takes the diagnostics list; ``read``
and ``to_structure`` say which functions are the format's; ``matches`` says the
file is claimed on content.  A declaration checked against the real signature
turns "the table says so" into "the table and the code agree", which is
``_SURFACE_FLAGS``' lesson (WP-1037) one registry over: a derived claim rots
silently unless the *name* it asks about is data.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import rietx as rx
from rietx.io.projects import registry
from rietx.io.projects.registry import (
    PROJECT_FORMATS,
    ProjectFormat,
    identify_project_format,
    read_project_model,
)
from rietx.schemas import Diagnostic

# The `.pcr` builders are `test_projects_fullprof`'s, imported rather than
# rewritten: a second fixture writer for one format is a second description of
# its layout, and the two would drift on exactly the control-line field count
# that format refuses a file over.
from tests.test_projects_fullprof import _pcr, _phase

# --------------------------------------------------------------------------
# Fixtures, synthesized.  A `.pcr` opens with COMM and then the Job/Npr/Nph
# control line; a `.inp` has no required opening at all, which is the whole
# reason its sniff is a keyword scan and the `.pcr`'s is a first-line test.

#: A `.pcr` header and nothing else.  Deliberately **not** a readable file: the
#: sniff's whole claim is that it decides on the first line, so a fixture that
#: would also parse could not tell a first-line test from a parse attempt.  The
#: full-read tests below use `test_projects_fullprof`'s builders instead.
PCR_HEADER_ONLY = """COMM  synthetic single-phase test
!Job Npr Nph Nba Nex Nsc Nor Dum Iwg Ilo Ias Res Ste Nre Cry Uni Cor Opt
   0   7   1   6   0   0   0   0   0   0   0   0   0   0   0   0   0   0
"""

INP_MINIMAL = """'A synthetic .inp, shaped after the archive files projects/topas.py quotes.
r_wp 9.73
xdd "sample.xy"
 str
  phase_name "corundum"
  space_group R-3c
  a  @ 4.7602
  c  @ 12.9933
  site Al1 x 0 y 0 z 0.3522 occ Al+3 1. beq !b 0.4
"""

INP_NO_PHASE = """iters 1000
prm !zero 0.0
"""

INP_STR_MACRO = """xdd "sample.xy"
 STR(R-3c)
  phase_name "corundum"
"""

#: A file whose only TOPAS keywords sit inside comments.  It is the sniff's
#: sharpest case: every keyword below is present as text, and none of them is
#: stated, so a scan that looked for substrings rather than line-start tokens
#: would claim an Abaqus deck that mentioned `str` in a heading.
INP_ALL_COMMENTED = """'xdd "C:\\data\\str\\run.xy"
/* str
   phase_name "not a phase"
*/
nothing is stated here
"""

ABAQUS_INP = """*HEADING
 A finite-element deck, which also uses .inp
*NODE
1, 0., 0., 0.
*ELEMENT, TYPE=C3D8
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    # Named for `test_portability`'s reason and not only to satisfy it: the
    # sniff decodes through `base.decode`, so a fixture written in the
    # platform's encoding would be testing the platform rather than the sniff.
    p.write_text(text, encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# Dispatch


#: A GSAS .EXP is 80-character cards; the width is half the evidence, so the
#: fixture is built through a helper rather than written as free text.
def _cards(*rows: str) -> str:
    return "".join(f"{row:<80}" for row in rows)


EXP_MINIMAL = _cards(
    "     VERSION    6     Sat Jan 01 16:30:48 2011",
    "      DESCR   a refinement",
    " EXPR  NHST     1",
)

#: The same keys at the same columns, but the cards are not 80 characters. A
#: reader that tested the vocabulary alone would claim this.
EXP_WRONG_WIDTH = (
    "     VERSION    6\n"
    "      DESCR   a refinement\n"
)


@pytest.mark.parametrize("name,text,expected", [
    ("refined.pcr", PCR_HEADER_ONLY, "fullprof_pcr"),
    ("run.inp", INP_MINIMAL, "topas_inp"),
    ("refined.EXP", EXP_MINIMAL, "gsas_exp"),
    # the suffix is not the evidence here either
    ("whatever", EXP_MINIMAL, "gsas_exp"),
    # a Pawley or indexing-only .inp states no phase and is still a .inp
    ("pawley.inp", INP_NO_PHASE, "topas_inp"),
    # and one this build refuses to *read* is still recognised, so the caller
    # gets the reader's refusal naming the macro rather than "no format claims
    # this file", which is the less useful of the two messages
    ("macro.inp", INP_STR_MACRO, "topas_inp"),
])
def test_a_file_reaches_the_format_that_can_read_it(tmp_path, name, text, expected):
    assert identify_project_format(_write(tmp_path, name, text)).name == expected


def test_the_suffix_is_not_the_evidence(tmp_path):
    """``.inp`` is written by unrelated programs, so content decides.

    ``io/CLAUDE.md`` § Dispatch, and WP-1407's rule one rank up: a file
    extension does not name a format here.  An Abaqus deck with the same suffix
    is refused, and a ``.pcr``'s content is claimed whatever it is called.
    """
    with pytest.raises(ValueError, match="not a refinement file"):
        identify_project_format(_write(tmp_path, "mesh.inp", ABAQUS_INP))
    assert identify_project_format(
        _write(tmp_path, "no_suffix_at_all", PCR_HEADER_ONLY)).name == "fullprof_pcr"


def test_the_record_width_is_half_the_exp_evidence(tmp_path):
    """A GSAS key at column 0 is not enough on its own.

    ``HST`` and ``DESCR`` are ordinary words, so a file quoting them at the
    start of a line — a note about the format, or another program's fixed-column
    table — would be claimed on the vocabulary alone.  The 80-character record
    is a structural invariant of the format (GSAS read these by direct access),
    so the two tests together are what make the claim safe.
    """
    with pytest.raises(ValueError, match="not a refinement file"):
        identify_project_format(_write(tmp_path, "narrow.EXP", EXP_WRONG_WIDTH))


def test_a_gsas_instrument_file_is_not_claimed_as_a_refinement(tmp_path):
    """``.PRM`` is 80-column GSAS too, and belongs to a different reader.

    It carries a machine and no model, which is why it sits outside this
    registry (``read_gsas_prm``); its keys are ``INS``, absent from the
    vocabulary here, so the sniff declines it and the refusal names where it
    should go instead.
    """
    prm = _cards("INS   BANK      1", "INS   HTYPE   PXCR")
    with pytest.raises(ValueError, match="read_gsas_prm"):
        identify_project_format(_write(tmp_path, "inst.prm", prm))



def test_a_latin1_title_does_not_cost_the_file_its_sniff(tmp_path):
    """A ``.EXP`` is a byte format and its title is whatever was typed.

    ``head`` decodes as UTF-8 with ``errors="ignore"``, so one accented
    character in a ``DESCR`` record is *dropped* and that card measures 79
    characters in the decoded text while still being 80 bytes on disk.  The
    width test therefore runs on the bytes.  Reading the text instead rejected
    the whole file over one byte, which is the shape of refusal nobody can
    debug from the message.
    """
    title = "      DESCR   caf\xe9 standard".encode("latin-1")
    path = tmp_path / "accented.EXP"
    path.write_bytes(b"\r\n".join([
        b"     VERSION    6".ljust(80),
        title.ljust(80),
        b" EXPR  NHST     1".ljust(80),
    ]) + b"\r\n")
    assert len(title.ljust(80)) == 80
    assert len(title.ljust(80).decode("utf-8", errors="ignore")) == 79
    assert identify_project_format(path).name == "gsas_exp"


def test_a_keyword_inside_a_comment_is_not_a_statement(tmp_path):
    """The sniff goes through the reader's own ``strip_comments``.

    Both TOPAS comment forms are here — ``'`` to end of line and a nesting
    ``/* */`` block — because a sniff that reimplemented either would be a
    second grammar to keep in step with the parser, and the two would drift.
    """
    with pytest.raises(ValueError, match="not a refinement file"):
        identify_project_format(_write(tmp_path, "comments.inp", INP_ALL_COMMENTED))


def test_the_refusal_names_what_this_build_does_open(tmp_path):
    """A message, not a traceback — and it points the three near misses onward.

    A caller reaching this has a file of *some* kind, and the three things it is
    most likely to be each have a reader that is deliberately not in this
    registry.  Naming them is the difference between "no" and "not here, try
    that".
    """
    with pytest.raises(ValueError) as exc:
        identify_project_format(_write(tmp_path, "x.txt", "10.0 3\n10.1 5\n"))
    message = str(exc.value)
    for expected in ("FullProf .pcr", "TOPAS .inp", "read_pattern",
                     "read_gsas_prm", "read_recipe"):
        assert expected in message


def test_the_refusal_says_when_the_file_is_binary(tmp_path):
    """A vendor binary is the likeliest thing to arrive at the wrong door.

    Every sniff here decodes with ``errors="ignore"``, so a ``.raw`` looks from
    the refusal exactly like a text file nothing claimed — and all three readers
    the message goes on to name are wrong advice for it.  ``identify_format``
    says so one registry over, for the same reason and in the same words.
    """
    path = tmp_path / "scan.raw"
    path.write_bytes(b"RAW1.01\x00\x00\x00\x00" + bytes(64))
    with pytest.raises(ValueError, match="looks binary"):
        identify_project_format(path)


def test_read_project_model_tags_the_answer_with_its_format(tmp_path):
    """The answer names the format and hands on the format's own model.

    Deliberately not a union with optional fields: a blank would read as an
    answer (WP-1076), so a caller reads ``stated`` and gets only fields the
    format really has.
    """
    model = read_project_model(_pcr(tmp_path, "refined.pcr", _phase()))
    assert model.format.name == "fullprof_pcr"
    assert model.path.name == "refined.pcr"
    assert model.stated.phases and model.stated.phases[0].name == "Trirutile"
    # `reports_at="build"`, so the repairs reach the list handed to to_structure
    diagnostics: list = []
    structure = model.to_structure(diagnostics=diagnostics)
    assert [p.name for p in structure.phases] == ["Trirutile"]
    # the file's own refine flags crossed, decoded out of the codewords — the
    # half nobody can reconstruct from a CIF plus a pattern
    assert structure.phases[0].scale.vary is True


def test_the_inp_reader_reports_its_repairs_at_read(tmp_path):
    """``reports_at="both"`` (the magnetic chain's TOPAS_MOMENT_* diagnostics
    added the build half; this call exercises the read half, still the one
    a plain import with no ``magnetic_symmetry=`` reaches), exercised rather
    than asserted from the table."""
    diagnostics: list = []
    model = read_project_model(_write(tmp_path, "run.inp", INP_MINIMAL),
                               diagnostics=diagnostics)
    assert model.format.reports_at == "both"
    assert model.stated.r_wp == pytest.approx(9.73)
    structure = model.to_structure()
    assert [p.name for p in structure.phases] == ["corundum"]
    # the file's own refine flags crossed, which is the payload this WP is about
    assert structure.phases[0].cell.a.vary is True


def test_the_reads_reports_are_on_the_answer_whether_or_not_a_list_was_passed(tmp_path):
    """The asymmetry must not become a silent empty list.

    A `.inp` reports while parsing and a `.pcr` while converting, so a caller
    who passes their list to the *other* call gets nothing back — and an empty
    list reads as "this file needed no repairs", which is WP-1076's trap with a
    different shape.  So the read's half is kept on the answer regardless, the
    way `Recipe` keeps its own, and the keyword stays what it is everywhere else
    in this package: a channel for a caller accumulating across several files.
    """
    # The fixture's `occ Al+3` is TOPAS's sign-first spelling; rietx's species
    # are IUCr digit-first, so the reader rewrites it to `Al3+` and reports the
    # substitution.  A real repair, and one a caller reading the model back
    # could not otherwise tell from a stated value.
    path = _write(tmp_path, "run.inp", INP_MINIMAL)

    silent = read_project_model(path)                    # no list passed
    codes = {d.code for d in silent.diagnostics}
    # `R-3c` is bare, and the tables hold it on hexagonal and on rhombohedral
    # axes, so the read reports the setting it assumed as well (WP-1118).  The
    # `.inp` carries no operator list to settle it the way a `.gpx` does.
    assert codes == {"TOPAS_SPECIES_NORMALISED",
                     "SPACE_GROUP_SETTING_ASSUMED"}, (
        "the read's reports are not on the answer")

    collected: list = []
    asked = read_project_model(path, diagnostics=collected)
    assert {d.code for d in collected} == codes          # the caller's list too
    assert {d.code for d in asked.diagnostics} == codes  # and still the answer's
    # and the caller's own list object is extended, never replaced
    assert isinstance(collected, list)

    # the build half adds nothing for this format, and says so by being empty
    # rather than by the read's reports being unreachable
    build_notes: list = []
    asked.to_structure(diagnostics=build_notes)
    assert not build_notes
    assert asked.diagnostics


def test_a_reader_error_reaches_the_caller_naming_the_file(tmp_path):
    """The front door adds no exception of its own.

    ``io/CLAUDE.md`` § Project readers: a project reader refuses where a pattern
    reader would repair, and the refusal names the file.  Dispatching through
    the registry must not turn that into a bare parser exception or a
    half-built model.
    """
    path = _write(tmp_path, "macro.inp", INP_STR_MACRO)
    with pytest.raises(ValueError) as exc:
        read_project_model(path)
    assert "macro.inp" in str(exc.value) and "STR(" in str(exc.value)


def _stub_format(**overrides) -> ProjectFormat:
    """A registry member that exists only for this module.

    Two of the front door's promises are about members no real format is: one
    that reports before it refuses, and one recognised in order to be declined.
    Both are contracts of `read_project_model`/`identify_project_format` rather
    than of any parser, so they are exercised at that level instead of being
    asserted from the table and believed.
    """
    fields = dict(
        name="stub", title="Stub Format", extensions=(".stub",),
        sniff="claims any file, for this module only", carries=("nothing",),
        reports_at="read", matches=lambda _p: True,
        read=lambda _p, **_kw: None, to_structure=lambda _m, **_kw: None)
    return ProjectFormat(**(fields | overrides))


def test_a_read_that_repairs_then_refuses_keeps_what_it_repaired(tmp_path, monkeypatch):
    """Parity with `read_pattern`, which hands its list straight down.

    The front door reads into a list of its own so the answer can carry the
    reports whether or not one was passed — but copying only on success would
    lose every repair a read made before it refused, which is the most useful
    thing a caller holding an exception has: how far it got, and what it found.

    Tested through a stub because **no reader in this build can reach the case
    today**: `read_topas_inp` appends every one of its diagnostics after its
    last raise, and `read_fullprof_pcr` reports at build. So the `finally` is a
    property of the door, asserted where it lives — without it, a reader that
    later emits before refusing would lose the reports in silence.
    """
    def repairs_then_refuses(_path, *, diagnostics=None, **_kw):
        diagnostics.append(Diagnostic(level="info", code="STUB_REPAIRED",
                                      message="a repair made before refusing"))
        raise ValueError("refused after repairing")

    monkeypatch.setattr(registry, "PROJECT_FORMATS",
                        (_stub_format(read=repairs_then_refuses),))
    notes: list = []
    with pytest.raises(ValueError, match="refused after repairing"):
        read_project_model(_write(tmp_path, "x.stub", "anything"),
                           diagnostics=notes)
    assert [d.code for d in notes] == ["STUB_REPAIRED"]


def test_a_refusing_member_is_left_out_of_the_supported_list(tmp_path, monkeypatch):
    """`refuses` has no writer among the members, so exercise the filter itself.

    Root CLAUDE.md: a declared name is a claim, and an absent writer fails no
    test.  `None` is the honest empty state here rather than a defaulted
    `False`, and the field is deliberate symmetry with `PatternFormat.refuses`
    — but the `if f.refuses is None` filter it exists for is unreachable while
    no member sets it, so it is tested against a member that does rather than
    left to be believed.
    """
    declined = _stub_format(matches=lambda _p: False,
                            refuses="recognised in order to be declined")
    monkeypatch.setattr(registry, "PROJECT_FORMATS",
                        (*PROJECT_FORMATS, declined))
    with pytest.raises(ValueError) as exc:
        registry.identify_project_format(
            _write(tmp_path, "nothing.txt", "10.0 3\n10.1 5\n"))
    # in the registry, and absent from the sentence listing what is supported
    assert "Stub Format" not in str(exc.value)
    assert "FullProf .pcr" in str(exc.value)


# --------------------------------------------------------------------------
# The arm


def test_every_project_format_appears_in_the_capabilities_arm():
    """The membership rule ``reader_formats`` is held to, one registry over."""
    caps = rx.capabilities()
    assert [f.name for f in caps.project_formats] == [f.name for f in PROJECT_FORMATS]
    by_name = {f.name: f for f in caps.project_formats}
    assert by_name["fullprof_pcr"].extensions == [".pcr"]
    # the arm states what each file carries *beyond* a structure, which is what
    # a client asks before it reads a model it has no common shape for
    assert "refine flags" in " ".join(by_name["topas_inp"].carries)
    assert by_name["topas_inp"].reports_at == "both"
    assert by_name["fullprof_pcr"].reports_at == "build"


def test_the_front_door_is_what_the_feature_flag_reports():
    """``project_readers`` reports the door, not a format.

    A build that grows a third format should not need this flag edited — which
    format there is is ``project_formats``' question.
    """
    from rietx.capabilities import _SURFACE_FLAGS

    assert _SURFACE_FLAGS["project_readers"] == "read_project_model"
    assert rx.capabilities().features["project_readers"] is True


def test_the_registry_and_the_package_export_the_same_readers():
    """Every member's ``read`` is reachable by name from the package.

    The two halves drift the way ``_SURFACE_FLAGS`` describes: a reader renamed
    in its module keeps working through the registry while the documented name
    is gone, and nothing goes red.  So the check is that each member's callable
    **is** the exported one, by identity.
    """
    exported = {f.read.__name__ for f in PROJECT_FORMATS}
    assert exported <= set(rx.__all__), exported - set(rx.__all__)
    for fmt in PROJECT_FORMATS:
        assert getattr(rx, fmt.read.__name__) is fmt.read


# --------------------------------------------------------------------------
# The declarations


@pytest.mark.parametrize("fmt", PROJECT_FORMATS, ids=lambda f: f.name)
def test_reports_at_matches_the_real_signature(fmt: ProjectFormat):
    """The declared channels are **exactly** the calls that take the keyword.

    ``reports_at`` is read by :meth:`ProjectModel.to_structure` and by
    :func:`read_project_model` to decide which call gets the caller's
    diagnostics list, so a wrong value does not raise — it silently returns an
    empty list, which is the shape of bug that reads as "this file needed no
    repairs".

    Partitioned **both ways** rather than only forwards.  Asserting that the
    declared call takes the keyword leaves the other direction open, which is
    the half that bites: a reader that grows a second channel while its
    declaration still names one keeps working, drops the new channel's reports
    in silence, and passes.  That is how ``gsas_exp`` arrived — it repairs at
    both ends — and a forwards-only assertion would have let it declare
    ``"read"`` and lose every build-time report.
    """
    takes = {
        "read": "diagnostics" in inspect.signature(fmt.read).parameters,
        "build": "diagnostics" in inspect.signature(fmt.to_structure).parameters,
    }
    declared = {"read", "build"} if fmt.reports_at == "both" else {fmt.reports_at}
    actual = {name for name, has in takes.items() if has}
    assert declared == actual, (
        f"{fmt.name} declares reports_at={fmt.reports_at!r}, so its channels "
        f"are {sorted(declared)}, but the calls that actually take a "
        f"diagnostics keyword are {sorted(actual)}.  A channel that exists and "
        f"is not declared is dropped in silence; one declared and absent would "
        f"raise on the first caller who passed a list")


@pytest.mark.parametrize("fmt", PROJECT_FORMATS, ids=lambda f: f.name)
def test_every_declared_field_is_populated(fmt: ProjectFormat):
    """No empty state that reads as an answer (WP-1076).

    ``carries`` and ``sniff`` are prose a client shows a person; an empty one
    is not "this format carries nothing", it is a row nobody wrote.
    """
    assert fmt.name and fmt.title and fmt.sniff
    assert fmt.extensions and all(e.startswith(".") for e in fmt.extensions)
    assert fmt.carries and all(fmt.carries)
    assert callable(fmt.matches) and callable(fmt.read) and callable(fmt.to_structure)


def test_the_order_is_strongest_evidence_first():
    """``PATTERN_FORMATS``' rule, and here it is four members rather than sixteen.

    The binary member goes first, because every other sniff decodes the head
    with ``errors="ignore"`` and would meet a pickle as text with its bytes
    dropped.  Then FullProf, whose evidence is a line the format *requires*
    first, and TOPAS last, whose evidence is a keyword anywhere in a 64 kB head.
    A file satisfying two would be claimed by the stronger test, and the order
    is what says so.
    """
    assert PROJECT_FORMATS[0].name == "gsas2_gpx"
    assert PROJECT_FORMATS[-1].name == "topas_inp"
    text = [f.name for f in PROJECT_FORMATS]
    assert text.index("fullprof_pcr") < text.index("topas_inp")
    assert "COMM" in PROJECT_FORMATS[text.index("fullprof_pcr")].sniff


def test_the_sniff_budgets_differ_by_kind_not_by_taste():
    """A first-line test needs ``HEAD_BYTES``; a keyword scan needs more.

    The ``.inp`` budget is the only one asked for by name in this package, so
    the reason is worth pinning: a ``.inp`` has no required opening, and its
    first block opener sits behind whatever preamble the author wrote.
    """
    from rietx.io.formats.base import HEAD_BYTES

    assert registry.INP_SNIFF_BYTES > HEAD_BYTES


def test_the_three_readers_left_out_are_left_out_on_purpose():
    """``read_gsas_prm``, ``read_recipe`` and the pattern readers are not here.

    Each is a foreign-file reader and each is deliberately outside this
    registry — a ``.prm`` carries a machine and no model, a recipe is a
    build-wide feature that resolves to something ready to fit, and a pattern is
    the other registry's. The test is that they stay reachable and stay out,
    because "it is missing" and "it is elsewhere on purpose" are answers a
    later session has to be able to tell apart.
    """
    names = {f.read.__name__ for f in PROJECT_FORMATS}
    assert "read_gsas_prm" not in names and "read_recipe" not in names
    assert hasattr(rx, "read_gsas_prm") and hasattr(rx, "read_recipe")
    assert rx.capabilities().features["powderline_recipe"] is True


def test_the_arm_names_each_format_writer_by_its_exported_name():
    """The write direction is a name, not a flag, and the name must resolve.

    A format's writer is published as the top-level verb that writes it, so a
    client learns what to call rather than only that something is possible, and
    a format with no writer answers ``None`` rather than ``False`` — which
    would be a claim about a format nobody had wired (WP-1076).  The pair
    drifts exactly as ``_SURFACE_FLAGS`` describes, so the name is checked
    against ``rietx.__all__`` and the callable by identity.
    """
    by_name = {f.name: f for f in rx.capabilities().project_formats}
    for fmt in PROJECT_FORMATS:
        published = by_name[fmt.name].writes
        if fmt.write is None:
            assert published is None
            continue
        assert published == fmt.write.__name__
        assert published in rx.__all__
        assert getattr(rx, published) is fmt.write

    # Three of the four write today, and GSAS-II is the one that does not —
    # a task line in WP-1118 rather than a shape this arm still needs, since a
    # format gaining a writer changes its value and never this field.
    assert by_name["gsas2_gpx"].writes is None
    assert {f.name for f in PROJECT_FORMATS if f.write is not None} == {
        "topas_inp", "fullprof_pcr", "gsas_exp"}
