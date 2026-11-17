"""PyInstaller hook for rietx (WP-1950, issue #898).

Runs only inside a PyInstaller build, found through
``rietx.__pyinstaller.get_hook_dirs``. A freeze follows imports, and four
things rietx needs at run time are not imports PyInstaller can see:

* **Data files.** The scattering, dispersion and attenuation tables load
  through ``importlib.resources`` from ``rietx.data``, and the browser pages
  (``gui``, ``watch``, ``compare_app``, ``viz``) serve a ``static`` directory
  by path. ``collect_data_files`` takes every non-Python file in the package.
* **Submodules reached by name.** ``rietx.__getattr__`` imports a submodule on
  first attribute access, and the schema exports are found with
  ``pkgutil.iter_modules``, so the package's modules are collected whole
  (this one excepted).
* **The kernel wheel.** ``model.compiled`` imports ``rietx_kernels`` inside a
  function. A freeze that misses it still fits, on the numpy path, warning
  once; named here so the compiled tier is what a frozen app runs.
* **The version.** ``refine`` reads ``importlib.metadata.version`` for the
  provenance every result and history node stamps. Without the dist-info it
  warns and stamps the development version, so the metadata is copied.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

from rietx._about import DIST_NAME

#: the import names; the distribution's is DIST_NAME, which copy_metadata takes
PACKAGE = "rietx"
KERNELS = "rietx_kernels"

hiddenimports = collect_submodules(
    PACKAGE, filter=lambda name: not name.startswith(f"{PACKAGE}.__pyinstaller"))
hiddenimports.append(KERNELS)

datas = collect_data_files(PACKAGE) + copy_metadata(DIST_NAME)
