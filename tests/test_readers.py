"""The pattern readers: dispatch, the option vocabulary, and what they repair.

Three things are asserted here that nothing else can see once a file is read.

**A repair is only allowed where it can be reported.**  Root CLAUDE.md's rule is
that a silent correction is a reader's to make, and only where the deviation is
a *report* rather than a *contradiction*.  ``ascending`` is that rule applied to
2θ ordering, and the tests below are one per row of its table — including the
two rows that **raise**, which are the load-bearing half: a file whose ranges are
stitched or whose duplicate points disagree has more than one defensible reading,
and picking one silently is exactly what this package refuses.

**A dropped reader option is not the same as a typo'd one.**  The first is
normal (a form carries a value across a change of file) and is reported; the
second is a caller error and raises.  Both are ``reader_options_for``'s.

**A sniff is bounded.**  ``head`` reads a fixed prefix, so the cost of asking ten
formats "is this yours?" does not scale with the pattern.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.io.formats import (
    METADATA_KEYS,
    PATTERN_FORMATS,
    head,
    metadata,
    multiscan_default,
)
from rietx.io.formats.base import PatternFormat, ascending, reader_options_for
from rietx.io.readers import identify_format, list_scans


def write_xy(path, tt, y, sig=None):
    rows = ([f"{a} {b}" for a, b in zip(tt, y)] if sig is None
            else [f"{a} {b} {c}" for a, b, c in zip(tt, y, sig)])
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


# ----------------------------------------------------------------- ascending
def test_a_scan_stored_high_to_low_is_reversed_and_says_so(tmp_path):
    """The same measurement, stored backwards — reversing loses nothing.

    Several vendor formats write a scan measured high→low, and ``PatternData``
    requires strictly increasing 2θ, so before this the file simply did not
    open.  The reversal is a *report*: no datum is invented, dropped or chosen.
    """
    p = write_xy(tmp_path / "down.xy", [30.0, 20.0, 10.0], [3.0, 2.0, 1.0])
    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.two_theta == [10.0, 20.0, 30.0]
    assert data.intensity == [1.0, 2.0, 3.0]     # carried with its own 2θ
    assert [d.code for d in notes] == ["PATTERN_SCAN_REVERSED"]
    # and with no list to report into it still reads: the channel is optional
    assert rx.read_pattern(p).two_theta == [10.0, 20.0, 30.0]


def test_the_esd_column_is_reversed_with_the_points_it_belongs_to(tmp_path):
    """σ is per point, so a reversal that moved only 2θ and y would silently
    re-pair every weight with the wrong channel — invisible in every plot."""
    p = write_xy(tmp_path / "down.xye", [3.0, 2.0, 1.0], [30.0, 20.0, 10.0],
                 [3.3, 2.2, 1.1])
    data = rx.read_pattern(p)
    assert data.two_theta == [1.0, 2.0, 3.0]
    assert data.sigma == [1.1, 2.2, 3.3]


def test_a_repeated_point_with_the_same_intensity_is_dropped(tmp_path):
    """A format artefact: the repeat carries no measurement the first lacks."""
    p = write_xy(tmp_path / "dup.xy", [10.0, 20.0, 20.0, 30.0],
                 [1.0, 2.0, 2.0, 3.0])
    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.two_theta == [10.0, 20.0, 30.0]
    assert [d.code for d in notes] == ["PATTERN_DUPLICATE_POINTS"]


def test_a_repeated_point_with_a_different_intensity_is_refused(tmp_path):
    """A contradiction, not a report — and the difference is the whole rule.

    Averaging the two invents a datum that was never measured; dropping one
    picks a measurement arbitrarily.  Both are choices the caller has to make,
    so the reader names the 2θ and stops.
    """
    p = write_xy(tmp_path / "clash.xy", [10.0, 20.0, 20.0, 30.0],
                 [1.0, 2.0, 7.0, 3.0])
    with pytest.raises(ValueError, match=r"20.*appears twice"):
        rx.read_pattern(p)


def test_stitched_ranges_are_refused_rather_than_sorted_or_concatenated(tmp_path):
    """GSAS-II concatenates, which mixes two step sizes and two counting times
    into one weighting regime.  Here the three readings are three different
    measurements and choosing between them is the caller's."""
    p = write_xy(tmp_path / "stitch.xy", [10.0, 11.0, 12.0, 10.5, 11.5],
                 [1.0, 2.0, 3.0, 4.0, 5.0])
    with pytest.raises(ValueError, match="does not run in one direction"):
        rx.read_pattern(p)


def test_the_scan_option_is_named_only_by_a_format_that_has_one(tmp_path):
    """Telling someone to select a scan in a file that cannot hold several is a
    wrong instruction, not a vague one — so ``ascending`` takes the format."""
    tt, y = [10.0, 11.0, 10.5], [1.0, 2.0, 3.0]
    # named, not indexed: ``PATTERN_FORMATS[-1]`` meant ``xy`` until WP-1407 put
    # a refusal below it, and this case wants a single-scan *reader*
    single_scan = next(f for f in PATTERN_FORMATS if f.name == "xy")
    with pytest.raises(ValueError) as plain:
        ascending(tt, y, path=tmp_path / "a.xy", fmt=single_scan)
    assert "scan=" not in str(plain.value)

    multi = PatternFormat(
        name="multi", title="Multi", extensions=(), sniff="", sigma="",
        matches=lambda p: False, read=lambda p: None, options=("scan",))
    with pytest.raises(ValueError, match="name one with scan="):
        ascending(tt, y, path=tmp_path / "a.multi", fmt=multi)


def test_a_non_constant_step_is_neither_repaired_nor_refused(tmp_path):
    """SRM 660c is 24 stitched *regions* of differing step and is entirely
    legal; only the *direction* is a question the reader may ask."""
    p = write_xy(tmp_path / "vary.xy", [10.0, 10.1, 10.3, 10.6, 11.0],
                 [1.0, 2.0, 3.0, 4.0, 5.0])
    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)
    assert len(data.two_theta) == 5 and notes == []


def test_every_registered_reader_passes_through_the_same_policy():
    """One helper, not a rule restated per format — otherwise the fourth reader
    is the one that quietly sorts instead of refusing."""
    import inspect

    from rietx.io.formats import chi, gsas, pdcif, ras, xy

    for module in (chi, gsas, pdcif, ras, xy):
        body = inspect.getsource(module)
        assert "ascending(" in body, f"{module.__name__} does not use ascending()"
        assert "diagnostics" in body


def test_the_axis_policy_is_one_function_and_one_code():
    """The same rule for the *other* thing four readers now decide.

    Factored at the fourth consumer, which is where ``io/CLAUDE.md`` said the
    trigger was: the three-way verdict (read / refuse / assume-and-say-so) is
    ``base.check_axis`` and the code is ``PATTERN_X_AXIS_ASSUMED``.  What is
    deliberately *not* shared is the classifying — four formats state their axis
    in four shapes — so this asserts the policy, not the vocabularies.
    """
    import inspect
    import re

    from rietx.io.formats import base, chi, ras, uxd

    emits = re.compile(r'code\s*=\s*"[A-Z_]*X_AXIS_ASSUMED"')
    for module in (chi, ras, uxd):
        body = inspect.getsource(module)
        assert "check_axis(" in body, f"{module.__name__} decides an axis alone"
        assert not emits.search(body), (
            f"{module.__name__} spells its own axis code; there is one, and it "
            "lives in base.check_axis")
    assert inspect.getsource(base).count('code="PATTERN_X_AXIS_ASSUMED"') == 1


# ------------------------------------------------------------- reader options
def test_an_option_this_format_does_not_take_is_dropped_but_reported(tmp_path):
    """A UI carries a value across a change of file and that is normal; an API
    caller who passed it believed they had selected something."""
    p = write_xy(tmp_path / "plain.xy", [10.0, 20.0], [1.0, 2.0])
    notes: list = []
    rx.read_pattern(p, block="_meas", diagnostics=notes)

    assert [d.code for d in notes] == ["READER_OPTION_IGNORED"]
    assert notes[0].where == ["block"] and notes[0].level == "info"


def test_an_option_no_format_takes_is_a_typo_and_raises(tmp_path):
    p = write_xy(tmp_path / "plain.xy", [10.0, 20.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="unknown reader option 'blcok'"):
        rx.read_pattern(p, blcok="_meas")


def test_none_means_unspecified_rather_than_a_value():
    """``read_pattern(p, block=None)`` still reads the first block that parses,
    which is what every caller threading an absent setting through relies on."""
    pdcif = next(f for f in PATTERN_FORMATS if f.name == "pdcif")
    assert reader_options_for(pdcif, {"block": None}) == {}
    assert reader_options_for(pdcif, {"block": "_meas"}) == {"block": "_meas"}


def test_an_int_option_arrives_as_an_int_however_it_was_stored():
    """``DataRef.options`` is dict[str, str], so a scan round-trips through a
    project as "2" and has to reach the reader as the integer 2."""
    from rietx.io.formats.base import ReaderOption

    assert ReaderOption(name="scan", kind="int", help="").coerce("2") == 2
    with pytest.raises(ValueError, match="scan= takes an integer"):
        ReaderOption(name="scan", kind="int", help="").coerce("first")


def test_the_default_scan_is_never_a_silent_one(tmp_path):
    """Reading one of a file's scans is a choice, and a default only the GUI
    preview reveals leaves the API and the CLI blind — ``INDEX_SHIFT_ALLOWANCE``
    one seam over: an assumed selection must not look like a deliberate one."""
    notes: list = []
    multiscan_default(3, None, path=tmp_path / "m.ras", diagnostics=notes)
    assert [d.code for d in notes] == ["PATTERN_MULTISCAN_DEFAULTED"]
    assert "scan 0 of 3" in notes[0].message

    quiet: list = []
    multiscan_default(3, 1, path=tmp_path / "m.ras", diagnostics=quiet)   # chosen
    multiscan_default(1, None, path=tmp_path / "m.ras", diagnostics=quiet)  # only one
    assert quiet == []


# ---------------------------------------------------------------------- chi
def write_chi(path, x_label, tt, y, *, declared=None, n_datasets=1):
    count = len(tt) if declared is None else declared
    head_lines = [path.stem + ".tif", x_label, "Intensity",
                  f"       {count}" + (f"  {n_datasets}" if n_datasets else "")]
    rows = [f"  {a:.6f}  {b:.6f}" for a, b in zip(tt, y)]
    path.write_text("\n".join(head_lines + rows) + "\n", encoding="utf-8")
    return path


def test_the_chi_point_count_line_is_no_longer_read_as_a_data_point(tmp_path):
    """The regression this reader exists for.

    ``.chi`` line 4 is ``<npoints> [<ndatasets>]``, and ``2000 1`` is a
    perfectly good pair of floats — so the ASCII-column fallback appended it as
    a point at x = 2000, y = 1.  A phantom datum thousands of degrees outside
    the pattern, which survives every plot and quietly widens the fitted range.
    """
    tt = [10.0, 10.01, 10.02]
    p = write_chi(tmp_path / "ceo2.chi", "2-Theta Angle (Degrees)", tt,
                  [1.0, 2.0, 3.0], n_datasets=1)

    assert identify_format(p).name == "chi"
    data = rx.read_pattern(p)
    assert data.two_theta == tt              # three points, not four
    assert 3.0 not in data.two_theta         # the count line is not a datum

    # and the fallback really would have taken it: the same bytes, read as xy
    from rietx.io.formats.xy import read_xy
    assert len(read_xy(p).two_theta) == len(tt) + 1


@pytest.mark.parametrize("label,what", [
    ("q (nm^-1)", "scattering vector"),
    ("Q_A^-1", "scattering vector"),
    ("d (Angstrom)", "d-spacing"),
    ("d-spacing", "d-spacing"),
])
def test_an_axis_that_is_recognisably_not_two_theta_is_refused(tmp_path, label, what):
    """Reading a q axis as 2θ gives a confident wrong cell from values that
    parse perfectly — the exact failure class this package refuses.  The
    conversion needs a wavelength the file does not carry, so inventing one
    would be worse than declining."""
    p = write_chi(tmp_path / "int.chi", label, [1.0, 2.0], [1.0, 2.0])
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(p)
    assert repr(label) in str(exc.value) and what in str(exc.value)


def test_a_two_theta_label_wins_over_the_d_in_degrees(tmp_path):
    """"2-Theta Angle (Degrees)" must not be read as a d axis by its own
    spelling — which is why the 2θ recogniser is consulted first."""
    p = write_chi(tmp_path / "ok.chi", "2-Theta Angle (Degrees)", [1.0, 2.0],
                  [1.0, 2.0])
    notes: list = []
    rx.read_pattern(p, diagnostics=notes)
    assert notes == []


def test_an_unrecognisable_axis_is_read_as_two_theta_and_says_so(tmp_path):
    """Unrecognisable is not the same as recognisably wrong: most files really
    are 2θ, so this reads — but the assumption is stated, with the label."""
    p = write_chi(tmp_path / "odd.chi", "Angle", [1.0, 2.0], [1.0, 2.0])
    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert [d.code for d in notes] == ["PATTERN_X_AXIS_ASSUMED"]
    assert "'Angle'" in notes[0].message
    assert data.metadata["x_label"] == "Angle"   # verbatim, never normalised


def test_the_count_gate_is_what_keeps_an_xy_with_a_prose_header_out(tmp_path):
    """The shape gate alone is not decisive — a three-line prose header over a
    lone integer passes it — so line 4's own claim is checked against the rows
    that follow.  That read is O(N) and is the one stated exemption to the
    bounded-head rule; it runs only behind the shape gate."""
    tt, y = [10.0, 10.01, 10.02], [1.0, 2.0, 3.0]
    honest = write_chi(tmp_path / "real.chi", "2-Theta", tt, y)
    lying = write_chi(tmp_path / "prose.xy", "2-Theta", tt, y, declared=999)

    assert identify_format(honest).name == "chi"
    assert identify_format(lying).name == "xy"   # falls through, as it should


# ---------------------------------------------------------------------- dif
PEAK_LIST = """\
Quartz, SiO2
  D-SPACING   INTENSITY   H  K  L
     4.25510      16.29    1  0  0
     3.34350     100.00    1  0  1
     2.45680       9.15    1  1  0
     2.28150       8.09    1  0  2
     2.23670       4.29    1  1  1
"""


def test_a_peak_list_is_refused_by_name_rather_than_refined_against(tmp_path):
    """~30 delta functions are not a profile, and Rwp will not say so.

    The ASCII fallback reads a ``.dif`` perfectly happily; the refinement that
    follows fits every background coefficient, every width and every scale to a
    picture of a diffractogram.  So the file is claimed *in order to be
    declined*, and the refusal names what to do instead.
    """
    p = tmp_path / "quartz.dif"
    p.write_text(PEAK_LIST, encoding="utf-8")

    fmt = identify_format(p)
    assert fmt.name == "dif_peaklist" and fmt.refuses
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(p)
    assert "quartz.dif" in str(exc.value) and "peak list" in str(exc.value)
    assert "index_pattern" in str(exc.value)   # the tool that does take positions


def test_the_evidence_is_the_hkl_columns_not_the_suffix(tmp_path):
    """A real profile someone named ``.dif`` still opens: the suffix is a
    filename and the Miller indices are the format."""
    p = tmp_path / "actually_a_scan.dif"
    p.write_text("\n".join(f"{10 + i * 0.02:.4f} {i}" for i in range(60)),
                 encoding="utf-8")

    assert identify_format(p).name == "xy"
    assert len(rx.read_pattern(p).two_theta) == 60


def test_a_peak_list_under_another_suffix_is_not_claimed(tmp_path):
    """The converse, stated so the pair is symmetric: matching needs *both*, so
    this reader cannot start claiming ASCII files with integer columns."""
    p = tmp_path / "quartz.txt"
    p.write_text(PEAK_LIST, encoding="utf-8")
    assert identify_format(p).name != "dif_peaklist"


def test_a_refusal_is_an_entry_in_capabilities_not_a_side_table():
    """``reader_formats`` would mean two things if refusals lived elsewhere; the
    field says which an entry is, so a client can tell "we can open this" from
    "we know what this is and it is the wrong kind of file"."""
    caps = rx.capabilities()
    by_name = {r.name: r for r in caps.reader_formats}
    assert by_name["dif_peaklist"].refuses
    assert all(by_name[f.name].refuses is None
               for f in PATTERN_FORMATS if f.refuses is None)


# --------------------------------------------------------------------- head
def test_the_head_read_is_bounded_and_reports_the_mark(tmp_path):
    """A sniff may not cost O(file): the predecessor decoded a whole file and
    then sliced 4 kB off it, once per registered format."""
    p = tmp_path / "big.xy"
    p.write_text("BANK 1\n" + "0.0 1.0\n" * 40_000, encoding="utf-8")
    h = head(p)
    assert len(h.raw) == 4096 and h.encoding == "utf-8" and h.bom is False
    assert h.text.startswith("BANK 1")


@pytest.mark.parametrize("mark,codec", [
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
])
def test_a_byte_order_mark_names_the_codec_and_strips_itself(tmp_path, mark, codec):
    """Load-bearing beyond the encoding: ASCII-range UTF-16LE is *valid* UTF-8
    with interleaved NULs, so the mark is what will separate a Windows vendor
    export from a binary file when ``xy`` stops being total."""
    body = "BANK 1"
    raw = mark + (body.encode("utf-16-le") if mark == b"\xff\xfe"
                  else body.encode("utf-16-be") if mark == b"\xfe\xff"
                  else body.encode("utf-8"))
    p = tmp_path / "marked.txt"
    p.write_bytes(raw)
    h = head(p)
    assert h.encoding == codec and h.bom is True
    assert h.text == body          # the mark itself is not part of the text


def test_head_is_not_cached_because_restage_re_reads_the_same_path(tmp_path):
    """A path-keyed cache would be a correctness hazard for exactly the file a
    user just replaced — which is what the GUI's restage does."""
    p = tmp_path / "same.xy"
    p.write_text("first\n", encoding="utf-8")
    assert head(p).text.startswith("first")
    p.write_text("second\n", encoding="utf-8")
    assert head(p).text.startswith("second")


# ----------------------------------------------------------------- dispatch
def test_a_gsas_file_is_claimed_by_content_not_by_suffix(tmp_path):
    """``.raw`` is a GSAS extension *and* Bruker's binary one; the two are held
    disjoint by construction (a BANK record against magic bytes), so the name
    on the file never decides."""
    p = tmp_path / "misnamed.dat"
    p.write_text("BANK 1 3 3 CONS 1000.0 100.0 0 0 STD\n  1  2  3\n",
                 encoding="utf-8")
    assert identify_format(p).name == "gsas"


# --------------------------------------------------------------- gsas ESD
def write_gsas_esd(path: Path, intensities, esds, *, start=5000.0, step=10.0,
                   title="synthetic ESD bank") -> Path:
    """A GSAS ESD bank, packed at the field *positions* the format declares.

    The layout is written **literally** here — eight characters to a field,
    five (intensity, esd) pairs to an 80-column record — and nothing is
    imported from ``rietx.io.formats.gsas``.  A writer that shares its
    constants with the parser can only confirm that the parser agrees with
    itself (`src/rietx/io/CLAUDE.md` § Adding a format), and the whole point
    of this fixture is that the *position* of a field carries meaning the
    whitespace between fields does not.

    ``start`` and ``step`` are centidegrees, as the BANK record's are.
    """
    assert len(intensities) == len(esds)
    fields = [f"{v:8.1f}" for pair in zip(intensities, esds, strict=True)
              for v in pair]
    assert all(len(f) == 8 for f in fields), (
        "a value overflowed its 8-character field, so this fixture would be "
        "testing a file GSAS could not have written")
    while len(fields) % 10:                      # pad the last record, as GSAS does
        fields.append(f"{0.0:8.1f}")
    records = ["".join(fields[i:i + 10]) for i in range(0, len(fields), 10)]
    assert all(len(r) == 80 for r in records)
    path.write_text(
        f"{title}\n"
        f"BANK 1 {len(intensities)} {len(records)} CONS "
        f"{start:.6f} {step:.6f} 0 0 ESD\n" + "\n".join(records) + "\n",
        encoding="utf-8")
    return path


def test_an_esd_intensity_that_fills_its_field_keeps_its_own_number(tmp_path):
    """The bug real APS 11-BM standards patterns exposed, in a synthetic bank.

    An ESD field is eight characters.  An intensity of 100000.0 or more written
    to one decimal fills all eight, so **no separating space is left** and the
    field abuts the esd in front of it: ``11BM_LaB6.raw``'s line 1050 reads
    ``… 64175.2   298.5101641.3   375.8``, and splitting it on whitespace
    yields nine numbers where the record holds ten.  Every channel after that
    point is then shifted — on that file it happened to raise, because two
    decimal points do not parse, but a bank whose values carry no decimal point
    would have fused into a plausible wrong number instead.

    Reading the field by position is what makes the record's own arithmetic
    hold, so that is what is asserted: the numbers back out exactly as written.
    ``tests/data/README.md`` § GSAS ESD records which real files established
    this and why none of them is vendored.
    """
    intensity = [1998.8, 27996.3, 41437.0, 64175.2, 101641.3, 157086.4,
                 224981.5, 999999.9, 287704.3, 42.0]
    esd = [44.7, 167.3, 203.6, 253.3, 318.8, 396.3, 474.3, 1000.0, 536.4, 6.5]
    p = write_gsas_esd(tmp_path / "highcount.gsa", intensity, esd)

    # the fixture really does pack the offending layout, not merely a big
    # number: the record it wrote has no space at that boundary, and so a
    # whitespace split of it loses values.
    record = p.read_text(encoding="utf-8").splitlines()[2]
    assert "253.3101641.3" in record, (
        "this fixture is not packing the fusion it exists for")
    assert len(record.split()) == 9, "the record holds ten fields, not nine"

    d = rx.read_pattern(p)
    assert d.intensity == pytest.approx(intensity, abs=0.0)
    assert d.sigma == pytest.approx(esd, abs=0.0)
    assert d.two_theta == pytest.approx(
        [50.0 + 0.1 * i for i in range(len(intensity))])


def test_an_esd_field_that_is_not_a_number_is_refused_by_name(tmp_path):
    """A positional read can no longer fall back on "whatever splitting gives",
    so the field that does not parse has to say *which* field it was — the
    reader's own boundary, per `src/rietx/io/CLAUDE.md` § Refusals.  ``float``'s
    unaided complaint names neither the file nor the column."""
    p = write_gsas_esd(tmp_path / "corrupt.gsa", [10.0] * 10, [3.0] * 10)
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[2] = lines[2][:16] + "    n/a " + lines[2][24:]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc:
        rx.read_pattern(p)
    assert "corrupt.gsa" in str(exc.value)
    assert "17-24" in str(exc.value) and "'n/a'" in str(exc.value)


def test_a_project_keeps_the_repairs_in_memory_and_out_of_project_json(tmp_path):
    """They are a deterministic function of bytes + reader + options, and
    ``DataRef`` records all three — so a ``project.json`` field would be a
    second authority.  Putting the repairs in the reader also puts them under
    the fingerprint check, which is what says "a reader change, not a corrupt
    project" if one ever changes."""
    from tests.test_refine_synthetic import perturbed_models

    p = write_xy(tmp_path / "down.xy", [30.0, 20.0, 10.0], [3.0, 2.0, 1.0])
    structure, ins = perturbed_models()
    project = rx.Project.create(tmp_path / "rev.rex", pattern=p,
                                structure=structure, instrument=ins)

    assert [d.code for d in project.data_diagnostics] == ["PATTERN_SCAN_REVERSED"]
    stored = (tmp_path / "rev.rex" / "project.json").read_text(encoding="utf-8")
    assert "PATTERN_SCAN_REVERSED" not in stored
    # …and re-reading reproduces them, because the bytes and the reader did
    assert [d.code for d in rx.Project.open(project.path).data_diagnostics] == [
        "PATTERN_SCAN_REVERSED"]


def test_a_binary_file_is_refused_by_name_rather_than_by_traceback(tmp_path):
    """The failure this seam exists to remove.

    ``xy`` used to be the *total* fallback, so opening a Bruker binary reached
    ``read_text`` and raised a bare ``UnicodeDecodeError`` — a message about
    codecs, from a user who asked to open a diffraction pattern.  Now nothing
    claims it and the refusal names the formats this build does read, built
    from the registry so a format added tomorrow appears in it.

    The bytes here used to *be* a Bruker header, which this build now reads —
    so the case is written as what it always meant: a binary file no registered
    format claims.  A Bruker binary that is merely broken is refused by its own
    reader instead, which is a better message and a different test.

    The **name** moved too, and for the same kind of reason: a binary ``.raw``
    now has its own refusal (six vendors write that suffix), so this case has to
    be a binary file whose suffix claims nothing in order to still reach the
    terminal message.
    """
    p = tmp_path / "d8.dat"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 8)

    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(p)
    message = str(refusal.value)
    assert "d8.dat" in message and "looks binary" in message
    # every **reader**'s title, and no refusal's: a format recognised in order
    # to be declined is not something this build can read, so listing one under
    # "Supported" would contradict the sentence it follows
    for fmt in PATTERN_FORMATS:
        assert (fmt.title in message) is (fmt.refuses is None), fmt.name


def test_an_unclaimed_binary_raw_names_six_vendors_and_picks_none(tmp_path):
    """``.raw`` belongs to six unrelated vendors and this build reads two of
    them, so "not a pattern this build can read" invites the reasonable but
    wrong conclusion that the file is corrupt.  The refusal claims to recognise
    nothing — the format most likely to land here is Stoe's, which has no
    description in any licence anywhere, so asserting a vendor would be exactly
    the guess this area exists to prevent."""
    p = tmp_path / "stoe.raw"
    p.write_bytes(b"\x00\x01\x02\x03" + bytes(range(256)) * 8)

    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(p)
    message = str(refusal.value)

    assert "stoe.raw" in message
    assert "6 unrelated vendors" in message
    for vendor in ("Bruker/Siemens DIFFRAC", "GSAS", "Rigaku", "Scintag",
                   "Shimadzu", "Stoe"):
        assert vendor in message
    # it says which this build reads, and offers a way out
    assert "v3 and v4" in message and "PC-APD" in message
    assert "ASCII" in message
    # and it names no vendor as *this* file's
    assert "is a Stoe" not in message


def test_a_real_raw_is_never_routed_to_the_unclaimed_refusal(tmp_path):
    """The entry sits below every reader, so the ordering cannot go wrong —
    asserted rather than trusted, because the message it would give is
    confidently unhelpful about a file that reads perfectly."""
    from tests.writers_xrd import CORUNDUM_HEAD, write_philips_rd, write_raw4

    bruker = write_raw4(tmp_path / "bruker.raw", [
        dict(start=10.0, step=0.02, intensity=[500.0 + i % 7 for i in range(50)])])
    philips = write_philips_rd(tmp_path / "philips.raw", CORUNDUM_HEAD)

    assert rx.io.readers.identify_format(bruker).name == "bruker_raw"
    assert rx.io.readers.identify_format(philips).name == "philips_rd"
    assert len(rx.read_pattern(bruker).two_theta) == 50


def test_a_pks_or_udi_is_refused_as_a_peak_list_on_its_name(tmp_path):
    """Unlike ``.dif`` this is a suffix match, because no sample of either
    format could be obtained to write a content test against — and the refusal
    says so rather than implying a check it did not do."""
    for name, vendor in (("scan.pks", "Stoe"), ("scan.udi", "PANalytical")):
        p = tmp_path / name
        p.write_text("; peak list\n  10.00   1234   1 1 0\n"
                     "  20.00    567   2 0 0\n", encoding="utf-8")

        with pytest.raises(ValueError) as refusal:
            rx.read_pattern(p)
        message = str(refusal.value)

        assert name in message and vendor in message
        assert "declined on its name" in message


def test_a_real_profile_misnamed_pks_still_opens(tmp_path):
    """``.dif``'s escape, kept: a suffix is a filename.  Dropping it would make
    a genuine two-column scan a lab happened to name ``.pks`` unopenable with
    nothing to do about it."""
    p = tmp_path / "profile.pks"
    p.write_text("".join(f"{10.0 + 0.02 * i:.2f} {500 + i % 7}\n"
                         for i in range(40)), encoding="utf-8")

    assert rx.io.readers.identify_format(p).name == "xy"
    assert len(rx.read_pattern(p).two_theta) == 40


def test_the_pks_escape_survives_a_comment_header_and_a_short_scan(tmp_path):
    """The escape's gate predicts whether ``xy`` would open the file, so it has
    to skip the lines ``xy`` skips: a ``#`` header is the commonest shape a
    two-column export has, and counting those lines against it closed the escape
    for exactly the files it exists to let out.  The bounded read's cut line is
    dropped for the same reason it is dropped at all — only when the read *was*
    bounded, or an eight-row profile is refused for being seven rows long."""
    commented = tmp_path / "header.pks"
    commented.write_text("# sample: alumina\n! 2theta intensity\n" +
                         "".join(f"{10.0 + 0.02 * i:.2f} {500 + i % 7}\n"
                                 for i in range(40)), encoding="utf-8")
    short = tmp_path / "short.udi"
    short.write_text("".join(f"{10.0 + 0.02 * i:.2f} {500 + i % 7}\n"
                             for i in range(8)), encoding="utf-8")

    assert rx.io.readers.identify_format(commented).name == "xy"
    assert len(rx.read_pattern(commented).two_theta) == 40
    assert rx.io.readers.identify_format(short).name == "xy"

    # and a peak list is still one: its rows carry an hkl and its header is not
    # a comment marker either reader knows
    peaks = tmp_path / "real.pks"
    peaks.write_text("; peak list\n  10.00   1234   1 1 0\n"
                     "  20.00    567   2 0 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="declined on its name"):
        rx.read_pattern(peaks)


def test_a_byte_order_mark_means_text_even_though_utf16_is_full_of_nuls(tmp_path):
    """The one carve-out, and it is not hypothetical: ASCII-range UTF-16LE is
    *valid* UTF-8 with interleaved NULs, and Windows vendor software exports it.
    Before this such a file died with "no numeric data found", so the reach is
    strictly new."""
    p = tmp_path / "windows.xy"
    p.write_bytes("﻿10 1\n20 2\n30 3\n".encode("utf-16-le"))

    assert identify_format(p).name == "xy"
    assert rx.read_pattern(p).two_theta == [10.0, 20.0, 30.0]


def test_the_registry_order_is_the_dispatch_order():
    """The first format whose ``matches`` returns True reads the file, so the
    tuple's order is behaviour and ``xy`` being last **of the readers** is the
    whole of why anything else is ever reached.

    One entry sits below it and it is not a reader: ``raw_unclaimed`` refuses a
    binary ``.raw`` every reader has already declined, and its position is what
    makes that safe — reached last, it cannot shadow anything, so no ordering
    mistake can route a real Bruker or Philips file into a message that names
    six vendors and picks none.  That is asserted as a property of what the
    entry *is* rather than as its index, so a second such refusal does not
    silently slip above a reader.
    """
    names = [f.name for f in PATTERN_FORMATS]
    readers = [f.name for f in PATTERN_FORMATS if f.refuses is None]

    assert readers[-1] == "xy"
    assert names[-1] == "raw_unclaimed"
    assert len(set(names)) == len(names)
    # every entry after the last reader is a refusal
    assert all(f.refuses is not None
               for f in PATTERN_FORMATS[names.index("xy") + 1:])


# --------------------------------------------------------------------- gsas
def write_gsas(path, *, bintype, flag, body, nchan, nrec=1,
               coeffs=(1000.0, 250.0, 0, 0)):
    """A GSAS bank, packed literally: ``BANK`` record then the rows given.

    The record is written in the vendor's own field order — bank number, channel
    count, record count, bintype, then the bintype's coefficients, then the type
    flag **last**.  ``flag=None`` writes no flag at all, which is legal and means
    STD; ``coeffs`` is variable-length because that order is what puts a
    *coefficient* in the flag's position when a file writes an odd number of them.
    """
    head_line = " ".join(["BANK", "1", str(nchan), str(nrec), bintype,
                          *(str(c) for c in coeffs)])
    if flag is not None:
        head_line += f" {flag}"
    path.write_text(f"a synthetic {bintype}/{flag} bank\n{head_line}\n{body}",
                    encoding="utf-8")
    return path


def gsas_esd_rows(pairs):
    """(intensity, esd) pairs as ESD records: ten 8-character fields to a row."""
    flat = [v for pair in pairs for v in pair]
    assert all(len(f"{v:8.1f}") == 8 for v in flat)     # no field overflows
    return "".join("".join(f"{v:8.1f}" for v in flat[i:i + 10]) + "\n"
                   for i in range(0, len(flat), 10))


def gsas_fxye_rows(rows):
    """(centidegrees, y, esd) triples, free-format as the spec has FXYE."""
    return "".join(f"{a:15.4f}{b:15.4f}{c:15.4f}\n" for a, b, c in rows)


#: Six (intensity, esd) pairs — twelve numbers, and **twelve divides by three**,
#: which is the whole trap: that was the only gate a non-CONS bank had to pass
#: before being read as three-column FXYE.  The values are chosen so the wrong
#: reading comes out *ascending* and therefore survives ``ascending``'s
#: non-monotone refusal: every third number (10, 20, 30, 40) rises.
_ESD_PAIRS = [(10.0, 3.2), (100.0, 20.0), (105.0, 10.2),
              (30.0, 5.5), (120.0, 40.0), (130.0, 11.4)]


@pytest.mark.parametrize("bintype", [
    "LOG6",                                 # a flight time on a clock with no table
    "COND", "CONQ", "LPSD", "EDS",          # d-spacing, Q, detector position, energy
])
def test_a_bintype_whose_axis_has_nowhere_to_go_is_refused_by_name(tmp_path, bintype):
    """`PatternData` holds a 2θ and a flight time; these are neither.

    Read as FXYE — which is what a non-``CONS`` bank was once forced into — the
    file's own x column comes back divided by 100 and labelled degrees, so a
    d-spacing or a Q presents as a perfectly plausible scan.  This is the axis
    policy's *recognisably something else* row reached through the bintype, and
    the refusal names the file, the bintype and what its axis actually holds.

    `COND` and `CONQ` are in the list on purpose: they share three characters
    with `CONS` and are different axes, so they are what a prefix match would
    have swallowed.  `LOG6` is here rather than beside the two TOF bintypes read
    below because its step table is the Los Alamos Model 6 clock's and is not in
    the data file at all — the axis is a flight time and is still not
    establishable.
    """
    tof = [1000.0 + 250.0 * i for i in range(37)]
    rows = [(t, 500.0, 22.4) for t in tof]
    p = write_gsas(tmp_path / f"{bintype.lower()}.gsa", bintype=bintype,
                   flag="FXYE", body=gsas_fxye_rows(rows), nchan=len(rows))
    with pytest.raises(ValueError) as e:
        rx.read_pattern(p)
    assert p.name in str(e.value) and bintype in str(e.value)

    # the same bytes with the one bintype that *is* established parse, so the
    # refusal above is the bintype's doing and not a broken fixture
    ok = write_gsas(tmp_path / "cons.gsa", bintype="CONS", flag="FXYE",
                    body=gsas_fxye_rows(rows), nchan=len(rows))
    assert rx.read_pattern(ok).two_theta[0] == pytest.approx(10.0)


@pytest.mark.parametrize("bintype", ["RALF", "SLOG", "TIME_MAP"])
def test_a_tof_bintype_with_its_own_x_column_reads_as_microseconds(tmp_path, bintype):
    """The other half of the same decision, now the axis has somewhere to go.

    **The bintype decides the fold**, which is the whole point: these are the
    identical bytes the ``CONS`` control below reads as centidegrees, and the
    manual's own words for an FXYE x column are "centidegrees for CW data or
    microseconds for TOF data".
    """
    tof = [1000.0 + 250.0 * i for i in range(37)]
    rows = [(t, 500.0, 22.4) for t in tof]
    p = write_gsas(tmp_path / f"{bintype.lower()}_fxye.gsa", bintype=bintype,
                   flag="FXYE", body=gsas_fxye_rows(rows), nchan=len(rows))
    data = rx.read_pattern(p)
    assert data.axis == "tof"
    assert data.two_theta is None
    assert data.tof[0] == pytest.approx(1000.0)
    assert data.tof[-1] == pytest.approx(tof[-1])

    ok = write_gsas(tmp_path / "cons.gsa", bintype="CONS", flag="FXYE",
                    body=gsas_fxye_rows(rows), nchan=len(rows))
    assert rx.read_pattern(ok).two_theta[0] == pytest.approx(10.0)


def test_a_ralf_bank_of_esd_pairs_is_not_read_as_three_column_fxye(tmp_path):
    """The bintype/type-flag conflation, at the value count that hid it.

    A bank's binning says nothing about how its records are packed, so a ``RALF``
    bank whose flag says ``ESD`` holds (intensity, esd) pairs — but the old code
    forced every non-``CONS`` bank to FXYE unless its value count failed a
    divisible-by-three test, which twelve numbers pass.  Six channels then came
    back as four points whose 2θ were intensities and whose intensities were
    esds, ascending and plausible.
    """
    flat = [v for pair in _ESD_PAIRS for v in pair]
    assert len(flat) % 3 == 0                    # the fixture really is the trap
    body = gsas_esd_rows(_ESD_PAIRS)
    p = write_gsas(tmp_path / "ralf_esd.gsa", bintype="RALF", flag="ESD",
                   body=body, nchan=len(_ESD_PAIRS))
    with pytest.raises(ValueError) as e:
        rx.read_pattern(p)
    assert p.name in str(e.value) and "RALF" in str(e.value)

    # and the identical records under the established bintype read as the pairs
    # they are — which is what says the flag was never the problem
    ok = write_gsas(tmp_path / "cons_esd.gsa", bintype="CONST", flag="ESD",
                    body=body, nchan=len(_ESD_PAIRS))
    d = rx.read_pattern(ok)
    assert d.intensity == [y for y, _ in _ESD_PAIRS]
    assert d.sigma == [s for _, s in _ESD_PAIRS]
    assert d.two_theta == [pytest.approx(10.0 + 2.5 * i)
                           for i in range(len(_ESD_PAIRS))]


def test_an_unrecognised_bintype_is_refused_rather_than_assumed(tmp_path):
    """A bintype the manual does not define is the weaker case of the same rule:
    what its x axis means is not established *at all*, so there is nothing to
    fall back to."""
    p = write_gsas(tmp_path / "mystery.gsa", bintype="QSTEP", flag="FXYE",
                   body=gsas_fxye_rows([(1000.0, 5.0, 2.2), (1100.0, 6.0, 2.4)]),
                   nchan=2)
    with pytest.raises(ValueError, match="QSTEP"):
        rx.read_pattern(p)


@pytest.mark.parametrize("flag", ["ALT", "FXY"])
def test_a_type_flag_with_no_layout_here_is_refused_by_name(tmp_path, flag):
    """Both were read as *counts only* — the STD default, reached silently.

    An ALT record holds x, intensity and an error; an FXY record holds x and
    intensity.  Neither layout is implemented, and falling through to STD put
    the file's own x column into the intensity array and synthesized an axis
    from the bank record in its place.  The output even said so: the pattern
    came back tagged ``gsas-alt``, the flag used as a label and not a decision.
    """
    body = ("".join(f"{t * 100:8.0f}{y:7.0f}{e:6.0f}\n"
                    for t, y, e in [(10.0, 100.0, 10.0), (11.0, 5000.0, 71.0),
                                    (12.0, 120.0, 11.0)])
            if flag == "ALT" else
            "".join(f"{t:12.5f} {y:12.3f}\n"
                    for t, y in [(10.0, 100.0), (11.0, 5000.0), (12.0, 120.0)]))
    p = write_gsas(tmp_path / f"{flag.lower()}.gsa", bintype="CONS", flag=flag,
                   body=body, nchan=3)
    with pytest.raises(ValueError) as e:
        rx.read_pattern(p)
    assert p.name in str(e.value) and flag in str(e.value)


def test_an_unrecognised_type_flag_is_refused_rather_than_read_as_std(tmp_path):
    """The general case: a flag nobody recognises says nothing about a layout,
    so there is no default that is better than a refusal."""
    p = write_gsas(tmp_path / "mystery_flag.gsa", bintype="CONS", flag="XYZW",
                   body="  10 20 30 40\n", nchan=4)
    with pytest.raises(ValueError, match="XYZW"):
        rx.read_pattern(p)


@pytest.mark.parametrize("coeffs", [
    (1000.0, 20.0, 0, 0),        # the shape every real fixture writes
    (1000.0, 20.0),              # c3/c4 omitted
    (1000.0, 20.0, 0),           # an *odd* coefficient count — the trap below
])
def test_a_bank_stating_no_type_flag_is_still_read_as_std(tmp_path, coeffs):
    """``STD`` is the default and has to stay one, which is what makes refusing
    an unrecognised flag a narrow change rather than a wide one.

    The third row is why the flag is matched as a **keyword**: the flag is the
    last field on the record, after the bintype's coefficients, so a record
    writing an odd number of them leaves a coefficient in the flag's position.
    Reading ``0`` there as a flag would refuse a file that parses correctly —
    and before this change it was read as one, and tagged the pattern
    ``gsas-0``.
    """
    p = write_gsas(tmp_path / "noflag.gsa", bintype="CONST", flag=None,
                   body="  10 20 30 40\n", nchan=4, coeffs=coeffs)
    d = rx.read_pattern(p)
    assert d.intensity == [10.0, 20.0, 30.0, 40.0]
    assert d.two_theta == [pytest.approx(10.0 + 0.2 * i) for i in range(4)]
    assert d.sigma is None                       # counts only, Poisson fallback
    assert d.metadata["format"] == "gsas-std"


def _gsas_behind_long_time_map(path, *, table_rows, data_rows=40):
    """A ``TIME_MAP`` bank behind a step table long enough to push its ``BANK``
    record past the sniff window — the shape of a real HIPD@LANSCE file
    (``vnb5053.dat`` from the GSAS distribution's examples), packed literally
    here because that file cannot be vendored (its data carries the Regents of
    the University of California's copyright, which the distribution's own notice
    does not waive).

    The layout is written out, never taken from the parser: a ``TIME_MAP``
    header line, ``table_rows`` records of ten 8-column integers (the tabulated
    step map), then a bank record naming ``TIME_MAP`` with its *one* coefficient
    — the map number — and an ``STD`` flag, then counts.  The single coefficient
    is the point: a real TIME_MAP bank writes a lone map number where a CONS
    bank writes a start angle and a step, so its record does not fit the CONS
    field count.
    """
    lines = ["TIME_MAP10   703   71 TIME_MAP  50 CONLOG[0.30:0.0005]"]
    lines += ["".join(f"{1000 + r * 10 + k:8d}" for k in range(10))
              for r in range(table_rows)]
    bank_offset = len(("\n".join(lines) + "\n").encode("utf-8"))
    lines.append("BANK  1  7550  755 TIME_MAP   1 STD 00000000")
    lines += ["".join(f"{100 + r * 10 + k:8d}" for k in range(10))
              for r in range(data_rows)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path, bank_offset


def test_a_bank_past_the_sniff_window_is_still_claimed_as_gsas(tmp_path):
    """A ``TIME_MAP`` step table can push the first ``BANK`` record past the 4 kB
    ``head`` window, and the sniff read only that window — so a real GSAS file
    was not claimed and fell to the ``xy`` catch-all, which read its
    fixed-format records as columns and refused with the wrong cause (a 2θ axis
    it never had, and only a misread column running backwards kept that from
    being a plausible *wrong pattern* instead).  The ``TIME_MAP`` token is
    GSAS-shaped evidence and does land in the window, so a file showing it earns
    one more bounded read to look past the table — the ``.chi`` count-check
    discipline, not a widened window for every file.
    """
    from rietx.io.formats.base import HEAD_BYTES
    p, bank_offset = _gsas_behind_long_time_map(
        tmp_path / "vnb.dat", table_rows=HEAD_BYTES // 80 + 30)
    assert bank_offset > HEAD_BYTES          # the fixture really is past-window
    assert identify_format(p).name == "gsas"


def test_a_time_map_bank_past_the_window_refuses_by_name_not_as_missing(tmp_path):
    """Once the sniff claims it, the bank is refused for *what it is* — a
    TIME_MAP flight-time bank — not as a 2θ-direction error (unfixed sniff, from
    ``xy``) and not as a missing BANK record.

    That last is why the bintype is read off a *loose* header match: a real
    TIME_MAP bank writes one coefficient where the strict CONS record parse
    needs two, so matching with that parse first skipped the bank and reported
    it absent — a file plainly holding a ``BANK`` record told it had none, and
    the by-name refusal #142 built never reached.
    """
    from rietx.io.formats.base import HEAD_BYTES
    p, _ = _gsas_behind_long_time_map(
        tmp_path / "vnb.dat", table_rows=HEAD_BYTES // 80 + 30)
    with pytest.raises(ValueError) as e:
        rx.read_pattern(p)
    msg = str(e.value)
    assert p.name in msg and "TIME_MAP" in msg
    assert "no BANK record" not in msg


def test_a_time_map_bank_writes_one_coefficient_and_is_refused_by_name(tmp_path):
    """The bintype gate must not depend on the CONS coefficient count — and this
    isolates that from the sniff, the bank sitting well inside the window.

    A real TIME_MAP bank writes a single coefficient (the map number), so the
    strict CONS record regex — a start angle and a step, two coefficients —
    never matched it, and the by-name refusal sat behind a match a TIME_MAP bank
    cannot make; before this it came back ``no BANK record found``.  The axis
    decision is taken off the bank *header*, which every bintype shares, for
    exactly this reason.
    """
    p = write_gsas(tmp_path / "onecoeff.gsa", bintype="TIME_MAP", flag="STD",
                   body="     100     200     300\n", nchan=3, coeffs=(1,))
    with pytest.raises(ValueError) as e:
        rx.read_pattern(p)
    assert p.name in str(e.value) and "TIME_MAP" in str(e.value)


def test_a_cons_bank_whose_record_will_not_parse_refuses_by_name(tmp_path):
    """The loose-header read has its own failure mode, and it must not fall back
    to the pre-existing lie.

    A ``CONS`` bank matching the *header* but not the record — the bintype is
    read, the two coefficients a CONS bank owes are absent — is now reachable
    precisely because the header match is a relaxation of the record match.  It
    raises naming the file rather than falling through to ``no BANK record
    found``, which is the same defect this module fixed one bintype over: a file
    plainly containing a ``BANK`` line told it has none.
    """
    p = write_gsas(tmp_path / "nocoeff.gsa", bintype="CONS", flag="STD",
                   body="     100     200     300\n", nchan=3, coeffs=())
    with pytest.raises(ValueError) as e:
        rx.read_pattern(p)
    msg = str(e.value)
    assert p.name in msg
    assert "no BANK record found" not in msg, (
        "the header matched, so the refusal must say the record could not be "
        "read rather than claim the file has no bank at all")


# ---------------------------------------------------------------------- ras
DATA = Path(__file__).parent / "data"


def write_ras(path, rows, *, axis="TwoThetaTheta", unit_y="counts",
              step=None, speed=None, speed_unit=None, comment=None, extra=()):
    """One-scan ``.ras`` bytes.  Text format, so a writer module would buy the
    round-trip nothing — the circularity the binary formats need it for is in
    packing *offsets*, and there are none here."""
    header = [f'*MEAS_SCAN_AXIS_X "{axis}"', f'*MEAS_SCAN_UNIT_Y "{unit_y}"']
    for key, value in (("MEAS_SCAN_STEP", step), ("MEAS_SCAN_SPEED", speed),
                       ("MEAS_SCAN_SPEED_UNIT", speed_unit),
                       ("FILE_COMMENT", comment)):
        if value is not None:
            header.append(f'*{key} "{value}"')
    header.extend(extra)
    body = ["*RAS_INT_START"]
    body += [" ".join(f"{v}" for v in row) for row in rows]
    body.append("*RAS_INT_END")
    lines = (["*RAS_DATA_START", "*RAS_HEADER_START", *header, "*RAS_HEADER_END"]
             + body + ["*RAS_DATA_END"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_the_real_scan_reads_and_carries_the_anode_its_header_names(tmp_path):
    """The fixture is a real SmartLab export (NIMS M-DaC_XRD, MIT), and what it
    proves that a synthetic file cannot is that these header keys are spelled
    the way an instrument actually spells them."""
    data = rx.read_pattern(DATA / "rigaku_nims.ras")

    assert identify_format(DATA / "rigaku_nims.ras").name == "ras"
    assert len(data.two_theta) == 3501
    assert (data.two_theta[0], data.two_theta[-1]) == (25.0, 60.0)
    assert data.metadata["anode"] == "Cu"
    assert data.metadata["wavelength"] == "1.540593"
    assert data.metadata["scan_count"] == "1"


def test_whole_counts_get_the_poisson_fallback_rather_than_an_invented_sigma():
    """``sigma is None`` is the *correct* answer here, not a missing one: the
    fallback √max(y,1) is exactly right for a raw count, and the file's
    intensities are integers to the last of 3501 points."""
    data = rx.read_pattern(DATA / "rigaku_nims.ras")

    assert data.sigma is None
    assert all(float(v).is_integer() for v in data.intensity)
    assert data.metadata["intensity_unit"] == "counts"      # and it agrees


def test_a_rate_gets_a_sigma_derived_from_the_counts_it_was_a_rate_of(tmp_path):
    """20 counts in 0.3 s is 66.6667 cps, and its σ is √20/0.3 — not √66.6667.
    The counting time comes from the header's own step and speed."""
    counts = [20, 31, 47, 53]
    t = 0.3
    p = write_ras(tmp_path / "rate.ras",
                  [(10.0 + 0.03 * i, round(c / t, 4)) for i, c in enumerate(counts)],
                  unit_y="cps", step=0.03, speed=6.0, speed_unit="deg/min")

    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.metadata["count_time_s"] == "0.3"
    assert data.sigma is not None
    for got, n in zip(data.sigma, counts):
        assert got == pytest.approx(n ** 0.5 / t, rel=1e-4)
    assert "PATTERN_INTENSITY_SCALED" not in [d.code for d in notes]


def test_the_speed_unit_is_read_because_deg_per_minute_is_not_deg_per_second(tmp_path):
    """The same numbers with the unit changed are a different counting time by a
    factor of 60, hence a σ wrong by √60. So the unit is read, and a header that
    does not state one leaves the time *unknown* rather than assumed."""
    rows = [(10.0 + 0.03 * i, round(c / 0.3, 4)) for i, c in enumerate([20, 31, 47, 53])]

    per_second = rx.read_pattern(write_ras(tmp_path / "s.ras", rows, unit_y="cps",
                                           step=0.03, speed=6.0, speed_unit="deg/sec"))
    unstated = rx.read_pattern(write_ras(tmp_path / "u.ras", rows, unit_y="cps",
                                         step=0.03, speed=6.0))

    # 0.005 s per step makes y·t nowhere near whole, so nothing is established
    assert per_second.sigma is None and unstated.sigma is None
    assert "count_time_s" not in unstated.metadata


def test_the_declared_intensity_unit_is_a_claim_and_does_not_decide_sigma(tmp_path):
    """Measured on real files: ``rigaku-xrd-analysis``'s ``example.ras`` declares
    counts and stores 84.3047, which no scale makes integral. Trusting the label
    there would apply √y to a quantity that is not a count, so the label is
    recorded and the arithmetic decides."""
    p = write_ras(tmp_path / "lying.ras",
                  [(10.0 + 0.004 * i, v) for i, v in
                   enumerate([84.3047, 84.1685, 73.4107, 75.6654])],
                  unit_y="counts", step=0.004, speed=2.0, speed_unit="deg/min")

    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.sigma is None
    assert data.metadata["intensity_unit"] == "counts"          # recorded verbatim
    scaled = [d for d in notes if d.code == "PATTERN_INTENSITY_SCALED"]
    assert len(scaled) == 1 and "0.12 s per step" in scaled[0].message


def test_a_rocking_curve_is_refused_rather_than_refined_as_a_pattern(tmp_path):
    """An ω scan is a real, common export whose points parse perfectly. Reading
    one as 2θ is the confident-wrong-cell class, so it is refused by name — the
    ``.chi`` axis policy one module over, applied to a header key."""
    p = write_ras(tmp_path / "rock.ras", [(15.55 + 0.004 * i, 84.0) for i in range(4)],
                  axis="Omega")

    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(p)
    assert "rock.ras" in str(refusal.value) and "rocking curve" in str(refusal.value)


def test_an_unrecognised_axis_is_read_as_two_theta_and_says_so(tmp_path):
    p = write_ras(tmp_path / "odd.ras", [(10.0 + i, 5.0) for i in range(4)],
                  axis="TwoThetaChi")

    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert len(data.two_theta) == 4
    assert [d.code for d in notes if d.code == "PATTERN_X_AXIS_ASSUMED"]
    assert "*MEAS_SCAN_AXIS_X" in notes[0].message


def test_a_scan_is_selected_never_concatenated(tmp_path):
    """Two passes generally differ in step and counting time, so merging them
    puts two weighting regimes in one residual. ``scan=`` picks; nothing joins."""
    path = DATA / "rigaku_multiscan.ras"

    first = rx.read_pattern(path, scan=0)
    second = rx.read_pattern(path, scan=1)

    assert first.two_theta == [10.0, 10.5, 11.0]
    assert second.two_theta == [20.0, 20.5, 21.0]
    assert second.metadata["scan"] == "1"
    assert second.metadata["scan_count"] == "2"


def test_the_defaulted_scan_says_so_on_a_real_multi_scan_file():
    notes: list = []
    rx.read_pattern(DATA / "rigaku_multiscan.ras", diagnostics=notes)
    chosen: list = []
    rx.read_pattern(DATA / "rigaku_multiscan.ras", scan=1, diagnostics=chosen)

    assert "PATTERN_MULTISCAN_DEFAULTED" in [d.code for d in notes]
    assert "PATTERN_MULTISCAN_DEFAULTED" not in [d.code for d in chosen]


def test_a_scan_the_file_does_not_have_is_refused_by_number():
    with pytest.raises(ValueError, match="holds 2 scan"):
        rx.read_pattern(DATA / "rigaku_multiscan.ras", scan=7)


def test_listing_scans_labels_them_with_what_the_file_calls_them():
    """A picker showing "Scan 0" and "Scan 1" has told the user nothing they did
    not already know."""
    scans = list_scans(DATA / "rigaku_multiscan.ras")

    assert [s.label for s in scans] == ["Low angle scan", "High angle scan"]
    assert [s.two_theta_range for s in scans] == [(10.0, 11.0), (20.0, 21.0)]
    assert [s.n_points for s in scans] == [3, 3]


def test_listing_scans_of_a_format_that_has_none_is_a_refusal_not_an_empty_list():
    """"This file has one scan" and "this format has no scan structure" are
    different answers, and only the second is true of a pdCIF."""
    with pytest.raises(ValueError, match="one measurement per file"):
        list_scans(DATA / "nist_srm660c_100a.cif")


def test_an_attenuator_column_is_reported_and_never_applied():
    """No specification states whether column 2 is already corrected for it, and
    applying it twice or not at all are both wrong — so the reader matches the
    convention the other codes use and says which points it affects."""
    notes: list = []
    data = rx.read_pattern(DATA / "rigaku_three_column.ras", diagnostics=notes)

    assert data.intensity == [250.0, 310.5, 480.2, 390.7]     # column 2, untouched
    found = [d for d in notes if d.code == "RAS_ATTENUATOR_PRESENT"]
    assert len(found) == 1
    assert "10–11.5" in found[0].message and found[0].where == ["intensity", "sigma"]


def test_choosing_a_scan_and_enumerating_them_are_two_halves_of_one_fact():
    """The biconditional: a format that lets a caller choose a scan must be able
    to say what there is to choose between, and one that cannot hold several has
    nothing to enumerate."""
    for fmt in PATTERN_FORMATS:
        assert ("scan" in fmt.options) == (fmt.scans is not None), fmt.name


def test_every_key_a_reader_writes_is_one_the_vocabulary_declares():
    """Two consumers *match* on these keys — the wizard's anode pre-selection and
    the scan count in a preview — and neither can match on a name each reader
    spells for itself."""
    for fixture in ("rigaku_nims.ras", "11BM_NAC.fxye", "qarr/corundum.prn",
                    "nist_srm660c_100a.cif"):
        keys = set(rx.read_pattern(DATA / fixture).metadata)
        assert keys <= set(METADATA_KEYS), (fixture, keys - set(METADATA_KEYS))
    assert all(prose for prose in METADATA_KEYS.values())

    with pytest.raises(ValueError, match="undeclared pattern metadata key"):
        metadata(source_file="a.ras", detector_serial="XYZ")


def test_the_schema_is_a_parser_boundary_like_any_other(tmp_path):
    """A ``PatternData`` validator is the last boundary a reader crosses, and its
    refusal must name the file like every other one.

    Found by the truncation harness rather than by reading: a ``.XRA`` cut short
    enough to lose its ``BANK`` record fell through to ``xy``, parsed one point,
    and raised pydantic's report — which passed "the refusal names the file"
    only because pydantic *echoed* the metadata dict, filename included. One
    more metadata key pushed the name past that echo's truncation and the
    invariant failed, having never held.
    """
    p = write_xy(tmp_path / "onepoint.xy", [15.0], [3.0])

    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(p)
    message = str(refusal.value)
    assert "onepoint.xy" in message and "at least 2 points" in message
    assert "pydantic" not in message and "validation error" not in message


# --------------------------------------------------------------- philips rd
def test_a_philips_rd_reproduces_its_own_prn_conversion_bit_for_bit():
    """The strongest claim any binary reader here makes, and it is available
    only because the IUCr CPD kit publishes the *same scans* in two formats:
    ``qarr/corundum.rd`` is the original logged file and ``qarr/corundum.prn``
    is a conversion of it that this repo already committed for the QPA
    acceptance.  So the oracle is independent of everything in this module."""
    rd = rx.read_pattern(DATA / "qarr" / "corundum.rd")
    prn = rx.read_pattern(DATA / "qarr" / "corundum.prn")

    assert rd.intensity == prn.intensity          # all 7251, exactly
    assert rd.two_theta == pytest.approx(prn.two_theta, abs=5e-10)
    assert rx.io.readers.identify_format(DATA / "qarr" / "corundum.rd").name \
        == "philips_rd"


def test_the_rd_intensities_are_root_compressed_not_raw():
    """Read raw, the ``uint16`` gives a profile with every peak in the right
    place and every intensity wrong — the failure no reader can see in its own
    output.  The gap is large and one-directional, so this cannot pass by
    accident: the raw maximum is 829 where the count is 6872."""
    import numpy as np

    raw = np.frombuffer((DATA / "qarr" / "corundum.rd").read_bytes(),
                        dtype="<u2", count=7251, offset=250).astype(np.int64)
    data = rx.read_pattern(DATA / "qarr" / "corundum.rd")

    assert raw.max() == 829
    assert max(data.intensity) == 6872.0
    assert data.intensity == [float(v * v // 100) for v in raw]


def test_the_two_prn_converters_disagree_by_one_count_on_exactly_one_file():
    """``qarr/cpd-1e.rd`` is committed because it is the exception, and the
    fixture exists so a successor does not "fix" the reader to chase it: the
    kit's ``.prn`` converter truncates on fifteen files and this one's rounds.
    The reader truncates — what xylib and the other fifteen conversions do — so
    this file is off by exactly one count where the rounding differs, and by
    nothing anywhere else."""
    rd = rx.read_pattern(DATA / "qarr" / "cpd-1e.rd")
    prn = rx.read_pattern(DATA / "qarr" / "cpd-1e.prn")

    off = [b - a for a, b in zip(rd.intensity, prn.intensity) if a != b]
    assert set(off) == {1.0}
    assert len(off) == 2108


def test_a_philips_rd_reports_the_anode_it_states_twice():
    """The anode is the one enumerated code with a consumer, and decoding it
    makes the file say ``Cu`` twice — once as the code at offset 85 and once as
    λα1 — which is what lets ``suggest_instrument`` resolve by agreement."""
    from rietx.gui.imports import suggest_instrument

    data = rx.read_pattern(DATA / "qarr" / "corundum.rd")

    assert data.metadata["anode"] == "Cu"
    assert data.metadata["wavelength"] == "1.540562"
    assert data.metadata["sample"] == "CPD RR Corundum"
    assert suggest_instrument(data.metadata)["radiation"] == "CuKa"


def test_a_wrong_data_offset_is_caught_by_the_maximum_value_field(tmp_path):
    """Offset 136 holds ``max(v)`` in all 28 real files and is in no published
    description.  It is the sharpest of the three gates because a ``.rd`` read
    at the wrong offset still *looks* like a diffraction pattern."""
    from tests.writers_xrd import CORUNDUM_HEAD, write_philips_rd

    p = write_philips_rd(tmp_path / "lying.rd", CORUNDUM_HEAD, stated_max=999)

    with pytest.raises(ValueError, match="records a maximum stored value of 999"):
        rx.read_pattern(p)


def test_a_length_that_disagrees_with_the_header_is_refused(tmp_path):
    from tests.writers_xrd import CORUNDUM_HEAD, write_philips_rd

    p = write_philips_rd(tmp_path / "short.rd", CORUNDUM_HEAD, end=99.0)

    with pytest.raises(ValueError, match=r"short\.rd is V3RD.*should be"):
        rx.read_pattern(p)


def test_bytes_past_the_last_point_are_refused(tmp_path):
    """Same gate from the other side: the header says how long the file is."""
    from tests.writers_xrd import CORUNDUM_HEAD, write_philips_rd

    p = write_philips_rd(tmp_path / "trailing.rd", CORUNDUM_HEAD,
                         trailing=b"\x01\x02")

    with pytest.raises(ValueError, match="and it is"):
        rx.read_pattern(p)


def test_a_v5_reads_only_when_the_length_gate_holds(tmp_path):
    """V5 has no real file anywhere and its data offset rests on one description
    copied twice.  It is read because ``n`` comes from the header, so
    ``len == 810 + 2n`` tests the header offsets and the data start jointly and
    a wrong 810 cannot shift the pattern silently.  The refusal says so."""
    from tests.writers_xrd import CORUNDUM_HEAD, write_philips_rd

    counts = CORUNDUM_HEAD
    good = write_philips_rd(tmp_path / "good.sd", counts, version=b"V5RD")

    assert rx.read_pattern(good).intensity == [float(c) for c in counts]

    # the same bytes claiming to be V5 with a V3-sized header: 560 bytes short
    v3 = write_philips_rd(tmp_path / "mislabelled.sd", counts)
    raw = bytearray(v3.read_bytes())
    raw[:4] = b"V5RD"
    (tmp_path / "mislabelled.sd").write_bytes(bytes(raw))

    with pytest.raises(ValueError, match="No V5 file was obtainable anywhere"):
        rx.read_pattern(tmp_path / "mislabelled.sd")


def test_a_damaged_angle_triple_is_refused_by_name_not_by_overflow(tmp_path):
    """The three doubles at offset 214 are bytes like any other, and a damaged
    header can hold a denormal step or an infinity.  ``round()`` answers those
    with an ``OverflowError`` that names neither the file nor the field — and
    ``OverflowError`` is outside every caller's allowlist, so it reaches the GUI
    import route as a 500 rather than as a refusal."""
    import struct

    for step, start, end in ((5e-324, 5.0, 50.0),       # span overflows
                             (0.02, 5.0, float("inf")),  # so does the range
                             (float("nan"), 5.0, 50.0)):
        buf = bytearray(b"\x00" * 300)
        buf[0:4] = b"V3RD"
        buf[214:238] = struct.pack("<3d", step, start, end)
        p = tmp_path / f"damaged_{step:g}_{end:g}.rd"
        p.write_bytes(bytes(buf))

        with pytest.raises(ValueError, match="which is not a scan"):
            rx.read_pattern(p)


def test_philips_rd_and_bruker_raw_are_disjoint_in_both_directions(tmp_path):
    """``.raw`` is written by six unrelated vendors and ``.rd`` by two, so
    neither reader may trust a suffix.  Both match on magic bytes, so a Philips
    file named ``.raw`` still reaches this reader and a Bruker file named
    ``.rd`` still reaches that one."""
    from tests.writers_xrd import CORUNDUM_HEAD, write_philips_rd, write_raw4

    philips = write_philips_rd(tmp_path / "philips.raw", CORUNDUM_HEAD)
    bruker = write_raw4(tmp_path / "bruker.rd", [
        dict(start=10.0, step=0.02, intensity=[500.0 + i % 7 for i in range(50)])])

    assert rx.io.readers.identify_format(philips).name == "philips_rd"
    assert rx.io.readers.identify_format(bruker).name == "bruker_raw"


# ---------------------------------------------------------------------- udf
#: The 19 keys every one of the 56 real ``.udf`` files carries, in their order,
#: with the values an ASU PANalytical Aeris wrote on 3 June 2025.  No real file
#: can be vendored — all three repositories holding them declare no licence — so
#: the header is reproduced as *facts read off them* (`tests/data/README.md`
#: § Philips has the table) and the tests below synthesize from it.
AERIS_HEADER = [
    ("SampleIdent", "2025_06_03_CeO2_3_60_8min"),
    ("Title1", "CeO2 Standard"),
    ("Title2", ""),
    ("DiffrType", "?"),
    ("DiffrNumber", "1"),
    ("Anode", "Cu"),
    ("LabdaAlpha1", " 1.540598"),
    ("LabdaAlpha2", " 1.544426"),
    ("RatioAlpha21", " 0.50000"),
    ("DivergenceSlit", "Fixed, 1/2"),
    ("ReceivingSlit", "UNDEFINED"),
    ("MonochromatorUsed", "NO"),
    ("GeneratorVoltage", "  40"),
    ("TubeCurrent", "  15"),
    ("FileDateTime", "03-jun-2025 15:55"),
    ("ScanType", "CONTINUOUS"),
    ("ScanStepTime", " 18.87"),
]

#: PyXRD's own inline UDF test data, verbatim under **BSD-2** — the one
#: vendorable fixture this format has.  Unlike its ``.rd`` sibling it is valid
#: as committed: UDF is plain ASCII, so the raw-string prefix does it no harm.
#: It carries **5** of the 19 keys, and ends its block ``0/`` where every real
#: file ends ``425,/``, which is the evidence that the comma is optional.
PYXRD_UDF_FIXTURE = """SampleIdent,Sample5 ,/
Title1,Dat2rit program ,/
Title2,Sample5 ,/
DataAngleRange,   5.0000, 5.6400,/
ScanStepSize,     0.020,/
RawScan
    8000,    7000,    6000,    5000,    4000,    3000,    2000,    1000
    800,     700,     600,     500,     400,     300,     200,     100
    80,      70,      60,      50,      40,      30,      20,      10
    8,       7,       6,       5,       4,       3,       2,       1
    0/"""


def write_udf(path, values, *, lo=3.00043, step=0.01086644,
              hi=None, header=AERIS_HEADER, marker="RawScan", comma=True):
    """A ``.udf`` in the real files' shape: 19 keys, a marker, eight per line.

    ``hi`` defaults to the end angle the range and step imply, so a caller that
    wants the two to *disagree* has to say so — which is the gate under test.
    """
    hi = lo + step * (len(values) - 1) if hi is None else hi
    lines = [f"{k},{v},/" for k, v in header]
    lines += [f"DataAngleRange, {lo:9.5f}, {hi:9.5f},/",
              f"ScanStepSize, {step:.11f},/", marker]
    rows = [values[i:i + 8] for i in range(0, len(values), 8)]
    body = [",".join(f"{v:8.0f}" for v in row) for row in rows]
    path.write_text("\n".join(lines) + "\n" + ",\n".join(body)
                    + ("," if comma else "") + "/\n", encoding="utf-8")
    return path


def test_a_udf_reconstructs_its_axis_and_reports_what_the_header_knows(tmp_path):
    """The abscissa is not stored: it is ``DataAngleRange`` plus ``ScanStepSize``."""
    counts = [3819, 3775, 3890, 3829, 3764, 3811, 3894, 3752, 3827, 3784]
    p = write_udf(tmp_path / "aeris.udf", counts)

    data = rx.read_pattern(p)

    assert rx.io.readers.identify_format(p).name == "udf"
    assert len(data.two_theta) == 10
    assert data.two_theta[0] == pytest.approx(3.00043)
    assert data.two_theta[1] - data.two_theta[0] == pytest.approx(0.01086644)
    assert data.intensity == [float(c) for c in counts]
    assert data.metadata["anode"] == "Cu"
    assert data.metadata["wavelength"] == "1.540598"
    assert data.metadata["wavelength_alpha2"] == "1.544426"
    # whole numbers are counts, whose σ is the package's Poisson fallback
    assert data.sigma is None


def test_a_udf_value_may_contain_commas_so_a_line_splits_on_the_first_only(tmp_path):
    """``DivergenceSlit,Fixed, 1/2,/`` is two fields and ``Title1`` runs to ten
    in the real corpus.  Splitting on every comma is the obvious parse and would
    make the title ``CeO2`` and the slit ``Fixed``."""
    header = [(k, v) for k, v in AERIS_HEADER if k != "Title1"]
    header.insert(1, ("Title1", "CBN - Sorbic Acid, Slurry, Heptane, 5/9/25, JL"))
    p = write_udf(tmp_path / "commas.udf", [10, 20, 30, 40], header=header)

    data = rx.read_pattern(p)

    assert data.metadata["title"] == "CBN - Sorbic Acid, Slurry, Heptane, 5/9/25, JL"


def test_an_empty_udf_value_is_a_present_key_not_an_absent_one(tmp_path):
    """``Title2,,/`` occurs in nearly every real file."""
    p = write_udf(tmp_path / "empty.udf", [10, 20, 30, 40])

    data = rx.read_pattern(p)

    # Title2 is empty in AERIS_HEADER and no metadata key claims it; what the
    # test pins is that the *parse* survived it and the next keys still landed
    assert data.metadata["sample"] == "2025_06_03_CeO2_3_60_8min"
    assert "title" in data.metadata


def test_a_udf_whose_two_length_statements_disagree_is_refused(tmp_path):
    """The file says how long it is twice — a range plus a step, and a count of
    values — and the two agree in all 56 real files.  A disagreement puts the 2θ
    of *every* point in doubt, so it is a contradiction and not a repair."""
    p = write_udf(tmp_path / "short.udf", [10, 20, 30, 40], hi=3.1)

    with pytest.raises(ValueError, match=r"short\.udf.*points.*data block holds 4"):
        rx.read_pattern(p)


def test_a_udf_step_that_is_not_a_number_is_refused_by_name(tmp_path):
    """``DataAngleRange`` and ``ScanStepSize`` are free text, so ``nan`` and
    ``inf`` parse as floats and a denormal step overflows the point count.
    ``round()`` refuses all three without naming the file — an ``OverflowError``
    on the infinities, a bare ``ValueError`` on the NaN — so the scan gate asks
    for a finite span rather than only for a positive one."""
    for step in ("5e-324", "nan", "inf"):
        p = tmp_path / f"bad_{step}.udf"
        p.write_text(f"DataAngleRange, 5.0, 50.0,/\nScanStepSize, {step},/\n"
                     "RawScan\n1,2,3,/\n", encoding="utf-8")

        with pytest.raises(ValueError, match="do not describe a scan"):
            rx.read_pattern(p)


def test_the_terminating_comma_is_optional(tmp_path):
    """Every real file ends ``425,/``; PyXRD's vendorable fixture ends ``0/``."""
    a = write_udf(tmp_path / "with.udf", [10, 20, 30, 40], comma=True)
    b = write_udf(tmp_path / "without.udf", [10, 20, 30, 40], comma=False)

    assert rx.read_pattern(a).intensity == rx.read_pattern(b).intensity


def test_the_vendorable_pyxrd_fixture_parses_on_five_keys(tmp_path):
    """It carries 5 of the 19 keys, so the reader must require only the two that
    make an abscissa — a vocabulary check would reject the one file that ships."""
    p = tmp_path / "pyxrd.udf"
    p.write_text(PYXRD_UDF_FIXTURE, encoding="utf-8")

    data = rx.read_pattern(p)

    assert rx.io.readers.identify_format(p).name == "udf"
    assert len(data.two_theta) == 33
    assert data.two_theta[0] == pytest.approx(5.0)
    assert data.two_theta[-1] == pytest.approx(5.64)
    assert data.intensity[0] == 8000.0 and data.intensity[-1] == 0.0
    assert "anode" not in data.metadata


def test_a_udf_derives_no_counting_time_from_scan_step_time(tmp_path):
    """``ScanStepTime`` is not seconds per step on a PIXcel-class detector: the
    Aeris writes 18.87 for a scan its own name calls eight minutes over 5246
    points.  Recording it as ``count_time_s`` would make every derived σ wrong."""
    p = write_udf(tmp_path / "time.udf", [10, 20, 30, 40])

    assert "count_time_s" not in rx.read_pattern(p).metadata


def test_a_udf_with_scaled_intensities_withholds_sigma_and_says_so(tmp_path):
    """The format declares no intensity unit, so arithmetic is all there is."""
    p = tmp_path / "rate.udf"
    header = "\n".join(f"{k},{v},/" for k, v in AERIS_HEADER)
    p.write_text(header + "\nDataAngleRange,   3.00000,   3.06000,/\n"
                 "ScanStepSize, 0.02000,/\nRawScan\n"
                 "  3.5,  4.25,  5.75,  6.5,/\n", encoding="utf-8")

    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.sigma is None
    assert [n.code for n in notes] == ["PATTERN_INTENSITY_SCALED"]


def test_a_udf_seeds_the_instrument_hint_without_the_three_candidate_guess(tmp_path):
    """The header states the anode *and* both wavelengths exactly, so the hint
    resolves by agreement rather than by matching λ against Kα1/Kα2/weighted
    mean.  This is why ``RatioAlpha21`` earns no ``METADATA_KEYS`` entry: the
    CuKa preset already carries the 0.5 every real file states, so a declared
    key would have no consumer (WP-1076)."""
    from rietx.gui.imports import suggest_instrument

    p = write_udf(tmp_path / "hint.udf", [10, 20, 30, 40])

    hint = suggest_instrument(rx.read_pattern(p).metadata)

    assert hint["radiation"] == "CuKa"
    assert "anode and wavelength agreeing" in hint["why"]


# ---------------------------------------------------------------------- uxd
def write_uxd(path, ranges, *, anode="Cu", wl1=1.540600, radius=250.0):
    """A ``.uxd`` of one or more ranges.  No real ``.uxd`` could be vendored —
    the only obtainable ones are GPL or carry no licence at all — so these are
    synthesized, and every structural claim they make was verified against a
    real file first (`tests/data/README.md` names which)."""
    lines = ["; written by tests", "_FILEVERSION=2", f"_ANODE='{anode}'",
             f"_WL1={wl1:.6f}", f"_GONIOMETER_RADIUS={radius:.6f}"]
    for n, r in enumerate(ranges, start=1):
        lines.append(f"; (Data for Range number {n})")
        lines.append(f"_DRIVE='{r['drive']}'")
        for key in ("STEPTIME", "STEPSIZE", "START", "2THETA"):
            if key.lower() in r:
                lines.append(f"_{key}={r[key.lower()]:.6f}")
        lines.append(r["marker"])
        for row in r["rows"]:
            lines.append("   " + "      ".join(f"{v}" for v in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_the_block_marker_is_read_as_two_facts_not_looked_up_as_a_name(tmp_path):
    """``_2THETA`` means "there is a position column"; ``COUNTS``/``CPS`` is the
    unit.  Independent, so the four spellings are two bits rather than a table."""
    counts = [3, 5, 8, 6]
    paired = write_uxd(tmp_path / "paired.uxd", [dict(
        drive="COUPLED", marker="_2THETACOUNTS", steptime=1.0,
        rows=[(10.0 + 0.02 * i, c) for i, c in enumerate(counts)])])
    implied = write_uxd(tmp_path / "implied.uxd", [dict(
        drive="COUPLED", marker="_COUNTS", steptime=1.0, stepsize=0.02,
        start=10.0, rows=[(c,) for c in counts])])

    a, b = rx.read_pattern(paired), rx.read_pattern(implied)
    assert a.two_theta == pytest.approx(b.two_theta)     # start + i·step
    assert a.intensity == b.intensity == [3.0, 5.0, 8.0, 6.0]
    assert a.metadata["intensity_unit"] == "counts" and a.sigma is None


def test_a_cps_block_gets_its_sigma_from_steptime(tmp_path):
    """Structural, so it is trusted: unlike ``.ras``'s free-text unit field, the
    unit here is the token that opens the block and cannot disagree with it."""
    p = write_uxd(tmp_path / "rate.uxd", [dict(
        drive="COUPLED", marker="_2THETACPS", steptime=4.0,
        rows=[(10.0 + 0.02 * i, c / 4.0) for i, c in enumerate([12, 20, 33, 41])])])

    data = rx.read_pattern(p)

    assert data.metadata["intensity_unit"] == "cps"
    assert data.metadata["count_time_s"] == "4.0"
    for got, n in zip(data.sigma, [12, 20, 33, 41]):
        assert got == pytest.approx(n ** 0.5 / 4.0, rel=1e-9)


def test_a_cps_block_without_a_steptime_withholds_sigma_and_says_so(tmp_path):
    p = write_uxd(tmp_path / "nortime.uxd", [dict(
        drive="COUPLED", marker="_2THETACPS",
        rows=[(10.0 + 0.02 * i, 3.5 * i + 1) for i in range(4)])])

    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.sigma is None
    assert [d.code for d in notes] == ["PATTERN_INTENSITY_SCALED"]


def test_the_drive_decides_the_axis_because_the_marker_name_lies(tmp_path):
    """The finding this reader is built around: a rocking curve and a pole figure
    are both stored under a marker called ``_2THETACOUNTS``. Four of the five
    real ``.uxd`` files read while writing this are not 2θ scans at all."""
    rocking = write_uxd(tmp_path / "rock.uxd", [dict(
        drive="THETA", marker="_2THETACOUNTS", steptime=1.0,
        rows=[(-1.0 + 0.04 * i, 100) for i in range(4)])])

    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(rocking)
    assert "rock.uxd" in str(refusal.value) and "rocking curve" in str(refusal.value)
    assert "_2THETACOUNTS" in str(refusal.value)     # the trap, named in the refusal


def test_a_detector_scan_reads_because_two_theta_is_what_it_steps(tmp_path):
    p = write_uxd(tmp_path / "det.uxd", [dict(
        drive="2THETA", marker="_2THETACOUNTS", steptime=1.0,
        rows=[(10.0 + 0.02 * i, 100 + i) for i in range(4)])], radius=350.0)

    data = rx.read_pattern(p)

    assert data.metadata["scan_axis"] == "2THETA"
    assert data.metadata["goniometer_radius_mm"] == "350.0"


def test_ranges_of_different_counting_time_are_selected_never_joined(tmp_path):
    """Not academic: one real 153-range file carries ``_STEPTIME`` of both 2 s
    and 20 s. Concatenating those puts measurements a factor of ten apart in
    counting statistics under one Poisson assumption."""
    p = write_uxd(tmp_path / "two.uxd", [
        dict(drive="COUPLED", marker="_2THETACOUNTS", steptime=2.0,
             rows=[(10.0 + 0.1 * i, 40 + i) for i in range(4)]),
        dict(drive="COUPLED", marker="_2THETACOUNTS", steptime=20.0,
             rows=[(20.0 + 0.1 * i, 400 + i) for i in range(4)]),
    ])

    notes: list = []
    first = rx.read_pattern(p, diagnostics=notes)
    second = rx.read_pattern(p, scan=1)

    assert first.two_theta[0] == 10.0 and second.two_theta[0] == 20.0
    assert first.metadata["count_time_s"] == "2.0"
    assert second.metadata["count_time_s"] == "20.0"
    assert "PATTERN_MULTISCAN_DEFAULTED" in [d.code for d in notes]
    assert [s.label for s in list_scans(p)] == ["COUPLED 10–10.3°", "COUPLED 20–20.3°"]


def test_counts_with_no_position_column_and_no_step_is_refused(tmp_path):
    """``_COUNTS`` puts the whole x axis in ``_START`` and ``_STEPSIZE``. Without
    them there is no axis — and a default step of 1 would be an invented one."""
    p = write_uxd(tmp_path / "bare.uxd", [dict(
        drive="COUPLED", marker="_COUNTS", steptime=1.0,
        rows=[(c,) for c in (3, 5, 8, 6)])])

    with pytest.raises(ValueError, match="no 2θ axis to read"):
        rx.read_pattern(p)


def test_an_unknown_block_marker_is_named_rather_than_skipped(tmp_path):
    p = tmp_path / "odd.uxd"
    p.write_text("_FILEVERSION=2\n_DRIVE='COUPLED'\n_INTENSITIES\n10.0 5\n11.0 6\n",
                 encoding="utf-8")

    with pytest.raises(ValueError, match="_INTENSITIES"):
        rx.read_pattern(p)


# -------------------------------------------------------------------- xrdml
#: FAIRmat's own reader output for the same file, vendored beside it — an
#: independent implementation's answer, which is what makes it an oracle rather
#: than a transcription of ours.  It records array *shapes* and the header
#: metadata; the intensities themselves it does not carry.
def _oracle(stem: str) -> dict:
    import json

    return json.loads((DATA / f"{stem}.json").read_text(encoding="utf-8"))


def test_the_real_powder_scan_matches_its_independent_oracle():
    """Every field the oracle carries, against the reader — not a sample of them.

    The oracle is FAIRmat's ``readers-xrd`` output for this exact file
    (Apache-2.0, vendored with it), so agreement is a cross-implementation
    check on the element paths, not a round-trip through our own understanding.
    """
    oracle = _oracle("panalytical_powder.xrdml")
    data = rx.read_pattern(DATA / "panalytical_powder.xrdml")

    assert len(data.two_theta) == int(oracle["2Theta"].strip("(),"))
    assert len(data.intensity) == int(oracle["intensity"].strip("(),"))
    assert data.metadata["scan_axis"] == oracle["metadata"]["scan_axis"]
    assert data.metadata["anode"] == oracle["metadata"]["source"]["anode_material"]
    assert float(data.metadata["wavelength"]) == float(
        oracle["metadata"]["source"]["kAlpha1"])
    assert float(data.metadata["wavelength_alpha2"]) == float(
        oracle["metadata"]["source"]["kAlpha2"])
    assert data.metadata["scan_count"] == "1"
    # not in the oracle, and the reason the reader bothers: two of the four
    # bragg_brentano numbers need not be typed when the file already knows them
    assert data.metadata["goniometer_radius_mm"] == "240.0"


def test_raw_counts_get_no_sigma_because_the_poisson_fallback_is_right():
    """``sigma=None`` here is the *correct* answer, not a missing one — the
    stored values are the detector's own integers."""
    data = rx.read_pattern(DATA / "panalytical_powder.xrdml")

    assert data.sigma is None
    assert data.metadata["intensity_unit"] == "counts"
    assert all(float(v).is_integer() for v in data.intensity)


def test_the_beam_attenuator_is_applied_and_sigma_goes_through_it():
    """The finding this reader is built around, on the file that established it.

    A single point of the GaAs 004 substrate reflection was measured behind a
    188× foil, and the raw series *dips* there — 1341, 14602, **1877**, 13749 —
    which is the attenuation and not a profile.  So the stored counts are the
    attenuated ones, the reported intensity is their product, and σ is
    √counts·a rather than √y: the case GSAS-II gets wrong by weighting 1/y.
    """
    notes: list = []
    data = rx.read_pattern(DATA / "panalytical_attenuator.xrdml", diagnostics=notes)

    apex = max(range(len(data.intensity)), key=lambda i: data.intensity[i])
    assert data.intensity[apex] == 1877.0 * 188.0
    assert data.intensity[apex - 1] == 14602.0 and data.intensity[apex + 1] == 13749.0
    assert data.sigma is not None
    assert data.sigma[apex] == pytest.approx(1877.0 ** 0.5 * 188.0)
    # and nowhere else: an unattenuated point's σ is what the fallback would be
    assert data.sigma[apex - 1] == pytest.approx(14602.0 ** 0.5)
    assert [d.code for d in notes] == ["XRDML_ATTENUATOR_APPLIED"]
    assert "66.1" in notes[0].message and "188" in notes[0].message


def test_a_reciprocal_space_map_is_scans_and_says_which_one_it_read():
    """101 scans in one file, so the default is a choice and is never silent."""
    notes: list = []
    data = rx.read_pattern(DATA / "panalytical_mesh.xrdml", diagnostics=notes)

    assert data.metadata["scan_count"] == "101"
    assert data.metadata["scan"] == "0"
    assert [d.code for d in notes] == ["PATTERN_MULTISCAN_DEFAULTED"]
    assert rx.read_pattern(DATA / "panalytical_mesh.xrdml",
                           scan=100).metadata["scan"] == "100"


def test_a_stack_of_identical_ranges_is_labelled_by_what_differs():
    """``ScanInfo.label`` may not be invented, and "2Theta 67.45–69.95°" a
    hundred and one times tells a picker nothing.  What separates the scans is
    the axis each was fixed at, which is knowable only across the whole list."""
    scans = list_scans(DATA / "panalytical_mesh.xrdml")

    assert len(scans) == 101
    assert len({s.label for s in scans}) == 101
    assert all("Omega" in s.label for s in scans)
    assert all(s.n_points == 255 for s in scans)


def test_the_position_list_form_is_read_as_written():
    """Three forms exist and the mesh uses the third: 2θ written out per point
    rather than as a start and an end."""
    data = rx.read_pattern(DATA / "panalytical_mesh.xrdml", scan=0)

    assert len(data.two_theta) == 255
    assert data.two_theta[0] == pytest.approx(67.45053915)
    assert data.two_theta[-1] == pytest.approx(69.95146085)


def test_both_schema_versions_are_claimed_because_nothing_matches_the_namespace():
    """1.6 and 2.1 are both current in the wild; keying on either would refuse
    half the files a lab owns."""
    versions = set()
    for stem in ("panalytical_powder", "panalytical_attenuator", "panalytical_mesh"):
        path = DATA / f"{stem}.xrdml"
        assert identify_format(path).name == "xrdml"
        versions.add(path.read_text(encoding="utf-8")
                     .split('xmlns="', 1)[1].split('"', 1)[0])
    assert len(versions) == 2


def write_xrdml(path: Path, *, scan_axis="Gonio", start=10.0, end=13.0,
                counts=(10, 20, 30, 40), element="counts", unit="counts",
                attenuation=None, count_time="1.0", root="xrdMeasurements",
                namespace="http://www.xrdml.com/XRDMeasurement/2.1") -> Path:
    """A minimal but schema-shaped ``.xrdml`` — for the cases no fixture holds."""
    attn = ("" if attenuation is None else
            f"<beamAttenuationFactors>{' '.join(map(str, attenuation))}"
            "</beamAttenuationFactors>")
    time = "" if count_time is None else (
        f'<commonCountingTime unit="seconds">{count_time}</commonCountingTime>')
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<{root} xmlns="{namespace}">'
        f'<sample><id>S1</id><name></name></sample>'
        f'<xrdMeasurement measurementType="Scan">'
        f'<usedWavelength><kAlpha1 unit="Angstrom">1.5405980</kAlpha1>'
        f'<kAlpha2 unit="Angstrom">1.5444260</kAlpha2></usedWavelength>'
        f'<incidentBeamPath><radius unit="mm">240.00</radius>'
        f'<xRayTube><anodeMaterial>Cu</anodeMaterial></xRayTube>'
        f'</incidentBeamPath>'
        f'<scan scanAxis="{scan_axis}" status="Completed"><dataPoints>'
        f'<positions axis="2Theta" unit="deg">'
        f'<startPosition>{start}</startPosition>'
        f'<endPosition>{end}</endPosition></positions>'
        f'{time}{attn}'
        f'<{element} unit="{unit}">{" ".join(map(str, counts))}</{element}>'
        f'</dataPoints></scan></xrdMeasurement></{root}>',
        encoding="utf-8")
    return path


def test_a_rocking_curve_is_refused_by_the_axis_it_names(tmp_path):
    p = write_xrdml(tmp_path / "rock.xrdml", scan_axis="Omega")

    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(p)
    assert "rock.xrdml" in str(refusal.value)
    assert "rocking curve" in str(refusal.value)


def test_a_rate_gets_a_derived_sigma_from_the_files_own_counting_time(tmp_path):
    p = write_xrdml(tmp_path / "rate.xrdml", element="intensities", unit="cps",
                    counts=(10.0, 20.0, 30.0, 40.0), count_time="4.0")

    data = rx.read_pattern(p)

    assert data.sigma is not None
    assert data.sigma[0] == pytest.approx((10.0 * 4.0) ** 0.5 / 4.0)
    assert data.metadata["count_time_s"] == "4.0"


def test_a_rate_with_no_counting_time_withholds_sigma_and_says_why(tmp_path):
    p = write_xrdml(tmp_path / "bare.xrdml", element="intensities", unit="cps",
                    count_time=None)

    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.sigma is None
    assert [d.code for d in notes] == ["PATTERN_INTENSITY_SCALED"]
    assert "<commonCountingTime>" in notes[0].message


def test_a_fixed_two_theta_is_not_a_pattern_however_the_scan_axis_is_spelled(
        tmp_path):
    """``scanAxis`` can say ``Gonio`` on a scan whose 2θ never moved — a φ or χ
    scan written by software that did not update the attribute.  The positions
    are the authority when they contradict it."""
    p = tmp_path / "fixed.xrdml"
    p.write_text(
        '<?xml version="1.0"?><xrdMeasurements '
        'xmlns="http://www.xrdml.com/XRDMeasurement/2.1"><xrdMeasurement>'
        '<scan scanAxis="Gonio"><dataPoints>'
        '<positions axis="2Theta"><commonPosition>33.0</commonPosition></positions>'
        '<positions axis="Phi"><startPosition>0</startPosition>'
        '<endPosition>90</endPosition></positions>'
        '<counts unit="counts">1 2 3 4</counts>'
        '</dataPoints></scan></xrdMeasurement></xrdMeasurements>', encoding="utf-8")

    with pytest.raises(ValueError, match="single fixed position"):
        rx.read_pattern(p)


def test_a_position_list_that_disagrees_with_the_data_is_refused(tmp_path):
    p = tmp_path / "short.xrdml"
    p.write_text(
        '<?xml version="1.0"?><xrdMeasurements '
        'xmlns="http://www.xrdml.com/XRDMeasurement/2.1"><xrdMeasurement><scan '
        'scanAxis="2Theta"><dataPoints><positions axis="2Theta">'
        '<listPositions>10 11 12</listPositions></positions>'
        '<counts unit="counts">1 2 3 4</counts>'
        '</dataPoints></scan></xrdMeasurement></xrdMeasurements>', encoding="utf-8")

    with pytest.raises(ValueError, match="3 positions for 4"):
        rx.read_pattern(p)


def test_xml_that_is_not_an_xrdml_is_not_claimed_by_this_reader(tmp_path):
    """The sniff is the **root element**, not the suffix: a `.xrdml`-named
    something-else keeps falling down the registry rather than being parsed as a
    measurement it is not.  It lands on the text catch-all, which refuses it by
    name — which is the whole point of the catch-all being a reader and not a
    fallback that guesses."""
    p = tmp_path / "other.xrdml"
    p.write_text('<?xml version="1.0"?><plotData><x>1</x></plotData>',
                 encoding="utf-8")

    assert identify_format(p).name == "xy"
    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(p)
    assert "other.xrdml" in str(refusal.value)


def test_a_prefixed_root_element_is_still_claimed(tmp_path):
    """A default namespace is what the real files use, but a prefix is legal —
    and a sniff that reads ``<x:xrdMeasurements>`` as an element named ``x`` is
    the kind of near-miss that shows up only on somebody else's export."""
    p = tmp_path / "prefixed.xrdml"
    p.write_text('<?xml version="1.0"?><x:xrdMeasurements '
                 'xmlns:x="http://www.xrdml.com/XRDMeasurement/1.6">'
                 '<x:xrdMeasurement><x:scan scanAxis="Gonio"><x:dataPoints>'
                 '<x:positions axis="2Theta"><x:startPosition>10</x:startPosition>'
                 '<x:endPosition>13</x:endPosition></x:positions>'
                 '<x:counts unit="counts">1 2 3 4</x:counts>'
                 '</x:dataPoints></x:scan></x:xrdMeasurement></x:xrdMeasurements>',
                 encoding="utf-8")

    assert identify_format(p).name == "xrdml"
    assert len(rx.read_pattern(p).two_theta) == 4


def test_a_comment_before_the_root_does_not_decide_the_sniff(tmp_path):
    """A comment may legally contain angle brackets, so it is stripped before the
    first element is looked for — otherwise a `<scan>` mentioned in prose wins."""
    p = tmp_path / "commented.xrdml"
    p.write_text('<?xml version="1.0"?><!-- written by <scan> exporter -->'
                 '<xrdMeasurements xmlns="http://www.xrdml.com/XRDMeasurement/1.6">'
                 '<xrdMeasurement><scan scanAxis="Gonio"><dataPoints>'
                 '<positions axis="2Theta"><startPosition>10</startPosition>'
                 '<endPosition>13</endPosition></positions>'
                 '<counts unit="counts">1 2 3 4</counts>'
                 '</dataPoints></scan></xrdMeasurement></xrdMeasurements>',
                 encoding="utf-8")

    assert identify_format(p).name == "xrdml"
    assert len(rx.read_pattern(p).two_theta) == 4


# --------------------------------------------------------------------- rasx
def write_rasx(path: Path, scans, *, manifest_only=(), omit_conditions=False,
               root_extra="") -> Path:
    """A minimal but manifest-shaped ``.rasx`` — the cases no fixture holds.

    A zip of text files, so the circularity a binary writer has to manage does
    not arise here: what this restates from the reader's understanding is the
    *manifest convention*, and that is written down in the reader's docstring
    from four real archives.
    """
    import zipfile

    groups, members = [], {}
    for i, scan in enumerate(scans):
        profile = f"Profile{i}.txt"
        conditions = f"MesurementConditions{i}.xml"
        rows = "\n".join("\t".join(f"{v}" for v in row) for row in scan["rows"])
        members[f"Data{i}/{profile}"] = "﻿" + rows + "\n"
        listed = f'<ContentHashList Name="{profile}" ContentHash="0" />'
        if not omit_conditions:
            members[f"Data{i}/{conditions}"] = (
                '﻿<?xml version="1.0" encoding="utf-8"?><MeasurementConditions>'
                f'<HWConfigurations><XrayGenerator><TargetName>Cu</TargetName>'
                f'<WavelengthKalpha1>1.540593</WavelengthKalpha1>'
                f'</XrayGenerator></HWConfigurations><ScanInformation>'
                f'<AxisName>{scan.get("axis", "TwoTheta")}</AxisName>'
                f'<Step>{scan.get("step", 0.02)}</Step>'
                f'<Speed>{scan.get("speed", 1.0)}</Speed>'
                f'<SpeedUnit>deg/min</SpeedUnit>'
                f'<IntensityUnit>{scan.get("unit", "counts")}</IntensityUnit>'
                f'<SampleName>{scan.get("sample", "")}</SampleName>'
                '</ScanInformation></MeasurementConditions>')
            listed += f'<ContentHashList Name="{conditions}" ContentHash="0" />'
        groups.append(f'<Data{i} Type="Profile">{listed}</Data{i}>')

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("root.xml", '﻿<?xml version="1.0" encoding="utf-8"?>'
                         f'<Root Version="1.1.0.0">{"".join(groups)}{root_extra}'
                         "</Root>")
        for name, text in members.items():
            archive.writestr(name, text.encode("utf-8"))
        for name in manifest_only:
            archive.writestr(name, "not a profile\n")
    return path


def test_the_real_rasx_powder_scan_reads_whole():
    data = rx.read_pattern(DATA / "rigaku_powder.rasx")

    assert len(data.two_theta) == 2726
    assert data.two_theta[0] == 10.0 and data.two_theta[-1] == 119.0
    assert data.metadata["scan_axis"] == "TwoTheta"
    assert data.metadata["anode"] == "Cu"
    assert data.metadata["wavelength"] == "1.540593"
    assert data.metadata["count_time_s"] == "2.4"      # 0.04° ÷ 1 deg/min × 60


def test_the_declared_unit_is_refuted_by_arithmetic_in_this_container_too():
    """A correction to this WP's own premise, which recorded cps as *verified by
    fixture* for `.rasx`.

    Two of the three real files declare ``<IntensityUnit>counts</IntensityUnit>``
    and store values like 170.55354309082 that no scale makes integral; the
    third declares counts and *is* integral to the last of 7001 points.  So this
    is the same free-text lie ``.ras`` tells, and the same arithmetic settles it
    — which is why both formats call one function.
    """
    lying: list = []
    liar = rx.read_pattern(DATA / "rigaku_powder.rasx", diagnostics=lying)
    honest: list = []
    truth = rx.read_pattern(DATA / "rigaku_zno_counts.rasx", diagnostics=honest)

    assert liar.metadata["intensity_unit"] == truth.metadata["intensity_unit"]
    assert [d.code for d in lying] == ["PATTERN_INTENSITY_SCALED"]
    assert liar.sigma is None       # withheld, and said so
    assert honest == [] and truth.sigma is None   # withheld, and correct
    assert all(float(v).is_integer() for v in truth.intensity)


def test_the_manifest_is_the_authority_not_the_name_list(tmp_path):
    """A zip may carry anything; ``root.xml`` is what says which members are
    scans and in which order."""
    p = write_rasx(tmp_path / "two.rasx",
                   [dict(rows=[(10.0, 5.0), (10.02, 6.0), (10.04, 7.0)]),
                    dict(rows=[(20.0, 1.0), (20.02, 2.0), (20.04, 3.0)])],
                   manifest_only=("Data9/Profile9.txt", "thumbnail.png"))

    assert [s.index for s in list_scans(p)] == [0, 1]
    assert rx.read_pattern(p, scan=1).two_theta == [20.0, 20.02, 20.04]


def test_the_default_scan_of_a_rasx_is_never_silent(tmp_path):
    p = write_rasx(tmp_path / "two.rasx",
                   [dict(rows=[(10.0, 5.0), (10.02, 6.0)]),
                    dict(rows=[(20.0, 1.0), (20.02, 2.0)])])
    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.metadata["scan_count"] == "2"
    assert [d.code for d in notes] == ["PATTERN_MULTISCAN_DEFAULTED"]


def test_a_manifest_naming_a_member_the_archive_lacks_is_refused_by_name(tmp_path):
    """The other half of "the manifest is the authority": a real profile member
    is present, so the sniff claims the file, and the manifest still points
    somewhere else.  Following the name list instead would read it happily."""
    import zipfile

    p = tmp_path / "hollow.rasx"
    with zipfile.ZipFile(p, "w") as archive:
        archive.writestr("root.xml", '<Root><Data0 Type="Profile">'
                         '<ContentHashList Name="Profile7.txt" /></Data0></Root>')
        archive.writestr("Data0/Profile0.txt", "10 1\n11 2\n")

    assert identify_format(p).name == "rasx"
    with pytest.raises(ValueError, match="internally inconsistent"):
        rx.read_pattern(p)


def test_a_member_past_the_cap_is_refused_rather_than_materialised(tmp_path,
                                                                   monkeypatch):
    """``ZipInfo.file_size`` is a number in the archive's own header, so it is
    the one a bomb lies about — hence ``read(cap + 1)`` and a length test rather
    than a size check before reading."""
    from rietx.io.formats import rasx

    p = write_rasx(tmp_path / "big.rasx",
                   [dict(rows=[(10.0 + 0.01 * i, 5.0) for i in range(200)])])
    monkeypatch.setattr(rasx, "MAX_MEMBER_BYTES", 64)

    with pytest.raises(ValueError, match="larger than"):
        rx.read_pattern(p)


def test_a_zip_that_is_not_a_rasx_is_not_claimed(tmp_path):
    """Zip magic says "an archive"; only a ``Data<N>/Profile<N>.txt`` member says
    whose.  Other zip-container formats sit in the same registry, so the sniff
    has to be about the manifest and never about the magic alone."""
    import zipfile

    p = tmp_path / "other.rasx"
    with zipfile.ZipFile(p, "w") as archive:
        archive.writestr("notes.txt", "not a diffraction file at all")

    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(p)
    assert "other.rasx" in str(refusal.value)
    assert "Supported" in str(refusal.value)


def test_the_attenuator_column_is_reported_here_exactly_as_in_ras(tmp_path):
    """One vendor's unstated convention, not one format's — so the two
    containers share the contract and the code."""
    p = write_rasx(tmp_path / "attn.rasx", [dict(
        rows=[(10.0, 5.0, 1.0), (10.02, 6.0, 10.0), (10.04, 7.0, 1.0)])])

    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.intensity == [5.0, 6.0, 7.0]          # never applied
    assert "RAS_ATTENUATOR_PRESENT" in [d.code for d in notes]


def test_a_rocking_curve_in_a_rasx_is_refused_on_the_vendors_vocabulary(tmp_path):
    p = write_rasx(tmp_path / "rock.rasx", [dict(
        axis="Omega", rows=[(10.0, 5.0), (10.02, 6.0), (10.04, 7.0)])])

    with pytest.raises(ValueError, match="rocking curve"):
        rx.read_pattern(p)


def test_the_scan_information_block_wins_over_a_like_named_leaf_elsewhere(
        tmp_path):
    """``Step`` and ``Speed`` are generic enough for an optics or alignment block
    to carry one, and a first-wins flatten over the whole document would then
    derive the counting time — and every σ with it — from somebody else's step."""
    import zipfile

    p = write_rasx(tmp_path / "shadow.rasx", [dict(
        step=0.02, speed=1.0, unit="cps",
        rows=[(10.0 + 0.02 * i, 1.5) for i in range(4)])])
    with zipfile.ZipFile(p) as archive:
        names = archive.namelist()
        members = {n: archive.read(n) for n in names}
    conditions = next(n for n in names if "Conditions" in n)
    members[conditions] = members[conditions].replace(
        b"<ScanInformation>",
        b"<Optics><Step>99</Step><Speed>99</Speed></Optics><ScanInformation>")
    with zipfile.ZipFile(p, "w") as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)

    # 0.02° ÷ 1 deg/min × 60 = 1.2 s, not 99/99
    assert rx.read_pattern(p).metadata["count_time_s"] == "1.2"


def test_a_group_with_no_conditions_still_yields_its_points(tmp_path):
    """The points are the pattern and the header is metadata, so losing the
    second is a thinner answer rather than no answer."""
    p = write_rasx(tmp_path / "bare.rasx",
                   [dict(rows=[(10.0, 5.0), (10.02, 6.0), (10.04, 7.0)])],
                   omit_conditions=True)

    notes: list = []
    data = rx.read_pattern(p, diagnostics=notes)

    assert data.two_theta == [10.0, 10.02, 10.04]
    assert "anode" not in data.metadata
    # …and the axis is unknown rather than assumed silently
    assert [d.code for d in notes] == ["PATTERN_X_AXIS_ASSUMED"]


# --------------------------------------------------------------------- brml
def write_brml(path: Path, scans, *, manifest=None, unit="Counts") -> Path:
    """A minimal but view-shaped ``.brml`` — the cases no vendorable file holds.

    The column layout is written *from* ``DataViews`` here exactly as the reader
    reads it back, which is the honest limit of a synthesized fixture: what it
    exercises is the failure paths, not the format.  The two real files are what
    established the layout, and `tests/data/README.md` records what each showed.
    """
    import zipfile

    members, refs = {}, []
    for i, scan in enumerate(scans):
        rows = "".join(f"<Datum>{','.join(str(v) for v in row)}</Datum>"
                       for row in scan["rows"])
        recorded = scan.get("recorded_length", 1)
        names = scan.get("axes", ("TwoTheta", "Theta"))
        axes = "".join(f'<FieldDefinitions FieldName="{a}" AxisId="{a}" />'
                       for a in names)
        # the recorded channel sits after the two fixed ones and every axis —
        # computed rather than fixed, which is the reader's own rule applied to
        # the writer, and the only way a one-axis scan can be written at all
        recorded_start = 2 + len(names)
        name = f"Experiment0/RawData{i}.xml"
        members[name] = (
            '<?xml version="1.0"?><RawData '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<TubeMaterial>Cu</TubeMaterial><WaveLength Unit="Å" Value="1.5406" />'
            f'<DataRoutes><DataRoute RouteFlag="{scan.get("flag", "Measured")}">'
            f'<ScanInformation ScanName="{scan.get("scan_name", "TwoThetaOmegaScan")}" />'
            f'{rows}<DataViews>'
            '<RawDataView xsi:type="FixedRawDataView" Start="0" Length="1" '
            'LogicName="MeasuredTime" Unit="s" />'
            '<RawDataView xsi:type="FixedRawDataView" Start="1" Length="1" '
            'LogicName="AbsorptionFactor" Unit="" />'
            f'<RawDataView xsi:type="VaryingRawDataView" Start="2" '
            f'Length="{len(names)}">'
            f'<Varying>{axes}</Varying></RawDataView>'
            f'<RawDataView xsi:type="RecordedRawDataView" '
            f'Start="{recorded_start}" '
            f'Length="{recorded}"><Recording>'
            f'<Unit Prefix="None" Base="{unit}" /></Recording></RawDataView>'
            '</DataViews></DataRoute></DataRoutes></RawData>')
        refs.append(f"<string>{name}</string>")

    listed = "".join(refs) if manifest is None else manifest
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Experiment0/DataContainer.xml",
                         '<?xml version="1.0"?><DataContainer '
                         f'RawDataLength="{len(scans)}">'
                         f"<RawDataReferenceList>{listed}</RawDataReferenceList>"
                         "</DataContainer>")
        for name, text in members.items():
            archive.writestr(name, text)
    return path


def test_the_real_brml_reads_through_its_own_channel_description():
    """No index is counted: in this file 2θ is column 2 and the intensity is
    column **7**, which is why GSAS-II's fixed ``entry[2]``/``entry[4]`` is a
    coincidence of one layout rather than the format."""
    data = rx.read_pattern(DATA / "bruker_absorber.brml")

    assert len(data.two_theta) == 2001
    assert data.two_theta[0] == 44.0 and data.two_theta[-1] == 48.0
    assert data.metadata["scan_axis"] == "TwoThetaOmegaScan"
    assert data.metadata["anode"] == "Cu"
    assert data.metadata["wavelength"] == "1.5406"
    assert data.metadata["intensity_unit"] == "Counts"
    assert data.metadata["count_time_s"] == "1.0"


def test_the_bruker_absorber_is_already_applied_so_only_sigma_goes_through_it():
    """The third answer from a third vendor, and the same structural test.

    In this file ``y`` is not integral, ``y × a`` is not, and ``y / a`` **is**;
    and the stored series runs continuously across the point where the absorber
    engages while ``y / a`` steps by a factor of seven.  So Bruker stores the
    corrected intensity — nothing is multiplied — but the Poisson quantity is
    still ``y / a``, so σ = √(y/a)·a.
    """
    notes: list = []
    data = rx.read_pattern(DATA / "bruker_absorber.brml", diagnostics=notes)

    apex = max(range(len(data.intensity)), key=lambda i: data.intensity[i])
    assert data.intensity[apex] == 495559.8          # stored, not multiplied
    assert data.sigma is not None
    assert data.sigma[apex] == pytest.approx((495559.8 / 8.3) ** 0.5 * 8.3)
    # the counted quantity really is y/a: whole numbers, to the last point
    assert all(abs(v / 8.3 - round(v / 8.3)) < 1e-3 or abs(v - round(v)) < 1e-3
               for v in data.intensity)
    assert [d.code for d in notes] == ["BRML_ABSORBER_ENGAGED"]
    assert "8.3" in notes[0].message


def test_a_detector_frame_is_refused_rather_than_read_as_a_profile(tmp_path):
    """``EJZ060_13_004_RSM.brml`` records 1280 channels per row and still claims
    ``AxisId="TwoTheta"`` in its ``ScanAxes``, so the axis check passes and only
    the recorded view's own ``Length`` says what the rows are."""
    p = write_brml(tmp_path / "psd.brml", [dict(
        recorded_length=1280,
        rows=[(1, 1, 44.0 + 0.01 * i, 18.0) + tuple(range(1280))
              for i in range(4)])])

    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(p)
    assert "psd.brml" in str(refusal.value)
    assert "position-sensitive-detector frame" in str(refusal.value)


def test_a_scan_with_no_two_theta_axis_is_refused_by_what_it_does_step(tmp_path):
    p = write_brml(tmp_path / "rock.brml", [dict(
        axes=("Theta",), scan_name="RockingCurveScan",
        rows=[(1, 1, 18.0 + 0.01 * i, 5) for i in range(4)])])   # 2θ never moves

    with pytest.raises(ValueError) as refusal:
        rx.read_pattern(p)
    assert "rocking curve" in str(refusal.value)


def test_the_manifest_orders_the_scans_because_the_name_list_does_not(tmp_path):
    """A real 801-scan archive stores its members …20, 22, 21,
    experimentCollection.xml, 23…, so the zip's own order is not the scans'."""
    p = write_brml(tmp_path / "many.brml",
                   [dict(rows=[(1, 1, 10.0 + 0.01 * i, 5.0, 100 + i)
                               for i in range(4)]),
                    dict(rows=[(1, 1, 30.0 + 0.01 * i, 5.0, 200 + i)
                               for i in range(4)])])
    notes: list = []

    first = rx.read_pattern(p, diagnostics=notes)
    second = rx.read_pattern(p, scan=1)

    assert first.two_theta[0] == 10.0 and second.two_theta[0] == 30.0
    assert [d.code for d in notes] == ["PATTERN_MULTISCAN_DEFAULTED"]
    assert [s.index for s in list_scans(p)] == [0, 1]


def _with_extra_route(path: Path, flag: str) -> Path:
    """The same ``.brml`` with a second ``DataRoute`` spliced in."""
    import zipfile

    with zipfile.ZipFile(path) as archive:
        container = archive.read("Experiment0/DataContainer.xml").decode()
        raw = archive.read("Experiment0/RawData0.xml").decode()
    doubled = raw.replace("</DataRoutes>",
                          f'<DataRoute RouteFlag="{flag}"><Datum>1,1,90,45,7'
                          "</Datum></DataRoute></DataRoutes>")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Experiment0/DataContainer.xml", container)
        archive.writestr("Experiment0/RawData0.xml", doubled)
    return path


def test_a_processed_route_beside_the_measured_one_is_not_what_gets_fitted(
        tmp_path):
    """A processed route is somebody else's background subtraction; refining
    against it unasked is the silent substitution this package refuses.  Where
    exactly one route says ``Measured``, that is the answer and the rest are
    ignored — where two do, choosing is the file's job and the reader stops."""
    rows = [(1, 1, 10.0 + 0.01 * i, 5.0, 100 + i) for i in range(4)]

    ignored = _with_extra_route(
        write_brml(tmp_path / "one.brml", [dict(rows=rows)]), "Processed")
    assert rx.read_pattern(ignored).two_theta[0] == 10.0

    ambiguous = _with_extra_route(
        write_brml(tmp_path / "two.brml", [dict(rows=rows)]), "Measured")
    with pytest.raises(ValueError, match="not exactly one marked Measured"):
        rx.read_pattern(ambiguous)


def test_the_xsi_prefix_is_resolved_rather_than_matched_as_text(tmp_path):
    """The prefix is the document's to choose — ``xsi:`` here, ``xs:`` in the
    next file — and ElementTree resolves it away, so matching the literal string
    would break on a file this reader must still open."""
    import zipfile

    p = write_brml(tmp_path / "prefixed.brml",
                   [dict(rows=[(1, 1, 10.0 + 0.01 * i, 5.0, 100 + i)
                               for i in range(4)])])
    with zipfile.ZipFile(p) as archive:
        container = archive.read("Experiment0/DataContainer.xml").decode()
        raw = archive.read("Experiment0/RawData0.xml").decode()
    renamed = raw.replace("xmlns:xsi=", "xmlns:zz=").replace("xsi:type=", "zz:type=")
    with zipfile.ZipFile(p, "w") as archive:
        archive.writestr("Experiment0/DataContainer.xml", container)
        archive.writestr("Experiment0/RawData0.xml", renamed)

    assert len(rx.read_pattern(p).two_theta) == 4


def test_a_manifest_naming_a_missing_raw_data_is_refused_by_name(tmp_path):
    p = write_brml(tmp_path / "hollow.brml",
                   [dict(rows=[(1, 1, 10.0, 5.0, 100)])],
                   manifest="<string>Experiment0/RawData9.xml</string>")

    assert identify_format(p).name == "brml"
    with pytest.raises(ValueError, match="internally inconsistent"):
        rx.read_pattern(p)


# --------------------------------------------------------------------------- #
# Bruker/Siemens .raw — the binary DIFFRAC formats
#
# The real fixture is the only evidence about the format, and it is evidence
# about *structure* alone: FAIRmat scrambled its intensities before publishing
# it (tests/data/README.md carries the measurement).  So the numbers asserted
# from it are header numbers, the synthesized files carry every value assertion,
# and one test below pins the scrambling itself — otherwise a later session
# reads "7134 real points from a real diffractometer" and writes an acceptance
# row against intensities that are noise.
# --------------------------------------------------------------------------- #

RAW4 = DATA / "bruker_raw4_scrambled.raw"


def test_the_real_v4_fixture_reports_the_header_its_instrument_wrote():
    d = rx.read_pattern(RAW4)

    assert len(d.two_theta) == 7134
    assert d.two_theta[0] == pytest.approx(10.0)
    assert d.two_theta[-1] == pytest.approx(85.04129916, abs=1e-6)
    assert d.metadata["scan_axis"] == "2Theta"
    assert d.metadata["scan_count"] == "1"
    assert d.metadata["anode"] == "Cu"
    assert d.metadata["sample"] == "HeOx-1001-nsp-sps-900C-10min-01-poliert"
    # milliseconds, not seconds: 310 ms × 7134 steps is a 37-minute scan and
    # seconds would make it 25 days
    assert float(d.metadata["count_time_s"]) == pytest.approx(0.310003, abs=1e-6)
    assert float(d.metadata["wavelength"]) == pytest.approx(1.5406, abs=1e-6)


def test_the_real_v4_fixtures_intensities_are_not_a_diffraction_profile():
    """The fixture proves structure and metadata, never values — pinned here.

    A profile stepped at 0.0105° has adjacent channels on the same peak, so its
    lag-1 autocorrelation is near one; this file's is ~0.016 and its
    point-to-point scatter is √2 times its own spread, which is what independent
    values look like.  Nearly a third of the intensities are negative.
    """
    import numpy as np

    y = np.asarray(rx.read_pattern(RAW4).intensity)

    assert abs(np.corrcoef(y[:-1], y[1:])[0, 1]) < 0.1
    assert np.diff(y).std() / y.std() == pytest.approx(np.sqrt(2), abs=0.1)
    assert (y < 0).mean() > 0.3


def test_the_real_v4_fixture_withholds_sigma_because_no_scale_verifies():
    """v4 declares no intensity unit anywhere, so arithmetic has to decide — and
    on this file it decides nothing, which is the third answer and not a
    missing one."""
    diagnostics = []
    d = rx.read_pattern(RAW4, diagnostics=diagnostics)

    assert d.sigma is None
    assert [x.code for x in diagnostics] == ["PATTERN_INTENSITY_SCALED"]


def test_the_range_count_is_walked_not_counted_from_the_drive_names():
    """``2Theta`` appears **twice** in this single-range file — once as a drive
    record and once as the scan-axis record — so a reader that counts the string
    to find its banks (GSAS-II does) reports two ranges where there is one."""
    assert RAW4.read_bytes().count(b"2Theta") == 2
    assert rx.read_pattern(RAW4).metadata["scan_count"] == "1"
    assert len(list_scans(RAW4)) == 1


def test_the_datum_stride_is_the_one_declared_not_a_fixed_four_or_eight(tmp_path):
    """The bug both other readers have, in both directions.

    GSAS-II reads ``datumSize`` and then reads ``nSteps`` *consecutive* float32s;
    FAIRmat hard-codes an 8-byte stride as "interleaved float32 pairs".  Written
    at 4 and at 8, the same intensities must come back the same.
    """
    from tests.writers_xrd import write_raw4

    y = [100.0 + (i % 13) for i in range(300)]
    narrow = write_raw4(tmp_path / "d4.raw",
                        [dict(start=10.0, step=0.02, intensity=y, datum_size=4)])
    wide = write_raw4(tmp_path / "d8.raw",
                      [dict(start=10.0, step=0.02, intensity=y, datum_size=8)])
    twelve = write_raw4(tmp_path / "d12.raw",
                        [dict(start=10.0, step=0.02, intensity=y, datum_size=12)])

    assert rx.read_pattern(narrow).intensity == y
    assert rx.read_pattern(wide).intensity == y
    assert rx.read_pattern(twelve).intensity == y


def test_a_datum_that_cannot_hold_a_float32_is_refused(tmp_path):
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "thin.raw",
                   [dict(start=10.0, step=0.02, intensity=[1.0, 2.0, 3.0],
                         datum_size=2)])

    with pytest.raises(ValueError, match="datum of 2 bytes"):
        rx.read_pattern(p)


def test_a_second_range_is_a_scan_to_choose_between_never_a_continuation(tmp_path):
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "two.raw", [
        dict(start=10.0, step=0.02, intensity=[100.0 + i % 7 for i in range(200)]),
        dict(start=40.0, step=0.05, intensity=[50.0 + i % 5 for i in range(150)]),
    ])

    diagnostics = []
    first = rx.read_pattern(p, diagnostics=diagnostics)
    assert len(first.two_theta) == 200
    assert first.two_theta[0] == pytest.approx(10.0)
    assert first.metadata["scan_count"] == "2"
    assert "PATTERN_MULTISCAN_DEFAULTED" in [x.code for x in diagnostics]

    second = rx.read_pattern(p, scan=1, diagnostics=[])
    assert len(second.two_theta) == 150
    assert second.two_theta[0] == pytest.approx(40.0)
    assert [s.n_points for s in list_scans(p)] == [200, 150]

    with pytest.raises(ValueError, match="scan=2 is not one of them"):
        rx.read_pattern(p, scan=2)


def test_a_rocking_curve_is_refused_by_what_it_actually_is(tmp_path):
    """The drive record says the scan stepped θ with the detector fixed.  Its
    points parse perfectly and would refine to a confidently wrong cell."""
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "rock.raw", [dict(
        start=10.0, step=0.01, intensity=[500.0] * 50, scan_type="Rocking Curve",
        drives=(("2Theta", 34.0, 0), ("Theta", 10.0, 2)))])

    with pytest.raises(ValueError, match="rocking curve about θ"):
        rx.read_pattern(p)


def test_an_unfamiliar_drive_is_read_as_two_theta_and_says_so(tmp_path):
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "odd.raw", [dict(
        start=10.0, step=0.01, intensity=[500.0] * 50, scan_type="Custom Scan",
        drives=(("Gimbal", 10.0, 2),))])

    diagnostics = []
    assert len(rx.read_pattern(p, diagnostics=diagnostics).two_theta) == 50
    assert "PATTERN_X_AXIS_ASSUMED" in [x.code for x in diagnostics]


def test_the_scan_type_answers_when_no_drive_record_is_flagged(tmp_path):
    """The flag is one file's evidence, so it is never the only statement asked.

    With nothing flagged, the file still says what *kind* of scan it is, and a
    locked-coupled one steps 2θ whatever its drive records look like.
    """
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "unflagged.raw", [dict(
        start=10.0, step=0.01, intensity=[500.0] * 50,
        drives=(("2Theta", 10.0, 0), ("Theta", 5.0, 0)))])

    diagnostics = []
    assert len(rx.read_pattern(p, diagnostics=diagnostics).two_theta) == 50
    assert [x.code for x in diagnostics] == []

    # and a scan type that is recognisably *not* 2θ is refused there too — a
    # file saying "Psi Scan" has told us its abscissa, and nothing about its
    # drive records makes that less true
    tilt = write_raw4(tmp_path / "unflagged_psi.raw", [dict(
        start=10.0, step=0.01, intensity=[500.0] * 50, scan_type="Psi Scan",
        drives=(("2Theta", 10.0, 0),))])
    with pytest.raises(ValueError, match="ψ tilt"):
        rx.read_pattern(tilt)

    # only an *unfamiliar* one is assumed, which is this reader's ignorance
    unknown = write_raw4(tmp_path / "unflagged_odd.raw", [dict(
        start=10.0, step=0.01, intensity=[500.0] * 50, scan_type="Bespoke Sweep",
        drives=(("2Theta", 10.0, 0),))])
    diagnostics = []
    rx.read_pattern(unknown, diagnostics=diagnostics)
    assert [x.code for x in diagnostics] == ["PATTERN_X_AXIS_ASSUMED"]


def test_the_flagged_record_must_also_sit_at_the_ranges_start_angle(tmp_path):
    """Two statements that have to agree.  A flag on a drive parked somewhere
    else is not the abscissa, so the scan type answers instead — and here it
    says the scan is a coupled one, which reads."""
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "parked.raw", [dict(
        start=10.0, step=0.01, intensity=[500.0] * 50,
        drives=(("2Theta", 10.0, 0), ("Phi", 271.0, 2)))])

    diagnostics = []
    assert len(rx.read_pattern(p, diagnostics=diagnostics).two_theta) == 50
    assert [x.code for x in diagnostics] == []


def test_counts_take_the_poisson_fallback_and_a_rate_gets_a_derived_sigma(tmp_path):
    from tests.writers_xrd import write_raw4

    counts = write_raw4(tmp_path / "counts.raw", [dict(
        start=10.0, step=0.02, intensity=[400.0 + i % 9 for i in range(120)])])
    assert rx.read_pattern(counts).sigma is None       # the fallback is correct

    # odd counts over a 2 s step: the stored rate is a half-integer, so it is
    # not counts, and y·t is whole, so it is that count divided by the time
    rate = write_raw4(tmp_path / "cps.raw", [dict(
        start=10.0, step=0.02, step_time_ms=2000.0,
        intensity=[(401.0 + 2 * (i % 9)) / 2.0 for i in range(120)])])
    d = rx.read_pattern(rate)
    assert d.sigma is not None
    assert d.sigma[0] == pytest.approx((401.0 ** 0.5) / 2.0, rel=1e-6)


def test_a_range_header_whose_segments_overrun_its_size_is_refused(tmp_path):
    """The self-consistency gate: a mis-parsed length walks into the intensity
    records and finds plausible-looking segments there, so "ended exactly where
    it said it would" is the difference between a parse and a coincidence."""
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "overrun.raw",
                   [dict(start=10.0, step=0.02, intensity=[100.0] * 60)],
                   header_overrun=-20)

    assert identify_format(p).name == "bruker_raw"
    with pytest.raises(ValueError, match="overrun"):
        rx.read_pattern(p)


def test_a_range_declaring_more_points_than_the_file_holds_is_refused(tmp_path):
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "short.raw",
                   [dict(start=10.0, step=0.02, intensity=[100.0] * 60)])
    p.write_bytes(p.read_bytes()[:-120])

    with pytest.raises(ValueError, match="truncated"):
        rx.read_pattern(p)


@pytest.mark.parametrize("magic,version", [(b"RAW ", 1), (b"RAW2", 2)])
def test_an_undescribed_raw_version_is_refused_by_its_version_not_a_traceback(
        magic, version, tmp_path):
    """v1 has no description at all and v2 exactly one, uncorroborated — so
    both are named rather than guessed at.  A parser written from a single
    description with no file to check it against is how a reader comes to return
    a plausible wrong pattern, which is what this whole seam exists to stop."""
    p = tmp_path / f"v{version}.raw"
    p.write_bytes(magic + b"\x00" * 4000)

    assert identify_format(p).name == "bruker_raw"
    with pytest.raises(ValueError, match=f"RAW version {version}"):
        rx.read_pattern(p)


def test_the_two_raw_formats_are_disjoint_in_both_directions(tmp_path):
    """A GSAS file named ``.raw`` still reaches ``gsas``; a Bruker file named
    ``.gsas`` still reaches ``bruker_raw``.  Magic bytes against a ``BANK``
    record — the sets cannot overlap, and both directions are tested because
    only one of them is the one dispatch order would fix."""
    from tests.writers_xrd import write_raw4

    gsas_named_raw = tmp_path / "gsas.raw"
    gsas_named_raw.write_text(
        "a title\nBANK 1 4 4 CONST 1000.0 20.0 0 0 STD\n"
        "     100     110     120     130\n", encoding="utf-8")
    assert identify_format(gsas_named_raw).name == "gsas"

    bruker_named_gsas = write_raw4(
        tmp_path / "bruker.gsas",
        [dict(start=10.0, step=0.02, intensity=[100.0] * 60)])
    assert identify_format(bruker_named_gsas).name == "bruker_raw"


def test_a_range_stored_high_to_low_is_reversed_and_says_so(tmp_path):
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "down.raw", [dict(
        start=40.0, step=-0.02, intensity=[100.0 + i for i in range(50)])])

    diagnostics = []
    d = rx.read_pattern(p, diagnostics=diagnostics)
    assert d.two_theta[0] < d.two_theta[-1]
    assert d.intensity[0] == 149.0
    assert "PATTERN_SCAN_REVERSED" in [x.code for x in diagnostics]


def test_the_alternate_range_marker_is_read_the_same_way(tmp_path):
    """Two values mark a range — 0 and 160 — and neither is a segment type."""
    from tests.writers_xrd import write_raw4

    p = write_raw4(tmp_path / "marker160.raw",
                   [dict(start=10.0, step=0.02, intensity=[100.0] * 60)],
                   marker=160)

    assert len(rx.read_pattern(p).two_theta) == 60


# --------------------------------------------------------------------------- #
# .raw v3 (RAW1.01) — three agreeing descriptions and no file at all
#
# Everything here is synthesized, so it exercises the reader's arithmetic and
# its gates, never the format.  What makes v3 shippable on that footing is the
# gates themselves: `data_record_length == 4 + 8·popcount(varying_parameters)`
# cannot be satisfied by a header read at the wrong offset, and the declared
# ranges have to account for the whole file.
# --------------------------------------------------------------------------- #


def test_a_v3_range_reads_its_header_and_its_counts(tmp_path):
    from tests.writers_xrd import write_raw3

    y = [400.0 + i % 11 for i in range(250)]
    p = write_raw3(tmp_path / "one.raw", [dict(start=10.0, step=0.02,
                                               intensity=y, step_time=1.0)],
                   sample="corundum", radius=280.0)

    assert identify_format(p).name == "bruker_raw"
    d = rx.read_pattern(p)
    assert d.intensity == y
    assert d.two_theta[0] == pytest.approx(10.0)
    assert d.two_theta[-1] == pytest.approx(10.0 + 0.02 * 249)
    assert d.metadata["sample"] == "corundum"
    assert d.metadata["anode"] == "Cu"
    assert d.metadata["scan_axis"] == "locked coupled"
    assert float(d.metadata["goniometer_radius_mm"]) == pytest.approx(280.0)
    assert d.sigma is None                       # integral counts, Poisson is right


def test_the_v3_data_starts_past_the_extra_records_the_header_counts(tmp_path):
    """The field GSAS-II's literal ``+40`` is standing in for.

    Optional records sit between a range header and its data, and their total
    size is declared at +256.  A reader that ignores it reads the first datum
    from inside one of them — which is why GSAS-II carries a bare ``except``
    that retries the whole block 40 bytes earlier.
    """
    from tests.writers_xrd import write_raw3

    y = [500.0 + i for i in range(60)]
    plain = write_raw3(tmp_path / "plain.raw",
                       [dict(start=10.0, step=0.02, intensity=y)])
    padded = write_raw3(tmp_path / "extras.raw",
                        [dict(start=10.0, step=0.02, intensity=y,
                              extras=[(100, 40), (110, 32)])])

    assert padded.stat().st_size == plain.stat().st_size + 72
    assert rx.read_pattern(padded).intensity == y


def test_a_v3_datum_is_the_declared_record_not_four_bytes(tmp_path):
    """`data_record_length` is 4 + 8 per varying parameter, so a scan that
    stores a measured 2θ has 12-byte data records — and the measured column is
    used, which is the whole reason it is written."""
    from tests.writers_xrd import write_raw3

    y = [300.0 + i for i in range(40)]
    # a deliberately *uneven* axis, so reading start + i·step would differ
    measured = [10.0 + 0.02 * i + 0.001 * (i % 3) for i in range(40)]
    p = write_raw3(tmp_path / "varying.raw",
                   [dict(start=10.0, step=0.02, intensity=y, two_theta=measured)])

    d = rx.read_pattern(p)
    assert d.intensity == y
    assert d.two_theta == pytest.approx(measured)


def test_a_v3_record_length_disagreeing_with_its_varying_bits_is_refused(tmp_path):
    """The gate that says the header was parsed at all: the two fields are
    written by the same instrument from the same fact, so a header read at the
    wrong offset will not satisfy them both."""
    from tests.writers_xrd import write_raw3

    p = write_raw3(tmp_path / "bad.raw",
                   [dict(start=10.0, step=0.02, intensity=[1.0] * 30,
                         varying=0b101, record_length=4)])

    with pytest.raises(ValueError, match="wants 20"):
        rx.read_pattern(p)


def test_v3_ranges_are_scans_and_the_default_says_so(tmp_path):
    from tests.writers_xrd import write_raw3

    p = write_raw3(tmp_path / "two.raw", [
        dict(start=10.0, step=0.02, intensity=[100.0] * 200),
        dict(start=40.0, step=0.01, intensity=[50.0] * 300, extras=[(150, 24)]),
    ])

    diagnostics = []
    assert len(rx.read_pattern(p, diagnostics=diagnostics).two_theta) == 200
    assert "PATTERN_MULTISCAN_DEFAULTED" in [x.code for x in diagnostics]
    assert len(rx.read_pattern(p, scan=1).two_theta) == 300
    assert [s.n_points for s in list_scans(p)] == [200, 300]


def test_a_vt_reel_surfaces_its_own_series_coordinate(tmp_path):
    """The temperature each range records reaches a caller (WP-1110 item 17).

    v3 has parsed this field since the reader shipped and then dropped it, so
    an agent refining a 68-pattern in-situ reel read ``_Range.temperature_k``
    off this module's private ``_parse`` to recover the 318/323/333 K its own
    trajectory was indexed by.  On an in-situ run the series coordinate *is*
    the experiment: without it there is no ``x=`` for ``refine_sequential``.

    It reaches two surfaces because two questions are asked at different
    times — ``list_scans`` before choosing a scan, the pattern's metadata
    after reading one — and the label carries it as well as the field, since
    every range of a reel scans the same axis over the same angles and would
    otherwise enumerate as N identical rows.
    """
    from tests.writers_xrd import write_raw3

    p = write_raw3(tmp_path / "ramp.raw", [
        dict(start=10.0, step=0.02, intensity=[100.0] * 60, temperature=t)
        for t in (318.0, 323.0, 333.0)
    ])

    assert [s.temperature_k for s in list_scans(p)] == [318.0, 323.0, 333.0]
    assert "318 K" in list_scans(p)[0].label
    assert rx.read_pattern(p, scan=1).metadata["temperature_k"] == "323.0"


def test_a_range_recording_no_temperature_says_nothing(tmp_path):
    """Absent is not ambient.

    The v3 field is zero-filled when the instrument had no temperature to
    record, and ``metadata()`` drops a ``None``, so the key is missing rather
    than present with a number nobody measured — the same rule the σ fallback
    follows one rank up.
    """
    from tests.writers_xrd import write_raw3

    p = write_raw3(tmp_path / "ambient.raw",
                   [dict(start=10.0, step=0.02, intensity=[100.0] * 60)])

    assert "temperature_k" not in rx.read_pattern(p).metadata
    assert list_scans(p)[0].temperature_k is None
    assert "K" not in list_scans(p)[0].label


@pytest.mark.parametrize("code,what", [
    (3, "rocking curve about θ"), (5, "φ rotation"), (12, "ψ tilt"),
    (14, "reciprocal-space map"),
])
def test_a_v3_scan_type_that_is_not_a_profile_is_refused_by_name(code, what,
                                                                 tmp_path):
    from tests.writers_xrd import write_raw3

    p = write_raw3(tmp_path / f"t{code}.raw",
                   [dict(start=10.0, step=0.02, intensity=[100.0] * 40,
                         scan_type=code)])

    with pytest.raises(ValueError, match=what):
        rx.read_pattern(p)


def test_a_v3_scan_type_this_reader_has_no_name_for_is_assumed_and_says_so(
        tmp_path):
    """The enum has one source, so an unfamiliar code is this reader's ignorance
    and not the file's fault — which is the assumed arm, not the refused one."""
    from tests.writers_xrd import write_raw3

    p = write_raw3(tmp_path / "psd.raw",
                   [dict(start=10.0, step=0.02, intensity=[100.0] * 40,
                         scan_type=130)])          # a PSD fast scan: abscissa unclear

    diagnostics = []
    assert len(rx.read_pattern(p, diagnostics=diagnostics).two_theta) == 40
    assert [x.code for x in diagnostics] == ["PATTERN_X_AXIS_ASSUMED"]


def test_v3_refuses_a_file_its_declared_ranges_do_not_account_for(tmp_path):
    """The global gate, and the reason v3 ships without a fixture: if the
    arithmetic is right the last range ends on EOF or on a pad, and if it is
    wrong what is left over is counts -- so the gate reads the leftover's
    content, and says where the first byte of it is."""
    from tests.writers_xrd import write_raw3

    p = write_raw3(tmp_path / "extra_tail.raw",
                   [dict(start=10.0, step=0.02, intensity=[100.0] * 40)],
                   trailing=b"\x00" * 32 + b"\x00\x00\x96\x43" * 8)  # f32 300.0

    with pytest.raises(ValueError, match="unaccounted for.*first non-zero"):
        rx.read_pattern(p)


def test_v3_reads_a_file_whose_leftover_is_a_zero_pad(tmp_path):
    """A real DIFFRAC VT reel pads past its last range -- measured: 3280 zero
    bytes past 82 ranges of a 318-1123 K reel, which the length-only gate
    refused outright.  A range read at the wrong offset leaves counts behind
    and counts are not zeros, so the pad is admitted by content while the
    ranges still have to account for everything before it."""
    from tests.writers_xrd import write_raw3

    p = write_raw3(tmp_path / "padded.raw",
                   [dict(start=10.0, step=0.02, intensity=[100.0] * 40)],
                   trailing=b"\x00" * 3280)

    assert len(rx.read_pattern(p).two_theta) == 40


def test_a_v3_range_count_that_is_not_a_count_is_refused(tmp_path):
    from tests.writers_xrd import write_raw3

    p = write_raw3(tmp_path / "many.raw",
                   [dict(start=10.0, step=0.02, intensity=[100.0] * 40)])
    raw = bytearray(p.read_bytes())
    raw[12:16] = (999_999).to_bytes(4, "little")
    p.write_bytes(bytes(raw))

    with pytest.raises(ValueError, match="not a number of measurements"):
        rx.read_pattern(p)


# ----------------------------------------------- pdCIF: the net intensity column
# ``_pd_proc_intensity_net`` is the item a TOPAS deposit writes (WP-1806, #561).
# It is read last of the intensity items, reported every time it is the one
# read, and a column labelled net that never comes near zero is reported as
# still carrying its background.  Nothing is repaired: y is the file's.

def _write_pdcif(path, columns: dict[str, list[float]]):
    """A one-block pdCIF holding ``columns`` as one loop, 2θ first."""
    tags = list(columns)
    rows = zip(*(columns[t] for t in tags))
    text = ("data_synthetic\nloop_\n" + "".join(f"{t}\n" for t in tags)
            + "".join(" ".join(repr(float(v)) for v in r) + "\n" for r in rows))
    path.write_text(text, encoding="utf-8")
    return path


_TT = [10.0, 10.01, 10.02, 10.03, 10.04, 10.05]
_Y = [400.0, 410.0, 900.0, 1200.0, 420.0, 405.0]
#: weights with a variable counting time folded in, so σ = 1/√w is not √y
_W = [0.0050, 0.0049, 0.0011, 0.0016, 0.0048, 0.0049]


def test_a_net_column_reads_with_its_weights_and_is_reported(tmp_path):
    """T1: the item TOPAS deposits, refused before it was in ``_PDCIF_Y``."""
    p = _write_pdcif(tmp_path / "net.cif", {
        "_pd_proc_2theta_corrected": _TT, "_pd_proc_ls_weight": _W,
        "_pd_proc_intensity_net": _Y})
    found: list = []
    pat = rx.read_pattern(p, diagnostics=found)
    assert pat.intensity == _Y
    assert pat.sigma == pytest.approx([1 / w ** 0.5 for w in _W], rel=1e-12)
    assert "PATTERN_INTENSITY_NET" in [d.code for d in found]
    assert pat.metadata["intensity_item"] == "_pd_proc_intensity_net"


def test_the_same_values_as_a_total_column_read_identically_and_say_nothing(tmp_path):
    """T2, the control: only the item's name differs, so only the report may."""
    net = _write_pdcif(tmp_path / "net.cif", {
        "_pd_proc_2theta_corrected": _TT, "_pd_proc_ls_weight": _W,
        "_pd_proc_intensity_net": _Y})
    total = _write_pdcif(tmp_path / "total.cif", {
        "_pd_proc_2theta_corrected": _TT, "_pd_proc_ls_weight": _W,
        "_pd_proc_intensity_total": _Y})
    found: list = []
    a, b = rx.read_pattern(net), rx.read_pattern(total, diagnostics=found)
    assert (a.two_theta, a.intensity, a.sigma) == (b.two_theta, b.intensity, b.sigma)
    assert found == []
    assert "intensity_item" not in b.metadata


def test_a_total_column_beside_a_net_one_wins(tmp_path):
    """T3: net is last, so a file stating both reads as it did before."""
    p = _write_pdcif(tmp_path / "both.cif", {
        "_pd_proc_2theta_corrected": _TT, "_pd_proc_ls_weight": _W,
        "_pd_proc_intensity_net": [v - 300.0 for v in _Y],
        "_pd_proc_intensity_total": _Y})
    found: list = []
    pat = rx.read_pattern(p, diagnostics=found)
    assert pat.intensity == _Y
    assert found == []


def test_a_net_columns_own_su_wins_over_the_weights(tmp_path):
    """T4: the su suffix rule reaches the net item with no code of its own."""
    su = [21.0, 22.0, 33.0, 37.0, 22.5, 21.5]
    p = _write_pdcif(tmp_path / "su.cif", {
        "_pd_proc_2theta_corrected": _TT, "_pd_proc_ls_weight": _W,
        "_pd_proc_intensity_net": _Y, "_pd_proc_intensity_net_su": su})
    assert rx.read_pattern(p).sigma == su


def test_the_acridine_deposit_reads_its_weights_and_its_net_column_disagrees():
    """T5, the real file (COD 2242872, ``tests/data/README.md``).

    Its weights carry a variable counting time, so w·y is about 1 at low angle
    and about 5 from 26 to 30°: a σ taken as √y instead would weigh the high
    half wrongly by up to √5.  Its net column never comes within 14σ of zero,
    so the contradiction fires.
    """
    import numpy as np

    found: list = []
    pat = rx.read_pattern(DATA / "cod_2242872.cif", diagnostics=found)
    tt, y = np.array(pat.two_theta), np.array(pat.intensity)
    s = np.array(pat.sigma)
    assert len(tt) == 6601
    assert (tt[0], tt[-1]) == (2.002, 35.002)
    wy = y / s ** 2
    assert np.median(wy[tt < 18.0]) == pytest.approx(1.05, abs=0.02)
    assert np.median(wy[(tt >= 26.0) & (tt < 30.0)]) == pytest.approx(5.1, abs=0.1)
    codes = [d.code for d in found]
    assert codes == ["PATTERN_INTENSITY_NET", "PATTERN_NET_HAS_BACKGROUND"]
    assert found[1].level == "warning"
    assert found[1].value == pytest.approx(14.12, abs=0.01)


def test_a_net_column_with_a_true_zero_baseline_is_only_reported(tmp_path):
    """T6, the contradiction's negative arm: a subtracted pattern returns to
    within noise of zero between its peaks, so only the info code fires."""
    import numpy as np

    rng = np.random.default_rng(1806)
    tt = np.round(np.arange(10.0, 12.0, 0.01), 4)
    peak = 2000.0 * np.exp(-0.5 * ((tt - 11.0) / 0.03) ** 2)
    sig = np.sqrt(peak + 100.0)      # a background of 100 was subtracted
    y = peak + rng.normal(0.0, 1.0, tt.size) * sig
    p = _write_pdcif(tmp_path / "zero.cif", {
        "_pd_proc_2theta_corrected": tt.tolist(),
        "_pd_proc_ls_weight": (1.0 / sig ** 2).tolist(),
        "_pd_proc_intensity_net": y.tolist()})
    found: list = []
    rx.read_pattern(p, diagnostics=found)
    assert [d.code for d in found] == ["PATTERN_INTENSITY_NET"]


def test_a_calculated_net_column_alone_is_still_refused(tmp_path):
    """T7: ``_pd_calc_intensity_net`` is a model, never a measurement."""
    p = _write_pdcif(tmp_path / "calc.cif", {
        "_pd_proc_2theta_corrected": _TT, "_pd_calc_intensity_net": _Y})
    with pytest.raises(ValueError, match="no pdCIF pattern block found"):
        rx.read_pattern(p)
