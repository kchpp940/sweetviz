import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from sweetviz.sv_types import NumWithPercent, FeatureType


SCHEMA_VERSION = "1.0"


def _num_with_percent_to_dict(obj: NumWithPercent) -> Optional[Dict[str, Optional[float]]]:
    if obj is None:
        return None
    return {
        "number": obj.number,
        "percentage": obj.perc
    }


def _feature_type_to_string(ft: FeatureType) -> str:
    if ft is None:
        return None
    return ft.value


def _convert_value(val: Any) -> Any:
    if isinstance(val, NumWithPercent):
        return _num_with_percent_to_dict(val)
    if isinstance(val, FeatureType):
        return _feature_type_to_string(val)
    if isinstance(val, float):
        if math.isnan(val):
            return None
        if math.isinf(val):
            return None
        return val
    if isinstance(val, dict):
        return {k: _convert_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_convert_value(v) for v in val]
    if isinstance(val, pd.Series):
        return None
    if hasattr(val, 'to_json') and not isinstance(val, dict):
        return None
    return val


def _extract_base_stats(feature_dict: dict) -> dict:
    base_stats = feature_dict.get("base_stats", {})
    result = {}
    for k, v in base_stats.items():
        result[k] = _convert_value(v)
    if "num_missing" in result and result["num_missing"] is not None:
        missing_pct = result["num_missing"].get("percentage", 0)
        if missing_pct is not None:
            result["missing_rate"] = round(missing_pct, 2)
        else:
            result["missing_rate"] = 0.0
    else:
        result["missing_rate"] = 0.0
    return result


def _extract_stats(feature_dict: dict) -> Optional[dict]:
    stats = feature_dict.get("stats")
    if stats is None or not stats:
        return None
    return _convert_value(stats)


def _extract_details(feature_dict: dict, feature_type: FeatureType) -> Optional[dict]:
    detail = feature_dict.get("detail")
    if detail is None:
        return None
    result = {}

    if feature_type in (FeatureType.TYPE_NUM,):
        for key in ("frequent_values", "min_values", "max_values"):
            if key in detail:
                converted = []
                for item in detail[key]:
                    if isinstance(item, (list, tuple)):
                        entry = {
                            "value": _convert_value(item[0]),
                            "count": _convert_value(item[1]),
                        }
                        if len(item) > 2:
                            entry["count_compare"] = _convert_value(item[2])
                        converted.append(entry)
                    elif isinstance(item, dict):
                        converted.append(_convert_value(item))
                result[key] = converted

    if feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL, FeatureType.TYPE_TEXT):
        full_count = detail.get("full_count", [])
        converted = []
        for row in full_count:
            if isinstance(row, dict) and not row.get("is_total"):
                entry = {
                    "name": _convert_value(row.get("name")),
                    "count": _convert_value(row.get("count")),
                }
                if row.get("count_compare") is not None:
                    entry["count_compare"] = _convert_value(row.get("count_compare"))
                converted.append(entry)
        if feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL):
            result["top_categories"] = converted
        else:
            result["top_values"] = converted

    return result if result else None


def _extract_compare(feature_dict: dict) -> Optional[dict]:
    compare_dict = feature_dict.get("compare")
    if compare_dict is None:
        return None
    result = {}
    if "type" in compare_dict:
        result["type"] = _feature_type_to_string(compare_dict["type"])
    if "base_stats" in compare_dict:
        result["base_stats"] = _extract_base_stats(compare_dict)
    if "stats" in compare_dict and compare_dict.get("stats"):
        result["stats"] = _extract_stats(compare_dict)
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
            "source": _convert_value(src),
            "compare": _convert_value(cmp),
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
                "source": src_val,
                "compare": cmp_val,
                "diff": diff,
                "diff_pct": round(diff_pct, 4),
            }
            abs_diff_pct = abs(diff_pct)
            if key in ("std", "variance", "mean", "perc95", "iqr") and abs_diff_pct > 10:
                total_score += min(abs_diff_pct, 50) * 0.3
                if key == "std":
                    reasons.append("标准差")
                elif key == "mean":
                    reasons.append("平均值")
                elif key == "perc95":
                    reasons.append("95%分位数")
                elif key == "variance":
                    reasons.append("方差")
                elif key == "iqr":
                    reasons.append("四分位距")

    score = round(min(total_score, 100), 1)
    if score >= 30:
        severity = "high"
    elif score >= 15:
        severity = "medium"
    elif score >= 5:
        severity = "low"
    else:
        severity = "none"

    return {
        "score": score,
        "severity": severity,
        "top_reasons": reasons[:3],
        "details": details,
    }


def _compute_drift_categorical(source_details: dict, compare_details: dict,
                               source_base: dict, compare_base: dict,
                               feature_type: FeatureType) -> dict:
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
            "source": _convert_value(src),
            "compare": _convert_value(cmp),
            "diff_count": diff_count,
            "diff_pct_points": round(diff_pct, 4),
        }
        if abs(diff_pct) > 5:
            total_score += abs(diff_pct) * 0.5
            if key == "num_missing":
                reasons.append("缺失率差异")

    cat_key = "top_categories" if feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL) else "top_values"
    src_cats = {item.get("name"): item for item in (source_details or {}).get(cat_key, [])}
    cmp_cats = {item.get("name"): item for item in (compare_details or {}).get(cat_key, [])}

    all_names = set(src_cats.keys()) | set(cmp_cats.keys())
    for name in all_names:
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
        shift = {
            "name": name,
            "source": _convert_value(src_count),
            "compare": _convert_value(cmp_count),
            "diff_count": diff_count,
            "diff_pct_points": round(diff_pct, 4),
        }
        details["category_shifts"].append(shift)
        abs_diff_pct = abs(diff_pct)
        if abs_diff_pct > 5:
            total_score += abs_diff_pct * 0.8
            cat_label = "类别" if feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL) else "值"
            reasons.append(f"{cat_label} '{name}' 占比差异")

    score = round(min(total_score, 100), 1)
    if score >= 30:
        severity = "high"
    elif score >= 15:
        severity = "medium"
    elif score >= 5:
        severity = "low"
    else:
        severity = "none"

    return {
        "score": score,
        "severity": severity,
        "top_reasons": reasons[:3],
        "details": details,
    }


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

    if feature_type == FeatureType.TYPE_NUM:
        return _compute_drift_numeric(source_stats, compare_stats, source_base, compare_base)
    elif feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL, FeatureType.TYPE_TEXT):
        compare_details = _extract_details(compare_dict, feature_type)
        return _compute_drift_categorical(source_details, compare_details, source_base, compare_base, feature_type)
    return None


def compute_drift_summary(features: Dict[str, dict]) -> Optional[dict]:
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


def _extract_feature(feature_dict: dict, include_drift: bool = True) -> dict:
    feature_type = feature_dict.get("type")
    result = {
        "name": feature_dict.get("name"),
        "display_name": feature_dict.get("display_name", feature_dict.get("name")),
        "type": _feature_type_to_string(feature_type),
        "is_target": feature_dict.get("is_target", False),
    }
    if "base_stats" in feature_dict:
        result["base_stats"] = _extract_base_stats(feature_dict)
    stats = _extract_stats(feature_dict)
    if stats:
        result["stats"] = stats
    details = _extract_details(feature_dict, feature_type)
    if details:
        result["details"] = details
    compare = _extract_compare(feature_dict)
    if compare:
        result["compare"] = compare
    if include_drift and "drift" in feature_dict and feature_dict["drift"] is not None:
        result["drift"] = _convert_value(feature_dict["drift"])
    return result


def compute_all_drifts(report) -> None:
    if report.compare_name is None:
        return
    for fdict in report._features.values():
        if "drift" not in fdict or fdict["drift"] is None:
            fdict["drift"] = compute_drift(fdict)
    if report._target is not None and "drift" not in report._target:
        report._target["drift"] = compute_drift(report._target)


def build_report_data(report, include_drift: bool = True) -> dict:
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_name": getattr(report, "source_name", "DataFrame"),
        "compare_name": getattr(report, "compare_name", None),
    }
    try:
        import sweetviz
        metadata["sweetviz_version"] = sweetviz.__version__
    except (ImportError, AttributeError):
        pass

    source_summary = _convert_value(getattr(report, "summary_source", None))
    compare_summary = _convert_value(getattr(report, "summary_compare", None))

    if include_drift and report.compare_name is not None:
        compute_all_drifts(report)

    features = {}
    for fname, fdict in report._features.items():
        features[fname] = _extract_feature(fdict, include_drift=include_drift)

    target = None
    if report._target is not None:
        target = _extract_feature(report._target, include_drift=include_drift)

    associations = _convert_value(getattr(report, "_associations", None))
    associations_compare = _convert_value(getattr(report, "_associations_compare", None))

    drift_summary = None
    if include_drift and report.compare_name is not None:
        all_features_for_summary = {}
        for fname, fdict in report._features.items():
            all_features_for_summary[fname] = fdict
        if report._target is not None:
            all_features_for_summary[report._target.get("name")] = report._target
        drift_summary = compute_drift_summary(all_features_for_summary)

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
    if drift_summary is not None:
        result["drift_summary"] = drift_summary

    return result


def to_json(report, filepath: str = None, include_drift: bool = True,
            indent: int = 2) -> str:
    data = build_report_data(report, include_drift=include_drift)
    json_str = json.dumps(data, ensure_ascii=False, indent=indent, default=str)
    if filepath is not None:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json_str)
    return json_str
