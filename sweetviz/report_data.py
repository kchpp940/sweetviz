import math
import numbers
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from sweetviz.sv_types import NumWithPercent, FeatureType


SCHEMA_VERSION = "1.0"


def _nwp_to_dict(obj: NumWithPercent) -> Optional[Dict]:
    if obj is None:
        return None
    return {
        "number": _convert_value(obj.number),
        "percentage": _convert_value(obj.perc),
    }


def _convert_value(val: Any) -> Any:
    if isinstance(val, NumWithPercent):
        return _nwp_to_dict(val)
    if isinstance(val, FeatureType):
        return val.value
    if isinstance(val, bytes):
        try:
            return val.decode("ascii")
        except (UnicodeDecodeError, AttributeError):
            return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(val, bool):
        return val
    if isinstance(val, numbers.Integral):
        return int(val)
    if isinstance(val, numbers.Real):
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return {k: _convert_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_convert_value(v) for v in val]
    if isinstance(val, (pd.Series, pd.DataFrame)):
        return None
    if val is None:
        return None
    return val


def _extract_graph_data(graph_obj) -> Optional[dict]:
    if graph_obj is None:
        return None
    result = {}
    base64 = getattr(graph_obj, "graph_base64", None)
    if base64 is not None:
        if isinstance(base64, bytes):
            try:
                result["graph_base64"] = base64.decode("ascii")
            except (UnicodeDecodeError, AttributeError):
                result["graph_base64"] = None
        else:
            result["graph_base64"] = base64
    size = getattr(graph_obj, "size_in_inches", None)
    if size is not None:
        result["size_in_inches"] = [float(size[0]), float(size[1])]
    idx = getattr(graph_obj, "index_for_css", None)
    if idx is not None:
        result["index_for_css"] = idx
    button = getattr(graph_obj, "button_name", None)
    if button is not None:
        result["button_name"] = button
    return result if result else None


def _extract_base_stats(feature_dict: dict) -> dict:
    base_stats = feature_dict.get("base_stats", {})
    result = {}
    for k, v in base_stats.items():
        result[k] = _convert_value(v)
    if "num_missing" in result and result["num_missing"] is not None:
        missing_pct = result["num_missing"].get("percentage", 0)
        result["missing_rate"] = round(missing_pct, 2) if missing_pct is not None else 0.0
    else:
        result["missing_rate"] = 0.0
    return result


def _extract_stats(feature_dict: dict) -> Optional[dict]:
    stats = feature_dict.get("stats")
    if stats is None or not stats:
        return None
    return _convert_value(stats)


def _extract_details(feature_dict: dict, feature_type) -> Optional[dict]:
    detail = feature_dict.get("detail")
    if detail is None:
        return None
    return _convert_value(detail)


def _extract_compare(feature_dict: dict) -> Optional[dict]:
    compare_dict = feature_dict.get("compare")
    if compare_dict is None:
        return None
    result = {}
    if "type" in compare_dict:
        ct = compare_dict["type"]
        result["type"] = ct.value if isinstance(ct, FeatureType) else ct
    if "base_stats" in compare_dict:
        result["base_stats"] = _extract_base_stats(compare_dict)
    if "stats" in compare_dict and compare_dict.get("stats"):
        result["stats"] = _extract_stats(compare_dict)
    return result


def _extract_feature(feature_dict: dict) -> dict:
    feature_type = feature_dict.get("type")
    result = {
        "name": feature_dict.get("name"),
        "display_name": feature_dict.get("display_name", feature_dict.get("name")),
        "safe_name": feature_dict.get("safe_name"),
        "order_index": feature_dict.get("order_index"),
        "is_target": feature_dict.get("is_target", False),
    }
    ft = feature_type.value if isinstance(feature_type, FeatureType) else feature_type
    if ft is not None:
        result["type"] = ft
    if "base_stats" in feature_dict:
        result["base_stats"] = _extract_base_stats(feature_dict)
    stats = _extract_stats(feature_dict)
    if stats:
        result["stats"] = stats
    details = _extract_details(feature_dict, feature_type)
    if details:
        result["detail"] = details
    compare = _extract_compare(feature_dict)
    if compare:
        result["compare"] = compare
    if "drift" in feature_dict and feature_dict["drift"] is not None:
        result["drift"] = _convert_value(feature_dict["drift"])
    mini = feature_dict.get("minigraph")
    if mini is not None:
        mini_data = _extract_graph_data(mini)
        if mini_data:
            result["minigraph"] = mini_data
    detail_graphs = feature_dict.get("detail_graphs")
    if detail_graphs:
        graphs = []
        for g in detail_graphs:
            gd = _extract_graph_data(g)
            if gd:
                graphs.append(gd)
        if graphs:
            result["detail_graphs"] = graphs
    return result


def _compute_drift_numeric(source_stats: dict, compare_stats: dict,
                            source_base: dict, compare_base: dict) -> dict:
    details = {"base": {}, "numeric_stats": {}}
    total_score = 0.0
    reasons = []

    base_keys = ["num_values", "num_missing", "num_distinct", "num_zeroes"]
    for key in base_keys:
        src = source_base.get(key)
        cmp = compare_base.get(key)
        if src is None or cmp is None:
            continue
        src_num = src.get("number", 0) or 0
        cmp_num = cmp.get("number", 0) or 0
        src_pct = src.get("percentage", 0) or 0
        cmp_pct = cmp.get("percentage", 0) or 0
        diff_count = cmp_num - src_num
        diff_pct = cmp_pct - src_pct
        details["base"][key] = {
            "source": src, "compare": cmp,
            "diff_count": diff_count,
            "diff_pct_points": round(diff_pct, 4),
        }
        if abs(diff_pct) > 5:
            total_score += abs(diff_pct) * 0.5
            if key == "num_missing":
                reasons.append("缺失率差异")

    if source_stats and compare_stats:
        numeric_keys = ["max", "perc95", "perc75", "mean", "perc50", "perc25", "perc5", "min",
                        "range", "iqr", "std", "variance", "kurtosis", "skewness", "sum"]
        for key in numeric_keys:
            if key not in source_stats or key not in compare_stats:
                continue
            src_val = source_stats.get(key)
            cmp_val = compare_stats.get(key)
            if src_val is None or cmp_val is None:
                continue
            if isinstance(src_val, float) and (math.isnan(src_val) or math.isinf(src_val)):
                continue
            if isinstance(cmp_val, float) and (math.isnan(cmp_val) or math.isinf(cmp_val)):
                continue
            diff = cmp_val - src_val
            if abs(src_val) > 1e-10:
                diff_pct = (diff / abs(src_val)) * 100.0
            else:
                diff_pct = 0.0 if diff == 0 else float('inf')
            details["numeric_stats"][key] = {
                "source": src_val, "compare": cmp_val,
                "diff": diff, "diff_pct": round(diff_pct, 4),
            }
            abs_diff_pct = abs(diff_pct)
            if key in ("std", "variance", "mean", "perc95", "iqr") and abs_diff_pct > 10:
                total_score += min(abs_diff_pct, 50) * 0.3
                if key == "std": reasons.append("标准差")
                elif key == "mean": reasons.append("平均值")
                elif key == "perc95": reasons.append("95%分位数")
                elif key == "variance": reasons.append("方差")
                elif key == "iqr": reasons.append("四分位距")

    score = round(min(total_score, 100), 1)
    severity = "high" if score >= 30 else "medium" if score >= 15 else "low" if score >= 5 else "none"
    return {"score": score, "severity": severity, "top_reasons": reasons[:3], "details": details}


def _compute_drift_categorical(source_details: dict, compare_details: dict,
                                source_base: dict, compare_base: dict,
                                feature_type) -> dict:
    details = {"base": {}, "category_shifts": []}
    total_score = 0.0
    reasons = []

    base_keys = ["num_values", "num_missing", "num_distinct"]
    for key in base_keys:
        src = source_base.get(key)
        cmp = compare_base.get(key)
        if src is None or cmp is None:
            continue
        src_num = src.get("number", 0) or 0
        cmp_num = cmp.get("number", 0) or 0
        src_pct = src.get("percentage", 0) or 0
        cmp_pct = cmp.get("percentage", 0) or 0
        diff_count = cmp_num - src_num
        diff_pct = cmp_pct - src_pct
        details["base"][key] = {
            "source": src, "compare": cmp,
            "diff_count": diff_count,
            "diff_pct_points": round(diff_pct, 4),
        }
        if abs(diff_pct) > 5:
            total_score += abs(diff_pct) * 0.5
            if key == "num_missing":
                reasons.append("缺失率差异")

    ft = feature_type.value if isinstance(feature_type, FeatureType) else feature_type
    cat_key = "top_categories" if ft in ("CATEGORICAL", "BOOL") else "top_values"

    def _get_categories(details_dict):
        if not details_dict:
            return {}
        if cat_key in details_dict:
            return {item.get("name"): item for item in details_dict.get(cat_key, [])}
        if "full_count" in details_dict:
            result = {}
            for row in details_dict["full_count"]:
                if isinstance(row, dict) and not row.get("is_total"):
                    name = row.get("name")
                    if name is not None:
                        result[name] = row
            return result
        return {}

    src_cats = _get_categories(source_details)
    cmp_cats = _get_categories(compare_details)

    for name in set(src_cats.keys()) | set(cmp_cats.keys()):
        src_item = src_cats.get(name)
        cmp_item = cmp_cats.get(name)
        src_count = src_item.get("count") if src_item else None
        cmp_count = cmp_item.get("count") if cmp_item else None
        src_num = src_count.get("number", 0) if src_count else 0
        cmp_num = cmp_count.get("number", 0) if cmp_count else 0
        src_pct = src_count.get("percentage", 0) if src_count else 0
        cmp_pct = cmp_count.get("percentage", 0) if cmp_count else 0
        diff_count = cmp_num - src_num
        diff_pct = cmp_pct - src_pct
        details["category_shifts"].append({
            "name": name,
            "source": src_count, "compare": cmp_count,
            "diff_count": diff_count,
            "diff_pct_points": round(diff_pct, 4),
        })
        if abs(diff_pct) > 5:
            total_score += abs(diff_pct) * 0.8
            cat_label = "类别" if ft in ("CATEGORICAL", "BOOL") else "值"
            reasons.append(f"{cat_label} '{name}' 占比差异")

    score = round(min(total_score, 100), 1)
    severity = "high" if score >= 30 else "medium" if score >= 15 else "low" if score >= 5 else "none"
    return {"score": score, "severity": severity, "top_reasons": reasons[:3], "details": details}


def compute_drift(feature_dict: dict) -> Optional[dict]:
    compare_dict = feature_dict.get("compare")
    if compare_dict is None:
        return None
    feature_type = feature_dict.get("type")
    source_base = _extract_base_stats(feature_dict)
    compare_base = _extract_base_stats(compare_dict)
    source_stats = _extract_stats(feature_dict)
    compare_stats = _extract_stats(compare_dict)
    source_details = _extract_details(feature_dict, feature_type)
    ft = feature_type.value if isinstance(feature_type, FeatureType) else feature_type
    if ft == "NUMERIC":
        return _compute_drift_numeric(source_stats, compare_stats, source_base, compare_base)
    elif ft in ("CATEGORICAL", "BOOL", "TEXT"):
        compare_details = _extract_details(compare_dict, feature_type)
        return _compute_drift_categorical(source_details, compare_details, source_base, compare_base, feature_type)
    return None


def compute_all_drifts(features: Dict[str, dict], target: Optional[dict]) -> None:
    for fdict in features.values():
        if "drift" not in fdict or fdict["drift"] is None:
            fdict["drift"] = compute_drift(fdict)
    if target is not None and "drift" not in target:
        target["drift"] = compute_drift(target)


def compute_drift_summary(features: Dict[str, dict], target: Optional[dict]) -> Optional[dict]:
    drift_scores = []
    for fname, fdict in features.items():
        drift = fdict.get("drift")
        if drift is not None:
            drift_scores.append({
                "feature_name": fname,
                "display_name": fdict.get("display_name", fname),
                "score": drift.get("score", 0),
                "severity": drift.get("severity", "none"),
                "top_reasons": drift.get("top_reasons", []),
            })
    if target is not None and target.get("drift") is not None:
        drift_scores.append({
            "feature_name": target["name"],
            "display_name": target.get("display_name", target["name"]),
            "score": target["drift"].get("score", 0),
            "severity": target["drift"].get("severity", "none"),
            "top_reasons": target["drift"].get("top_reasons", []),
        })
    if not drift_scores:
        return None
    drift_scores.sort(key=lambda x: x["score"], reverse=True)
    scores = [d["score"] for d in drift_scores]
    severity_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for d in drift_scores:
        sev = d["severity"]
        if sev in severity_counts:
            severity_counts[sev] += 1
    return {
        "num_features": len(drift_scores),
        "average_score": round(sum(scores) / len(scores), 1),
        "max_score": max(scores),
        "severity_counts": severity_counts,
        "top_features": drift_scores,
    }


def build_report_data(report) -> dict:
    if report.compare_name is not None:
        compute_all_drifts(report._features, report._target)

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_name": report.source_name,
        "compare_name": report.compare_name,
    }
    try:
        import sweetviz
        metadata["sweetviz_version"] = sweetviz.__version__
    except (ImportError, AttributeError):
        pass

    source_summary = _convert_value(report.summary_source)
    compare_summary = _convert_value(report.summary_compare) if report.summary_compare is not None else None

    features = {}
    for fname, fdict in report._features.items():
        features[fname] = _extract_feature(fdict)

    target = None
    if report._target is not None:
        target = _extract_feature(report._target)

    associations = _convert_value(report._associations)
    associations_compare = _convert_value(report._associations_compare) if report._associations_compare is not None else None

    graph_legend = None
    if hasattr(report, 'graph_legend') and report.graph_legend is not None:
        graph_legend = _extract_graph_data(report.graph_legend)

    association_graphs = {}
    if hasattr(report, '_association_graphs'):
        for k, v in report._association_graphs.items():
            gd = _extract_graph_data(v)
            if gd:
                association_graphs[k] = gd
    if not association_graphs:
        association_graphs = None

    association_graphs_compare = {}
    if hasattr(report, '_association_graphs_compare'):
        for k, v in report._association_graphs_compare.items():
            gd = _extract_graph_data(v)
            if gd:
                association_graphs_compare[k] = gd
    if not association_graphs_compare:
        association_graphs_compare = None

    drift_summary = compute_drift_summary(report._features, report._target)

    result = {
        "metadata": metadata,
        "source_summary": source_summary,
        "features": features,
    }
    if target is not None:
        result["target"] = target
    if compare_summary is not None:
        result["compare_summary"] = compare_summary
    if associations is not None:
        result["associations"] = associations
    if associations_compare is not None:
        result["associations_compare"] = associations_compare
    if graph_legend is not None:
        result["graph_legend"] = graph_legend
    if association_graphs is not None:
        result["association_graphs"] = association_graphs
    if association_graphs_compare is not None:
        result["association_graphs_compare"] = association_graphs_compare
    if drift_summary is not None:
        result["drift_summary"] = drift_summary
    return result


def to_json_safe(report_data: dict) -> dict:
    return _convert_value(report_data)
