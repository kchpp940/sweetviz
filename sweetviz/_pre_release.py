from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import traceback
from typing import List, Tuple

try:
    import importlib.resources as pkg_resources
except ImportError:
    import importlib_resources as pkg_resources


PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

_results: List[Tuple[str, str, str]] = []


def _record(name: str, status: str, detail: str = ""):
    _results.append((name, status, detail))


def _reset():
    global _results
    _results = []


def _safe_run(name: str, func, *args, **kwargs):
    try:
        detail = func(*args, **kwargs)
        _record(name, PASS, detail or "")
    except Exception as exc:
        _record(name, FAIL, f"{type(exc).__name__}: {exc}")
        if os.environ.get("SWEETVIZ_PRERELEASE_VERBOSE"):
            traceback.print_exc()


REQUIRED_TEMPLATES = [
    "dataframe_page.html",
    "dataframe_summary.html",
    "dataframe_associations.html",
    "feature_summary_numeric.html",
    "feature_summary_cat.html",
    "feature_summary_text.html",
    "feature_summary_target_numeric.html",
    "feature_summary_target_cat.html",
    "feature_summary_base_stats.html",
    "feature_detail_numeric.html",
    "feature_detail_cat.html",
    "feature_detail_text.html",
    "include_missing.html",
    "sweetviz.css",
    "sv_assets.css",
]

REQUIRED_JS = [
    "jquery-3.7.1.min.js",
    "sweetviz.js",
    "sweetviz_vertical.js",
]

REQUIRED_FONTS = [
    "Roboto-Medium.ttf",
    "NotoSansCJK-Medium.ttc",
]

REQUIRED_MPL_STYLES = [
    "graph_base.mplstyle",
    "graph_target.mplstyle",
]

REQUIRED_PACKAGE_DATA = [
    "sweetviz_defaults.ini",
]


def _check_resource_readable(package: str, subpath: str, filename: str) -> str:
    try:
        ref = pkg_resources.files(package).joinpath(subpath).joinpath(filename)
        data = ref.read_bytes()
        if len(data) == 0:
            raise ValueError(f"{filename} is empty")
        return f"OK ({len(data)} bytes)"
    except Exception as exc:
        raise RuntimeError(f"Cannot read {package}/{subpath}/{filename}: {exc}") from exc


def check_template_resources():
    missing = []
    for name in REQUIRED_TEMPLATES:
        try:
            _check_resource_readable("sweetviz", "templates", name)
        except Exception:
            missing.append(name)
    for name in REQUIRED_JS:
        try:
            _check_resource_readable("sweetviz", "templates/js", name)
        except Exception:
            missing.append(name)
    if missing:
        raise RuntimeError(f"Missing template resources: {missing}")
    return f"{len(REQUIRED_TEMPLATES)} templates + {len(REQUIRED_JS)} JS files"


def check_font_resources():
    missing = []
    for name in REQUIRED_FONTS:
        try:
            _check_resource_readable("sweetviz", "fonts", name)
        except Exception:
            missing.append(name)
    if missing:
        raise RuntimeError(f"Missing font resources: {missing}")
    return f"{len(REQUIRED_FONTS)} fonts OK"


def check_mpl_style_resources():
    missing = []
    for name in REQUIRED_MPL_STYLES:
        try:
            _check_resource_readable("sweetviz", "mpl_styles", name)
        except Exception:
            missing.append(name)
    if missing:
        raise RuntimeError(f"Missing mpl_style resources: {missing}")
    return f"{len(REQUIRED_MPL_STYLES)} mpl_styles OK"


def check_ini_config():
    for name in REQUIRED_PACKAGE_DATA:
        try:
            ref = pkg_resources.files("sweetviz").joinpath(name)
            data = ref.read_text(encoding="utf-8")
            if not data.strip():
                raise ValueError(f"{name} is empty")
        except Exception as exc:
            raise RuntimeError(f"Cannot read {name}: {exc}") from exc
    return f"{len(REQUIRED_PACKAGE_DATA)} INI files OK"


def check_template_code_consistency():
    from jinja2 import Environment, PackageLoader

    env = Environment(loader=PackageLoader("sweetviz", "templates"))
    on_disk = set(env.list_templates())

    code_referenced = {
        t for t in REQUIRED_TEMPLATES
        if t.endswith(".html")
    }

    missing_from_disk = code_referenced - on_disk
    unused_on_disk = {t for t in on_disk if t.endswith(".html")} - code_referenced

    msgs = []
    if missing_from_disk:
        msgs.append(f"Referenced in code but missing from package: {missing_from_disk}")
    if unused_on_disk:
        msgs.append("On disk but not in required list (may be include-d): " + str(unused_on_disk))
    if msgs:
        raise RuntimeError("; ".join(msgs))
    return f"{len(code_referenced)} HTML templates consistent"


PUBLIC_API = {
    "sweetviz": ["__version__", "__title__", "__license__"],
    "sweetviz.sv_public": ["analyze", "compare", "compare_intra"],
    "sweetviz.feature_config": ["FeatureConfig"],
    "sweetviz.dataframe_report": ["DataframeReport"],
    "sweetviz.config": ["config"],
    "sweetviz.serialize": ["to_json", "build_report_data", "compute_drift"],
}


def check_public_api_imports():
    failures = []
    for module_name, attrs in PUBLIC_API.items():
        try:
            mod = importlib.import_module(module_name)
        except ImportError as exc:
            failures.append(f"Cannot import {module_name}: {exc}")
            continue
        for attr in attrs:
            if not hasattr(mod, attr):
                failures.append(f"{module_name}.{attr} not found")
    if failures:
        raise RuntimeError(f"API import failures: {failures}")
    total = sum(len(v) for v in PUBLIC_API.values())
    return f"{len(PUBLIC_API)} modules, {total} symbols OK"


def check_sweetviz_top_level():
    import sweetviz
    for attr in ("analyze", "compare", "compare_intra", "FeatureConfig",
                 "DataframeReport", "config_parser", "__version__"):
        if not hasattr(sweetviz, attr):
            raise AttributeError(f"sweetviz.{attr} missing from top-level")
    return "7 top-level exports OK"


def _make_df():
    import pandas as pd
    import numpy as np
    np.random.seed(42)
    return pd.DataFrame({
        "num_col": np.random.randn(50),
        "cat_col": np.random.choice(["a", "b", "c"], 50),
        "bool_col": np.random.choice([True, False], 50),
    })


def _make_df_compare():
    import pandas as pd
    import numpy as np
    np.random.seed(99)
    return pd.DataFrame({
        "num_col": np.random.randn(40) + 1,
        "cat_col": np.random.choice(["a", "b", "d"], 40),
        "bool_col": np.random.choice([True, False], 40),
    })


def check_analyze_report():
    import sweetviz
    df = _make_df()
    report = sweetviz.analyze(df)
    if not hasattr(report, "_features"):
        raise RuntimeError("Report missing _features")
    if len(report._features) != 3:
        raise RuntimeError(f"Expected 3 features, got {len(report._features)}")
    return f"3 features analyzed OK"


def check_analyze_with_target():
    import sweetviz
    df = _make_df()
    report = sweetviz.analyze(df, target_feat="num_col")
    if report._target is None:
        raise RuntimeError("Target not set")
    return "Target feature OK"


def check_compare_report():
    import sweetviz
    df1 = _make_df()
    df2 = _make_df_compare()
    report = sweetviz.compare(df1, df2)
    if report.compare_name is None:
        raise RuntimeError("Compare name not set")
    if len(report._features) != 3:
        raise RuntimeError(f"Expected 3 features in compare, got {len(report._features)}")
    return "Compare report OK"


def check_compare_intra_report():
    import sweetviz
    import pandas as pd
    df = _make_df()
    report = sweetviz.compare_intra(
        df, df["bool_col"], ("TrueGroup", "FalseGroup")
    )
    if report.compare_name is None:
        raise RuntimeError("compare_intra: compare_name not set")
    return "compare_intra OK"


def check_feature_config():
    import sweetviz
    df = _make_df()
    fc = sweetviz.FeatureConfig(skip=["bool_col"])
    report = sweetviz.analyze(df, feat_cfg=fc)
    if "bool_col" in report._features:
        raise RuntimeError("Skipped column still present")
    if len(report._features) != 2:
        raise RuntimeError(f"Expected 2 features after skip, got {len(report._features)}")
    return "FeatureConfig skip OK"


def check_show_html_widescreen():
    import sweetviz
    df = _make_df()
    report = sweetviz.analyze(df)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "report_ws.html")
        report.show_html(filepath=path, open_browser=False, layout="widescreen")
        _validate_html_file(path, "widescreen")
    return "widescreen HTML OK"


def check_show_html_vertical():
    import sweetviz
    df = _make_df()
    report = sweetviz.analyze(df)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "report_vt.html")
        report.show_html(filepath=path, open_browser=False, layout="vertical")
        _validate_html_file(path, "vertical")
    return "vertical HTML OK"


def check_show_html_compare():
    import sweetviz
    df1 = _make_df()
    df2 = _make_df_compare()
    report = sweetviz.compare(df1, df2)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "report_cmp.html")
        report.show_html(filepath=path, open_browser=False, layout="widescreen")
        _validate_html_file(path, "compare")
    return "compare HTML OK"


def _validate_html_file(path: str, label: str):
    if not os.path.isfile(path):
        raise RuntimeError(f"{label}: HTML file not created at {path}")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if len(content) < 500:
        raise RuntimeError(f"{label}: HTML file too small ({len(content)} bytes)")
    if "sweetviz" not in content.lower():
        raise RuntimeError(f"{label}: HTML missing 'sweetviz' marker")
    if "</html>" not in content.lower():
        raise RuntimeError(f"{label}: HTML not properly closed")


REQUIRED_JSON_TOP_KEYS = {"metadata", "source_summary", "features"}
REQUIRED_METADATA_KEYS = {"schema_version", "generated_at", "source_name", "sweetviz_version"}


def check_to_json_analyze():
    import sweetviz
    df = _make_df()
    report = sweetviz.analyze(df)
    json_str = report.to_json()
    _validate_json_report(json_str, "analyze")
    return "analyze JSON OK"


def check_to_json_compare_with_drift():
    import sweetviz
    df1 = _make_df()
    df2 = _make_df_compare()
    report = sweetviz.compare(df1, df2)
    json_str = report.to_json(include_drift=True)
    data = _validate_json_report(json_str, "compare+drift")
    if "compare_summary" not in data:
        raise RuntimeError("compare+drift: missing compare_summary")
    if "drift_summary" not in data:
        raise RuntimeError("compare+drift: missing drift_summary")
    drift = data["drift_summary"]
    if "num_features" not in drift:
        raise RuntimeError("compare+drift: drift_summary missing num_features")
    return "compare+drift JSON OK"


def check_to_json_file():
    import sweetviz
    df = _make_df()
    report = sweetviz.analyze(df)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "report.json")
        json_str = report.to_json(filepath=path)
        if not os.path.isfile(path):
            raise RuntimeError("JSON file not created")
        with open(path, "r", encoding="utf-8") as f:
            file_content = f.read()
        if json_str != file_content:
            raise RuntimeError("JSON string differs from file content")
    _validate_json_report(json_str, "file")
    return "JSON file export OK"


def check_get_report_data():
    import sweetviz
    df = _make_df()
    report = sweetviz.analyze(df)
    data = report.get_report_data()
    if not isinstance(data, dict):
        raise RuntimeError("get_report_data did not return dict")
    _validate_report_dict(data, "get_report_data")
    return "get_report_data OK"


def check_to_json_no_drift():
    import sweetviz
    df1 = _make_df()
    df2 = _make_df_compare()
    report = sweetviz.compare(df1, df2)
    json_str = report.to_json(include_drift=False)
    data = json.loads(json_str)
    if "drift_summary" in data:
        raise RuntimeError("drift_summary present when include_drift=False")
    return "include_drift=False OK"


def _validate_json_report(json_str: str, label: str) -> dict:
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label}: invalid JSON: {exc}") from exc
    _validate_report_dict(data, label)
    return data


def _validate_report_dict(data: dict, label: str):
    missing_top = REQUIRED_JSON_TOP_KEYS - set(data.keys())
    if missing_top:
        raise RuntimeError(f"{label}: missing top-level keys: {missing_top}")

    meta = data.get("metadata", {})
    missing_meta = REQUIRED_METADATA_KEYS - set(meta.keys())
    if missing_meta:
        raise RuntimeError(f"{label}: missing metadata keys: {missing_meta}")

    features = data.get("features", {})
    if not features:
        raise RuntimeError(f"{label}: features dict is empty")
    for fname, fdata in features.items():
        for key in ("name", "type", "base_stats"):
            if key not in fdata:
                raise RuntimeError(f"{label}: feature '{fname}' missing '{key}'")


def check_notebook_html_generation():
    import sweetviz
    df = _make_df()
    report = sweetviz.analyze(df)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "notebook_report.html")

        import unittest.mock as mock
        mock_display = mock.MagicMock()
        mock_html_cls = mock.MagicMock()

        ipython_display_mod = mock.MagicMock()
        ipython_display_mod.display = mock_display
        ipython_display_mod.HTML = mock_html_cls

        with mock.patch.dict("sys.modules", {
            "IPython.display": ipython_display_mod,
            "IPython": mock.MagicMock(),
        }):
            report.show_notebook(layout="widescreen", filepath=path)

        if not mock_display.called:
            raise RuntimeError("IPython.display was not called")

        if not os.path.isfile(path):
            raise RuntimeError("Notebook file output not created")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if "sweetviz" not in content.lower():
            raise RuntimeError("Notebook HTML output missing 'sweetviz' marker")
        if "</html>" not in content.lower():
            raise RuntimeError("Notebook HTML not properly closed")

    return "notebook HTML path OK"


def check_notebook_vertical_layout():
    import sweetviz
    df = _make_df()
    report = sweetviz.analyze(df)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "notebook_vt.html")

        import unittest.mock as mock
        mock_display = mock.MagicMock()
        ipython_display_mod = mock.MagicMock()
        ipython_display_mod.display = mock_display
        ipython_display_mod.HTML = mock.MagicMock()

        with mock.patch.dict("sys.modules", {
            "IPython.display": ipython_display_mod,
            "IPython": mock.MagicMock(),
        }):
            report.show_notebook(layout="vertical", filepath=path)

        if not os.path.isfile(path):
            raise RuntimeError("Notebook vertical file output not created")

    return "notebook vertical layout OK"


def check_config_loads():
    from sweetviz.config import config
    for section in ("General", "Output_Defaults", "Layout", "Graphs",
                    "Processing", "Type_Detection"):
        if section not in config:
            raise RuntimeError(f"Config section [{section}] missing")
    return f"{len(config.sections())} config sections OK"


def check_config_values():
    from sweetviz.config import config
    layout = config["Output_Defaults"].get("html_layout")
    if layout not in ("widescreen", "vertical"):
        raise RuntimeError(f"Unexpected html_layout: {layout}")
    scale = config["Output_Defaults"].getfloat("html_scale")
    if scale <= 0:
        raise RuntimeError(f"Invalid html_scale: {scale}")
    return "Key config values OK"


ALL_CHECKS = [
    ("resources.templates", check_template_resources),
    ("resources.fonts", check_font_resources),
    ("resources.mpl_styles", check_mpl_style_resources),
    ("resources.ini_config", check_ini_config),
    ("resources.template_consistency", check_template_code_consistency),
    ("api.imports", check_public_api_imports),
    ("api.top_level", check_sweetviz_top_level),
    ("api.config_loads", check_config_loads),
    ("api.config_values", check_config_values),
    ("report.analyze", check_analyze_report),
    ("report.analyze_target", check_analyze_with_target),
    ("report.compare", check_compare_report),
    ("report.compare_intra", check_compare_intra_report),
    ("report.feature_config", check_feature_config),
    ("html.widescreen", check_show_html_widescreen),
    ("html.vertical", check_show_html_vertical),
    ("html.compare", check_show_html_compare),
    ("json.analyze", check_to_json_analyze),
    ("json.compare_drift", check_to_json_compare_with_drift),
    ("json.file_export", check_to_json_file),
    ("json.get_report_data", check_get_report_data),
    ("json.no_drift", check_to_json_no_drift),
    ("notebook.html", check_notebook_html_generation),
    ("notebook.vertical", check_notebook_vertical_layout),
]


def run_all(skip_tags=None):
    _reset()
    skip_tags = skip_tags or set()
    for name, func in ALL_CHECKS:
        tag = name.split(".")[0]
        if tag in skip_tags:
            _record(name, SKIP)
            continue
        _safe_run(name, func)

    passed = sum(1 for _, s, _ in _results if s == PASS)
    failed = sum(1 for _, s, _ in _results if s == FAIL)
    skipped = sum(1 for _, s, _ in _results if s == SKIP)

    verbose = os.environ.get("SWEETVIZ_PRERELEASE_VERBOSE") or "--verbose" in sys.argv

    print("\n" + "=" * 64)
    print("Sweetviz Pre-Release Check Results")
    print("=" * 64)
    for name, status, detail in _results:
        marker = {"PASS": "✓", "FAIL": "✗", "SKIP": "○"}[status]
        line = f"  {marker} {name}"
        if detail and (verbose or status == FAIL):
            line += f"  ({detail})"
        print(line)

    print("-" * 64)
    print(f"  Total: {len(_results)}  |  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}")
    print("=" * 64)

    if failed > 0:
        print("\n❌ Pre-release checks FAILED. Do not release.")
        return 1
    print("\n✅ All pre-release checks passed. Safe to release.")
    return 0


def main():
    skip_tags = set()
    for arg in sys.argv[1:]:
        if arg.startswith("--skip="):
            skip_tags.update(arg[len("--skip="):].split(","))
    sys.exit(run_all(skip_tags))
