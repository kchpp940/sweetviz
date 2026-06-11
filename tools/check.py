#!/usr/bin/env python3
"""
Unified quality check entry point for sweetviz developers.

Runs, in order:
    1. requirements sync check   (required for build)
    2. ruff lint                  (optional; skipped if ruff not installed)
    3. pytest                     (optional; skipped if pytest not installed)

Usage:
    python tools/check.py              # run all checks
    python tools/check.py --fast       # skip pytest, just lint + sync
    python tools/check.py --requirements-only
    python tools/check.py --lint-only
    python tools/check.py --test-only
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sweetviz"
TOOLS = ROOT / "tools"


def _run(cmd, desc, *, cwd=None, check=False):
    print(f"\n==> {desc}")
    print(f"    $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd or ROOT))
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result.returncode


def check_requirements() -> int:
    return _run(
        [sys.executable, str(TOOLS / "generate_requirements.py"), "--check"],
        "Checking requirements-*.txt <-> pyproject.toml sync",
    )


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def check_lint() -> int:
    if not _module_available("ruff"):
        print("\n==> Linting with ruff")
        print("    ruff not installed — SKIP (pip install sweetviz[dev])")
        return 0
    return _run(
        [sys.executable, "-m", "ruff", "check", str(SRC), str(TOOLS)],
        "Linting with ruff",
    )


def check_tests() -> int:
    if not _module_available("pytest"):
        print("\n==> Running tests")
        print("    pytest not installed — SKIP (pip install sweetviz[test])")
        return 0
    if not (ROOT / "tests").exists() and not list(ROOT.glob("test_*.py")):
        print("\n==> Running tests")
        print("    no tests/ directory or test_*.py files found — SKIP")
        return 0
    rc = _run(
        [sys.executable, "-m", "pytest", "-q"],
        "Running tests with pytest",
    )
    if rc == 5:
        print("    (pytest collected no tests — not an error)")
        return 0
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true", help="Skip pytest")
    parser.add_argument("--requirements-only", action="store_true")
    parser.add_argument("--lint-only", action="store_true")
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()

    rc_sum = 0

    if args.test_only:
        rc_sum += check_tests()
    elif args.lint_only:
        rc_sum += check_lint()
    elif args.requirements_only:
        rc_sum += check_requirements()
    else:
        rc_sum += check_requirements()
        rc_sum += check_lint()
        if not args.fast:
            rc_sum += check_tests()

    print()
    print("=" * 60)
    if rc_sum == 0:
        print("All checks passed.")
    else:
        print(f"Some checks failed (aggregate exit code: {rc_sum}).")
    print("=" * 60)
    return 0 if rc_sum == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
