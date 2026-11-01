# A markdown twin of every page of the manual, and the llms.txt that
# lists them (WP-1980).  An agent reads these, never the HTML: WP-1975 § F8
# chose a clean markdown copy of each page beside the skill.
#
# The twin is written by the HTML build itself, beside its page, as
# `page.html.md`: the llms.txt proposal (https://llmstxt.org) names that
# spelling, and a twin inside the HTML output reaches every version WP-1979
# deploys with no step of its own.  It is translated from the doctree the
# HTML page is written from, after Sphinx has resolved every reference, so a
# link in a twin is the page's own link with `.md` appended.
#
# The translator is sphinx-markdown-builder's, which WP-1975's spike measured
# closest to clean.  What it loses on this tree is mended in three places.
# `_normalise` rewrites the nodes it does not know into ones it does: a
# sphinx-design card, dropdown or tab, a mermaid diagram, the dark half of a
# figure pair and the comments and icons the HTML carries.
# `_write_inline_figures` writes a notebook's inline figure out as a file.
# `TwinTranslator` writes what needs its own markdown: an admonition as a
# labelled blockquote, a bibliography entry, an image path the HTML build
# copied, and a table with no column padding, which measured 9 % of the
# parameter map's twin.

import base64 as _base64
import hashlib as _hashlib
import html as _html
import posixpath as _posixpath
import re as _re
from pathlib import Path as _Path

from docutils import nodes as _nodes
from sphinx import addnodes as _addnodes
from sphinx.util.osutil import relative_uri as _relative_uri
from sphinx_markdown_builder.contexts import IndentContext as _IndentContext
from sphinx_markdown_builder.contexts import SubContextParams as _SubContextParams
from sphinx_markdown_builder.contexts import TableContext as _TableContext
from sphinx_markdown_builder.contexts import WrappedContext as _WrappedContext
from sphinx_markdown_builder.translator import MarkdownTranslator as _MarkdownTranslator
from sphinx_markdown_builder.translator import pushing_context as _pushing_context

#: Appended to a page's `.html` name, as the llms.txt proposal spells it.
TWIN_SUFFIX = ".md"

#: An internal link to a page, split before its anchor.
_PAGE_LINK = _re.compile(r"^(?P<page>[^:#?]*\.html)(?P<rest>[#?].*)?$")

#: The first sentence of a paragraph, split as `_first_sentence` in
#: tests/test_manual.py splits it.  A full stop ends one only before
#: whitespace, so a dotted name such as `rx.fit` does not.
_SENTENCE_END = _re.compile(r"(?<=[.?!])\s")


def _is_component(node, *names: str) -> bool:
    return isinstance(node, _nodes.Element) and node.get("design_component") in names


def _bold(children) -> _nodes.paragraph:
    return _nodes.paragraph("", "", _nodes.strong("", "", *children))


def _without_raw(node: _nodes.Element) -> list:
    """A title's children with the HTML icons sphinx-design puts beside it."""
    return [child for child in node.deepcopy().children if not isinstance(child, _nodes.raw)]


def _normalise(doctree: _nodes.document) -> None:
    """Rewrite the nodes the markdown translator cannot write into ones it can.

    Every rewrite keeps the text a reader of the HTML page sees.  Only what is
    there for the browser goes: a dark figure that repeats its light twin, an
    HTML comment, an icon, a radio button that switches tabs.
    """
    for node in list(doctree.findall(_nodes.raw)):
        text = node.astext().lstrip()
        if "html" in node.get("format", "").split() and text.startswith(("<!--", "<svg")):
            node.parent.remove(node)
    for node in list(doctree.findall(_nodes.image)):
        if "only-dark" in node["classes"]:
            node.parent.remove(node)
    # An API signature's bare `*` carries a tooltip (PEP 3102); the `*` stays.
    for signature in list(doctree.findall(_addnodes.desc_signature)):
        for node in list(signature.findall(_nodes.abbreviation)):
            node.replace_self(_nodes.Text(node.astext()))
    # A model's fields (`py:fields`, docs/py_fields.py) are a list, where the
    # translator writes every signature as a heading of its own.
    for node in list(doctree.findall(_addnodes.desc)):
        if node.get("desctype") == "fields":
            node.replace_self(_nodes.bullet_list("", *(
                _nodes.list_item("", _nodes.paragraph("", "", _nodes.literal(text, text)))
                for text in (sig.astext() for sig in node.findall(_addnodes.desc_signature)))))
    for node in list(doctree.findall(lambda n: type(n).__name__ == "mermaid")):
        code = node["code"].replace("\\*", "*")
        node.replace_self(_nodes.literal_block(code, code, language="mermaid"))
    for node in list(doctree.findall(_nodes.admonition)):
        if isinstance(node[0], _nodes.title):
            node["twin_label"] = node[0].astext()
            node.remove(node[0])
    # A card is a title, its text and one link that covers the whole card.
    for card in list(doctree.findall(lambda n: _is_component(n, "card"))):
        link = next(card.findall(lambda n: isinstance(n, _nodes.reference)
                                 and "sd-stretched-link" in n["classes"]), None)
        title = next(card.findall(lambda n: _is_component(n, "card-title")), None)
        if link is not None:
            link.parent.remove(link)
        out = []
        if title is not None:
            text = _without_raw(title)
            if link is not None:
                text = [_nodes.reference("", "", *text, **{
                    key: link[key] for key in ("refuri", "refid", "internal") if key in link})]
            out.append(_bold(text))
            title.parent.remove(title)
        for part in card.findall(
                lambda n: _is_component(n, "card-header", "card-body", "card-footer")):
            out.extend(part.children)
        card.replace_self(out)
    for node in list(doctree.findall(lambda n: type(n).__name__ == "dropdown_main")):
        title, *body = node.children
        node.replace_self([_bold(_without_raw(title)), *body])
    for node in list(doctree.findall(lambda n: type(n).__name__ == "sd_tab_input")):
        node.parent.remove(node)
    for node in list(doctree.findall(lambda n: type(n).__name__ == "sd_tab_label")):
        node.replace_self(_bold(_without_raw(node)))
    for node in list(doctree.findall(lambda n: type(n).__name__ == "PassthroughTextElement")):
        node.replace_self(node.children)
    # A bibliography entry: its label in bold, then the reference, after the
    # anchor a citation in the text links to.
    for node in list(doctree.findall(_nodes.citation)):
        label = node.next_node(_nodes.label)
        text = [child for paragraph in node.findall(_nodes.paragraph) for child in paragraph.children]
        node.replace_self([*(_nodes.target(refid=ref) for ref in node["ids"]),
                           _nodes.paragraph("", "", _nodes.strong("", f"[{label.astext()}]"),
                                            _nodes.Text(" "), *text)])


#: One `<img>` tag, and the light half of a figure pair drawn inline.
_IMG_TAG = _re.compile(r"<img\b[^>]*>")
#: What a figure block holds besides its images: the `<div>` round them and
#: the stylesheet that shows one half per theme.
_FIGURE_WRAPPING = _re.compile(r"</?div\b[^>]*>|<style\b[^>]*>.*?</style\s*>", _re.S)
_INLINE_LIGHT_PNG = _re.compile(
    r'\bclass="[^"]*\bonly-light\b[^"]*"[^>]*\bsrc="data:image/png;base64,([^"]+)"')
_ALT = _re.compile(r'\balt="([^"]*)"')


def _write_inline_figures(doctree: _nodes.document, builder, docname: str) -> None:
    """Each inline figure pair as a link to its light half, written as a file.

    A notebook's figure reaches the HTML page as one raw block holding a light
    and a dark PNG inline, as rietx's notebook display draws it.  Copied as it
    is, the base64 was most of a tutorial's twin: six of the seven measured
    62 752 to 551 259 characters, and 7 561 to 39 799 with each figure a link
    (WP-1986).
    So the light half is written into `_images/` under its content's hash and
    linked, as a page's figure pair is, and the dark half and the stylesheet
    that switches between them go.  A raw block holding anything else is left
    as it is.
    """
    for node in list(doctree.findall(_nodes.raw)):
        text = node.astext()
        if "html" not in node.get("format", "").split():
            continue
        tags = _IMG_TAG.findall(text)
        light = [m for m in map(_INLINE_LIGHT_PNG.search, tags) if m]
        if len(light) != 1 or _FIGURE_WRAPPING.sub("", _IMG_TAG.sub("", text)).strip():
            continue
        data = _base64.b64decode(light[0][1])
        name = f"twin-{_hashlib.sha256(data).hexdigest()[:16]}.png"
        path = _Path(builder.outdir) / builder.imagedir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        alt = _ALT.search(light[0].string)
        node.replace_self(_nodes.image(
            uri=_relative_uri(builder.get_target_uri(docname), f"{builder.imagedir}/{name}"),
            alt=_html.unescape(alt[1]) if alt else ""))


class _CompactTable(_TableContext):
    """A GitHub table with no padding: the cells as written, `|` escaped."""

    def make(self):
        rows = [self.make_row(row) for row in [*self.headers, *self.body]]
        if not rows:
            return self.internal_context.make()
        lines = ["| " + " | ".join(cell.strip().replace("|", "\\|") for cell in row) + " |"
                 for row in rows]
        lines.insert(1, "|" + "---|" * len(rows[0]))
        prefix = self.internal_context.make()
        return (prefix + "\n\n" if prefix else "") + "\n".join(lines)


class TwinTranslator(_MarkdownTranslator):
    """sphinx-markdown-builder's translator, writing into the HTML build."""

    def __init__(self, document, builder, docname: str):
        super().__init__(document, builder)
        self._page_uri = builder.get_target_uri(docname)

    def _push_box(self, title: str):
        # The base calls this for its own kinds, named in capitals ("SEE ALSO").
        self._push_label(title.capitalize())

    def _push_label(self, label: str):
        # A labelled blockquote, where the base writes a heading: a heading
        # would open a section of its own in the page the twin copies.
        self._push_context(_IndentContext("> ", empty=True, params=_SubContextParams(2, 2)))
        self.add(f"**{label}**", suffix_eol=2)

    @_pushing_context
    def visit_admonition(self, node):
        # An author's title is kept as written, an acronym ("TOPAS") included.
        self._push_label(node.get("twin_label", "Note"))

    @_pushing_context
    def visit_table(self, _node):
        self._push_context(_CompactTable(params=_SubContextParams(2, 2)))

    def _fetch_ref_uri(self, node):
        uri = super()._fetch_ref_uri(node)
        if node.get("internal", self.status.default_ref_internal):
            match = _PAGE_LINK.match(uri)
            if match:
                return match["page"] + TWIN_SUFFIX + (match["rest"] or "")
        return uri

    def visit_image(self, node):
        uri = node["uri"]
        images = self.builder.env.images
        if uri in images:
            uri = _relative_uri(self._page_uri, f"{self.builder.imagedir}/{images[uri][1]}")
        self.add(f"![{node.get('alt', '')}]({uri})")

    @_pushing_context
    def visit_download_reference(self, node):
        if "refuri" in node:
            target = node["refuri"]
        elif "filename" in node:
            target = _relative_uri(self._page_uri, f"_downloads/{node['filename']}")
        else:
            target = node.get("reftarget", "")
        self._push_context(_WrappedContext("[", f"]({target})"))


def twin_path(builder, docname: str) -> str:
    """A page's twin, relative to the build's root."""
    return builder.get_target_uri(docname) + TWIN_SUFFIX


def answer_sentence(twin: str) -> str:
    """The first sentence of the paragraph under a twin's title.

    The page contract puts an answer sentence there on every page.
    """
    paragraphs = [p.strip() for p in twin.split("\n\n")]
    for heading, paragraph in zip(paragraphs, paragraphs[1:]):
        # The title's line is the block's last: its section's anchors precede it.
        if heading.rpartition("\n")[2].startswith("# "):
            return _SENTENCE_END.split(" ".join(paragraph.split()), maxsplit=1)[0]
    return ""


def _reading_order(env, root: str) -> list[str]:
    """Every page the root's toctrees reach, in the order the sidebar shows them."""
    order: list[str] = []

    def visit(docname: str) -> None:
        if docname in order:
            return
        order.append(docname)
        for child in env.toctree_includes.get(docname, []):
            visit(child)

    visit(root)
    return order


#: A markdown link or image target that is relative to the page it sits in.
_RELATIVE_LINK = _re.compile(r"(\]\()(?![a-z][a-z0-9+.-]*:|#|/)([^)\s]+)\)")


def _from_root(twin: str, path: str) -> str:
    """A twin's relative links rewritten to start from the build's root."""
    base = path.rpartition("/")[0]
    if not base:
        return twin

    def rebase(match):
        target = _posixpath.normpath(f"{base}/{match[2]}")
        return f"{match[1]}{target})"

    return _RELATIVE_LINK.sub(rebase, twin)


def write_llms_txt(app) -> None:
    """`llms.txt` and `llms-full.txt` at the build's root, from the twins.

    The llms.txt proposal's shape: the project as the H1, the front page's
    answer sentence as the summary, then one H2 per tab and one line per page,
    its link and its answer sentence.  `llms-full.txt` is every twin in the
    same order, its links rewritten to start from the root it sits at.
    """
    out = _Path(app.outdir)
    root = app.config.root_doc
    twins = {}
    for docname in _reading_order(app.env, root):
        path = twin_path(app.builder, docname)
        if (out / path).is_file():
            twins[docname] = (path, (out / path).read_text(encoding="utf-8"))
    lines = [f"# {app.config.project}", "", f"> {answer_sentence(twins[root][1])}", ""]
    for tab in app.env.toctree_includes.get(root, []):
        lines += [f"## {app.env.titles[tab].astext()}", ""]
        for docname in _reading_order(app.env, tab):
            path, twin = twins[docname]
            # The sentence's own links start from its twin, not from the root.
            summary = _from_root(answer_sentence(twin), path)
            lines.append(f"- [{app.env.titles[docname].astext()}]({path}): {summary}")
        lines.append("")
    (out / "llms.txt").write_text("\n".join(lines), encoding="utf-8")
    full = "\n\n".join(_from_root(twin, path).strip() for path, twin in twins.values())
    (out / "llms-full.txt").write_text(full + "\n", encoding="utf-8")


# Only the `html` builder: a page of `dirhtml` or `singlehtml` is not
# `<docname>.html`, so `TWIN_SUFFIX` would not name a file beside it.
def _on_doctree_resolved(app, doctree, docname: str) -> None:
    if app.builder.name == "html":
        write_twin(app, doctree, docname)


def _on_build_finished(app, exception) -> None:
    if exception is None and app.builder.name == "html":
        write_llms_txt(app)


def _on_config_inited(_app, config) -> None:
    # A link into a twin keeps the HTML page's fragment, which names a
    # section's id, so every section writes its ids as anchors.
    config.markdown_anchor_sections = True


def setup(app):
    # The translator reads sphinx-markdown-builder's `markdown_*` settings,
    # so its extension is loaded for them; the builder it adds is not used.
    app.setup_extension("sphinx_markdown_builder")
    app.connect("config-inited", _on_config_inited)
    # Late, so every other handler has finished with the doctree first.
    app.connect("doctree-resolved", _on_doctree_resolved, priority=900)
    app.connect("build-finished", _on_build_finished)
    return {"parallel_read_safe": True, "parallel_write_safe": True}


def write_twin(app, doctree: _nodes.document, docname: str) -> str:
    """Translate one resolved page into markdown and write it beside the HTML."""
    doctree = doctree.deepcopy()
    builder = app.builder
    # Sphinx resolves a toctree only after this event, so a visible one is
    # resolved here the way the HTML builder will, and a hidden one goes.
    for toctree in list(doctree.findall(_addnodes.toctree)):
        resolved = app.env.resolve_toctree(docname, builder, toctree, prune=True)
        if resolved is None:
            toctree.parent.remove(toctree)
        else:
            toctree.replace_self(resolved)
    _write_inline_figures(doctree, builder, docname)
    _normalise(doctree)
    visitor = TwinTranslator(doctree, builder, docname)
    doctree.walkabout(visitor)
    text = visitor.astext().strip() + "\n"
    path = _Path(app.outdir) / twin_path(builder, docname)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text
