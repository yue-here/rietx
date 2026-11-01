"""The hosted manual's versions (WP-1979, `docs/docs_versions.py`).

The deploy itself runs only in pages.yml, so these tests drive the same
functions against a fake site and a fake release list, with no network.
"""

from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

from rietx._about import DIST_NAME

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _load():
    spec = importlib.util.spec_from_file_location(
        "_docs_versions", ROOT / "docs" / "docs_versions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


versions = _load()


def _release(tag, *, docs=True, draft=False, prerelease=False):
    assets = [{"name": f"{DIST_NAME}-{tag[1:]}.tar.gz"}]
    if docs:
        assets.append({"name": versions.asset_name(tag[1:])})
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease, "assets": assets}


@pytest.mark.parametrize(("version", "directory"), [
    ("1.10.0.dev0", "dev"), ("1.9.1.dev0", "dev"), ("1.10.0rc1", "dev"),
    ("1.10.0", "1.10"), ("1.10.2", "1.10"), ("2.0.0", "2.0"),
])
def test_a_version_maps_to_its_minor_or_to_dev(version, directory):
    assert versions.docs_version(version) == directory


def test_the_newest_patch_of_each_recent_minor_is_kept():
    releases = [_release("v1.10.0"), _release("v1.10.2"), _release("v1.10.1"),
                _release("v1.9.0"), _release("v1.11.0", draft=True),
                _release("v1.12.0", prerelease=True), _release("v1.8.0", docs=False),
                _release("kernels-v1.0.0")]
    # Numeric order: a string sort would put 1.9 above 1.10.
    assert versions.kept_releases(releases) == [("1.10", "1.10.2"), ("1.9", "1.9.0")]


def test_only_the_newest_minors_are_kept():
    releases = [_release(f"v1.{minor}.0") for minor in range(10, 20)]
    kept = versions.kept_releases(releases)
    assert [minor for minor, _ in kept] == [f"1.{m}" for m in range(19, 19 - versions.KEEP_MINORS, -1)]


def test_the_switcher_marks_the_newest_minor_stable():
    entries = versions.switcher_entries(["1.11", "1.10"])
    assert entries == [
        {"name": "dev", "version": "dev", "url": "/docs/dev/"},
        {"name": "1.11 (stable)", "version": "1.11", "url": "/docs/stable/", "preferred": True},
        {"name": "1.10", "version": "1.10", "url": "/docs/1.10/"},
    ]


def _site(tmp_path):
    (tmp_path / "docs" / "dev").mkdir(parents=True)
    (tmp_path / "docs" / "dev" / "index.html").write_text("dev", encoding="utf-8")
    return tmp_path


def _tarball(tmp_path, version, llms=None):
    path = tmp_path / versions.asset_name(version)
    files = {"./index.html": version} | ({"./llms.txt": llms} if llms else {})
    with tarfile.open(path, "w:gz") as archive:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


def test_assemble_lays_out_each_kept_minor_and_stable(tmp_path):
    site = _site(tmp_path / "site")
    versions.assemble(site, [("1.11", "1.11.1"), ("1.10", "1.10.0")],
                      lambda version: _tarball(tmp_path, version))
    docs = site / "docs"
    assert (docs / "1.11" / "index.html").read_text(encoding="utf-8") == "1.11.1"
    assert (docs / "1.10" / "index.html").read_text(encoding="utf-8") == "1.10.0"
    assert (docs / "stable" / "index.html").read_text(encoding="utf-8") == "1.11.1"
    assert [e["url"] for e in json.loads((docs / "switcher.json").read_text(encoding="utf-8"))] \
        == ["/docs/dev/", "/docs/stable/", "/docs/1.10/"]
    assert 'url=stable/"' in (docs / "index.html").read_text(encoding="utf-8")


def test_before_any_release_carries_a_tree_docs_points_at_dev(tmp_path):
    site = _site(tmp_path)
    versions.assemble(site, [], lambda version: pytest.fail("nothing to fetch"))
    assert 'url=dev/"' in (site / "docs" / "index.html").read_text(encoding="utf-8")
    assert len(json.loads((site / "docs" / "switcher.json").read_text(encoding="utf-8"))) == 1


def test_a_retired_page_gets_a_stub_pointing_into_the_hosted_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(versions, "RETIRED", {"profiles": "theory/profiles#tchz"})
    site = _site(tmp_path)
    versions.assemble(site, [], lambda version: pytest.fail("nothing to fetch"))
    stub = (site / "profiles.html").read_text(encoding="utf-8")
    assert 'content="0; url=/docs/dev/theory/profiles.html#tchz"' in stub
    assert 'rel="canonical" href="https://rietx.org/docs/dev/theory/profiles.html#tchz"' in stub
    # The stub names its own heading, so the reader's fragment is not carried over.
    assert "location.hash" not in stub


def test_a_stub_without_a_heading_carries_the_readers_fragment_over(tmp_path, monkeypatch):
    """An installed release's help anchors are `<chapter>.html#<heading>` at the
    site root, and the meta refresh alone would drop the heading."""
    monkeypatch.setattr(versions, "RETIRED", {"profiles": "theory/profiles"})
    site = _site(tmp_path)
    versions.assemble(site, [], lambda version: pytest.fail("nothing to fetch"))
    stub = (site / "profiles.html").read_text(encoding="utf-8")
    assert '<script>location.replace("/docs/dev/theory/profiles.html" + location.hash)' in stub
    assert 'content="0; url=/docs/dev/theory/profiles.html"' in stub


def test_a_stub_points_at_stable_only_once_stable_has_the_page(tmp_path, monkeypatch):
    monkeypatch.setattr(versions, "RETIRED", {"profiles": "index", "background": "theory/bg"})
    site = _site(tmp_path / "site")
    versions.assemble(site, [("1.11", "1.11.1")], lambda version: _tarball(tmp_path, version))
    # The release's tarball holds index.html and nothing under theory/.
    assert "url=/docs/stable/index.html" in (site / "profiles.html").read_text(encoding="utf-8")
    assert "url=/docs/dev/theory/bg.html" in (site / "background.html").read_text(encoding="utf-8")


def test_the_root_llms_txt_is_the_hosted_trees_with_its_links_rebased(tmp_path):
    """Dev's while the stable tree has none, then stable's (WP-1980)."""
    site = _site(tmp_path / "site")
    (site / "docs" / "dev" / "llms.txt").write_text(
        "# rietx\n\n- [A](concepts/a.html.md): x\n- [B](https://example.org/b.md): y\n",
        encoding="utf-8")
    versions.assemble(site, [("1.11", "1.11.1")], lambda version: _tarball(tmp_path, version))
    assert (site / "llms.txt").read_text(encoding="utf-8") == (
        "# rietx\n\n- [A](/docs/dev/concepts/a.html.md): x\n- [B](https://example.org/b.md): y\n")
    versions.assemble(site, [("1.12", "1.12.0")],
                      lambda version: _tarball(tmp_path, version, llms="- [A](a.html.md): x\n"))
    assert (site / "llms.txt").read_text(encoding="utf-8") == "- [A](/docs/stable/a.html.md): x\n"


def test_assemble_runs_twice_over_one_site(tmp_path):
    site = _site(tmp_path / "site")
    for _ in range(2):
        versions.assemble(site, [("1.11", "1.11.1")], lambda version: _tarball(tmp_path, version))
    assert (site / "docs" / "stable" / "index.html").read_text(encoding="utf-8") == "1.11.1"


def test_every_page_the_old_tree_published_has_a_stub():
    """The old tree (`docs/manual/`) is retired (WP-1986), so a stub is the
    only thing left serving each of its URLs."""
    assert not (ROOT / "docs" / "manual").exists()
    lost = [page for page in versions.OLD_PAGES if page not in versions.RETIRED]
    assert not lost, f"no RETIRED entry, so their URLs 404: {lost}"


def _new_tree_page_exists(page):
    new_tree = ROOT / "docs" / "docs"
    if any((new_tree / f"{page}{suffix}").is_file() for suffix in (".md", ".ipynb")):
        return True
    # The tutorial notebooks are copied into start/tutorials/ at build time
    # (`sphinx_shared.copy_tutorials`), from their committed home.
    folder, _, stem = page.rpartition("/")
    return folder == "start/tutorials" and (ROOT / "examples" / "tutorials" / f"{stem}.ipynb").is_file()


def test_a_stub_targets_a_new_tree_page():
    for old, new in versions.RETIRED.items():
        assert old in versions.OLD_PAGES, f"{old} was never published"
        page = new.partition("#")[0]
        assert _new_tree_page_exists(page), f"{old} -> {new}, which docs/docs/ has no page for"


def test_a_stub_never_overwrites_a_landing_page_file():
    """pages.yml copies the landing page into the site root before the stubs
    are written, so a stub at a landing page's path would replace it.  The
    pages are `build.py`'s own table; its other files sit in folders no old
    page used."""
    spec = importlib.util.spec_from_file_location(
        "_landing_build", ROOT / "docs" / "landing" / "build.py")
    landing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(landing)
    stubs = {f"{old}.html" for old in versions.RETIRED}
    clashes = sorted(stubs & (set(landing.PAGES) | {"favicon.svg"}))
    assert not clashes, f"a stub would overwrite the landing page's {clashes}"
    folders = {Path(stub).parts[0] for stub in stubs if "/" in stub}
    assert not folders & {"img", "data", "notebooks"}, folders


def test_the_workflows_agree_with_the_script():
    release = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    pages = (WORKFLOWS / "pages.yml").read_text(encoding="utf-8")
    # release.yml attaches the asset under the name the script fetches.
    assert versions.asset_name("${version}") in release
    assert "docs/docs_versions.py site" in pages
    assert 'export DOCS_VERSION="${version%.*}"' in release


def _shared(monkeypatch, installed, docs_version=None):
    """Import docs/sphinx_shared.py afresh, as a build under this version would."""
    import rietx

    monkeypatch.setattr(rietx, "__version__", installed)
    if docs_version is None:
        monkeypatch.delenv("DOCS_VERSION", raising=False)
    else:
        monkeypatch.setenv("DOCS_VERSION", docs_version)
    monkeypatch.syspath_prepend(str(ROOT / "docs"))
    spec = importlib.util.spec_from_file_location("_sphinx_shared", ROOT / "docs" / "sphinx_shared.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("installed", "docs_version", "ref"), [
    ("1.10.0.dev0", None, "main"),
    # main at the commit a release is cut from, before its tag exists.
    ("1.10.0", None, "main"),
    ("1.10.2", "1.10", "v1.10.2"),
])
def test_a_build_links_its_tag_only_when_it_is_a_release_build(monkeypatch, installed,
                                                                docs_version, ref):
    assert _shared(monkeypatch, installed, docs_version).SOURCE_REF == ref


@pytest.mark.parametrize(("installed", "docs_version"), [("1.10.2", "1.9"), ("1.10.0.dev0", "1.10")])
def test_a_build_refuses_a_docs_version_that_is_not_the_installed_release(monkeypatch, installed,
                                                                         docs_version):
    with pytest.raises(RuntimeError, match="names another release"):
        _shared(monkeypatch, installed, docs_version)
