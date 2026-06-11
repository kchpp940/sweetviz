"""
example_runner.py

Unified, reproducible entry point for all sweetviz examples and demos.

Goals
-----
* All doc, README, notebook, CI, and manual-test flows use the SAME
  small synthetic data sets and the SAME calls.
* New feature development has a single script to run in order to verify
  every public code path still produces expected output.
* Outputs are always written to a single, predictable location
  (``./sweetviz_example_outputs/``) so they can be diffed / cleaned easily.

Public API
----------
:func:`load_dataset`         – return one of the built-in DataFrames
:func:`run_all_examples`     – execute every demo + produce HTML/JSON outputs
:func:`run_analyze`          – single-dataset analyze() demo
:func:`run_compare`          – two-dataset compare() demo
:func:`run_compare_intra`    – compare_intra() demo
:func:`run_with_target`      – analyze() with a boolean / numeric target
:func:`run_with_feature_cfg` – demonstrate FeatureConfig
:func:`run_export_html`      – demonstrate show_html() variants
:func:`run_export_json`      – demonstrate to_json() metadata export
:func:`run_notebook_demo`    – (safe no-op for scripted runs) notebook usage
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from sweetviz.sv_public import analyze, compare, compare_intra
from sweetviz.feature_config import FeatureConfig
from sweetviz.dataframe_report import DataframeReport


# ---------------------------------------------------------------------------
# 1.  Deterministic sample datasets
# ---------------------------------------------------------------------------

_SEED = 42


def _make_titanic_like(n_rows: int = 220, seed: int = _SEED) -> pd.DataFrame:
    """A small, Titanic-like dataset covering NUM / CAT / BOOL / TEXT types."""
    rng = np.random.default_rng(seed)
    n = n_rows

    survived = rng.integers(0, 2, size=n).astype(bool)
    pclass = rng.choice([1, 2, 3], size=n, p=[0.20, 0.25, 0.55]).astype(int)
    sex = rng.choice(["male", "female"], size=n, p=[0.64, 0.36])

    # Age: numeric with some missing values
    age = np.clip(rng.normal(30.0, 13.0, size=n), 0.4, 80.0).round(1)
    age_missing_mask = rng.random(size=n) < 0.08
    age = np.where(age_missing_mask, np.nan, age)

    fare = np.clip(
        np.where(
            pclass == 1,
            rng.normal(85.0, 28.0, size=n),
            np.where(
                pclass == 2,
                rng.normal(32.0, 11.0, size=n),
                rng.normal(15.0, 7.0, size=n),
            ),
        ),
        4.0,
        512.0,
    ).round(2)

    embarked = rng.choice(["S", "C", "Q", None], size=n, p=[0.70, 0.19, 0.09, 0.02])

    # Cabin: text-like, many unique tokens + some empties
    letters = rng.choice(list("ABCDEFG"), size=n)
    numbers = rng.integers(10, 140, size=n)
    cabin_list: List[Optional[str]] = [f"{L}{N}" for L, N in zip(letters, numbers)]
    for idx in np.where(rng.random(size=n) < 0.22)[0]:
        cabin_list[idx] = None

    name_prefix = rng.choice(
        ["Mr.", "Mrs.", "Miss.", "Master.", "Dr.", "Rev."],
        size=n,
        p=[0.52, 0.17, 0.15, 0.06, 0.05, 0.05],
    )
    name_suffix = rng.choice(
        ["Smith", "Brown", "Patel", "Garcia", "Kim", "Okafor", "Silva", "Dubois"],
        size=n,
    )

    return pd.DataFrame(
        {
            "PassengerId": np.arange(1, n + 1),
            "Survived": survived.astype(int),   # bool-style target (0/1 int)
            "Pclass": pclass,
            "Name": [f"{p} {s}" for p, s in zip(name_prefix, name_suffix)],
            "Sex": sex,
            "Age": age,
            "Fare": fare,
            "Embarked": embarked,
            "Cabin": cabin_list,
        }
    )


def _split_train_test(df: pd.DataFrame, seed: int = _SEED) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    mask = rng.random(len(df)) < 0.7
    return df[mask].copy(), df[~mask].copy()


_DATASET_REGISTRY = {
    "titanic_train": lambda: _split_train_test(_make_titanic_like())[0],
    "titanic_test":  lambda: _split_train_test(_make_titanic_like())[1],
    "titanic_full":  lambda: _make_titanic_like(),
}


def load_dataset(name: str = "titanic_full") -> pd.DataFrame:
    """Return a deterministic built-in example DataFrame.

    Parameters
    ----------
    name :
        One of ``"titanic_full"`` (default), ``"titanic_train"``,
        ``"titanic_test"``.
    """
    if name not in _DATASET_REGISTRY:
        raise KeyError(
            f"Unknown example dataset '{name}'. "
            f"Available: {sorted(_DATASET_REGISTRY)}"
        )
    return _DATASET_REGISTRY[name]().copy()


# ---------------------------------------------------------------------------
# 2.  Output directory helpers
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), "sweetviz_example_outputs")


def ensure_output_dir(base_dir: Optional[str] = None) -> str:
    out = base_dir or DEFAULT_OUTPUT_DIR
    os.makedirs(out, exist_ok=True)
    return out


# ---------------------------------------------------------------------------
# 3.  Result dataclass – so callers can inspect programmatically
# ---------------------------------------------------------------------------

@dataclass
class ExampleResult:
    """Holds the result of a single example run."""
    name: str
    report: Optional[DataframeReport]
    outputs: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# 4.  Individual example runners
# ---------------------------------------------------------------------------

def run_analyze(
    output_dir: Optional[str] = None,
    write_html: bool = True,
    write_json: bool = True,
    open_browser: bool = False,
    verbosity: str = "off",
) -> ExampleResult:
    """sv.analyze() on the full Titanic dataset."""
    out = ensure_output_dir(output_dir)
    df = load_dataset("titanic_full")
    result = ExampleResult(name="analyze_basic", report=None)

    try:
        report = analyze(df, verbosity=verbosity)
        result.report = report
        if write_html:
            p = os.path.join(out, "01_analyze_basic_widescreen.html")
            report.show_html(filepath=p, open_browser=open_browser, layout="widescreen")
            result.outputs["html_widescreen"] = p
            p_v = os.path.join(out, "01_analyze_basic_vertical.html")
            report.show_html(filepath=p_v, open_browser=open_browser, layout="vertical")
            result.outputs["html_vertical"] = p_v
        if write_json:
            pj = os.path.join(out, "01_analyze_basic_metadata.json")
            report.to_json(filepath=pj)
            result.outputs["json"] = pj
    except Exception as exc:  # pragma: no cover - debug path
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def run_compare(
    output_dir: Optional[str] = None,
    write_html: bool = True,
    write_json: bool = True,
    open_browser: bool = False,
    verbosity: str = "off",
) -> ExampleResult:
    """sv.compare() – training vs test split, with boolean target Survived."""
    out = ensure_output_dir(output_dir)
    df_train = load_dataset("titanic_train")
    df_test  = load_dataset("titanic_test")
    result = ExampleResult(name="compare_train_vs_test", report=None)

    try:
        report = compare(
            [df_train, "Train"],
            [df_test,  "Test"],
            target_feat="Survived",
            verbosity=verbosity,
        )
        result.report = report
        if write_html:
            p = os.path.join(out, "02_compare_train_test_widescreen.html")
            report.show_html(filepath=p, open_browser=open_browser, layout="widescreen")
            result.outputs["html_widescreen"] = p
        if write_json:
            pj = os.path.join(out, "02_compare_train_test_metadata.json")
            report.to_json(filepath=pj)
            result.outputs["json"] = pj
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def run_compare_intra(
    output_dir: Optional[str] = None,
    write_html: bool = True,
    write_json: bool = True,
    open_browser: bool = False,
    verbosity: str = "off",
) -> ExampleResult:
    """sv.compare_intra() – split by Sex == 'male' vs female."""
    out = ensure_output_dir(output_dir)
    df = load_dataset("titanic_full")
    result = ExampleResult(name="compare_intra_male_vs_female", report=None)

    try:
        report = compare_intra(
            df,
            df["Sex"] == "male",
            ["Male", "Female"],
            target_feat="Survived",
            verbosity=verbosity,
        )
        result.report = report
        if write_html:
            p = os.path.join(out, "03_compare_intra_sex_widescreen.html")
            report.show_html(filepath=p, open_browser=open_browser, layout="widescreen")
            result.outputs["html_widescreen"] = p
        if write_json:
            pj = os.path.join(out, "03_compare_intra_sex_metadata.json")
            report.to_json(filepath=pj)
            result.outputs["json"] = pj
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def run_with_target(
    output_dir: Optional[str] = None,
    write_html: bool = True,
    write_json: bool = True,
    open_browser: bool = False,
    verbosity: str = "off",
) -> ExampleResult:
    """analyze() with a numeric target (Fare) – exercises target analysis code."""
    out = ensure_output_dir(output_dir)
    df = load_dataset("titanic_full")
    # Fare has no NaN in our synthetic set – safe as numeric target
    result = ExampleResult(name="analyze_with_numeric_target", report=None)

    try:
        report = analyze(
            df,
            target_feat="Fare",  # numeric target
            verbosity=verbosity,
        )
        result.report = report
        if write_html:
            p = os.path.join(out, "04_analyze_target_fare_widescreen.html")
            report.show_html(filepath=p, open_browser=open_browser, layout="widescreen")
            result.outputs["html_widescreen"] = p
            p_v = os.path.join(out, "04_analyze_target_fare_vertical.html")
            report.show_html(filepath=p_v, open_browser=open_browser, layout="vertical")
            result.outputs["html_vertical"] = p_v
        if write_json:
            pj = os.path.join(out, "04_analyze_target_fare_metadata.json")
            report.to_json(filepath=pj)
            result.outputs["json"] = pj
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def run_with_feature_cfg(
    output_dir: Optional[str] = None,
    write_html: bool = True,
    write_json: bool = True,
    open_browser: bool = False,
    verbosity: str = "off",
) -> ExampleResult:
    """Demonstrate FeatureConfig: skip an id col, force types for some cols."""
    out = ensure_output_dir(output_dir)
    df = load_dataset("titanic_full")
    result = ExampleResult(name="analyze_with_feature_config", report=None)

    try:
        fc = FeatureConfig(
            skip="PassengerId",
            force_cat=["Pclass"],           # int that should really be ordinal/cat
            force_text=["Cabin", "Name"],  # text-ish columns
            feature_names={"Fare": "TicketFareUSD"},  # custom display name
        )
        report = analyze(
            df,
            target_feat="Survived",
            feat_cfg=fc,
            verbosity=verbosity,
        )
        result.report = report
        if write_html:
            p = os.path.join(out, "05_analyze_feature_config.html")
            report.show_html(filepath=p, open_browser=open_browser, layout="widescreen")
            result.outputs["html_widescreen"] = p
        if write_json:
            pj = os.path.join(out, "05_analyze_feature_config_metadata.json")
            report.to_json(filepath=pj)
            result.outputs["json"] = pj
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def run_export_html(
    output_dir: Optional[str] = None,
    open_browser: bool = False,
    verbosity: str = "off",
    write_html: bool = True,
    write_json: bool = True,
) -> ExampleResult:
    """Exercises every combination of layout + scale for show_html()."""
    out = ensure_output_dir(output_dir)
    df = load_dataset("titanic_full")
    result = ExampleResult(name="export_html_variants", report=None)

    try:
        report = analyze(df, target_feat="Survived", verbosity=verbosity)
        result.report = report

        variants = [
            ("06_html_widescreen_scale_1p0", "widescreen", 1.0),
            ("06_html_widescreen_scale_0p8", "widescreen", 0.8),
            ("06_html_vertical_scale_1p0",   "vertical",   1.0),
            ("06_html_vertical_scale_0p9",   "vertical",   0.9),
        ]
        for fname, layout, scale in variants:
            p = os.path.join(out, f"{fname}.html")
            report.show_html(filepath=p, open_browser=open_browser,
                             layout=layout, scale=scale)
            result.outputs[f"html_{layout}_scale_{scale}"] = p
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def run_export_json(
    output_dir: Optional[str] = None,
    verbosity: str = "off",
    write_html: bool = True,
    write_json: bool = True,
    open_browser: bool = False,
) -> ExampleResult:
    """Exercises to_json() with and without drift analysis."""
    out = ensure_output_dir(output_dir)
    df_train = load_dataset("titanic_train")
    df_test  = load_dataset("titanic_test")
    result = ExampleResult(name="export_json_metadata", report=None)

    try:
        # Compare-report so drift fields are populated
        report = compare(
            [df_train, "Train"],
            [df_test,  "Test"],
            target_feat="Survived",
            verbosity=verbosity,
        )
        result.report = report

        p_all = os.path.join(out, "07_metadata_with_drift.json")
        report.to_json(filepath=p_all, include_drift=True)
        result.outputs["json_with_drift"] = p_all

        p_no_drift = os.path.join(out, "07_metadata_no_drift.json")
        report.to_json(filepath=p_no_drift, include_drift=False)
        result.outputs["json_no_drift"] = p_no_drift

        # Validate JSON is actually parseable
        for p in (p_all, p_no_drift):
            with open(p, "r", encoding="utf-8") as fh:
                json.load(fh)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    return result


def run_notebook_demo(
    output_dir: Optional[str] = None,
    verbosity: str = "off",
    open_browser: bool = False,
    write_html: bool = True,
    write_json: bool = True,
) -> ExampleResult:
    """Safe-for-CI notebook-usage demo.

    We never actually invoke IPython from the runner, but we *do* exercise
    the same code path that builds the iFrame payload by calling
    ``show_notebook()`` with ``filepath`` set (so a matching HTML file is
    written alongside the notebook-targeted rendering).  The iFrame itself
    is only useful inside a real kernel.
    """
    out = ensure_output_dir(output_dir)
    df = load_dataset("titanic_full")
    result = ExampleResult(name="notebook_demo", report=None)

    try:
        report = analyze(df, target_feat="Survived", verbosity=verbosity)
        result.report = report

        # Write the companion HTML only – avoid triggering IPython.display
        fp_wide = os.path.join(out, "08_notebook_companion_widescreen.html")
        fp_vert = os.path.join(out, "08_notebook_companion_vertical.html")

        # We can't display() in a script, but we CAN make sure the
        # file-output branch of show_notebook() still works:
        report.show_notebook(
            w="100%",
            h=700,
            scale=0.9,
            layout="widescreen",
            filepath=fp_wide,
            file_layout="widescreen",
            file_scale=1.0,
        )
        result.outputs["notebook_file_widescreen"] = fp_wide

        report.show_notebook(
            w="100%",
            h="Full",
            scale=0.85,
            layout="vertical",
            filepath=fp_vert,
            file_layout="vertical",
            file_scale=1.0,
        )
        result.outputs["notebook_file_vertical"] = fp_vert
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"

    return result


# ---------------------------------------------------------------------------
# 5.  Top-level orchestration
# ---------------------------------------------------------------------------

RUNNERS = {
    "analyze":            run_analyze,
    "compare":            run_compare,
    "compare_intra":      run_compare_intra,
    "target":             run_with_target,
    "feature_config":     run_with_feature_cfg,
    "html":               run_export_html,
    "json":               run_export_json,
    "notebook":           run_notebook_demo,
}


def run_all_examples(
    output_dir: Optional[str] = None,
    open_browser: bool = False,
    verbose: bool = True,
    verbosity_api: str = "off",
) -> Dict[str, ExampleResult]:
    """Run every registered example and write outputs to ``output_dir``.

    Returns a dict of :class:`ExampleResult` keyed by example name.
    """
    out = ensure_output_dir(output_dir)
    if verbose:
        print(f"[sweetviz example_runner] Writing outputs to: {out}")

    results: Dict[str, ExampleResult] = {}
    for name, runner in RUNNERS.items():
        if verbose:
            print(f"  • {name} … ", end="", flush=True)
        r = runner(output_dir=out, open_browser=open_browser,
                   verbosity=verbosity_api)
        results[name] = r
        if verbose:
            print("OK" if r.ok else f"FAIL – {r.error}")

    if verbose:
        oks = sum(1 for r in results.values() if r.ok)
        print(f"\nDone. {oks}/{len(results)} examples passed.")
        for name, r in results.items():
            if r.ok and r.outputs:
                for label, path in r.outputs.items():
                    print(f"  - {name:18s} [{label:20s}] -> {path}")

    return results


# ---------------------------------------------------------------------------
# 6.  Command-line entry point: `python -m sweetviz.example_runner`
# ---------------------------------------------------------------------------

def _parse_args(argv: Optional[List[str]] = None) -> Dict[str, Any]:
    import argparse
    parser = argparse.ArgumentParser(
        description="Run the complete sweetviz example suite.",
    )
    parser.add_argument(
        "examples",
        nargs="*",
        help="Examples to run (default: all). Choices: "
             + ", ".join(sorted(RUNNERS)),
    )
    parser.add_argument(
        "-o", "--output-dir", default=None,
        help="Directory to write HTML/JSON into (default: ./sweetviz_example_outputs)",
    )
    parser.add_argument(
        "--open-browser", action="store_true",
        help="Open every generated HTML report in the default browser.",
    )
    parser.add_argument(
        "--api-verbosity", default="off",
        choices=["off", "progress_only", "full"],
        help="Verbosity for the sweetviz analyze/compare calls themselves.",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress the runner's own progress output.",
    )
    ns = parser.parse_args(argv)

    selected = ns.examples or list(RUNNERS.keys())
    unknown = [e for e in selected if e not in RUNNERS]
    if unknown:
        parser.error(f"Unknown example(s): {unknown}. "
                     f"Choose from: {sorted(RUNNERS)}")

    return {
        "selected": selected,
        "output_dir": ns.output_dir,
        "open_browser": ns.open_browser,
        "api_verbosity": ns.api_verbosity,
        "verbose": not ns.quiet,
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    out = ensure_output_dir(args["output_dir"])

    if args["verbose"]:
        print(f"[sweetviz example_runner] Output dir: {out}")
        print(f"  Selected: {', '.join(args['selected'])}")

    results: Dict[str, ExampleResult] = {}
    for name in args["selected"]:
        runner = RUNNERS[name]
        if args["verbose"]:
            print(f"  → {name} … ", end="", flush=True)
        r = runner(output_dir=out,
                   open_browser=args["open_browser"],
                   verbosity=args["api_verbosity"])
        results[name] = r
        if args["verbose"]:
            if r.ok:
                extra = ""
                if r.outputs:
                    extra = f" ({len(r.outputs)} file(s))"
                print("OK" + extra)
            else:
                print(f"FAIL – {r.error}")

    failed = [name for name, r in results.items() if not r.ok]
    if args["verbose"]:
        total = len(results)
        passed = total - len(failed)
        print(f"\nResult: {passed}/{total} passed" +
              (f"; FAILED: {', '.join(failed)}" if failed else "."))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
