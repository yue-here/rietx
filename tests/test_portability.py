"""WP-1002 — the portability rules that only a non-POSIX platform can break.

These are source guards, not behaviour tests: they parse the tree and fail on a
construct, because the failure they prevent is invisible on the platform this
package is developed on.  Both encode something measured on a Windows runner
rather than something assumed.

**Text I/O must name its encoding.**  ``Path.read_text()`` and ``open()`` use
``locale.getpreferredencoding(False)``, which is UTF-8 on macOS and Linux and
**cp1252 on Windows** (measured: the runner reports ``preferred encoding:
cp1252``, ``stdout encoding: cp1252``).  So a file this package writes as UTF-8
on one platform is read back as mojibake — or raises ``UnicodeDecodeError`` —
on another.  Six of the seven failures in the first Windows run were exactly
this, every one of them ``'charmap' codec can't decode byte 0x81``.  Python
3.15 makes UTF-8 the default and retires the problem, but the supported range
here starts at 3.11.

**CSV must be written through ``newline=""``.**  ``csv.writer`` emits ``\\r\\n``
per the spec; writing that string through text mode translates each ``\\n``
again, so every line ends ``\\r\\r\\n`` — a file with a blank line between every
row.  That was the seventh failure, and a real one: ``write_qpa_table``
produced corrupt CSV on Windows while its sibling ``write_reflection_table``,
which already opened with ``newline=""``, did not.

**A POSIX-only import is guarded or it is a collection error.**  WP-1439: the
run-recording track put a bare ``import fcntl`` at the top of
``tests/test_runs.py``, so on Windows that module did not import and its 51
cases went unrun behind a single ``error`` line.  The package had guarded the
same import at all three of its own sites, which is exactly why nothing looked
wrong.  A guarded import degrades to a skip; an unguarded one takes the file.

**A write handle names its newline.**  WP-1439 again, and the CSV rule one
case over.  ``csv.writer`` emits its own ``\r\n`` and so wants ``newline=""``;
a JSONL writer emits its own ``\n`` and wants ``newline="\n"``.  Left to text
mode, every JSONL file this package writes is CRLF on Windows and LF
everywhere else — the same events at a different size and a different
checksum, which is what ``history.jsonl`` being part of a ``.rex`` project
makes a contract question rather than a cosmetic one.  The rule is on
``open`` and not on ``write_text``: a handle is what lines are written
through, while ``write_text`` puts a whole document down in one call.  Seven
sites in the tree, all of them JSONL but the lock file.

The guards parse rather than grep because the calls that matter span lines —
the multi-line ``write_text(json.dumps({...}), encoding="utf-8")`` in
``viz/live.py`` is invisible to a line-based search, which is how one site
survived the first sweep.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TREES = ("src", "tests", "examples")

#: Calls that open a text stream and therefore need an explicit encoding.
_TEXT_IO = {"read_text", "write_text", "open"}

#: Receivers whose ``.open`` is not a text stream: ``webbrowser.open`` /
#: ``webbrowser.open_new_tab``, ``Project.open`` — which opens a *directory*
#: (WP-1005) and does its own reading through calls this guard checks
#: individually — and a ``zipfile.ZipFile``, whose ``.open`` returns **bytes**
#: whatever its mode, so ``encoding=`` there is a ``TypeError`` rather than an
#: omission (the container readers decode those bytes through
#: ``io.formats.base.decode``, which reads the member's own byte-order mark).
#: The match is on the receiver's source text, so it is a name list and will go
#: stale; it goes stale in the safe direction, since a new non-file ``.open``
#: fails this test until someone adds the row — and the ``zip`` entry is why a
#: reader names its archive handle ``zip_*``.  ``tarfile.open`` is the same case:
#: its mode (``"w:gz"``) names a compression, never a text stream.
_NOT_FILE_IO = ("webbrowser", "urllib", "request", "Project", "zip", "tarfile")

#: Standard-library modules that exist on POSIX and not on Windows.  ``fcntl``
#: is the only one this package reaches for; the rest are here because the next
#: one reached for will come from this list, and a name costs nothing until
#: somebody imports it.
_POSIX_ONLY = {"fcntl", "termios", "pwd", "grp", "pty", "tty", "resource",
               "syslog", "posix", "crypt", "spwd", "nis"}

#: Handlers that let a missing module through.  A bare ``except`` counts: it is
#: broader than it should be and it still degrades the import to a skip.
#: ``OSError`` is deliberately *not* here, tempting as it looks beside the
#: file-I/O rules above: ``ImportError`` descends from ``Exception`` and not
#: from ``OSError``, so ``except OSError`` around an import catches nothing and
#: the module still dies on collection.
_CATCHES_MISSING = {"ImportError", "ModuleNotFoundError",
                    "Exception", "BaseException"}

#: The characters a mode string is made of.  A mode is short and spelled from
#: these; a *filename* literal in the same call is neither, which is how
#: ``open("tests/data/cell.dat", "r")`` came to look like a write (its ``a``)
#: and ``open("refs.bib", "w")`` like binary (its ``b``).
_MODE_CHARS = set("rwaxbt+U")


def _python_files() -> list[Path]:
    out: list[Path] = []
    for tree in TREES:
        out.extend(sorted((ROOT / tree).rglob("*.py")))
    return out


def _mode_strings(call: ast.Call) -> list[str]:
    """The mode literals of one open call, and nothing else it was passed.

    The mode sits first in ``p.open("a")`` and second in ``open(p, "a")``, so
    both positions are read -- and then filtered to what a mode can actually
    be spelled with.  Taking every string argument instead reads the
    *filename* as a mode, in both directions: ``open("tests/data/cell.dat",
    "r")`` becomes a write on its ``a`` and ``open("refs.bib", "w")`` becomes
    binary on its ``b``, which exempts a real write handle from both of the
    rules below (WP-1439).
    """
    found = [a.value for a in call.args[:2]
             if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    found += [kw.value.value for kw in call.keywords
              if kw.arg == "mode" and isinstance(kw.value, ast.Constant)
              and isinstance(kw.value.value, str)]
    return [m for m in found if m and len(m) <= 3 and set(m) <= _MODE_CHARS]


def _is_binary_mode(call: ast.Call) -> bool:
    """True when a mode argument selects binary, where encoding is illegal."""
    return any("b" in mode for mode in _mode_strings(call))


def _text_io_calls(tree: ast.AST, source: str) -> list[tuple[ast.Call, str]]:
    """Every call that opens a text stream, with the receiver's source text."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        else:
            continue
        if name not in _TEXT_IO:
            continue
        # The receiver is only read by the two exemptions below, and
        # ast.get_source_segment re-splits the whole source on every call.
        # Taken before this filter it ran once per *attribute* call in the
        # tree rather than once per text-I/O call, which is quadratic in file
        # size and was the whole cost of this file.
        receiver = ""
        if isinstance(func, ast.Attribute):
            receiver = ast.get_source_segment(source, func.value) or ""
        # os.open returns a file descriptor, never a text stream, and rejects
        # `encoding=` outright -- so flagging it asks for an argument that
        # cannot be given.  _NOT_FILE_IO cannot express this: it substring-
        # matches the receiver, and "os" matches any receiver spelling those
        # letters, so the exemption is an exact-receiver test instead.
        # Pillow's Image.open is the same case: it returns an image and takes
        # no `encoding=` (WP-1544's notebook figure encoder reads one back).
        if name == "open" and receiver in ("os", "Image"):
            continue
        if any(bad in receiver for bad in _NOT_FILE_IO):
            continue
        if _is_binary_mode(node):
            continue
        found.append((node, receiver))
    return found


def _calls_a_csv_writer(tree: ast.AST) -> bool:
    """True when the module actually constructs a csv writer."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"writer", "DictWriter"}
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "csv"):
            return True
    return False


def test_every_text_io_call_names_its_encoding():
    """No implicit locale encoding anywhere in the tree.

    The default differs by platform, so an unnamed encoding means the package
    behaves differently on Windows than it was validated on — silently, for
    ASCII inputs, right up until a user's CIF carries an accented author name.
    """
    offenders = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        for call, _ in _text_io_calls(ast.parse(source), source):
            if not any(kw.arg == "encoding" for kw in call.keywords):
                offenders.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not offenders, (
        "text I/O without an explicit encoding= (cp1252 on Windows, UTF-8 here):\n  "
        + "\n  ".join(offenders))


#: The workflow scripts: the hooks and the skills' helpers.  They sit outside
#: the package, but their tests run on Windows.
WORKFLOW_SCRIPTS = (ROOT / ".claude" / "hooks", ROOT / ".claude" / "skills")

_SUBPROCESS = {"run", "Popen", "check_output", "check_call", "call"}


def _workflow_scripts() -> list[Path]:
    return [path for tree in WORKFLOW_SCRIPTS for path in sorted(tree.rglob("*.py"))]


def _text_mode_subprocess_calls(tree: ast.AST) -> list[ast.Call]:
    """`subprocess` calls that decode their output in the locale's encoding."""
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _SUBPROCESS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"):
            text_mode = any(
                kw.arg in ("text", "universal_newlines")
                and not (isinstance(kw.value, ast.Constant) and kw.value.value is False)
                for kw in node.keywords)
            if text_mode and not any(kw.arg == "encoding" for kw in node.keywords):
                found.append(node)
    return found


def _text_stdin_reads(tree: ast.AST, source: str) -> list[ast.Call]:
    """Reads of `sys.stdin` as text, which Windows decodes as cp1252.

    A hook payload is UTF-8 JSON, so it is read from `sys.stdin.buffer`.
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr in ("read", "readline", "readlines")
                and ast.get_source_segment(source, func.value) == "sys.stdin"):
            found.append(node)
        elif any(ast.get_source_segment(source, arg) == "sys.stdin" for arg in node.args) \
                and isinstance(func, ast.Attribute) and func.attr == "load":
            found.append(node)
    return found


def test_a_hook_decodes_what_git_and_gh_print_as_utf8():
    """A hook's text I/O names its encoding, its subprocess output included (WP-2043).

    The hooks read WP files and PR titles through git and gh, and those carry
    a status ✅ and em dashes.  `text=True` alone decoded them as cp1252 on
    Windows, where ✅ arrives as `âœ…`: `closed_wp_writes` read every closed
    WP as open, and five tests were red on four Windows nightlies.  A hook's
    payload on stdin is UTF-8 JSON too, and the skills' helpers read the same
    git and gh output.  The test-side subprocess calls are not held to this,
    because the ones that read non-ASCII output pin their own pipe
    (`test_examples._run`).
    """
    offenders = []
    for path in _workflow_scripts():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = _text_mode_subprocess_calls(tree) + _text_stdin_reads(tree, source)
        calls += [call for call, _ in _text_io_calls(tree, source)
                  if not any(kw.arg == "encoding" for kw in call.keywords)]
        offenders += [f"{path.relative_to(ROOT)}:{call.lineno}" for call in calls]
    assert not offenders, (
        "a hook decodes text in the locale's encoding (cp1252 on Windows):\n  "
        + "\n  ".join(offenders))


def test_the_hook_guard_can_actually_fail():
    """The subprocess and stdin halves of the guard above, made to fail once."""
    source = ('import subprocess\nsubprocess.run(["git"], text=True)\n'
              'subprocess.run(["git"], encoding="utf-8")\n'
              'subprocess.run(["git"], text=False)\n')
    assert [call.lineno for call in _text_mode_subprocess_calls(ast.parse(source))] == [2]
    source = ('import json, sys\njson.load(sys.stdin)\nsys.stdin.read()\n'
              'json.loads(sys.stdin.buffer.read())\n')
    assert sorted(call.lineno for call in _text_stdin_reads(ast.parse(source), source)) == [2, 3]


def test_csv_writers_open_with_newline_suppressed():
    """Anything handing csv.writer output to a file must pass newline="".

    csv.writer emits \\r\\n itself; text mode then translates the \\n again and
    every row ends \\r\\r\\n on Windows.  Measured on a real runner, not feared.
    """
    offenders = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        if "csv" not in source:
            continue
        tree = ast.parse(source)
        # a *call*, not a mention: this file and validation_matrix.py both
        # discuss csv.writer in prose, and a substring test flags them
        if not _calls_a_csv_writer(tree):
            continue
        for call, _ in _text_io_calls(tree, source):
            writes = isinstance(call.func, ast.Attribute) and call.func.attr in {
                "open", "write_text"}
            if not writes:
                continue
            # only writers matter; a read cannot double a line ending
            modes = _mode_strings(call)
            if call.func.attr == "open" and not any("w" in m or "a" in m for m in modes):
                continue
            if not any(kw.arg == "newline" for kw in call.keywords):
                offenders.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not offenders, (
        "a module that builds CSV with csv.writer opens a file without newline=\"\":\n  "
        + "\n  ".join(offenders))


def _catches_a_missing_module(handler: ast.ExceptHandler) -> bool:
    """True when this ``except`` clause lets an absent module through."""
    if handler.type is None:
        return True
    clauses = (handler.type.elts if isinstance(handler.type, ast.Tuple)
               else [handler.type])
    names = []
    for node in clauses:
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
    return any(name in _CATCHES_MISSING for name in names)


def _guarded_import_lines(tree: ast.AST) -> set[int]:
    """Line numbers of every import sitting inside a try that catches."""
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(_catches_a_missing_module(h) for h in node.handlers):
            continue
        for child in node.body:
            for inner in ast.walk(child):
                if isinstance(inner, (ast.Import, ast.ImportFrom)):
                    guarded.add(inner.lineno)
    return guarded


def _imported_roots(node: ast.AST) -> list[str]:
    """The top-level module names one import statement brings in."""
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0:
        return [(node.module or "").split(".")[0]]
    return []


def test_posix_only_imports_are_guarded():
    """A module Windows does not ship is imported inside a try, or not at all.

    Unguarded it is not one failure but the whole file: pytest reports a
    collection error and every case in it silently stops being evidence.  That
    is how ``tests/test_runs.py`` went unrun on Windows for three nights while
    the package's own three ``fcntl`` sites were guarded correctly.
    """
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        guarded = _guarded_import_lines(tree)
        for node in ast.walk(tree):
            roots = set(_imported_roots(node)) & _POSIX_ONLY
            if not roots or node.lineno in guarded:
                continue
            names = ", ".join(sorted(roots))
            offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} ({names})")
    assert not offenders, (
        "a POSIX-only import outside a try/except that catches it -- on "
        "Windows this is a collection error, not a skip:\n  "
        + "\n  ".join(offenders))


def test_every_write_handle_names_its_newline():
    """Whoever opens a handle for writing decides whose line ending it uses.

    ``newline="\\n"`` for a machine format this package reads back (all the
    JSONL), ``newline=""`` for anything going through ``csv.writer``, and an
    explicit ``newline=None`` for prose a person opens in an editor, where the
    platform's ending is the right one.  The point is that the decision is
    visible: left out it is the platform's by default, and a JSONL file then
    changes size and checksum depending on who ran the fit.

    ``write_text`` is deliberately out of scope -- it puts a whole document
    down in one call, where a handle is the thing lines go through.
    """
    offenders = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        for call, _ in _text_io_calls(ast.parse(source), source):
            name = (call.func.attr if isinstance(call.func, ast.Attribute)
                    else call.func.id)
            if name != "open":
                continue
            if not any(c in m for m in _mode_strings(call) for c in "wax"):
                continue
            if not any(kw.arg == "newline" for kw in call.keywords):
                offenders.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not offenders, (
        "a handle opened for writing without newline=, so its line ending is "
        "the platform's:\n  " + "\n  ".join(offenders))


@pytest.mark.parametrize("snippet, guard", [
    ('from pathlib import Path\nPath("x").read_text()\n', "encoding"),
    ('import csv\nimport io\nw = csv.writer(io.StringIO())\n'
     'from pathlib import Path\nPath("x").open("w")\n', "newline"),
])
def test_the_guards_can_actually_fail(snippet, guard, tmp_path):
    """A guard that cannot fail is decoration.

    Both rules are checked against source that violates them, so a refactor
    that quietly stops detecting anything fails here rather than passing
    vacuously.
    """
    tree = ast.parse(snippet)
    calls = _text_io_calls(tree, snippet)
    assert calls, "the walker found no text I/O in a snippet that is all text I/O"
    assert not any(kw.arg == guard for call, _ in calls for kw in call.keywords)


def test_the_newline_guard_reads_the_mode_and_not_the_filename():
    """A write is named by a mode, and a filename carrying one of its letters
    is not one.  Both directions were wrong before WP-1439's review: a read of
    ``cell.dat`` was a write on its ``a``, and a write to ``refs.bib`` was
    binary on its ``b``, which exempted it from every rule in this file."""
    read = ast.parse('open("tests/data/cell.dat", "r", encoding="utf-8")')
    write = ast.parse('open("refs.bib", "w", encoding="utf-8")')
    assert _mode_strings(read.body[0].value) == ["r"]
    assert _mode_strings(write.body[0].value) == ["w"]
    assert not _is_binary_mode(write.body[0].value)


def test_the_posix_import_guard_reads_what_the_handler_catches():
    """``except OSError`` is not a guard.  ``ImportError`` does not descend
    from it, so the module still fails to collect on a platform without
    ``fcntl`` -- which is the failure this rule exists to prevent."""
    caught = ast.parse("try:\n    import fcntl\nexcept ImportError:\n    pass\n")
    missed = ast.parse("try:\n    import fcntl\nexcept OSError:\n    pass\n")
    assert _guarded_import_lines(caught) == {2}
    assert _guarded_import_lines(missed) == set()
    assert not issubclass(ImportError, OSError)


def test_webbrowser_open_is_not_mistaken_for_file_io():
    """The exclusion list earns its place: `webbrowser.open(url)` is a call
    named ``open`` that must never be asked for an encoding."""
    snippet = 'import webbrowser\nwebbrowser.open("http://localhost:8000")\n'
    assert not _text_io_calls(ast.parse(snippet), snippet)


# ----------------------------------------------------------------------
# the CLI's own output
# ----------------------------------------------------------------------
#: Commands whose output carries characters cp1252 has no code point for.
#: ``skill --print`` reaches ``α`` at character 4795 of the body; ``index
#: --help`` reaches ``Å`` in argparse's own help text.  Both exited 1 on the
#: nightly's Windows runner (run 33251188429) before ``cli._utf8_output``.
_NON_ASCII_COMMANDS = (("skill", "--print"), ("index", "--help"))


def _cli_through_an_ansi_pipe(*command: str) -> subprocess.CompletedProcess[bytes]:
    """The CLI with stdout claiming cp1252 — a Windows capture, on any platform.

    ``PYTHONIOENCODING`` is the same fallback the runner takes when stdout is
    not a console, which is what kept this invisible here for a whole
    milestone.  Bytes, never ``text=True``: the decode *is* the assertion.
    """
    return subprocess.run(
        [sys.executable, "-m", "rietx.cli", *command],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        timeout=120,  # a runaway guard, not a timer (tests/CLAUDE.md)
    )


@pytest.mark.parametrize("command", _NON_ASCII_COMMANDS, ids=lambda c: " ".join(c))
def test_the_cli_writes_utf8_into_an_ansi_code_page_pipe(command):
    """A pipe that claims cp1252 gets UTF-8, not a ``UnicodeEncodeError``."""
    out = _cli_through_an_ansi_pipe(*command)
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    text = out.stdout.decode("utf-8")  # raises if the stream is not UTF-8
    assert any(ord(c) > 127 for c in text), "nothing non-ASCII survived to assert on"


def test_the_skill_body_arrives_whole_through_the_pipe():
    """``skill --print`` is documented as the way into a harness that reads no
    skills, so the pipe must carry the file rather than a rendering of it.

    This is the assertion ``errors="replace"`` would fail where an exit status
    would not: that also exits 0, and hands an agent ``K?`` for ``Kα``.
    """
    from rietx import skill as skill_module

    out = _cli_through_an_ansi_pipe("skill", "--print")
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")
    body = out.stdout.decode("utf-8").replace("\r\n", "\n")
    assert body.rstrip("\n") == skill_module.read(None).rstrip("\n")


def _cli_subprocess_calls(tree: ast.AST) -> list[ast.Call]:
    """``subprocess.run``/``Popen`` calls whose argv mentions ``rietx.cli``."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in {"run", "Popen"}):
            continue
        argv = node.args[0] if node.args else None
        if not isinstance(argv, (ast.List, ast.Tuple)):
            continue
        literals = [e.value for e in argv.elts if isinstance(e, ast.Constant)]
        if any(isinstance(v, str) and "rietx.cli" in v for v in literals):
            out.append(node)
    return out


def test_a_pipe_from_the_cli_names_utf8_rather_than_the_locale():
    """The other half of ``cli._utf8_output``, and it fails on the same platform.

    The CLI writes UTF-8 on every platform; a reader that takes ``text=True``
    decodes with ``locale.getpreferredencoding(False)``, cp1252 on Windows. The
    two disagree and the **reader** raises — measured on the nightly's Windows
    runner (run 33297474071) on the ``₁`` of ``occ₁``, whose UTF-8 lead byte
    0x81 cp1252 has no code point for.

    The producer's fix cannot close this; only the consumer's can, and there is
    no platform here on which forgetting it goes red, which is what makes it a
    source guard rather than a behaviour test.

    **Bytes are not an offender.**  A call that asks for neither ``text`` nor
    ``encoding`` gets bytes and decodes them itself, which is what
    ``_cli_through_an_ansi_pipe`` above does deliberately — there the decode is
    the assertion.  What cannot be right is asking the *pipe* to decode without
    saying with what.
    """
    offenders = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _cli_subprocess_calls(tree):
            kw = {k.arg: k.value for k in call.keywords}
            decodes = any(isinstance(kw.get(name), ast.Constant) and kw[name].value
                          for name in ("text", "universal_newlines"))
            if decodes and "encoding" not in kw:
                offenders.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert not offenders, (
        "these ask the pipe to decode the rietx CLI's output without saying "
        f"with what, so they use the locale codec: {offenders}"
    )


def test_the_cli_pipe_guard_can_actually_fail():
    """The guard above is an absence assertion (`tests/CLAUDE.md`), so prove it
    still fails on the construct it is written for."""
    snippet = ('import subprocess\n'
               'subprocess.run(["python", "-m", "rietx.cli", "skill"], text=True)\n')
    calls = _cli_subprocess_calls(ast.parse(snippet))
    assert len(calls) == 1
    names = {kw.arg for kw in calls[0].keywords}
    assert "text" in names and "encoding" not in names
