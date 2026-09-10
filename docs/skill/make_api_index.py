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
        "from memory (§1). **Handed another program's input file** — a "
        "PowderLine `GSASII_Rietveld` recipe — read it with `rx.read_recipe` "
        "rather than parsing it yourself: it returns the model, the instrument "
        "and a plan together, and every unit it could not carry across says so "
        "as a `RECIPE_*` diagnostic instead of arriving silently wrong. "
        "`rx.read_gsas_prm` reads a GSAS-I `.prm` instrument-parameter file "
        "(the dominant one-bank, constant-wavelength case; a neutron "
        "time-of-flight file and every other GSAS profile function are "
        "refused by name). A GSAS `.EXP`/`.LST` refinement output has no "
        "reader and is transcribed by hand. A TOPAS `.inp` and a FullProf "
        "`.pcr` do have readers — `rietx.io.projects.read_topas_inp` and "
        "`read_fullprof_pcr` — with no top-level `rx.` entry point yet; "
        "`rx.read_recipe` will not open either.",
        ("rx.read_pattern", "rx.read_pdcif", "rx.read_recipe",
         "rx.read_gsas_prm", "rx.Structure.from_cif",
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
        "auto-commit a history node each.",
        ("rx.Refinement", "rx.Refinement.fit", "rx.Refinement.report",
         "rx.Refinement.summary", "rx.Refinement.suggest",
         "rx.Refinement.predict", "rx.Refinement.run_stage",
         "rx.Refinement.parameters", "rx.Refinement.set_vary",
         "rx.Refinement.set_values", "rx.Refinement.tie",
         "rx.Refinement.tie_equal", "rx.Refinement.untie",
         "rx.Refinement.add_variable", "rx.Refinement.remove_variable",
         "rx.Refinement.edit",
         "rx.refine", "rx.RefinementPlan", "rx.Stage", "rx.PLAN_INFO",
         "rx.ParameterRow"),
    ),
    (
        "The four answers are four different types",
        "A refinement, a series, an indexing run and a suggestion each return "
        "their own type, and none nests inside another. An `rx.IndexingResult` "
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
        "are the two experiments §4 step 14 and §4b call for.",
        ("rx.build_report", "rx.FitReport", "rx.report.compare_rivals",
         "rx.report.predict_then_verify"),
    ),
    (
        "Series, history, projects",
        "`refine_sequential` chains N patterns by warm start (§9b); "
        "`refine_multi` stacks them into one joint residual, which is a "
        "different thing. The history verbs work the DAG every fit commits to "
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
        "§7b-7f, each step returning a ranked list and never a singleton.",
        ("rx.pick_peaks", "rx.index_pattern", "rx.determine_extinction_symbol"),
    ),
    (
        "Out",
        "Files and figures. `rx.format_su` renders a value with its esd as "
        "`1.2345(12)`; `plot_for_vlm` is the montage §5 allows as a check on a "
        "conclusion already reached from numbers. `rx.write_recipe_tables` is "
        "the return leg of `rx.read_recipe` — a finished refinement as "
        "PowderLine's four tables, for a pipeline that dispatched the job here.",
        ("rx.write_refinement_cif", "rx.write_qpa_table",
         "rx.write_reflection_table", "rx.reflection_table",
         "rx.write_recipe_tables", "rx.format_su",
         "rx.viz.plot_result", "rx.viz.plot_for_vlm",
         "rietx.viz.html.write_html"),
    ),
)

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


def _model_fields(cls) -> list[str]:
    from pydantic_core import PydanticUndefined

    out = []
    for name, info in cls.model_fields.items():
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


def _entry(dotted: str) -> str:
    from pydantic import BaseModel

    obj = _resolve(dotted)
    doc = _doc_line(obj)
    tail = f" — {doc}" if doc else ""
    if isinstance(obj, dict):
        keys = ", ".join(f"`{k}`" for k in obj)
        return f"- `{dotted}` — keys: {keys}"
    if inspect.isclass(obj) and issubclass(obj, BaseModel):
        fields = ", ".join(_model_fields(obj))
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


def render() -> str:
    parts = [HEADER]
    for title, prose, names in SECTIONS:
        parts += [f"## {title}", "", prose, ""]
        parts += [_entry(n) for n in names]
        parts.append("")
    text = "\n".join(parts)
    assert " at 0x" not in text and "PydanticUndefined" not in text, text
    return text


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != text:
            print(f"{TARGET} is stale; run {Path(__file__).name}", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET} ({len(text.encode('utf-8'))} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
