"""
Setuptools setup script — registers lightweight build hooks.

Hooks run during `python -m build`, `pip install .`, and `pip install -e .`:
  * Always: lightweight packaging checks (file manifest, MANIFEST rules,
    pyproject.toml deps completeness & version pins). No runtime deps.
  * SWEETVIZ_ENFORCE_PRERELEASE=1: additionally run the full 24-check
    pre-release suite (requires sweetviz + all runtime deps installed).

Environment:
  SWEETVIZ_SKIP_BUILD_HOOK=1   — bypass the hook entirely.
"""
from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist as _sdist

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(ROOT, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


def _inject_hook(cmd_class):
    orig_run = cmd_class.run

    def hooked_run(self):
        from build_hooks import run as run_build_hooks
        run_build_hooks()
        orig_run(self)

    cmd_class.run = hooked_run
    return cmd_class


@_inject_hook
class PrereleaseBuildPy(build_py):
    pass


@_inject_hook
class PrereleaseSdist(_sdist):
    pass


try:
    from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel

    @_inject_hook
    class PrereleaseBdistWheel(_bdist_wheel):
        pass
except ImportError:
    PrereleaseBdistWheel = None


cmdclass = {
    "build_py": PrereleaseBuildPy,
    "sdist": PrereleaseSdist,
}
if PrereleaseBdistWheel is not None:
    cmdclass["bdist_wheel"] = PrereleaseBdistWheel


setup(cmdclass=cmdclass)
