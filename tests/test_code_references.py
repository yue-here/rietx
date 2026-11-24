"""Every name, path and test a comment in ``src/rietx`` cites is in the tree (WP-2233).

The resolver and its rules are `tests/code_references.py`'s docstring.  The
planted breaks below show each kind of miss failing once, with a message that
names the citing file and line.
"""

from __future__ import annotations

import pytest

from tests import code_references as cr


def test_every_comment_citation_resolves():
    """12-14 s locally, most of it importing every rietx module.  Fast tier
    rather than ``slow``: a stale citation is written by an ordinary change,
    and the nightly is too late to name the change that wrote it."""
    misses = cr.unallowed(cr.find_misses())
    assert not misses, (
        f"{len(misses)} citations do not resolve:\n"
        + "\n".join(f"  {m}" for m in misses) + f"\n{cr.MESSAGE}")


def _misses(text: str, file: str = "src/rietx/refine.py") -> list[cr.Miss]:
    return list(cr.misses_in(cr.Block(file, 10, text)))


@pytest.mark.parametrize("text", [
    ":func:`rietx.refine.Refinement.fit`",          # absolute
    ":meth:`Refinement.fit`",                        # relative to the citing module
    ":class:`~rietx.schemas.common.Diagnostic`",     # tilde form
    ":func:`Title <rietx.crystallography.cif.structure_from_cif>`",
    ":data:`SCHEMA_VERSION`",                        # a name defined elsewhere in rietx
    "``refine._build_result``",                      # the module the export shadows
    "``model.y_obs``",                               # a variable, not a module path
    "``tests/test_bccg.py::test_cg_core_matches_direct_solve``",
    "``model/rows.py``",                             # relative to src/rietx
])
def test_a_live_citation_resolves(text):
    assert _misses(text) == []


def test_a_renamed_function_fails_with_its_file_and_line():
    found = _misses("Text first.\nThen :func:`rietx.refine.fit_renamed_away` here.")
    assert [str(m) for m in found] == [
        "src/rietx/refine.py:11: role :func:`rietx.refine.fit_renamed_away`"]


def test_a_role_wrapped_across_lines_is_read_whole():
    found = _misses(":data:`~rietx.crystallography.magnetic.moments.\nNO_SUCH_TILT`")
    assert [m.cited for m in found] == [
        ":data:`~rietx.crystallography.magnetic.moments.NO_SUCH_TILT`"]


def test_a_deleted_test_file_fails():
    found = _misses("see ``tests/test_deleted_long_ago.py``")
    assert [(m.kind, m.cited, m.line) for m in found] == [
        ("path", "tests/test_deleted_long_ago.py", 10)]


def test_a_renamed_test_fails_by_its_node():
    found = _misses("``tests/test_bccg.py::test_unconstrained_matches_direct_solve``")
    assert [m.cited for m in found] == [
        "tests/test_bccg.py::test_unconstrained_matches_direct_solve"]


def test_a_stale_dotted_literal_fails():
    assert [m.cited for m in _misses("``refine._attach_origin``")] == [
        "``refine._attach_origin``"]


@pytest.mark.parametrize("text", [
    "obs/calc", "and/or", "https://example.org/a/b.py", "``tests/eval_*/x.py``",
])
def test_prose_that_only_looks_like_a_path_is_not_checked(text):
    assert _misses(text) == []


def test_the_allowlist_is_read_from_source_by_ast():
    source = 'ALLOWLIST: dict[str, str] = {\n    "a/b.py": "why",\n    "``c.d``": "why"}\n'
    assert cr.allowlist_names(source) == {"a/b.py", "``c.d``"}
    assert cr.allowlist_names((cr.ROOT / cr.REL).read_text(encoding="utf-8")) == set(
        cr.ALLOWLIST)


def test_every_allowlist_entry_carries_a_reason():
    assert all(reason.strip() for reason in cr.ALLOWLIST.values())


def test_a_new_allowlist_entry_beside_other_edits_fails(monkeypatch, capsys):
    """The planted break for ``--delta``: an entry the base lacks, in a change
    that also edits a source file."""
    from tests import skill_caps

    monkeypatch.setattr(skill_caps, "base", lambda: ("BASE", "a planted base"))
    monkeypatch.setattr(skill_caps, "rev_exists", lambda rev: True)
    base_source = (cr.ROOT / cr.REL).read_text(encoding="utf-8")
    monkeypatch.setattr(skill_caps, "_git", lambda *a: type(
        "R", (), {"returncode": 0, "stdout": base_source})())
    monkeypatch.setitem(cr.ALLOWLIST, "``refine._planted``", "a planted entry")

    monkeypatch.setattr(skill_caps, "changed_files", lambda rev: {cr.REL})
    assert cr.delta_main() == 0
    assert "allowlist entry new against the base: ``refine._planted``" in (
        capsys.readouterr().out)

    monkeypatch.setattr(skill_caps, "changed_files",
                        lambda rev: {cr.REL, "src/rietx/refine.py"})
    assert cr.delta_main() == 1
    err = capsys.readouterr().err
    assert "src/rietx/refine.py" in err and "change that touches only" in err


def test_a_pull_request_whose_base_is_missing_fails(monkeypatch, capsys):
    from tests import skill_caps

    monkeypatch.setattr(skill_caps, "base", lambda: ("HEAD^1", "the pull request's base"))
    monkeypatch.setattr(skill_caps, "rev_exists", lambda rev: False)
    assert cr.delta_main() == 1
    assert "fetch-depth: 2" in capsys.readouterr().err


def test_the_change_that_adds_the_file_passes(monkeypatch, capsys):
    from tests import skill_caps

    monkeypatch.setattr(skill_caps, "base", lambda: ("BASE", "a planted base"))
    monkeypatch.setattr(skill_caps, "rev_exists", lambda rev: True)
    monkeypatch.setattr(skill_caps, "_git", lambda *a: type(
        "R", (), {"returncode": 128, "stdout": ""})())
    assert cr.delta_main() == 0
    assert "is new against a planted base" in capsys.readouterr().out
