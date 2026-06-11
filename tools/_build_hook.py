"""
setuptools build hook — runs before building sdist / wheel.

Validates that requirements-*.txt files are in sync with pyproject.toml,
and refuses to build if they drift. This guarantees that released packages
contain a requirements.txt that matches the actual dependency declarations.

Activated via pyproject.toml:
    [tool.setuptools]
    cmdclass = {"sdist": "tools._build_hook.checking_sdist",
                "build_py": "tools._build_hook.checking_build_py"}
"""
from __future__ import annotations

import sys
from pathlib import Path

from setuptools.command.build_py import build_py as _build_py
from setuptools.command.sdist import sdist as _sdist


ROOT = Path(__file__).resolve().parent.parent
CHECK_SCRIPT = ROOT / "tools" / "generate_requirements.py"


def _run_check():
    if not CHECK_SCRIPT.exists():
        print(
            f"[build-hook] WARNING: {CHECK_SCRIPT.name} not found, "
            "skipping requirements sync check.",
            file=sys.stderr,
        )
        return

    import subprocess
    result = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        sys.stderr.write(
            "\n[build-hook] ERROR: requirements-*.txt files are out of sync "
            "with pyproject.toml.\n"
            "Run: python tools/generate_requirements.py\n"
            "then re-run the build.\n"
        )
        raise SystemExit(1)
    print("[build-hook] requirements-*.txt in sync with pyproject.toml.")


class checking_sdist(_sdist):
    def run(self):
        _run_check()
        super().run()


class checking_build_py(_build_py):
    def run(self):
        _run_check()
        super().run()
