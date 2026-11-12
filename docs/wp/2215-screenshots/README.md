# WP-2215 — the frame at `/next`

Review pictures for `../2215-the-frame.md`. Each shows the whole window of the rebuilt
page at 1440 × 900, one device pixel per CSS pixel, in light and in dark. The matching
prototype pictures stay outside the repository; the pull request names where they are.

- `next-main-*.png`: the `fap` example project open, both side panels showing, the
  console hidden.
- `next-console-*.png`: the console shown from the status bar's button.
- `next-wfmenu-*.png`: the workflow menu open from the top bar.
- `next-filemenu-*.png`: the File menu open from the project name.
- `next-settings-*.png`: Settings, opened from the cog.
- `next-palette-*.png`: the command palette, opened with ⌘K.
- `next-keys-*.png`: the list of keys, opened with `?`.
- `next-start-*.png`: the start screen, with no project open.
- `next-newproject-*.png`: New project, opened from the start screen.

Taken 2026-11-11 on macOS (arm64) with the cached chromium, against the dist this branch
commits, with `RIETX_STATE_DIR` pointed at a temporary directory. Every menu and dialog
was opened by a real click or key press. Retaken the same day after the review, with the
page's own fonts loaded before each shot: Instrument Sans for words, IBM Plex Mono for keys
and code, and IBM Plex Sans for the Greek in New project's `Cu Kα1/Kα2`. The panes are empty because their contents are
the later pieces' work (WP-2214, R2 to R4).
