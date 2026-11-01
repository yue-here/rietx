"""The term list Vale reads (WP-1982).

Vale itself runs in CI's lint job, over the manual; these tests hold the
inputs it reads to their authorities.  The accept list is generated from
`rietx.help` and a hand-kept file, so it is committed and held equal to its
generator, the `tokens.css` pattern (WP-1429).
"""

import functools
import importlib.util
import re
from pathlib import Path

import pytest

VALE = Path(__file__).resolve().parent.parent / "docs" / "vale"


@functools.cache
def _terms():
    spec = importlib.util.spec_from_file_location("_vale_terms", VALE / "terms.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.cache
def _forms() -> frozenset[str]:
    return frozenset(_terms().dictionary_forms())


def _swap_keys() -> list[str]:
    """The reject side: each synonym pattern of `rietx/Terms.yml`."""
    text = (VALE / "rietx" / "Terms.yml").read_text(encoding="utf-8")
    block = text.split("\nswap:\n", 1)[1]
    keys = re.findall(r'^  (?:"([^"]+)"|([^:#\s][^:]*)):', block, re.M)
    return [quoted or bare for quoted, bare in keys]


def _banned() -> list[str]:
    text = (VALE / "rietx" / "Banned.yml").read_text(encoding="utf-8")
    return re.findall(r"^  - (.+)$", text.split("\ntokens:\n", 1)[1], re.M)


def test_the_accept_list_is_its_generators_output():
    """A new help title the dictionary lacks fails here until the list is rewritten."""
    terms = _terms()
    committed = terms.ACCEPT.read_text(encoding="utf-8")
    assert committed == "\n".join(terms.accept_lines()) + "\n", (
        "the accept list is stale: run `.venv/bin/python docs/vale/terms.py`")


def test_no_term_is_both_accepted_and_rejected():
    """One concept, one term: a word on the accept side is no synonym or banned word.

    Both halves of the accept side, the hand-kept file and the words
    `rietx.help` brings, so a help title cannot carry a rejected synonym in.
    """
    accepted = [re.sub(r"^\[(.)(.)\]", r"\1", line) for line in _terms().accept_lines()]
    rejected = [re.compile(key, re.I) for key in _swap_keys() + _banned()]
    both = [(word, pattern.pattern) for word in accepted
            for pattern in rejected if pattern.fullmatch(word)]
    assert not both, f"accepted and rejected at once: {both}"


def test_the_reject_side_parses():
    """The two readers above see the files' whole lists, or they test nothing."""
    keys = _swap_keys()
    assert "cell (?:edge|length|constant)s?" in keys and "zeroes" in keys
    assert len(keys) > 70
    assert "just" in _banned()


@pytest.mark.parametrize("word, known", [
    ("polarisation", True), ("polarization", False),
    ("normalised", True), ("normalized", False),
    ("centre", True), ("center", False),
    ("colours", True), ("reflections", True), ("unrefined", True),
])
def test_the_dictionary_is_british_with_its_affixes_expanded(word, known):
    """`dictionary_forms` reaches a suffixed and a prefixed form, and no American one.

    "normalised" and "unrefined" exist only through the affix rules, so a
    stem-only reading of the .dic file fails them.
    """
    assert (word in _forms()) is known


def test_a_lower_case_term_may_open_a_sentence():
    """Vale.Terms holds a term to its listed case, so "anisotropic" would flag
    "Anisotropic strain is…" without the bracket."""
    lines = _terms().accept_lines()
    assert "[aA]nisotropic" in lines and "Rietveld" in lines and "TOPAS" in lines


@pytest.mark.parametrize("word, american", [
    ("Polarization", True), ("analyze", True), ("color", True),
    ("center", True), ("license", True), ("catalog", True),
    ("Rietveld", False), ("microstrain", False),
])
def test_an_american_help_word_never_reaches_the_accept_list(word, american):
    """`help_words` drops a word the dictionary knows in British spelling, in
    each of the six American patterns, and keeps a word it lacks outright."""
    assert _terms().is_american(word, _forms()) is american
