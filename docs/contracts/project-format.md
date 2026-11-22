# Project format version history

One note per change to `PROJECT_FORMAT_VERSION` (`rietx.schemas.project`), which `capabilities()` reports as
`project_format_version`. The rule for when the number moves is the comment
above the constant. `tests/test_capabilities.py` fails when no note names the
constant's current value. These notes name removed things on purpose, so the
code-reference check does not read this directory.

``1.1`` (WP-1047): ``DataRef.options`` gained ``scan``, so the vocabulary a
reader call is replayed from grew.  A **minor** bump because nothing already
written means anything different — the major gate still opens every 1.x — and
an honest one because an older build handed such a project cannot use the key
at all.  It would in fact die earlier than the check, on ``read_pattern``'s
old signature; that is not fixable retroactively, and recording that the
vocabulary grew is the part that is.

``1.2`` (WP-1123): the persisted plan gained ``intermediate_ftol``, so a
project written here carries a key an older build's ``extra="forbid"``
refuses.  Minor for the same reason 1.1 was: the major gate still opens
every 1.x, nothing already written means anything different, and what the
bump records is that the vocabulary grew.

``1.3`` (WP-1207): a project may hold **no phase** — ``project.json`` itself
is unchanged, and what moved is one rank down, in the ``history.jsonl`` state
an older build's ``Structure`` validator refuses to construct.  Minor, and
for the same reason 1.1 and 1.2 were: the major gate still opens every 1.x
and nothing already written means anything different.  The version is the
only field that can say so *before* the log is read, which is the whole
reason it moves for a change that added no key here.

``1.4`` (WP-1323): the persisted plan gained ``lebail_passes``, a key an older
build's ``extra="forbid"`` refuses.  Minor, as 1.2 was for ``intermediate_ftol``.

``1.5`` (WP-2002, B1): the persisted plan gained ``phase_support_sigma``, the
absent-phase hold's threshold.  Minor, as 1.4 was for ``lebail_passes``.

Also in 1.5 (WP-2002, the sixth round's Q1 and Q2): ``closing_window_tol``,
the closing stage's window area fraction, unreleased beside it.

``1.6`` (WP-2030): the stored indexing controls gained ``formula`` and
``temperature``, keys an older build's ``extra="forbid"`` refuses, written
as null when unset.  Minor, as 1.4 was for ``lebail_passes``.

Also in 1.6 (issue #193): the persisted plan gained
``intermediate_lorentz_window_tol``, a bank's Lorentzian window tolerance in
every declared stage but the last, and its stages ``lorentz_window_tol``,
unreleased beside it.
