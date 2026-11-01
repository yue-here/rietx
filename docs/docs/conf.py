# Sphinx configuration for the manual (WP-1978): six tabs under
# pydata-sphinx-theme.  WP-1975 § I chose the toolchain, and WP-1986 retired
# the tree this one replaced.
#
# The fenced constants, the citation style, the diagram theme, the tutorial
# copy and the `{source}` role are in `docs/sphinx_shared.py`, which the tests
# import too.  The markdown twin and llms.txt are `docs/markdown_twin.py`'s
# (WP-1980).
#
# Each version is hosted at <DOCS_URL>/docs/<version>/ (WP-1979):
# `sphinx_shared.DOCS_VERSION` says which one this build is, and
# `docs/docs_versions.py` assembles the kept versions and writes the
# switcher file every version's menu reads.

import sys as _sys
from importlib.metadata import version as _dist_version
from pathlib import Path as _Path

from rietx._about import DIST_NAME, DOCS_URL, REPO_URL

_sys.path.append(str(_Path(__file__).resolve().parent.parent))
import reference_pages as _reference  # noqa: E402
import sphinx_shared as _shared  # noqa: E402

project = DIST_NAME
author = "rietx developers"
release = _dist_version(DIST_NAME)
version = release

# `myst_nb` in place of `myst_parser`: it runs myst-parser underneath, so every
# `myst_*` setting below still applies, and it adds `.ipynb` as a source for
# the Start tab's notebooks.  They render with the outputs they were
# committed with: `examples/tutorials/build.py` writes those outputs and
# `tests/test_tutorials.py` executes every notebook, so the page shows what
# the tests ran, and executing again here would make the manual's numbers a
# second run's.
extensions = [
    "myst_nb",
    "sphinx_design",
    "sphinxcontrib.bibtex",
    "sphinxcontrib.mermaid",
    # A markdown twin beside every page, and llms.txt (docs/markdown_twin.py).
    "markdown_twin",
    # A model's fields in the API reference, one line each (docs/py_fields.py).
    "py_fields",
    # A signature in the code blocks' colours (docs/py_highlight.py).
    "py_highlight",
]
nb_execution_mode = "off"

mermaid_light_theme = _shared.MERMAID_LIGHT_THEME
mermaid_dark_theme = _shared.MERMAID_DARK_THEME
mermaid_init_config = _shared.MERMAID_INIT_CONFIG

bibtex_bibfiles = [str(_shared.BIBFILE)]
bibtex_default_style = _shared.BIBTEX_DEFAULT_STYLE
bibtex_reference_style = _shared.BIBTEX_REFERENCE_STYLE

myst_enable_extensions = _shared.MYST_EXTENSIONS
myst_substitutions = {
    **_shared.MYST_SUBSTITUTIONS,
    "release": release,
    # The tutorial notebooks, copied in from examples/tutorials/ at every
    # build into the gitignored `start/tutorials/`, whose toctree is
    # `start/tutorials.md`.  The count is what that page quotes.
    "N_TUTORIALS": _shared.copy_tutorials(_Path(__file__).parent / "start" / "tutorials"),
}
# A markdown link to `page.md#a-heading` resolves, so a Concepts or Guides page
# can point at the Theory section behind a claim (tests/test_manual.py).
myst_heading_anchors = 3

# Numbered sections and section-prefixed equation numbers ((3.2), not (2)).
numfig = True
math_numfig = True

# `_generated/` holds the Reference tab's bodies, written below from the code
# that owns each fact (WP-1981).  A committed page `{include}`s each one, so
# Sphinx must not read them as documents of their own.
exclude_patterns = ["_build", "_generated"]

_reference.write_bodies()

# The API reference's objects (WP-2022).  A signature longer than this puts
# one parameter a line; a `Literal` reads as its values joined by `|`; a
# contents entry names the class a method is on (`Refinement.summary()`),
# and not the module, which is `rx` for nearly every one.
python_maximum_signature_line_length = 72
python_display_short_literal_types = True
toc_object_entries_show_parents = "domain"

html_theme = "pydata_sphinx_theme"
html_title = DIST_NAME
# The manual and the landing page are one site (WP-2021), and these two files
# are the landing page's own, read from `docs/landing/src/` rather than
# copied: the favicon (the mark in the site's accent; without one a browser
# falls back to the origin root, which belongs to the user Pages site this
# project sits under) and `tokens.css`, the site's colours and faces.
# `custom.css` maps pydata's names onto the tokens, so it loads after them,
# and `fonts/fonts.css` serves the two faces from this tree.
_LANDING = _Path(__file__).resolve().parent.parent / "landing" / "src"
html_favicon = str(_LANDING / "favicon.svg")
html_static_path = ["_static", str(_LANDING / "tokens.css")]
html_css_files = ["tokens.css", "fonts/fonts.css", "custom.css"]
html_js_files = ["rietx-theme.js"]
# The footer is ours (`_templates/rietx-footer.html`), with no credit to the
# tools that built the page.
html_show_sphinx = False
# The tab's pages and nothing above them: pydata's collapse button is gone,
# since 0.23 keeps no state for it and every click through re-expanded it.
html_sidebars = {"**": ["sidebar-nav-bs"]}
# A release's pages name stable/ as their canonical copy, so a search engine
# sends a reader to the newest release rather than to an old one.
html_baseurl = f"{DOCS_URL}/docs/{'dev' if _shared.DOCS_VERSION == 'dev' else 'stable'}/"
# The header's brand and theme control, the breadcrumb, the sidebar's
# heading, the twin link and the footer are templates of our own
# (`_templates/`, each saying what it replaces).  Every URL and the word reach
# them through the context, never spelled in a template.
templates_path = ["_templates"]
html_context = {
    "rietx_home": DOCS_URL,
    "rietx_name": DIST_NAME,
    "rietx_repo": REPO_URL,
    "rietx_docs_version": _shared.DOCS_VERSION,
    # pydata's, read from the context: follow the system until the reader pins a
    # theme.  Unset, pydata writes an empty mode on a first visit and logs it as
    # invalid before it resets.
    "default_mode": "auto",
}
html_theme_options = {
    "navbar_start": ["rietx-brand"],
    # The tabs follow the brand, as the landing page's links do, rather than
    # starting over the content column: that column's 25 % holds a 100 px
    # brand, and with the version label a release shows, the bar folded onto
    # two rows below 1270 px under "content" and stays on one down to 1110 px
    # here (measured in chromium on the built Concepts page).
    "navbar_align": "left",
    # Six tabs, so none folds into a "More" dropdown.
    "header_links_before_dropdown": 6,
    "navbar_end": ["version-switcher", "navbar-icon-links", "rietx-theme"],
    "switcher": {
        "json_url": "/docs/switcher.json",
        "version_match": _shared.DOCS_VERSION,
    },
    # The switcher file is the deploy's, written after every build, so the
    # build has none to check.
    "check_switcher": False,
    # Dev, and each release older than the newest, says so above every page,
    # quietly for dev and in the warning colour for an old release
    # (`custom.css` § The version banner).
    "show_version_warning_banner": True,
    "icon_links": [
        {"name": "GitHub", "url": REPO_URL, "icon": "fa-brands fa-github"},
    ],
    # The theme's arrow-key page turning takes the keys a reader scrolls with.
    "navigation_with_keys": False,
    # The right column is the page's sections and its markdown twin, in place
    # of "Show Source".  The front page has neither worth a column.
    "secondary_sidebar_items": {"**": ["page-toc", "rietx-twin"], "index": []},
    "footer_start": ["rietx-footer"],
    "footer_center": [],
    "footer_end": [],
}


def setup(app):
    app.add_role("source", _shared.source_role)
    return {"version": release, "parallel_read_safe": True, "parallel_write_safe": True}
