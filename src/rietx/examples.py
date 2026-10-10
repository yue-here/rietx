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
to drift.  What this module adds is a sentence for a person who has not
refined anything yet, which is a different reader from the one comparing
corrections.

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
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ._about import DATA_PACKAGE, PROJECT_SUFFIX

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
        plan=inputs.plan, two_theta_limits=inputs.two_theta_limits,
        excluded_regions=list(inputs.data.excluded_regions) or None,
        reader_options=dict(std.reader_options) or None)
