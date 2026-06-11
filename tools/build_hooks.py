"""
Build hooks for sweetviz.

This hook runs during `python -m build`, `pip install .`, `pip install -e .`.

Default behaviour (always, no runtime deps):
  1. Verify package-data MANIFEST rules are present and match pyproject.toml
  2. Verify every expected runtime file (templates, fonts, mpl_styles, INI)
     actually exists on disk under sweetviz/
  3. Verify pyproject.toml dependencies are complete and version-pinned

Opt-in full pre-release check (requires sweetviz + pandas + all deps installed):
  Set SWEETVIZ_ENFORCE_PRERELEASE=1 to additionally run the full 24-check
  pre-release suite. Intended for release-machine / CI use only.

Any failure aborts the build with a non-zero exit code.
Set SWEETVIZ_SKIP_BUILD_HOOK=1 to bypass entirely.
"""
from __future__ import annotations

import configparser
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
MANIFEST_IN = ROOT / "MANIFEST.in"

REQUIRED_PACKAGE_FILES = [
    "sweetviz/sweetviz_defaults.ini",
    "sweetviz/templates/dataframe_page.html",
    "sweetviz/templates/dataframe_summary.html",
    "sweetviz/templates/dataframe_associations.html",
    "sweetviz/templates/feature_summary_numeric.html",
    "sweetviz/templates/feature_summary_cat.html",
    "sweetviz/templates/feature_summary_text.html",
    "sweetviz/templates/feature_summary_target_numeric.html",
    "sweetviz/templates/feature_summary_target_cat.html",
    "sweetviz/templates/feature_summary_base_stats.html",
    "sweetviz/templates/feature_detail_numeric.html",
    "sweetviz/templates/feature_detail_cat.html",
    "sweetviz/templates/feature_detail_text.html",
    "sweetviz/templates/include_missing.html",
    "sweetviz/templates/sweetviz.css",
    "sweetviz/templates/sv_assets.css",
    "sweetviz/templates/js/jquery-3.7.1.min.js",
    "sweetviz/templates/js/sweetviz.js",
    "sweetviz/templates/js/sweetviz_vertical.js",
    "sweetviz/fonts/Roboto-Medium.ttf",
    "sweetviz/fonts/NotoSansCJK-Medium.ttc",
    "sweetviz/mpl_styles/graph_base.mplstyle",
    "sweetviz/mpl_styles/graph_target.mplstyle",
]

RUNTIME_DEPS_EXPECTED = [
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

_results: List[Tuple[str, str, str]] = []


def _record(name: str, status: str, detail: str = ""):
    _results.append((name, status, detail))


def _fail(msg: str):
    raise SystemExit(f"[sweetviz-build-hook] {msg}")


def _parse_pyproject_deps() -> dict:
    text = PYPROJECT.read_text(encoding="utf-8")
    deps_block = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not deps_block:
        raise _fail("Cannot parse [project].dependencies from pyproject.toml")
    raw = deps_block.group(1)
    deps = {}
    for m in re.finditer(r"['\"]([^'\"]+)['\"]", raw):
        spec = m.group(1)
        name = re.split(r"[<>=!~\s;]", spec, maxsplit=1)[0].lower().replace("_", "-")
        deps[name] = spec
    return deps


def check_package_files_exist() -> str:
    missing = [p for p in REQUIRED_PACKAGE_FILES if not (ROOT / p).is_file()]
    if missing:
        _fail(f"Missing package files on disk: {missing}")
    return f"{len(REQUIRED_PACKAGE_FILES)} expected files present"


def check_manifest_rules() -> str:
    if not MANIFEST_IN.exists():
        _fail(f"MANIFEST.in not found at {MANIFEST_IN}")
    content = MANIFEST_IN.read_text(encoding="utf-8")
    missing = [r for r in MANIFEST_RULES_REQUIRED if r not in content]
    if missing:
        _fail(f"MANIFEST.in missing rules: {missing}")
    return f"{len(MANIFEST_RULES_REQUIRED)} required MANIFEST rules present"


def check_pyproject_deps_complete() -> str:
    declared = _parse_pyproject_deps()
    missing = [d for d in RUNTIME_DEPS_EXPECTED if d.lower().replace("_", "-") not in declared]
    if missing:
        _fail(f"pyproject.toml missing runtime deps: {missing}")
    bad = []
    for name, spec in declared.items():
        if name in ("importlib-metadata",):
            continue
        if not re.search(r"[<>=!~]", spec):
            bad.append(f"{name} has no version pin: {spec}")
    if bad:
        _fail("pyproject.toml deps without version pins: " + "; ".join(bad))
    return f"{len(declared)} deps declared, all {len(RUNTIME_DEPS_EXPECTED)} expected present & version-pinned"


def check_setup_py_exists() -> str:
    if not (ROOT / "setup.py").is_file():
        _fail("setup.py missing — build hooks cannot be registered")
    return "setup.py present"


def run_full_pre_release_suite() -> str:
    sys.path.insert(0, str(ROOT))
    try:
        from sweetviz._pre_release import run_all
    except Exception as exc:
        _fail(
            f"SWEETVIZ_ENFORCE_PRERELEASE=1 requested but cannot import "
            f"sweetviz._pre_release: {exc}. Ensure sweetviz + all runtime "
            f"deps are installed in the build environment."
        )
    rc = run_all()
    if rc != 0:
        _fail(f"SWEETVIZ_ENFORCE_PRERELEASE=1 suite failed (rc={rc})")
    return "Full 24-check pre-release suite passed"


def run():
    if os.environ.get("SWEETVIZ_SKIP_BUILD_HOOK"):
        print("[sweetviz-build-hook] SWEETVIZ_SKIP_BUILD_HOOK=1 — bypassing",
              file=sys.stderr)
        return

    print("[sweetviz-build-hook] Running lightweight packaging checks...",
          file=sys.stderr)

    _record("files.on_disk", "PASS", check_package_files_exist())
    _record("manifest.rules", "PASS", check_manifest_rules())
    _record("deps.pyproject", "PASS", check_pyproject_deps_complete())
    _record("setup_py.present", "PASS", check_setup_py_exists())

    if os.environ.get("SWEETVIZ_ENFORCE_PRERELEASE"):
        print("[sweetviz-build-hook] SWEETVIZ_ENFORCE_PRERELEASE=1 — "
              "running full pre-release suite...", file=sys.stderr)
        _record("prerelease.suite", "PASS", run_full_pre_release_suite())

    passed = sum(1 for _, s, _ in _results if s == "PASS")
    print(f"[sweetviz-build-hook] OK ({passed} checks)", file=sys.stderr)
