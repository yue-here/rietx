"""How a rietx object reads when printed, shown in a notebook, or logged (WP-1544).

Text is the authority and HTML a projection of the same rows, because an agent
reads stdout and a person reads a notebook cell, and the two must not disagree.

Four rules hold for everything here:

- **A display reads fields; it never computes.** IPython builds text/plain *and*
  text/html for every displayed value, so a renderer calling ``report()`` or
  ``summary()`` would run a report's rival fits twice per cell.
- **No glosses.** A renderer prints a field's name, or the label ``help.py``
  carries for it.  What a name *is* is written there and nowhere else (WP-1202).
- **No colour of its own.** HTML is semantic tags only: JupyterLab's and
  GitHub's sanitisers strip styles, and a colour here would be a fourth surface
  beside ``viz/theme.py``'s three.
- **A display is laid out to be read** (WP-2037): values in one aligned
  column, numbers to the digits that carry meaning, a unit where there is
  one, and an empty state that says whether the check ran.  The last is read
  off a field like any other value, so a view whose empty list means two
  things needs a field that tells them apart.

Private: nothing here is API.  The hooks that call it (``__repr_args__``,
``__str__``, ``_repr_pretty_``, ``_repr_html_``) are the surface.
"""

from __future__ import annotations

import math
import numbers

import numpy as np

#: A sequence longer than this prints as a count and a range, never its items.
#: Eight keeps a cell's six lattice numbers and a short line list whole while a
#: pattern's thousands of channels collapse to one line.
ELIDE_ABOVE = 8


class _Elided:
    """A stand-in whose ``repr`` is a summary of the sequence it replaced."""

    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text

    def __repr__(self) -> str:
        return self.text


def _kind(items) -> str:
    """A plural noun for what the sequence holds, read off its items."""
    types = {type(x) for x in items}
    if len(types) == 1:
        (t,) = types
        if issubclass(t, bool):
            return "bools"
        if issubclass(t, numbers.Integral):
            return "ints"
        if issubclass(t, numbers.Real):
            return "floats"
        if issubclass(t, str):
            return "strings"
        if t in (list, tuple, dict):
            return t.__name__ + "s"
        return t.__name__
    return "items"


def summarise(value, *, above: int = ELIDE_ABOVE):
    """``value`` itself, or an :class:`_Elided` summary when it is a long sequence.

    A numeric sequence keeps its range (``<5753 floats 15…130.04>``), since
    that is what a reader checks first; a sequence of anything else keeps its
    element type (``<212 Reflection>``).  A dict, or a sequence short enough to
    keep, is walked one level at a time, because a result's ticks are a dict
    of thousand-long lists.
    """
    if isinstance(value, dict):
        return {k: summarise(v, above=above) for k, v in value.items()}
    if isinstance(value, np.ndarray):
        if value.size <= above:
            return value
        shape = "×".join(str(n) for n in value.shape)
        if np.issubdtype(value.dtype, np.number) and np.isfinite(value).any():
            finite = value[np.isfinite(value)]
            return _Elided(f"<{shape} {value.dtype} {finite.min():g}…{finite.max():g}>")
        return _Elided(f"<{shape} {value.dtype}>")
    if not isinstance(value, (list, tuple)):
        return value
    if len(value) <= above:
        kept = [summarise(v, above=above) for v in value]
        return type(value)(kept) if isinstance(value, list) else tuple(kept)
    kind = _kind(value)
    if kind in ("floats", "ints"):
        arr = np.asarray(value, dtype=float)
        finite = arr[np.isfinite(arr)]
        if finite.size:
            return _Elided(f"<{len(value)} {kind} {finite.min():g}…{finite.max():g}>")
    return _Elided(f"<{len(value)} {kind}>")


# ---------------------------------------------------------------------------
# The text tree every schema prints as (``Base.__str__``)
# ---------------------------------------------------------------------------

#: A model that fits on one line within this many characters prints that way.
ONE_LINE_WIDTH = 100

#: A list of models longer than this shows its first rows and a count: a
#: structure's 19 atoms stay whole, a reflection list's 2000 do not.
TREE_ROWS = 32


def _number(value: float, esd: float | None = None) -> str:
    from .crystallography.cif import format_su
    if esd is not None and esd > 0 and np.isfinite(esd) and np.isfinite(value):
        return format_su(value, esd)
    return f"{value:.8g}"


#: The significant figures :func:`significant` keeps: enough to read a number
#: against a threshold quoted to one or two (five steps per FWHM, a gain of
#: 0.3, a score of 0.05).
SIGNIFICANT = 3


def significant(value: float, digits: int = SIGNIFICANT) -> str:
    """``value`` to ``digits`` significant figures: ``4.65``, ``146``, ``0.843``.

    Written out from 1e-4 up to 1e6, with the digits before the point kept
    whole (``10000``, never ``1e+04``), and as ``1e+07`` outside that range.
    A view passes its bare numbers through this; a ``Parameter`` never comes
    here, since a cell length needs its decimals and its esd says how many
    (:func:`_number`).
    """
    if not math.isfinite(value) or value == 0:
        return f"{value:g}"
    # the decade after rounding, so 9.996 prints "10.0" and not "10.00"
    decade = math.floor(math.log10(abs(float(f"{value:.{digits - 1}e}"))))
    if not -4 <= decade < 6:
        return f"{value:.{digits}g}"
    return f"{value:.{max(digits - 1 - decade, 0)}f}"


def parameter_text(p) -> str:
    """One ``Parameter`` on one line: ``value(esd) unit``, and ``(vary)`` when
    it is free.  Bounds stay in ``Refinement.parameters()``, where every row
    carries them."""
    from .help import UNIT_DISPLAY
    text = _number(p.value, p.stderr)
    if p.unit:
        text += " " + UNIT_DISPLAY.get(p.unit, p.unit)
    if p.vary:
        text += " (vary)"
    return text


def _is_model(value) -> bool:
    from .schemas.common import Base
    return isinstance(value, Base)


def _is_parameter(value) -> bool:
    from .schemas.common import Parameter
    return isinstance(value, Parameter)


def _shown(value) -> bool:
    """A field the tree prints: ``None`` and empty containers say nothing."""
    if value is None:
        return False
    if isinstance(value, (list, tuple, dict)) and not value:
        return False
    return True


def _leaf(value) -> str | None:
    """A value's one-line text, or ``None`` when it needs lines of its own."""
    if _is_parameter(value):
        return parameter_text(value)
    if _is_model(value):
        return None
    if isinstance(value, float):
        return _number(value)
    if isinstance(value, (list, tuple, dict)):
        items = value.values() if isinstance(value, dict) else value
        if any(_is_model(v) and not _is_parameter(v) for v in items):
            return None     # rows of models: `_container_lines` lists them
    if isinstance(value, (list, tuple, dict, np.ndarray)):
        value = summarise(value)
        if isinstance(value, _Elided):
            return value.text
        leaves = [_leaf(v) for v in (value.values() if isinstance(value, dict) else value)]
        if any(p is None for p in leaves):
            return None
        parts = ([f"{k}: {p}" for k, p in zip(value, leaves, strict=True)]
                 if isinstance(value, dict) else leaves)
        bra, ket = ("{", "}") if isinstance(value, dict) else ("[", "]")
        return bra + ", ".join(parts) + ket
    return repr(value) if isinstance(value, str) else str(value)


def _fields(model, order=None, show_empty=False, keep=()):
    names = list(order) if order is not None else list(type(model).model_fields)
    return [(name, getattr(model, name)) for name in names
            if show_empty or name in keep or _shown(getattr(model, name))]


def _one_line(model) -> str | None:
    parts = []
    for name, value in _fields(model):
        leaf = _leaf(value)
        if leaf is None:
            return None
        parts.append(f"{name}={leaf}")
    line = f"{type(model).__name__}({', '.join(parts)})"
    return line if len(line) <= ONE_LINE_WIDTH else None


def _aligned(rows: list, indent: str) -> list[str]:
    """One block's lines.  A ``(label, text)`` row is one line, its text in
    the column after the block's longest label; a list of lines (a nested
    block, opened by its own first line) is kept as it was built."""
    width = max((len(row[0]) for row in rows if isinstance(row, tuple)), default=0)
    lines = []
    for row in rows:
        if isinstance(row, tuple):
            label, text = row
            lines.append(f"{indent}{label.ljust(width)} {text}")
        else:
            lines += row
    return lines


def _tree_lines(model, indent: str, order=None, show_empty=False, values=None) -> list[str]:
    values = values or {}
    rows: list = []
    for name, value in _fields(model, order, show_empty, keep=values):
        label = f"{name}:"
        if name in values:
            rows.append((label, values[name]))
            continue
        if show_empty and not _shown(value):
            rows.append((label, "None" if value is None else "none"))
            continue
        leaf = _leaf(value)
        long_container = (leaf is not None and len(indent) + len(name) + len(leaf) > ONE_LINE_WIDTH
                          and isinstance(value, (list, tuple, dict))
                          and not isinstance(summarise(value), _Elided))
        if leaf is not None and not long_container:
            rows.append((label, leaf))
        elif _is_model(value):
            first, *rest = _model_lines("", value, indent + "  ")
            rows.append((label, first) if not rest else [f"{indent}{label} {first}", *rest])
        else:
            rows.append(_container_lines(name, value, indent))
    return _aligned(rows, indent)


def _designed(model) -> bool:
    """Whether ``model``'s class draws its own view (overrides ``Base.__str__``)."""
    from .schemas.common import Base
    return type(model).__str__ is not Base.__str__


def _model_lines(prefix: str, model, indent: str) -> list[str]:
    """A nested model after ``prefix``: its designed view when it has one,
    else on one line when it fits, else as a tree indented by ``indent``."""
    if _designed(model):
        first, *rest = str(model).splitlines() or [""]
        return [prefix + first] + [indent + line for line in rest]
    one = _one_line(model)
    if one is not None:
        return [prefix + one]
    return [prefix + type(model).__name__] + _tree_lines(model, indent)


def _container_lines(name, value, indent: str) -> list[str]:
    items = list(value.items()) if isinstance(value, dict) else list(enumerate(value))
    lines = [f"{indent}{name}: {len(items)} {_kind([v for _, v in items])}"]
    rows: list = []
    for key, item in items[:TREE_ROWS]:
        key_text = f"[{key}]" if isinstance(value, (list, tuple)) else str(key)
        label = key_text if isinstance(value, (list, tuple)) else key_text + ":"
        leaf = _leaf(item)
        if leaf is not None:
            rows.append((label, leaf))
        elif _is_model(item):
            first, *rest = _model_lines("", item, indent + "    ")
            rows.append((label, first) if not rest
                        else [f"{indent}  {label} {first}", *rest])
        else:
            rows.append(_container_lines(key_text, item, indent + "  "))
    lines += _aligned(rows, indent + "  ")
    if len(items) > TREE_ROWS:
        lines.append(f"{indent}  … {len(items) - TREE_ROWS} more")
    return lines


def tree(model, *, order=None, groups=None, show_empty: bool = False,
         head: str | None = None, values=None) -> str:
    """A schema as an indented field tree: one line per ``Parameter``, a model
    that fits on one line kept on one, ``None`` and empty fields left out.
    The one-line fields of a block print their values in one column.

    A designed view passes ``order`` (the fields to print, in reading order)
    and ``show_empty`` where an empty list is itself a finding ("checked, and
    nothing"), and ``head`` for a first line that says what the object is of.
    ``groups`` replaces ``order`` with ``(heading, fields)`` pairs, each field
    printed under its heading.  ``values`` maps a field to the text it prints:
    a number cut to its meaningful digits (:func:`significant`), or an empty
    state that says why it is empty.  The view reads that text off fields.
    """
    if _is_parameter(model):
        return parameter_text(model)
    if (order is None and groups is None and not show_empty and head is None
            and values is None):
        one = _one_line(model)
        if one is not None:
            return one
    first = head or type(model).__name__
    if groups is None:
        return "\n".join([first] + _tree_lines(model, "  ", order, show_empty, values))
    lines = [first]
    for heading, names in groups:
        lines += ["  " + heading, *_tree_lines(model, "    ", names, show_empty, values)]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The parameter table: one row builder, a text and an HTML renderer
# ---------------------------------------------------------------------------

def row_state(row) -> str:
    """What a ``ParameterRow`` is doing, in the field's own words: ``vary``,
    ``fixed``, or the first of ``locked``, ``tied = …``, ``mode_fixed``,
    ``held``, ``needs_held_cell`` that holds it (``held_because``'s order)."""
    if row.locked:
        return "locked"
    if row.tie is not None:
        return f"tied = {row.tie.describe()}"
    if row.mode_fixed:
        return "mode_fixed"
    if row.held:
        return "held"
    if row.needs_held_cell:
        return "needs_held_cell"
    return "vary" if row.vary else "fixed"


def parameter_cells(row) -> tuple[str, str, str]:
    """``(path, value(esd), state)``: the one row both renderers draw."""
    return row.path, _number(row.value, row.esd), row_state(row)


def refined_parameter_text(p) -> str:
    """A ``RefinedParameter`` on one line, as a ``ParameterRow`` prints:
    ``path  value(esd)  state``.  The state is ``vary``, or ``tied`` for a row
    that did not vary, since a result lists only rows that varied or were
    tied.  ``at_bound`` follows when the bound guard found the row there, the
    equations that set it when any did, and the profile interval's ends when
    the row carries one (WP-2002), ``?`` for an end its side did not find."""
    cells = [p.path, _number(p.value, p.stderr), "vary" if p.vary else "tied"]
    if p.at_bound:
        cells.append("at_bound")
    if p.equations:
        cells.append("equations: " + ", ".join(p.equations))
    if p.interval is not None:
        ends = ["?" if v is None else f"{v:.6g}"
                for v in (p.interval.lower, p.interval.upper)]
        cells.append(f"interval [{ends[0]}, {ends[1]}]")
    return "  ".join(cells)


def distance_text(d) -> str:
    """A ``GeometryDistance`` on one line: ``P3–O5  1.5331(50) Å  2_554``.
    The symmetry code is the second atom's, left out when it is the identity
    (``.``) or unknown (``None``); ``contact`` ends a nonbonded row."""
    cells = [f"{d.atom_1}–{d.atom_2}", _number(d.distance, d.stderr) + " Å"]
    if d.symmetry_2 not in (".", None):
        cells.append(d.symmetry_2)
    if not d.bonded:
        cells.append("contact")
    return "  ".join(cells)


MICROSTRUCTURE_HEADER = ("path", "value", "unavailable")


def microstructure_sections(block) -> tuple[str, list[tuple[str, str, str]], list[str]]:
    """A ``PhaseMicrostructure`` as a head line, one row a term and two tail
    lines: :meth:`__str__` lays the rows out as text, ``_repr_html_`` as a table.

    The head carries the phase and the two constants a size was read with, the
    rows each reading with its esd (Å for a size, Δd/d bare) or the reason it
    has none, and the tail the agreement ratios and the separability verdict
    beside them.  Those four print even when ``None``, since ``None`` there is
    the field's answer: not readable, or not assessed.
    """
    def ratio(x):
        return "None" if x is None else f"{x:.3g}"

    wavelength = "None" if block.wavelength is None else f"{block.wavelength:g} Å"
    name = f"{block.phase_name} " if block.phase_name else ""
    head = (f"PhaseMicrostructure: {name}(phase {block.phase_index}), "
            f"scherrer_k {block.scherrer_k:g}, wavelength {wavelength}")
    rows = []
    for t in block.terms:
        value = "" if t.value is None else _number(t.value, t.esd)
        if value and t.kind == "size":
            value += " Å"
        rows.append((t.path, value, t.unavailable or ""))
    tail = [f"size_agreement: {ratio(block.size_agreement)}   "
            f"strain_agreement: {ratio(block.strain_agreement)}",
            f"separable: {block.separable}   "
            f"size_strain_collinearity: {ratio(block.size_strain_collinearity)}"]
    return head, rows, tail


def trajectory_sections(traj) -> tuple[str, tuple[str, str, str], list[tuple[str, str, str]]]:
    """A ``Trajectory`` as a head line, a header and one row a point:
    ``(label, x, value(esd))``.  The x column is headed by ``x_label``, so
    a temperature reads as ``T (K)`` and a series without a coordinate as
    ``index``.  A point with no esd prints its value alone, and one with no
    label an empty cell, since a trajectory built by hand may carry none.
    A missing x is an empty cell too, so every value gets its row."""
    n = len(traj.value)
    head = f"Trajectory: {traj.path}, {n} point(s)"

    def padded(items, fill):
        return [*items[:n], *[fill] * (n - len(items))]

    xs = [f"{x:g}" for x in traj.x[:n]]
    rows = [(label, x, _number(v, esd))
            for label, x, v, esd in zip(padded(traj.labels, ""), padded(xs, ""),
                                        traj.value, padded(traj.stderr, None),
                                        strict=True)]
    return head, ("label", traj.x_label, "value"), rows


def table_text(header: tuple[str, ...], rows: list[tuple[str, ...]], indent: str = "") -> list[str]:
    """Left-aligned columns, two spaces apart, header first."""
    widths = [max(len(c) for c in col) for col in zip(header, *rows)]
    out = []
    for cells in (header, *rows):
        line = "  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()
        out.append(indent + line)
    return out


def table_html(header: tuple[str, ...], rows: list[tuple[str, ...]], caption: str | None = None) -> str:
    """The same rows as a bare ``<table>``: no style, so the notebook's own
    theme draws it and a sanitiser has nothing to strip."""
    from html import escape
    parts = ["<table>"]
    if caption:
        parts.append(f"<caption>{escape(caption)}</caption>")
    parts.append("<thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in header)
                 + "</tr></thead><tbody>")
    for cells in rows:
        parts.append("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in cells) + "</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


PARAMETER_HEADER = ("path", "value", "state")


def pre_html(text: str) -> str:
    """Text in a ``<pre>``, escaped: the HTML form of a view with no table."""
    from html import escape
    return f"<pre>{escape(text)}</pre>"


def diagnostics_html(diagnostics, context: str | None = None) -> str:
    """Each diagnostic as a ``<details>``: the headline shown, the rest folded.

    The summary is ``str(d)``'s first line.  The fold holds what the text form
    prints under it (``at:``, ``help:``) and the code's explanation, which
    the text form leaves out because it is the same for every finding
    (WP-1985).  ``context`` names what the findings are about, such as one
    indexing candidate.
    """
    from html import escape
    parts = []
    for d in diagnostics:
        head, *rest = str(d).splitlines()
        if context:
            rest.insert(0, f"  on: {context}")
        body = "".join(f"<p>{escape(line.strip())}</p>" for line in rest)
        if d.explanation:
            body += f"<p>{escape(d.explanation)}</p>"
        parts.append(f"<details><summary>{escape(head)}</summary>{body}</details>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Refinement (not a schema, so it has no tree)
# ---------------------------------------------------------------------------

def refinement_parts(ref) -> tuple[list[str], list, int]:
    """The head lines, the free rows and the row count for a ``Refinement``.

    Reads the object's own fields and builds its parameter table, which is a
    pure function of them (milliseconds, no fit, no file written).
    """
    phases = ", ".join(f"{p.name} ({p.space_group})" for p in ref.structure.phases)
    n = len(ref.structure.phases)
    head = [f"Refinement of {n} phase{'s' if n != 1 else ''}: {phases}",
            f"  mode: {ref._mode}   backend: {ref._backend}   solver: {ref._solver}"]
    result = ref.result_
    if result is None:
        head.append("  last fit: none")
    else:
        st = result.statistics
        head.append(f"  last fit: {result.status}   Rwp {st.rwp:.4f}   GoF {st.gof:.2f}"
                    f"   {len(result.diagnostics)} diagnostics")
    tree = ref.history
    if tree is not None and len(tree):
        head.append(f"  history: {len(tree)} nodes, head {tree.head}")
    try:
        rows = ref.parameters()
    except Exception as exc:   # a display never raises over a model it is showing
        head.append(f"  parameters: not available ({type(exc).__name__}: {exc})")
        return head, [], 0
    free = [r for r in rows if row_state(r) == "vary"]   # a held vary flag is not free
    head.append(f"  parameters: {len(free)} of {len(rows)} vary; "
                "ref.parameters() lists every row")
    return head, free, len(rows)


def refinement_text(ref) -> str:
    head, free, _ = refinement_parts(ref)
    if free:
        head += table_text(PARAMETER_HEADER, [parameter_cells(r) for r in free], "    ")
    return "\n".join(head)


def refinement_html(ref) -> str:
    head, free, _ = refinement_parts(ref)
    html = pre_html("\n".join(head))
    if free:
        html += table_html(PARAMETER_HEADER, [parameter_cells(r) for r in free])
    return html
