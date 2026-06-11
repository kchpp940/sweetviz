"""
Build hooks for sweetviz.

Enforces pre-release checks before producing any build artifact.
Set SWEETVIZ_SKIP_PRERELEASE_HOOK=1 to bypass (CI debugging only).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional


def _clean_env() -> dict:
    """Return a copy of os.environ without pip/build-isolation env vars that
    would pollute the target interpreter's site-packages."""
    env = os.environ.copy()
    for key in list(env.keys()):
        if (
            key.startswith("PYTHON")
            or key.startswith("PIP_")
            or key.startswith("VIRTUAL_ENV")
            or key in ("PEP517_BUILD_BACKEND", "SETUPTOOLS_ENABLE_FEATURES")
        ):
            env.pop(key, None)
    return env


def _find_host_python(src_root: str) -> Optional[str]:
    candidates = []
    for env_key in ("SWEETVIZ_HOST_PYTHON", "CONDA_PREFIX"):
        if os.environ.get(env_key):
            base = os.environ[env_key]
            if env_key == "SWEETVIZ_HOST_PYTHON":
                candidates.append(base)
            else:
                candidates.append(os.path.join(base, "bin", "python"))
                candidates.append(os.path.join(base, "bin", "python3"))
    candidates.extend([
        sys.executable,
        shutil.which("python3") or "",
        shutil.which("python") or "",
        "/usr/bin/python3",
        "/usr/local/bin/python3",
        "/opt/homebrew/bin/python3",
    ])
    clean_env = _clean_env()
    seen = set()
    for c in candidates:
        if not c or c in seen:
            continue
        seen.add(c)
        if not os.path.isfile(c):
            continue
        try:
            result = subprocess.run(
                [
                    c, "-c",
                    "import sys; sys.path.insert(0, sys.argv[1]); "
                    "import pandas, sweetviz; print('OK')",
                    src_root,
                ],
                capture_output=True,
                text=True,
                timeout=15,
                env=clean_env,
            )
            if result.returncode == 0 and "OK" in result.stdout:
                return c
        except Exception:
            pass
    return None


def _run_prerelease_hook():
    if os.environ.get("SWEETVIZ_SKIP_PRERELEASE_HOOK"):
        print("[sweetviz-build] SWEETVIZ_SKIP_PRERELEASE_HOOK=1 -> skipping pre-release check hook",
              file=sys.stderr)
        return

    print("[sweetviz-build] Running pre-release checks before build...", file=sys.stderr)

    src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    try:
        import pandas  # noqa: F401
        import sweetviz  # noqa: F401
    except ImportError:
        host_python = _find_host_python(src_root)
        if host_python is None:
            raise SystemExit(
                "[sweetviz-build] Cannot find a Python interpreter with pandas+sweetviz installed. "
                "Install the package first ('pip install -e .') or set SWEETVIZ_SKIP_PRERELEASE_HOOK=1 to bypass."
            )
        print(f"[sweetviz-build] Rerunning pre-release checks via host Python: {host_python}", file=sys.stderr)
        clean_env = _clean_env()
        result = subprocess.run(
            [
                host_python,
                "-c",
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "from sweetviz._pre_release import run_all; sys.exit(run_all())",
                src_root,
            ],
            cwd=src_root,
            env=clean_env,
        )
        if result.returncode != 0:
            raise SystemExit(
                f"[sweetviz-build] Pre-release checks failed (rc={result.returncode}). "
                "Fix the issues or set SWEETVIZ_SKIP_PRERELEASE_HOOK=1 to bypass."
            )
        print("[sweetviz-build] Pre-release checks passed (via host interpreter).", file=sys.stderr)
        return

    try:
        from sweetviz._pre_release import run_all
    except Exception as exc:
        raise SystemExit(
            f"[sweetviz-build] Cannot import sweetviz._pre_release from {src_root}: {exc}. "
            "Set SWEETVIZ_SKIP_PRERELEASE_HOOK=1 to bypass."
        )

    rc = run_all()
    if rc != 0:
        raise SystemExit(
            f"[sweetviz-build] Pre-release checks failed (rc={rc}). "
            "Fix the issues or set SWEETVIZ_SKIP_PRERELEASE_HOOK=1 to bypass."
        )
    print("[sweetviz-build] Pre-release checks passed.", file=sys.stderr)
