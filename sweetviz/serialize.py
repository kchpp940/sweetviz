import json
import math
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from sweetviz.sv_types import NumWithPercent, FeatureType


def _serialize_value(value: Any) -> Any:
    if isinstance(value, NumWithPercent):
        return _serialize_value(value.to_dict())
    elif isinstance(value, FeatureType):
        return value.value
    elif isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_serialize_value(v) for v in value]
    elif isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    elif isinstance(value, (np.integer,)):
        return int(value)
    elif isinstance(value, (np.floating,)):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    elif isinstance(value, (np.bool_,)):
        return bool(value)
    elif isinstance(value, np.ndarray):
        return [_serialize_value(v) for v in value.tolist()]
    elif isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    elif hasattr(value, '__class__') and hasattr(value, '__module__'):
        if value.__class__.__module__.startswith('pandas'):
            if isinstance(value, pd.Series):
                return None
            try:
                return _serialize_value(value.item())
            except Exception:
                return None
    elif isinstance(value, str):
        return value
    elif value is None:
        return None
    elif isinstance(value, (int, bool)):
        return value
    elif hasattr(value, 'to_dict') and not isinstance(value, (dict, list, str, int, float, bool, type(None))):
        try:
            return _serialize_value(value.to_dict())
        except Exception:
            return None
    else:
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            try:
                return _serialize_value(value.item())
            except Exception:
                return None


def _serialize_base_stats(feature_dict: Dict) -> Dict:
    result = {}
    base_stats = feature_dict.get("base_stats", {})
    result["total_rows"] = base_stats.get("total_rows")
    result["num_values"] = _serialize_value(base_stats.get("num_values"))
    result["num_missing"] = _serialize_value(base_stats.get("num_missing"))
    result["num_zeroes"] = _serialize_value(base_stats.get("num_zeroes"))
    result["num_distinct"] = _serialize_value(base_stats.get("num_distinct"))
    num_missing = base_stats.get("num_missing")
    if num_missing is not None and hasattr(num_missing, "perc"):
        result["missing_rate"] = num_missing.perc
    else:
        result["missing_rate"] = None
    return result


def _serialize_numeric_stats(feature_dict: Dict) -> Dict:
    stats = feature_dict.get("stats", {})
    result = {}
    for key in ["min", "max", "mean", "std", "variance", "kurtosis", "skewness", "sum", "range", "iqr", "cv", "perc5", "perc25", "perc50", "perc75", "perc95"]:
        if key in stats:
            result[key] = _serialize_value(stats[key])
    return result


def _serialize_categorical_details(feature_dict: Dict, max_top: int = 10) -> Dict:
    result = {"top_categories": []}
    detail = feature_dict.get("detail", {})
    full_count = detail.get("full_count", [])
    for item in full_count:
        if item.get("is_total"):
            continue
        if len(result["top_categories"]) >= max_top:
            break
        cat_item = {
            "name": item.get("name"),
            "count": _serialize_value(item.get("count")),
        }
        if item.get("count_compare") is not None:
            cat_item["count_compare"] = _serialize_value(item.get("count_compare"))
        result["top_categories"].append(cat_item)
    return result


def _serialize_numeric_details(feature_dict: Dict) -> Dict:
    result = {"frequent_values": [], "min_values": [], "max_values": []}
    detail = feature_dict.get("detail", {})
    for key in ["frequent_values", "min_values", "max_values"]:
        for item in detail.get(key, []):
            if len(item) >= 2:
                val_item = {
                    "value": _serialize_value(item[0]),
                    "count": _serialize_value(item[1])
                }
                if len(item) >= 3 and item[2] is not None:
                    val_item["count_compare"] = _serialize_value(item[2])
                result[key].append(val_item)
    return result


def serialize_feature(feature_dict: Dict) -> Dict:
    result = {
        "name": feature_dict.get("name"),
        "type": _serialize_value(feature_dict.get("type")),
        "is_target": feature_dict.get("is_target", False),
        "base_stats": _serialize_base_stats(feature_dict),
    }

    feature_type = feature_dict.get("type")
    if feature_type == FeatureType.TYPE_NUM:
        result["stats"] = _serialize_numeric_stats(feature_dict)
        result["details"] = _serialize_numeric_details(feature_dict)
    elif feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL):
        result["details"] = _serialize_categorical_details(feature_dict)
    elif feature_type == FeatureType.TYPE_TEXT:
        result["details"] = _serialize_categorical_details(feature_dict)

    compare = feature_dict.get("compare")
    if compare is not None:
        result["compare"] = {
            "type": _serialize_value(compare.get("type")),
            "base_stats": _serialize_base_stats(compare),
        }
        compare_type = compare.get("type")
        if compare_type == FeatureType.TYPE_NUM:
            result["compare"]["stats"] = _serialize_numeric_stats(compare)
        result["compare_summary"] = _compute_compare_summary(feature_dict, compare)

    return result


def _compute_compare_summary(source_dict: Dict, compare_dict: Dict) -> Dict:
    summary = {}

    source_missing = source_dict.get("base_stats", {}).get("num_missing")
    compare_missing = compare_dict.get("base_stats", {}).get("num_missing")

    if source_missing and compare_missing:
        source_missing_perc = source_missing.perc if source_missing.perc is not None else 0
        compare_missing_perc = compare_missing.perc if compare_missing.perc is not None else 0
        summary["missing_rate_diff"] = _serialize_value(compare_missing_perc - source_missing_perc)

    source_distinct = source_dict.get("base_stats", {}).get("num_distinct")
    compare_distinct = compare_dict.get("base_stats", {}).get("num_distinct")

    if source_distinct and compare_distinct:
        source_distinct_perc = source_distinct.perc if source_distinct.perc is not None else 0
        compare_distinct_perc = compare_distinct.perc if compare_distinct.perc is not None else 0
        summary["distinct_rate_diff"] = _serialize_value(compare_distinct_perc - source_distinct_perc)

    feature_type = source_dict.get("type")
    if feature_type == FeatureType.TYPE_NUM:
        source_stats = source_dict.get("stats", {})
        compare_stats = compare_dict.get("stats", {})
        for stat_key in ["mean", "min", "max", "std", "perc50"]:
            if stat_key in source_stats and stat_key in compare_stats:
                s_val = source_stats[stat_key]
                c_val = compare_stats[stat_key]
                if s_val is not None and c_val is not None and not (math.isnan(s_val) or math.isnan(c_val)):
                    summary[f"{stat_key}_diff"] = _serialize_value(c_val - s_val)
                    if s_val != 0:
                        summary[f"{stat_key}_diff_pct"] = _serialize_value(((c_val - s_val) / abs(s_val)) * 100.0)

    return summary


def serialize_dataframe_summary(summary_dict: Optional[Dict]) -> Optional[Dict]:
    if summary_dict is None:
        return None
    result = {
        "name": _serialize_value(summary_dict.get("name")),
        "num_rows": _serialize_value(summary_dict.get("num_rows")),
        "num_columns": _serialize_value(summary_dict.get("num_columns")),
        "num_skipped_columns": _serialize_value(summary_dict.get("num_skipped_columns")),
        "memory_total": _serialize_value(summary_dict.get("memory_total")),
        "memory_single_row": _serialize_value(summary_dict.get("memory_single_row")),
        "duplicates": _serialize_value(summary_dict.get("duplicates")),
        "num_cat": _serialize_value(summary_dict.get("num_cat")),
        "num_numerical": _serialize_value(summary_dict.get("num_numerical")),
        "num_text": _serialize_value(summary_dict.get("num_text")),
    }
    if "num_cmp_not_in_source" in summary_dict:
        result["num_cmp_not_in_source"] = _serialize_value(summary_dict["num_cmp_not_in_source"])
    return result


def serialize_associations(associations: Optional[Dict]) -> Optional[Dict]:
    if associations is None:
        return None
    result = {}
    for feat_name, feat_assoc in associations.items():
        result[feat_name] = _serialize_value(feat_assoc)
    return result
