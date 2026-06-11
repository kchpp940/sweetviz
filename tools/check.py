"""
tools/check.py
==============

Pre-release / CI / local quality gate for sweetviz.

Commands
--------
``tools/check.py examples``
    Run the unified ``sweetviz.example_runner`` against the built-in demo
    data and assert that every expected artefact is produced (HTML variants,
    notebook companion HTML, JSON metadata with and without drift).
    This is the *single source of truth* for "does the library still render
    end-to-end" – README examples, notebooks, and docs all agree with it.

``tools/check.py release``
    Full pre-release check.  Currently runs the ``examples`` gate.  Can be
    extended with package-build, import, or baseline-report comparisons.

The script intentionally lives outside the ``sweetviz`` package and is *not*
distributed to end users (it is developer tooling only).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
"""Absolute path to the sweetviz repository root."""

DEFAULT_OUTPUT_DIR = REPO_ROOT / "sweetviz_example_outputs"


# ---------------------------------------------------------------------------
# 1.  Structured result types
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Result of a single (sub-)check."""
    name: str
    passed: bool
    detail: str = ""

    def print(self, indent: int = 0) -> None:
        prefix = "  " * indent
        symbol = "✓" if self.passed else "✗"
        print(f"{prefix}{symbol} {self.name} — {self.detail}")


@dataclass
class GateResult:
    """Result of a top-level gate (e.g. 'examples')."""
    name: str
    checks: List[CheckResult] = field(default_factory=list)
    exit_code: int = 0
    summary: str = ""

    def add(self, name: str, passed: bool, detail: str = "") -> CheckResult:
        c = CheckResult(name=name, passed=passed, detail=detail)
        self.checks.append(c)
        if not passed:
            self.exit_code = 1
        return c

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def print(self) -> None:
        header = f"── {self.name} {'─' * max(3, 60 - len(self.name))}"
        print(header)
        for c in self.checks:
            c.print(indent=1)
        print("─" * len(header))
        oks = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)
        status = "PASS" if self.passed else "FAIL"
        print(f"[{status}] {oks}/{total} sub-checks passed")
        if self.summary:
            print(self.summary)
        print()


# ---------------------------------------------------------------------------
# 2.  Helper utilities
# ---------------------------------------------------------------------------

def _ensure_clean_output_dir(path: Path, keep_existing: bool) -> Path:
    if path.exists() and not keep_existing:
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_subprocess(argv: List[str]) -> subprocess.CompletedProcess:
    """Run a subprocess and capture its output."""
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


def _file_exists_and_not_empty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _is_valid_html(path: Path) -> bool:
    """Very lenient check – the file must contain a ``<!DOCTYPE`` or ``<html``."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(8192).lower()
        return "<!doctype" in head or "<html" in head
    except OSError:
        return False


def _is_valid_json(path: Path, assert_keys: Optional[Tuple[str, ...]] = None) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return False
    if assert_keys:
        if not isinstance(data, dict):
            return False
        return all(k in data for k in assert_keys)
    return True


# ---------------------------------------------------------------------------
# 3.  The 'examples' gate – run sweetviz.example_runner and validate outputs
# ---------------------------------------------------------------------------

# The example runner writes files with fixed, predictable names.  If any of
# these names change in example_runner.py, they must be updated here as well
# (and vice versa) – this coupling is deliberate: it forces documentation,
# README, notebooks, and CI to stay in lock-step.

# Canonical top-level JSON keys produced by DataframeReport.to_json().
# If serialize.py changes these, update both places.
_JSON_KEYS_ANALYZE = ("metadata", "source_summary", "features", "associations")
_JSON_KEYS_COMPARE = _JSON_KEYS_ANALYZE + ("compare_summary",)  # compare-only
_JSON_KEYS_COMPARE_TARGET = _JSON_KEYS_COMPARE + ("target",)    # with target
_JSON_KEYS_DRIFT = ("drift_summary",)


def _has_all_keys(path: Path, keys: Tuple[str, ...]) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    return all(k in data for k in keys)


def _has_any_key_nested(path: Path, needles: Tuple[str, ...]) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return False
    def _walk(node: object) -> bool:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in needles:
                    return True
                if _walk(v):
                    return True
        elif isinstance(node, list):
            for item in node:
                if _walk(item):
                    return True
        return False
    return _walk(data)


EXPECTED_ARTIFACTS: List[Tuple[str, Callable[[Path], bool], str]] = [
    # (filename, validator, label)

    # — analyze() —
    ("01_analyze_basic_widescreen.html", _is_valid_html,
                                                        "analyze · widescreen HTML"),
    ("01_analyze_basic_vertical.html",   _is_valid_html,
                                                        "analyze · vertical HTML"),
    ("01_analyze_basic_metadata.json",
        lambda p: _has_all_keys(p, _JSON_KEYS_ANALYZE),
                                                        "analyze · JSON metadata"),

    # — compare() with boolean target Survived —
    ("02_compare_train_test_widescreen.html", _is_valid_html,
                                                        "compare · widescreen HTML"),
    ("02_compare_train_test_metadata.json",
        lambda p: _has_all_keys(p, _JSON_KEYS_COMPARE_TARGET + _JSON_KEYS_DRIFT),
                                                        "compare · JSON metadata"),

    # — compare_intra() —
    ("03_compare_intra_sex_widescreen.html", _is_valid_html,
                                                        "compare_intra · widescreen HTML"),
    ("03_compare_intra_sex_metadata.json",
        lambda p: _has_all_keys(p, _JSON_KEYS_COMPARE_TARGET + _JSON_KEYS_DRIFT),
                                                        "compare_intra · JSON metadata"),

    # — analyze() with numeric target Fare —
    ("04_analyze_target_fare_widescreen.html", _is_valid_html,
                                                        "target(numeric) · widescreen HTML"),
    ("04_analyze_target_fare_vertical.html",   _is_valid_html,
                                                        "target(numeric) · vertical HTML"),
    ("04_analyze_target_fare_metadata.json",
        lambda p: _has_all_keys(p, _JSON_KEYS_ANALYZE + ("target",)),
                                                        "target(numeric) · JSON metadata"),

    # — FeatureConfig variant —
    ("05_analyze_feature_config.html",   _is_valid_html,
                                                        "FeatureConfig · widescreen HTML"),
    ("05_analyze_feature_config_metadata.json",
        lambda p: _has_all_keys(p, _JSON_KEYS_ANALYZE + ("target",)),
                                                        "FeatureConfig · JSON metadata"),

    # — HTML layout × scale matrix —
    ("06_html_widescreen_scale_1p0.html", _is_valid_html,
                                                        "show_html matrix · wide 1.00"),
    ("06_html_widescreen_scale_0p8.html", _is_valid_html,
                                                        "show_html matrix · wide 0.80"),
    ("06_html_vertical_scale_1p0.html",   _is_valid_html,
                                                        "show_html matrix · vert 1.00"),
    ("06_html_vertical_scale_0p9.html",   _is_valid_html,
                                                        "show_html matrix · vert 0.90"),

    # — JSON metadata drift variants —
    ("07_metadata_with_drift.json",
        lambda p: (_has_all_keys(p, _JSON_KEYS_COMPARE_TARGET + _JSON_KEYS_DRIFT)
                   and _has_any_key_nested(p, ("drift",))),
                                                        "JSON · with drift fields"),
    ("07_metadata_no_drift.json",
        lambda p: (_has_all_keys(p, _JSON_KEYS_COMPARE_TARGET)
                   and not _has_all_keys(p, _JSON_KEYS_DRIFT)
                   and not _has_any_key_nested(p, ("drift",))),
                                                        "JSON · no drift fields"),

    # — show_notebook() filepath branch —
    ("08_notebook_companion_widescreen.html", _is_valid_html,
                                                        "show_notebook · widescreen companion"),
    ("08_notebook_companion_vertical.html",   _is_valid_html,
                                                        "show_notebook · vertical companion"),
]


def gate_examples(
    output_dir: Optional[Path] = None,
    keep_existing: bool = False,
    api_verbosity: str = "off",
) -> GateResult:
    """Run the example runner and validate every expected artefact.

    This is the authoritative end-to-end smoke test for sweetviz:
    README, notebook, and docs examples all rely on the same runner.
    """
    out = _ensure_clean_output_dir(output_dir or DEFAULT_OUTPUT_DIR, keep_existing)
    result = GateResult(
        name="EXAMPLES — sweetviz.example_runner end-to-end smoke test"
    )

    # --- a) Run the example runner ------------------------------------------------
    cmd = [
        sys.executable, "-m", "sweetviz.example_runner",
        "-o", str(out),
        "--api-verbosity", api_verbosity,
    ]
    proc = _run_subprocess(cmd)
    runner_ok = proc.returncode == 0
    result.add(
        "`python -m sweetviz.example_runner` executes cleanly",
        runner_ok,
        (f"exit={proc.returncode}" +
         (f"; stderr: {proc.stderr.strip()[:400]}" if not runner_ok else "")),
    )
    if not runner_ok:
        result.summary = (
            f"Example runner failed with exit code {proc.returncode}.\n"
            f"STDOUT:\n{proc.stdout[-2000:]}\n"
            f"STDERR:\n{proc.stderr[-2000:]}\n"
        )
        return result

    # --- b) Artifact-by-artifact validation ---------------------------------------
    for filename, validator, label in EXPECTED_ARTIFACTS:
        fp = out / filename
        exists = _file_exists_and_not_empty(fp)
        valid = validator(fp) if exists else False
        result.add(
            label,
            exists and valid,
            (f"OK  — {fp.stat().st_size:>8,} B" if (exists and valid) else
             ("MISSING" if not exists else
              f"PRESENT but failed content check ({fp.stat().st_size} B)")),
        )

    # --- c) Structural: drift report MUST be a superset of no-drift ----------------
    drift_json = out / "07_metadata_with_drift.json"
    nodrift_json = out / "07_metadata_no_drift.json"
    if _file_exists_and_not_empty(drift_json) and _file_exists_and_not_empty(nodrift_json):
        try:
            with open(drift_json) as f:
                d = json.load(f)
            with open(nodrift_json) as f:
                n = json.load(f)
            d_keys = set(d.keys()) if isinstance(d, dict) else set()
            n_keys = set(n.keys()) if isinstance(n, dict) else set()
            superset = n_keys.issubset(d_keys)
            result.add(
                "JSON metadata: drift-variant keys ⊇ no-drift keys",
                superset,
                f"drift_keys={sorted(d_keys)}, no_drift_keys={sorted(n_keys)}",
            )
        except Exception as exc:  # pragma: no cover
            result.add("JSON metadata: drift ⊇ no-drift key check", False,
                       f"parse error: {exc!r}")

    # --- d) File count sanity ------------------------------------------------------
    produced = sorted(p.name for p in out.iterdir() if p.is_file())
    result.add(
        f"At least {len(EXPECTED_ARTIFACTS)} artefacts on disk",
        len(produced) >= len(EXPECTED_ARTIFACTS),
        f"produced {len(produced)} files in {out}",
    )

    result.summary = (
        f"All example artefacts written to:\n  {out}\n"
        "To inspect visually: open any 01–08 HTML file in a browser,\n"
        "or run again with:  python tools/check.py examples --open-browser"
    )
    return result


# ---------------------------------------------------------------------------
# 4.  The 'release' gate – superset of all pre-release checks
# ---------------------------------------------------------------------------

def gate_release(**kw) -> GateResult:
    """Full pre-release gate – runs every tier of checks.

    Currently equivalent to ``examples``; intended to be extended with
    package build, import smoke tests, and jsdom-level DOM assertions.
    """
    out_dir = kw.get("output_dir")
    keep = kw.get("keep_existing", False)
    verbosity = kw.get("api_verbosity", "off")

    result = GateResult(name="RELEASE — full pre-release gate")

    ex = gate_examples(output_dir=out_dir, keep_existing=keep,
                       api_verbosity=verbosity)
    for c in ex.checks:
        # Re-emit every sub-check under a namespace so the overall listing
        # is easy to scan.
        result.checks.append(c)
    if not ex.passed:
        result.exit_code = 1

    # TODO: add build / import / jsdom tiers here.

    result.summary = (
        ("All release gates passed.\n" if result.passed else
         "Release gate FAILED — see individual sub-checks above.\n") +
        f"Output directory: {(out_dir or DEFAULT_OUTPUT_DIR)}"
    )
    return result


# ---------------------------------------------------------------------------
# 5.  CLI
# ---------------------------------------------------------------------------

GATES: Dict[str, Callable[..., GateResult]] = {
    "examples": gate_examples,
    "release":  gate_release,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools/check.py",
        description="Sweetviz pre-release / CI quality gates.",
    )
    parser.add_argument(
        "gate", choices=sorted(GATES),
        help="Which check tier to run.  'release' runs every tier.",
    )
    parser.add_argument(
        "-o", "--output-dir", default=None,
        help=f"Override artefact output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--keep-existing", action="store_true",
        help="Do not remove existing output-dir contents before running.",
    )
    parser.add_argument(
        "--api-verbosity", default="off",
        choices=["off", "progress_only", "full"],
        help="Verbosity passed through to sweetviz analyze/compare calls.",
    )
    parser.add_argument(
        "--open-browser", action="store_true",
        help="After a successful run, open one generated HTML file (for local debugging).",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress per-check detail; only print the final status line.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    gate_fn = GATES[args.gate]
    result = gate_fn(
        output_dir=Path(args.output_dir) if args.output_dir else None,
        keep_existing=args.keep_existing,
        api_verbosity=args.api_verbosity,
    )

    if not args.quiet:
        result.print()
    else:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {args.gate}")

    if args.open_browser and result.passed:
        out = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
        showcase = out / "01_analyze_basic_widescreen.html"
        if showcase.is_file():
            try:
                import webbrowser
                webbrowser.open(showcase.as_uri())
            except Exception:
                pass

    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
