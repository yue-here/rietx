"""Example projects, shipped in the wheel (WP-1204).

A new user's first problem is not the refinement; it is having nothing to
refine.  So the GUI's empty state offers a short list of real specimens, each
one click from an open project, and this module is what stands behind that
click: a data directory inside the package, and a build that is a plain
:meth:`Project.create` with the standard's own protocol.

**The protocol is quoted, never restated.**  Each example *is* an entry in
:data:`rietx.viz.compare.STANDARDS` — the same registry the settings-comparison
UI ranks corrections on, pinned field by field against the acceptance suites by
``tests/test_compare_ui.py``.  So an example's plan, held parameters and
excluded regions are the ones the suite measures, and there is no second copy
to drift.  One field is the package's rather than the suite's: the closing
stage, which a first fit runs only where the default does (WP-2036).  What
this module adds is a sentence for a person who has not refined anything yet,
which is a different reader from the one comparing corrections.

**The list is derived from what shipped.**  :func:`list_examples` is
``STANDARDS`` filtered by :meth:`Standard.available` against
:func:`examples_dir`, so adding a file to the package data adds an example and
removing one removes it — there is no hand-written list to fall out of step
with the directory.  Which standards ship is a *licensing* question and not a
size one: the IUCr CPD round-robin patterns carry no explicit licence (see
``tests/data/README.md``) and are already kept out of the sdist, so the four
pure-phase standards built on them cannot ship here either.  Everything below
is APS, NIST or COD material.

**Nothing here fits anything.**  A build writes a project at its starting
values; the refinement is the user's first click, not ours.

**A file a guide needs but no example uses is fetched, not shipped**
(:func:`fetch`, WP-1986).  The 11-BM silicon scan and its empty capillary are
3 MB the wheel would carry for two manual pages, so each is downloaded on
first use from the repository at a pinned commit and checked against its
sha256.  The test suite fills the cache from ``tests/data/`` and never reaches
the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ._about import DATA_PACKAGE, PROJECT_SUFFIX, REPO_URL

if TYPE_CHECKING:  # pragma: no cover - import cost, not behaviour
    from .project import Project

#: One line for someone who has not refined anything yet: what the specimen is,
#: and what opening it teaches.  Deliberately *not* ``Standard.description``,
#: which is written for a reader comparing corrections ("watch the displacement
#: parameters, not Rwp") and answers a question a first-time user has not asked
#: yet.  Keyed by standard, and ``tests/test_example_projects.py`` fails on a
#: key that is not a shipped standard or a shipped standard with no key, so the
#: two cannot drift apart in either direction.
#:
#: **A standard can be worth shipping and wrong to offer here.**  SRM 660c is
#: the package's absolute cell anchor and stays a ``STANDARDS`` entry and an
#: acceptance suite, but it is not an example: NIST step-scanned only the 24
#: windows containing peaks, so 39 % of its 20.3-150.9° span is measured and
#: the rest is not there at all.  That is normal for a certification
#: measurement and reads as broken data to someone meeting the package for the
#: first time.  An example is what a stranger opens with no provenance to go
#: on, so the bar is higher than "a good dataset".
DESCRIPTIONS: dict[str, str] = {
    "fap": (
        "Fluorapatite from the GSAS-II tutorial, on a lab Cu Kα doublet: an "
        "ordinary powder pattern from an ordinary diffractometer. Seven atomic "
        "sites with real positional freedom, which is where a refinement "
        "starts to need a plan rather than a button. The reference values come "
        "from GSAS's own converged fit of the same file."),
    "nac": (
        "A synchrotron capillary pattern from APS 11-BM: Na₂Ca₃Al₂F₁₄ with a "
        "fluorite impurity. Two phases, very sharp peaks and a short "
        "wavelength — open this one to see what a phase you did not ask for "
        "looks like in the difference curve."),
}


@dataclass(frozen=True)
class ExampleInfo:
    """One example, as a client lists it."""

    #: the standard's key, and the argument :func:`build_example` takes
    name: str
    title: str
    description: str
    #: total size on disk of this example's input files.  A build copies the
    #: pattern into the project, so this is roughly what one costs.
    bytes: int


def examples_dir() -> Path:
    """The packaged input files.

    A real filesystem path rather than a ``Traversable``: the readers and
    :func:`~rietx.crystallography.cif.structure_from_cif` open files by path,
    and every install that carries this package also carries compiled
    extensions (rietx-kernels, gemmi), so it is never imported from a zip.
    """
    from importlib import resources

    return Path(str(resources.files(DATA_PACKAGE))) / "examples"


def _standards():
    """The shipped subset of the comparison registry, in its order."""
    from .viz.compare import STANDARDS

    root = examples_dir()
    return [s for s in STANDARDS if s.available(root)]


def list_examples() -> list[ExampleInfo]:
    """Every example this build carries."""
    root = examples_dir()
    return [ExampleInfo(
        name=s.key, title=s.title, description=DESCRIPTIONS[s.key],
        bytes=sum((root / f).stat().st_size for f in s.files))
        for s in _standards()]


def build_example(name: str, into: str | Path) -> "Project":
    """Create ``<into>/<name>.rex`` from the packaged inputs, and open it.

    ``into`` is the *parent* directory; the project is named after the example,
    so two builds into the same place collide rather than overwriting — which
    is :meth:`Project.create`'s refusal, with its own remedy in it.

    The reader call travels with the pattern.  ``Standard.reader_options`` is
    passed rather than left to the default, because a pdCIF carrying a
    ``_meas`` and a ``_calc`` block is a different pattern depending on
    ``block``, and the project records which one was read.
    """
    from .project import Project

    root = examples_dir()
    for std in _standards():
        if std.key == name:
            break
    else:
        raise KeyError(
            f"unknown example {name!r}; this build carries "
            f"{[s.key for s in _standards()]}")

    inputs = std.build(root)
    return Project.create(
        Path(into) / f"{name}{PROJECT_SUFFIX}",
        pattern=root / std.pattern,
        structure=inputs.structure, instrument=inputs.instrument,
        plan=_first_fit_plan(inputs.plan),
        two_theta_limits=inputs.two_theta_limits,
        excluded_regions=list(inputs.data.excluded_regions) or None,
        reader_options=dict(std.reader_options) or None)


def _first_fit_plan(plan):
    """The standard's plan with the package's default closing stage.

    A standard declares its suite's closing stage so that ``rietx compare``
    reproduces the acceptance numbers.  An example is a person's first fit, and
    a first fit runs the default, which has no closing stage since WP-2222
    (ruled 2026-11-19: its time was too high for a default).  Every other field
    is the standard's (WP-2036)."""
    from dataclasses import replace

    from .strategy.staged import RefinementPlan

    default = RefinementPlan(stages=[]).closing_window_tol
    return replace(plan, closing_window_tol=default)


@dataclass(frozen=True)
class RemoteFile:
    """A data file fetched on first use rather than shipped (WP-1986)."""

    #: of the bytes as published, checked on every download and every cache hit
    sha256: str
    #: what the file holds and who measured it
    description: str
    #: why it may be redistributed, as ``tests/data/README.md`` states it
    licence: str


#: The repository commit the files are fetched from.  A commit and never a
#: branch, so the bytes behind each URL cannot change under the hashes below.
REMOTE_COMMIT = "7916301d024eb19fb1fae2b21e260b3aedd8f6de"

_APS_STANDARD = ("APS 11-BM's published standard-reference scan, a U.S. "
                 "Government work, publicly distributed")

#: Files a guide needs and the wheel does not carry, about 1.5 MB each.  They
#: live in the repository's ``tests/data/``, whose README holds their provenance.
REMOTE_FILES: dict[str, RemoteFile] = {
    "11BM_Si640c.xy": RemoteFile(
        sha256="a10f555ed01e10f488eaaf5b7a22500dde1fe9b21dceb5429f4c0eb771621578",
        description=("NIST SRM 640c silicon in a Kapton capillary, APS 11-BM run "
                     "4918, 25 Feb 2010, λ 0.412359 Å, 1.996-49.995° 2θ"),
        licence=_APS_STANDARD),
    "11BM_Kapton.xy": RemoteFile(
        sha256="5f313c296f7efdf3c7150124604c0796451582c7b10342cfeadc1f34ea0d4e49",
        description=("the same Kapton capillary scanned empty, APS 11-BM run "
                     "4736, 11 Feb 2010, λ 0.412225 Å, 0.500-49.996° 2θ"),
        licence=_APS_STANDARD),
}


def fetch(name: str) -> Path:
    """The local path of a :data:`REMOTE_FILES` entry, downloaded on first use.

    The copy is kept under the per-user state directory (``~/.rietx/data``,
    moved by ``$RIETX_STATE_DIR``), and its sha256 is checked before the path
    is returned, so a truncated or altered copy is fetched again rather than
    read.  A failed download raises :class:`OSError` naming the URL and the
    path to save the file at by hand, the route for a machine with no network.
    """
    import hashlib
    import http.client
    import os
    import tempfile
    import urllib.request

    from .viz.theme import state_dir

    if name not in REMOTE_FILES:
        raise KeyError(f"unknown data file {name!r}; fetch() knows "
                       f"{sorted(REMOTE_FILES)}")
    want = REMOTE_FILES[name].sha256
    path = state_dir() / "data" / name
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == want:
        return path

    raw = REPO_URL.replace("github.com", "raw.githubusercontent.com")
    url = f"{raw}/{REMOTE_COMMIT}/tests/data/{name}"
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            body = response.read()
    # IncompleteRead, a connection dropped mid-body, is an HTTPException and
    # not an OSError, and is as much a failed download as a refused one.
    except (OSError, http.client.HTTPException) as exc:
        raise OSError(f"could not download {name} from {url} ({exc}). Download "
                      f"it by another route and save it as {path}.") from exc
    got = hashlib.sha256(body).hexdigest()
    if got != want:
        raise OSError(f"{name} from {url} has sha256 {got[:12]}, not {want[:12]}, "
                      "so it is not the published file. Nothing was saved.")
    path.parent.mkdir(parents=True, exist_ok=True)
    # A partial file of its own per call: two processes fetching at once must
    # not install each other's half-written bytes under the checked name.
    fd, partial = tempfile.mkstemp(dir=path.parent, prefix=name + ".", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(body)
        os.replace(partial, path)
    except BaseException:
        Path(partial).unlink(missing_ok=True)
        raise
    return path
