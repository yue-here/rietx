"""The skill tree's format contract (WP-1304).

`docs/skill/rietx/` is the agent-facing document in the open Agent Skills
format: a `SKILL.md` an agent reads whole in one call, reference files loaded
when a task calls for them.  Three things can rot silently here and each has a
test below.

**The caps.**  The document this replaced was 144 427 B, 2.2x the Read tool's
~66 kB cap, so an agent that tried to load it got lines 1-707 and then went
hunting with `grep` and `sed` — five roundtrips for one document, with §7's
diagnostics table never reaching context at all.  A skill body is read *whole*
when the skill activates, so its size is a fixed cost paid by every session
that loads it: `SKILL_MAX_BYTES` is half the Read cap, and `SKILL_MAX_LINES` is
the specification's own recommendation.  `REFERENCE_MAX_BYTES` is the other
tool's limit — Bash output above 40 kB comes back as a 2 kB preview, so a
reference file that a session might `cat` stays under it.

Raising a cap is a decision about every future session's fixed cost.  Make it
in a commit that says so; the fix for a full body is to move a lookup into a
reference file, which is what the tree is for.  The numbers, and the budget
below each that fails only growth (WP-1338), are `tests/skill_caps.py`'s.

**The frontmatter.**  Fields outside the specification are ignored by some
harnesses and rejected by others, so the field *set* is asserted rather than
just the required members.

**The names.**  `references/api.md` is the document three "explore the library"
runs (114 calls) were trying to write from source, and one of them asserted
that everything public is re-exported from the top-level package, which is
false.  So the file is **generated** from the installed package by
`docs/skill/make_api_index.py` — every signature, field and default rendered,
none typed — and pinned byte for byte here, so a rename, a new keyword or a
changed default fails until it is regenerated.  The body's own `report.x` /
`result.x` names, which no generator writes, are walked through the types the
same way the manual's are (`tests/api_surface.attr_step`), and every `rx.X` in
the tree is really exported — the WP-1037 bug's shape, one document over.
"""

from __future__ import annotations

import functools
import os
import re
from pathlib import Path

import pytest
import yaml

from tests import skill_caps
from tests.api_surface import attr_step, resolve_dotted
from tests.skill_caps import (
    API_INDEX_MAX_BYTES,
    REFERENCE_DIR,
    REFERENCE_MAX_BYTES,
    ROOT,
    SKILL,
    SKILL_DIR,
    SKILL_MAX_BYTES,
    SKILL_MAX_LINES,
)

REFERENCES = sorted(REFERENCE_DIR.glob("*.md"))
API_INDEX = REFERENCE_DIR / "api.md"
#: The generated indexes, `api.md` and any `api-<technique>.md` beside it.
#: `api.md` is the everyday one and a technique index is loaded only by a
#: session doing that technique, which is the whole point of the split: a
#: name nobody outside magnetic refinement will ever call costs every other
#: session nothing.  The glob is deliberate — a technique index is *created*
#: by the work that needs it, so this set must not be a list that the
#: creating PR has to remember to edit.
API_INDEXES = sorted(REFERENCE_DIR.glob("api*.md"))

# The ceilings and budgets, with the history of every move, live in
# `tests/skill_caps.py`, which CI's lint job runs as a report before the suite.

#: Every field the specification defines, and whether it is required.
#: agentskills.io/specification, verified 2026-08-29.
SPEC_FIELDS = {
    "name": True,
    "description": True,
    "license": False,
    "compatibility": False,
    "metadata": False,
    "allowed-tools": False,
}
SPEC_NAME_RE = re.compile(r"^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$")
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500


def _frontmatter() -> dict:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must open with YAML frontmatter"
    _, block, _ = text.split("---\n", 2)
    return yaml.safe_load(block)


def test_the_body_is_within_its_caps():
    """The whole point of the split: one Read, whole, every time."""
    size = len(SKILL.read_bytes())
    lines = len(SKILL.read_text(encoding="utf-8").splitlines())
    assert size <= SKILL_MAX_BYTES, (
        f"SKILL.md is {size} B (cap {SKILL_MAX_BYTES}). Move a lookup table "
        "into references/ — see tests/skill_caps.py on raising a cap."
    )
    assert lines < SKILL_MAX_LINES, (
        f"SKILL.md is {lines} lines (cap {SKILL_MAX_LINES}, the spec's own)."
    )


@pytest.mark.parametrize("path", REFERENCES, ids=lambda p: p.name)
def test_every_reference_file_is_within_its_cap(path: Path):
    generated = path in API_INDEXES
    cap = API_INDEX_MAX_BYTES if generated else REFERENCE_MAX_BYTES
    size = len(path.read_bytes())
    assert size <= cap, (
        f"{path.name} is {size} B (cap {cap}); "
        + ("the generator renders one signature per public name, so this is "
           "the public API outgrowing the file: move a task shape's names to "
           "an api-<shape>.md (make_api_index.py's TECHNIQUES), on the "
           "criterion tests/skill_caps.py's API_INDEX_MAX_BYTES records."
           if generated else "split it.")
    )


def test_no_name_has_an_entry_row_in_two_api_indexes():
    """A split moves a name; it never copies one.  Two rows for one name are
    two signatures that a later edit to `SECTIONS` can let drift apart, and
    the reader routed to either file cannot tell which is current."""
    seen: dict[str, str] = {}
    twice = []
    for path in API_INDEXES:
        for name in re.findall(r"^- `((?:rx|rietx)\.[A-Za-z0-9_.]+)",
                               path.read_text(encoding="utf-8"), re.M):
            # One object, two spellings: `rietx.X` is `rx.X`.
            name = "rx." + name.split(".", 1)[1]
            if name in seen:
                twice.append(f"{name}: {seen[name]} and {path.name}")
            seen[name] = path.name
    assert len(seen) > 100, f"only {len(seen)} entry rows found — the regex broke"
    assert not twice, twice


# --- the budgets (#247) -----------------------------------------------------
#
# A ceiling fails on any tree; a budget fails only a change that grows a file
# past it, so two pull requests that merge together land in the gap between
# the two instead of failing each other.  `tests/skill_caps.py` has the numbers
# and why; CI's lint job runs the same check as a report on every pull request,
# drafts included, which is where it gates.  Here it gates the author, locally,
# against the merge-base with origin/main.


def test_no_change_grows_a_capped_file_past_its_budget():
    rev, how = skill_caps.base()
    if os.environ.get("GITHUB_ACTIONS"):
        pytest.skip("CI gates this in the lint job, against the pull request's base")
    if rev is None or not skill_caps.rev_exists(rev):
        pytest.skip(f"nothing to measure against: {how}")
    failures = skill_caps.budget_failures(skill_caps.rows(rev))
    assert not failures, "\n".join(failures)


def test_the_budget_fails_growth_past_it_and_nothing_else():
    """The rule's four cases, on made-up sizes: only growth that ends past the
    budget fails, and a new file counts from zero."""
    cap = skill_caps.Cap(REFERENCE_DIR / "x.md", 1000, 900)
    row = skill_caps.Row
    cases = {
        "grows past": row(cap, 880, 950),
        "shrinks while over": row(cap, 990, 950),
        "grows under": row(cap, 500, 890),
        "new and over": row(cap, None, 950),
    }
    failing = {k for k, r in cases.items() if skill_caps.budget_failures([r])}
    assert failing == {"grows past", "new and over"}
    assert cases["grows past"].cut_needed() == 50
    assert cases["new and over"].cut_needed() == 50


def test_every_capped_file_has_a_budget_under_its_ceiling_unless_generated():
    for cap in skill_caps.caps():
        generated = cap.path in API_INDEXES
        assert (cap.budget is None) == generated, cap.rel
        assert generated or cap.budget < cap.ceiling, cap.rel


def test_a_version_bump_is_not_growth():
    """The body's budget counts the Markdown below its frontmatter, so the
    release bump of `metadata.version` never trips it."""
    cap = next(c for c in skill_caps.caps() if c.path == SKILL)
    text = SKILL.read_text(encoding="utf-8")
    bumped = text.replace('version: "', 'version: "99.99.99.dev0+', 1)
    assert bumped != text
    assert cap.budgeted_bytes(bumped) == cap.budgeted_bytes(text)


def test_the_frontmatter_is_the_specs_and_nothing_else():
    meta = _frontmatter()
    unknown = sorted(set(meta) - set(SPEC_FIELDS))
    assert not unknown, (
        f"frontmatter fields outside the Agent Skills spec: {unknown} — some "
        "harnesses reject an unknown key rather than ignoring it"
    )
    missing = sorted(k for k, required in SPEC_FIELDS.items()
                     if required and k not in meta)
    assert not missing, f"required frontmatter fields missing: {missing}"


def test_the_name_matches_the_directory_and_the_specs_shape():
    name = _frontmatter()["name"]
    assert SPEC_NAME_RE.match(name), (
        f"name {name!r}: 1-64 chars of [a-z0-9-], no leading, trailing or "
        "doubled hyphen"
    )
    assert name == SKILL_DIR.name, (
        f"name {name!r} must match the parent directory {SKILL_DIR.name!r}"
    )


def test_the_description_and_compatibility_fit_their_budgets():
    """`description` is loaded for *every* skill at startup, so it is charged
    against a catalogue budget rather than this skill's own (Codex caps the
    whole catalogue at 8000 chars)."""
    meta = _frontmatter()
    assert len(meta["description"]) <= DESCRIPTION_MAX
    assert len(meta.get("compatibility", "")) <= COMPATIBILITY_MAX


def test_metadata_values_are_strings_and_the_version_is_the_packages():
    """The spec's `metadata` is a map of string to string, and a version that
    is not the package's is worse than no version at all."""
    import rietx

    meta = _frontmatter().get("metadata", {})
    non_strings = sorted(k for k, v in meta.items() if not isinstance(v, str))
    assert not non_strings, (
        f"metadata values must be strings (quote them): {non_strings}"
    )
    assert meta["version"] == rietx.__version__, (
        f"SKILL.md metadata.version is {meta['version']!r}, the package is "
        f"{rietx.__version__!r} — bump it with the version (docs/RELEASING.md)"
    )


_LINK = re.compile(r"\]\((?!https?:)([^)#]+)")


def test_every_relative_link_in_the_tree_resolves():
    for path in [SKILL, *REFERENCES]:
        for target in _LINK.findall(path.read_text(encoding="utf-8")):
            resolved = (path.parent / target).resolve()
            assert resolved.exists(), f"{path.name}: dead link {target}"


#: The body's standing instruction to look up a name the agent holds.  It
#: replaced the routing rows for a fired code: under it Opus reached 17 of 18
#: fired codes' rows against 4 (tests/eval_skill_placement/PROTOCOL.md).
GREP_INSTRUCTION = "`grep -rn NAME references/`"


def test_every_reference_file_is_reachable_from_the_body():
    """A reference nothing points at is a file no agent will open.

    A file of code rows is reached by grepping for the code, once the body
    says to, so it needs no routing row of its own."""
    text = SKILL.read_text(encoding="utf-8")
    greppable = GREP_INSTRUCTION in text
    unreferenced = [p.name for p in REFERENCES
                    if f"references/{p.name}" not in text
                    and not (greppable and _code_tables(p.read_text(encoding="utf-8")))]
    assert not unreferenced, (
        f"reference files the body never names: {unreferenced} — add a row to "
        "the body's index table, or key the file's rows by a name an agent "
        "holds so the body's grep instruction reaches it"
    )


DOTTED = re.compile(r"`(rx\.[A-Za-z_][A-Za-z0-9_.]*|rietx\.[A-Za-z_][A-Za-z0-9_.]*)")


# --- the reference files' own contract (WP-1330) ----------------------------
#
# A reference is opened by an agent that has read the body's routing row and
# nothing else, so its first three paragraphs say what that row said: the
# section it specialises, when to load it, and that the body's numbering is
# the one it cites.  Every file already opened this way by convention; the pin
# is for the next one.  A task *shape* — a series, a batch, a magnetic phase —
# gets one reference file each, which is how the skill grows without the body
# growing, and a file that opens some other way is one the routing table
# cannot describe.
#
# A reference that collects rules from *runs* (batch.md first, filled from a
# contributor's logs by an agent) declares in its provenance paragraph that
# every row carries its evidence.  Each numbered row then ends in a tag saying
# what was measured, or what would decide it.  That is the form an agent
# analysing logs fills in, and the gate that refuses a row with no number
# behind it.

REFERENCE_LOAD_PREFIX = "Load it "
REFERENCE_PROVENANCE_PREFIX = "*A reference file of the `rietx` skill."
EVIDENCE_DECLARATION = "Every row carries its evidence"
#: ``# 9c. Title`` — the section a reference specialises, from its own H1.
_H1_SECTION = re.compile(r"^# (\d+[a-z]?)\.")
#: ``**9c.3 The rule.**`` — a numbered row of an evidence-tagged reference,
#: matched against one paragraph.
_ROW_HEAD = re.compile(r"^\*\*(\d+[a-z]?)\.(\d+) ")
#: ``*(Measured: …)*`` / ``*(Hypothesis: …)*`` — the tag *closes* the row, so it
#: is matched at the end of the row's last paragraph, never searched for: a
#: quoted example in the prose, or a tag under an "Open questions" heading
#: after the rows, must not cover a row that has none.
_EVIDENCE_TAG = re.compile(r"\*\((Measured|Hypothesis): .+\)\*\Z", re.S)


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n[ \t]*\n", text) if p.strip()]


@pytest.mark.parametrize("path", REFERENCES, ids=lambda p: p.name)
def test_every_reference_opens_with_its_load_condition_and_provenance(path: Path):
    paras = _paragraphs(path.read_text(encoding="utf-8"))
    assert len(paras) >= 4, (
        f"{path.name}: a title, a load condition, a provenance line, then content")
    assert paras[0].startswith("# ") and "\n" not in paras[0], (
        f"{path.name}: the first line is a one-line H1 title")
    assert paras[1].startswith(REFERENCE_LOAD_PREFIX), (
        f"{path.name}: the second paragraph opens {REFERENCE_LOAD_PREFIX!r} — the "
        "situation the body's routing row names, restated where the reader lands")
    assert paras[2].startswith(REFERENCE_PROVENANCE_PREFIX), (
        f"{path.name}: the third paragraph is the provenance line, "
        f"{REFERENCE_PROVENANCE_PREFIX!r}…")


def _evidence_tagged() -> list[Path]:
    """The references whose provenance paragraph opts into tagged rows.

    Runs at collection (it parametrises a test), so a malformed file is left
    to the header test above to name rather than raised here, where it would
    take the whole module down.
    """
    tagged = []
    for p in REFERENCES:
        paras = _paragraphs(p.read_text(encoding="utf-8"))
        if len(paras) > 2 and EVIDENCE_DECLARATION in " ".join(paras[2].split()):
            tagged.append(p)
    return tagged


def _rows(paras: list[str]) -> list[list[str]]:
    """The rows section: each row is its head paragraph plus what follows it,
    from the first numbered row to the next heading."""
    rows: list[list[str]] = []
    for p in paras:
        if p.startswith("#"):
            if rows:
                break
            continue
        if _ROW_HEAD.match(p):
            rows.append([p])
        elif rows:
            rows[-1].append(p)
    return rows


def test_the_evidence_gate_has_a_file_to_gate():
    """Collector liveness: an empty list would pass the row test vacuously."""
    assert _evidence_tagged(), (
        f"no reference declares {EVIDENCE_DECLARATION!r} — batch.md was the "
        "first; if it stopped, the row gate below covers nothing")


@pytest.mark.parametrize("path", _evidence_tagged(), ids=lambda p: p.name)
def test_every_row_of_an_evidence_tagged_reference_carries_its_tag(path: Path):
    paras = _paragraphs(path.read_text(encoding="utf-8"))
    section = _H1_SECTION.match(paras[0])
    assert section, f"{path.name}: a tagged reference's H1 carries its section number"
    rows = _rows(paras)
    assert rows, f"{path.name}: declares tagged rows and has none"
    numbers = []
    for row in rows:
        sec, n = _ROW_HEAD.match(row[0]).groups()
        assert sec == section.group(1), (
            f"{path.name}: row {sec}.{n} is numbered under §{sec}; the file is "
            f"§{section.group(1)}")
        unnumbered = [p for p in row[1:] if p.startswith("**")]
        assert not unnumbered, (
            f"{path.name}: after row {sec}.{n}, a bold-opened paragraph is not a "
            f"numbered row, so the gate cannot see it: {unnumbered[0][:60]!r}")
        assert _EVIDENCE_TAG.search(row[-1]), (
            f"{path.name}: row {sec}.{n} does not close with a *(Measured: …)* or "
            "*(Hypothesis: …)* tag — name the run and its number, or what "
            "would decide it")
        numbers.append(int(n))
    assert numbers == sorted(set(numbers)), (
        f"{path.name}: row numbers must be unique and increasing, got {numbers}")


# A tag on a row measured outside this repository reads exactly like a citation,
# so #239 put two obligations on it in prose: the file declares the corpus once
# in its provenance line, and every such tag spells it the same way.  Both were
# unchecked -- `.+` in `_EVIDENCE_TAG` is the whole contract, so a row closing
# `*(Measured: some runs I did)*` passed while naming nothing (#241).
#
# **Why the gate requires the complement rather than recognising a repo tag.**
# A repo-shaped tag has no fixed spelling: `WP-\d+` is reliable, but "an eval
# round" and "a dataset in `tests/data/README.md`" are prose, so a pattern for
# them either grows with every new phrasing or starts refusing honest tags.
# Requiring instead that every `Measured` tag opens with `WP-` **or** with the
# declared corpus gives up on validating repo tags -- which the WP files and
# `test_every_dotted_name_in_the_api_indexes_resolves` already cover from the
# other side -- and spends the whole budget on the private case, which has no
# other guard.  A per-row marker would make the classification trivial and #239
# ruled it out, on the ground that declaring once costs no row an edit; that is
# why the problem cannot simply be designed away.
#
# `Hypothesis` tags name what *would* decide a question rather than a run, so
# they are outside this gate.  A file may hold both kinds, as `batch.md` does
# with two `WP-` tags among 28 private ones, so the gate is per tag, never per
# file.

#: The corpus a file declares for rows measured on data it cannot ship: the one
#: bold span in its provenance paragraph.  Bold is the declaration site because
#: the prose already uses it (`batch.md` § Writing a row says "name the
#: **corpus** the file declares"), and requiring *exactly* one turns that from a
#: convention a reader infers into one a test can find.
_CORPUS_DECLARATION = re.compile(r"\*\*(.+?)\*\*")


def _declared_corpus(paras: list[str]) -> str | None:
    """The corpus this file declares, or ``None`` if it declares none.

    Raises nothing on a malformed declaration: it returns the ambiguity as a
    list so the caller can name the file, since this runs under a parametrised
    test rather than at collection.
    """
    spans = _CORPUS_DECLARATION.findall(" ".join(paras[2].split()))
    if len(spans) != 1:
        return None if not spans else "\x00".join(spans)
    return spans[0]


def _tag_parts(text: str) -> tuple[str, str] | None:
    """``(kind, body)`` of the tag closing a row, whitespace-normalised.

    Built on ``_EVIDENCE_TAG`` rather than a second copy of the tag grammar:
    ``docs/wp/1338-the-skills-own-gates.md`` quotes that constant verbatim, and
    two spellings of one grammar is how the quote goes stale.  The flattening
    matters -- not because the match would otherwise stop short
    (``_EVIDENCE_TAG`` is compiled with ``re.S``, so ``.`` already crosses the
    wrap) but because the extracted body would otherwise carry the newline a tag
    wraps across, and ``body.startswith(corpus)`` compares it against a corpus
    spelled on one line in the provenance paragraph.
    """
    m = _EVIDENCE_TAG.search(text)
    if m is None:
        return None
    kind = m.group(1)
    flat = " ".join(m.group(0).split())
    return kind, flat[len(f"*({kind}: "):-len(")*")]


def test_the_corpus_gate_has_a_private_tag_to_gate():
    """Collector liveness, in `test_the_evidence_gate_has_a_file_to_gate`'s
    idiom: if no file declares a corpus, or none of its rows uses it, the
    "or the declared corpus" arm below is dead and the gate silently reduces to
    "every tag starts with WP-", which no current file would satisfy."""
    declaring = []
    for path in _evidence_tagged():
        paras = _paragraphs(path.read_text(encoding="utf-8"))
        corpus = _declared_corpus(paras)
        if corpus and "\x00" not in corpus:
            used = [r for r in _rows(paras)
                    if (t := _tag_parts(r[-1])) and t[0] == "Measured"
                    and t[1].startswith(corpus)]
            if used:
                declaring.append((path.name, corpus, len(used)))
    assert declaring, (
        "no evidence-tagged reference declares a corpus and measures a row "
        "against it — batch.md was the first (#233); if that stopped, the "
        "private half of the gate below covers nothing and only the WP- arm "
        "is still doing work")


def _corpus_problems(name: str, text: str) -> list[str]:
    """Every way a file's `Measured` tags fail the corpus rule, as messages."""
    paras = _paragraphs(text)
    corpus = _declared_corpus(paras)
    if corpus is not None and "\x00" in corpus:
        spans = corpus.split("\x00")
        return [f"{name}: the provenance paragraph holds {len(spans)} bold spans "
                f"({', '.join(repr(s) for s in spans)}) — exactly one is the "
                "corpus declaration, so a second is ambiguous. Bold the corpus "
                "and nothing else there"]
    problems = []
    for row in _rows(paras):
        sec, n = _ROW_HEAD.match(row[0]).groups()
        parts = _tag_parts(row[-1])
        if parts is None or parts[0] != "Measured":
            continue          # no tag is the row gate's business; Hypothesis is outside
        body = parts[1]
        if body.startswith("WP-"):
            continue
        if not corpus:
            problems.append(
                f"{name}: row {sec}.{n} closes *(Measured: {body[:50]}…)*, "
                "which names neither a WP nor a declared corpus — and this file "
                "declares no corpus. Either name the run so a reader can open it, "
                "or declare the corpus once in the provenance paragraph, in bold")
        elif not body.startswith(corpus):
            problems.append(
                f"{name}: row {sec}.{n} closes *(Measured: {body[:60]}…)*. A "
                f"row measured outside this repository names the declared corpus "
                f"{corpus!r} first, spelled the same way every time — otherwise "
                "the tag reads as a citation to something a reader could go and "
                "find. Start it with that string, or with WP- if the run is here")
    return problems


@pytest.mark.parametrize("path", _evidence_tagged(), ids=lambda p: p.name)
def test_every_measured_tag_names_this_repository_or_the_declared_corpus(
        path: Path):
    problems = _corpus_problems(path.name, path.read_text(encoding="utf-8"))
    assert not problems, "\n".join(problems)


def test_the_corpus_gate_fails_each_broken_shape():
    """The three ways a private tag goes wrong, on a made-up file, and the
    two tags that must pass."""
    def doc(provenance: str, *tags: str) -> str:
        rows = "\n\n".join(f"**9z.{i} A rule.** Text. *(Measured: {tag})*"
                             for i, tag in enumerate(tags, 1))
        return (f"# 9z. Title\n\nLoad it when.\n\n{REFERENCE_PROVENANCE_PREFIX} "
                f"{provenance}\n\n{rows}\n")

    declared = "Every row carries its evidence, runs on **corpus A**."
    assert not _corpus_problems("x", doc(declared, "WP-1338, a round", "corpus A, run 4"))
    assert _corpus_problems("x", doc(declared, "Corpus A, run 4"))          # misspelled
    assert _corpus_problems("x", doc("Every row carries its evidence.",
                                     "some runs I did"))                   # none declared
    assert _corpus_problems("x", doc("**A** and **B**.", "A, run 1"))        # ambiguous


# --- an evidence tag's WP, read against the index (WP-1907) ---------------
#
# A `(Measured: WP-NNNN …)` tag carries no date, so a measurement a later WP
# overturned reads as current.  The WP it names is the date: that WP must be a
# row of the index, and when another WP file says it **supersedes** it, the
# tag must name the superseder too, which is the re-read the row needs.  The
# grammar is the phrase the WP files already use for an overturned claim
# ("supersedes WP-1023"), never a "superseded in part" note, which records a
# finding that *earlier* work had overtaken (`/wp-start` step 5).

WP_DIR = ROOT / "docs" / "wp"
_ANY_TAG = re.compile(r"\*\((Measured|Hypothesis): (.+?)\)\*", re.S)
_WP_REF = re.compile(r"WP-(\d{4})\b")
_SUPERSEDES = re.compile(r"\b[Ss]upersedes WP-(\d{4})\b")
#: Every file whose tags are read: the generated `api*.md` carry none.
_TAG_FILES = [SKILL, *(p for p in REFERENCES if p not in API_INDEXES)]


def _tagged_wps(text: str) -> list[tuple[str, set[str]]]:
    """``(tag body, the WPs it names)`` for every evidence tag in ``text``."""
    return [(" ".join(m.group(2).split()), set(_WP_REF.findall(m.group(2))))
            for m in _ANY_TAG.finditer(text)]


def _index_rows() -> set[str]:
    index = (WP_DIR / "README.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| \[(\d{4})\]\(", index, re.M))


def _superseders(texts: dict[str, str]) -> dict[str, set[str]]:
    """``{superseded WP: the WPs whose files say they supersede it}``."""
    out: dict[str, set[str]] = {}
    for number, text in texts.items():
        for old in _SUPERSEDES.findall(text):
            if old != number:
                out.setdefault(old, set()).add(number)
    return out


def _tag_problems(name: str, text: str, index: set[str],
                  superseders: dict[str, set[str]]) -> list[str]:
    problems = []
    for body, wps in _tagged_wps(text):
        for wp in sorted(wps - index):
            problems.append(f"{name}: a tag names WP-{wp}, which is not a row of "
                            f"docs/wp/README.md (renumbered?): {body[:100]!r}")
        for wp in sorted(wps & superseders.keys()):
            missing = superseders[wp] - wps
            if missing:
                later = ", ".join(f"WP-{n}" for n in sorted(missing))
                problems.append(
                    f"{name}: a tag rests on WP-{wp}, which {later} says it "
                    f"supersedes; re-read the row and name {later} in its tag: "
                    f"{body[:100]!r}")
    return problems


#: A WP not started (⬜) or stopped (🛑) has overturned nothing yet, so its
#: "supersedes" is a plan and asks no tag to name it.
_STATUS = re.compile(r"Status: (\S+)")


def _wp_texts() -> dict[str, str]:
    texts = {p.name[:4]: p.read_text(encoding="utf-8")
             for p in sorted(WP_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))}
    return {n: t for n, t in texts.items()
            if (m := _STATUS.search(t)) is None or m.group(1) not in ("⬜", "🛑")}


def test_the_tag_gate_has_tags_and_a_supersession_to_read():
    """Collector liveness for both halves: tags naming a WP exist, and the
    supersession grammar has at least one real instance in the WP files."""
    named = [wps for p in _TAG_FILES for _, wps in _tagged_wps(p.read_text(encoding="utf-8"))
             if wps]
    assert named, "no evidence tag in the skill names a WP; the index check reads nothing"
    assert _superseders(_wp_texts()), (
        "no WP file says it 'supersedes WP-NNNN'; the supersession half reads "
        "nothing, so its grammar has drifted from what the WP files write")


@pytest.mark.parametrize("path", _TAG_FILES, ids=lambda p: p.name)
def test_every_wp_an_evidence_tag_names_is_indexed_and_not_superseded(path: Path):
    problems = _tag_problems(path.name, path.read_text(encoding="utf-8"),
                             _index_rows(), _superseders(_wp_texts()))
    assert not problems, "\n".join(problems)


def test_the_tag_gate_fails_each_broken_shape():
    index, sup = {"1403", "1500"}, {"1403": {"1500"}}
    assert not _tag_problems("x", "*(Measured: WP-1500 — a run)*", index, sup)
    assert not _tag_problems("x", "*(Measured: WP-1403, re-read in WP-1500)*", index, sup)
    assert _tag_problems("x", "*(Measured: WP-1403 — a run)*", index, sup)   # superseded
    assert _tag_problems("x", "*(Measured: WP-9999 — a run)*", index, sup)   # no such WP
    assert _superseders({"1500": "This supersedes WP-1403.",
                         "1403": "Superseded in part, 2026-09-15: WP-1300"}) == {
        "1403": {"1500"}}


@pytest.mark.parametrize("path", API_INDEXES, ids=lambda p: p.name)
def test_every_dotted_name_in_the_api_indexes_resolves(path: Path):
    """No API index can name something the package does not have, so a name
    a split moves out of `api.md` keeps its guard."""
    text = path.read_text(encoding="utf-8")
    names = {m.rstrip(".") for m in DOTTED.findall(text)}
    floor = 60 if path == API_INDEX else 0
    assert len(names) > floor, f"{path.name}: only {len(names)} names found — the regex broke"
    for name in sorted(names):
        dotted = name if name.startswith("rietx.") else "rietx." + name[len("rx."):]
        resolve_dotted(dotted, path.name)


def _generator():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "make_api_index", ROOT / "docs" / "skill" / "make_api_index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_technique_field_is_a_field_and_deferred():
    """`make_api_index.TECHNIQUE_FIELDS` keeps a technique's fields out of
    `api.md` (WP-1805).  Each name must be a live field of its model, or a
    rename leaves a dead skip behind, and each must be deferred from the
    manual too, since nothing documents it until its technique index lands."""
    import rietx as rx

    deferred = set((ROOT / "tests" / "api_surface_deferred.txt")
                   .read_text(encoding="utf-8").split())
    skips = _generator().TECHNIQUE_FIELDS
    assert skips
    for dotted, names in skips.items():
        cls = getattr(rx, dotted[len("rx."):])
        for name in names:
            assert name in cls.model_fields, (dotted, name)
            assert f"{cls.__name__}.{name}" in deferred, (dotted, name)
            assert f"`{name}:" not in API_INDEX.read_text(encoding="utf-8").split(
                f"- `{dotted}`")[1].split("\n- ")[0], (dotted, name)


def test_every_technique_member_is_a_deferred_name():
    """`make_api_index.TECHNIQUE_MEMBERS` elides a technique's union members
    from `api.md` (WP-1809); each must be a live export and deferred from the
    manual (deferred, or documented in a Part 1 chapter once the deferred
    ceiling is full), and absent from the rendered index."""
    import rietx as rx
    from tests.test_manual_api import documented_names

    deferred = set((ROOT / "tests" / "api_surface_deferred.txt")
                   .read_text(encoding="utf-8").split())
    documented = documented_names()
    members = _generator().TECHNIQUE_MEMBERS
    assert members
    text = API_INDEX.read_text(encoding="utf-8")
    for name in members:
        assert hasattr(rx, name), name
        assert name in deferred or name in documented, name
        assert name not in text, name


def test_the_api_indexes_are_what_the_generator_renders():
    """`references/api.md` and every `api-<technique>.md` are generated and
    committed (they ship in the wheel with no build step), so the committed
    bytes must be what the generator renders from *this* package — a rename, a
    new keyword or a changed default fails here until the file is regenerated.
    Both directions: an index the generator no longer writes fails too."""
    import difflib

    rendered = _generator().targets()
    assert {p.name for p in rendered} == {p.name for p in API_INDEXES}, (
        "the committed api*.md files are not the ones make_api_index.py writes")
    for path, text in rendered.items():
        committed = (REFERENCE_DIR / path.name).read_text(encoding="utf-8")
        if text != committed:
            diff = list(difflib.unified_diff(
                committed.splitlines(), text.splitlines(),
                "committed", "rendered", lineterm="", n=0))
            pytest.fail(
                f"references/{path.name} is stale — regenerate with\n"
                "  .venv/bin/python docs/skill/make_api_index.py && "
                "rietx skill --install . --copy\n"
                + "\n".join(diff[:40]))
        # the selection cannot be wider than what a reader can reach
        assert " at 0x" not in text


# --- the hand-written names (#238) ------------------------------------------
#
# `report.regions`, `result.statistics.rwp`, `entry.rungs_tried`,
# `StageResult.held_reach`: field names an author typed, which no generator
# writes.  A rule written against a field that has moved is a rule nobody can
# follow, so each is walked through the types the way the manual's names are.
# Until WP-1338 the walk read the body alone, and the reference files, which
# hold four times its names, were checked by hand at review.
#
# **A root is a variable name or an exported class**, and the two are read
# differently.  A class in `rietx.__all__` is its own root, so a type-level
# claim (`SeriesResult.diagnostics`) is walked with no list to maintain.  A
# variable name is a convention, and some stand for more than one type: in
# `series.md` a `result` is a `SeriesResult`, and in `magnetic.md`
# `report.magnetic` is the module `rietx.report.magnetic`.  So a variable root
# names every type it stands for, and a chain passes when it resolves on one.
# That can pass a field named on the wrong answer type; it cannot pass a field
# that no longer exists on any of them, which is the rot this gate is for.
#
# **What the walk cannot see.**  A negative claim (`StageResult` carries no
# `rwp`) names nothing to resolve, and a field added later falsifies it
# silently; `NEGATIVE_FIELD_CLAIM` below pins the one phrasing the tree uses.
# An attribute a plain class assigns on `self` (`SequentialRefinement.results_`,
# set in `__init__`) has no class-level trace but the source line, so the walk
# accepts it there and stops, the attribute's type being unknown.  A variable
# name outside `_variable_roots()` is not walked:
# `background.` is a report block in one file and a module in another, and
# `phases.0.cell.a` is a parameter path, which `rx.help_for` owns.

#: A span that is a dotted name and nothing else, possibly called.
DOTTED_NAME = re.compile(
    r"`([A-Za-z_][A-Za-z0-9_]*)((?:\.[A-Za-z_][A-Za-z0-9_]*)+)(?:\(|`)")


def _format_models() -> tuple:
    """What a `read_<format>` verb returns for another program's file.

    A `model.` in the foreign-file rows is one of these (`TopasModel`,
    `GsasModel`, …), none exported, so they are read off the readers'
    return annotations rather than listed: a new format's model joins by
    shipping its reader."""
    import inspect
    import sys

    import rietx as rx

    found = [rx.ProjectModel]
    for name in rx.__all__:
        fn = getattr(rx, name)
        if not (name.startswith("read_") and inspect.isroutine(fn)):
            continue
        # Only the return annotation: `get_type_hints` would evaluate every
        # parameter's too, and some name a type imported for checking only.
        ret = inspect.unwrap(fn).__annotations__.get("return")
        if isinstance(ret, str):
            ret = getattr(sys.modules[fn.__module__], ret, None)
        if isinstance(ret, type) and ret.__name__.endswith("Model"):
            found.append(ret)
    return tuple(dict.fromkeys(found))  # read_project_model returns ProjectModel too


def _variable_roots() -> dict[str, tuple]:
    """The variable names the skill uses for an object in hand, and every type
    each one stands for somewhere in the tree."""
    import rietx as rx
    import rietx.report

    return {
        "report": (rx.FitReport, rietx.report),
        "result": (rx.RefinementResult, rx.SeriesResult, rx.IndexingResult,
                   rx.SuggestionResult),
        "statistics": (rx.Statistics,),
        "d": (rx.Diagnostic,),
        "ref": (rx.Refinement,),
        "series": (rx.SeriesResult,),
        "entry": (rx.SeriesEntry,),
        "model": _format_models(),
        "instrument": (rx.Instrument,),
    }


@functools.cache
def _roots() -> dict[str, tuple]:
    import inspect

    import rietx as rx

    classes = {name: (getattr(rx, name),) for name in rx.__all__
               if inspect.isclass(getattr(rx, name))}
    return {**classes, **_variable_roots()}


def _assigned_on_self(cls: type, name: str) -> bool:
    import inspect

    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError):
        return False
    return re.search(rf"self\.{re.escape(name)}\s*[:=]", source) is not None


def _union_arms(obj: object, step: str) -> list[type]:
    """The rietx classes a pydantic field's union annotation admits, in
    declaration order — more than one only for a discriminated union such as
    ``Instrument.source``, where a name is real if *any* arm carries it."""
    import typing

    fields = getattr(obj, "model_fields", None) or {} if isinstance(obj, type) else {}
    if step not in fields:
        return []
    return [a for a in typing.get_args(fields[step].annotation)
            if isinstance(a, type) and a.__module__.startswith("rietx")]


def _first_missing_step(obj: object, steps: list[str]) -> str | None:
    for i, step in enumerate(steps):
        arms = _union_arms(obj, step)
        if len(arms) > 1:
            rest = [_first_missing_step(arm, steps[i + 1:]) for arm in arms]
            return None if any(m is None for m in rest) else rest[0]
        ok, nxt = attr_step(obj, step)
        if ok:
            obj = nxt
        elif isinstance(obj, type) and _assigned_on_self(obj, step):
            return None
        else:
            return step
    return None


def _unresolved_names(text: str, roots: dict[str, tuple]) -> tuple[int, list[str]]:
    """How many dotted names the walk visited, and the ones resolving on none
    of their root's types."""
    walked, bad = 0, []
    for root, chain in DOTTED_NAME.findall(text):
        if root not in roots:
            continue
        walked += 1
        steps = chain.lstrip(".").split(".")
        missing = [_first_missing_step(t, steps) for t in roots[root]]
        if all(m is not None for m in missing):
            bad.append(f"{root}{chain}: no {missing[0]!r}")
    return walked, bad


#: Every file an author writes by hand; the generated indexes have their own
#: byte-for-byte pin above.
AUTHORED = [SKILL, *(p for p in REFERENCES if p not in API_INDEXES)]


@pytest.mark.parametrize("path", AUTHORED, ids=lambda p: p.name)
def test_every_dotted_name_in_an_authored_file_resolves(path: Path):
    _, bad = _unresolved_names(path.read_text(encoding="utf-8"), _roots())
    assert not bad, (
        f"{path.name} names fields the package does not have: {bad}. Rename "
        "them to what the type carries now, or delete the claim")


#: ```StageResult` carries no `rwp` `` — the one negative claim the tree makes
#: about a field, and the kind a walk cannot see: nothing resolves, so a field
#: added later falsifies it silently (WP-1334 proposes exactly that one).  This
#: is a phrasing, not a grammar, so a claim worded another way is unpinned.
NEGATIVE_FIELD_CLAIM = re.compile(r"`([A-Z][A-Za-z0-9_]*)` (?:carries|has) no `([a-z_][a-z0-9_]*)`")


def _stale_negative_claims(text: str, roots: dict[str, tuple]) -> tuple[int, list[str]]:
    found, stale = 0, []
    for cls, field in NEGATIVE_FIELD_CLAIM.findall(text):
        if cls not in roots:
            continue
        found += 1
        if any(attr_step(t, field)[0] for t in roots[cls]):
            stale.append(f"`{cls}` now has `{field}`")
    return found, stale


def test_every_negative_field_claim_is_still_true():
    roots, found = _roots(), 0
    for path in AUTHORED:
        n, stale = _stale_negative_claims(path.read_text(encoding="utf-8"), roots)
        found += n
        assert not stale, f"{path.name}: {stale} — the claim is false now; rewrite it"
    assert found, "no negative claim matched — the phrasing moved, and this pins nothing"
    assert _stale_negative_claims("`StageResult` carries no `status`", roots)[1], (
        "a claim the type contradicts must fail")


def test_the_dotted_walk_visits_the_tree_and_fails_a_broken_name():
    """Liveness, re-sited from the body's own density to the tree's: the body
    held 40 walkable names and the references 194 more when the walk widened,
    and a regex that stopped matching would pass every file above."""
    roots = _roots()
    walked = sum(_unresolved_names(p.read_text(encoding="utf-8"), roots)[0]
                 for p in AUTHORED)
    assert walked > 150, f"the walk visited only {walked} names — the regex broke"
    _, bad = _unresolved_names(
        "`result.statistics.rwp` `SeriesResult.no_such_field` "
        "`entry.no_such_field` `report.magnetic.moment_pair_diagnostics`", roots)
    assert bad == ["SeriesResult.no_such_field: no 'no_such_field'",
                   "entry.no_such_field: no 'no_such_field'"], bad


# --- a table cell ends at its first pipe (WP-1409) --------------------------
#
# GFM splits a table row on every unescaped `|`, code spans included, so
# `scale × |F|² × profile` in a cell opens a span the cell never closes and
# the backticks print literally.  The manual's HTML scan caught that one only
# because `using/skill.md` includes the body whole; no reference file reaches
# that build.  So the check runs on the Markdown: split each table row where
# GFM does, and require every code span to close inside its own cell.

_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
_BACKTICK_RUN = re.compile(r"`+")


def _cells_with_an_open_span(line: str) -> list[str]:
    """The cells of one table row in which a code span opens and never closes.

    A span opens on a run of N backticks and closes on the next run of exactly
    N, which is how a span can hold a backtick at all."""
    bad = []
    for cell in _UNESCAPED_PIPE.split(line.strip().strip("|")):
        open_run = 0
        for run in _BACKTICK_RUN.findall(cell):
            if not open_run:
                open_run = len(run)
            elif len(run) == open_run:
                open_run = 0
        if open_run:
            bad.append(cell.strip())
    return bad


def _broken_table_spans(text: str) -> list[str]:
    bad, fenced = [], False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.lstrip().startswith("|"):
            bad += [f"line {n}: {cell[:60]!r}" for cell in _cells_with_an_open_span(line)]
    return bad


@pytest.mark.parametrize("path", [SKILL, *REFERENCES], ids=lambda p: p.name)
def test_no_code_span_is_cut_by_a_table_cell(path: Path):
    bad = _broken_table_spans(path.read_text(encoding="utf-8"))
    assert not bad, (
        f"{path.name}: a code span in a table cell holds an unescaped `|`, which "
        f"ends the cell before the span closes: {bad}. Escape the pipe as `\\|`, "
        "or drop the span as abstention.md's § 6 row does")


def test_the_table_span_check_catches_the_row_it_was_written_for():
    assert _broken_table_spans("| a | `scale × |F|² × profile` |")
    assert not _broken_table_spans("| a | `scale × \\|F\\|² × profile` |")
    assert not _broken_table_spans("| a | ``x`y`` and `z` |")
    assert not _broken_table_spans("```\n| `open |\n```")


RX_DOT_NAME = re.compile(r"`rx\.([A-Za-z_][A-Za-z0-9_]*)")


def test_every_rx_dot_name_in_the_tree_is_reachable():
    """Writing `rx.X` promises a reader can do the same (WP-1302's rule, and
    WP-1037's bug: the flag asked `hasattr(rx, "index")` while the export was
    `index_pattern`).

    A submodule keeps the promise the same way an export does — `rx.report`,
    `rx.viz` and `rx.io` are reachable only because `rietx/__init__` imports
    them, which is exactly the fact this asserts.  Nothing else is allowed:
    an attribute that is neither in `__all__` nor a module is a name a reader
    cannot rely on.
    """
    import types

    import rietx as rx

    missing = set()
    for path in [SKILL, *REFERENCES]:
        for name in RX_DOT_NAME.findall(path.read_text(encoding="utf-8")):
            if name in rx.__all__:
                continue
            if isinstance(getattr(rx, name, None), types.ModuleType):
                continue
            missing.add((path.name, name))
    assert not missing, sorted(missing)


def test_the_body_carries_the_judgement_core():
    """The rules an orchestrator copies into a brief stay in the body, not in a
    reference file: the campaign this WP answers had workers restating rules
    from a brief 71 times and opening the document 0 times."""
    text = SKILL.read_text(encoding="utf-8")
    for anchor in ("## 1.", "## 2.", "## 3.", "## 4.", "## 4b.", "## 6.",
                   "## 10."):
        assert anchor in text, f"the body no longer carries {anchor}"
    assert "stop condition" in text.lower()


# § 10's block is the one an agent copies, so `examples/skill_worked_default.py`
# runs it (`tests/test_examples.py`).  The body cannot `{literalinclude}` the
# script, because an agent reads SKILL.md raw, so the two are two copies and
# this holds them equal.  Each side drops only the lines naming its files.
WORKED_DEFAULT = ROOT / "examples" / "skill_worked_default.py"
_WORKED_DEFAULT_FENCE = re.compile(r"^## 10\..*?^```python\n(.*?)^```", re.S | re.M)


def _body_worked_default(text: str) -> list[str]:
    block = _WORKED_DEFAULT_FENCE.search(text)
    assert block, "SKILL.md has no ```python fence under its § 10 heading"
    return [line for line in block.group(1).splitlines()
            if not line.startswith("PATTERN, CIF =")]


def _example_worked_default(text: str) -> list[str]:
    lines = text.splitlines()
    return [line for line in lines[lines.index("import numpy as np"):]
            if not line.startswith(("DATA =", "PATTERN, CIF ="))]


def _worked_default_drift(body: str, example: str) -> list[str]:
    a, b = _body_worked_default(body), _example_worked_default(example)
    return [f"line {n}: body {x!r} / example {y!r}"
            for n, (x, y) in enumerate(zip(a, b), 1) if x != y] + (
        [f"body has {len(a)} lines, example {len(b)}"] if len(a) != len(b) else [])


def test_the_worked_default_is_the_example_that_runs():
    drift = _worked_default_drift(SKILL.read_text(encoding="utf-8"),
                                  WORKED_DEFAULT.read_text(encoding="utf-8"))
    assert not drift, (
        "SKILL.md § 10 and examples/skill_worked_default.py have drifted apart: "
        f"{drift[:5]}. Edit both in the same change: the body is what an agent "
        "copies, the example is what tests/test_examples.py runs")


def test_the_worked_default_check_catches_the_drift_it_was_written_for():
    body = SKILL.read_text(encoding="utf-8")
    example = WORKED_DEFAULT.read_text(encoding="utf-8")
    assert not _worked_default_drift(body, example)
    assert _worked_default_drift(body, example.replace("[:12]", "[:10]"))
    assert _worked_default_drift(body, example + "print(result.statistics)\n")
    assert _worked_default_drift(body.replace("import rietx as rx\n", ""), example)


def test_the_api_index_resolves_through_a_field_hop():
    """Liveness for the resolver itself: a pydantic field is not a class
    attribute, so a walk that used plain getattr would pass this file by
    failing on its first result field."""
    import rietx as rx

    ok, obj = attr_step(rx.RefinementResult, "statistics")
    assert ok and obj is rx.Statistics
    assert not attr_step(rx.RefinementResult, "no_such_field")[0]


# --- the skill's doors -----------------------------------------------------
#
# `tests/api_surface.py` partitions the package's whole call surface against
# the **manual**, whose job is coverage.  The skill is a different document
# with a different denominator: it is a protocol, not a reference, and the
# only names it is obliged to carry are the ones a caller cannot arrive at by
# following an object already in hand.
#
# That set is derived, not listed: the module-level **functions** in
# `rietx.__all__`.  A free verb is the one thing nothing leads to.  A type is
# either returned by a verb — and the index renders its fields where the
# answer is described — or constructed from a class the index already carries
# with its full signature, so an agent holding an `Instrument` reaches its
# constructors through `help(rx.Instrument)`.  Nothing an agent holds leads to
# `read_recipe`, which is why four agents of four, both models, handed a real
# TOPAS `.inp` beside the data it describes, parsed it by hand and never
# called it (WP-1307 round 1.1; `tests/eval_agent_surface/PROTOCOL.md`).
#
# **Documented means named in a generated api index**, not merely somewhere in
# the tree.  `read_recipe` was in `references/diagnostics.md` the whole time,
# inside a `RECIPE_*` row that cannot fire until the door has already been
# used, so a tree-wide test would have called that coverage.  An index is the
# file the routing table names for *"you are about to call rietx: entry
# points"*, and it is generated, so this gate lands on `make_api_index.py`'s
# SECTIONS selection — the thing WP-1306 had no reason to touch when it added
# the `RECIPE_*` rows and shipped the diagnostics without the door.
#
# **A technique nobody's everyday fit uses gets an index of its own**
# (`api-<technique>.md`), and `api.md` stays the everyday one.  The reason is
# the reader's context and not the byte cap: `api.md` is loaded by every
# session that is about to call rietx, so a name only a magnetic refinement
# will ever reach is a cost paid by every session that will never reach it.
# The cap follows from that rather than causing it.  The authored heuristics
# for the same technique stay in their own `references/<technique>.md` under
# the shape rule (root CLAUDE.md § skill) — an authored file and a generated
# index are different objects, and only the generated one is pinned byte for
# byte against `make_api_index.py`.
#
# Deliberately NOT covered, recorded so a later session reads it as a gap and
# not as a decision: alternative constructors (`Instrument.
# flat_plate_transmission`, the seven `RefinementPlan.*` presets).  Thirty of
# the thirty-five are reached another way — a plan by its name string through
# `rx.PLAN_INFO`, a `GuardFinding.*` never by a caller at all — so a partition
# over them would be thirty shrugs, which is the curated list this file exists
# to avoid.

#: An entry *row* of the api index, which always renders as ``- `rx.name(…``.
#: A prose mention is not a door: the paragraph above a section may name a verb
#: in passing, and matching those would let a sentence satisfy the gate that a
#: signature row is supposed to.
API_INDEX_ENTRY = re.compile(r"^- `rx\.([A-Za-z_][A-Za-z0-9_]*)", re.M)


def _documented_verbs() -> set[str]:
    """Names an api index gives an entry row of its own.

    The union over `api.md` and every `api-<technique>.md`.  A verb's door is
    signed wherever a session that would call it is routed, and a technique's
    session is routed to the technique's index.
    """
    return {name for path in API_INDEXES
            for name in API_INDEX_ENTRY.findall(path.read_text(encoding="utf-8"))}


#: A verb the skill deliberately does not carry, and why.  Each entry is a
#: *reason*, never a shrug; the meta-test below fails on one that names
#: nothing, so a rename cannot leave a dead exclusion behind.
SKILL_EXCLUDED_VERBS: dict[str, str] = {
    "help_registry": (
        "the whole corpus in one call, for the GUI server's GET /api/help "
        "(`gui/session.py`). An agent reads one path at a time with "
        "`rx.help_for(path)`, which section In carries."
    ),
    "help_key_for": (
        "the lookup behind `ParameterRow.help_key`, which `refine.py` has "
        "already done by the time a caller holds a row. The index renders "
        "that field, so a caller has the key without making the call."
    ),
}


def _public_verbs() -> dict[str, object]:
    """The package's free verbs, read out of the live package."""
    import inspect

    import rietx as rx

    return {n: getattr(rx, n) for n in rx.__all__
            if inspect.isroutine(getattr(rx, n))}


def test_every_public_verb_is_documented_in_the_skill_or_excluded():
    """A new entry point ships with its door signed, or with a reason.

    The rule CLAUDE.md already carried — a WP adding a diagnostic code adds
    its row to the skill — is what WP-1306 followed: the `RECIPE_*` rows are
    present and good. Nothing told it to add the *entry point*, so the
    diagnostics arrived and the door did not. This is that rule made
    self-enforcing.
    """
    verbs = _public_verbs()
    assert len(verbs) > 20, f"only {len(verbs)} verbs found — __all__ moved"

    documented = _documented_verbs()
    undocumented = sorted(set(verbs) - documented - set(SKILL_EXCLUDED_VERBS))
    assert not undocumented, (
        "public entry points the skill does not name — add each to "
        "docs/skill/make_api_index.py's SECTIONS (then regenerate, and "
        "`rietx skill --install . --copy`), or to SKILL_EXCLUDED_VERBS with "
        f"the reason a reader never needs it: {undocumented}")


def test_the_verb_exclusions_are_live_and_reasoned():
    """The exclusion table is the authored half, so it rots like any list.

    An entry naming a verb that no longer exists is a dead promise; one that
    is *also* documented is a contradiction, and the documentation wins.
    """
    verbs = _public_verbs()
    dead = sorted(set(SKILL_EXCLUDED_VERBS) - set(verbs))
    assert not dead, f"excluded, but no longer a public verb: {dead}"

    documented = _documented_verbs()
    both = sorted(set(SKILL_EXCLUDED_VERBS) & documented)
    assert not both, f"excluded and documented — drop the exclusion: {both}"

    for name, reason in SKILL_EXCLUDED_VERBS.items():
        assert len(reason) > 40, f"{name}'s exclusion is a shrug, not a reason"
#: Families that fire while **reading another program's file** rather than on
#: a fit: the project readers (`rietx.io.projects`) and the PowderLine recipe
#: reader.  None of them ever reaches ``result.diagnostics``, which is what
#: makes a table of them a different lookup from the engine's — §7g exists for
#: exactly that split, and WP-1103 appended two engine rows
#: (``EXTRA_PEAK_ON_REFLECTION``, ``EXTRA_PEAK_NO_INTENSITY``) to the recipe
#: table where nothing caught it: the preamble above a table is prose, so a row
#: filed under the wrong one is told to a reader in the wrong voice and travels
#: with the wrong block the next time one moves.
#: ``GSAS_FIELD_`` is the record grammar the ``.EXP`` and ``.prm`` readers
#: share, so its codes fire from either and carry neither suffix.
FOREIGN_FILE_PREFIXES = ("RECIPE_", "TOPAS_", "FULLPROF_", "GSAS_PRM_",
                          "GSAS_EXP_", "GSAS_FIELD_", "GSAS2_GPX_",
                          "GSAS2_INSTPRM_", "GSAS2_CIF_", "GSAS_IPARM_")

_CODE_ROW = re.compile(r"^\| `([A-Z][A-Z0-9_]+)`")


def _code_tables(text: str) -> list[list[str]]:
    """Each run of consecutive code rows, as the codes it lists."""
    tables: list[list[str]] = []
    run: list[str] = []
    for line in text.splitlines():
        m = _CODE_ROW.match(line)
        if m:
            run.append(m.group(1))
        elif run and not line.startswith("|"):
            tables.append(run)
            run = []
    if run:
        tables.append(run)
    return tables


@pytest.mark.parametrize("path", REFERENCES, ids=lambda p: p.name)
def test_no_table_mixes_a_foreign_file_family_with_an_engine_row(path: Path):
    """A table is introduced by a paragraph saying where its codes come from.

    That paragraph is the only thing telling a reader whether a row arrives on
    ``result.diagnostics`` or on a reader's own channel, so a table holding
    both answers describes at least one of its rows wrongly — and a block moved
    wholesale (§7's `RECIPE_*` family is queued to join §7g) carries the
    stowaway into a file an agent whose *fit* fired it will never open.
    """
    for codes in _code_tables(path.read_text(encoding="utf-8")):
        foreign = [c for c in codes if c.startswith(FOREIGN_FILE_PREFIXES)]
        if not foreign:
            continue
        engine = [c for c in codes if not c.startswith(FOREIGN_FILE_PREFIXES)]
        assert not engine, (
            f"{path.name}: a table of {foreign[0]}'s family also lists "
            f"{engine} — those fire on result.diagnostics, so they belong in "
            "the engine table under its own preamble, not this one")


@pytest.mark.parametrize("path", REFERENCES, ids=lambda p: p.name)
def test_no_code_is_listed_twice_in_one_reference(path: Path):
    """A row is a lookup, so a second one for the same code is a wrong answer.

    The two copies drift as soon as either is edited, and a reader who stops at
    the first never learns the second exists — ``GSAS2_GPX_SETTING_FROM_OPERATORS``
    shipped twice, once saying the operators' setting "need not be" the symbol's
    and once saying it "is not", which are different claims (WP-1118 review).
    """
    seen: dict[str, int] = {}
    for codes in _code_tables(path.read_text(encoding="utf-8")):
        for code in codes:
            seen[code] = seen.get(code, 0) + 1
    twice = sorted(c for c, n in seen.items() if n > 1)
    assert not twice, (
        f"{path.name}: {twice} each have more than one row — a lookup with two "
        "answers, and the copies drift the first time either is edited")
