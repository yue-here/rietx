"""WP-1204 — the example projects shipped in the wheel.

Not ``test_examples.py``, which runs the ``examples/`` scripts the manual
``{literalinclude}``s.  These are ``.rex`` *projects* built from packaged data
for the GUI's empty state.

Nothing here fits anything: a build is a :meth:`Project.create`, so the whole
suite is milliseconds and carries no ``slow`` mark.  What it asserts is that
each project records the protocol its standard declares — a project whose plan
or excluded regions quietly differed would put a user's first refinement on a
protocol no acceptance suite measures.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.examples import (
    DESCRIPTIONS,
    ExampleInfo,
    build_example,
    examples_dir,
    list_examples,
)
from rietx.schemas.plan import CLOSING_WINDOW_TOL, PlanSpec
from rietx.viz.compare import STANDARD_BY_KEY

EXAMPLES = list_examples()
NAMES = [e.name for e in EXAMPLES]

#: Why every shipped file may be redistributed, quoted from
#: ``tests/data/README.md``.  A hand-written table on purpose, and the one
#: place in this package where that is the right shape: the point is that a
#: file cannot enter the wheel without someone stating its licence.  The IUCr
#: CPD round-robin patterns carry no explicit licence and are already excluded
#: from the sdist, which is why the four pure-phase standards built on them are
#: not examples however small and useful they are.  SRM 660c is out for a
#: different reason and it is not a licence one — see `rietx.examples`' own
#: comment: its pattern is 24 scan windows and reads as broken data to someone
#: who does not know that.
LICENCES = {
    "11BM_NAC.fxye": "Argonne/APS tutorial data (U.S. Government work)",
    "cod_1000236.cif": "COD (public domain dedication)",
    "FAP.XRA": "Argonne/APS tutorial data (U.S. Government work)",
    # The same tutorial and the same fence as FAP.XRA beside it.  It ships
    # because the fap standard *reads its protocol from it* (WP-1118) rather
    # than restating the numbers, so the file is an input and not a reference.
    "FAP.EXP": "Argonne/APS tutorial data (U.S. Government work)",
    # Transcribed from FAP.EXP, so the same fence again.
    "fluorapatite.cif": "Argonne/APS tutorial data (U.S. Government work)",
}

#: Shipped for the tutorial notebooks (WP-1545) and read by no standard.  A
#: tutorial starts from a CIF because a reader's own phase arrives as one, and
#: `_build_fap` reads its structure from FAP.EXP.  Listing it in the standard's
#: `files` would declare an input the build never opens.
TUTORIAL_ONLY = {"fluorapatite.cif"}


def test_this_build_carries_examples():
    """A guard against the whole suite passing vacuously if the data directory
    failed to ship: every assertion below is parametrised over the list."""
    assert NAMES, "no examples shipped — check src/rietx/data/examples/"


def test_the_list_is_in_bijection_with_the_data_directory():
    """The list is *derived* from the directory (``Standard.available``), so
    the failure this catches is a file with no example rather than the other
    way round — an input copied in for a standard that cannot ship, or one left
    behind by a standard that was removed."""
    on_disk = {str(p.relative_to(examples_dir()))
               for p in examples_dir().rglob("*") if p.is_file()}
    claimed = {f for name in NAMES for f in STANDARD_BY_KEY[name].files}
    assert on_disk == claimed | TUTORIAL_ONLY


def test_a_tutorial_only_file_has_a_tutorial():
    """The other half of the exemption above: a file kept for the tutorials
    is still read by one, or it is a file with no user."""
    tutorials = Path(__file__).resolve().parent.parent / "examples" / "tutorials"
    import importlib.util
    spec = importlib.util.spec_from_file_location("_tutorials_build", tutorials / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    text = "".join(p.read_text(encoding="utf-8") for p in build.sources(tutorials))
    assert [f for f in sorted(TUTORIAL_ONLY) if f not in text] == []


def test_every_shipped_file_has_a_stated_licence():
    """Ship-ability is a licence question, not a size one."""
    on_disk = {str(p.relative_to(examples_dir()))
               for p in examples_dir().rglob("*") if p.is_file()}
    assert on_disk == set(LICENCES)
    assert not [f for f in on_disk if f.startswith("qarr/")], (
        "the IUCr CPD round-robin patterns carry no explicit licence and are "
        "kept out of the sdist; a wheel on PyPI publishes them harder still")


def test_every_example_has_a_description_and_every_description_an_example():
    """``DESCRIPTIONS`` is the one hand-written half of ``ExampleInfo``, so it
    is the half that can drift."""
    assert set(DESCRIPTIONS) == set(NAMES)
    for e in EXAMPLES:
        assert e.description == DESCRIPTIONS[e.name]
        assert e.title == STANDARD_BY_KEY[e.name].title
        assert e.bytes > 0


def test_example_info_says_what_the_files_actually_weigh():
    for e in EXAMPLES:
        want = sum((examples_dir() / f).stat().st_size
                   for f in STANDARD_BY_KEY[e.name].files)
        assert e.bytes == want


@pytest.mark.parametrize("name", NAMES)
def test_an_example_records_the_protocol_its_standard_declares(name, tmp_path):
    """Field by field against ``build()``'s own answer, which is what
    ``tests/test_compare_ui.py`` pins to the acceptance suites.  Two copies
    would be one too many; this asserts there is only one."""
    inputs = STANDARD_BY_KEY[name].build(examples_dir())
    project = build_example(name, tmp_path)

    assert project.path == tmp_path / f"{name}.rex"
    assert project.doc.mode == "rietveld"
    assert project.doc.two_theta_limits == inputs.two_theta_limits
    assert [tuple(r) for r in project.doc.excluded_regions] == \
           [tuple(r) for r in inputs.data.excluded_regions]
    # every plan field the standard's, bar the closing stage: a first fit runs
    # the package default there, and the standard declares its suite's (WP-2036)
    got = project.doc.plan.model_dump()
    want = PlanSpec.from_plan(inputs.plan).model_dump()
    assert want["closing_window_tol"] == CLOSING_WINDOW_TOL
    assert got.pop("closing_window_tol") == rx.RefinementPlan(stages=[]).closing_window_tol
    want.pop("closing_window_tol")
    assert got == want

    # the reader *call*, not merely the bytes: a pdCIF with a _meas and a _calc
    # block is a different pattern depending on `block`
    assert dict(project.data_ref.options) == dict(
        STANDARD_BY_KEY[name].reader_options)


@pytest.mark.parametrize("name", NAMES)
def test_an_example_fits_the_channels_its_protocol_leaves(name, tmp_path):
    """``fitted_mask`` is the one authority for which channels the next run
    fits, and it is where the limits and exclusions become a number.  On the
    fluorapatite example that number is GSAS's own 5750, which is what makes
    the two codes' agreement indices comparable at all."""
    inputs = STANDARD_BY_KEY[name].build(examples_dir())
    project = build_example(name, tmp_path)

    kept = np.asarray(inputs.data.two_theta, dtype=float)
    if inputs.two_theta_limits is not None:
        lo, hi = inputs.two_theta_limits
        kept = kept[(kept >= lo) & (kept <= hi)]
    for lo, hi in inputs.data.excluded_regions:
        kept = kept[(kept < lo) | (kept > hi)]
    assert int(project.fitted_mask().sum()) == kept.size


@pytest.mark.parametrize("name", NAMES)
def test_an_example_is_built_unfitted(name, tmp_path):
    """WP-1204's non-goal, asserted rather than intended: a build writes the
    starting values, and the refinement is the user's first click."""
    project = build_example(name, tmp_path)
    assert len(project.history) == 1
    assert project.refinement.result_ is None


@pytest.mark.parametrize("name", NAMES)
def test_a_built_example_reopens(name, tmp_path):
    """``Project.open`` re-reads the directory and checks the pattern's sha256
    *and* its parsed-array fingerprint, so this is where a copied-in file that
    is not what the reference says it is would be caught."""
    built = build_example(name, tmp_path)
    reopened = rx.Project.open(built.path)
    assert reopened.data_ref.sha256 == built.data_ref.sha256
    assert reopened.data_ref.n_points == built.data_ref.n_points


def test_an_unknown_example_names_what_this_build_carries(tmp_path):
    with pytest.raises(KeyError) as exc:
        build_example("corundum", tmp_path)
    assert all(n in str(exc.value) for n in NAMES)


def test_building_the_same_example_twice_refuses_rather_than_overwrites(tmp_path):
    build_example(NAMES[0], tmp_path)
    with pytest.raises(FileExistsError):
        build_example(NAMES[0], tmp_path)


def test_the_packaged_inputs_are_byte_identical_to_the_test_data():
    """The examples are copies of files ``tests/data/README.md`` documents, and
    the acceptance suites measure the originals.  A divergence would make the
    reference values in that README describe a file nobody ships."""
    import hashlib

    source = Path(__file__).parent / "data"
    for name in sorted(LICENCES):
        if not (source / name).exists():
            pytest.skip(f"{name} is not present in tests/data")
        packaged = (examples_dir() / name).read_bytes()
        original = (source / name).read_bytes()
        assert hashlib.sha256(packaged).digest() == \
               hashlib.sha256(original).digest(), name


def test_example_info_is_what_a_client_serialises():
    """Four fields and no more: the GUI's empty state renders this verbatim."""
    import dataclasses

    assert [f.name for f in dataclasses.fields(ExampleInfo)] == \
           ["name", "title", "description", "bytes"]


DATA = Path(__file__).parent / "data"


def test_every_remote_file_is_the_test_data_file_it_names():
    """`fetch` downloads `tests/data/<name>` at a pinned commit and checks it
    against `REMOTE_FILES`, so a hash that drifts from the committed file is a
    download that always fails."""
    import hashlib

    from rietx.examples import REMOTE_FILES

    for name, remote in REMOTE_FILES.items():
        assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == \
               remote.sha256, name


class _Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def test_fetch_downloads_once_and_then_reads_its_copy(tmp_path, monkeypatch):
    import urllib.request

    from rietx._about import REPO_URL, STATE_DIR_ENV
    from rietx.examples import REMOTE_COMMIT, fetch

    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path))
    urls = []

    def urlopen(url, timeout):
        urls.append(url)
        return _Response((DATA / "11BM_Kapton.xy").read_bytes())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    path = fetch("11BM_Kapton.xy")
    assert path == tmp_path / "data" / "11BM_Kapton.xy"
    assert path.read_bytes() == (DATA / "11BM_Kapton.xy").read_bytes()
    raw = REPO_URL.replace("https://github.com/", "https://raw.githubusercontent.com/")
    assert urls == [f"{raw}/{REMOTE_COMMIT}/tests/data/11BM_Kapton.xy"]
    assert fetch("11BM_Kapton.xy") == path and len(urls) == 1

    # a damaged copy is fetched again rather than read
    path.write_bytes(b"truncated")
    assert fetch("11BM_Kapton.xy").read_bytes()[:2] == b"##" and len(urls) == 2


def test_fetch_refuses_bytes_that_are_not_the_published_file(tmp_path, monkeypatch):
    import http.client
    import urllib.request

    from rietx._about import STATE_DIR_ENV
    from rietx.examples import fetch

    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout: _Response(b"<html>not found</html>"))
    with pytest.raises(OSError, match="not the published file"):
        fetch("11BM_Kapton.xy")
    assert not (tmp_path / "data").exists() or not any((tmp_path / "data").iterdir())

    def offline(url, timeout):
        raise OSError("no network")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    with pytest.raises(OSError, match=r"save it as .*11BM_Kapton\.xy"):
        fetch("11BM_Kapton.xy")

    def dropped(url, timeout):
        raise http.client.IncompleteRead(b"##", 1000)

    monkeypatch.setattr(urllib.request, "urlopen", dropped)
    with pytest.raises(OSError, match=r"save it as .*11BM_Kapton\.xy"):
        fetch("11BM_Kapton.xy")
    with pytest.raises(KeyError, match="unknown data file"):
        fetch("nope.xy")
