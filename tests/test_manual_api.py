"""Part 1's anti-divergence guards: name resolution, and a coverage partition.

Part 2's guards work because an equation names the symbol it was transcribed
from (`test_manual.py`).  A reference manual fails differently, and this repo
has measured how: ``features["indexing"]`` was ``False`` for its entire life
because the flag's ``hasattr`` name (``index``) and the real export
(``index_pattern``) drifted apart while the meta-test asserted the flag's own
expression rather than the name (WP-1037).  A manual is a much larger surface
of exactly that bug, so what is checked here is **names**:

* every dotted rietx name Part 1 spells resolves against the live package;
* every parameter dot-path matches a real `ParameterTable` (and carries no
  brackets — stage plans glob with fnmatch, where ``[..]`` is a character
  class);
* every fenced ``python`` block parses, and either executes or carries a
  written reason it does not;
* the derived public surface (`tests/api_surface.py`) is **partitioned**:
  every name is documented in a Part 1 chapter, excluded with a reason, or in
  the generated `deferred-1.0.x` bucket — the WP-1003 freeze's **provisional**
  tier, whose names may still change in a 1.0.x release;
* and a name whose subsystem is **declared provisional** (WP-1078's
  ``PROVISIONAL_MODULES``) is documented all the same, on a page that links the
  promise.  Documenting a name freezes it, so the declaration is the only way a
  chapter can cover a subsystem still under development without promising it.

The partition is what stops coverage from silently dropping.  A new public
method is on the derived surface the moment it is written and in none of the
three buckets, so this test fails and names it; the fix is to document it,
exclude it with a reason, or regenerate the deferred file — which is a diff a
reviewer sees.  It tightens from both sides: if the scan for documented names
ever stops matching, those names fall out of every bucket and the partition
fails; if it over-matches, they land in two buckets and it fails too.

**What it does not measure is quality.**  The cheapest way to turn a coverage
partition green is a line reading "`SharingMap` maps sharing".  The bar for
that is the executed examples and human review; this test only stops a name
from being forgotten.
"""

from __future__ import annotations

import ast
import importlib
import re
from fnmatch import fnmatch
from pathlib import Path

import pytest

from rietx import Instrument, PreferredOrientation
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import (
    HUMP_FWHM_MIN,
    HumpComponent,
    PeakComponent,
    RoughnessSuortti,
)
from rietx.schemas.structure import AnisoU, StephensStrain
from tests.api_surface import (
    DEFERRED_CEILING,
    EXCLUDED_TYPES,
    EXCLUSIONS,
    PROVISIONAL_MODULES,
    attr_step,
    declares,
    derive_surface,
    load_deferred,
    provisional_names,
    reachable_types,
    resolve_dotted,
)
from tests.test_coordinates import make_rutile
from tests.test_schemas import make_lab6

REPO_ROOT = Path(__file__).resolve().parent.parent
#: The manual (WP-1978), every tab of it, and since WP-1986 retired the old tree
#: in `docs/manual/` the only one.  A name it spells resolves, and a name it
#: documents counts toward the partition.  Its Theory tab is included: a code
#: span there is a name a reader may type, wherever the page sits.
DOCS_TREE = REPO_ROOT / "docs" / "docs"
PAGES = sorted(p for p in DOCS_TREE.rglob("*.md")
               if not {"_build", "_generated"} & set(p.relative_to(DOCS_TREE).parts))
#: The pages tabulating a closed vocabulary, read by the tests that hold each
#: table to its `Literal`.
PEAKS_PAGE = DOCS_TREE / "reference" / "peaks.md"
INDEXING_PAGE = DOCS_TREE / "reference" / "indexing.md"

CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^```\{?([\w-]+)\}?[^\n]*\n(.*?)^```", re.S | re.M)
LITERALINCLUDE = re.compile(r"^```\{literalinclude\}\s+(\S+)\s*$", re.M)
DOTTED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_*][A-Za-z0-9_*]*)*")
# A block that is not executed says why, on the line above its fence.  A bare
# exemption is how this rots, so the reason is part of the syntax.
NO_EXEC = re.compile(r"<!--\s*api-doc:\s*no-exec\s*[-—]\s*(?P<reason>[^>]+?)\s*-->")

# Roots of a parameter dot-path (`params/vector.py`), as opposed to a dotted
# python name.  The two look alike in a code span and are checked differently.
PATH_ROOTS = ("phases.", "instrument.")
# A dot-path's segments may be indices (`phases.0.cell.a`), which `DOTTED`
# stops at: it cut that path to `phases` and so checked no indexed path (WP-1986).
PATH_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_*]+)*")
# The table checked against is one small model, so an index is read as 0: the
# check is that the path names a real family, not that atom 4 exists there.
INDEX = re.compile(r"(?<=\.)\d+(?=\.|$)")

# The label the compatibility chapter defines and a provisional subsystem's own
# chapter refers to (WP-1078).  A cross-reference rather than a second copy of
# the promise: sphinx `-W` fails on a dangling `{ref}`, so the two halves cannot
# drift the way two paragraphs saying the same thing would.
PROVISIONAL_TARGET = "provisional-by-declaration"
COMPATIBILITY_PAGE = DOCS_TREE / "reference" / "compatibility.md"


def _where(page: Path) -> str:
    """A page's path under `docs/`, since the new tree has an `index.md` per tab."""
    return page.relative_to(REPO_ROOT / "docs").as_posix()


def _pages() -> list[tuple[Path, str]]:
    return [(page, page.read_text(encoding="utf-8")) for page in PAGES]


def _fences(text: str, language: str) -> list[str]:
    return [body for lang, body in FENCE.findall(text) if lang == language]


def _python_blocks(page: Path, text: str) -> list[tuple[str, str | None]]:
    """Each ``python`` fence with its no-exec reason, or None if it executes.

    The marker is the HTML comment on the line above the fence, so a block and
    its exemption cannot drift apart the way a separate list of exempt blocks
    would.
    """
    out: list[tuple[str, str | None]] = []
    for match in re.finditer(r"^```python[^\n]*\n(.*?)^```", text, re.S | re.M):
        preceding = text[: match.start()].rstrip().rsplit("\n", 1)[-1]
        marker = NO_EXEC.search(preceding)
        out.append((match.group(1), marker.group("reason") if marker else None))
    return out


def _included_sources(page: Path, text: str) -> list[str]:
    """The text every `{literalinclude}` shows: the file, or the slice its options cut.

    The walkthroughs are `examples/` scripts shown verbatim (WP-1067: one
    authority, and it is `examples/`), so what a script spells is what a
    reader of the chapter sees.
    """
    sources = []
    for match in LITERALINCLUDE.finditer(text):
        target = match.group(1)
        path = (page.parent / target).resolve()
        assert path.exists(), f"{_where(page)}: literalinclude target does not exist: {target}"
        sources.append(_included_slice(path.read_text(encoding="utf-8"),
                                       text[match.end():], page, target))
    return sources


def _included_slice(source: str, after: str, page: Path, target: str) -> str:
    """The lines of ``source`` the directive's options show, as Sphinx cuts them.

    A reader sees the slice, so a name elsewhere in the file is not one the
    page wrote.  Sphinx keeps or drops a marker's whole line
    (`LiteralIncludeReader.start_filter`/`end_filter`), so the cut is by line:
    `start-at` wins over `start-after`, `end-at` over `end-before`, and
    `end-before` never matches the slice's first line.  An option that slices
    some other way is refused, since reading it as the whole file would credit
    the page with names it does not show.
    """
    options = dict(re.findall(r"^:([a-z-]+):[ \t]*(.*)$",
                              after.split("```", 1)[0], re.M))
    unread = sorted({"lines", "pyobject", "start-line", "end-line"} & options.keys())
    assert not unread, (f"{_where(page)}: {target} slices by :{unread[0]}:, "
                        "which this guard does not read")

    def marker(key: str) -> str:
        value = options[key]
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]  # MyST reads an option as YAML, quotes and all
        return value

    def line_of(lines: list[str], key: str, skip_first: bool = False) -> int:
        text = marker(key)
        at = next((i for i, line in enumerate(lines)
                   if text in line and not (skip_first and i == 0)), None)
        assert at is not None, f"{_where(page)}: {target} has no :{key}: {text!r}"
        return at

    lines = source.splitlines(keepends=True)
    if "start-at" in options:
        lines = lines[line_of(lines, "start-at"):]
    elif "start-after" in options:
        lines = lines[line_of(lines, "start-after") + 1:]
    if "end-at" in options:
        lines = lines[:line_of(lines, "end-at") + 1]
    elif "end-before" in options:
        lines = lines[:line_of(lines, "end-before", skip_first=True)]
    return "".join(lines)


def _code_text(page: Path, text: str) -> str:
    """Everything on a page that is code: spans, python fences, includes.

    Prose is deliberately not scanned.  "the Structure schema" in a sentence is
    not documentation of `Structure`, and matching it would make the partition
    satisfiable by accident.
    """
    parts = [
        *CODE_SPAN.findall(text),
        *_fences(text, "python"),
        *_included_sources(page, text),
    ]
    return "\n".join(parts)


def documented_names() -> set[str]:
    """Surface names a Part 1 chapter spells, in code, qualified.

    Qualified: a chapter documents `Statistics.rwp` by naming it, not by
    showing ``result.statistics.rwp`` — an expression cannot be attributed to a
    type without inferring one, and a reference chapter names the type anyway.
    A leading ``rietx.`` is stripped, so ``rietx.read_pattern`` and
    ``read_pattern`` are one name.

    **The blind spot, and it is not fixable here.**  This counts a name as
    documented wherever it is *spelled*, and
    :func:`test_every_dotted_name_resolves` checks the same name against the
    package — so a paragraph describing type A that spells type B's member
    passes both and freezes B's name.  Measured: ``report.md`` documented
    ``FitReport.identifiability`` as an ``Identifiability`` for the whole of
    v1.0.0-1.0.1, when it is an ``IdentifiabilityEvidence``; the two share
    ``top_correlations`` and ``soft_modes``, so every check was green and three
    names froze against the wrong type (WP-1067's closing handover).  Catching
    it needs a reading — check each spelled name against the type the paragraph
    is *about* — which is why it is written here rather than asserted.  Pairs of
    this shape today: the two identifiability blocks, ``Statistics`` against
    ``BackgroundEvidence`` (both carry ``rwp``), and ``StageReport`` against
    ``StageResult``.

    The same session found the other half of it: two docstrings that
    contradicted their own code (``report.layer1._trends`` claiming a joint fit,
    ``schemas.indexing``'s ``not_validated`` claiming one cause of two), each
    faithfully transcribed into a chapter.  A chapter is drafted from a
    docstring, so **read the code beside it**; nothing in this file can.
    """
    surface = derive_surface()
    found: set[str] = set()
    for page, text in _pages():
        for token in DOTTED.findall(_code_text(page, text)):
            name = token.removeprefix("rietx.")
            if name in surface:
                found.add(name)
    return found


def _fully_declared() -> tuple[object, object]:
    """LaB6 with every *optional* block declared, and an instrument to match.

    Preferred orientation, Stephens strain, surface roughness and additive
    background peaks contribute no dot-paths at all unless the model declares
    the block, so a manual naming `phases.*.preferred_orientation.r` would fail
    the check below against a plain model — for the right reason, on a real
    path.  Declaring them here is what lets Part 1 name the parameters those
    corrections actually refine.
    """
    structure = make_lab6()
    phase = structure.phases[0]
    aniso = AnisoU(u11=Parameter(value=0.006, unit="A^2"),
                   u22=Parameter(value=0.006, unit="A^2"),
                   u33=Parameter(value=0.006, unit="A^2"))
    atoms = [phase.atoms[0].model_copy(update={"aniso": aniso}), *phase.atoms[1:]]
    structure = structure.model_copy(update={"phases": [phase.model_copy(update={
        "atoms": atoms,
        "preferred_orientation": PreferredOrientation(axis=(0, 0, 1), r=Parameter(value=1.0)),
        "microstrain": StephensStrain.isotropic(1e-3, phase.cell),
    })]})
    instrument = Instrument.debye_scherrer(wavelength=0.4139)
    geometry = instrument.geometry.model_copy(
        update={"surface_roughness": RoughnessSuortti(b=Parameter(value=0.2))})
    peak = HumpComponent(position=Parameter(value=12.0, unit="deg"),
                          height=Parameter(value=0.0, min=0.0,
                                           transform="softplus"),
                          fwhm=Parameter(value=6.0,
                                         min=HUMP_FWHM_MIN,
                                         transform="softplus"))
    # paths are compared with every index read as 0, so the second member's
    # `extra_components.1.center` answers for a page's `.0.center`
    line = PeakComponent(center=Parameter(value=44.6, min=44.4, max=44.9, unit="deg"))
    return structure, instrument.model_copy(
        update={"geometry": geometry, "extra_components": [peak, line]})


def _magnetic() -> tuple[object, object]:
    """Rutile with a moment on the Ti site, under a P 4₂/mnm-derived MSG.

    Same reason as :func:`_fully_declared` one function up: a moment block
    contributes no dot-paths at all unless a phase declares one, so a manual
    naming ``phases.*.atoms.*.moment.dof*`` would fail the check below against
    every plain model — for the right reason, on a real path.  A neutron
    instrument, because that is the only radiation the term reaches.
    """
    from rietx.schemas.structure import MagneticSymmetry, Moment

    structure = make_rutile()
    phase = structure.phases[0]
    atoms = [phase.atoms[0].model_copy(update={
        "moment": Moment.from_values((0.0, 0.0, 4.6), "Ti3+")}), *phase.atoms[1:]]
    return (structure.model_copy(update={"phases": [phase.model_copy(update={
        "atoms": atoms,
        # built rather than assigned: ``model_copy(update=…)`` does not
        # revalidate, so the number-as-input shorthand would stay a string
        "magnetic_symmetry": MagneticSymmetry.model_validate("136.499")})]}),
        Instrument.constant_wavelength_neutron(2.4))


from rietx.schemas.instrument import IncidentSpectrum  # noqa: E402


def _distortion():
    """A child on mode amplitudes (WP-1419), for the same reason as the two above:
    ``phases.*.distortion_modes.modes.*.amplitude`` exists on no other table."""
    from rietx.schemas.structure import Structure
    from tests.test_help import _distortion_phase

    return Structure(phases=[_distortion_phase()])


def _parameter_paths() -> set[str]:
    """Every dot-path four representative models put on the table.

    LaB6 (cubic, tied cell, locked special positions), rutile with free
    coordinates — which is what puts `…atoms.*.dof.*` paths in reach — the
    fully-declared LaB6 above for the optional correction blocks, a magnetic
    rutile for the moment DOFs, and a ``neutron_tof`` bank, whose calibration
    and ``ProfileTOF`` coefficients (``instrument.source.difc``,
    ``instrument.source.profile_tof.gam0`` …) exist on no constant-wavelength
    table.
    """
    plain = Instrument.debye_scherrer(wavelength=0.4139)
    bank = Instrument.tof_neutron_bank(difc=12000.0, two_theta_bank_deg=90.0)
    # a declared spectrum, since ITYP 0 (the default) has no coefficient rows
    bank.source.incident_spectrum = IncidentSpectrum(
        itype=3, coefficients=[Parameter(value=1.0)] * 12)
    models = [(make_lab6(), plain), (make_rutile(vary_coords=True), plain),
              _fully_declared(), _magnetic(), (make_lab6(), bank),
              (_distortion(), plain)]
    paths: set[str] = set()
    for structure, instrument in models:
        paths.update(entry.path for entry in ParameterTable(structure, instrument).entries)
    return paths


# --- names ----------------------------------------------------------------


# The two hops below moved to tests/api_surface.py in WP-1304, where the skill
# tree's API index asks the same question of a second document.
def _step(obj: object, attr: str) -> tuple[bool, object]:
    return attr_step(obj, attr)


def _resolve_absolute(page: Path, dotted: str) -> None:
    resolve_dotted(dotted, _where(page))


def test_every_dotted_name_resolves():
    """A dotted rietx name in Part 1 imports and attributes out.  This is the
    WP-1037 bug's shape: the manual says `index`, the package exports
    `index_pattern`, and nothing notices.

    Resolution starts from the derived type registry, not from `rietx`:
    `Statistics` and `Capabilities` are reachable and documented types that
    `__all__` does not export, and traversing from the package would refuse
    them for the wrong reason.
    """
    surface = derive_surface()
    types_by_name = reachable_types()
    roots = {name.split(".")[0] for name in surface}
    rietx = importlib.import_module("rietx")
    for page, text in _pages():
        for token in DOTTED.findall(_code_text(page, text)):
            if token.startswith("rietx.") and token not in surface:
                # A fully-spelled name is always checkable, module path and
                # all: `rietx.viz.compare.run` reaches past `__all__`, and
                # `rietx.viz` is not even an attribute until something imports
                # it, so resolution walks the longest importable prefix first.
                _resolve_absolute(page, token)
                continue
            dotted = token.removeprefix("rietx.")
            if "." not in dotted or dotted.startswith(PATH_ROOTS) or dotted in surface:
                continue
            head, _, tail = dotted.partition(".")
            if head not in roots:
                continue
            obj = types_by_name.get(head) or getattr(rietx, head, None)
            assert obj is not None, f"{_where(page)}: `{token}` — nothing named {head!r}"
            for attr in tail.split("."):
                ok, obj = _step(obj, attr)
                assert ok, f"{_where(page)}: `{token}` — {head} has no member {attr!r}"
                if obj is None:  # a field of a non-rietx type: nothing further to walk
                    break


RX_DOT_NAME = re.compile(r"\brx\.([A-Za-z_][A-Za-z0-9_]*)\b")


def test_every_rx_dot_name_is_exported():
    """A bare ``rx.X`` in Part 1 must be a real top-level export (WP-1302).

    Stricter than :func:`test_every_dotted_name_resolves`, which is happy
    with a deeper path (``rietx.io.readers.PATTERN_FORMATS``) that ``rx.``
    was never meant to reach: writing ``rx.X`` in a chapter is the promise
    that a reader can do the same, and ``__init__.py``'s derived re-exports
    exist so that promise holds without the two drifting apart (the gap this
    closed: ``Source``, ``EmissionLine``, ``BackgroundChebyshev`` and more
    were named throughout ``data.md`` unqualified while unimportable).
    """
    import rietx as rx

    missing = {(_where(page), name)
               for page, text in _pages()
               for name in RX_DOT_NAME.findall(_code_text(page, text))
               if name not in rx.__all__}
    assert not missing, sorted(missing)


def test_imports_shown_in_part_one_exist():
    """`from rietx import capabilities` in a chapter names something the
    package exports.  A bare name is not dotted, so the resolver above cannot
    see it, and an executed block would only catch it if the block runs — this
    catches it in a block that is exempt, and in a code span."""
    pattern = re.compile(r"from\s+(rietx[\w.]*)\s+import\s+([^\n(]+)")
    for page, text in _pages():
        for module_name, names in pattern.findall(_code_text(page, text)):
            module = importlib.import_module(module_name)
            for name in (part.strip() for part in names.split(",")):
                if not name:
                    continue
                imported = name.split(" as ")[0].strip()
                # `from rietx.viz import compare` is a *submodule* import,
                # legal whether or not the parent re-exports it — and hasattr
                # sees a submodule only after something has imported it, which
                # made this assertion depend on xdist test placement.
                if not hasattr(module, imported):
                    try:
                        importlib.import_module(f"{module_name}.{imported}")
                        continue
                    except ModuleNotFoundError:
                        pass
                assert hasattr(module, imported), (
                    f"{_where(page)}: `from {module_name} import {imported}` — "
                    f"{module_name} exports no {imported!r}"
                )


def test_every_figure_reference_exists():
    """A manual figure is a committed file, not a build product, so a renamed
    or unregenerated one is a broken image and nothing else notices: sphinx
    warns on a missing image, but the figures are generated by
    `docs/docs/make_figures.py` and a stale reference to a file that still
    exists builds clean and shows the wrong picture.  This catches the half a
    build can catch, by name."""
    for page, target in _image_targets():
        assert (page.parent / target).exists(), f"{_where(page)}: missing image: {target}"


def _image_targets() -> list[tuple[Path, str]]:
    """Each local image a page shows, as (page, target)."""
    found = []
    for page, text in _pages():
        targets = [
            *re.findall(r"^```\{(?:image|figure)\}\s+(\S+)\s*$", text, re.M),
            *re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", text),
        ]
        found += [(page, t) for t in targets if not t.startswith(("http://", "https://"))]
    return found


def test_nothing_gitignores_a_shown_image():
    """The repo-wide `*.png` rule swallows a committed image directory unless an
    un-ignore line names it, and the figures moved directory (WP-1986).

    The existence check above passes on the machine that drew the figures
    whatever `.gitignore` says, and a fresh clone then has broken images.  This
    asks git, with `--no-index` because check-ignore answers for a tracked file
    from the index without reading the rules.  A match counts only when its rule
    is not a negation, the shape `test_gui_manual.py`'s screenshot guard reads,
    so no `.gitignore` line is copied here (`tests/CLAUDE.md`).
    """
    import subprocess

    files = sorted({(page.parent / target).resolve().relative_to(REPO_ROOT).as_posix()
                    for page, target in _image_targets()})
    assert files, "no page shows a local image: the image regexes or the pages moved"
    result = subprocess.run(
        ["git", "check-ignore", "-v", "-z", "--no-index", "--stdin"],
        input="\0".join(files) + "\0", cwd=REPO_ROOT, capture_output=True,
        text=True, encoding="utf-8", check=False,
    )
    assert result.returncode in (0, 1), f"git check-ignore failed: {result.stderr}"
    fields = result.stdout.split("\0")[:-1]
    ignored = [path for source, line, pattern, path in zip(*[iter(fields)] * 4)
               if not pattern.startswith("!")]
    assert not ignored, f"images a page shows are gitignored: {ignored}"


def test_every_closed_vocabulary_member_is_named_where_its_table_is():
    """A closed `Literal` Part 1 tabulates is tabulated whole.

    The failure this exists for is not a missing row, which a reader notices.
    It is the **count in the sentence above the table**, which nobody
    recomputes: the old `using/indexing.md` read "Five of the twelve take a line out of
    `PeakList.usable`" while `PeakFlag` held fourteen members and
    `PEAK_UNUSABLE_FLAGS` six, so both numbers were wrong and had been since the
    vocabulary last grew (WP-1409).  `-W` cannot see it, `test_help.py` covers
    the help corpus rather than the manual's prose, and a reader has no way to
    know the sentence was ever true.

    So the members are the authority and the page is checked against them, both
    ways: the members are read off the live `Literal`, and a member the page
    never names in code font fails here.  The three below are the ones Part 1
    tabulates row by row.
    `EXEMPT` carries the members a page deliberately describes elsewhere, with
    the reason, which is the only way this test is satisfied without a row.

    Membership alone does not close the failure this exists for, though.  A
    fifteenth `PeakFlag` with a row of its own satisfies every check above
    while "a closed vocabulary of fourteen" stands untouched one line higher,
    so `test_the_flag_counts_in_the_prose_are_the_live_counts` reads the
    counts themselves.
    """
    import typing

    from rietx.schemas.indexing import Confidence, IndexCaveat, PeakFlag

    # vocabulary -> (page, members deliberately covered somewhere else)
    VOCABULARIES = {
        "PeakFlag": (PeakFlag, PEAKS_PAGE, {}),
        "IndexCaveat": (IndexCaveat, INDEXING_PAGE, {}),
        "Confidence": (Confidence, INDEXING_PAGE, {}),
    }
    for name, (literal, page, exempt) in VOCABULARIES.items():
        members = set(typing.get_args(literal))
        assert members, f"{name} is not a Literal of strings"
        page_name = page.name
        text = page.read_text(encoding="utf-8")
        spelled = set(CODE_SPAN.findall(text))
        missing = sorted(members - spelled - set(exempt))
        assert not missing, (
            f"{page_name} never names {name} member(s) {missing}. A closed "
            f"vocabulary the page tabulates is tabulated whole, and the count "
            f"in the sentence above the table is the thing that rots."
        )
        for member, reason in exempt.items():
            assert member in members, (
                f"{name} no longer has {member!r}, so its exemption in this "
                f"test is stale: {reason}"
            )


def test_the_peak_flag_table_marks_exactly_the_unusable_flags():
    """`reference/peaks.md`'s flag table has a "Usable?" column, and it is the
    same partition `PEAK_UNUSABLE_FLAGS` is.

    The table is the reader's copy of a frozenset in `schemas/indexing.py`, and
    a flag that changes side there is a row that now says the opposite of what
    the package does.  Read off the rendered row rather than off a count, so
    the guard survives the prose above it being rewritten (WP-1409).

    The row pattern is deliberately held to the live vocabulary as well.  A cell
    may carry an escaped pipe (`\\|F\\|²` is how this manual writes one), and
    such a row does not match the pattern at all — the partition above would
    then pass while quietly checking one flag fewer, which is the failure the
    `assert rows` line alone cannot see.
    """
    import typing

    from rietx.schemas.indexing import PEAK_UNUSABLE_FLAGS, PeakFlag

    members = set(typing.get_args(PeakFlag))
    text = PEAKS_PAGE.read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([a-z_0-9]+)` \|[^|]*\| (yes|no) \|\s*$", text, re.M)
    assert rows, "the peak-flag table is gone from peaks.md"
    said_unusable = {flag for flag, usable in rows if usable == "no"}
    tabulated = {flag for flag, _ in rows}
    assert tabulated <= members, (
        f"peaks.md tabulates {sorted(tabulated - members)}, "
        f"which PeakFlag does not hold"
    )
    assert said_unusable == PEAK_UNUSABLE_FLAGS & tabulated, (
        f"peaks.md's Usable? column says {sorted(said_unusable)} are "
        f"unusable; PEAK_UNUSABLE_FLAGS says "
        f"{sorted(PEAK_UNUSABLE_FLAGS & tabulated)}"
    )
    assert len(rows) == len(tabulated), "a flag is tabulated twice"
    assert PEAK_UNUSABLE_FLAGS <= tabulated, (
        f"every unusable flag earns a row, and "
        f"{sorted(PEAK_UNUSABLE_FLAGS - tabulated)} has none. Either the row "
        f"is missing, or it carries an escaped pipe and stopped matching"
    )


#: Cardinals and ordinals up to twenty, which is as far as a vocabulary count in
#: this manual has ever had to reach.
_COUNT_WORDS = {
    word: value
    for words in (
        "one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty",
        "first second third fourth fifth sixth seventh eighth ninth tenth "
        "eleventh twelfth thirteenth fourteenth fifteenth sixteenth "
        "seventeenth eighteenth nineteenth twentieth",
    )
    for value, word in enumerate(words.split(), 1)
}


def test_the_flag_counts_in_the_prose_are_the_live_counts():
    """The sentence above the flag table counts, and the counts are checked.

    This is the failure `test_every_closed_vocabulary_member_is_named_where_
    its_table_is` was written for and does not reach: a member arriving with a
    row of its own leaves every membership check green while "a closed
    vocabulary of fourteen" one line higher goes stale, and nobody recomputes
    it (WP-1409 found "Five of the twelve" against a vocabulary of fourteen).

    Written against the counts rather than the sentence, so the prose stays
    free to reword: every number the paragraph spells has to be one of the
    counts the vocabulary actually supports.  A count that stops being one of
    them is a number the page no longer has a reason to carry.
    """
    import typing

    from rietx.schemas.indexing import PEAK_UNUSABLE_FLAGS, PeakFlag

    members = typing.get_args(PeakFlag)
    text = PEAKS_PAGE.read_text(encoding="utf-8")
    section = text.split("### The flags", 1)
    assert len(section) == 2, "peaks.md lost its '### The flags' section"
    flags_section = re.split(r"^#{1,3} ", section[1], maxsplit=1, flags=re.M)[0]
    prose = flags_section.split("\n| Flag |", 1)[0]
    n_rows = len(re.findall(r"^\| `[a-z_0-9]+` \|", flags_section, re.M))

    live = {
        len(members),                                  # the whole vocabulary
        len(PEAK_UNUSABLE_FLAGS),                      # the unusable half
        len(members) - len(PEAK_UNUSABLE_FLAGS),       # the evidence half
        n_rows,                                        # what the table carries
        len(members) - n_rows,                         # what it does not
    }
    spelled = {
        word: _COUNT_WORDS[word]
        for word in re.findall(r"[a-z]+", prose.lower())
        if word in _COUNT_WORDS
    }
    stale = {word: value for word, value in spelled.items() if value not in live}
    assert not stale, (
        f"§ The flags counts {stale}, and PeakFlag supports only {sorted(live)} "
        f"({len(members)} members, {len(PEAK_UNUSABLE_FLAGS)} unusable, "
        f"{n_rows} tabulated). The vocabulary grew and the sentence did not."
    )


def test_parameter_dot_paths_resolve():
    """Every dot-path or glob Part 1 spells matches a real ParameterTable, and
    carries no brackets: stage plans match with fnmatch, where `[..]` is a
    character class rather than an index (root CLAUDE.md § Conventions)."""
    paths = {INDEX.sub("0", path) for path in _parameter_paths()}
    for page, text in _pages():
        # tokens *inside* a span, not whole spans: a path is usually quoted in
        # a call — `result.parameter("phases.0.cell.a")` — and checking only
        # spans that are paths outright would skip exactly those.
        for token in PATH_TOKEN.findall("\n".join(CODE_SPAN.findall(text))):
            if not token.startswith(PATH_ROOTS):
                continue
            assert "[" not in token and "]" not in token, (
                f"{_where(page)}: parameter path `{token}` uses brackets; fnmatch reads them "
                "as a character class"
            )
            assert any(fnmatch(path, INDEX.sub("0", token)) for path in paths), (
                f"{_where(page)}: parameter path `{token}` matches nothing on a real table"
            )


# --- examples -------------------------------------------------------------


def test_every_python_block_parses():
    """Free, and it catches the typo class immediately — including in a block
    that is exempt from execution."""
    for page, text in _pages():
        for block, _ in _python_blocks(page, text):
            try:
                ast.parse(block)
            except SyntaxError as exc:  # pragma: no cover - the message is the point
                pytest.fail(f"{_where(page)}: python block does not parse: {exc}")


def test_python_blocks_execute_or_say_why():
    """A block that only builds objects or reads fields runs here, against the
    bundled fixtures.  A block that refines does not exist as inline prose at
    all — it is a `{literalinclude}` of an `examples/` script, executed by
    `tests/test_examples.py` on the acceptance cadence (WP-1067's cost model,
    under `tests/CLAUDE.md`'s rule that a wall-clock budget in a test is a
    runaway guard and never a timer).  Anything else carries a reason, because
    a bare exemption is how this rots."""
    for page, text in _pages():
        for block, reason in _python_blocks(page, text):
            if reason is not None:
                assert len(reason.split()) >= 3, f"{_where(page)}: no-exec reason is a shrug: {reason}"
                continue
            try:
                exec(compile(block, f"{_where(page)}:python", "exec"), {"__name__": "manual_block"})
            except Exception as exc:  # pragma: no cover - the message is the point
                pytest.fail(
                    f"{_where(page)}: python block raised {type(exc).__name__}: {exc}\n"
                    f"--- block ---\n{block}\n"
                    "Add `<!-- api-doc: no-exec — <reason> -->` above it if it cannot run."
                )


# --- the partition --------------------------------------------------------


def test_derived_surface_is_partitioned():
    """Every public name is documented, excluded with a reason, or deferred.

    Fails on a name in none of the three (a new public method nobody
    documented) and on a name in two (a deferred name a chapter has since
    documented, with the generated bucket not regenerated).
    """
    surface = set(derive_surface())
    documented = documented_names()
    deferred = set(load_deferred())

    missing = surface - documented - deferred
    assert not missing, (
        f"{len(missing)} public name(s) in no bucket — document them in a Part 1 chapter, "
        "exclude them with a reason in tests/api_surface.py, or defer them with "
        f"`python -m tests.api_surface --write-deferred`: {sorted(missing)[:20]}"
    )
    overlap = documented & deferred
    assert not overlap, (
        f"{len(overlap)} name(s) both documented and deferred — regenerate the bucket with "
        f"`python -m tests.api_surface --write-deferred`: {sorted(overlap)[:20]}"
    )


def test_deferred_bucket_does_not_grow():
    """A ratchet: the bucket may shrink in any change and grow in none.

    `DEFERRED_CEILING` is lowered at each release cut, not here, so a change
    that documents names never has to edit it.
    """
    count = len(load_deferred())
    assert count <= DEFERRED_CEILING, (
        f"{count} names deferred, over the ceiling of {DEFERRED_CEILING}. Document the "
        "new names in a manual page, or exclude them with a reason in tests/api_surface.py. "
        "Raising DEFERRED_CEILING is a reviewed edit that says why in its commit."
    )


def test_deferred_bucket_has_no_stale_names():
    """A deferred name that no longer exists is a rename the bucket slept
    through — the failure mode the whole derivation exists to prevent."""
    surface = set(derive_surface())
    stale = [name for name in load_deferred() if name not in surface]
    assert not stale, f"deferred names no longer on the surface: {stale}"


# --- the third tier: documented, and declared provisional -----------------


REF_ROLE = re.compile(r"\{ref\}`([^`]*)`")


def _referenced_labels(text: str) -> set[str]:
    """The labels a page's `{ref}` roles point at, plain or `title <label>`."""
    labels = set()
    for body in REF_ROLE.findall(text):
        match = re.search(r"<([^>]+)>", body)
        labels.add((match.group(1) if match else body).strip())
    return labels


def test_provisional_modules_are_live_and_reasoned():
    """A declaration that matches no surface name is a module rename with a
    dead promise attached, and an empty reason is a shrug — the same bar the
    exclusions carry, for the same reason: the tier is data, so an entry that
    stopped meaning anything has to fail rather than sit there (WP-1078)."""
    surface = derive_surface()
    for prefix, reason in PROVISIONAL_MODULES.items():
        assert len(reason.split()) >= 5, f"{prefix}: declaration carries no real reason"
        covered = [name for name, entry in surface.items() if declares(entry.module, prefix)]
        assert covered, f"{prefix}: declared provisional but defines nothing on the surface"


def test_provisional_names_are_documented():
    """Provisional is a weaker *promise*, never thinner coverage.

    A subsystem under development is exactly the one a reader needs a reference
    for, so a declared name is still documented — this fails if a chapter drops
    one, which the partition alone would not catch: an undocumented name can
    sit in the deferred bucket instead and stay green.
    """
    provisional = provisional_names()
    assert provisional, "no name is provisional — the declaration reaches nothing"
    undocumented = provisional - documented_names()
    assert not undocumented, (
        f"{len(undocumented)} provisional name(s) no chapter documents: "
        f"{sorted(undocumented)[:20]}"
    )


def test_the_provisional_promise_reaches_the_chapters_that_document_it():
    """The declaration is in the compatibility chapter, and every provisional
    name is documented on a page that points at it.

    Derived rather than a list of page names: a chapter that documents a
    provisional name without linking the promise leaves a reader believing the
    documented tier applies, which is what it says everywhere else.  The link
    is a `{ref}` to one label, so the `-W` build fails on a dangling one and
    this test fails on a missing one — neither is a second copy of the promise,
    which is how a guard of this shape goes quiet (`tests/CLAUDE.md`).
    """
    compatibility = COMPATIBILITY_PAGE.read_text(encoding="utf-8")
    assert f"({PROVISIONAL_TARGET})=" in compatibility, (
        f"compatibility.md defines no `{PROVISIONAL_TARGET}` target for the chapters to link"
    )
    declared = {
        token
        for token in DOTTED.findall(_code_text(COMPATIBILITY_PAGE, compatibility))
        if token in PROVISIONAL_MODULES
    }
    assert declared == set(PROVISIONAL_MODULES), (
        "compatibility.md does not name every declared-provisional module: "
        f"missing {sorted(set(PROVISIONAL_MODULES) - declared)}"
    )

    provisional = provisional_names()
    told: set[str] = set()
    for page, text in _pages():
        if PROVISIONAL_TARGET not in _referenced_labels(text):
            continue
        told |= {t.removeprefix("rietx.") for t in DOTTED.findall(_code_text(page, text))}
    untold = provisional - told
    assert not untold, (
        f"{len(untold)} provisional name(s) documented only on pages that never link "
        f"`{PROVISIONAL_TARGET}`: {sorted(untold)[:20]}"
    )


def test_only_constants_lack_a_defining_module():
    """`Entry.module` is what the declaration is resolved against, so a kind
    that quietly stops carrying one would shrink the tier with every test
    green.  A constant is the one kind that legitimately has none — it is a
    dict bound in one module and imported into three — and there are two."""
    unattributed = {name: e.kind for name, e in derive_surface().items() if e.module is None}
    assert set(unattributed.values()) <= {"constant"}, (
        f"surface entries with no defining module: {sorted(unattributed)}"
    )


def test_exclusions_are_live_and_reasoned():
    """An exclusion that matches nothing is a rename with a dead reason
    attached, and an empty reason is a shrug.  Checked against the surface
    derived *without* exclusions, which is the only place an excluded name is
    still visible."""
    unfiltered = set(derive_surface(apply_exclusions=False))
    filtered = set(derive_surface())
    for name, reason in {**EXCLUDED_TYPES, **EXCLUSIONS}.items():
        assert len(reason.split()) >= 5, f"{name}: exclusion carries no real reason"
    for name in EXCLUSIONS:
        assert "." in name, f"{name}: member exclusions are qualified (Type.member)"
        assert name in unfiltered, f"{name}: excluded name is not on the surface at all"
        assert name not in filtered, f"{name}: excluded but still derived"
    for name in EXCLUDED_TYPES:
        assert name in unfiltered, f"{name}: excluded type is not on the surface at all"
        assert name not in filtered, f"{name}: excluded type still on the surface"
