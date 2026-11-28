"""The PyInstaller hook rietx ships for itself (WP-1950, issue #898).

PyInstaller finds it through the ``pyinstaller40`` entry point in
``pyproject.toml``, which names :func:`get_hook_dirs`. That is PyInstaller's
documented route for a library to carry its own hook (*Understanding
PyInstaller Hooks*, "Providing PyInstaller Hooks with your Package"), so an
application that freezes rietx needs no ``--collect-data``,
``--hidden-import`` or ``--copy-metadata`` of its own.

This package imports nothing from PyInstaller and is never imported by rietx;
the hook file beside it runs only inside a PyInstaller build. What it collects
and why is in that file's docstring.
"""

from __future__ import annotations

import os


def get_hook_dirs() -> list[str]:
    """The directories PyInstaller searches for ``hook-rietx.py``: this one."""
    return [os.path.dirname(os.path.abspath(__file__))]
