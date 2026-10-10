"""Regenerate the skill's API index, ``docs/skill/rietx/references/api.md``.

    .venv/bin/python docs/skill/make_api_index.py
    .venv/bin/rietx skill --install . --copy      # then re-sync the committed copies

The index is **generated and committed**, the way Part 1's figures are
(``docs/manual/make_figures.py``): committed so that it ships in the wheel and
in the two committed copies with no build step, generated so that no signature
in it was typed by hand.  WP-1304's brief for this file is the document three
"explore the library" runs (114 calls) wrote from source during the 2026-08
campaign — entry points *with signatures*, the model objects *with their
constructors*, the four answer types and their fields — one of which asserted
that everything public is re-exported from the top level, which was false, and
three later runs paid for it.  The campaign's own errors were signature errors
(``Refinement(pattern=…)``, ``Stage(free=…)``, a positional count), which a list
of names cannot prevent and a rendered signature can.

**What is data here, and what is derived.**  The *selection* — which names, in
which section, under what one-line rule — is the ``SECTIONS`` table below, and
is the only authored thing.  Everything after a name is read from the installed
package: a callable's parameters, annotations and defaults from
``inspect.signature``, a pydantic model's fields from ``model_fields``, a
dataclass's from ``dataclasses.fields``, and the first line of each docstring.
So a rename fails ``tests/test_skill.py`` (the name no longer resolves), a
changed default or a new keyword changes the rendered file (the test compares
bytes and says to regenerate), and nothing can be quoted from memory.

**`api.md` is the everyday index, and a technique gets one of its own.**
A session that is about to call rietx loads this file, so every name in it is
a cost that session pays whether or not it will ever make the call.  A
technique most fits never use — magnetic refinement is the first — therefore
renders to `api-<technique>.md` beside this file rather than into it, and is
loaded only by a session doing that technique.  `tests/test_skill.py`'s
coverage gate reads the union of `api*.md`, so a verb's door is signed
wherever its own sessions are routed; the glob means the PR that creates a
technique index has no list to remember to edit.  This is about the reader's
context rather than the byte cap, and the authored heuristics for the same
technique live in `references/<technique>.md` under the shape rule (root
CLAUDE.md § skill), which is an authored file and not a generated one.

**Rendering is deliberately its own.**  ``str(inspect.signature(f))`` quotes
every annotation under ``from __future__ import annotations`` and pydantic's
evaluated annotations print differently across Python versions
(``typing.Optional[X]`` against ``X | None``), while the pinning test runs on
3.11-3.14.  ``_ann`` normalises both to the source spelling, ``X | None``.
"""

from __future__ import annotations

import dataclasses
import enum
import inspect
import math
import re
import sys
import types
import typing
from pathlib import Path
from typing import Annotated, Literal, Union, get_args, get_origin

HERE = Path(__file__).resolve().parent
TARGET = HERE / "rietx" / "references" / "api.md"

#: (section title, one paragraph of rule or orientation, dotted names).  The
#: paragraph is the authored part; every name is rendered from the package.
SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "In",
        "Readers and constructors. `rx.read_pattern` opens every format "
        "`rx.capabilities()` lists and takes the file's esd column when it has "
        "one; a wavelength comes from the instrument preset or the file, never "
        "from memory (§1). **A file extension does not name a format here**: "
        "dispatch is on content, and a declined `.raw` names the six vendors "
        "who write one and picks none, so read the refusal rather than the "
        "suffix (Measured: WP-1407). **Handed another program's input "
        "file** — a "
        "PowderLine `GSASII_Rietveld` recipe — read it with `rx.read_recipe` "
        "rather than parsing it yourself: it returns the model, the instrument "
        "and a plan together, and a unit it could not carry says so as a "
        "`RECIPE_*` diagnostic. "
        "`rx.read_gsas_prm` reads a GSAS-I `.prm` instrument-parameter file "
        "(one constant-wavelength bank, profile type 3, `profile_set=` "
        "choosing among several; time-of-flight is refused by name). A "
        "Kα1/Kα2 doublet there comes back as two "
        "emission lines, the second weighted by the file's own `KRATIO`, so "
        "do not add a Kα2 line yourself after reading one "
        "(Measured: WP-1118). `rx.write_gsas_prm` is its inverse, and the one "
        "writer here whose payload is *not* the refine flags: an "
        "instrument-parameter file is a calibration, so it goes out frozen. It "
        "refuses a non-zero `zero_shift` — `ICONS`' `ZERO` has no established "
        "unit here and a guess is wrong by 100× — so zero it and let the "
        "receiving program refine it. "
        "`rx.read_gsas2_instprm`/`rx.write_gsas2_instprm` are that pair one "
        "program over, for GSAS-II's text calibration: `PXC` and `PNC` banks, "
        "and a **negative** width "
        "coefficient refused rather than clamped, which 2 of the 4 "
        "constant-wavelength files in GSAS-II's own tutorial corpus trip "
        "(Measured: WP-1118). "
        "**Handed another program's whole refinement** — a "
        "TOPAS `.inp`, a FullProf `.pcr`, a GSAS `.EXP` — call "
        "`rx.read_project_model`, which "
        "dispatches on content and returns what the file stated plus a "
        "`.to_structure()` carrying the file's **own refine flags**, the half "
        "nobody can rebuild from a CIF plus a pattern (Measured: WP-1118 — six "
        "agents handed a hand-transcribed series all named the transcription as "
        "the hardest part of the work). Read `.format.reports_at` to know which "
        "call takes your `diagnostics=` list: a `.inp` reports at read, a `.pcr` "
        "at `to_structure`, a `.EXP` at both. A GSAS `.EXP` carries the whole "
        "experiment rather than one phase, so read the wavelengths, excluded "
        "regions and refined profile terms off `model.stated` — a `Structure` "
        "cannot hold them. **A blank field there "
        "is not a zero**: `ka2_ratio` is `None` where the file states no "
        "Ka2/Ka1 ratio, and the 0.5 one field earlier is the polarization — "
        "both are conventionally 0.5 (Measured: WP-1118). A GSAS-II `.gpx` reads through the same door and "
        "carries two things the older formats cannot: the constraints, and the "
        "`vary_list` naming every variable the run refined. It is a **pickle**, so "
        "the reader resolves an allow-list and refuses any other global by name "
        "without reading the file (Measured: WP-1118). "
        "`to_structure` refuses a phase with no sites and keeps a negative "
        "`Uiso`, both of which real projects contain. **Two codes, two goodness-of-fit "
        "conventions**: a `.gpx`’s `gof` is the square root of reduced χ² and a "
        "`.EXP`’s `reduced_chi2` is not a root at all, so comparing your fit with "
        "either file’s figure means knowing which one it quoted (Measured: "
        "WP-1118). "
        "**All four formats write back**: `rx.write_topas_inp`, "
        "`rx.write_fullprof_pcr` and `rx.write_gsas_exp` are each format's "
        "`to_structure` inverse, a file "
        "whose refine flags reproduce the `Structure`'s `vary` exactly and "
        "whose space group is `get_spacegroup(...).xhm()`, never the phase's "
        "stored spelling. FullProf's grammar has no origin/axis suffix at all, so "
        "`write_fullprof_pcr` refuses a phase whose resolved setting a bare "
        "symbol cannot reach — most often origin choice 1 (Measured: WP-1118). "
        "A `.EXP` is the one written by **column**, so it reports what narrowed "
        "to fit a field and which merged refine flags it freed; pass "
        "`diagnostics=[]` for both (a `Biso` always narrows, the file storing "
        "`Uiso`). GSAS-II has no project file to write, so it takes the pair it "
        "imports: `rx.write_gsas2_phase_cif` for the phases and "
        "`rx.write_gsas2_instprm` for the machine. That CIF states the setting "
        "three ways, because GSAS-II reads a bare `F d -3 m` as origin choice 2 "
        "where gemmi reads choice 1 (Measured: WP-1118).",
        ("rx.read_pattern", "rx.read_pdcif", "rx.read_recipe",
         "rx.read_gsas_prm", "rx.write_gsas_prm", "rx.read_project_model",
         "rx.identify_project_format", "rx.read_topas_inp", "rx.write_topas_inp",
         "rx.read_fullprof_pcr", "rx.write_fullprof_pcr",
         "rx.read_gsas_exp", "rx.write_gsas_exp", "rx.read_gsas2_gpx",
         "rx.write_gsas2_phase_cif",
         "rx.read_gsas2_instprm", "rx.write_gsas2_instprm",
         "rx.Structure.from_cif",
         "rx.Instrument.bragg_brentano", "rx.Instrument.debye_scherrer",
         "rx.estimate_mu_r", "rx.auto_background", "rx.diagnose",
         "rx.load_instrument_profile", "rx.save_instrument_profile",
         "rx.capabilities", "rx.help_for"),
    ),
    (
        "The model objects",
        "Every refinable quantity is a `rx.Parameter` (`value`, `vary`, "
        "bounds), addressed by a dot-path such as `phases.0.cell.a` or "
        "`instrument.profile.w`; `rx.help_for(path)` says what any of them is. "
        "Each class below is its own constructor — the fields are the keyword "
        "arguments, a field with no default is required.",
        ("rx.Parameter", "rx.Structure", "rx.Phase", "rx.Atom", "rx.Cell",
         "rx.AnisoU", "rx.PreferredOrientation", "rx.StephensStrain",
         "rx.Instrument", "rx.Source", "rx.NeutronSource", "rx.Geometry",
         "rx.ProfileTCHZ", "rx.BackgroundChebyshev", "rx.BackgroundPSpline",
         "rx.BackgroundFixedPlusChebyshev", "rx.Dispersion", "rx.PatternData"),
    ),
    (
        "Refining",
        "`rx.Refinement` is the stateful entry point and `rx.refine` the "
        "one-shot function form. Plans are named in `rx.PLAN_INFO` or built as "
        "a `rx.RefinementPlan` of `rx.Stage`s; `ref.parameters()` lists every "
        "entry, fixed, locked and tied included, and the editing verbs "
        "auto-commit a history node each. **`vary=False` is not a pin**: a "
        "plan replaces the vary flags rather than continuing them, so a "
        "stage's `turn_on` glob frees whatever it matches. Say it with "
        "`ref.hold(globs)`, which outranks the glob, survives a save and "
        "reopen, and makes the stage report what it could not free "
        "(§8.25, §7 `HOLD_BLOCKED_PLAN`).",
        ("rx.Refinement", "rx.Refinement.fit", "rx.Refinement.report",
         "rx.Refinement.summary", "rx.Refinement.suggest",
         "rx.Refinement.predict", "rx.Refinement.run_stage",
         "rx.Refinement.parameters", "rx.Refinement.set_vary",
         "rx.Refinement.set_values", "rx.Refinement.tie",
         "rx.Refinement.tie_equal", "rx.Refinement.untie",
         "rx.Refinement.add_variable", "rx.Refinement.remove_variable",
         "rx.Refinement.hold", "rx.Refinement.unhold",
         "rx.Refinement.edit",
         "rx.refine", "rx.RefinementPlan", "rx.Stage", "rx.PLAN_INFO",
         "rx.ParameterRow"),
    ),
    (
        "The four answers are four different types",
        "None nests inside another. An `rx.IndexingResult` "
        "carries no `cell` key by design: `best_or_none()` is the only way to "
        "one cell, and it returns `None` more often than not (§6). "
        "`RefinedParameter.at_bound` is three-valued — test `is True`.",
        ("rx.RefinementResult", "rx.StageResult", "rx.Statistics",
         "rx.RefinedParameter", "rx.Diagnostic", "rx.SeriesResult",
         "rx.SeriesResult.trajectory", "rx.SeriesResult.to_table",
         "rx.SeriesResult.write_csv", "rx.SeriesResult.summary",
         "rx.SeriesEntry", "rx.IndexingResult", "rx.IndexingResult.best_or_none",
         "rx.IndexingResult.evidence", "rx.SuggestionResult",
         "rx.CandidateGroup"),
    ),
    (
        "The report",
        "`ref.report()` or `rx.build_report` gives the three-layer "
        "`rx.FitReport` §5 reads. `compare_rivals` and `predict_then_verify` "
        "are the two experiments §4 step 14 and §4b call for, and "
        "`compare_freed` prices a parameter you freed (§4).",
        ("rx.build_report", "rx.FitReport", "rx.report.compare_rivals",
         "rx.report.predict_then_verify", "rx.report.compare_freed",
         "rx.report.FreedComparison", "rx.report.FreedParameter"),
    ),
    (
        "Series, history, projects",
        "`refine_sequential` chains N patterns by warm start (§9b); "
        "`refine_multi` stacks them into one joint residual. The history verbs "
        "work the DAG every fit commits to "
        "(§9); a `Project` owns a `.rex` directory; a `CancelToken` cancels "
        "cooperatively, between residual evaluations.",
        ("rx.refine_sequential", "rx.SequentialRefinement", "rx.refine_multi",
         "rx.MultiHistogramRefinement", "rx.Refinement.checkout",
         "rx.Refinement.branch", "rx.Refinement.merge",
         "rx.Refinement.cherry_pick", "rx.replay", "rx.Project",
         "rx.Project.create", "rx.Project.open", "rx.Project.save",
         "rx.CancelToken"),
    ),
    (
        "An unknown phase",
        "Peaks, then a cell, then the extinction symbol — the closed loop of "
        "§7b-7f, each step returning a ranked list and never a singleton. "
        "`rx.fit_peaks` leaves that loop: it fits the positions *you* name, for "
        "a width analysis or a d-spacing, with no cell in the question.",
        ("rx.pick_peaks", "rx.fit_peaks", "rx.index_pattern",
         "rx.determine_extinction_symbol"),
    ),
    (
        "Out",
        "Files and figures. `rx.format_su` renders a value with its esd as "
        "`1.2345(12)`; `plot_for_vlm` is the montage §5 allows as a check on a "
        "conclusion already reached from numbers. `rx.write_recipe_tables` is "
        "the return leg of `rx.read_recipe` — a finished refinement as "
        "PowderLine's four tables, for a pipeline that dispatched the job here. "
        "A picture of the structure is `rx.viz.render_structure`, and of a "
        "pattern before any model `rx.viz.plot_pattern`, both in "
        "`api-figure.md`.",
        ("rx.write_refinement_cif", "rx.write_qpa_table",
         "rx.write_reflection_table", "rx.reflection_table",
         "rx.write_recipe_tables", "rx.format_su",
         "rx.viz.plot_result", "rx.viz.plot_for_vlm",
         "rietx.viz.html.write_html"),
    ),
)

#: A technique's own index, ``api-<name>.md``: its title, the load
#: condition the body's routing row names, and its sections, as above.
TECHNIQUES: dict[str, tuple[str, str, tuple[tuple[str, str, tuple[str, ...]], ...]]] = {
    "figure": (
        "The figure index",
        "Load it when you want a picture of a structure: a refined model to "
        "look at, a figure for a report, or a view down a zone axis; or a "
        "pattern drawn before any model exists.",
        (
            (
                "Drawing it",
                "`rx.viz.render_structure(ref.structure)` draws one phase as the "
                "GUI's structure viewer draws it, with no browser: an RGBA array "
                "in `.image`, a PNG when `path=` is given. Look at the picture "
                "you drew. `view=` takes `\"a\"`, `\"b\"`, `\"c\"`, `[u, v, "
                "w]`, `{\"hkl\": (h, k, l)}`, `\"auto\"` or a rotation; `.rotation` is the "
                "view drawn, and passing it back redraws the same picture. "
                "`.atoms` and `.letters` give pixel positions for labels you add "
                "yourself. `fig.to_px(points)` carries Cartesian Å into the "
                "image's pixels, so a legend from `.palette`, an axis triad and a "
                "scale bar from `.pixels_per_angstrom` are drawn in matplotlib as "
                "`examples/structure_furniture.py` draws them. For a site's colour (`#rrggbb`, `white` or `black`; "
                "anything else raises) or radius, edit the dict "
                "`rietx.gui.structure3d.build` returns and pass that. "
                "Another program's picture: `Structure.to_cif` writes the "
                "anisotropic loop, and VESTA or JmolData draws it (Hypothesis: "
                "WP-1470, from each program's manual; neither was run).",
                ("rx.viz.render_structure", "rietx.viz.figure3d.StructureFigure"),
            ),
            (
                "Reading the figure before looking",
                "`fig.report` holds the numbers a look would give, so read it "
                "first. `hidden` is the share of atoms covered over 80 % by one "
                "in front, and `hidden_atoms` names them. `dangling_bonds` "
                "counts bond halves that end in mid-air, a trimmed cell's "
                "included. `label_overlaps` "
                "counts pairs of letters that collide. `label_atom_overlaps` "
                "and `label_bond_overlaps` count letters lying on an atom or a "
                "bond. `empty` is the share of "
                "the frame with nothing drawn. `cut` counts what `keep` and "
                "`build`'s atom cap dropped, `atoms` the cell's images the cap "
                "left out, and `warnings` says when the cap trimmed the cell "
                "or a tensor was drawn flat. A cell past `max_atoms` (400) "
                "raises from a structure, so pass the count it names "
                "(Measured: #665, HKUST-1 648). "
                "There is no quality score, so the judgement is yours. Iterate "
                "at `size=400` and render the final size once. A look costs "
                "about width × height / 750 tokens, 213 at 400 px and 1333 at "
                "1000 px, and a turn besides (Hypothesis: WP-1503, the usual "
                "image-token rule; WP-1504 measures it with agents). "
                "`stacked` is the part of `hidden` behind a copy of the same "
                "site, which a view down an axis does by construction; "
                "`hidden - stacked` is what the view occludes. Keep a view the "
                "task named. When `hidden - stacked` is high, draw "
                "`view=\"auto\"` or take another of "
                "`.candidates` with the same `up=` and `turn=`, then add "
                "`turn=` for what stays hidden (Measured: WP-1533, HKUST-1 "
                "down a 0.53 hidden and 0.53 stacked, YBa₂Cu₃O₇ down b 1.00 "
                "and 1.00). A bond dangles when "
                "`boundary=False` leaves out the images it reaches, or when "
                "`hidden=` takes the atom at its far end; `keep` "
                "counts what it cuts in `cut` instead (Measured: WP-1503, NAC "
                "cell 158 dangling with `boundary=False`, 0 after a `keep`). "
                "`outline=True` for print. `cell=False` drops the frame and "
                "its a, b, c, and the view then fits the atoms; never clear "
                "`g[\"edges\"]` by hand (Measured: WP-1533, a 22 Å sphere of "
                "HKUST-1 8.5 px/Å framed, 16.4 bare). `stick=0.5` halves the "
                "sticks, which ellipsoids at 100 K need; never patch "
                "`scene.STICK_OF_SEMI_AXIS`, which `.recipe` cannot replay. "
                "`.recipe` is the call that draws the "
                "picture again, given the same first argument: "
                "`render_structure(g, **fig.recipe)`. Save the geometry "
                "yourself with `json.dump`, since 5000 atoms is megabytes. The "
                "search runs about a hundred id passes "
                "(Measured: WP-1940, NAC cell 1.3-1.4 s and 3143 atoms 22.6 s, "
                "against renders of 97-113 ms and 1.02-1.06 s).",
                ("rietx.viz.figure3d.FigureReport",),
            ),
            (
                "Part of the structure",
                "A site is left out, or a slab or a motif kept, by a mask over "
                "the dict's `atoms`: `g = build(structure)`, then "
                "`rx.viz.keep(g, ~rx.viz.select(g, label=\"F2\"))`. `hidden=` "
                "takes species and elements, never a site label, and leaves "
                "each neighbour's half of a bond as a stub; a mask on "
                "`element=` takes the bonds whole (Measured: WP-1529, calcite "
                "112 stubs under `hidden=(\"Ca\",)`, 0 after a `keep`). A "
                "polyhedron centre outside the cell is drawn only while its "
                "site's polyhedra are hidden, as in VESTA. Never delete "
                "from `atoms` by hand: bonds and polyhedra hold atoms by index, "
                "and `keep` is the one place that renumbers. Masks combine with "
                "`&`, `|` and `~`. `keep(..., complete=True)` brings back the "
                "far ends of cut bonds and the vertices of cut polyhedra, from "
                "the atoms `build` made; `complete=\"polyhedra\"` brings back "
                "the vertices alone, so nothing hangs off a window's edge. "
                "Its `note` counts what a cut lost. "
                "`component(via=\"edges\")` where bonds reach everything. "
                "`build(structure, extent=((0, 2), (0, 2), (0, 1)), "
                "max_atoms=2000)` draws a block of cells, raising past "
                "`max_atoms`; each atom's `image` says which atom of the cell it "
                "is, and `periodicity(g, mask)` reads 0 to 3 for a motif "
                "(Measured: WP-1502, NAC 3x3x3 in 44-62 ms). On a dark "
                "`background`, `recolour` C, whose default #383838 reads at "
                "1.56:1 against #151515 (Measured: WP-1533).",
                ("rx.viz.keep", "rx.viz.select", "rx.viz.plane", "rx.viz.sphere",
                 "rx.viz.component", "rx.viz.periodicity", "rx.viz.recolour"),
            ),
            (
                "The pattern before a model",
                "`data.plot()` on a `PatternData` just read draws it in the "
                "result panel's style, keywords shared with `result.plot()`. "
                "It shows the file, not a fit: judge a fit from the result's "
                "figure and its numbers. `title=` names either figure; the "
                "default draws none.",
                ("rx.viz.plot_pattern",),
            ),
        ),
    ),
    "magnetic": (
        "The magnetic structure index",
        "Load it when you are about to determine a magnetic structure: a "
        "converged neutron fit leaves intensity unexplained and you want the "
        "candidate models ranked rather than one stated by hand.",
        (
            (
                "Determining a magnetic structure",
                "`rx.solve_magnetic(ref, data, sites=[...], ion=...)` takes a "
                "converged **neutron** fit and proposes a propagation vector, "
                "candidate models per k, one trial refinement per class the "
                "powder cannot separate, and a ranked list with a stated "
                "criterion: ΔBIC against a nuclear reference, then a "
                "magnetic-only R, then parsimony, and never Rwp, since more "
                "amplitudes always fit better. Classes inside the tie width that "
                "neither the magnetic-only R nor parsimony separates "
                "abstain together rather than name a winner, and a class with no "
                "supported moment cannot win. A non-neutron histogram is refused "
                "by name; everything else, \"nothing to solve\" included, is "
                "reported. Read `MagneticSolution.verdict` before `.best`, and "
                "`references/magnetic.md` for what each reading must not be "
                "taken to mean. Provisional: the criterion may still move.",
                ("rx.solve_magnetic", "rx.MagneticSolution", "rx.MagneticTrial",
                 "rx.MomentRow"),
            ),
        ),
    ),
}

#: Fields a technique owns, kept out of ``api.md``'s field lists.  A field
#: renders automatically wherever its model does, so a technique's field on an
#: everyday type (``rx.Phase``) would land in the everyday index by the back
#: door that the technique-index rule above closes for its verbs.  Each one
#: belongs in the technique's own ``api-<technique>.md``; rigid bodies get that
#: index in WP-1812, and until then their fields are deferred here exactly as
#: ``tests/api_surface_deferred.txt`` defers them from the manual (WP-1805: no
#: raised cap).  ``tests/test_skill.py`` holds every name here to a real field.
TECHNIQUE_FIELDS: dict[str, frozenset[str]] = {
    "rx.Phase": frozenset({"rigid_bodies"}),
    "rx.ParameterRow": frozenset({"body"}),
}

HEADER = """# The API index

Load it when you are about to call rietx and want the name, the signature or
the constructor rather than a guess.

*A reference file of the `rietx` skill. The body it belongs to is
[`SKILL.md`](../SKILL.md). Generated by `docs/skill/make_api_index.py` from the
installed package — every signature, field and default below is rendered, not
typed, and a test fails when this file is older than the code. Do not edit it;
edit the generator's selection.*

**There is one integration surface and it is the Python API.** A caller runs a
verb, reads the typed answer, and dumps it with `model_dump(mode="json")` when a
file is wanted. A failure **raises**: there is no envelope and no error code.

Everything in `rx.` is `import rietx as rx`; `rx.report` and `rx.viz` are
submodules the package imports for you. `inspect.signature(obj)` or `help(obj)`
gives any call's full docstring; `A -> B` is a return annotation; a
`rx.Parameter(…)` default names the parameter's starting value and whether it
is free.
"""


def _resolve(dotted: str):
    """`rx.X.y` through the top-level package; `rietx.a.b.c` through the
    longest importable module prefix, so a submodule the package does not
    import for you (``rietx.viz.html``) is reachable by its full name."""
    import importlib

    import rietx as rx

    parts = dotted.split(".")
    obj, rest = rx, parts[1:]
    if parts[0] == "rietx":
        for n in range(len(parts), 0, -1):
            try:
                obj = importlib.import_module(".".join(parts[:n]))
            except ModuleNotFoundError:
                continue
            rest = parts[n:]
            break
    for step in rest:
        try:
            obj = getattr(obj, step)
        except AttributeError as exc:
            raise SystemExit(f"{dotted}: {step!r} does not exist — fix SECTIONS") from exc
    return obj


def _ann(t) -> str:
    """The source spelling of an annotation, the same on every Python."""
    if t is inspect.Parameter.empty:
        return ""
    if isinstance(t, str):
        return t.strip("'\"")
    if t is None or t is type(None):
        return "None"
    origin, args = get_origin(t), get_args(t)
    if origin is Union or origin is types.UnionType:
        return " | ".join(_ann(a) for a in args)
    if origin is Literal:
        return "Literal[" + ", ".join(repr(a) for a in args) + "]"
    if origin is Annotated:
        return _ann(args[0])
    if origin is not None:
        name = getattr(origin, "__name__", str(origin))
        return f"{name}[{', '.join(_ann(a) for a in args)}]" if args else name
    if isinstance(t, typing.TypeVar):
        return t.__name__
    if isinstance(t, typing.ForwardRef):
        return t.__forward_arg__
    if isinstance(t, type):
        return t.__name__
    return str(t).replace("typing.", "")


def _default(value) -> str:
    """A default's spelling: short, stable, and never an address."""
    from pydantic import BaseModel

    if isinstance(value, enum.Enum):
        return repr(value.value)
    if isinstance(value, BaseModel):
        if type(value).__name__ == "Parameter":
            bits = [repr(value.value)]
            if value.vary:
                bits.append("vary=True")
            if value.min is not None and math.isfinite(value.min):
                bits.append(f"min={value.min!r}")
            if value.max is not None and math.isfinite(value.max):
                bits.append(f"max={value.max!r}")
            return f"Parameter({', '.join(bits)})"
        return f"{type(value).__name__}(…)"
    if isinstance(value, Path):
        return f"Path({str(value)!r})"
    if isinstance(value, (list, tuple)):
        items = [_default(v) for v in value]
        open_, close = ("[", "]") if isinstance(value, list) else ("(", ")")
        if not items:
            return open_ + close
        if len(items) > 1 and len(set(items)) == 1:
            return f"{open_}{items[0]} × {len(items)}{close}"
        if len(items) > 6:
            items = items[:6] + ["…"]
        sep = ", " if len(items) > 1 or isinstance(value, list) else ","
        return open_ + sep.join(items) + close
    if isinstance(value, float) and not math.isfinite(value):
        return "inf" if value > 0 else "-inf" if value < 0 else "nan"
    text = repr(value)
    if " at 0x" in text or text.startswith("<"):
        return "…"
    return text


def _signature(obj, *, drop_self: bool) -> str:
    sig = inspect.signature(obj)
    params, seen_kw_only, pos_only_open = [], False, False
    for i, p in enumerate(sig.parameters.values()):
        if i == 0 and drop_self and p.name in ("self", "cls"):
            continue
        if p.kind is p.POSITIONAL_ONLY:
            pos_only_open = True
        elif pos_only_open:
            params.append("/")
            pos_only_open = False
        if p.kind is p.KEYWORD_ONLY and not seen_kw_only:
            params.append("*")
            seen_kw_only = True
        if p.kind is p.VAR_POSITIONAL:
            seen_kw_only = True
            text = f"*{p.name}"
        elif p.kind is p.VAR_KEYWORD:
            text = f"**{p.name}"
        else:
            text = p.name
        ann = _ann(p.annotation)
        if ann:
            text += f": {ann}"
        if p.default is not p.empty:
            text += f" = {_default(p.default)}" if ann else f"={_default(p.default)}"
        params.append(text)
    if pos_only_open:
        params.append("/")
    out = f"({', '.join(params)})"
    ret = _ann(sig.return_annotation)
    if ret and ret != "None":
        out += f" -> {ret}"
    return out


_RST_ROLE = re.compile(r":\w+:`~?([^`]+)`")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s")


def _doc_line(obj) -> str:
    """The first sentence of the object's *own* docstring.

    ``inspect.getdoc`` inherits, which would give every schema class its base
    class's line; a dataclass with no docstring carries an auto-generated
    signature, which is not documentation; and a first *line* can end
    mid-sentence, so the first paragraph is joined and cut at its first
    sentence.
    """
    doc = obj.__doc__ if inspect.isclass(obj) else inspect.getdoc(obj)
    if not doc:
        return ""
    paragraph = inspect.cleandoc(doc).split("\n\n", 1)[0]
    text = " ".join(paragraph.split())
    if inspect.isclass(obj) and text.startswith(obj.__name__ + "("):
        return ""
    text = _SENTENCE_END.split(text, 1)[0]
    text = _RST_ROLE.sub(lambda m: f"`{m.group(1)}`", text).replace("``", "`")
    if len(text) > 200:
        text = text[:199].rstrip() + "…"
    return text


def _model_fields(cls, skip: frozenset[str] = frozenset()) -> list[str]:
    from pydantic_core import PydanticUndefined

    out = []
    for name, info in cls.model_fields.items():
        if name in skip:
            continue
        text = f"{name}: {_ann(info.annotation)}"
        if info.default_factory is not None:
            text += f" = {_default(info.default_factory())}"
        elif info.default is not PydanticUndefined:
            text += f" = {_default(info.default)}"
        out.append(f"`{text}`")
    return out


def _dataclass_fields(cls) -> list[str]:
    out = []
    for f in dataclasses.fields(cls):
        text = f"{f.name}: {_ann(f.type)}"
        if f.default_factory is not dataclasses.MISSING:
            text += f" = {_default(f.default_factory())}"
        elif f.default is not dataclasses.MISSING:
            text += f" = {_default(f.default)}"
        out.append(f"`{text}`")
    return out


def _entry(dotted: str, technique: str | None = None) -> str:
    from pydantic import BaseModel

    obj = _resolve(dotted)
    doc = _doc_line(obj)
    tail = f" — {doc}" if doc else ""
    if isinstance(obj, dict):
        keys = ", ".join(f"`{k}`" for k in obj)
        return f"- `{dotted}` — keys: {keys}"
    if inspect.isclass(obj) and issubclass(obj, BaseModel):
        skip = TECHNIQUE_FIELDS.get(dotted, frozenset()) if technique is None else frozenset()
        fields = ", ".join(_model_fields(obj, skip))
        return f"- `{dotted}`{tail}\n  Fields: {fields}"
    if inspect.isclass(obj) and dataclasses.is_dataclass(obj):
        fields = ", ".join(_dataclass_fields(obj))
        return f"- `{dotted}`{tail}\n  Fields: {fields}"
    if inspect.isclass(obj):
        return f"- `{dotted}{_signature(obj, drop_self=False)}`{tail}"
    if callable(obj):
        is_method = "." in dotted[3:] and inspect.isclass(_resolve(dotted.rsplit(".", 1)[0]))
        return f"- `{dotted}{_signature(obj, drop_self=is_method)}`{tail}"
    raise SystemExit(f"{dotted}: not a class, callable or dict — fix SECTIONS")


def _technique_header(title: str, load: str) -> str:
    return f"""# {title}

{load}

*A reference file of the `rietx` skill. The body it belongs to is
[`SKILL.md`](../SKILL.md). Generated by `docs/skill/make_api_index.py` from the
installed package, like [`api.md`](api.md), and loaded only by a session doing
this; everything in `rx.` is `import rietx as rx`.*
"""


def render(technique: str | None = None) -> str:
    """``api.md``, or ``api-<technique>.md`` for a name in :data:`TECHNIQUES`."""
    if technique is None:
        parts, sections = [HEADER], SECTIONS
    else:
        title, load, sections = TECHNIQUES[technique]
        parts = [_technique_header(title, load)]
    for title, prose, names in sections:
        parts += [f"## {title}", "", prose, ""]
        parts += [_entry(n, technique) for n in names]
        parts.append("")
    text = "\n".join(parts)
    assert " at 0x" not in text and "PydanticUndefined" not in text, text
    return text


def targets() -> dict[Path, str]:
    """Every index this script writes, and what it renders into each."""
    out = {TARGET: render()}
    for name in TECHNIQUES:
        out[TARGET.with_name(f"api-{name}.md")] = render(name)
    return out


def main(argv: list[str]) -> int:
    stale = 0
    for path, text in targets().items():
        if "--check" in argv:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != text:
                print(f"{path} is stale; run {Path(__file__).name}", file=sys.stderr)
                stale = 1
            continue
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path} ({len(text.encode('utf-8'))} B)")
    return stale


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
