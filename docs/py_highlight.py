# A Python signature coloured the way a Python code block is (WP-2023).
#
# Sphinx writes each piece of a signature as a span whose class is already a
# Pygments token name (`n`, `o`, `p`, `w`, `k`), and pydata-sphinx-theme's
# `pygments.css` colours those classes only under `.highlight`, so the
# signature came out one ink.  This handler puts `highlight` on each
# Python-domain signature and relabels the pieces Sphinx leaves as a bare name:
#
#     the call's name          -> nf  (a class's -> nc)
#     an annotation's type     -> nc, a built-in class -> nb, None -> kc
#     a default                -> its literal's kind: s, mi, mf, kc; else as is
#
# A parameter's own name stays `n`.  The classes carry no text, so the
# markdown twin (docs/markdown_twin.py) reads the same words; and every colour
# is Pygments', `custom.css` adding selectors only: the signature keeps its own
# ground and the `:target` tint, and a parameter name is set upright.
#
# On `doctree-resolved`, after the type links are resolved, and ahead of the
# twin's own handler at priority 900.

import ast as _ast
import builtins as _builtins
import inspect as _inspect
import warnings as _warnings

from docutils import nodes as _nodes
from sphinx import addnodes as _addnodes

#: The object kinds whose name is a call's, and a class's.
_FUNCTIONS = frozenset({"function", "method", "classmethod", "staticmethod", "decorator",
                        "decoratormethod"})
_CLASSES = frozenset({"class", "exception"})


def _type_class(text: str) -> str:
    """The token of one name in an annotation."""
    if text == "None":
        return "kc"
    if _inspect.isclass(getattr(_builtins, text, None)):
        return "nb"
    return "nc"


def _default_class(text: str) -> str | None:
    """The token of a default, by the kind of literal it is; None for anything
    `ast.literal_eval` does not read as one scalar (`-inf`, a factory)."""
    try:
        with _warnings.catch_warnings():
            # A default like `'\d'` is a SyntaxWarning to the parser, not to the page.
            _warnings.simplefilter("ignore", SyntaxWarning)
            value = _ast.literal_eval(text.strip())
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    if value is None or isinstance(value, bool):
        return "kc"
    if isinstance(value, (str, bytes)):
        return "s"
    if isinstance(value, int):
        return "mi"
    if isinstance(value, float):
        return "mf"
    return None


def _wrap(text: _nodes.Text, *classes: str) -> None:
    text.parent.replace(text, _nodes.inline(str(text), str(text), classes=list(classes)))


def _annotation(nodes) -> None:
    """Relabel an annotation's names: a link's and a bare one's alike."""
    for node in list(nodes):
        if isinstance(node, _nodes.Text):
            if node.strip():
                _wrap(node, _type_class(node.strip()))
        elif isinstance(node, _nodes.reference):
            node["classes"].append(_type_class(node.astext()))
        # A `desc_sig_name` inside an annotation is a keyword's name in a call
        # (`Annotated[str, Check(len=10)]`), not a type: it stays `n`.


def _default(node: _nodes.Element) -> None:
    token = _default_class(node.astext())
    if token:
        node["classes"].append(token)


def _parameter(param: _addnodes.desc_parameter) -> None:
    """`name: annotation = default`; the name and its `*` stay as they are."""
    after = None
    for child in param.children:
        if isinstance(child, _addnodes.desc_sig_punctuation) and child.astext() == ":":
            after = "annotation"
        elif isinstance(child, _addnodes.desc_sig_operator) and child.astext() == "=":
            after = "default"
        elif after == "annotation" and isinstance(child, _addnodes.desc_sig_name):
            _annotation(child.children)
        elif isinstance(child, _nodes.Element) and "default_value" in child["classes"]:
            # A parameter Sphinx could not parse is one bare `Text` of the whole list.
            _default(child)


def _property(node: _addnodes.desc_annotation) -> None:
    """An attribute's `: annotation` or ` = value`, which Sphinx writes as a
    `desc_annotation` of punctuation and bare text."""
    signs = [c for c in node.children if isinstance(c, _addnodes.desc_sig_punctuation)]
    if not signs:
        return
    rest = node.children[node.index(signs[0]) + 1:]
    if signs[0].astext() == ":":
        _annotation(rest)
    elif signs[0].astext() == "=":
        for text in [c for c in rest if isinstance(c, _nodes.Text) and c.strip()]:
            token = _default_class(text)
            _wrap(text, *(["default_value"] + ([token] if token else [])))


def colour_signature(signode: _addnodes.desc_signature, objtype: str) -> None:
    signode["classes"].append("highlight")
    for child in signode.children:
        if isinstance(child, _addnodes.desc_name):
            token = "nf" if objtype in _FUNCTIONS else "nc" if objtype in _CLASSES else None
            if token:
                child["classes"].append(token)
        elif isinstance(child, _addnodes.desc_annotation):
            _property(child)
        elif isinstance(child, _addnodes.desc_returns):
            _annotation(child.children)
    for param in signode.findall(_addnodes.desc_parameter):
        _parameter(param)


def _on_doctree_resolved(_app, doctree, _docname) -> None:
    for desc in doctree.findall(_addnodes.desc):
        if desc.get("domain") == "py":
            for signode in desc.children:
                if isinstance(signode, _addnodes.desc_signature):
                    colour_signature(signode, desc.get("objtype", ""))


def setup(app):
    app.connect("doctree-resolved", _on_doctree_resolved)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
