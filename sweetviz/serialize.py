import json
import math
import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from sweetviz.sv_types import NumWithPercent, FeatureType


SCHEMA_VERSION = "1.0"

NUMERIC_STATS_GROUP_1 = ["max", "perc95", "perc75", "mean", "perc50", "perc25", "perc5", "min"]
NUMERIC_STATS_GROUP_2 = ["range", "iqr", "std", "variance", "kurtosis", "skewness", "sum"]
ALL_NUMERIC_STATS = NUMERIC_STATS_GROUP_1 + NUMERIC_STATS_GROUP_2


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
    result["total_rows"] = _serialize_value(base_stats.get("total_rows"))
    result["num_values"] = _serialize_value(base_stats.get("num_values"))
    result["num_missing"] = _serialize_value(base_stats.get("num_missing"))
    result["num_zeroes"] = _serialize_value(base_stats.get("num_zeroes"))
    result["num_distinct"] = _serialize_value(base_stats.get("num_distinct"))
    num_missing = base_stats.get("num_missing")
    if num_missing is not None and hasattr(num_missing, "perc"):
        result["missing_rate"] = _serialize_value(num_missing.perc)
    else:
        result["missing_rate"] = None
    return result


def _serialize_numeric_stats(feature_dict: Dict) -> Dict:
    stats = feature_dict.get("stats", {})
    result = {}
    for key in ALL_NUMERIC_STATS + ["cv"]:
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


def _numwithpercent_to_primitives(nwp: NumWithPercent) -> Dict:
    if nwp is None:
        return {"number": None, "percentage": None}
    return {
        "number": _serialize_value(nwp.number),
        "percentage": _serialize_value(nwp.perc)
    }


def _to_python_number(val):
    if val is None:
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, (int, float, bool)):
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    return None


def _safe_diff_pct(compare_val, source_val):
    s = _to_python_number(source_val)
    c = _to_python_number(compare_val)
    if s is None or c is None:
        return None
    if s == 0:
        return None
    return _serialize_value(((c - s) / abs(s)) * 100.0)


def _safe_diff(compare_val, source_val):
    s = _to_python_number(source_val)
    c = _to_python_number(compare_val)
    if s is None or c is None:
        return None
    return _serialize_value(c - s)


def _compute_nwp_drift(source_nwp: NumWithPercent, compare_nwp: NumWithPercent) -> Dict:
    s = _numwithpercent_to_primitives(source_nwp)
    c = _numwithpercent_to_primitives(compare_nwp)
    return {
        "source": s,
        "compare": c,
        "diff_count": _safe_diff(c["number"], s["number"]),
        "diff_pct_points": _safe_diff(c["percentage"], s["percentage"])
    }


def _compute_numeric_drift(source_stats: Dict, compare_stats: Dict) -> Dict:
    drift = {}
    for stat_key in ALL_NUMERIC_STATS:
        if stat_key in source_stats and stat_key in compare_stats:
            s_val = source_stats[stat_key]
            c_val = compare_stats[stat_key]
            drift[stat_key] = {
                "source": _serialize_value(s_val),
                "compare": _serialize_value(c_val),
                "diff": _safe_diff(c_val, s_val),
                "diff_pct": _safe_diff_pct(c_val, s_val)
            }
    return drift


def compute_drift_summary(source_dict: Dict, compare_dict: Dict) -> Dict:
    drift_summary = {"base": {}}

    source_base = source_dict.get("base_stats", {})
    compare_base = compare_dict.get("base_stats", {})

    for stat_name in ["num_values", "num_missing", "num_distinct"]:
        drift_summary["base"][stat_name] = _compute_nwp_drift(
            source_base.get(stat_name), compare_base.get(stat_name)
        )

    feature_type = source_dict.get("type")
    if feature_type == FeatureType.TYPE_NUM:
        drift_summary["base"]["num_zeroes"] = _compute_nwp_drift(
            source_base.get("num_zeroes"), compare_base.get("num_zeroes")
        )
        drift_summary["numeric_stats"] = _compute_numeric_drift(
            source_dict.get("stats", {}), compare_dict.get("stats", {})
        )
    elif feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL, FeatureType.TYPE_TEXT):
        drift_summary["category_shifts"] = []
        source_detail = source_dict.get("detail", {}).get("full_count", [])
        for item in source_detail:
            if item.get("is_total"):
                continue
            s_cnt = item.get("count")
            c_cnt = item.get("count_compare")
            s_num = s_cnt.number if s_cnt is not None else None
            c_num = c_cnt.number if c_cnt is not None else None
            s_perc = s_cnt.perc if s_cnt is not None else None
            c_perc = c_cnt.perc if c_cnt is not None else None
            drift_summary["category_shifts"].append({
                "name": item.get("name"),
                "source": _numwithpercent_to_primitives(s_cnt),
                "compare": _numwithpercent_to_primitives(c_cnt),
                "diff_count": _safe_diff(c_num, s_num),
                "diff_pct_points": _safe_diff(c_perc, s_perc)
            })

    return drift_summary


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
        result["drift_summary"] = compute_drift_summary(feature_dict, compare)

    return result


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


def build_report_metadata(report) -> Dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_name": report.source_name,
        "compare_name": report.compare_name,
    }
