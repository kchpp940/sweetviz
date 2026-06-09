import numpy as np
from sweetviz.config import config
from sweetviz.sv_types import FeatureType


NEAR_ZERO_THRESHOLD = 1e-3
TYPE_MISMATCH_WEIGHT = 50.0
MAX_RELATIVE_DIFF_THRESHOLD = 500.0


class DriftConfig:
    def __init__(self):
        self.enabled = config.getboolean("Drift_Detection", "enabled", fallback=True)
        self.missing_rate_threshold = config.getfloat("Drift_Detection", "missing_rate_threshold", fallback=5.0)
        self.distinct_count_threshold = config.getfloat("Drift_Detection", "distinct_count_threshold", fallback=20.0)
        self.numeric_quantile_threshold = config.getfloat("Drift_Detection", "numeric_quantile_threshold", fallback=15.0)
        self.numeric_quantile_absolute_threshold = config.getfloat(
            "Drift_Detection", "numeric_quantile_absolute_threshold", fallback=1.0
        )
        self.category_top_threshold = config.getfloat("Drift_Detection", "category_top_threshold", fallback=10.0)
        self.severity_medium_threshold = config.getfloat("Drift_Detection", "severity_medium_threshold", fallback=15.0)
        self.severity_high_threshold = config.getfloat("Drift_Detection", "severity_high_threshold", fallback=30.0)
        self.weight_missing_rate = config.getfloat("Drift_Detection", "weight_missing_rate", fallback=25.0)
        self.weight_distinct_count = config.getfloat("Drift_Detection", "weight_distinct_count", fallback=15.0)
        self.weight_numeric_quantile = config.getfloat("Drift_Detection", "weight_numeric_quantile", fallback=30.0)
        self.weight_category_top = config.getfloat("Drift_Detection", "weight_category_top", fallback=30.0)
        self.drift_score_medium_threshold = config.getfloat("Drift_Detection", "drift_score_medium_threshold", fallback=10.0)
        self.drift_score_high_threshold = config.getfloat("Drift_Detection", "drift_score_high_threshold", fallback=25.0)
        self.category_top_n = config.getint("Drift_Detection", "category_top_n", fallback=5)
        self.top_reasons_count = config.getint("Drift_Detection", "top_reasons_count", fallback=5)


_drift_config = DriftConfig()


def get_config():
    return _drift_config


def get_feature_type_name(ft):
    type_map = {
        FeatureType.TYPE_NUM: "数值 (Numeric)",
        FeatureType.TYPE_CAT: "分类 (Categorical)",
        FeatureType.TYPE_BOOL: "布尔 (Boolean)",
        FeatureType.TYPE_TEXT: "文本 (Text)",
        FeatureType.TYPE_ALL_NAN: "全缺失 (All-NaN)",
    }
    return type_map.get(ft, f"未知 ({ft})")


def _is_near_zero(val):
    if val is None:
        return False
    if isinstance(val, float) and np.isnan(val):
        return False
    try:
        return abs(float(val)) < NEAR_ZERO_THRESHOLD
    except (TypeError, ValueError):
        return False


def _is_all_missing(base_stats):
    if base_stats is None:
        return True
    num_values = base_stats.get("num_values")
    if num_values is None:
        return True
    return num_values.number == 0


def _is_constant_numeric(source_stats, compare_stats):
    if source_stats is None or compare_stats is None:
        return False
    src_std = source_stats.get("std")
    cmp_std = compare_stats.get("std")
    try:
        src_std_zero = src_std is not None and (np.isnan(src_std) or abs(float(src_std)) < NEAR_ZERO_THRESHOLD)
        cmp_std_zero = cmp_std is not None and (np.isnan(cmp_std) or abs(float(cmp_std)) < NEAR_ZERO_THRESHOLD)
        return src_std_zero or cmp_std_zero
    except (TypeError, ValueError):
        return False


def _compute_relative_diff_safe(source_val, compare_val, use_absolute_fallback=False,
                                absolute_threshold=None):
    if source_val is None or compare_val is None:
        return None, 0.0
    if isinstance(source_val, float) and np.isnan(source_val):
        return None, 0.0
    if isinstance(compare_val, float) and np.isnan(compare_val):
        return None, 0.0
    src = float(source_val)
    cmp = float(compare_val)
    diff_abs = abs(cmp - src)
    if _is_near_zero(src) and _is_near_zero(cmp):
        return 0.0, diff_abs
    either_near_zero = _is_near_zero(src) or _is_near_zero(cmp)
    if either_near_zero:
        if use_absolute_fallback and absolute_threshold is not None:
            if diff_abs >= absolute_threshold:
                abs_percent = min(100.0, diff_abs * 10.0)
                return abs_percent, diff_abs
            return None, diff_abs
        return float('inf'), diff_abs
    rel_diff = diff_abs / abs(src) * 100.0
    if rel_diff > MAX_RELATIVE_DIFF_THRESHOLD and use_absolute_fallback and absolute_threshold is not None:
        if diff_abs >= absolute_threshold:
            abs_percent = min(100.0, diff_abs * 10.0)
            return abs_percent, diff_abs
        return None, diff_abs
    return rel_diff, diff_abs


def _compute_absolute_diff_percent(source_val, compare_val):
    if source_val is None or compare_val is None:
        return None
    return abs(compare_val - source_val)


def _classify_severity(diff_percent):
    cfg = get_config()
    if diff_percent is None or diff_percent == float('inf') or np.isnan(diff_percent):
        return "low"
    if diff_percent >= cfg.severity_high_threshold:
        return "high"
    elif diff_percent >= cfg.severity_medium_threshold:
        return "medium"
    return "low"


def _make_drift_item(drift_type, sub_type, label, source_val, compare_val,
                     diff_value, diff_percent, max_weight, category):
    cfg = get_config()
    severity = _classify_severity(diff_percent)
    if diff_percent is None or diff_percent == float('inf') or (isinstance(diff_percent, float) and np.isnan(diff_percent)):
        normalized_score = 0.0
    else:
        normalized_score = min(100.0, float(diff_percent))
    weighted_score = (normalized_score / 100.0) * max_weight
    return {
        "type": drift_type,
        "sub_type": sub_type,
        "label": label,
        "source_value": source_val,
        "compare_value": compare_val,
        "diff_value": diff_value,
        "diff_percent": diff_percent,
        "normalized_score": normalized_score,
        "weighted_score": weighted_score,
        "severity": severity,
        "category": category
    }


def detect_missing_rate_drift(source_base, compare_base):
    cfg = get_config()
    source_all_missing = _is_all_missing(source_base)
    compare_all_missing = _is_all_missing(compare_base)
    if source_all_missing and compare_all_missing:
        return []
    if source_all_missing or compare_all_missing:
        source_missing = 100.0 if source_all_missing else (
            source_base["num_missing"].perc if source_base["num_missing"].perc is not None else 0.0
        )
        compare_missing = 100.0 if compare_all_missing else (
            compare_base["num_missing"].perc if compare_base["num_missing"].perc is not None else 0.0
        )
        diff_abs = abs(compare_missing - source_missing)
        if diff_abs < cfg.missing_rate_threshold:
            return []
        label = "全缺失列变化" if source_all_missing or compare_all_missing else "缺失率差异"
        if source_all_missing:
            label = "Source 全缺失，Compare 有数据"
        elif compare_all_missing:
            label = "Compare 全缺失，Source 有数据"
        item = _make_drift_item(
            drift_type="missing_rate",
            sub_type="all_missing" if (source_all_missing or compare_all_missing) else "missing_rate",
            label=label,
            source_val=source_missing,
            compare_val=compare_missing,
            diff_value=diff_abs,
            diff_percent=diff_abs,
            max_weight=cfg.weight_missing_rate,
            category="basic"
        )
        return [item]
    source_missing = source_base["num_missing"].perc if source_base["num_missing"].perc is not None else 0.0
    compare_missing = compare_base["num_missing"].perc if compare_base["num_missing"].perc is not None else 0.0
    diff_abs = _compute_absolute_diff_percent(source_missing, compare_missing)
    if diff_abs is None or diff_abs < cfg.missing_rate_threshold:
        return []
    item = _make_drift_item(
        drift_type="missing_rate",
        sub_type="missing_rate",
        label="缺失率差异",
        source_val=source_missing,
        compare_val=compare_missing,
        diff_value=diff_abs,
        diff_percent=diff_abs,
        max_weight=cfg.weight_missing_rate,
        category="basic"
    )
    return [item]


def detect_distinct_count_drift(source_base, compare_base):
    cfg = get_config()
    if _is_all_missing(source_base) or _is_all_missing(compare_base):
        return []
    source_distinct_count = source_base.get("num_distinct", {}).number if hasattr(source_base.get("num_distinct", {}), 'number') else 0
    compare_distinct_count = compare_base.get("num_distinct", {}).number if hasattr(compare_base.get("num_distinct", {}), 'number') else 0
    if source_distinct_count <= 1 and compare_distinct_count <= 1:
        return []
    source_distinct = source_base["num_distinct"].perc if source_base["num_distinct"].perc is not None else 0.0
    compare_distinct = compare_base["num_distinct"].perc if compare_base["num_distinct"].perc is not None else 0.0
    diff_rel, diff_abs = _compute_relative_diff_safe(
        source_distinct, compare_distinct, use_absolute_fallback=True,
        absolute_threshold=5.0
    )
    if diff_rel is None or diff_rel == float('inf') or diff_rel < cfg.distinct_count_threshold:
        return []
    item = _make_drift_item(
        drift_type="distinct_count",
        sub_type="distinct_count",
        label="唯一值占比差异",
        source_val=source_distinct,
        compare_val=compare_distinct,
        diff_value=diff_abs,
        diff_percent=diff_rel,
        max_weight=cfg.weight_distinct_count,
        category="basic"
    )
    return [item]


def detect_numeric_quantile_drift(source_stats, compare_stats):
    cfg = get_config()
    if source_stats is None or compare_stats is None:
        return []
    items = []
    is_constant = _is_constant_numeric(source_stats, compare_stats)
    quantile_map = [
        ("perc95", "95%分位数"),
        ("perc75", "Q3 (75%分位数)"),
        ("perc50", "中位数"),
        ("perc25", "Q1 (25%分位数)"),
        ("perc5", "5%分位数"),
        ("mean", "均值"),
        ("std", "标准差"),
    ]
    total_quantiles = len(quantile_map)
    weight_per_quantile = cfg.weight_numeric_quantile / total_quantiles if total_quantiles > 0 else 0
    for q_key, q_label in quantile_map:
        source_val = source_stats.get(q_key)
        compare_val = compare_stats.get(q_key)
        if source_val is None or compare_val is None:
            continue
        if isinstance(source_val, float) and np.isnan(source_val):
            continue
        if isinstance(compare_val, float) and np.isnan(compare_val):
            continue
        use_absolute = is_constant or _is_near_zero(source_val) or _is_near_zero(compare_val)
        if use_absolute:
            diff_abs = abs(float(compare_val) - float(source_val))
            if diff_abs < cfg.numeric_quantile_absolute_threshold:
                continue
            diff_percent = min(100.0, diff_abs * 10.0)
            label = f"{q_label} (常量/近零列，绝对差异)"
        else:
            diff_rel, diff_abs = _compute_relative_diff_safe(
                source_val, compare_val,
                use_absolute_fallback=True,
                absolute_threshold=cfg.numeric_quantile_absolute_threshold
            )
            if diff_rel is None or diff_rel == float('inf') or diff_rel < cfg.numeric_quantile_threshold:
                continue
            diff_percent = diff_rel
            label = q_label
        item = _make_drift_item(
            drift_type="quantile",
            sub_type=q_key,
            label=label,
            source_val=float(source_val),
            compare_val=float(compare_val),
            diff_value=diff_abs,
            diff_percent=diff_percent,
            max_weight=weight_per_quantile,
            category="numeric"
        )
        items.append(item)
    return items


def detect_category_top_drift(source_counts, compare_counts, source_total, compare_total):
    cfg = get_config()
    if source_counts is None or compare_counts is None:
        return []
    source_vc = source_counts["value_counts_without_nan"]
    compare_vc = compare_counts["value_counts_without_nan"]
    if len(source_vc) == 0 or len(compare_vc) == 0:
        return []
    items = []
    source_top = source_vc.head(cfg.category_top_n)
    compare_top = compare_vc.head(cfg.category_top_n)
    source_top_set = set(source_top.index)
    compare_top_set = set(compare_top.index)
    source_only = source_top_set - compare_top_set
    compare_only = compare_top_set - source_top_set
    if len(source_only) > 0 or len(compare_only) > 0:
        membership_diff = (len(source_only) + len(compare_only)) * 20.0
        item = _make_drift_item(
            drift_type="category_membership",
            sub_type="top_membership",
            label=f"Top {cfg.category_top_n} 类别成员变化",
            source_val=list(source_top_set),
            compare_val=list(compare_top_set),
            diff_value=len(source_only) + len(compare_only),
            diff_percent=membership_diff,
            max_weight=cfg.weight_category_top * 0.4,
            category="category"
        )
        item["source_only"] = list(source_only)
        item["compare_only"] = list(compare_only)
        items.append(item)
    common_top = source_top_set & compare_top_set
    if len(common_top) > 0:
        weight_per_cat = cfg.weight_category_top * 0.6 / len(common_top)
    else:
        weight_per_cat = 0
    for cat in common_top:
        try:
            source_count = source_vc.get(cat, 0)
            compare_count = compare_vc.get(cat, 0)
            source_perc = source_count / source_total * 100.0 if source_total > 0 else 0
            compare_perc = compare_count / compare_total * 100.0 if compare_total > 0 else 0
            diff_abs = _compute_absolute_diff_percent(source_perc, compare_perc)
            if diff_abs is None or diff_abs < cfg.category_top_threshold:
                continue
            item = _make_drift_item(
                drift_type="category_ratio",
                sub_type=str(cat),
                label=f"类别 '{cat}' 占比差异",
                source_val=float(source_perc),
                compare_val=float(compare_perc),
                diff_value=diff_abs,
                diff_percent=diff_abs,
                max_weight=weight_per_cat,
                category="category"
            )
            items.append(item)
        except (TypeError, KeyError):
            continue
    return items


def detect_type_mismatch(source_type, compare_type):
    cfg = get_config()
    if source_type == compare_type:
        return None
    if source_type == FeatureType.TYPE_ALL_NAN or compare_type == FeatureType.TYPE_ALL_NAN:
        return None
    src_name = get_feature_type_name(source_type)
    cmp_name = get_feature_type_name(compare_type)
    diff_percent = 100.0
    item = _make_drift_item(
        drift_type="type_mismatch",
        sub_type="type_mismatch",
        label=f"字段类型不一致: Source={src_name} → Compare={cmp_name}",
        source_val=src_name,
        compare_val=cmp_name,
        diff_value=1.0,
        diff_percent=diff_percent,
        max_weight=TYPE_MISMATCH_WEIGHT,
        category="basic"
    )
    return item


def aggregate_feature_drift(all_drift_items, feature_type, type_mismatch=None):
    cfg = get_config()
    result = {
        "has_drift": False,
        "drift_score": 0.0,
        "severity": "none",
        "top_reasons": [],
        "all_drifts": all_drift_items,
        "category_scores": {
            "basic": 0.0,
            "numeric": 0.0,
            "category": 0.0,
        },
        "type_mismatch": type_mismatch is not None,
    }
    if type_mismatch is not None:
        src_type, cmp_type = type_mismatch
        result["source_type"] = get_feature_type_name(src_type)
        result["compare_type"] = get_feature_type_name(cmp_type)
    if len(all_drift_items) == 0:
        return result
    total_score = 0.0
    for item in all_drift_items:
        total_score += item["weighted_score"]
        cat = item["category"]
        result["category_scores"][cat] += item["weighted_score"]
    result["drift_score"] = min(100.0, total_score)
    if result["type_mismatch"]:
        if result["drift_score"] < cfg.drift_score_medium_threshold:
            result["drift_score"] = cfg.drift_score_medium_threshold + 1.0
    if result["drift_score"] >= cfg.drift_score_high_threshold:
        result["severity"] = "high"
    elif result["drift_score"] >= cfg.drift_score_medium_threshold:
        result["severity"] = "medium"
    else:
        result["severity"] = "low"
    sorted_items = sorted(all_drift_items, key=lambda x: x["weighted_score"], reverse=True)
    result["top_reasons"] = sorted_items[:cfg.top_reasons_count]
    if len(sorted_items) > 0 and result["drift_score"] > 0:
        result["has_drift"] = True
    elif result["type_mismatch"]:
        result["has_drift"] = True
        result["severity"] = "high"
    else:
        result["has_drift"] = False
        result["severity"] = "none"
    return result


def compute_feature_drift(feature_type, source_type, compare_type,
                          source_base, compare_base,
                          source_stats=None, compare_stats=None,
                          source_counts=None, compare_counts=None,
                          source_total=None, compare_total=None):
    cfg = get_config()
    empty_result = {
        "has_drift": False,
        "drift_score": 0.0,
        "severity": "none",
        "top_reasons": [],
        "all_drifts": [],
        "category_scores": {"basic": 0.0, "numeric": 0.0, "category": 0.0},
        "type_mismatch": False,
    }
    if not cfg.enabled:
        return empty_result
    type_mismatch_info = None
    all_items = []
    type_mismatch_item = detect_type_mismatch(source_type, compare_type)
    if type_mismatch_item is not None:
        type_mismatch_info = (source_type, compare_type)
        all_items.append(type_mismatch_item)
    source_all_missing = _is_all_missing(source_base)
    compare_all_missing = _is_all_missing(compare_base)
    if source_all_missing and compare_all_missing:
        if type_mismatch_info is not None:
            return aggregate_feature_drift(all_items, feature_type, type_mismatch_info)
        return empty_result
    all_items.extend(detect_missing_rate_drift(source_base, compare_base))
    if not (source_all_missing or compare_all_missing):
        all_items.extend(detect_distinct_count_drift(source_base, compare_base))
    if type_mismatch_info is None:
        if feature_type == FeatureType.TYPE_NUM and not (source_all_missing or compare_all_missing):
            all_items.extend(detect_numeric_quantile_drift(source_stats, compare_stats))
        if feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL, FeatureType.TYPE_TEXT) \
                and not (source_all_missing or compare_all_missing):
            all_items.extend(detect_category_top_drift(source_counts, compare_counts,
                                                       source_total, compare_total))
    return aggregate_feature_drift(all_items, feature_type, type_mismatch_info)
