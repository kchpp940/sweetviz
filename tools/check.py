#!/usr/bin/env python
"""
Sweetviz unified pre-release / CI quality checks.

Usage:
    python tools/check.py                  # all checks
    python tools/check.py requirements     # check requirements consistency
    python tools/check.py manifest         # check MANIFEST.in vs package data
    python tools/check.py prerelease       # run sweetviz pre-release suite
    python tools/check.py build            # build wheel + sdist, verify contents
    python tools/check.py all              # everything (default)
    python tools/check.py --skip build     # skip a category

Exit code 0 = everything passed; non-zero = failures.
"""
from __future__ import annotations

import configparser
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
MANIFEST_IN = ROOT / "MANIFEST.in"

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

_results: List[Tuple[str, str, str]] = []


def _record(name: str, status: str, detail: str = ""):
    _results.append((name, status, detail))


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        **kw,
    )


# ---------------------------------------------------------------------------
# 1. Requirements consistency: pyproject.toml dependencies vs runtime imports
# ---------------------------------------------------------------------------

RUNTIME_DEPENDENCIES = [
    "pandas", "numpy", "matplotlib", "tqdm", "scipy",
    "jinja2", "importlib_resources",
]

MANIFEST_RULES_REQUIRED = [
    "recursive-include sweetviz/templates",
    "recursive-include sweetviz/fonts",
    "recursive-include sweetviz/mpl_styles",
    "include sweetviz/sweetviz_defaults.ini",
    "include LICENSE",
    "include setup.py",
    "recursive-include tools",
]


def _parse_pyproject_deps():
    text = PYPROJECT.read_text(encoding="utf-8")
    deps_block = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not deps_block:
        raise RuntimeError("Cannot parse [project].dependencies from pyproject.toml")
    raw = deps_block.group(1)
    deps = {}
    for m in re.finditer(r"['\"]([^'\"]+)['\"]", raw):
        spec = m.group(1)
        name = re.split(r"[<>=!~\s;]", spec, maxsplit=1)[0].lower().replace("_", "-")
        deps[name] = spec
    return deps


def check_pyproject_deps_declared():
    declared = _parse_pyproject_deps()
    missing = []
    for dep in RUNTIME_DEPENDENCIES:
        norm = dep.lower().replace("_", "-")
        if norm not in declared:
            missing.append(dep)
    if missing:
        raise RuntimeError(f"Missing runtime deps in pyproject.toml: {missing}")
    return f"{len(declared)} deps declared, all {len(RUNTIME_DEPENDENCIES)} expected present"


def check_requirements_no_invalid_specs():
    declared = _parse_pyproject_deps()
    bad = []
    for name, spec in declared.items():
        if name in ("importlib_metadata",):
            continue
        if not re.search(r"[<>=!~]", spec):
            bad.append(f"{name} has no version pin: {spec}")
    if bad:
        raise RuntimeError("; ".join(bad))
    return "All deps carry version constraints"


def check_manifest_in_includes():
    if not MANIFEST_IN.exists():
        raise RuntimeError(f"MANIFEST.in not found at {MANIFEST_IN}")
    content = MANIFEST_IN.read_text(encoding="utf-8")
    missing = [g for g in MANIFEST_RULES_REQUIRED if g not in content]
    if missing:
        raise RuntimeError(f"MANIFEST.in missing rules: {missing}")
    return f"{len(MANIFEST_RULES_REQUIRED)} required rules present"


def check_manifest_no_debug_files():
    content = MANIFEST_IN.read_text(encoding="utf-8")
    for bad in ("prune .git", "exclude *.pyc", "exclude __pycache__"):
        if bad in content:
            continue
    return "MANIFEST.in looks clean (no accidental debug-file includes detected)"


# ---------------------------------------------------------------------------
# 2. Pre-release suite (delegates to sweetviz._pre_release)
# ---------------------------------------------------------------------------

def check_prerelease_suite():
    result = _run(
        [sys.executable, "-c", "from sweetviz._pre_release import run_all; import sys; sys.exit(run_all())"]
    )
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-15:])
        raise RuntimeError(f"sweetviz pre-release checks failed (rc={result.returncode}).\n{tail}\nSTDERR: {result.stderr[-500:]}")
    return "Pre-release suite passed"


def check_pytest_pre_release():
    result = _run(
        [sys.executable, "-m", "pytest", "tests/pre_release", "-q", "--tb=short"]
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pytest tests/pre_release failed (rc={result.returncode}).\n"
            f"{result.stdout[-1000:]}\n{result.stderr[-500:]}"
        )
    return "pytest tests/pre_release passed"


# ---------------------------------------------------------------------------
# 3. Build verification: wheel + sdist, verify contents
# ---------------------------------------------------------------------------

WHEEL_MUST_HAVE = [
    "sweetviz/__init__.py",
    "sweetviz/_pre_release.py",
    "sweetviz/_metadata.py",
    "sweetviz/sv_public.py",
    "sweetviz/dataframe_report.py",
    "sweetviz/serialize.py",
    "sweetviz/sweetviz_defaults.ini",
    "sweetviz/templates/dataframe_page.html",
    "sweetviz/templates/js/jquery-3.7.1.min.js",
    "sweetviz/templates/js/sweetviz.js",
    "sweetviz/templates/js/sweetviz_vertical.js",
    "sweetviz/fonts/Roboto-Medium.ttf",
    "sweetviz/fonts/NotoSansCJK-Medium.ttc",
    "sweetviz/mpl_styles/graph_base.mplstyle",
    "sweetviz/mpl_styles/graph_target.mplstyle",
]

SDIST_MUST_HAVE = [
    "pyproject.toml",
    "MANIFEST.in",
    "LICENSE",
    "README.md",
    "sweetviz/__init__.py",
    "sweetviz/sweetviz_defaults.ini",
]


def check_build_wheel_contents():
    result = _run([sys.executable, "-m", "build", "--wheel", "--outdir", "dist"])
    if result.returncode != 0:
        raise RuntimeError(f"wheel build failed.\n{result.stderr[-800:]}")

    wheels = list((ROOT / "dist").glob("sweetviz-*.whl"))
    if not wheels:
        raise RuntimeError("No wheel built in dist/")
    wheel = max(wheels, key=lambda p: p.stat().st_mtime)

    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())

    missing = [p for p in WHEEL_MUST_HAVE if p not in names]
    if missing:
        raise RuntimeError(f"Wheel missing files: {missing}")
    return f"Wheel {wheel.name} has {len(WHEEL_MUST_HAVE)} required files"


def check_build_sdist_contents():
    result = _run([sys.executable, "-m", "build", "--sdist", "--outdir", "dist"])
    if result.returncode != 0:
        raise RuntimeError(f"sdist build failed.\n{result.stderr[-800:]}")

    sdists = list((ROOT / "dist").glob("sweetviz-*.tar.gz"))
    if not sdists:
        raise RuntimeError("No sdist built in dist/")

    import tarfile
    sdist = max(sdists, key=lambda p: p.stat().st_mtime)
    with tarfile.open(sdist, "r:gz") as tf:
        names = set()
        for m in tf.getmembers():
            names.add("/".join(m.name.split("/")[1:]))

    missing = [p for p in SDIST_MUST_HAVE if p not in names]
    if missing:
        raise RuntimeError(f"sdist missing files: {missing}")
    return f"sdist {sdist.name} has {len(SDIST_MUST_HAVE)} required files"


def check_wheel_install_and_import():
    wheels = list((ROOT / "dist").glob("sweetviz-*.whl"))
    if not wheels:
        raise RuntimeError("No wheel to test install from (run check_build_wheel_contents first)")
    wheel = max(wheels, key=lambda p: p.stat().st_mtime)

    script = (
        "import sys, subprocess;"
        "subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--force-reinstall', '--no-deps', sys.argv[1]]);"
        "import sweetviz;"
        "print('VERSION', sweetviz.__version__);"
        "print('ANALYZE', callable(sweetviz.analyze));"
        "report = sweetviz.analyze(__import__('pandas').DataFrame({'a': [1,2,3]}));"
        "print('REPORT', type(report).__name__);"
    )
    result = _run([sys.executable, "-c", script, str(wheel)])
    if result.returncode != 0:
        raise RuntimeError(f"Wheel install+import failed.\n{result.stdout[-1000:]}\n{result.stderr[-1000:]}")
    return "Wheel installs cleanly and sweetviz.analyze runs"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CATEGORIES = {
    "requirements": [
        ("requirements.pyproject_deps", check_pyproject_deps_declared),
        ("requirements.version_pins", check_requirements_no_invalid_specs),
        ("requirements.manifest_globs", check_manifest_in_includes),
        ("requirements.manifest_clean", check_manifest_no_debug_files),
    ],
    "prerelease": [
        ("prerelease.suite", check_prerelease_suite),
        ("prerelease.pytest", check_pytest_pre_release),
    ],
    "build": [
        ("build.wheel_contents", check_build_wheel_contents),
        ("build.sdist_contents", check_build_sdist_contents),
        ("build.wheel_install", check_wheel_install_and_import),
    ],
}


def _safe_run(name: str, func, *args, **kwargs):
    try:
        detail = func(*args, **kwargs)
        _record(name, PASS, detail or "")
    except Exception as exc:
        _record(name, FAIL, f"{type(exc).__name__}: {exc}")


def run(targets=None, skip=None):
    targets = targets or ["all"]
    skip = skip or set()

    if "all" in targets:
        targets = list(CATEGORIES.keys())

    todo: List[Tuple[str, callable]] = []
    for cat in targets:
        if cat in skip:
            continue
        if cat not in CATEGORIES:
            raise ValueError(f"Unknown check category: {cat}. Available: {list(CATEGORIES.keys()) + ['all']}")
        todo.extend(CATEGORIES[cat])

    for name, func in todo:
        _safe_run(name, func)

    passed = sum(1 for _, s, _ in _results if s == PASS)
    failed = sum(1 for _, s, _ in _results if s == FAIL)
    skipped = sum(1 for _, s, _ in _results if s == SKIP)

    print("\n" + "=" * 64)
    print("Sweetviz Unified Pre-Release Check (tools/check.py)")
    print("=" * 64)
    for name, status, detail in _results:
        marker = {"PASS": "✓", "FAIL": "✗", "SKIP": "○"}[status]
        line = f"  {marker} {name}"
        if detail:
            line += f"  ({detail})"
        print(line)

    print("-" * 64)
    print(f"  Total: {len(_results)}  |  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}")
    print("=" * 64)

    if failed > 0:
        print("\n❌ Unified checks FAILED. Do not release.")
        return 1
    print("\n✅ All unified checks passed. Safe to release.")
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    skip_flags = [a[len("--skip="):] for a in sys.argv[1:] if a.startswith("--skip=")]
    skip = set()
    for s in skip_flags:
        skip.update(s.split(","))
    targets = args or ["all"]
    sys.exit(run(targets, skip))


if __name__ == "__main__":
    main()
