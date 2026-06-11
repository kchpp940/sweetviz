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
import re
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
# 4.  The 'doc_consistency' gate – ensure README / notebooks only reference
#     the unified example_runner and never fall back to bespoke examples
# ---------------------------------------------------------------------------

@dataclass
class SnippetViolation:
    """A single violation found inside a code snippet."""
    file: Path
    line: int              # 1-based line number inside the source file
    snippet_index: int     # which code block in the file (0-based)
    rule_id: str
    message: str

    def format(self) -> str:
        return (
            f"{self.file}:{self.line} "
            f"[{self.rule_id}, block #{self.snippet_index}] {self.message}"
        )


# — Rules —
# Each rule is (id, description, predicate(text, surrounding_context) -> Optional[str] message).
# Returning None means "no violation".
#
# Permissiveness philosophy:
#   OK  – pure API docs that say `sv.analyze(my_dataframe)` with placeholder vars.
#   BAD – any code snippet that:
#      (a) fabricates its own demo DataFrame
#      (b) hard-codes a bespoke output path (not sweetviz_example_outputs/ nor example_runner)
#      (c) shows a full end-to-end without pointing to sweetviz.example_runner

_OLD_OUTPUT_PATHS = (
    "SWEETVIZ_REPORT",                 # default fallbacks
    "sweetviz_report",
    "report.html",
    "_output.html",                    # historical dev files
    "_test_output",
    "_verify_report",
    "_validate_",
    "_check_",
)

_INLINE_DATA_PATTERNS = (
    "pd.DataFrame({",                  # inline dict-style construction
    "pd.DataFrame([",                  # inline list-of-rows
    "pd.read_csv(",                    # bespoke CSV data
    "pd.read_excel(",
    "sklearn.datasets.load_iris",      # third-party data sets
    "sklearn.datasets.load_digits",
    "sklearn.datasets.load_wine",
    "sklearn.datasets.load_breast",
    "seaborn.load_dataset(",
    "np.random.rand(",                 # ad-hoc numpy-data construction
    "np.arange(",
)


def _iter_python_snippets_from_markdown(text: str) -> List[Tuple[int, int, str]]:
    """Return ``(start_line, snippet_index, code)`` for every ```python fenced block."""
    lines = text.splitlines()
    snippets: List[Tuple[int, int, str]] = []
    i = 0
    idx = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```python") or line.startswith("``` {.python}"):
            block_start_line = i + 1  # fence line
            i += 1
            buf: List[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            snippets.append((block_start_line + 1, idx, "\n".join(buf)))
            idx += 1
        i += 1
    return snippets


def _iter_python_from_ipynb(path: Path) -> List[Tuple[int, int, str]]:
    """Return code-cells as snippets for an .ipynb file."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            nb = json.load(fh)
    except Exception:
        return []
    cells = nb.get("cells", []) if isinstance(nb, dict) else []
    out: List[Tuple[int, int, str]] = []
    line_cursor = 1  # approximate; ipynb is JSON so line numbers are fuzzy
    cell_idx = 0
    for c in cells:
        if c.get("cell_type") != "code":
            line_cursor += 1
            continue
        src = c.get("source", [])
        if isinstance(src, list):
            code = "".join(src)
        else:
            code = str(src)
        out.append((line_cursor, cell_idx, code))
        cell_idx += 1
        line_cursor += code.count("\n") + 2
    return out


def _scan_snippet(
    file: Path,
    start_line: int,
    snippet_index: int,
    code: str,
) -> List[SnippetViolation]:
    """Apply every rule to a single Python code snippet."""
    violations: List[SnippetViolation] = []

    # Determine whether this snippet is pure API documentation.
    # A snippet is considered "not a self-contained demo" (and therefore exempt
    # from data- and path-rules) when ANY of the following holds:
    #   - it uses well-known placeholder variable names
    #   - it looks like a function signature / default-argument listing
    #     (i.e. contains "param='...'" style defaults but no actual sweetviz calls)
    references_runner = (
        "sweetviz.example_runner" in code
        or "from sweetviz.example_runner" in code
        or "example_runner" in code
    )
    has_placeholder_vars = (
        "my_dataframe" in code
        or ("test_df" in code and "sv.load_dataset" not in code and not references_runner)
    )
    looks_like_signature = (
        # Function signature / default-param block – contains param=value on its
        # own line(s), no `sv.` calls, no `import`.
        re.search(r"\w+\s*=\s*['\"]", code) is not None
        and "sv." not in code
        and "import " not in code
    )
    is_placeholder = has_placeholder_vars or looks_like_signature or references_runner

    # --- Rule 1: must never fabricate inline demo data -----------------------
    for pat in _INLINE_DATA_PATTERNS:
        if pat in code:
            violations.append(SnippetViolation(
                file, start_line, snippet_index, "DOC-DATA",
                f"contains '{pat}' — demo data should come from "
                "sweetviz.example_runner.load_dataset() instead."
            ))
            break  # only one data-construction warning per block

    # --- Rule 2: must never use legacy bespoke output paths -----------------
    # Exemptions: pure API-documentation snippets that use placeholder vars
    # (e.g. `my_dataframe`) are allowed to mention the default filename
    # 'SWEETVIZ_REPORT.html' in comments/signature strings.
    if not is_placeholder:
        for pat in _OLD_OUTPUT_PATHS:
            if pat.lower() in code.lower():
                violations.append(SnippetViolation(
                    file, start_line, snippet_index, "DOC-PATH",
                    f"uses legacy output path '{pat}' — outputs should be written "
                    "through sweetviz.example_runner into sweetviz_example_outputs/."
                ))
                break

    if references_runner or is_placeholder:
        # Allowed: either explicitly using the unified runner, or it is an
        # API-docs snippet that only uses placeholder variable names.
        return violations

    # --- Rule 3: end-to-end blocks must reference the runner or use ---------
    #     placeholder vars (caught above, so this is the else branch).
    # Block is neither placeholder-only nor runner-based – it must be an
    # attempt to write a self-contained demo with bespoke state.  Flag it
    # if it contains both a DataFrame source + sweetviz API call.
    has_data_ref = (
        any(var + "." in code or f"[{var}]" in code
            for var in ("df", "train", "data", "dataset", "df_train", "df_test"))
        or "pd." in code
    )
    has_sv_api = any(api in code for api in (
        "sv.analyze", "sv.compare", "sv.compare_intra",
        "sweetviz.analyze", "sweetviz.compare", "sweetviz.compare_intra",
        ".show_html(", ".show_notebook(", ".to_json(",
    ))
    if has_data_ref and has_sv_api:
        violations.append(SnippetViolation(
            file, start_line, snippet_index, "DOC-DEMO",
            "self-contained demo does not reference sweetviz.example_runner — "
            "either use placeholder vars (e.g. `my_dataframe`) for pure API docs, "
            "or import from `sweetviz.example_runner` for runnable examples."
        ))

    return violations


def _scan_file(path: Path) -> List[SnippetViolation]:
    violations: List[SnippetViolation] = []
    suffix = path.suffix.lower()
    if suffix == ".md":
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        for start_line, idx, code in _iter_python_snippets_from_markdown(text):
            violations.extend(_scan_snippet(path, start_line, idx, code))
    elif suffix == ".ipynb":
        for start_line, idx, code in _iter_python_from_ipynb(path):
            violations.extend(_scan_snippet(path, start_line, idx, code))
    elif suffix == ".py":
        # Standalone example scripts (NOT part of the sweetviz package or tools).
        # Only scan files that look like demos: anything in examples/, or at
        # repo root with 'demo' or 'example' in the name.
        rel = path.relative_to(REPO_ROOT)
        parts = rel.parts
        is_example_script = (
            parts[0] in {"examples", "scripts", "demos"}
            or ("example" in path.name.lower() or "demo" in path.name.lower())
        )
        if not is_example_script:
            return violations
        with open(path, "r", encoding="utf-8") as fh:
            code = fh.read()
        violations.extend(_scan_snippet(path, 1, 0, code))
    return violations


def _discover_doc_files() -> List[Path]:
    """Yield every README / doc / notebook / example-script to scan."""
    paths: List[Path] = []
    # README + markdown in docs/
    for pat in ("README.md", "README*.md", "CHANGELOG.md"):
        paths.extend(sorted(REPO_ROOT.glob(pat)))
    for md in (REPO_ROOT / "docs").rglob("*.md") if (REPO_ROOT / "docs").exists() else []:
        paths.append(md)
    # Notebooks anywhere in repo (but not in node_modules / build dirs)
    for nb in REPO_ROOT.rglob("*.ipynb"):
        rel = nb.relative_to(REPO_ROOT)
        if any(part in ("node_modules", ".venv", "venv", "build", "dist", ".git")
               for part in rel.parts):
            continue
        paths.append(nb)
    # Example scripts (loose)
    for root_name in ("examples", "demos", "scripts"):
        root = REPO_ROOT / root_name
        if root.exists():
            paths.extend(sorted(root.rglob("*.py")))
    # Any *example*.py / *demo*.py at repo root
    for pat in ("*example*.py", "*demo*.py"):
        paths.extend(sorted(REPO_ROOT.glob(pat)))
    # De-duplicate while preserving order
    seen: set = set()
    uniq: List[Path] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def gate_doc_consistency(
    output_dir: Optional[Path] = None,
    keep_existing: bool = False,
    api_verbosity: str = "off",
) -> GateResult:
    """Scan README / docs / notebooks / example scripts for demo drift.

    A demo is *consistent* when it either:
      (a) uses placeholder variable names like ``my_dataframe`` (pure API docs), OR
      (b) explicitly imports from ``sweetviz.example_runner``.

    Any other self-contained demo snippet is a drift risk and is flagged.
    """
    result = GateResult(name="DOC_CONSISTENCY — README + notebooks only reference unified runner")

    files = _discover_doc_files()

    # --- Sub-check 1: at least one tracked file exists -----------------------
    result.add(
        "At least one doc/example file is tracked for scanning",
        len(files) > 0,
        f"found {len(files)} file(s): " + ", ".join(
            f.name for f in files[:6]) + (" …" if len(files) > 6 else ""),
    )

    # --- Sub-check 2: scan every file ----------------------------------------
    all_violations: List[SnippetViolation] = []
    for path in files:
        try:
            vs = _scan_file(path)
        except Exception as exc:  # pragma: no cover – paranoid
            result.add(f"Scan {path.name}", False, f"scan error: {exc!r}")
            continue
        all_violations.extend(vs)
        result.add(
            f"{path.relative_to(REPO_ROOT)} — no demo drift",
            len(vs) == 0,
            f"{len(vs)} violation(s)" if vs else "OK",
        )

    # --- Sub-check 3: zero violations overall --------------------------------
    rule_breakdown: Dict[str, int] = {}
    for v in all_violations:
        rule_breakdown[v.rule_id] = rule_breakdown.get(v.rule_id, 0) + 1
    result.add(
        "0 demo-drift violations across all tracked files",
        len(all_violations) == 0,
        (f"{len(all_violations)} total — "
         + (", ".join(f"{k}×{v}" for k, v in sorted(rule_breakdown.items()))
            if rule_breakdown else "clean")),
    )

    # Build human-readable detail
    if all_violations:
        preview = "\n".join(f"    • {v.format()}" for v in all_violations[:20])
        extra = "" if len(all_violations) <= 20 else (
            f"\n    … and {len(all_violations) - 20} more"
        )
        result.summary = (
            f"Found {len(all_violations)} demo-drift violation(s).\n"
            f"Violations:\n{preview}{extra}\n\n"
            "Fix by:\n"
            "  (1) replacing bespoke data with sweetviz.example_runner.load_dataset(),\n"
            "  (2) routing outputs through sweetviz_example_outputs/ via the runner,\n"
            "  (3) or, for pure API docs, using placeholder names like `my_dataframe`."
        )
    else:
        result.summary = (
            f"Scanned {len(files)} file(s). All demo code either references\n"
            "sweetviz.example_runner or uses placeholder variable names."
        )
    return result


# ---------------------------------------------------------------------------
# 5.  The 'release' gate – EVERY tier must pass (AND)
# ---------------------------------------------------------------------------

def gate_release(**kw) -> GateResult:
    """Full pre-release gate – runs every tier of checks.

    All tiers are AND-ed together: any single failure causes the overall
    gate to fail.  This is the entry point used by CI (see
    ``.github/workflows/pre-release.yml``) and by any local release script.
    """
    out_dir = kw.get("output_dir")
    keep = kw.get("keep_existing", False)
    verbosity = kw.get("api_verbosity", "off")

    result = GateResult(name="RELEASE — full pre-release gate (all tiers must pass)")

    # -- Tier 1: examples (end-to-end rendering artefacts) -------------------
    ex = gate_examples(output_dir=out_dir, keep_existing=keep,
                       api_verbosity=verbosity)
    for c in ex.checks:
        c.name = f"[examples] {c.name}"
        result.checks.append(c)
    if not ex.passed:
        result.exit_code = 1

    # -- Tier 2: doc consistency (README + notebooks don't drift) ------------
    doc = gate_doc_consistency()
    for c in doc.checks:
        c.name = f"[docs]     {c.name}"
        result.checks.append(c)
    if not doc.passed:
        result.exit_code = 1

    # -- (future tiers here: build, import, jsdom, …) -------------------------

    # -- Combined summary -----------------------------------------------------
    tiers = [("examples", ex.passed), ("doc_consistency", doc.passed)]
    passing = sum(1 for _, ok in tiers if ok)
    total = len(tiers)
    tier_line = ", ".join(
        f"{name}: {'PASS' if ok else 'FAIL'}" for name, ok in tiers
    )
    result.summary = (
        f"Tier summary [{passing}/{total} passed]: {tier_line}\n"
        f"Output directory: {(out_dir or DEFAULT_OUTPUT_DIR)}\n"
        + (
            "All release gates passed — safe to build and publish.\n"
            if result.passed else
            "RELEASE GATE FAILED — fix failing tier(s) above before publishing.\n"
        )
        + ("\n-- examples note --\n" + ex.summary if ex.summary else "")
        + ("\n-- docs note --\n"     + doc.summary if doc.summary else "")
    )
    return result


# ---------------------------------------------------------------------------
# 6.  CLI
# ---------------------------------------------------------------------------

GATES: Dict[str, Callable[..., GateResult]] = {
    "examples":          gate_examples,
    "doc_consistency":   gate_doc_consistency,
    "release":           gate_release,
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
