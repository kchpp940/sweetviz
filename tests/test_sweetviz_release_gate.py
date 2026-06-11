"""
pytest shim for the sweetviz pre-release gate.

Allows the full release-quality gate to be invoked via:

    pytest -k sweetviz_release_gate
    pytest -k sweetviz_examples
    pytest -k sweetviz_doc_consistency

The actual implementation lives in tools/check.py so that the same exact code
path is exercised by developers (CLI), CI (GitHub Actions), and the test
suite (pytest).  All three must agree – this prevents any drift between
where README / docs / notebooks point and what the check runner actually
tests.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make sure 'tools' package is on sys.path even when pytest is invoked from
# the repo root and 'tools' isn't installed as a package.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.check import (  # noqa: E402  (import after sys.path tweak)
    gate_examples,
    gate_doc_consistency,
    gate_release,
)


OUTPUT_DIR = REPO_ROOT / "sweetviz_example_outputs"


@pytest.mark.slow
@pytest.mark.sweetviz_release_gate
def test_sweetviz_examples_render(tmp_path_factory):
    """Analyze/compare/target/feature_config/HTML/JSON/notebook all render."""
    out_dir = tmp_path_factory.mktemp("sweetviz-examples")
    result = gate_examples(output_dir=out_dir, api_verbosity="off")
    assert result.passed, (
        f"example runner produced {sum(1 for c in result.checks if not c.passed)}"
        f" failing sub-checks:\n"
        + "\n".join(f"  ✗ {c.name}: {c.detail}"
                    for c in result.checks if not c.passed)
    )


@pytest.mark.sweetviz_release_gate
def test_sweetviz_doc_consistency():
    """README + notebooks + example scripts only reference the unified runner."""
    result = gate_doc_consistency()
    assert result.passed, (
        f"doc consistency produced "
        f"{sum(1 for c in result.checks if not c.passed)} failing sub-checks\n"
        + (result.summary or "")
    )


@pytest.mark.slow
@pytest.mark.sweetviz_release_gate
def test_sweetviz_release_gate(tmp_path_factory):
    """Combined gate – examples AND docs, ANDed together exactly like CI."""
    out_dir = tmp_path_factory.mktemp("sweetviz-release")
    result = gate_release(output_dir=out_dir, api_verbosity="off")
    assert result.passed, (
        "release gate FAILED – see tier breakdown below:\n"
        + (result.summary or "")
        + "\n-- individual failures --\n"
        + "\n".join(f"  ✗ [{c.name.split(']')[0][1:]}] "
                    f"{']'.join(c.name.split(']')[1:]).lstrip()}"
                    f" — {c.detail}"
                    for c in result.checks if not c.passed)
    )
