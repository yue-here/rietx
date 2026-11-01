"""WP-1062, retargeted by WP-1066 — an old name is gone, and stays gone.

Two renames now: ``pxrd-refine``/``pxrdref`` → ``anatase`` (WP-1062, ~300
files) → ``rietx`` (WP-1066).  What makes each *finished* rather than merely
done is this test: a reintroduction fails CI instead of depending on a note in
someone's mailbox.

Four things about how it is written are deliberate.

**It greps old tokens, never the current one.**  Not for the reason WP-1062
gave — that reason was about ``anatase`` being ambiguous — but for a plainer
one that holds for any name: the current name is *supposed* to appear, in the
README, in ``_about.py``, in every ``prog=`` string and every
``:func:`~rietx.…``` cross reference, so an audit against it could only ever be
a per-path allowlist of the whole tree.  The price, stated in ``_about.py`` and
unfixable here, is that a freshly hardcoded ``"rietx"`` is invisible to this
test; only the import-it-from-``_about`` rule catches that.

**One of the tokens it greps is domain vocabulary, and that is a dated
liability.**  ``anatase`` is a phase this software analyses.  It appears zero
times as vocabulary today, but ``rutile`` — the other TiO₂ polymorph — appears
~168 times in the QPA test data, and anatase/rutile is the canonical
quantitative-phase-analysis pair.  So the day a fixture or tutorial gains an
anatase phase, that path joins :data:`ALLOWED` with the reason "the TiO₂ phase,
not the old package".  Make that judgement once, deliberately; do not reach for
it to silence a failure that is really a stale reference.  ``pxrd`` never had
this problem — the prose consistently writes "powder X-ray diffraction" — and
``rietx`` cannot acquire it, since the nearest domain word, *Rietveld*, does not
contain the token.

**It greps ``pxt`` too.** The project suffix ``.pxrd`` contains ``pxrd`` and the
first token catches it, but the textdoc magic ``pxt`` does not contain it and
nothing else would ever notice a stale one.  Both were format tokens of the
oldest name, and both were replaced (``.rex``, ``rxt``) rather than rebranded,
because a versioned contract must not move when a brand does — which is why the
second rename left all three format tokens alone and touched only the brand.

**The allowlist is paths, with a reason each.** An allowlist of *lines* would
drift against its own files; an allowlist of paths states which files are
allowed to remember, and there are only three kinds.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Both old distribution/import names and the old textdoc magic.  Case-
#: insensitive — ``PXRDREF_STATE_DIR``, ``__PXRDREF_NO_PLOTLY__`` and
#: ``ANATASE_STATE_DIR`` were all real.
STALE = re.compile(r"pxrd|pxt|anatase", re.IGNORECASE)

#: The only files allowed to carry an old name, and why.
ALLOWED = {
    # this file: it *is* the audit, so it necessarily spells what it forbids.
    # Not discoverable by reading — the first run passed because the file was
    # still untracked and `git grep` cannot see an untracked file.
    "tests/test_no_stale_name.py",
    # each documents a rename, so each names every side of it and cannot be
    # swept without destroying its own subject
    "docs/wp/1062-rename.md",
    "docs/wp/1066-rename.md",
    # vendored third-party tables whose provenance header records the
    # modification under the name it was made with.  Parsed byte-sensitively by
    # crystallography/{attenuation,dispersion}.py; historical, not current.
    "src/rietx/data/mu_McMaster.dat",
    "src/rietx/data/f1f2_CromerLiberman.dat",
    # the milestone record's paragraph on each rename, whose subject is the
    # name that was left behind
    "docs/milestones/v1.0.md",
    # the WP index's row for WP-1062, whose title is its subject; generated
    # from that file's heading since WP-1507 moved the rows out of ROADMAP
    "docs/wp/README.md",
    # the TiO₂ phase, not the old package: a vendored COMCIFS dictionary's
    # _pd_prep example names an anatase specimen (WP-1319)
    "tests/data/cif_dictionaries/cif_pd.dic",
    # not a name at all: Hunspell affix flags, as in `black/PXTGMDNRYS`, in the
    # vendored en_GB dictionary Vale spell-checks the manual with (WP-1982)
    "docs/vale/config/dictionaries/en_GB.dic",
}


def _tracked_hits() -> dict[str, list[str]]:
    """Every tracked line matching the stale tokens, by path."""
    out = subprocess.run(
        ["git", "grep", "-nIiE", STALE.pattern],
        cwd=ROOT, capture_output=True, text=True, check=False).stdout
    hits: dict[str, list[str]] = {}
    for line in out.splitlines():
        path, _, rest = line.partition(":")
        # A committed notebook's figure is one base64 line, and a three-letter
        # token matched without case turns up in it by chance, about twice in
        # 70 kB (WP-1545).  The light and dark pair carries the same base64
        # inline, as one HTML line (WP-1970).  Its prose and code are still read.
        body = rest.partition(":")[2].lstrip()
        if path.endswith(".ipynb") and (body.startswith('"image/')
                                        or "data:image/png;base64," in body):
            continue
        hits.setdefault(path, []).append(rest)
    return hits


def test_no_file_outside_the_allowlist_carries_the_old_name():
    """The audit the rename is measured by.

    A failure here is nearly always one of two things: a literal that should
    have been an ``_about.py`` import, or a doc written from memory.
    """
    offenders = {p: v for p, v in _tracked_hits().items() if p not in ALLOWED}
    assert not offenders, (
        "the old name is back in " + ", ".join(sorted(offenders)) + " — import "
        "the token from rietx._about instead of spelling it")


def test_no_tracked_path_carries_the_old_name():
    """Contents are half of it; a file *named* for the old package is the other.

    ``src/pxrdref/`` and ``gui/src/lib/pxt.ts`` were both real, and a path is
    invisible to a content grep.

    A brand token in a path costs twice, which is why **no filename here may
    carry one — a WP's least of all.**  ``docs/wp/1062-rename-to-anatase.md``
    failed this test on its own name *and* dragged in every file that linked to
    it, because a markdown link spells the filename; WP-1066 renamed it (and
    itself) to a bare ``NNNN-rename.md``.  The title line inside says which name
    the WP was about, and says it in a place the allowlist can exempt.
    """
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True, check=False).stdout
    named = [p for p in out.splitlines() if STALE.search(p)]
    assert not named, f"tracked paths still spell the old name: {named}"


def test_the_citation_records_quote_the_current_name():
    """CITATION.cff and the manual's ``@software`` bib entry both carry the
    distribution name, and neither is code, so neither can import
    ``_about.DIST_NAME`` — this test is their import (WP-1003).  A future
    rename that moves the brand tokens fails here instead of shipping a
    citation record for a package that no longer exists.
    """
    from rietx._about import DIST_NAME

    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(rf"^title: {re.escape(DIST_NAME)}\s*$", cff, re.MULTILINE), (
        "CITATION.cff's title is not the distribution name")
    bib = (ROOT / "docs" / "docs" / "references.bib").read_text(encoding="utf-8")
    entry = re.search(r"@software\{.*?\n\}", bib, re.DOTALL)
    assert entry is not None, "references.bib has no @software entry"
    assert DIST_NAME in entry.group(0), (
        "the @software entry does not name the distribution")


def test_every_allowlisted_file_still_exists_and_still_needs_it():
    """An allowlist that outlives its reason is an allowlist that hides a bug.

    Both halves matter: a path that no longer exists is a stale entry, and a
    path that no longer matches is one whose exemption has been earned away —
    either way the entry should go, and nothing else would ever say so.
    """
    hits = _tracked_hits()
    for path in sorted(ALLOWED):
        assert (ROOT / path).exists(), f"allowlisted file is gone: {path}"
        assert path in hits, (
            f"{path} no longer carries the old name — drop it from ALLOWED")
