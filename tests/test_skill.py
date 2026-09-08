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
reference file, which is what the tree is for.

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

import re
from pathlib import Path

import pytest
import yaml

from tests.api_surface import attr_step, resolve_dotted

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "docs" / "skill" / "rietx"
SKILL = SKILL_DIR / "SKILL.md"
REFERENCE_DIR = SKILL_DIR / "references"
REFERENCES = sorted(REFERENCE_DIR.glob("*.md"))
API_INDEX = REFERENCE_DIR / "api.md"

#: A skill body is read whole on activation; the Read tool returned 66 kB on
#: the document this replaced, so the body is capped at half of it.
# Half the Read tool's ~66 kB cap, the derivation this module's docstring
# states; 32_000 was that halving rounded down and WP-1131 rounded it up, in
# the commit that needed the 941 B — a fifth deliverable class (microstructure)
# in the body's own deliverable table, with its worked measurement in
# references/judging.md where the other four keep theirs.  The cost this cap
# governs — the fixed bytes every session that loads the skill pays — moves by
# 3 %, and the alternative was a deliverable whose row lived outside the table
# its peers are in, which is what the cap exists to protect against.
SKILL_MAX_BYTES = 33_000
#: agentskills.io/specification: "Keep your main SKILL.md under 500 lines."
SKILL_MAX_LINES = 500
#: Bash output above 40 kB is truncated to a ~2 kB preview, so a reference file
#: stays comfortably under that even when a session cats it rather than Reads.
REFERENCE_MAX_BYTES = 36_000

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
        "into references/ — see this module's docstring on raising a cap."
    )
    assert lines < SKILL_MAX_LINES, (
        f"SKILL.md is {lines} lines (cap {SKILL_MAX_LINES}, the spec's own)."
    )


@pytest.mark.parametrize("path", REFERENCES, ids=lambda p: p.name)
def test_every_reference_file_is_within_its_cap(path: Path):
    size = len(path.read_bytes())
    assert size <= REFERENCE_MAX_BYTES, (
        f"{path.name} is {size} B (cap {REFERENCE_MAX_BYTES}); split it."
    )


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


def test_every_reference_file_is_reachable_from_the_body():
    """A reference nothing points at is a file no agent will open."""
    text = SKILL.read_text(encoding="utf-8")
    unreferenced = [p.name for p in REFERENCES
                    if f"references/{p.name}" not in text]
    assert not unreferenced, (
        f"reference files the body never names: {unreferenced} — add a row to "
        "the body's index table"
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
# `test_every_dotted_name_in_the_api_index_resolves` already cover from the
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
    matters -- a tag wraps across lines, and ``.`` does not cross a newline, so
    a naive match reads `(Measured: archive` and stops.
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


@pytest.mark.parametrize("path", _evidence_tagged(), ids=lambda p: p.name)
def test_every_measured_tag_names_this_repository_or_the_declared_corpus(
        path: Path):
    paras = _paragraphs(path.read_text(encoding="utf-8"))
    corpus = _declared_corpus(paras)
    assert corpus is None or "\x00" not in corpus, (
        f"{path.name}: the provenance paragraph holds "
        f"{len(corpus.split(chr(0)))} bold spans "
        f"({', '.join(repr(s) for s in corpus.split(chr(0)))}) — exactly one "
        "is the corpus declaration, so a second is ambiguous. Bold the corpus "
        "and nothing else there")

    for row in _rows(paras):
        sec, n = _ROW_HEAD.match(row[0]).groups()
        parts = _tag_parts(row[-1])
        if parts is None or parts[0] != "Measured":
            continue          # no tag is the row gate's business; Hypothesis is outside
        body = parts[1]
        if body.startswith("WP-"):
            continue
        assert corpus, (
            f"{path.name}: row {sec}.{n} closes *(Measured: {body[:50]}…)*, "
            "which names neither a WP nor a declared corpus — and this file "
            "declares no corpus. Either name the run so a reader can open it, "
            "or declare the corpus once in the provenance paragraph, in bold")
        assert body.startswith(corpus), (
            f"{path.name}: row {sec}.{n} closes *(Measured: {body[:60]}…)*. A "
            f"row measured outside this repository names the declared corpus "
            f"{corpus!r} first, spelled the same way every time — otherwise "
            "the tag reads as a citation to something a reader could go and "
            "find. Start it with that string, or with WP- if the run is here")


def test_every_dotted_name_in_the_api_index_resolves():
    """The API index cannot name something the package does not have."""
    text = API_INDEX.read_text(encoding="utf-8")
    names = {m.rstrip(".") for m in DOTTED.findall(text)}
    assert len(names) > 60, f"only {len(names)} names found — the regex broke"
    for name in sorted(names):
        dotted = name if name.startswith("rietx.") else "rietx." + name[len("rx."):]
        resolve_dotted(dotted, API_INDEX.name)


def test_the_api_index_is_what_the_generator_renders():
    """`references/api.md` is generated and committed (it ships in the wheel
    with no build step), so the committed bytes must be what the generator
    renders from *this* package — a rename, a new keyword or a changed default
    fails here until the file is regenerated."""
    import difflib
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "make_api_index", ROOT / "docs" / "skill" / "make_api_index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    rendered = mod.render()
    committed = API_INDEX.read_text(encoding="utf-8")
    if rendered != committed:
        diff = list(difflib.unified_diff(
            committed.splitlines(), rendered.splitlines(),
            "committed", "rendered", lineterm="", n=0))
        pytest.fail(
            "references/api.md is stale — regenerate with\n"
            "  .venv/bin/python docs/skill/make_api_index.py && "
            "rietx skill --install . --copy\n"
            + "\n".join(diff[:40]))
    # the selection cannot be wider than what a reader can reach
    assert " at 0x" not in rendered


#: `report.regions`, `result.statistics.rwp`, `statistics.esd_inflation`,
#: `d.suggestion` — the body's own field names, which no generator writes.
BODY_DOTTED = re.compile(
    r"`(report|result|statistics|d)((?:\.[A-Za-z_][A-Za-z0-9_]*)+)(?:\(|`)")


def test_every_dotted_name_in_the_body_resolves():
    """The judgement core names result and report fields by hand (`report.
    identifiability.exchanges`, `statistics.max_shift_over_esd`), and a rule
    written against a field that has moved is a rule nobody can follow.
    Each is walked through the types the way the manual's names are."""
    import rietx as rx

    roots = {"report": rx.FitReport, "result": rx.RefinementResult,
             "statistics": rx.Statistics, "d": rx.Diagnostic}
    text = SKILL.read_text(encoding="utf-8")
    bad = []
    for root, chain in BODY_DOTTED.findall(text):
        obj = roots[root]
        for step in chain.lstrip(".").split("."):
            ok, obj = attr_step(obj, step)
            if not ok:
                bad.append(f"{root}{chain}: no {step!r}")
                break
    assert not bad, bad
    assert len(BODY_DOTTED.findall(text)) > 15, "the regex found too little"


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
# **Documented means named in `references/api.md`**, not merely somewhere in
# the tree.  `read_recipe` was in `references/diagnostics.md` the whole time,
# inside a `RECIPE_*` row that cannot fire until the door has already been
# used, so a tree-wide test would have called that coverage.  `api.md` is the
# file the routing table names for *"you are about to call rietx: entry
# points"*, and it is generated, so this gate lands on `make_api_index.py`'s
# SECTIONS selection — the thing WP-1306 had no reason to touch when it added
# the `RECIPE_*` rows and shipped the diagnostics without the door.
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
    """Names the api index gives an entry row of its own."""
    return set(API_INDEX_ENTRY.findall(API_INDEX.read_text(encoding="utf-8")))


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
