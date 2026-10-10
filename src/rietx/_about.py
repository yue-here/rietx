"""The name-bearing literals, in one place (WP-1062).

Every string in this package that spells the *distribution*, the on-disk
*format tokens* or the *state directory* lives here and nowhere else.  The
module imports nothing — not even from this package — so anything may import
it: the forward model, the GUI server, ``docs/manual/conf.py``, the tests.

Two rules the values below follow, and they point in opposite directions:

* **The brand tokens track the distribution.**  :data:`DIST_NAME` is what
  ``importlib.metadata.version`` is asked for, and :data:`STATE_DIR_NAME`,
  :data:`STATE_DIR_ENV`, :data:`PROJECTS_DIR_NAME`, :data:`DATA_PACKAGE`,
  :data:`SERVER_TOKEN` and :data:`DOCS_URL` are user-visible spellings of the
  same name.  Renaming the package moves all seven together.
* **The format tokens do not.**  :data:`PROJECT_SUFFIX`, :data:`TEXTDOC_MAGIC`
  and :data:`PROFILE_FORMAT_KEY` name *versioned contracts*
  (``schemas.project.PROJECT_FORMAT_VERSION``, ``gui.textdoc.FORMAT_VERSION``,
  ``io.instrument_profile.FORMAT_VERSION``), and a contract must not move
  because a brand did.  Keeping them free of the brand is what stops a future
  rename from being a format break, and stops a format inheriting whatever
  ambiguity the brand acquires.

**Import these; never spell them.** ``tests/test_no_stale_name.py`` fails on a
reintroduction of an *old* name, and it greps only old ones: an audit against
the current name would fail on the many places that legitimately say it — the
README, this module, ``prog=`` strings, every ``:func:`~rietx.…``` cross
reference.  The consequence is that a freshly hardcoded ``"rietx"``, ``".rex"``
or ``"rxt"`` is **invisible to every test in the suite**.  Nothing but the rule
catches it.

WP-1066 renamed the brand a second time and left every format token below
untouched, which is the second rule above paying for itself one rename after it
was written.  One of the two names it retired is also a phase this software
analyses, so the audit's grep for it has a foreseeable expiry; the test's own
docstring holds that argument, because spelling the token here would put this
module on the audit's allowlist and blind it to exactly the stale literal it
exists to catch.
"""

#: The distribution name — ``importlib.metadata.version`` argument, the
#: ``pip install 'NAME[extra]'`` hints, and the manual's ``release``.
DIST_NAME = "rietx"

#: Conventional suffix of a project *directory* (``project.py``).  Not
#: enforced there; the GUI wizard is what actually offers it.
PROJECT_SUFFIX = ".rex"

#: The event-stream directory inside a project (``project.py``, which
#: re-exports this as ``LIVE_DIR``, and ``runs.py``, which finds a project's
#: run without importing the refinement engine to ask).
LIVE_DIR_NAME = "live"

#: First word of the project text document's header line, ``<magic> N``, and
#: its file extension (``gui/textdoc.py``, and the CodeMirror language on the
#: frontend side, which cannot import this and carries its own copy).
TEXTDOC_MAGIC = "rxt"

#: Tag identifying an instrument-profile JSON file
#: (``io/instrument_profile.py``).
PROFILE_FORMAT_KEY = "instrument_profile"

#: Per-user state the GUI keeps outside any project — the recent list and the
#: theme — under ``$HOME``, with the env var overriding it so tests and a
#: sandboxed build never touch a real home directory.
STATE_DIR_NAME = ".rietx"
STATE_DIR_ENV = "RIETX_STATE_DIR"

#: Runs recorded by a fit nobody asked to record (WP-1403), under
#: ``<working directory>/<STATE_DIR_NAME>/<RUNS_DIR_NAME>/<run id>``.
#:
#: **Two directories are spelled** :data:`STATE_DIR_NAME` **and they are not
#: the same directory.** ``$HOME/.rietx`` is the GUI's per-user state, and
#: :data:`STATE_DIR_ENV` moves that one and only that one. The *working
#: directory's* ``.rietx/`` is this: telemetry belonging to the tree a fit ran
#: in, the way ``.git`` is one name whose meaning is its location. No env var
#: moves it, because a caller who wants it somewhere else passes
#: ``telemetry=<path>`` and a caller who wants none of it sets
#: :data:`TELEMETRY_ENV`. No test can catch the two being confused — they are
#: the same literal — so the note is the whole defence.
RUNS_DIR_NAME = "runs"

#: Where the GUI offers to put a *new* project, under ``$HOME``.  Not hidden and
#: not inside :data:`STATE_DIR_NAME`: these are the person's documents, not the
#: app's state, and a wizard suggesting a dot-directory would be suggesting
#: somewhere nobody looks.  Only ever a *suggestion* — the wizard's path field
#: is editable, and ``Project.create`` makes the parents on first use.
PROJECTS_DIR_NAME = "rietx-projects"

#: Switches the compiled kernel tier off (``0``/``off``/``no``/``false``), which
#: makes every residual take the pure-numpy path.  A *runtime* knob and not a
#: packaging one on purpose: the ``rietx-kernels`` wheel is a required
#: dependency so the fast path is what a default install gets, and an extra can
#: only ever add a dependency, never subtract one — so this is what a user who
#: cannot or will not run the compiled tier reaches for, and what keeps the
#: numpy path exercised.  It also silences the warning an install without the
#: wheel gives (``model/compiled.py``).
COMPILED_ENV = "RIETX_COMPILED"
#: Worker threads the compiled kernels split their rows across; unset means
#: ``min(8, cpu_count)``.  Set it to ``1`` where the parallelism is already one
#: rank up — a suite under ``xdist``, a series fanned out over processes.
COMPILED_THREADS_ENV = "RIETX_COMPILED_THREADS"

#: Switches automatic run recording off (``0``/``off``/``no``/``false``), so a
#: fit writes nothing anywhere unless its caller passed ``events=``. A runtime
#: knob beside :data:`COMPILED_ENV` and for the same reason: recording needs no
#: optional dependency, so packaging cannot express the choice.
#:
#: It **outranks** the ``telemetry=`` keyword, and there is deliberately no
#: value that switches recording back *on* against it. Someone who set this
#: wants their disk left alone everywhere, and a library call that could
#: override them would make the switch a suggestion. ``runs.set_enabled``
#: mirrors ``model.compiled.set_enabled`` for a caller who needs to change it
#: inside a process, and is what the suite uses.
TELEMETRY_ENV = "RIETX_TELEMETRY"

#: Import path of the bundled data package (scattering factors, attenuation
#: and dispersion tables), read through ``importlib.resources``.
DATA_PACKAGE = "rietx.data"

#: Short token for ephemeral server-side names a person may see in a path or a
#: stack trace: the upload staging directory and the run thread.
SERVER_TOKEN = "rietx"

#: Root of the hosted documentation (GitHub Pages, WP-1003), no trailing
#: slash.  The README, ``pyproject.urls`` and the skill's own frontmatter quote
#: it; the JSON tool description that used to append a document path to it went
#: with ``rietx.agent`` in WP-1303.  A brand token: a rename or a hosting move
#: changes it here and nowhere else.
DOCS_URL = "https://rietx.org"

#: Root of the source repository, no trailing slash.  A brand token like
#: :data:`DOCS_URL`, and the base the theory manual builds a per-equation
#: source link on (WP-1408): each *Source:* line resolves its dotted name
#: through ``inspect`` at build time and links to ``<REPO_URL>/blob/<ref>/<path>
#: #L<line>``.  Kept here rather than read from ``pyproject.urls`` because the
#: metadata of an editable install is not reliably the checkout's.
REPO_URL = "https://github.com/yue-here/rietx"
