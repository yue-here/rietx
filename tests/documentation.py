"""Where the documentation executes: CI's newest per-push leg alone (WP-1547, WP-2019).

Three things execute the documentation, as distinct from checking its text: the
tutorial notebooks (``test_tutorials.py``), the guide scripts behind each Guides
page (``test_examples.py``), and the ``-W`` manual build every built-HTML guard
reads (``test_manual.py``'s ``built_docs_tree``; a second, the old tree's, went
with that tree in WP-1986).
Together they were about a fifth of a fast leg (WP-2019's Context B), and each
ran on every leg.

``RIETX_DOCS=skip`` skips them, and CI sets it on every per-push leg but the
newest Python.  They skip rather than deselect, so a leg's passed+skipped still
sums to the unsharded count (tests/CLAUDE.md § Quoting numbers).  Unset, they
run: a local run, the ``docs`` job a planning-only PR gets, and the nightly's
``full``, Windows and macOS jobs, all on 3.13.

**What only another Python could break is the documentation's own code.**  The
rietx calls behind a cell, a guide or a ``{literalinclude}`` run on every leg
through the rest of the suite.  Syntax newer than the 3.11 floor fails ruff,
whose target is py311.  Three things pass every check here and could still
fail on 3.11 alone:

- a stdlib name newer than 3.11 in a tutorial's cells or a guide's own code;
- a line a page quotes that the interpreter formats, such as an exception's
  message or an enum's ``repr``, which a guide's page holds byte for byte;
- Sphinx or an extension resolving to a release that warns on one interpreter,
  which ``-W`` makes an error.

That is the trade, and it is not deferred to the nightly: 3.11 runs only per
push, and the nightly's 3.12 leg (``middle``) sets the switch too, so such a
break shows when a reader on that Python meets it.  What only the newest Python
can break stays per push: a notebook cell printing a new ``DeprecationWarning``
to stderr, a kernel release lagging the interpreter, a deprecation in a guide's
own code.
"""

from __future__ import annotations

import os

import pytest

#: The variable, and the one value that skips.  Any other value runs.
ENV = "RIETX_DOCS"
SKIP = "skip"

REASON = (f"{ENV}={SKIP}: CI executes the documentation on its newest Python leg "
          "(tests/documentation.py)")


def skipped() -> bool:
    """Whether this process skips the documentation's executions."""
    return os.environ.get(ENV) == SKIP


#: For a test that executes the documentation.
elsewhere = pytest.mark.skipif(skipped(), reason=REASON)


def skip_here() -> None:
    """For a fixture that executes the documentation: every consumer skips."""
    if skipped():
        pytest.skip(REASON)
