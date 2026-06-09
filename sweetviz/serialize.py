import json
import math
import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from sweetviz.sv_types import NumWithPercent, FeatureType


SCHEMA_VERSION = "1.0"

NUMERIC_STAT_KEYS = [
    "max", "perc95", "perc75", "mean", "perc50",
    "perc25", "perc5", "min", "range", "iqr",
    "std", "variance", "kurtosis", "skewness", "sum",
]

BASE_STAT_KEYS = [
    "total_rows", "num_values", "num_missing",
    "missing_rate", "num_zeroes", "num_distinct",
]

DATAFRAME_SUMMARY_KEYS = [
    "name", "num_rows", "num_columns", "num_skipped_columns",
    "memory_total", "memory_single_row", "duplicates",
    "num_cat", "num_numerical", "num_text",
    "num_cmp_not_in_source",
]


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
    base_stats = feature_dict.get("base_stats", {})
    result = {key: None for key in BASE_STAT_KEYS}

    for key in ["total_rows", "num_values", "num_missing", "num_zeroes", "num_distinct"]:
        result[key] = _serialize_value(base_stats.get(key))

    num_missing = base_stats.get("num_missing")
    if num_missing is not None and hasattr(num_missing, "perc"):
        result["missing_rate"] = _serialize_value(num_missing.perc)

    return result


def _serialize_numeric_stats(feature_dict: Dict) -> Dict:
    stats = feature_dict.get("stats", {})
    result = {key: None for key in NUMERIC_STAT_KEYS}
    for key in NUMERIC_STAT_KEYS:
        result[key] = _serialize_value(stats.get(key))
    return result


def _serialize_categorical_item(item: Dict) -> Dict:
    return {
        "name": _serialize_value(item.get("name")),
        "count": _serialize_value(item.get("count")),
        "count_compare": _serialize_value(item.get("count_compare")),
    }


def _serialize_value_item(item: tuple) -> Dict:
    value = item[0] if len(item) >= 1 else None
    count = item[1] if len(item) >= 2 else None
    count_compare = item[2] if len(item) >= 3 else None
    return {
        "value": _serialize_value(value),
        "count": _serialize_value(count),
        "count_compare": _serialize_value(count_compare),
    }


def _serialize_details(feature_dict: Dict, max_top: int = 10) -> Dict:
    result = {
        "top_categories": [],
        "frequent_values": [],
        "min_values": [],
        "max_values": [],
    }
    detail = feature_dict.get("detail", {})
    full_count = detail.get("full_count", [])

    for item in full_count:
        if item.get("is_total"):
            continue
        if len(result["top_categories"]) >= max_top:
            break
        result["top_categories"].append(_serialize_categorical_item(item))

    for key in ["frequent_values", "min_values", "max_values"]:
        for item in detail.get(key, []):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                result[key].append(_serialize_value_item(item))

    return result


def serialize_feature_drift(drift_dict: Optional[Dict]) -> Optional[Dict]:
    if drift_dict is None:
        return {
            "score": None,
            "severity": None,
            "top_reasons": [],
            "details": None,
        }
    serialized = _serialize_value(drift_dict)
    result = {
        "score": None,
        "severity": None,
        "top_reasons": [],
        "details": None,
    }
    if isinstance(serialized, dict):
        result["score"] = serialized.get("score")
        result["severity"] = serialized.get("severity")
        result["top_reasons"] = serialized.get("top_reasons", []) or []
        result["details"] = serialized.get("details")
    return result


def serialize_report_drift_summary(drift_summary: Optional[Dict]) -> Dict:
    if drift_summary is None:
        return {
            "num_features": 0,
            "average_score": None,
            "max_score": None,
            "severity_counts": {"high": 0, "medium": 0, "low": 0, "none": 0},
            "top_features": [],
        }
    serialized = _serialize_value(drift_summary)
    result = {
        "num_features": 0,
        "average_score": None,
        "max_score": None,
        "severity_counts": {"high": 0, "medium": 0, "low": 0, "none": 0},
        "top_features": [],
    }
    if isinstance(serialized, dict):
        result["num_features"] = serialized.get("num_features", 0) or 0
        result["average_score"] = serialized.get("average_score")
        result["max_score"] = serialized.get("max_score")
        sc = serialized.get("severity_counts")
        if isinstance(sc, dict):
            for level in ["high", "medium", "low", "none"]:
                result["severity_counts"][level] = sc.get(level, 0) or 0
        top = serialized.get("top_features")
        if isinstance(top, list):
            result["top_features"] = top
    return result


def _serialize_compare_feature(compare_dict: Optional[Dict]) -> Optional[Dict]:
    if compare_dict is None:
        return None
    result = {
        "type": _serialize_value(compare_dict.get("type")),
        "base_stats": _serialize_base_stats(compare_dict),
        "stats": {key: None for key in NUMERIC_STAT_KEYS},
    }
    compare_type = compare_dict.get("type")
    if compare_type == FeatureType.TYPE_NUM:
        result["stats"] = _serialize_numeric_stats(compare_dict)
    return result


def serialize_feature(feature_dict: Dict) -> Dict:
    feature_type = feature_dict.get("type")
    is_numeric = feature_type == FeatureType.TYPE_NUM

    result = {
        "name": feature_dict.get("name"),
        "type": _serialize_value(feature_type),
        "is_target": feature_dict.get("is_target", False),
        "base_stats": _serialize_base_stats(feature_dict),
        "stats": {key: None for key in NUMERIC_STAT_KEYS},
        "details": _serialize_details(feature_dict),
        "compare": _serialize_compare_feature(feature_dict.get("compare")),
        "drift": serialize_feature_drift(feature_dict.get("drift")),
    }

    if is_numeric:
        result["stats"] = _serialize_numeric_stats(feature_dict)

    return result


def serialize_dataframe_summary(summary_dict: Optional[Dict]) -> Dict:
    result = {key: None for key in DATAFRAME_SUMMARY_KEYS}
    if summary_dict is None:
        return result
    for key in DATAFRAME_SUMMARY_KEYS:
        result[key] = _serialize_value(summary_dict.get(key))
    return result


def serialize_associations(associations: Optional[Dict]) -> Dict:
    if associations is None:
        return {}
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


def build_top_level_dict() -> Dict:
    return {
        "metadata": None,
        "source_summary": serialize_dataframe_summary(None),
        "compare_summary": serialize_dataframe_summary(None),
        "target": None,
        "features": {},
        "associations": {},
        "associations_compare": {},
        "drift_summary": serialize_report_drift_summary(None),
    }
