"""WP-1011 — the glob fixture the frontend's matcher is held to.

The GUI's parameter table previews a bulk free/fix before sending it, which
means a matcher in TypeScript deciding what a Python glob selects.  Two matchers
for one vocabulary is a drift hazard with no natural alarm: the preview would
say 41 and the server would free 214, and nothing would fail.

So the authority is written down.  This module regenerates
``tests/data/gui/fnmatch_cases.json`` from :func:`fnmatch.fnmatchcase` — the
function ``ParameterTable.set_vary`` itself calls — over a **live** parameter
vocabulary, and ``gui/src/lib/fnmatch.test.ts`` replays every case through
``lib/fnmatch.ts``.  The fixture is committed because vitest must run without
pytest having run first (a CI job that installs node does not install this
package), so the check here is the same shape as the dist digest in
``test_gui_dist.py``: regenerate, compare, and fail *naming the command* when
they differ.

The vocabulary is live rather than a literal list for the reason every registry
meta-test in this repo exists: a path shape nobody thought of — ``adp.0``,
``microstrain.dof.3``, ``source.lines.1.weight`` — is exactly the one a hand-written
corpus omits and a grouping rule mishandles.
"""

from __future__ import annotations

import json
from fnmatch import fnmatchcase
from pathlib import Path

from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import (
    HUMP_FWHM_MIN,
    HumpComponent,
    Instrument,
)
from rietx.schemas.structure import (
    AnisoU,
    Atom,
    Cell,
    Phase,
    StephensStrain,
    Structure,
)
from rietx.strategy.staged import PLAN_PRESETS

FIXTURE = Path(__file__).parent / "data" / "gui" / "fnmatch_cases.json"

#: Globs the editor's own affordances produce, plus the shapes a user types.
#: The plan presets' ``turn_on`` globs are added live below — those are the ones
#: that must never diverge, since the table previews the same strings a stage runs.
_EDITOR_GLOBS = (
    "*",
    "*cell*",                       # what the filter box makes of "cell"
    "*biso*",
    "phases.0.*",
    "phases.*.cell.a",
    "phases.*.atoms.*.dof.*",
    "phases.*.atoms.*.adp.*",
    "phases.*.microstrain.dof.*",
    "instrument.*",
    "instrument.background.c?",     # single-character wildcard
    "instrument.profile.[uvw]",     # a character class
    "instrument.profile.[!uvw]",    # a negated class
    "phases.0.atoms.[0-9].biso",    # a range
    "instrument.source.lines.*.weight",
    "*.scale",
    "phases.0.cell.[]",             # empty class: matches nothing
    "phases.0.cell.[a",             # unclosed bracket: a literal '['
    "phases.0.cell.a]",             # a bare ']' is literal
    "**cell**",                     # collapsed star runs
    "PHASES.0.CELL.A",              # case-sensitive: fnmatchcase, not fnmatch
    "nothing.matches.this",
)


def _vocabulary() -> list[str]:
    """Every parameter path two deliberately different models produce.

    Brucite carries the shapes the LaB6 model has no reason to: an anisotropic
    ADP block (``adp.k`` beside ``u11``), a Stephens block (``microstrain.dof.k``
    beside ``s400``), a Kα doublet's second line weight, an atom on a special
    position whose coordinates are locked, and an additive background peak
    (``instrument.extra_components.0.fwhm``).  The last is here for a reason
    beyond covering its own glob: it is the one path a ``background`` glob must
    **not** reach, and ``instrument.background.*`` reaches it under any nested
    spelling because fnmatch's ``*`` crosses dots.  Without a peak in the
    vocabulary that separation is asserted against nothing.
    """
    from tests.test_refine_synthetic import perturbed_models

    def parameter(value: float) -> Parameter:
        return Parameter(value=value)

    lab6_structure, lab6_instrument = perturbed_models()
    cell = Cell(a=Parameter(value=3.15, min=0.1), b=Parameter(value=3.15, min=0.1),
                c=Parameter(value=4.77, min=0.1), alpha=parameter(90.0),
                beta=parameter(90.0), gamma=parameter(120.0))
    brucite = Phase(
        name="brucite", space_group="P -3 m 1", cell=cell,
        atoms=[
            Atom(label="Mg", species="Mg", x=parameter(0.0), y=parameter(0.0),
                 z=parameter(0.0), aniso=AnisoU.isotropic(0.01, cell)),
            Atom(label="O", species="O", x=parameter(1 / 3), y=parameter(2 / 3),
                 z=parameter(0.22)),
        ],
        microstrain=StephensStrain.isotropic(1000.0, cell))

    lab_instrument = Instrument.bragg_brentano()
    lab_instrument.extra_components = [HumpComponent(
        label="amorphous mount",
        position=Parameter(value=22.0, unit="deg"),
        height=Parameter(value=0.0, min=0.0, transform="softplus"),
        fwhm=Parameter(value=8.0, min=HUMP_FWHM_MIN,
                       transform="softplus"))]

    # a child on mode amplitudes (WP-1419): mccusker_structural frees its
    # amplitudes, and no other model has that path
    from tests.test_help import _distortion_phase

    paths: list[str] = []
    for structure, instrument in (
        (lab6_structure, lab6_instrument),
        (Structure(phases=[brucite]), lab_instrument),
        (Structure(phases=[_distortion_phase()]), lab_instrument),
    ):
        for entry in ParameterTable(structure, instrument).entries:
            if entry.path not in paths:
                paths.append(entry.path)
    return paths


def _globs() -> list[str]:
    """Editor globs plus every glob the shipped plan presets actually free."""
    out = list(_EDITOR_GLOBS)
    for build in PLAN_PRESETS.values():
        for stage in build().stages:
            for glob in stage.turn_on:
                if glob not in out:
                    out.append(glob)
    return out


def _corpus() -> dict:
    paths = _vocabulary()
    return {
        "_comment": (
            "Generated by tests/test_gui_fnmatch.py from fnmatch.fnmatchcase over "
            "the live parameter vocabulary; consumed by gui/src/lib/fnmatch.test.ts. "
            "Do not hand-edit — run `.venv/bin/python -m pytest "
            "tests/test_gui_fnmatch.py` to regenerate. Coverage is stars, "
            "single-character wildcards, character classes with ranges and "
            "negation, and the malformed-bracket cases Python treats as literals; "
            "an inverted range ([z-a]) is deliberately absent, because Python "
            "repairs one and the port does not, and no path here contains a "
            "bracket at all (CLAUDE.md, Conventions)."),
        "paths": paths,
        "patterns": [
            {"pattern": glob,
             "matches": [i for i, path in enumerate(paths)
                         if fnmatchcase(path, glob)]}
            for glob in _globs()
        ],
    }


def _dump(corpus: dict) -> str:
    return json.dumps(corpus, indent=1) + "\n"


def test_the_committed_glob_fixture_is_current():
    """Regenerate and compare — the dist-digest rule, one artefact over."""
    text = _dump(_corpus())
    if not FIXTURE.is_file() or FIXTURE.read_text(encoding="utf-8") != text:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(text, encoding="utf-8")
        raise AssertionError(
            f"{FIXTURE.relative_to(Path(__file__).parent.parent)} was stale and has "
            "been rewritten; commit it (the vitest parity test reads the committed "
            "copy, and node never runs this suite)")


def test_the_corpus_covers_every_glob_a_shipped_plan_frees():
    """A preset's globs are the strings the table previews; none may be missing."""
    corpus = json.loads(FIXTURE.read_text(encoding="utf-8"))
    covered = {entry["pattern"] for entry in corpus["patterns"]}
    for name, build in PLAN_PRESETS.items():
        for stage in build().stages:
            for glob in stage.turn_on:
                assert glob in covered, f"{name}/{stage.name} frees {glob!r}"


def test_the_corpus_exercises_both_answers_for_every_pattern():
    """A pattern matching everything (or nothing) tests nothing about a matcher.

    Two are exempt and named: ``*`` is the empty filter box, and one pattern is
    there precisely to match nothing.
    """
    corpus = json.loads(FIXTURE.read_text(encoding="utf-8"))
    total = len(corpus["paths"])
    assert total > 60 and len(corpus["patterns"]) > 20
    trivial = {"*", "nothing.matches.this"}
    for entry in corpus["patterns"]:
        if entry["pattern"] in trivial:
            continue
        hits = len(entry["matches"])
        assert hits < total, entry["pattern"]
    # …and the corpus as a whole must contain both answers in quantity
    assert sum(len(e["matches"]) for e in corpus["patterns"]) > 100


def test_the_vocabulary_carries_the_path_shapes_the_grouping_rule_bends_for():
    """The indexed-leaf shapes — an ADP component, a Stephens DOF, a line weight.

    ``lib/table.ts`` groups ``phases.0.atoms.3.adp.1`` under the *atom* rather
    than under a heading called ``adp``, which is a rule with nothing to test
    against if the corpus has no such path.
    """
    paths = json.loads(FIXTURE.read_text(encoding="utf-8"))["paths"]
    for shape in ("phases.0.atoms.0.adp.0", "phases.0.microstrain.dof.0",
                  "instrument.source.lines.1.weight", "phases.0.atoms.1.dof.0"):
        assert shape in paths
