"""The SessionStart workflow scan (.claude/hooks/session_start.py, WP-1061).

WP-1116 gave it its second coverage rule (commit order, which sees a miss
inside the same day) and taught it the heading entry form; the tests below
carry the measurement that shaped each.

The hook is stdlib-only and lives outside the package on purpose (it must not
depend on the venv it checks), so it is loaded here by file path and its scan
functions are driven directly against tmp_path git fixtures — no subprocess
output parsing.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / ".claude" / "hooks" / "session_start.py"

_spec = importlib.util.spec_from_file_location("wp_session_start_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _git(cwd: Path, *args: str, date: str | None = None) -> None:
    env = os.environ.copy()
    if date is not None:
        env["GIT_AUTHOR_DATE"] = f"{date}T12:00:00"
        env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00"
    subprocess.run(
        ["git", "-c", "user.email=wp@test", "-c", "user.name=wp",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd, env=env, check=True, capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs" / "wp").mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    return root


def write_wp(
    root: Path, num: str, glyph: str, entry_dates: list[str], with_log: bool = True
) -> None:
    text = f"# WP-{num} — fixture\n\nMilestone: v1.0 · Status: {glyph}\n\n## Goal\n\nx.\n"
    if with_log:
        text += "\n## Handover log\n\n"
        text += "".join(f"- **{d}** — an entry.\n" for d in entry_dates)
    (root / "docs" / "wp" / f"{num}-fixture.md").write_text(text, encoding="utf-8")


def commit_wp(root: Path, num: str, date: str, code: bool = False) -> None:
    """Commit the tree as one ``WP-NNNN:`` commit.

    ``code=True`` also writes a source file, which is what makes the commit
    *substantive* — a commit touching only the WP file, docs or ``.claude/`` is
    ritual and owes no handover of its own (hook ``_is_ritual``).
    """
    if code:
        src = root / "src" / "fixture.py"
        src.parent.mkdir(exist_ok=True)
        src.write_text(f"# {num} {date}\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"WP-{num}: fixture work", date=date)


def make_venv(root: Path, target: Path) -> None:
    sp = root / ".venv" / "lib" / "python3.12" / "site-packages"
    sp.mkdir(parents=True)
    (sp / "_editable_impl_rietx.pth").write_text(f"{target}\n", encoding="utf-8")


def test_healthy_state_renders_one_line(repo: Path) -> None:
    write_wp(repo, "9001", "✅ 2026-08-02 — done", ["2026-08-02"])
    commit_wp(repo, "9001", "2026-08-01")
    make_venv(repo, repo / "src")
    assert hook.handover_findings(repo) == []
    out = hook.render(repo)
    assert len(out.splitlines()) == 1
    assert "venv ok" in out
    assert "⚠" not in out


def test_open_wp_with_later_commit_flags_repair(repo: Path) -> None:
    write_wp(repo, "9002", "🔄 2026-08-01 — in flight", ["2026-08-01"])
    commit_wp(repo, "9002", "2026-08-03")
    (finding,) = hook.handover_findings(repo)
    assert finding.severity == "repair"
    assert (finding.wp, finding.glyph) == ("9002", "🔄")
    assert (finding.commit_date, finding.entry_date) == ("2026-08-03", "2026-08-01")
    out = hook.render(repo)
    assert hook.REPAIR_HINT in out
    assert hook.in_flight_wps(repo) == ["9002"]
    assert "in flight: WP-9002" in out


def test_open_wp_with_no_handover_log_flags_repair(repo: Path) -> None:
    # the shape the first live run found on main: ⬜ WP, commits, no log section
    write_wp(repo, "9003", "⬜", [], with_log=False)
    commit_wp(repo, "9003", "2026-08-03")
    (finding,) = hook.handover_findings(repo)
    assert finding.severity == "repair"
    assert finding.entry_date is None
    assert "no handover entry" in hook.render(repo)


def test_closed_wp_with_later_commit_is_soft_note(repo: Path) -> None:
    write_wp(repo, "9004", "✅ 2026-08-01 — shipped", ["2026-08-01"])
    commit_wp(repo, "9004", "2026-08-03")
    (finding,) = hook.handover_findings(repo)
    assert finding.severity == "note"
    out = hook.render(repo)
    assert "post-close commits not in the log" in out
    assert hook.REPAIR_HINT not in out


def test_same_day_miss_is_caught_by_commit_order(repo: Path) -> None:
    """The pre-WP-1116 blind spot: three sessions in one day is this repo's
    normal cadence (WP-1109, 2026-08-20), so a day-dated rule could only catch
    a miss that survived past midnight.  Order catches it inside the day."""
    write_wp(repo, "9005", "🔄 2026-08-03 — in flight", ["2026-08-03"])
    commit_wp(repo, "9005", "2026-08-03")  # the handover: touches the WP file
    commit_wp(repo, "9005", "2026-08-03", code=True)  # then work, un-handed-over
    (finding,) = hook.handover_findings(repo)
    assert (finding.severity, finding.basis) == ("repair", "order")
    assert finding.entry_date == "2026-08-03"  # same day, and still flagged
    assert "WP file not touched since" in hook.render(repo)


def test_ritual_commits_after_the_handover_do_not_flag(repo: Path) -> None:
    """The handover ritual spans several commits — a CLAUDE.md rule, the
    ROADMAP sync, a merge — and they land *after* the WP file's own edit.
    Requiring the WP file to come last flagged three healthy WPs on this
    repo's history (1016, 1059, 1078)."""
    write_wp(repo, "9006", "✅ 2026-08-03 — shipped", ["2026-08-03"])
    commit_wp(repo, "9006", "2026-08-03", code=True)
    write_wp(repo, "9006", "✅ 2026-08-03 — shipped", ["2026-08-03", "2026-08-03"])
    commit_wp(repo, "9006", "2026-08-03")  # the handover entry
    (repo / "CLAUDE.md").write_text("a standing rule.\n", encoding="utf-8")
    commit_wp(repo, "9006", "2026-08-03")  # protocol step 6, its own commit
    assert hook.handover_findings(repo) == []


def test_heading_entries_count_as_entries(repo: Path) -> None:
    """A multi-session day needs a per-session heading, which a date bullet
    cannot express.  Reading only bullets is what made this scan flag WP-1109
    and WP-1110 on 2026-08-20 when both had been handed over."""
    path = repo / "docs" / "wp" / "9007-fixture.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# WP-9007 — fixture\n\nMilestone: v1.1 · Status: 🔄 2026-08-03 — x\n\n"
        "## Handover log\n\n"
        "### 2026-08-03 (second session) — more\n\nbody.\n\n"
        "### 2026-08-03 — first\n\nbody.\n",
        encoding="utf-8",
    )
    commit_wp(repo, "9007", "2026-08-03")
    assert hook.wp_file_state(repo, "9007")[2] == "2026-08-03"
    assert hook.handover_findings(repo) == []


def test_the_window_is_days_so_a_busy_day_cannot_hide_a_miss(repo: Path) -> None:
    """The scan read the last 50 commits until 2026-10-10, when main took 88 in
    one day and two WPs a day behind sat 99 and 101 commits back, unflagged.
    The window now ends at HEAD's date and reaches back ``WINDOW_DAYS``."""
    write_wp(repo, "9009", "🔄 2026-08-01 — in flight", ["2026-08-01"])
    commit_wp(repo, "9009", "2026-08-02", code=True)
    for i in range(60):
        _git(repo, "commit", "-q", "--allow-empty", "-m", f"other work {i}",
             date="2026-08-03")
    (finding,) = hook.handover_findings(repo)
    assert (finding.wp, finding.basis) == ("9009", "date")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "a fortnight on",
         date="2026-08-20")
    assert hook.handover_findings(repo) == []


def test_repo_line_measures_against_origin_main(repo: Path, tmp_path: Path) -> None:
    """The local ``main`` is whatever was last fetched into it; on 2026-08-26 it
    sat 91 commits stale and the scan called a merged branch "ahead 90"."""
    write_wp(repo, "9008", "✅ 2026-08-02 — done", ["2026-08-02"])
    commit_wp(repo, "9008", "2026-08-01")
    _git(repo, "init", "-q", "--bare", str(tmp_path / "remote.git"))
    _git(repo, "remote", "add", "origin", str(tmp_path / "remote.git"))
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "checkout", "-q", "-b", "feature")
    make_venv(repo, repo / "src")
    assert "ahead 0 / behind 0 vs origin/main · merged" in hook.repo_line(repo)
    commit_wp(repo, "9008", "2026-08-02", code=True)
    line = hook.repo_line(repo)
    assert "ahead 1 / behind 0 vs origin/main" in line and "merged" not in line


def test_sessions_sharing_assigns_a_cwd_to_its_deepest_worktree(tmp_path: Path) -> None:
    """``.claude/worktrees/pr-bench`` lies *under* the main checkout and is a
    different tree, so containment alone would report a bench session to a
    main-checkout session and the reverse.  Deepest registered root wins."""
    main = tmp_path / "repo"
    bench = main / ".claude" / "worktrees" / "pr-bench"
    bench.mkdir(parents=True)
    sessions = [
        hook.Session(1, "05-04:02:33", str(main)),
        hook.Session(2, "00:10", str(bench)),
        hook.Session(3, "00:05", str(main / "src")),  # below the root: still its tree
        hook.Session(4, "00:01", str(tmp_path / "elsewhere")),
        hook.Session(5, "00:01", str(main)),  # the session running the scan
    ]
    roots = [main, bench]
    assert [s.pid for s in hook.sessions_sharing(main, sessions, roots, {5})] == [1, 3]
    assert [s.pid for s in hook.sessions_sharing(bench, sessions, roots, set())] == [2]
    out = hook.SHARED_HINT
    assert "one session per tree" in out


def test_session_rows_skip_the_pty_host_helpers() -> None:
    """A session's background shells run as ``claude --bg-pty-host``; one such
    orphan sat in the checkout for five days (pid 48273, 2026-08-26)."""
    ps = (
        "15964 11:44 /Users/yue/.local/share/claude/ClaudeCode.app/Contents/MacOS/claude"
        " --bg-pty-host /tmp/cc-x\n"
        "45077 06:46:12 claude\n"
        "17432 05:10 claude --model sonnet\n"
        "  999 00:01 /usr/bin/python3 claude-something\n"
    )
    assert hook._session_rows(ps) == [(45077, "06:46:12"), (17432, "05:10")]


def test_hook_cwd_without_a_payload_is_none() -> None:
    """Under pytest stdin is not a hook pipe; the read must answer None, and
    quickly, rather than raise or wait."""
    assert hook.hook_cwd() is None


# --------------------------------------------------------------------------- #
# The worktree-only gate (.claude/hooks/worktree_only.py): the main checkout is
# read-only for a session.
# --------------------------------------------------------------------------- #

_gate_spec = importlib.util.spec_from_file_location(
    "worktree_only_hook", ROOT / ".claude" / "hooks" / "worktree_only.py"
)
gate = importlib.util.module_from_spec(_gate_spec)
_gate_spec.loader.exec_module(gate)


@pytest.fixture
def repo_with_worktree(repo: Path) -> tuple[Path, Path]:
    (repo / "README").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    wt = repo / ".claude" / "worktrees" / "wp9001"
    _git(repo, "worktree", "add", "-q", "-b", "wp9001", str(wt))
    return repo, wt


def _edit(path: Path) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}


def _bash(command: str, cwd: Path) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}


def test_gate_refuses_edits_in_the_main_checkout_only(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    main, wt = repo_with_worktree
    assert gate.refusal(_edit(main / "src" / "new.py")) is not None  # dir need not exist
    assert gate.refusal(_edit(main / "README")) is not None
    assert gate.refusal(_edit(wt / "README")) is None  # a worktree under the checkout
    assert gate.refusal(_edit(tmp_path / "elsewhere" / "note.md")) is None  # no repo
    assert gate.refusal({"tool_name": "Read", "tool_input": {"file_path": str(main / "README")}}) is None


def test_gate_refuses_head_moving_git_in_the_main_checkout_only(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    main, wt = repo_with_worktree
    assert gate.refusal(_bash("git add -A && git commit -m x", main)) is not None
    assert gate.refusal(_bash("git checkout -b feature", main)) is not None
    assert gate.refusal(_bash("git stash push -u", main)) is not None
    assert gate.refusal(_bash("git log --oneline -3 && gh pr list", main)) is None
    assert gate.refusal(_bash("git fetch origin main && git worktree list", main)) is None
    assert gate.refusal(_bash("git commit -m x", wt)) is None
    # addressed at another tree by -C: that tree's business, not this gate's
    assert gate.refusal(_bash(f"git -C {wt} reset --hard origin/main", main)) is None


def test_gate_reason_names_the_fix(repo_with_worktree: tuple[Path, Path]) -> None:
    main, _ = repo_with_worktree
    reason = gate.refusal(_edit(main / "README"))
    assert "EnterWorktree" in reason and "claude -w" in reason


def test_gate_guards_this_checkout_and_not_another_repository(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    """WP-1410: the gate exists because sessions share ONE checkout's tree.

    Before scoping it refused any repository's main checkout, which caught auto
    memory the moment ``~/.claude/projects/<slug>/memory`` was symlinked into a
    configuration repo, and caught every unrelated clone besides. The session's
    own checkout must stay refused; the rest are not this gate's business.
    """
    main, _ = repo_with_worktree
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    (other / "README").write_text("x\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "init")

    # auto memory, as it is once linked into a repo shared between machines
    memory = tmp_path / "dotclaude" / "projects" / "-main"
    memory.mkdir(parents=True)
    (memory / "memory").symlink_to(other / "notes")
    (other / "notes").mkdir()

    def edit_from_session(path: Path) -> dict:
        return {"tool_name": "Edit", "tool_input": {"file_path": str(path)},
                "cwd": str(main)}

    assert gate.refusal(edit_from_session(main / "README")) is not None
    assert gate.refusal(edit_from_session(memory / "memory" / "note.md")) is None
    assert gate.refusal(edit_from_session(other / "README")) is None


def test_gate_without_a_cwd_guards_every_checkout(
    repo_with_worktree: tuple[Path, Path], tmp_path: Path
) -> None:
    """No ``cwd`` is no claim about the session, so the gate fails closed.

    Scoping reads the payload's ``cwd`` and nothing else. ``CLAUDE_PROJECT_DIR``
    describes the process rather than the call, so under a test harness it named
    a repository the payload never mentioned and allowed an edit that should
    have been refused.

    *Every* checkout, which is what fails closed means: the second repository
    below is the assertion the name makes, and without it a fallback flipped to
    "allow when the scope is unknown" would leave this test green.
    """
    main, wt = repo_with_worktree
    other = tmp_path / "another"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    (other / "README").write_text("x\n", encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "init")

    assert gate.refusal(_edit(main / "README")) is not None
    assert gate.refusal(_edit(other / "README")) is not None
    assert gate.refusal(_edit(wt / "README")) is None


def test_gate_fail_open_announces_itself() -> None:
    """A gate disabled by an internal error must not look like a working one.

    The first draft of WP-1410's scoping referenced an unimported ``os``; every
    case passed as allowed, the main checkout included, and nothing said so. The
    fail-open stays, because a bricked session costs more than a missed refusal.
    Reached here as a subprocess fed a payload that raises, which is how Claude
    Code reaches it.

    The exit code is the whole message. A ``PreToolUse`` hook's stderr reaches
    the session only on a non-zero, non-2 exit, which Claude Code renders as a
    hook error and runs the tool anyway; on exit 0 the line goes to the debug
    log and announces nothing. 2 would block, which is not fail-open.
    """
    proc = subprocess.run(
        [sys.executable, str(ROOT / ".claude" / "hooks" / "worktree_only.py")],
        input="not json", text=True, capture_output=True,
    )
    assert proc.returncode != 2, "must still fail open"
    assert proc.returncode != 0, "exit 0 sends stderr to the debug log, not the session"
    assert "gate disabled by" in proc.stderr


def test_venv_pointer_resolution(repo: Path, tmp_path: Path) -> None:
    assert "no .venv" in hook.venv_flag(repo)
    make_venv(repo, tmp_path / "other-tree" / "src")
    flag = hook.venv_flag(repo)
    assert "not this tree" in flag
    assert hook.VENV_FIX in flag  # the fix is printed verbatim
    (
        repo / ".venv" / "lib" / "python3.12" / "site-packages"
        / "_editable_impl_rietx.pth"
    ).write_text(f"{repo / 'src'}\n", encoding="utf-8")
    assert hook.venv_flag(repo) is None


def _fake_python(venv: Path, cpu: int | None) -> None:
    """A stand-in interpreter: a 64-bit Mach-O header naming *cpu*, or a fat one."""
    (venv / "bin").mkdir(parents=True, exist_ok=True)
    head = (b"\xca\xfe\xba\xbe\x00\x00\x00\x02" if cpu is None
            else b"\xcf\xfa\xed\xfe" + cpu.to_bytes(4, "little"))
    (venv / "bin" / "python").write_bytes(head + bytes(24))


def test_a_translated_venv_is_flagged_with_a_native_fix(tmp_path: Path) -> None:
    """A Rosetta venv imports the right tree and passes every test, only slower
    and down another evaluation path (WP-1940's probe interpreter, 2026-10-11),
    so the pointer check cannot see it and the header check must."""
    venv = tmp_path / ".venv"
    _fake_python(venv, 0x01000007)  # CPU_TYPE_X86_64
    assert hook.macho_arch(venv / "bin" / "python") == "x86_64"
    flag = hook.arch_flag(venv, "arm64")
    assert "x86_64" in flag and "uv venv --clear --python" in flag
    assert hook.arch_flag(venv, "x86_64") is None  # native on an Intel Mac
    _fake_python(venv, 0x0100000C)  # CPU_TYPE_ARM64
    assert hook.arch_flag(venv, "arm64") is None
    _fake_python(venv, None)  # universal: runs natively on either machine
    assert hook.macho_arch(venv / "bin" / "python") is None
    assert hook.arch_flag(venv, "arm64") is None
    assert hook.arch_flag(tmp_path / "absent", "arm64") is None


def test_the_venv_request_names_the_architecture_only_where_it_must() -> None:
    expected = "cpython-3.12-macos-aarch64-none" if sys.platform == "darwin" else "3.12"
    assert hook.python_request("arm64") == expected
    assert hook.python_request("x86_64") == "3.12"
    assert hook.python_request(hook.HOST_ARCH) in hook.VENV_FIX


# --------------------------------------------------------------------------- #
# The parser against the REAL corpus.
#
# Every test above builds its own WP file, in the one spelling the parser was
# written for -- so between them they could not notice that no WP in this repo
# uses it.  TEMPLATE.md writes `- **YYYY-MM-DD**`; every real handover log
# writes `### YYYY-MM-DD — title`, so the scan read the whole corpus as having
# no handover entries and flagged every open WP with recent commits as
# `repair first`.  tests/CLAUDE.md § Guards that go quiet: a guard that pins a
# copy of a string living somewhere else tests the copy, not the thing.
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[1]


def _wp_files_with_a_log() -> list[Path]:
    out = []
    for path in sorted((REPO_ROOT / "docs" / "wp").glob("[0-9]*.md")):
        _, sep, log = path.read_text(encoding="utf-8").partition("## Handover log")
        if sep and log.strip():
            out.append(path)
    return out


def test_the_parser_reads_every_real_handover_log() -> None:
    """The scan must find an entry date in every WP that has entries.

    This is the guard the synthetic tests cannot be: it reads the corpus the
    hook actually runs against, so a WP-file convention that drifts away from
    the parser fails here instead of going quiet.
    """
    files = _wp_files_with_a_log()
    assert len(files) > 5, f"expected a real corpus, found {len(files)} WP logs"
    unread = [
        p.name for p in files
        if hook.wp_file_state(REPO_ROOT, p.name[:4])[2] is None
    ]
    assert not unread, (
        "handover logs the session-start scan cannot read a date out of "
        f"(so every open one of them is flagged 'repair first'): {unread}"
    )


def test_both_entry_spellings_parse() -> None:
    """The template's bullet and the corpus's heading are both entries.

    Pinned together so neither can be dropped in favour of the other without
    a red test -- the drift above was silent precisely because only one of
    them was ever exercised.
    """
    assert hook._ENTRY_DATE_RE.findall("- **2026-08-20** — an entry.") == ["2026-08-20"]
    assert hook._ENTRY_DATE_RE.findall("### 2026-08-20 — an entry") == ["2026-08-20"]
    assert hook._ENTRY_DATE_RE.findall("## 2026-08-20 — an entry") == ["2026-08-20"]
    # not an entry: prose that merely opens with a date, and an undated heading
    assert hook._ENTRY_DATE_RE.findall("2026-08-20 was the day") == []
    assert hook._ENTRY_DATE_RE.findall("### the third session") == []


# --------------------------------------------------------------------------- #
# The handover-owed nudge (.claude/hooks/handover_owed.py): a WP session's last
# act is /wp-handover, not a summary of it.  Fires on Stop, once, only where a
# WP branch is at rest with the command never run (measured 2026-09-02).
# --------------------------------------------------------------------------- #

_owed_spec = importlib.util.spec_from_file_location(
    "handover_owed_hook", ROOT / ".claude" / "hooks" / "handover_owed.py"
)
owed = importlib.util.module_from_spec(_owed_spec)
_owed_spec.loader.exec_module(owed)


@pytest.fixture
def wp_branch_at_rest(repo: Path, tmp_path: Path) -> tuple[Path, Path]:
    """A pushed ``wp9001`` worktree carrying one substantive WP commit."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    (repo / "README").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-q", "-u", "origin", "main")
    wt = repo / ".claude" / "worktrees" / "wp9001"
    _git(repo, "worktree", "add", "-q", "-b", "wp9001-fixture", str(wt))
    (wt / "docs" / "wp").mkdir(parents=True, exist_ok=True)
    write_wp(wt, "9001", "🔄", ["2026-09-02"])
    commit_wp(wt, "9001", "2026-09-02", code=True)
    _git(wt, "push", "-q", "-u", "origin", "wp9001-fixture")
    return repo, wt


def _stop(tree: Path, transcript: Path | None = None, **extra) -> dict:
    payload = {"cwd": str(tree), "session_id": "s1", "hook_event_name": "Stop"}
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    payload.update(extra)
    return payload


def _transcript(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_nudge_fires_on_a_wp_branch_at_rest(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    _, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", '{"type":"assistant","text":"done"}\n')
    reason = owed.nudge(_stop(wt, t))
    assert reason is not None
    assert "WP-9001" in reason and "wp9001-fixture" in reason
    assert "/wp-handover 9001" in reason  # the command, spelled to be run


def test_nudge_names_the_branch_s_wp_not_the_newest_commit_s(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """A session that also touched another WP is still handed over on its own."""
    _, wt = wp_branch_at_rest
    _git(wt, "branch", "-m", "wp9001-fixture", "wp9002-fixture")
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    reason = owed.nudge(_stop(wt, t))
    assert reason is not None and "WP-9002" in reason  # not 9001, the commit's


def test_the_hook_s_own_source_does_not_look_like_a_handover(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """Reading the hook or these tests must not silence the hook.

    Both sentinels are assembled from fragments precisely so that neither file
    contains one; spelled out, they matched the transcript of every session
    that opened either, which is a false negative in the one place it hurts —
    the session maintaining the gate (measured 2026-09-02).
    """
    for path in (
        ROOT / ".claude" / "hooks" / "handover_owed.py",
        Path(__file__),
    ):
        assert not owed._HANDOVER_RAN_RE.search(path.read_text(encoding="utf-8")), path
    # and the reason it prints is not a match either, or one nudge silences the next
    _, wt = wp_branch_at_rest
    reason = owed.nudge(_stop(wt, _transcript(tmp_path, "quiet.jsonl", "{}\n")))
    assert reason and not owed._HANDOVER_RAN_RE.search(reason)


def test_nudge_is_silent_once_the_command_has_run(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    _, wt = wp_branch_at_rest
    # Assembled, not spelled: a literal here would land in the transcript of
    # any session that reads this file and silence the hook for it.
    cmd = "wp-" + "handover"
    for name, body in (
        ("skill.jsonl", '{"name":"Skill","input":{"skill": "%s"}}\n' % cmd),
        ("scoped.jsonl",
         '{"name":"Skill","input":{"skill":".claude/worktrees/t:%s"}}\n' % cmd),
        ("typed.jsonl", f"<command-{'name'}>/{cmd}</command-name>\n"),
    ):
        assert owed.nudge(_stop(wt, _transcript(tmp_path, name, body))) is None
    # merely reading or naming the command is not running it
    named = '{"name":"Bash","input":{"command":"cat .claude/skills/wp-handover/SKILL.md"}}\n'
    assert owed.nudge(_stop(wt, _transcript(tmp_path, "named.jsonl", named))) is not None


def test_nudge_never_blocks_two_stops_in_a_row(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    _, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    assert owed.nudge(_stop(wt, t, stop_hook_active=True)) is None


def test_nudge_is_silent_mid_flight(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """Dirty tree or unpushed work is a session still working, not one ending."""
    _, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    (wt / "src" / "fixture.py").write_text("# edited\n", encoding="utf-8")
    assert owed.nudge(_stop(wt, t)) is None
    commit_wp(wt, "9001", "2026-09-02")
    assert owed.nudge(_stop(wt, t)) is None  # clean again, but unpushed
    _git(wt, "push", "-q")
    assert owed.nudge(_stop(wt, t)) is not None


def test_nudge_needs_a_wp_branch_that_added_something(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    main, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    assert owed.nudge(_stop(main, t)) is None  # main adds nothing to origin/main
    _git(wt, "branch", "-m", "wp9001-fixture", "tidy-up")
    assert owed.nudge(_stop(wt, t)) is None  # commits, but not a WP branch
    assert owed.nudge(_stop(tmp_path, t)) is None  # not a repository at all


def test_nudge_does_not_require_a_wp_prefixed_commit(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """A docs-only WP session owes its handover as much as a code one.

    Its commits are ``docs:``/``tooling:`` (39 of the last 400 on main), and
    the branch — not the commit subject — is what names the WP.
    """
    main, wt = wp_branch_at_rest
    _git(wt, "reset", "-q", "--hard", "origin/main")
    (wt / "note.md").write_text("prose\n", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "docs: a paragraph")
    _git(wt, "push", "-q", "--force")
    reason = owed.nudge(_stop(wt, _transcript(tmp_path, "quiet.jsonl", "{}\n")))
    assert reason is not None and "WP-9001" in reason


def test_nudge_asks_once_per_head(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """A session that says "not finished" is not asked again until work lands."""
    _, wt = wp_branch_at_rest
    t = _transcript(tmp_path, "quiet.jsonl", "{}\n")
    assert owed.nudge(_stop(wt, t)) is not None
    assert owed.nudge(_stop(wt, t)) is None
    assert owed.nudge(_stop(wt, t, session_id="s2")) is not None  # a new session asks
    commit_wp(wt, "9001", "2026-09-03", code=True)
    _git(wt, "push", "-q")
    assert owed.nudge(_stop(wt, t)) is not None  # more work landed


def test_nudge_fails_silent_on_a_signal_it_cannot_measure(
    wp_branch_at_rest: tuple[Path, Path], tmp_path: Path
) -> None:
    """No readable transcript reads as "ran": never block on an unmeasured claim."""
    _, wt = wp_branch_at_rest
    assert owed.nudge(_stop(wt)) is None
    assert owed.nudge(_stop(wt, tmp_path / "missing.jsonl")) is None


# --------------------------------------------------------------------------- #
# The WP claim (.claude/hooks/wp_claim.py, WP-1422): one WP per session, so two
# sessions never spend a day on the same work.
# --------------------------------------------------------------------------- #

_claim_spec = importlib.util.spec_from_file_location(
    "wp_claim_hook", ROOT / ".claude" / "hooks" / "wp_claim.py"
)
claim = importlib.util.module_from_spec(_claim_spec)
_claim_spec.loader.exec_module(claim)

_create_spec = importlib.util.spec_from_file_location(
    "worktree_create_hook", ROOT / ".claude" / "hooks" / "worktree_create.py"
)
create = importlib.util.module_from_spec(_create_spec)
_create_spec.loader.exec_module(create)


@pytest.mark.parametrize(
    "name,wp",
    [
        ("wp1422-the-wp-two-sessions-picked", "1422"),
        ("1331-landing-page", "1331"),  # the repo writes both spellings
        ("wp-1422-x", "1422"),
        ("1422", "1422"),
        ("pr-bench", None),  # the bench claims nothing and must not
        ("termplot", None),
        ("wpem-benchmark", None),  # four digits required, not "any digits"
        ("main", None),
    ],
)
def test_a_name_declares_a_wp_or_declares_nothing(name: str, wp: str | None) -> None:
    assert claim.wp_from_name(name) == wp


@pytest.fixture
def two_trees(repo: Path) -> tuple[Path, Path, Path]:
    """A checkout with two WP worktrees, one of them nested inside the other.

    Nested because this repo really does that — ``.claude/worktrees/wp1402-x/
    .claude/worktrees/wp1403-y`` on 2026-09-15 — and containment alone would
    then assign the inner tree's session to the outer one as well.
    """
    (repo / "README").write_text("x\n", encoding="utf-8")
    # The real repo's rule, so the porcelain assertion below is about the claim
    # store and not about the fixture's own worktree directories.
    (repo / ".gitignore").write_text(".claude/worktrees/\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    outer = repo / ".claude" / "worktrees" / "wp9101-outer"
    _git(repo, "worktree", "add", "-q", "-b", "wp9101-outer", str(outer))
    inner = outer / ".claude" / "worktrees" / "wp9102-inner"
    _git(repo, "worktree", "add", "-q", "-b", "wp9102-inner", str(inner))
    return repo, outer, inner


def _sess(pid: int, cwd: Path, age: str = "01:00"):
    return hook.Session(pid, age, str(cwd))


def _porcelain(tree: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"], cwd=tree, capture_output=True, text=True
    ).stdout.strip()


def test_the_main_checkout_claims_nothing(two_trees: tuple[Path, Path, Path]) -> None:
    """It is read-only for a session (worktree_only.py), so it holds no WP."""
    main, _outer, _inner = two_trees
    trees = claim.worktree_branches(main)
    assert claim.main_checkout(trees) == main.resolve()
    assert [h.wp for h in claim.occupancy(trees, [], set(), {}, main)] == ["9101", "9102"]


def test_a_session_holds_the_deepest_tree_that_contains_it(
    two_trees: tuple[Path, Path, Path]
) -> None:
    main, outer, inner = two_trees
    trees = claim.worktree_branches(main)
    sessions = [_sess(11, outer), _sess(22, inner / "src"), _sess(33, main)]
    by_wp = {h.wp: h for h in claim.occupancy(trees, sessions, set(), {}, main)}
    assert [s.pid for s in by_wp["9101"].sessions] == [11]
    assert [s.pid for s in by_wp["9102"].sessions] == [22]


def test_the_scanning_session_is_not_reported_as_a_holder(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """Excluded by pid, so a session is never blocked by its own presence."""
    main, outer, _inner = two_trees
    trees = claim.worktree_branches(main)
    holders = claim.occupancy(trees, [_sess(11, outer)], {11}, {}, main)
    assert [h.held for h in holders] == [False, False]


def test_a_claim_overrides_the_branch_the_tree_is_on(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """The measured case: a tree resumed for a different WP than it is named
    for (2026-09-15, tree ``wp1404-*``, branch ``wp1413-*``, working 1413)."""
    main, outer, _inner = two_trees
    assert claim.write_claim(main, outer, "9199", by="session") is not None
    trees = claim.worktree_branches(main)
    held = {
        h.worktree: h
        for h in claim.occupancy(trees, [], set(), claim.read_claims(main), main)
    }[outer.resolve()]
    assert (held.wp, held.source, held.branch) == ("9199", "claim", "wp9101-outer")

    assert claim.release_claim(main, outer) is True
    assert claim.release_claim(main, outer) is False  # idempotent
    back = {
        h.worktree: h
        for h in claim.occupancy(trees, [], set(), claim.read_claims(main), main)
    }[outer.resolve()]
    assert (back.wp, back.source) == ("9101", "branch")


def test_the_store_is_shared_by_every_worktree_and_tracked_by_none(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """Git guarantees the common dir is one directory for the whole repository,
    which is why a claim crosses branches that never merge."""
    main, outer, inner = two_trees
    dirs = {claim.claims_dir(t) for t in (main, outer, inner)}
    assert len(dirs) == 1 and None not in dirs
    claim.write_claim(main, outer, "9199")
    for tree in (main, outer, inner):
        assert claim.read_claims(tree, prune=False)[outer.resolve()].wp == "9199"
        assert _porcelain(tree) == ""


def test_a_claim_dies_with_its_worktree(two_trees: tuple[Path, Path, Path]) -> None:
    """Pruned on read, so the ledger can never describe a tree that is gone and
    there is no expiry policy to tune.  A stale claim would be a false alarm,
    and a false alarm costs more than no alarm (session_start.py's docstring)."""
    main, outer, _inner = two_trees
    claim.write_claim(main, outer, "9199")
    _git(main, "worktree", "remove", "--force", str(outer))
    assert claim.read_claims(main) == {}
    assert list(claim.claims_dir(main).glob("*.json")) == []


def test_an_unreadable_claim_is_dropped_rather_than_raised(
    two_trees: tuple[Path, Path, Path]
) -> None:
    main, outer, _inner = two_trees
    claim.write_claim(main, outer, "9199")
    junk = claim.claims_dir(main) / "junk.json"
    junk.write_text("{not json", encoding="utf-8")
    assert set(claim.read_claims(main)) == {outer.resolve()}
    assert not junk.exists()


def test_two_live_trees_on_one_wp_are_the_clash(
    two_trees: tuple[Path, Path, Path]
) -> None:
    main, outer, inner = two_trees
    claim.write_claim(main, inner, "9101")  # inner now says it is on outer's WP
    trees = claim.worktree_branches(main)
    holders = claim.occupancy(
        trees, [_sess(11, outer), _sess(22, inner)], set(), claim.read_claims(main), main
    )
    assert claim.clashes(holders) == ["9101"]
    assert claim.clashes([h for h in holders if h.worktree == outer.resolve()]) == []


def test_a_closed_wp_whose_tree_was_kept_is_not_reported(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """Four of this repo's six trees on 2026-09-15 were finished work whose
    directory had not been removed.  Printing them puts the live row fifth."""
    main, _outer, inner = two_trees
    trees = claim.worktree_branches(main)
    holders = claim.occupancy(trees, [_sess(11, inner)], set(), {}, main)
    rows = claim.bears_on_a_clash(holders, {"9101": "✅", "9102": "✅"})
    assert [(h.wp, h.held) for h in rows] == [("9102", True)]  # held survives closing
    assert [h.wp for h in claim.bears_on_a_clash(holders, {"9101": "🔄"})] == ["9101", "9102"]


def test_held_elsewhere_excludes_this_tree(two_trees: tuple[Path, Path, Path]) -> None:
    main, outer, inner = two_trees
    trees = claim.worktree_branches(main)
    holders = claim.occupancy(trees, [_sess(11, outer), _sess(22, inner)], set(), {}, main)
    assert [h.wp for h in claim.held_elsewhere(holders, outer)] == ["9102"]
    assert [h.wp for h in claim.held_elsewhere(holders, None)] == ["9101", "9102"]


def test_the_refusal_names_the_holder_and_the_way_past_it(
    two_trees: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal with no override is a trap: a session parked idle in a tree it
    has finished with would block the next one for ever."""
    main, outer, _inner = two_trees
    monkeypatch.setattr(create.session_start, "live_sessions", lambda: [_sess(11, outer)])
    monkeypatch.setattr(create.session_start, "_ancestors", lambda: set())

    message = create.clash_refusal(main, "9101")
    assert "pid 11" in message and "wp9101-outer" in message
    assert f"release --worktree {outer.resolve()}" in message

    assert create.clash_refusal(main, "9102") == ""  # a dormant tree never refuses
    assert create.clash_refusal(main, "9999") == ""  # nothing at all


def test_the_session_start_line_is_silent_without_a_second_tree(repo: Path) -> None:
    """A machine running one session prints nothing here, so the flag stays
    worth reading on the day it fires."""
    write_wp(repo, "9001", "✅ 2026-08-02 — done", ["2026-08-02"])
    commit_wp(repo, "9001", "2026-08-01")
    make_venv(repo, repo / "src")
    assert hook.claim_lines(repo) == []
    assert len(hook.render(repo).splitlines()) == 1


def test_the_session_start_line_names_the_other_session(
    two_trees: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    main, outer, inner = two_trees
    write_wp(main, "9102", "🔄 2026-09-15 — in flight", ["2026-09-15"])
    monkeypatch.setattr(hook, "live_sessions", lambda: [_sess(22, inner, "03:14")])
    monkeypatch.setattr(hook, "_ancestors", lambda: set())

    (line,) = hook.claim_lines(outer)
    assert "WP-9102 held by pid 22 up 03:14" in line
    assert "wp9102-inner" in line and hook.CLAIM_HINT in line
    assert hook.claim_lines(inner) == []  # its own tree is not news to it


def test_a_wp_tree_with_no_wp_branch_falls_back_to_its_own_name(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """The third ``source`` value, which nothing else reaches.

    A detached HEAD has no branch to read, and a branch renamed to something
    that names no WP is the same case.  Declared as a vocabulary member, so it
    needs a producer and a test naming it (WP-1076's class).
    """
    main, outer, _inner = two_trees
    _git(outer, "checkout", "-q", "--detach")
    trees = claim.worktree_branches(main)
    assert trees[outer.resolve()] is None
    held = {h.worktree: h for h in claim.occupancy(trees, [], set(), {}, main)}[outer.resolve()]
    assert (held.wp, held.source, held.branch) == ("9101", "tree", None)
    assert held.provenance == "from the tree"


def test_a_claim_says_who_declared_it_and_when(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """``by`` and ``declared`` are written into every claim; this reads them.

    The create hook's automatic claim and a session's correction are the two
    cases, and ``source`` alone says "claim" for both.
    """
    main, outer, inner = two_trees
    _git(outer, "checkout", "-q", "--detach")  # no branch to outrank the hook's claim
    claim.write_claim(main, outer, "9199", by="worktree")
    claim.write_claim(main, inner, "9198", by="session")
    stored = claim.read_claims(main)
    assert {c.by for c in stored.values()} == {"worktree", "session"}

    trees = claim.worktree_branches(main)
    by_path = {h.worktree: h for h in claim.occupancy(trees, [], set(), stored, main)}
    # The stored date, not today's: this asserts that provenance renders the
    # fields the claim carries, never that the clock agrees with itself.
    when = stored[outer.resolve()].declared
    assert by_path[outer.resolve()].provenance == f"from the claim, by worktree {when}"
    assert by_path[inner.resolve()].provenance == f"from the claim, by session {when}"
    assert claim.describe(by_path[outer.resolve()], main).endswith(
        f"(from the claim, by worktree {when})"
    )


def test_the_create_hooks_claim_never_outranks_the_branch(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """The claim written from a tree's *name* is the weakest source, not the
    strongest, so it cannot pin a resumed tree to the WP it was named for.

    This is the measured case (2026-09-15: tree ``wp1404-*``, branch
    ``wp1413-*``, working 1413) run forward through the hook that makes trees.
    Ranked with a session's claim, the automatic one re-elevated the tree name
    above the branch and answered 9101 for ever.
    """
    main, outer, _inner = two_trees
    _git(outer, "checkout", "-q", "-b", "wp9199-resumed")
    claim.write_claim(main, outer, "9101", by="worktree")  # what the create hook wrote
    trees = claim.worktree_branches(main)
    held = {
        h.worktree: h
        for h in claim.occupancy(trees, [], set(), claim.read_claims(main), main)
    }[outer.resolve()]
    assert (held.wp, held.source, held.provenance) == ("9199", "branch", "from the branch")

    # A session saying so is the correction, and it still outranks the branch.
    claim.write_claim(main, outer, "9101", by="session")
    corrected = {
        h.worktree: h
        for h in claim.occupancy(trees, [], set(), claim.read_claims(main), main)
    }[outer.resolve()]
    assert (corrected.wp, corrected.source) == ("9101", "claim")


def test_the_main_checkout_is_gits_first_tree_not_the_shallowest_path(
    two_trees: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """A worktree outside ``.claude/worktrees`` can sit above the checkout.

    Under the shallowest-path rule that tree was called the main checkout and
    dropped from the scan, so the one tree a session had gone out of its way to
    make was the one nobody could see.
    """
    main, _outer, _inner = two_trees
    outside = tmp_path / "wp9103-outside"  # one path component; main has many
    _git(main, "worktree", "add", "-q", "-b", "wp9103-outside", str(outside))
    trees = claim.worktree_branches(main)
    assert claim.main_checkout(trees) == main.resolve()
    assert "9103" in {h.wp for h in claim.occupancy(trees, [], set(), {}, main)}


def test_a_dormant_row_says_dormant_rather_than_held_by_no_session(
    two_trees: tuple[Path, Path, Path]
) -> None:
    """Two states are the whole vocabulary, and one line may not claim both."""
    main, outer, _inner = two_trees
    trees = claim.worktree_branches(main)
    (holder,) = [h for h in claim.occupancy(trees, [], set(), {}, main) if h.wp == "9101"]
    line = claim.describe(holder, main)
    assert line.startswith("WP-9101 dormant in") and "no session" not in line


# --------------------------------------------------------------------------- #
# The contributor half (WP-1422): a clash with someone on another machine, which
# no local process scan can see.
# --------------------------------------------------------------------------- #


def _pr(number, title, body="", author="someone", branch="pr/x", files=()):
    return {
        "number": number, "title": title, "body": body,
        "author": {"login": author}, "headRefName": branch,
        "updatedAt": "2026-09-10T12:00:00Z", "isDraft": False,
        "files": [{"path": p} for p in files],
    }


def test_a_pr_that_names_no_wp_is_still_reached_through_its_issue(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The measured shape of every contributor PR on this repo, 2026-09-15.

    `pr/cell-degenerate-guard`, `pr/skill-recipe-rows-7g` and `cw-neutron-seed`
    were all on forks, so absent from `git ls-remote origin`, and not one named
    a WP in its branch, title or body.  They cite issues, and WP files cite the
    issues they close, so PR -> issue -> WP is the only chain that reaches them.
    """
    (repo / "docs" / "wp").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "wp" / "9301-bounds.md").write_text(
        "# WP-9301\n\nCloses #283.\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        claim, "_gh",
        lambda root, *a, **k: json.dumps([
            _pr(289, "lattice: name a degenerate cell (#283)", branch="pr/cell-guard")
        ]),
    )
    (pr,) = claim.open_prs(repo)
    assert (pr.wp, pr.issues, pr.author) == (None, (283,), "someone")

    (o,) = claim.overlaps([pr], claim.wp_issue_citations(repo))
    assert (o.wp, o.via) == ("9301", "issue #283")


def test_a_pr_that_names_a_wp_outright_does_not_go_through_an_issue(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Title, body or an edited WP file: the direct claim, which beats the
    issue chain and must not also produce issue rows."""
    (repo / "docs" / "wp").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "wp" / "9301-bounds.md").write_text("Closes #283.\n", encoding="utf-8")
    citations = claim.wp_issue_citations(repo)

    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: json.dumps([
        _pr(330, "WP-9302: something", body="see #283"),
    ]))
    (pr,) = claim.open_prs(repo)
    assert pr.wp == "9302"
    (o,) = claim.overlaps([pr], citations)
    assert (o.wp, o.via) == ("9302", "names it")

    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: json.dumps([
        _pr(331, "no wp here", files=["docs/wp/9303-thing.md", "src/x.py"]),
    ]))
    (pr,) = claim.open_prs(repo)
    assert pr.wp == "9303"  # the WP file it edits


def test_this_session_s_own_pr_is_not_reported_back_to_it(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "docs" / "wp").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: json.dumps([
        _pr(330, "WP-9302: mine"), _pr(331, "WP-9304: someone else's"),
    ]))
    prs = claim.open_prs(repo)
    assert [o.wp for o in claim.overlaps(prs, {})] == ["9302", "9304"]
    assert [o.wp for o in claim.overlaps(prs, {}, mine="9302")] == ["9304"]


def test_gh_declining_is_not_an_empty_table(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """"No PRs" and "could not look" must not read alike: only the second
    should stop a session trusting what it sees."""
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: None)
    assert claim.open_prs(repo) is None
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: "not json{")
    assert claim.open_prs(repo) is None
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: "[]")
    assert claim.open_prs(repo) == []


def test_one_broad_issue_does_not_fill_the_table_with_one_pr(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Measured: issue #287 is cited by five WP files, so printing per WP gave
    PR #291 five of the first live table's eight rows.  Grouping by PR shows the
    fan-out as a list, which is also what it is — weaker evidence than a PR that
    names one WP — with no threshold invented to say so."""
    wpdir = repo / "docs" / "wp"
    wpdir.mkdir(parents=True, exist_ok=True)
    for n in ("9401", "9402", "9403", "9404", "9405"):
        (wpdir / f"{n}-x.md").write_text("Closes #287.\n", encoding="utf-8")
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: json.dumps([
        _pr(291, "skill: rows join 7g (#287)"),
    ]))
    found = claim.overlaps(claim.open_prs(repo), claim.wp_issue_citations(repo))
    assert len(found) == 5
    grouped = claim.by_pull_request(found)
    assert len(grouped) == 1
    pr, touched = grouped[0]
    assert pr.number == 291 and len(touched) == 5
    line = claim.describe_pull_request(pr, touched)
    assert "WP-9401, WP-9402, WP-9403, WP-9404, WP-9405" in line
    assert line.count("#291") == 1


def test_a_wp_file_with_no_issue_citation_matches_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wpdir = repo / "docs" / "wp"
    wpdir.mkdir(parents=True, exist_ok=True)
    (wpdir / "9501-quiet.md").write_text("# WP-9501\n\nNo issue here.\n", encoding="utf-8")
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: json.dumps([
        _pr(289, "something (#283)"),
    ]))
    assert claim.wp_issue_citations(repo) == {"9501": set()}
    assert claim.overlaps(claim.open_prs(repo), claim.wp_issue_citations(repo)) == []


def test_a_claim_pr_is_recognised_before_it_says_anything(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The branch names the WP, so a draft PR claims it from its first push.

    `/wp-start` step 4b opens the claim before the title is written and
    sometimes before a WP file is touched, so the branch has to be a source in
    its own right — it is the one thing a claim PR always has.
    """
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: json.dumps([
        _pr(400, "", body="", branch="wp9601-the-thing"),
    ]))
    (pr,) = claim.open_prs(repo)
    assert pr.wp == "9601"
    (o,) = claim.overlaps([pr], {})
    assert (o.wp, o.via) == ("9601", "names it")


def test_the_stronger_sources_still_outrank_the_branch(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Title, then the WP file edited, then the branch.  A branch outlives the
    work it was cut for — a tree resumed for another WP keeps its old name — so
    it is the weakest of the three and must stay last."""
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: json.dumps([
        _pr(401, "WP-9602: titled", branch="wp9601-stale"),
        _pr(402, "untitled", branch="wp9601-stale", files=["docs/wp/9603-x.md"]),
    ]))
    titled, filed = claim.open_prs(repo)
    assert titled.wp == "9602"  # title beats the branch
    assert filed.wp == "9603"  # the WP file beats the branch


def test_a_branch_naming_no_wp_claims_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every contributor PR measured on 2026-09-15 had such a branch
    (`pr/cell-degenerate-guard`), and they must still reach a WP by issue
    alone rather than by a branch that says nothing."""
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: json.dumps([
        _pr(403, "lattice: a degenerate cell (#283)", branch="pr/cell-degenerate-guard"),
    ]))
    (pr,) = claim.open_prs(repo)
    assert pr.wp is None and pr.issues == (283,)
    assert [o.via for o in claim.overlaps([pr], {"9604": {283}})] == ["issue #283"]


def test_a_draft_claim_reads_as_a_draft(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A claim PR is a draft until the work is handed over, so the table has to
    say so: a draft holds the WP exactly as a ready PR does, and the reader
    needs to tell "claimed, in flight" from "finished, in review"."""
    raw = _pr(404, "WP-9605: claimed", branch="wp9605-x")
    raw["isDraft"] = True
    monkeypatch.setattr(claim, "_gh", lambda root, *a, **k: json.dumps([raw]))
    (pr,) = claim.open_prs(repo)
    assert pr.draft is True
    line = claim.describe_pull_request(pr, [("9605", "names it")])
    assert "(draft)" in line


# --------------------------------------------------------------------------- #
# The issue backlog (.claude/skills/issue-review/backlog.py): /issue-review's
# table, one row an open issue, cross-referenced against the planning record
# and origin/main.  Network-free here: the cross-reference is a pure function
# of what the three gh calls and git log return.
# --------------------------------------------------------------------------- #

_backlog_spec = importlib.util.spec_from_file_location(
    "issue_backlog", ROOT / ".claude" / "skills" / "issue-review" / "backlog.py"
)
backlog = importlib.util.module_from_spec(_backlog_spec)
_backlog_spec.loader.exec_module(backlog)


def _issue(n: int, **kw) -> "backlog.Issue":
    base = dict(
        number=n, title=f"issue {n}", author="someone", created="2026-09-01",
        updated="2026-09-01", labels=(), body=f"body of {n}", comments=(),
        url=f"https://example/{n}",
    )
    base.update(kw)
    return backlog.Issue(**base)


def test_a_citation_is_the_number_with_a_boundary() -> None:
    """The same regex wp_claim reads WP files with, so #284 never matches #2840."""
    assert backlog.cited_numbers("fixes #284, see #2840 and #28") == frozenset({284, 2840, 28})
    assert backlog.cited_numbers("") == frozenset()


@pytest.mark.parametrize(
    "paths,placement",
    [
        (["docs/wp/1416-x.md", "docs/ROADMAP.md", "tests/test_docs_consistency.py"], True),
        (["gui/CLAUDE.md", ".claude/skills/pr-review/SKILL.md"], True),
        (["docs/wp/1416-x.md", "src/rietx/io/formats/xy.py"], False),
        (["docs/docs/reference/parameters.md"], False),  # for a docs issue, the fix
        ([], False),  # a merge commit lists no files and is no evidence
    ],
)
def test_a_placement_touches_only_the_planning_record(paths: list, placement: bool) -> None:
    """The three triage PRs cited every issue they filed and bumped the ROADMAP
    cap in a test file, so the session-start hook's docs-only reading missed
    them: 65 of 86 open issues read as "landed" on 2026-09-21."""
    assert backlog.is_placement(paths) is placement


def test_the_row_separates_placements_from_landings_and_names_the_untriaged() -> None:
    issues = [_issue(266, author="yue-here"), _issue(284, author="mustachefeeling"),
              _issue(374, author="yue-here"), _issue(407, author="newcomer")]
    citations = {"1416": {266}, "1338": {284, 287}}
    statuses = {"1416": "⬜", "1338": "🔄"}
    refs = [
        backlog.Reference("merged PR", "PR #326 (2026-09-15)", frozenset({266, 284}), True),
        backlog.Reference("merged PR", "PR #292 (2026-09-10)", frozenset({284})),
        backlog.Reference("commit", "2a2f0ba9 2026-09-09 skill: rows", frozenset({284})),
        backlog.Reference("open PR", "#385 (them)", frozenset({374})),
    ]
    rows = backlog.cross_reference(issues, citations, statuses, frozenset({374}), refs)
    by = {r.issue.number: r for r in rows}
    assert by[266].wps == (("1416", "⬜"),)
    assert by[266].landed == () and by[266].placed == ("PR #326 (2026-09-15)",)
    assert by[284].landed == ("PR #292 (2026-09-10)", "2a2f0ba9 2026-09-09 skill: rows")
    assert by[374].wps == () and by[374].roadmap and by[374].triaged
    assert by[374].open_prs == ("#385 (them)",)
    assert not by[407].triaged
    text = backlog.table(rows, today=backlog.date(2026, 9, 21))
    assert text.count(backlog.UNTRIAGED) == 1 and "ROADMAP" in text
    pr = backlog.wp_claim.PullRequest
    prs = (pr(385, "", "them", "", "", False, None, (374,)),
           pr(386, "", "mustachefeeling", "", "", False, None, ()))
    assert backlog.summary(rows, prs).splitlines() == [
        "4 open; 1 untriaged; 1 with a landed reference; 1 cited by an open PR",
        "untriaged: #407",
        "landed reference: #284",
        "not by mustachefeeling or yue-here: #407 newcomer, PR #385 them",
    ]


def test_the_commit_log_parser_skips_merges_and_reads_the_file_list() -> None:
    """``--name-only`` with the record format: a merge commit has two parents
    and lists no files; a fix lists its code; a placement lists the record."""
    log = (
        "\x1e19d5c7e7\x1fp1 p2\x1f2026-09-20\x1fMerge pull request #408 from x\x1f\x1f\n"
        "\x1e1f8e9071\x1fp1\x1f2026-09-01\x1fschemas: Atom inherits bounds (#204)\x1f\x1f\n"
        "src/rietx/schemas/structure.py\ntests/test_schemas.py\n\n"
        "\x1eb3e1a4c2\x1fp1\x1f2026-09-15\x1fdocs: the triage\x1fplaces #266\n\x1f\n"
        "docs/wp/1416-x.md\ndocs/ROADMAP.md\n\n"
    )
    refs = backlog.parse_commit_log(log)
    assert [(r.label[:8], r.placement, sorted(r.cited)) for r in refs] == [
        ("1f8e9071", False, [204]),
        ("b3e1a4c2", True, [266]),
    ]


def test_wp_statuses_read_the_glyph_off_the_milestone_line(tmp_path: Path) -> None:
    wp = tmp_path / "docs" / "wp"
    wp.mkdir(parents=True)
    (wp / "9001-x.md").write_text("# WP-9001\n\nMilestone: unscheduled · Status: ⬜\n", encoding="utf-8")
    (wp / "9002-y.md").write_text("# WP-9002\n\nMilestone: v1.6 · Status: 🔄 2026-09-19 — claimed\n", encoding="utf-8")
    (wp / "9003-z.md").write_text("# WP-9003\n\nno status line\n", encoding="utf-8")
    (wp / "TEMPLATE.md").write_text("Milestone: v0.X · Status: ⬜\n", encoding="utf-8")
    assert backlog.wp_statuses(tmp_path) == {"9001": "⬜", "9002": "🔄", "9003": "?"}


def test_the_issue_file_carries_body_comments_and_both_reference_kinds() -> None:
    issue = _issue(390, comments=(("them", "2026-09-18T20:31:01Z", "a reply"),))
    row = backlog.Row(issue, (("1418", "⬜"),), False, (), ("PR #391 (2026-09-18)",), ("PR #326 (2026-09-15)",))
    text = backlog.issue_file(row)
    for needle in ("# #390 — issue 390", "body of 390", "### them · 2026-09-18T20:31:01Z", "a reply",
                   "cited by: WP-1418 ⬜", "PR #391 (2026-09-18)", "PR #326 (2026-09-15)"):
        assert needle in text


# --------------------------------------------------------------------------- #
# The WP index's merge driver (.claude/hooks/wp_index.py, WP-1507): two
# branches filing a WP each append adjacent rows, which git's line merge
# reports as a conflict.  Driven through a real `git merge` in a tmp repo,
# because what matters is what git does with the driver, not the function.
# --------------------------------------------------------------------------- #

_index_spec = importlib.util.spec_from_file_location(
    "wp_index", ROOT / ".claude" / "hooks" / "wp_index.py"
)
wp_index = importlib.util.module_from_spec(_index_spec)
sys.modules["wp_index"] = wp_index  # a dataclass resolves annotations through it
_index_spec.loader.exec_module(wp_index)

_ROADMAP_FIXTURE = (
    "# Roadmap\n\n## Work packages\n\n### Unscheduled\n\n"
    "The WPs are in [the index](wp/README.md#unscheduled).\n"
)


def _file_wp(root: Path, num: str, status: str = "⬜", tier: str = "P2") -> None:
    (root / "docs" / "wp" / f"{num}-fixture.md").write_text(
        f"# WP-{num} — fixture {num}\n\nMilestone: unscheduled · Status: {status}\n"
        f"Depends on: —\nPriority: {tier} 2026-09-27 — a fixture\n\n## Goal\n\nx.\n\n"
        "## Handover log\n\n- **2026-09-27** — made.\n",
        encoding="utf-8",
    )
    index = root / "docs" / "wp" / "README.md"
    index.write_text(wp_index.generate(root), encoding="utf-8")


def _two_branches(root: Path, ours, theirs) -> subprocess.CompletedProcess:
    """A base with two WPs, `ours` and `theirs` applied on two branches, merged."""
    (root / "docs" / "ROADMAP.md").write_text(_ROADMAP_FIXTURE, encoding="utf-8")
    (root / ".gitattributes").write_text("docs/wp/README.md merge=wpindex\n", encoding="utf-8")
    _file_wp(root, "0001")
    _file_wp(root, "0002")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    _git(root, "checkout", "-qb", "theirs")
    theirs(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "theirs")
    _git(root, "checkout", "-q", "main")
    ours(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "ours")
    return subprocess.run(
        ["git", "-c", "user.email=wp@test", "-c", "user.name=wp", "-c", "commit.gpgsign=false",
         "merge", "-q", "theirs", "-m", "merge"],
        cwd=root, capture_output=True, text=True, check=False,
    )


def _set_driver(root: Path) -> None:
    command = hook.MERGE_DRIVER.replace(
        "python3 .claude/hooks/wp_index.py",
        f'"{sys.executable}" "{ROOT / ".claude" / "hooks" / "wp_index.py"}"',
    )
    _git(root, "config", "merge.wpindex.driver", command)


def test_session_start_sets_the_index_merge_driver_once(repo: Path) -> None:
    hook.ensure_merge_driver(repo)
    got = subprocess.run(["git", "config", "--get", "merge.wpindex.driver"],
                         cwd=repo, capture_output=True, text=True, check=True)
    assert got.stdout.strip() == hook.MERGE_DRIVER
    config = (repo / ".git" / "config").read_text(encoding="utf-8")
    hook.ensure_merge_driver(repo)
    assert (repo / ".git" / "config").read_text(encoding="utf-8") == config


def test_two_branches_filing_adjacent_rows_merge_clean(tmp_path: Path) -> None:
    """The control first: without the driver, git conflicts on the index."""
    def ours(root: Path) -> None:
        _file_wp(root, "0003")

    def theirs(root: Path) -> None:
        _file_wp(root, "0004", tier="P1")
        (root / "docs" / "wp" / "0001-fixture.md").write_text(
            (root / "docs" / "wp" / "0001-fixture.md").read_text(encoding="utf-8")
            .replace("Status: ⬜", "Status: 🔄 2026-09-27"),
            encoding="utf-8",
        )
        (root / "docs" / "wp" / "README.md").write_text(wp_index.generate(root), encoding="utf-8")

    control = tmp_path / "control"
    control.mkdir()
    _git(control, "init", "-q", "-b", "main")
    (control / "docs" / "wp").mkdir(parents=True)
    assert _two_branches(control, ours, theirs).returncode != 0
    assert "<<<<<<<" in (control / "docs" / "wp" / "README.md").read_text(encoding="utf-8")

    root = tmp_path / "driven"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "docs" / "wp").mkdir(parents=True)
    _set_driver(root)
    merged = _two_branches(root, ours, theirs)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    index = (root / "docs" / "wp" / "README.md").read_text(encoding="utf-8")
    assert "<<<<<<<" not in index
    assert index == wp_index.generate(root)
    assert all(f"[{n}](" in index for n in ("0001", "0002", "0003", "0004"))


def test_a_row_both_branches_changed_gets_gits_markers(tmp_path: Path) -> None:
    """The driver declines, and the `|| git merge-file` half writes markers."""
    def rated(tier: str):
        def edit(root: Path) -> None:
            _file_wp(root, "0002", tier=tier)
        return edit

    root = tmp_path / "driven"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "docs" / "wp").mkdir(parents=True)
    _set_driver(root)
    merged = _two_branches(root, rated("P1"), rated("P3"))
    assert merged.returncode != 0
    assert "<<<<<<<" in (root / "docs" / "wp" / "README.md").read_text(encoding="utf-8")


def test_a_depends_link_the_other_branch_renumbered_is_declined() -> None:
    """One branch renumbers a WP, the other files a row depending on it.  The
    row merges in unchanged, linking a file the merged tree lacks, so the
    driver declines rather than write a row regenerating would not."""
    groups = wp_index.roadmap_groups(_ROADMAP_FIXTURE)

    def text(*specs: tuple[str, str]) -> str:
        hs = [wp_index.Header(n, f"{n}-x.md", f"t {n}", "unscheduled", None, "⬜", None,
                              "P2", dep) for n, dep in specs]
        return wp_index.render(groups, wp_index.rows_from_headers(hs, groups))

    base = text(("0001", "—"))
    ours = text(("0001", "—"), ("0002", "0001"))
    theirs = text(("0009", "—"))
    with pytest.raises(wp_index.Conflict, match="0002"):
        wp_index.merge(base, ours, theirs)


def test_a_week_old_release_tag_with_merges_since_owes_a_release(repo: Path) -> None:
    """The weekly cut (WP-1540): silent inside the week, and with nothing merged."""
    (repo / "README").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init", date="2026-09-01")
    _git(repo, "tag", "v1.0.0")
    tagged = datetime.date(2026, 9, 1)
    assert hook.release_flag(repo, today=tagged + datetime.timedelta(days=30)) is None

    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "x.py").write_text("y\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "work", date="2026-09-02")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge", "feature", date="2026-09-02")

    assert hook.release_flag(repo, today=tagged + datetime.timedelta(days=6)) is None
    flag = hook.release_flag(repo, today=tagged + datetime.timedelta(days=7))
    assert flag is not None and "v1.0.0 is 7 days old, 1 merges since" in flag


# --------------------------------------------------------------------------- #
# The PR-subscribe nudge (.claude/hooks/pr_subscribe.py, WP-1988): a PR this
# session puts up for review is one it watches.
# --------------------------------------------------------------------------- #

_sub_spec = importlib.util.spec_from_file_location(
    "pr_subscribe_hook", ROOT / ".claude" / "hooks" / "pr_subscribe.py"
)
pr_subscribe = importlib.util.module_from_spec(_sub_spec)
_sub_spec.loader.exec_module(pr_subscribe)

_PR_URL = "https://github.com/yue-here/rietx/pull/1013\n"
_READY = '✓ Pull request yue-here/rietx#1013 is marked as "ready for review"\n'


def _ran(command: str, stdout: str = "", stderr: str = "") -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command},
            "tool_response": {"stdout": stdout, "stderr": stderr}}


@pytest.mark.parametrize(
    "command, stdout, stderr",
    [
        ('gh pr create --title "WP-9001: x" --body y', _PR_URL, ""),
        ("gh pr ready", "", _READY),
        ("git push origin HEAD && gh pr ready 1013", "", _READY),
        ("gh -R yue-here/rietx pr ready 1013", "", _READY),
        # a newline separates commands as `;` does
        ("git push origin HEAD\ngh pr ready 1013", "", _READY),
        ("if true; then gh pr ready; fi", "", _READY),
        ("(gh pr ready)", "", _READY),
        # a heredoc body is data: an apostrophe or a "--draft" in it is not shell
        ("gh pr create --title x --body-file - <<'EOF'\ndon't\nEOF", _PR_URL, ""),
        ("gh pr create --title x --body-file - <<'EOF'\nnot --draft\nEOF", _PR_URL, ""),
        # a ref after a newline in the output keeps its owner
        ("gh pr ready", "", "note\n" + _READY.removeprefix("✓ Pull request ")),
    ],
)
def test_a_pr_put_up_for_review_is_named(command: str, stdout: str, stderr: str) -> None:
    assert pr_subscribe.target(_ran(command, stdout, stderr)) == ("yue-here", "rietx", 1013)


@pytest.mark.parametrize(
    "command, stdout",
    [
        # /wp-start step 4b's claim: still in flight, so not watched yet
        ('gh pr create --draft --title "WP-9001: x" --body y', _PR_URL),
        ("gh pr create -d --title x", _PR_URL),
        ("gh pr ready --undo", _READY),
        # names a PR without making one reviewable
        ("gh pr view --json url", _PR_URL),
        ("echo gh pr ready", _READY),
        # a create that failed prints no PR, and a nudge about none is noise
        ("gh pr create --title x", ""),
    ],
)
def test_a_draft_a_read_or_a_failure_is_silent(command: str, stdout: str) -> None:
    assert pr_subscribe.target(_ran(command, stdout)) is None


def test_the_mcp_calls_read_the_draft_flag() -> None:
    created = {"tool_name": "mcp__github__create_pull_request",
               "tool_input": {"owner": "o", "repo": "r", "title": "t", "head": "h"},
               "tool_response": [{"type": "text", "text": '{"number": 7, "state": "open"}'}]}
    assert pr_subscribe.target(created) == ("o", "r", 7)
    # the PR object carries `body` ahead of `html_url`: a cited PR must not win
    cited = json.dumps({"number": 7, "body": "see https://github.com/o/r/pull/3",
                        "html_url": "https://github.com/o/r/pull/7"})
    assert pr_subscribe.target(
        {**created, "tool_response": [{"type": "text", "text": cited}]}
    ) == ("o", "r", 7)
    created["tool_input"]["draft"] = True
    assert pr_subscribe.target(created) is None

    readied = {"tool_name": "mcp__github__update_pull_request",
               "tool_input": {"owner": "o", "repo": "r", "pullNumber": 7, "draft": False}}
    assert pr_subscribe.target(readied) == ("o", "r", 7)
    readied["tool_input"].pop("draft")  # a title edit, not a ready
    assert pr_subscribe.target(readied) is None


def test_the_nudge_reaches_the_model_and_fails_open_visibly() -> None:
    """``additionalContext`` on exit 0 is what the model reads; exit 1 is what the user does."""
    hook_path = ROOT / ".claude" / "hooks" / "pr_subscribe.py"
    proc = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(_ran("gh pr ready", "", _READY)), text=True, capture_output=True,
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    assert out["hookEventName"] == "PostToolUse"
    assert "subscribe_pr_activity" in out["additionalContext"]
    assert "pullNumber=1013" in out["additionalContext"]
    assert ".claude/skills/steward/SKILL.md" in out["additionalContext"]
    assert (ROOT / ".claude" / "skills" / "steward" / "SKILL.md").is_file()

    quiet = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(_ran("gh pr view")), text=True, capture_output=True,
    )
    assert (quiet.returncode, quiet.stdout) == (0, "")

    broken = subprocess.run(
        [sys.executable, str(hook_path)], input="not json", text=True, capture_output=True,
    )
    assert broken.returncode == 1 and "failed open" in broken.stderr


def test_the_nudge_is_registered_for_every_call_it_reads() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    matchers = [
        group["matcher"] for group in settings["hooks"]["PostToolUse"]
        if any("pr_subscribe.py" in h["command"] for h in group["hooks"])
    ]
    assert len(matchers) == 1
    assert set(matchers[0].split("|")) >= {
        "Bash", "mcp__github__create_pull_request", "mcp__github__update_pull_request"
    }
