#!/usr/bin/env python3
"""SessionStart scan: surface stale session-workflow state at the next session.

Read-only but for the merge driver's git config (``ensure_merge_driver``),
stdlib-only, and deliberately independent of the project venv —
a missing or wrong-tree venv is one of the conditions it must survive to
report.  Run with ``python3`` from PATH; it imports nothing from the package,
touches no network, and always exits 0: the report is a *prompt to the
session, never a gate* (WP-1061).

What it prints: one line of repo state (worktree root, branch, ahead/behind
``origin/main`` — the local ``main`` when there is no remote — uncommitted-change
count, venv resolution), then one line per flag — another live Claude session
whose shell sits in this same tree, **a WP another live session is already
working** (``wp_claim``), a missed ``/wp-handover`` (two severities, see below),
a venv whose editable ``rietx`` pointer resolves to a different tree, any WP
whose Status glyph is in flight, and a release owed once the newest ``v*`` tag
is a week old (``release_flag``, WP-1540).  Healthy output is one or two lines.

**One session per tree** is the rule the first flag enforces, and it is the one
this repo's collisions all reduce to: sessions launched in the same checkout
share HEAD, the index, the stash and the working tree, so one session's
``checkout``, ``reset --hard`` or ``git add -A`` lands in another's work
(measured 2026-08-26, four times in one day).  Which tree a session is in is
observable — every ``claude`` process has a cwd — so the scan reports the other
sessions whose cwd resolves to this worktree, excluding the one running it, and
``/wp-start`` step 3 says what to do about it: ``EnterWorktree`` before
editing, never work a second tree from here by ``git -C``.  The gate that makes
the rule hold without being read is ``worktree_only.py``.

**One WP per session** is the same rule one rank out, and the flag after it
reports it: two sessions in two proper trees still duplicate each other's work
and collide at handover if both picked WP-1422.  The tree a session sits in is
what says which WP it is on (``wp_claim``), and the gate that makes *that* rule
hold without being read is ``worktree_create.py``, which refuses a WP another
live session already holds.

The tree scanned is the one Claude Code passes on the hook's stdin (``cwd``),
falling back to the process's own: with ``claude --worktree`` the hook's
``$CLAUDE_PROJECT_DIR`` stays on the launch checkout while the session's shell
is in the worktree, and the report has to be about the tree the session works
in.

**Two independent coverage rules, because each covers the other's hole**
(WP-1116).  *Order*: the WP file must have been touched at or after the newest
**substantive** ``WP-NNNN:`` commit — a commit that is not a merge, does not
touch this WP's own file, and touches something outside ``docs/``,
``CLAUDE.md`` and ``.claude/``.  Being SHA-ordered it sees a missed handover
within the same day, which matters because this repo routinely runs three
sessions in one (WP-1109, 2026-08-20).  *Date*: the newest handover entry must
be no older than the newest ``WP-NNNN:`` commit — day-dated, so blind to a
same-day miss, but it is the only rule that sees a session whose every commit
was ritual (a docs-only WP).

Entry dates are read in **both** sanctioned forms, the ``- **YYYY-MM-DD**``
bullet and the ``### YYYY-MM-DD`` heading that multi-session days need
(docs/wp/TEMPLATE.md, pinned by tests/test_docs_consistency.py).  Parsing only
the first is what made this scan flag two correctly-handed-over WPs on
2026-08-20, and a false alarm costs more than no alarm: it teaches the reader
to skip the one line that is ever load-bearing.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import select
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Optional

_HOOKS = str(Path(__file__).resolve().parent)  # appended, never inserted: a
if _HOOKS not in sys.path:  # loose script here must not shadow a stdlib module
    sys.path.append(_HOOKS)
import wp_claim  # noqa: E402  (sibling hook, not a package)


def host_arch() -> str:
    """The hardware's architecture, which a translated process misreports.

    ``platform.machine()`` answers for the running process, so a hook started
    under Rosetta would call an arm64 Mac x86_64; the kernel's
    ``hw.optional.arm64`` answers for the machine.
    """
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["sysctl", "-n", "hw.optional.arm64"],
                                 capture_output=True, encoding="utf-8", errors="replace", timeout=5).stdout
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        if out.strip() == "1":
            return "arm64"
    return platform.machine()


def python_request(host: str) -> str:
    """The ``uv venv --python`` request that builds a native venv on *host*.

    A bare ``3.12`` takes the newest *managed* 3.12 whatever its architecture.
    One x86_64 interpreter installed for a wheel probe (WP-1940, 2026-10-11)
    therefore made every later worktree venv on that arm64 Mac run under
    Rosetta, where the bench cases ran 1.6-2.0x slower and took a different
    evaluation path.  Naming the architecture on an arm64 Mac closes that.
    """
    if sys.platform == "darwin" and host == "arm64":
        return "cpython-3.12-macos-aarch64-none"
    return "3.12"


HOST_ARCH = host_arch()
VENV_FIX = (f'uv venv --python {python_request(HOST_ARCH)} '
            '&& uv pip install --python .venv/bin/python -e ".[dev]"')
REPAIR_HINT = "repair first (/wp-handover, repair mode)"
SHARED_HINT = "one session per tree: EnterWorktree before editing (/wp-start step 3)"
CLAIM_HINT = "pick another WP, or /wp-start step 2 to see the whole table"
# The WP index's merge driver (WP-1507).  Git reads a driver from config and
# never from the tree, so its two keys in .git/config are the scan's one write.
# The second half gives git its own conflict markers when the script declines
# a merge, or when the checkout predates the script.  The check reads only
# .git/config.  The /pr-review bench overrides the driver per command, with
# `git -c`, so nothing it does ever makes the scan rewrite .git/config.
MERGE_DRIVER = (
    "python3 .claude/hooks/wp_index.py --merge %O %A %B || git merge-file %A %O %B"
)

_WP_COMMIT_RE = re.compile(r"^WP-(\d{4}):")
_STATUS_RE = re.compile(r"Status:\s*(⬜|🔄|✅|🛑)")
# Two spellings, because the corpus and the template disagree: TEMPLATE.md
# writes "- **YYYY-MM-DD** — ...", every real WP writes "### YYYY-MM-DD — ...".
# Matching only the template made this scan report "no handover entry" for
# every WP in the repo, so an open one was flagged `repair first` however
# complete its log was (measured 2026-08-20 on WP-1109 and WP-1110).  Both
# forms are now sanctioned rather than merely tolerated — docs/wp/TEMPLATE.md
# § Handover log carries the rule and tests/test_docs_consistency.py pins it.
_ENTRY_DATE_RE = re.compile(
    r"^(?:- \*\*|#{2,4} )(\d{4}-\d{2}-\d{2})", re.MULTILINE
)
# A path that carries no code and so cannot, by itself, owe a handover.
_RITUAL_PREFIXES = ("docs/", ".claude/")
_REPAIR_GLYPHS = ("🔄", "⬜")


class Finding(NamedTuple):
    wp: str  # four-digit WP number
    glyph: Optional[str]  # Status glyph, None if the file or line is missing
    commit_date: str  # newest WP-NNNN: commit date (YYYY-MM-DD)
    entry_date: Optional[str]  # newest handover-log entry date, None if none
    severity: str  # "repair" (open WP) or "note" (closed WP / missing file)
    basis: str  # "order" (WP file older than the work) or "date" (log behind)


def _git(root: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, encoding="utf-8", errors="replace", timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.rstrip("\n") if proc.returncode == 0 else None


def repo_line(root: Path) -> str:
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    # origin/main when there is one: the local ``main`` is whatever a session
    # last fetched into it, and in a checkout where every branch is cut from
    # origin/main it sat 91 commits stale on 2026-08-26, reporting a merged
    # branch as "ahead 90".
    base = "main"
    if _git(root, "rev-parse", "--verify", "-q", "origin/main") is not None:
        base = "origin/main"
    if branch == "main":
        position = "on main"
    else:
        ahead = _git(root, "rev-list", "--count", f"{base}..HEAD")
        behind = _git(root, "rev-list", "--count", f"HEAD..{base}")
        if ahead is None or behind is None:
            position = "no local main ref"
        else:
            position = f"ahead {ahead} / behind {behind} vs {base}"
            if ahead == "0":
                position += " · merged"  # /wp-start step 3: branch afresh
    status = _git(root, "status", "--porcelain")
    n_dirty = len(status.splitlines()) if status else 0
    dirty = "clean" if n_dirty == 0 else f"{n_dirty} uncommitted"
    return f"{root} @ {branch} · {position} · {dirty}"


# A release is cut weekly, and at once for a P1 fix (ROADMAP rule 6, WP-1540).
RELEASE_DAYS = 7


def release_flag(root: Path, today: Optional[dt.date] = None) -> Optional[str]:
    """Say a release is owed once the newest ``v*`` tag is a week old.

    A rule nobody is reminded of is the rule that let 268 merges wait behind
    one late milestone, so the weekly cut is read off the tags here rather than
    remembered.  The P1 half has no date to read and stays /wp-handover's.
    """
    tag = _git(root, "for-each-ref", "--sort=-creatordate", "--count=1",
               "--format=%(refname:short) %(creatordate:short)", "refs/tags/v*")
    if not tag:
        return None
    name, _, day = tag.partition(" ")
    try:
        age = ((today or dt.date.today()) - dt.date.fromisoformat(day)).days
    except ValueError:
        return None
    if age < RELEASE_DAYS:
        return None
    base = "origin/main"
    if _git(root, "rev-parse", "--verify", "-q", base) is None:
        base = "main"
    merges = _git(root, "rev-list", "--count", "--merges", f"{name}..{base}")
    if merges in (None, "0"):
        return None
    return (f"release owed: {name} is {age} days old, {merges} merges since "
            f"(weekly, ROADMAP rule 6; docs/RELEASING.md)")


class Session(NamedTuple):
    pid: int
    age: str  # ``ps`` etime, e.g. ``05-03:56:23``
    cwd: str


def _run(*args: str) -> Optional[str]:
    try:
        proc = subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace", timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _cwd_of(pid: int) -> Optional[str]:
    try:
        return os.readlink(f"/proc/{pid}/cwd")  # Linux
    except OSError:
        pass
    out = _run("lsof", "-a", "-d", "cwd", "-p", str(pid), "-Fn") or ""  # macOS
    for line in out.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def _session_rows(ps_out: str) -> list[tuple[int, str]]:
    """(pid, etime) per ``claude`` session in ``ps -axwwo pid=,etime=,args=``.

    Sessions, not helpers: a session runs ``claude --bg-pty-host …`` children
    for its background shells, and one of those sat in this checkout for five
    days after its session was gone (pid 48273, 2026-08-26).  Reporting it as
    a session would teach the reader to ignore the line.
    """
    rows = []
    for line in ps_out.splitlines():
        parts = line.split(None, 2)
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        argv = parts[2].split()
        if os.path.basename(argv[0]) != "claude" or "--bg-pty-host" in argv:
            continue
        rows.append((int(parts[0]), parts[1]))
    return rows


def live_sessions() -> list[Session]:
    """Every ``claude`` session on this machine, with its shell's cwd."""
    out = _run("ps", "-axwwo", "pid=,etime=,args=") or ""
    sessions = []
    for pid, age in _session_rows(out):
        cwd = _cwd_of(pid)
        if cwd is not None:
            sessions.append(Session(pid, age, cwd))
    return sessions


def _ancestors() -> set[int]:
    """This process's ancestry, so the session running the scan is not reported.

    Plus ``CLAUDE_PID``, which the Bash tool sets: run by hand from a session
    (``/wp-handover`` step 10) the shell's parent is that session's process, and
    the walk reaches it too, but the variable says so without depending on how
    the tool spawns its shell.
    """
    own = os.environ.get("CLAUDE_PID", "")
    seen: set[int] = {int(own)} if own.isdigit() else set()
    pid = os.getpid()
    for _ in range(32):
        out = _run("ps", "-o", "ppid=", "-p", str(pid))
        if not out or not out.strip().isdigit():
            break
        pid = int(out.strip())
        if pid <= 1:
            break
        seen.add(pid)
    return seen


def worktree_roots(root: Path) -> list[Path]:
    out = _git(root, "worktree", "list", "--porcelain") or ""
    roots = [Path(line[9:]) for line in out.splitlines() if line.startswith("worktree ")]
    return roots or [root]


def sessions_sharing(
    root: Path, sessions: list[Session], roots: list[Path], exclude: set[int]
) -> list[Session]:
    """The sessions whose cwd belongs to *this* worktree.

    Belongs, not merely lies under: ``.claude/worktrees/pr-bench`` is inside
    the main checkout's directory and is a different tree, so a cwd is
    assigned to the deepest registered worktree containing it.
    """
    resolved = [r.resolve() for r in roots]
    mine = root.resolve()
    hits = []
    for s in sessions:
        if s.pid in exclude:
            continue
        cwd = Path(s.cwd).resolve()
        owners = [r for r in resolved if cwd == r or r in cwd.parents]
        if owners and max(owners, key=lambda r: len(r.parts)) == mine:
            hits.append(s)
    return hits


def venv_flag(root: Path) -> Optional[str]:
    """Check that .venv's editable rietx pointer resolves to *this* tree.

    Without importing anything: uv writes ``_editable_impl_rietx.pth``
    containing the bare src path; setuptools writes ``__editable__*.pth`` plus
    a ``__editable__*finder.py`` holding quoted paths.  Either way the target
    must live under this worktree's root, or the venv measures another tree.
    """
    venv = root / ".venv"
    if not venv.is_dir():
        return f"no .venv in this tree — fix: {VENV_FIX}"
    targets: list[str] = []
    for sp in venv.glob("lib/python*/site-packages"):
        for pth in sp.glob("*.pth"):
            if "rietx" not in pth.name:
                continue
            for line in pth.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("import"):
                    targets.append(line)
        for finder in sp.glob("__editable__*rietx*.py"):
            text = finder.read_text(encoding="utf-8", errors="replace")
            targets.extend(m.group(1) for m in re.finditer(r"['\"](/[^'\"]+)['\"]", text))
    if not targets:
        return f"no editable rietx pointer in .venv — fix: {VENV_FIX}"
    resolved_root = root.resolve()
    for target in targets:
        try:
            if Path(target).resolve().is_relative_to(resolved_root):
                return arch_flag(venv, HOST_ARCH)
        except OSError:
            continue
    return f"venv resolves rietx to {targets[0]}, not this tree — fix: {VENV_FIX}"


_MACHO_CPU = {0x01000007: "x86_64", 0x0100000C: "arm64"}


def macho_arch(path: Path) -> Optional[str]:
    """The CPU a thin 64-bit Mach-O binary is built for.

    ``None`` for anything else, a universal binary included, since that one
    runs natively on either machine.  Eight bytes of header answer it without
    starting the interpreter, which a translated one makes slow.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(8)
    except OSError:
        return None
    if len(head) < 8 or head[:4] != b"\xcf\xfa\xed\xfe":  # MH_MAGIC_64, little-endian
        return None
    return _MACHO_CPU.get(int.from_bytes(head[4:8], "little"))


def arch_flag(venv: Path, host: str) -> Optional[str]:
    """Flag a venv whose interpreter runs translated on *host*.

    The pointer check above cannot see this: a Rosetta venv imports the right
    tree and passes every test, only slower and down a different evaluation
    path, so every timing taken in it is wrong (``python_request``).
    """
    built = macho_arch((venv / "bin" / "python").resolve())
    if built is None or built == host:
        return None
    return (f"venv runs {built} Python on this {host} machine, translated — fix: "
            f"{VENV_FIX.replace('uv venv ', 'uv venv --clear ', 1)}")


class Commit(NamedTuple):
    sha: str
    date: str  # YYYY-MM-DD, author date
    wp: str  # four-digit WP number from the ``WP-NNNN:`` subject prefix, else ""
    is_merge: bool
    files: tuple[str, ...]


# The handover scan reads the commits of the WINDOW_DAYS before HEAD's own
# commit date.  It read the last 50 commits until 2026-10-10, when main took 88
# commits in one day.  Two WPs whose logs were a day behind then sat 99 and 101
# commits back, and the scan was quiet.  A window in days keeps its reach as
# the commit rate grows.  It ends at HEAD rather than today so that a dormant
# branch is scanned over its own last fortnight, and so are the test fixtures.
WINDOW_DAYS = 14


def window_commits(root: Path, days: int = WINDOW_DAYS) -> list[Commit]:
    """Every commit of the ``days`` before HEAD's commit, newest first, with files.

    One ``git log`` pass, because this runs before every session.  A merge
    lists no files.
    """
    head = _git(root, "log", "-1", "--format=%cs")
    if head is None:
        return []
    since = dt.date.fromisoformat(head) - dt.timedelta(days=days)
    out = _git(
        root, "log", f"--since={since.isoformat()}", "--name-only",
        "--format=%x00%H\t%as\t%P\t%s",
    )
    commits: list[Commit] = []
    for chunk in (out or "").split("\x00")[1:]:
        header, _, body = chunk.partition("\n")
        parts = header.split("\t", 3)
        if len(parts) != 4:
            continue
        sha, date, parents, subject = parts
        m = _WP_COMMIT_RE.match(subject)
        files = tuple(f for f in body.split("\n") if f.strip())
        commits.append(
            Commit(sha, date, m.group(1) if m else "", len(parents.split()) > 1, files)
        )
    return commits


def wp_commits(root: Path, days: int = WINDOW_DAYS) -> list[Commit]:
    """The window's ``WP-NNNN:``-prefixed commits, newest first."""
    return [c for c in window_commits(root, days) if c.wp]


def _is_ritual(commit: Commit) -> bool:
    """True if this commit cannot, by itself, owe a handover entry.

    A merge carries no new work; a commit touching the WP's own file *is* the
    record being looked for; and a commit confined to docs, a CLAUDE.md or
    ``.claude/`` is the rest of the ritual (protocol steps 4-7), which lands in
    its own commits often enough that requiring the WP file to come last would
    flag three healthy WPs on this repo's own history.
    """
    if commit.is_merge:
        return True
    own = re.compile(rf"docs/wp/{commit.wp}-.*\.md$")
    if any(own.match(f) for f in commit.files):
        return True
    return all(
        f.startswith(_RITUAL_PREFIXES) or f.endswith("CLAUDE.md") for f in commit.files
    )


def wp_file_state(root: Path, wp: str) -> tuple[Optional[Path], Optional[str], Optional[str]]:
    """(path, Status glyph, newest handover-entry date) for docs/wp/NNNN-*.md."""
    matches = sorted((root / "docs" / "wp").glob(f"{wp}-*.md"))
    if not matches:
        return None, None, None
    text = matches[0].read_text(encoding="utf-8", errors="replace")
    m = _STATUS_RE.search(text)
    glyph = m.group(1) if m else None
    _, sep, log = text.partition("\n## Handover log")
    # bounded at the next H2: several WPs carry ``## References`` after it
    log = re.split(r"^## ", log, maxsplit=1, flags=re.MULTILINE)[0] if sep else ""
    dates = _ENTRY_DATE_RE.findall(log)
    return matches[0], glyph, max(dates) if dates else None


def handover_findings(root: Path, days: int = WINDOW_DAYS) -> list[Finding]:
    """Every WP whose handover log is behind its commits, by either rule."""
    window = window_commits(root, days)
    newest_commit: dict[str, Commit] = {}
    newest_work: dict[str, Commit] = {}
    for c in window:  # newest first
        if not c.wp:
            continue
        newest_commit.setdefault(c.wp, c)
        if not _is_ritual(c):
            newest_work.setdefault(c.wp, c)
    # Position of each sha in the window, so "the WP file was touched at or
    # after this commit" is a comparison rather than an ancestry walk.  A sha
    # outside the window ranks as older than everything in it, which is the
    # honest reading: the file has not been touched within the window.  The
    # newest touch of each file comes off the same pass, because a
    # ``git log -1 -- <file>`` per WP grows with the window.
    rank = {c.sha: i for i, c in enumerate(window)}
    OLDEST = len(window) + 1
    last_touch: dict[str, str] = {}
    for c in window:
        for f in c.files:
            last_touch.setdefault(f, c.sha)

    findings = []
    for wp, commit in sorted(newest_commit.items()):
        path, glyph, entry_date = wp_file_state(root, wp)
        if path is None:
            findings.append(Finding(wp, None, commit.date, None, "note", "date"))
            continue
        basis = None
        work = newest_work.get(wp)
        if work is not None:
            rel = path.relative_to(root).as_posix()
            touched = last_touch.get(rel, "")
            if rank.get(touched, OLDEST) > rank.get(work.sha, OLDEST):
                basis, commit = "order", work
        if basis is None:
            if entry_date is not None and entry_date >= commit.date:
                continue
            basis = "date"
        severity = "repair" if glyph in _REPAIR_GLYPHS else "note"
        findings.append(Finding(wp, glyph, commit.date, entry_date, severity, basis))
    return findings


def ensure_merge_driver(root: Path) -> None:
    """Point `merge=wpindex` (.gitattributes) at the index's row merge."""
    if _git(root, "config", "--local", "--get", "merge.wpindex.driver") != MERGE_DRIVER:
        _git(root, "config", "merge.wpindex.name", "the WP index, merged row by row")
        _git(root, "config", "merge.wpindex.driver", MERGE_DRIVER)


def in_flight_wps(root: Path) -> list[str]:
    flying = []
    for path in sorted((root / "docs" / "wp").glob("[0-9]*.md")):
        m = _STATUS_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        if m and m.group(1) == "🔄":
            flying.append(path.name[:4])
    return flying


def claim_lines(
    root: Path, sessions: Optional[list[Session]] = None, exclude: Optional[set[int]] = None
) -> list[str]:
    """What other live sessions are working, so this one does not pick it too.

    Reported, never refused: the block belongs at ``EnterWorktree``, where the
    trigger is sharpest and the cost of proceeding is a whole duplicated
    session (``worktree_create.py``).  Here it is a prompt, like every other
    line this scan prints (WP-1061).

    Takes the process scan rather than repeating it.  ``live_sessions`` is an
    ``lsof`` per ``claude`` process — 0.111 s of a 0.424 s scan on this desktop,
    2026-09-15 — and ``render`` has already paid for it.

    Quiet in the ordinary case.  Only a WP a live session in *another* tree is
    working prints, so a machine running one session prints nothing, and the
    finished-but-kept trees this repo is full of print nothing either: four of
    six on 2026-09-15 had no session in them, which is what
    ``wp_claim.held_elsewhere`` drops.  No glyph is read here — every row that
    survives it is *held*, and held outranks closed.
    """
    sessions = live_sessions() if sessions is None else sessions
    exclude = _ancestors() if exclude is None else exclude
    trees = wp_claim.worktree_branches(root)
    main = wp_claim.main_checkout(trees)
    holders = wp_claim.occupancy(trees, sessions, exclude, wp_claim.read_claims(root), main)
    rows = wp_claim.held_elsewhere(holders, root)
    lines = [f"⚠ {wp_claim.describe(h, main)} — {CLAIM_HINT}" for h in rows]
    lines += [
        f"⚠ WP-{wp} is live in more than one tree — the clash this scan exists to catch"
        for wp in wp_claim.clashes(holders)
    ]
    return lines


def render(root: Path) -> str:
    lines = [repo_line(root)]
    vflag = venv_flag(root)
    if vflag is None:
        lines[0] += " · venv ok"
    else:
        lines.append(f"⚠ {vflag}")
    sessions, excl = live_sessions(), _ancestors()  # one process scan, two flags
    for s in sessions_sharing(root, sessions, worktree_roots(root), excl):
        lines.append(
            f"⚠ another claude session is in this tree (pid {s.pid}, up {s.age}) — {SHARED_HINT}"
        )
    lines.extend(claim_lines(root, sessions, excl))
    for f in handover_findings(root):
        if f.basis == "order":
            entry = "WP file not touched since"
        elif f.entry_date:
            entry = f"last handover entry {f.entry_date}"
        else:
            entry = "no handover entry"
        if f.glyph is None:
            lines.append(f"note: WP-{f.wp} commits to {f.commit_date} but no docs/wp/{f.wp}-*.md")
        elif f.severity == "repair":
            lines.append(
                f"⚠ WP-{f.wp} ({f.glyph}): commits to {f.commit_date}, {entry} — {REPAIR_HINT}"
            )
        else:
            lines.append(
                f"note: WP-{f.wp} ({f.glyph}) post-close commits not in the log "
                f"(commits to {f.commit_date}, {entry})"
            )
    owed = release_flag(root)
    if owed:
        lines.append(f"⚠ {owed}")
    flying = in_flight_wps(root)
    if flying:
        lines.append("in flight: " + ", ".join(f"WP-{wp}" for wp in flying))
    return "\n".join(lines)


def hook_cwd() -> Optional[Path]:
    """The ``cwd`` Claude Code passes a hook on stdin, if this is a hook run.

    Run by hand (``/wp-handover`` step 10) stdin is a terminal or an idle pipe,
    so a bounded ``select`` stands in for "was anything sent": nothing within
    the window means no hook payload, never a hang.
    """
    try:
        if sys.stdin.isatty() or not select.select([sys.stdin], [], [], 0.2)[0]:
            return None
        text = sys.stdin.buffer.read().decode("utf-8", "replace").strip()
        cwd = json.loads(text).get("cwd") if text else None
        return Path(cwd) if cwd else None
    except Exception:
        return None


def main() -> int:
    root = _git(hook_cwd() or Path.cwd(), "rev-parse", "--show-toplevel")
    if root is None:
        print("session-start scan: not inside a git repository")
        return 0
    try:
        ensure_merge_driver(Path(root))
        print(render(Path(root)))
    except Exception as exc:  # a broken scan must inform, never block the session
        print(f"session-start scan failed ({exc.__class__.__name__}: {exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
