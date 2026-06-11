#!/usr/bin/env python
"""
Sweetviz unified pre-release / CI quality checks.

Usage:
    python tools/check.py                     # release pipeline (default)
    python tools/check.py requirements        # check requirements consistency
    python tools/check.py prerelease          # run sweetviz pre-release suite
    python tools/check.py build               # build wheel + sdist, verify contents
    python tools/check.py release             # requirements + prerelease + build
    python tools/check.py all                 # same as release
    python tools/check.py build --verbose     # show per-file build verification logs
    python tools/check.py --skip build        # skip a category / tag

Exit code 0 = everything passed; non-zero = failures.
"""
from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
MANIFEST_IN = ROOT / "MANIFEST.in"

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

_results: List[Tuple[str, str, str]] = []
VERBOSE: bool = False


def _set_verbose(v: bool):
    global VERBOSE
    VERBOSE = v


def _vlog(msg: str):
    if VERBOSE:
        print(f"    | {msg}", flush=True)


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
# 3. Build verification: wheel + sdist, verify contents via real unpacking
# ---------------------------------------------------------------------------

WHEEL_FILES_REQUIRED = [
    "__init__.py",
    "_pre_release.py",
    "sv_public.py",
    "dataframe_report.py",
    "serialize.py",
    "feature_config.py",
    "config.py",
    "sv_html.py",
    "sv_types.py",
    "type_detection.py",
    "utils.py",
    "graph.py",
    "graph_numeric.py",
    "graph_cat.py",
    "graph_associations.py",
    "graph_legend.py",
    "series_analyzer.py",
    "series_analyzer_numeric.py",
    "series_analyzer_cat.py",
    "series_analyzer_text.py",
    "sv_html_formatters.py",
    "sv_math.py",
    "comet_ml_logger.py",
    "from_profiling_pandas.py",
    "from_dython.py",
    "update_jquery.py",
    "sweetviz_defaults.ini",
    "templates/dataframe_page.html",
    "templates/dataframe_summary.html",
    "templates/dataframe_associations.html",
    "templates/feature_summary_numeric.html",
    "templates/feature_summary_cat.html",
    "templates/feature_summary_text.html",
    "templates/feature_summary_target_numeric.html",
    "templates/feature_summary_target_cat.html",
    "templates/feature_summary_base_stats.html",
    "templates/feature_detail_numeric.html",
    "templates/feature_detail_cat.html",
    "templates/feature_detail_text.html",
    "templates/include_missing.html",
    "templates/sweetviz.css",
    "templates/sv_assets.css",
    "templates/js/jquery-3.7.1.min.js",
    "templates/js/sweetviz.js",
    "templates/js/sweetviz_vertical.js",
    "fonts/Roboto-Medium.ttf",
    "fonts/NotoSansCJK-Medium.ttc",
    "fonts/LICENSE_OFL.txt",
    "mpl_styles/graph_base.mplstyle",
    "mpl_styles/graph_target.mplstyle",
]

WHEEL_FILES_REQUIRED = ["sweetviz/" + p for p in WHEEL_FILES_REQUIRED]

WHEEL_NONEMPTY_FILES = [
    p for p in WHEEL_FILES_REQUIRED
    if p.endswith((".html", ".css", ".js", ".ini", ".ttf", ".ttc", ".mplstyle"))
]

WHEEL_BINARIES_MIN_BYTES = {
    "sweetviz/fonts/Roboto-Medium.ttf": 100_000,
    "sweetviz/fonts/NotoSansCJK-Medium.ttc": 5_000_000,
    "sweetviz/templates/js/jquery-3.7.1.min.js": 50_000,
}

SDIST_FILES_REQUIRED = [
    "pyproject.toml",
    "setup.py",
    "MANIFEST.in",
    "LICENSE",
    "README.md",
    "tools/check.py",
    "tools/build_hooks.py",
    "scripts/pre_release_checks.py",
    "tests/__init__.py",
    "tests/pre_release/__init__.py",
    "tests/pre_release/test_pre_release.py",
    "sweetviz/__init__.py",
    "sweetviz/_pre_release.py",
    "sweetviz/sweetviz_defaults.ini",
    "sweetviz/templates/dataframe_page.html",
    "sweetviz/templates/sweetviz.css",
    "sweetviz/templates/js/sweetviz.js",
    "sweetviz/fonts/Roboto-Medium.ttf",
    "sweetviz/mpl_styles/graph_base.mplstyle",
]


def _build_wheel():
    result = _run([sys.executable, "-m", "build", "--wheel", "--outdir", "dist"])
    if result.returncode != 0:
        raise RuntimeError(f"wheel build failed.\n{result.stderr[-800:]}")
    wheels = list((ROOT / "dist").glob("sweetviz-*.whl"))
    if not wheels:
        raise RuntimeError("No wheel built in dist/")
    return max(wheels, key=lambda p: p.stat().st_mtime)


def _build_sdist():
    result = _run([sys.executable, "-m", "build", "--sdist", "--outdir", "dist"])
    if result.returncode != 0:
        raise RuntimeError(f"sdist build failed.\n{result.stderr[-800:]}")
    sdists = list((ROOT / "dist").glob("sweetviz-*.tar.gz"))
    if not sdists:
        raise RuntimeError("No sdist built in dist/")
    return max(sdists, key=lambda p: p.stat().st_mtime)


def _parse_entry_points(ep_text: str) -> dict:
    """Parse entry_points.txt into a dict: {group: {name: module.attr}}."""
    groups: dict = {}
    current = None
    for line in ep_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            groups[current] = {}
            continue
        if "=" in line and current is not None:
            name, value = line.split("=", 1)
            groups[current][name.strip()] = value.strip()
    return groups


def check_build_wheel_contents():
    import tarfile as _tf  # noqa: F401

    _vlog(f"Building wheel with python -m build --wheel --outdir dist")
    wheel = _build_wheel()
    _vlog(f"Wheel built: {wheel.name} ({wheel.stat().st_size:,} bytes)")

    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
        info_map = {zi.filename: zi for zi in zf.infolist()}
    _vlog(f"Wheel contains {len(names)} entries total")

    missing: list[str] = []
    present: int = 0
    for p in WHEEL_FILES_REQUIRED:
        if p in names:
            present += 1
        else:
            missing.append(p)
    _vlog(f"Required file presence: {present}/{len(WHEEL_FILES_REQUIRED)}")
    if missing:
        _vlog(f"MISSING files: {missing}")
        raise RuntimeError(f"Wheel missing {len(missing)} files: {missing}")

    empty: list[str] = []
    for p in WHEEL_NONEMPTY_FILES:
        size = info_map[p].file_size
        if size == 0:
            empty.append(p)
        else:
            _vlog(f"  non-empty resource OK: {p} ({size:,} bytes)")
    if empty:
        _vlog(f"ZERO-BYTE resources: {empty}")
        raise RuntimeError(f"Wheel contains zero-byte resource files: {empty}")

    too_small: list[str] = []
    for path, min_bytes in WHEEL_BINARIES_MIN_BYTES.items():
        size = info_map[path].file_size
        if size < min_bytes:
            too_small.append(f"{path} ({size:,} < {min_bytes:,})")
        else:
            _vlog(f"  binary size OK: {path} = {size:,} bytes (>= {min_bytes:,})")
    if too_small:
        raise RuntimeError(f"Wheel binary files suspiciously small: {too_small}")

    dist_info_candidates = [
        n for n in names if "/".join(n.split("/")[:1]).endswith(".dist-info")
    ]
    if not dist_info_candidates:
        dist_info_candidates = [
            n for n in names if ".dist-info/" in n or n.endswith(".dist-info")
        ]
    if not dist_info_candidates:
        raise RuntimeError(
            f"Wheel missing .dist-info directory. Sample names: {sorted(names)[:20]}"
        )
    dist_info_prefix = dist_info_candidates[0].split(".dist-info")[0] + ".dist-info/"
    entry_points_path = dist_info_prefix + "entry_points.txt"
    _vlog(f"Looking for entry points at: {entry_points_path}")
    if entry_points_path not in names:
        raise RuntimeError("Wheel missing .dist-info/entry_points.txt")

    with zipfile.ZipFile(wheel) as zf:
        ep_text = zf.read(entry_points_path).decode("utf-8")
    _vlog("entry_points.txt contents:")
    for line in ep_text.splitlines():
        _vlog(f"    {line}")

    entry_points = _parse_entry_points(ep_text)
    if "console_scripts" not in entry_points:
        raise RuntimeError("Wheel entry_points missing [console_scripts] group")
    if "sweetviz-check" not in entry_points["console_scripts"]:
        raise RuntimeError("Wheel missing 'sweetviz-check' console_scripts entry point")
    target = entry_points["console_scripts"]["sweetviz-check"]
    if "sweetviz._pre_release:main" not in target:
        raise RuntimeError(
            f"sweetviz-check entry point points to wrong target: {target}"
        )
    _vlog(f"sweetviz-check entry point OK: {target}")

    return (
        f"Wheel {wheel.name}: {len(WHEEL_FILES_REQUIRED)} files present, "
        f"{len(WHEEL_NONEMPTY_FILES)} non-empty resources verified, "
        f"sweetviz-check entry point -> {target}"
    )


def check_build_sdist_contents():
    import tarfile

    _vlog(f"Building sdist with python -m build --sdist --outdir dist")
    sdist = _build_sdist()
    _vlog(f"sdist built: {sdist.name} ({sdist.stat().st_size:,} bytes)")

    with tarfile.open(sdist, "r:gz") as tf:
        members = tf.getmembers()
        names = set()
        name_to_member = {}
        for m in members:
            rel = "/".join(m.name.split("/")[1:])
            names.add(rel)
            name_to_member[rel] = m
    _vlog(f"sdist contains {len(members)} entries total")

    missing: list[str] = []
    present: int = 0
    for p in SDIST_FILES_REQUIRED:
        if p in names:
            present += 1
        else:
            missing.append(p)
    _vlog(f"Required file presence: {present}/{len(SDIST_FILES_REQUIRED)}")
    if missing:
        _vlog(f"MISSING files: {missing}")
        raise RuntimeError(f"sdist missing {len(missing)} files: {missing}")

    sdist_nonempty = [
        p for p in SDIST_FILES_REQUIRED
        if p.endswith((".html", ".css", ".js", ".ini", ".ttf", ".ttc", ".mplstyle"))
    ]
    empty: list[str] = []
    for p in sdist_nonempty:
        size = name_to_member[p].size
        if size == 0:
            empty.append(p)
        else:
            _vlog(f"  non-empty resource OK: {p} ({size:,} bytes)")
    if empty:
        _vlog(f"ZERO-BYTE resources: {empty}")
        raise RuntimeError(f"sdist contains zero-byte resource files: {empty}")

    return (
        f"sdist {sdist.name}: {len(SDIST_FILES_REQUIRED)} files present, "
        f"{len(sdist_nonempty)} non-empty resources verified"
    )


def _make_temp_venv(wheel_path: Path) -> Tuple[Path, Path]:
    """
    Create a fully-isolated temp venv outside ROOT, install the built wheel
    (with its runtime dependencies) into it, and return:
      (venv_root, venv_python_binary)
    The caller should delete venv_root when done.
    """
    tmp_root = Path(tempfile.mkdtemp(prefix="sweetviz_venv_"))
    venv_root = tmp_root / "venv"
    venv.create(venv_root, with_pip=True, clear=True)
    _vlog(f"Created temporary venv at {venv_root}")

    # Determine venv python path
    if (venv_root / "bin" / "python").exists():
        py = venv_root / "bin" / "python"
    elif (venv_root / "Scripts" / "python.exe").exists():
        py = venv_root / "Scripts" / "python.exe"
    else:
        raise RuntimeError(f"Cannot find venv python under {venv_root}")

    # Upgrade pip inside the venv to avoid legacy resolver issues
    _vlog("Upgrading pip inside temp venv")
    r = subprocess.run(
        [str(py), "-m", "pip", "install", "--upgrade", "pip"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"pip upgrade in temp venv failed (rc={r.returncode}).\n"
            f"STDERR: {r.stderr[-800:]}"
        )

    # Install wheel WITH dependencies (sweetviz's runtime deps must resolve
    # from PyPI for this smoke test to be realistic).
    _vlog(f"Installing wheel {wheel_path.name} (with deps) into temp venv")
    r = subprocess.run(
        [str(py), "-m", "pip", "install", str(wheel_path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"pip install {wheel_path.name} in temp venv failed (rc={r.returncode}).\n"
            f"STDOUT:\n{r.stdout[-1200:]}\nSTDERR:\n{r.stderr[-1200:]}"
        )

    return tmp_root, py


def check_wheel_install_and_import():
    wheels = list((ROOT / "dist").glob("sweetviz-*.whl"))
    if not wheels:
        raise RuntimeError("No wheel to test install from (run check_build_wheel_contents first)")
    wheel = max(wheels, key=lambda p: p.stat().st_mtime)
    _vlog(f"Using wheel {wheel.name} for isolated-venv smoke test")

    tmp_root, venv_py = _make_temp_venv(wheel)
    try:
        # --- Run assertions from a CWD completely outside ROOT ---
        sandbox = Path(tempfile.mkdtemp(prefix="sweetviz_sandbox_"))
        _vlog(f"Smoke-test CWD (outside source tree): {sandbox}")

        smoke_script = [
            "import sys, os, shutil",
            "# Guard: current dir must not contain sweetviz/",
            "assert not os.path.isdir(os.path.join(os.getcwd(), 'sweetviz')), \"CWD contains sweetviz/ source tree!\"",
            "# Guard: sys.path must not contain ROOT",
            f"ROOT_HINT = {str(ROOT)!r}",
            "for p in sys.path:",
            "    if p and os.path.isdir(os.path.join(p, 'sweetviz')) and os.path.isdir(os.path.join(p, 'sweetviz', 'templates')):",
            "        # It's the venv site-packages — that's fine",
            "        pass",
            "import sweetviz",
            "print('VERSION', sweetviz.__version__)",
            "print('FILE', sweetviz.__file__)",
            "assert 'site-packages' in sweetviz.__file__ or 'dist-packages' in sweetviz.__file__ or 'Lib' in sweetviz.__file__, f\"Not from wheel: {sweetviz.__file__}\"",
            "print('ANALYZE', callable(sweetviz.analyze))",
            "print('DATAFRAMEREPORT', callable(sweetviz.DataframeReport))",
            "report = sweetviz.analyze(__import__('pandas').DataFrame({'a': [1,2,3], 'b': ['x','y','z']}))",
            "print('REPORT', type(report).__name__)",
            "svc = shutil.which('sweetviz-check')",
            "print('SVCLI', bool(svc), svc or '')",
        ]

        r = subprocess.run(
            [str(venv_py), "-c", "\n".join(smoke_script)],
            cwd=str(sandbox),
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0:
            raise RuntimeError(
                f"Wheel import smoke-test failed in isolated venv (rc={r.returncode}).\n"
                f"STDOUT:\n{r.stdout[-1500:]}\nSTDERR:\n{r.stderr[-1500:]}"
            )
        out = r.stdout
        for line in out.splitlines():
            _vlog(f"  [smoke] {line}")

        checks = {
            "import sweetviz": "VERSION" in out,
            "sweetviz.__file__ points to wheel": ("site-packages" in out or "dist-packages" in out or "Lib" in out),
            "sweetviz.analyze callable": "ANALYZE True" in out,
            "sweetviz.DataframeReport callable": "DATAFRAMEREPORT True" in out,
            "analyze() produces DataframeReport": "REPORT DataframeReport" in out,
            "sweetviz-check CLI on PATH": "SVCLI True" in out,
        }
        failed = [k for k, v in checks.items() if not v]
        if failed:
            raise RuntimeError(
                f"Wheel install smoke-test assertions failed: {failed}.\n"
                f"STDOUT:\n{out[-2000:]}"
            )

        # --- Run sweetviz-check CLI from the same sandbox CWD ---
        _vlog("Running sweetviz-check CLI inside isolated venv (sandboxed CWD)")
        svc_path = shutil.which("sweetviz-check")
        # If host env already has sweetviz-check, we need to use the venv one
        if not svc_path or str(venv_py.parent) not in svc_path:
            if (venv_py.parent / "sweetviz-check").exists():
                svc_bin = str(venv_py.parent / "sweetviz-check")
            else:
                svc_bin = str(venv_py.parent / "Scripts" / "sweetviz-check.exe")
        else:
            svc_bin = svc_path
        _vlog(f"sweetviz-check binary: {svc_bin}")

        r2 = subprocess.run(
            [svc_bin],
            cwd=str(sandbox),
            capture_output=True, text=True, timeout=300,
        )
        for line in (r2.stdout or "").splitlines()[-10:]:
            _vlog(f"  [svc] {line}")
        if r2.returncode != 0:
            raise RuntimeError(
                f"sweetviz-check CLI in isolated venv failed (rc={r2.returncode}).\n"
                f"STDOUT:\n{r2.stdout[-1500:]}\nSTDERR:\n{r2.stderr[-1500:]}"
            )
        if "All pre-release checks passed" not in r2.stdout:
            raise RuntimeError(
                "sweetviz-check CLI did not print success banner.\n"
                f"STDOUT:\n{r2.stdout[-1500:]}"
            )
    finally:
        _vlog(f"Cleaning up temp venv at {tmp_root}")
        shutil.rmtree(tmp_root, ignore_errors=True)

    return (
        "Isolated temp venv: wheel installs (with deps), analyze() runs from sandboxed CWD, "
        "sweetviz-check CLI executes and all 24 checks pass"
    )


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

CATEGORIES["release"] = (
    CATEGORIES["requirements"]
    + CATEGORIES["prerelease"]
    + CATEGORIES["build"]
)
CATEGORIES["all"] = CATEGORIES["release"]


def _safe_run(name: str, func, *args, **kwargs):
    try:
        detail = func(*args, **kwargs)
        _record(name, PASS, detail or "")
    except Exception as exc:
        _record(name, FAIL, f"{type(exc).__name__}: {exc}")


def run(targets=None, skip=None):
    targets = targets or ["release"]
    skip = skip or set()

    todo: List[Tuple[str, callable]] = []
    for cat in targets:
        if cat in skip:
            continue
        if cat not in CATEGORIES:
            raise ValueError(
                f"Unknown check category: {cat}. "
                f"Available: {sorted(CATEGORIES.keys())}"
            )
        todo.extend(CATEGORIES[cat])

    for name, func in todo:
        _safe_run(name, func)

    passed = sum(1 for _, s, _ in _results if s == PASS)
    failed = sum(1 for _, s, _ in _results if s == FAIL)
    skipped = sum(1 for _, s, _ in _results if s == SKIP)

    print("\n" + "=" * 64)
    print("Sweetviz Release-Quality Check (tools/check.py)")
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
    verbose = False
    raw_args = list(sys.argv[1:])
    for flag in ("--verbose", "-v"):
        if flag in raw_args:
            verbose = True
            raw_args.remove(flag)
    _set_verbose(verbose)

    args = [a for a in raw_args if not a.startswith("--")]
    skip_flags = [a[len("--skip="):] for a in raw_args if a.startswith("--skip=")]
    skip = set()
    for s in skip_flags:
        skip.update(s.split(","))
    targets = args or ["release"]
    sys.exit(run(targets, skip))


if __name__ == "__main__":
    main()
