"""
Setuptools setup script — required to inject pre-release check build hooks.

The hook runs BEFORE any build artifact (wheel / sdist) is produced,
preventing broken packages from being built without passing the
pre-release checklist.

The hook may be bypassed with:  SWEETVIZ_SKIP_PRERELEASE_HOOK=1
"""
from setuptools import setup, find_packages
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
        from build_hooks import _run_prerelease_hook
        _run_prerelease_hook()
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
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

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


setup(
    cmdclass=cmdclass,
)
