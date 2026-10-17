# Sphinx configuration for the new manual (WP-1978): six tabs under
# pydata-sphinx-theme, built beside docs/manual/ until each old chapter has
# been mined and retired (WP-1986).  WP-1975 § I chose the toolchain.
#
# What this tree shares with the old one (the fenced constants, the citation
# style, the diagram theme and the `{source}` role) is in
# `docs/sphinx_shared.py`, which both conf.py files import.  The markdown
# twin and llms.txt are `docs/markdown_twin.py`'s (WP-1980).
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
# the Start tab's notebooks.  They render with their committed outputs, for
# the reason the old tree's conf.py gives.
extensions = [
    "myst_nb",
    "sphinx_design",
    "sphinxcontrib.bibtex",
    "sphinxcontrib.mermaid",
    # A markdown twin beside every page, and llms.txt (docs/markdown_twin.py).
    "markdown_twin",
]
nb_execution_mode = "off"

mermaid_light_theme = _shared.MERMAID_LIGHT_THEME
mermaid_dark_theme = _shared.MERMAID_DARK_THEME
mermaid_init_config = _shared.MERMAID_INIT_CONFIG

bibtex_bibfiles = [str(_shared.BIBFILE)]
bibtex_default_style = _shared.BIBTEX_DEFAULT_STYLE
bibtex_reference_style = _shared.BIBTEX_REFERENCE_STYLE

myst_enable_extensions = _shared.MYST_EXTENSIONS
myst_substitutions = {**_shared.MYST_SUBSTITUTIONS, "release": release}
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

html_theme = "pydata_sphinx_theme"
html_title = DIST_NAME
# The old tree's mark.  Without a favicon a browser falls back to the origin
# root, which belongs to the user Pages site this project sits under.
html_favicon = "../manual/_static/favicon.svg"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
# A release's pages name stable/ as their canonical copy, so a search engine
# sends a reader to the newest release rather than to an old one.
html_baseurl = f"{DOCS_URL}/docs/{'dev' if _shared.DOCS_VERSION == 'dev' else 'stable'}/"
html_theme_options = {
    # Six tabs, so none folds into a "More" dropdown.
    "header_links_before_dropdown": 6,
    "navbar_end": ["version-switcher", "theme-switcher", "navbar-icon-links"],
    "switcher": {
        "json_url": "/docs/switcher.json",
        "version_match": _shared.DOCS_VERSION,
    },
    # The switcher file is the deploy's, written after every build, so the
    # build has none to check.
    "check_switcher": False,
    # Dev, and each release older than the newest, says so above every page.
    "show_version_warning_banner": True,
    "icon_links": [
        {"name": "GitHub", "url": REPO_URL, "icon": "fa-brands fa-github"},
    ],
    # The theme's arrow-key page turning takes the keys a reader scrolls with.
    "navigation_with_keys": False,
}


def setup(app):
    app.add_role("source", _shared.source_role)
    return {"version": release, "parallel_read_safe": True, "parallel_write_safe": True}
