# Release-note fragments

A change a user upgrading needs to hear about (a break, a number that moves,
a user-facing addition) stages its note here as a file of its own, in the
pull request that makes the change (WP-1941). Two pull requests that each add
a note then add two files, and neither has to rebase over the other.

**Name** the file `<id>.<section>.md`:

- `<id>` is the pull request's number. Before the pull request exists, use any
  name no other note uses, such as the WP (`wp1941`) or the issue
  (`issue877`); renaming it later is optional.
- `<section>` is a heading of the next release's staged notes,
  `docs/releases/X.Y.Z.md` (`pyproject.version` without its `.devN`), in
  lower case with every run of other characters a hyphen. `## New` is
  `new`; `### Numbers that move` is `numbers-that-move`. A note that needs a
  section the file lacks adds the heading to that file.

**Write** the text that goes under the heading, with no heading of its own:
usually one bullet, continuation lines indented two spaces, as the staged
notes already are. Several bullets for one section go in one file.

**Check** with `python -m tests.release_notes --check`, which
`tests/test_docs_consistency.py` also runs. `python -m tests.release_notes`
prints the notes with every fragment placed: each goes at the end of its
section, in `<id>` order, numbers first. One-bullet notes from separate pull
requests make one tight list; a section whose bullets are already
blank-separated gets a blank line before each note.

**After a cut**, the staged notes are a new file, and it may lack the heading
a note on an older branch names. `--check` then refuses that note, naming the
new file, and so does the docs job on main once the branch merges. Rebase onto
main, or re-run CI, after a release is cut; then add the heading to the new
file or rename the note to a section it has.

At the cut, `docs/RELEASING.md` step 2 joins the fragments into the staged
notes with `--write`, which deletes them, and the result is then edited as a
reader's document.
