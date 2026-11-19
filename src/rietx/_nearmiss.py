"""The one "did you mean" in the package: a missing name answered with the closest real one.

Four surfaces answer a name that does not exist with the name that does: a
top-level attribute (``rietx.__getattr__``), a schema field
(``schemas.common.Base.__getattr__``), a ``Stage``/``RefinementPlan`` field
(``strategy.staged``), and a stage ``turn_on`` path that names no parameter
(``STAGE_PATH_UNKNOWN``, WP-1414).  The ``Refinement`` verbs that take a
path answer an unknown one through it too (``refine._path_hint``, WP-1951).
They share this module so that "closest"
means one thing everywhere, and a change to it is one edit.

Standard-library only and importing nothing from the package, because
``rietx/__init__.py`` reaches it before anything else is built.

**Case is folded before the ratio.**  ``difflib`` is case-sensitive, so on a
dot path it answered ``instrument.profile.U`` — Caglioti's U as every paper
writes it — with ``instrument.profile.y``, a real path one character away and
the wrong parameter.  An exact match up to case is therefore offered first; the
``difflib`` ranking (cutoff 0.6, the value all three older call sites used)
fills the rest.

**A word the package spells two ways is offered under its other spelling**
(WP-1913, #728 item 5).  An estimated standard deviation is ``stderr`` on
``RefinedParameter``, the geometry rows and QPA's ``weight_fraction_stderr``,
and ``esd`` on ``ParameterRow`` and the parametric rows.  ``difflib`` scores
``esd`` against ``stderr`` at 0.22, under the cutoff, so
``RefinedParameter(...).esd`` never named the field.  :data:`SYNONYMS` swaps
one dot- or underscore-delimited word at a time.  A candidate equal to a
swapped name up to case comes second, after the case-only match.  The hint is
a pointer and never an alias: the attribute still raises.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable

#: ``difflib.get_close_matches``' own default, and what every call site used
#: before they shared this module
CUTOFF = 0.6

#: one word the package spells two ways, mapped both ways; a pair is added only
#: where both spellings are real field names somewhere in the schemas
SYNONYMS: dict[str, str] = {"esd": "stderr", "stderr": "esd"}


def _respelled(name: str) -> list[str]:
    """``name`` with each :data:`SYNONYMS` word swapped, one word at a time."""
    parts = re.split(r"([._])", name)
    forms = []
    for i, part in enumerate(parts):
        other = SYNONYMS.get(part.casefold())
        if other is not None:
            forms.append("".join(parts[:i] + [other] + parts[i + 1:]))
    return forms


def near_misses(name: str, candidates: Iterable[str], *, n: int = 3) -> list[str]:
    """Up to ``n`` of ``candidates`` closest to ``name``, best first.

    Exact matches up to case come first, then a match under the other
    spelling of a :data:`SYNONYMS` word, then ``difflib``'s ranking at
    :data:`CUTOFF`, without repeats.  Empty when nothing is close, which a
    caller renders as no hint at all rather than as a guess.
    """
    pool = list(dict.fromkeys(candidates))
    folded = name.casefold()
    exact = [c for c in pool if c.casefold() == folded and c != name]
    forms = {form.casefold() for form in _respelled(name)}
    respelled = [c for c in pool if c.casefold() in forms]
    ranked = difflib.get_close_matches(name, pool, n=n, cutoff=CUTOFF)
    return list(dict.fromkeys(exact + respelled + ranked))[:n]


def did_you_mean(name: str, candidates: Iterable[str], *, n: int = 3) -> str:
    """``"did you mean 'x'?"`` for the closest candidates, or ``""`` for none.

    The phrase is the one the three ``__getattr__`` hooks printed before they
    shared it, byte for byte: the matches joined and quoted as one string.
    """
    close = near_misses(name, candidates, n=n)
    return f"did you mean {', '.join(close)!r}?" if close else ""
