import math
from typing import Dict, List, Optional, Any

from sweetviz.sv_types import NumWithPercent, FeatureType


SEVERITY_THRESHOLD_HIGH = 15.0
SEVERITY_THRESHOLD_MEDIUM = 5.0

NUMERIC_STATS_GROUP_1 = ["max", "perc95", "perc75", "mean", "perc50", "perc25", "perc5", "min"]
NUMERIC_STATS_GROUP_2 = ["range", "iqr", "std", "variance", "kurtosis", "skewness", "sum"]
ALL_NUMERIC_STATS = NUMERIC_STATS_GROUP_1 + NUMERIC_STATS_GROUP_2

NUMERIC_STAT_LABELS = {
    "max": "最大值",
    "perc95": "95%分位数",
    "perc75": "75%分位数",
    "mean": "平均值",
    "perc50": "中位数",
    "perc25": "25%分位数",
    "perc5": "5%分位数",
    "min": "最小值",
    "range": "极差",
    "iqr": "四分位距",
    "std": "标准差",
    "variance": "方差",
    "kurtosis": "峰度",
    "skewness": "偏度",
    "sum": "总和",
}

BASE_STAT_LABELS = {
    "num_values": "有效值占比差异",
    "num_missing": "缺失率差异",
    "num_distinct": "唯一值占比差异",
    "num_zeroes": "零值占比差异",
}


def _severity_from_score(score: float) -> str:
    if score >= SEVERITY_THRESHOLD_HIGH:
        return "high"
    elif score >= SEVERITY_THRESHOLD_MEDIUM:
        return "medium"
    elif score > 0:
        return "low"
    else:
        return "none"


def _safe_abs_diff_pct(compare_val, source_val) -> Optional[float]:
    if source_val is None or compare_val is None:
        return None
    if not isinstance(source_val, (int, float)) or not isinstance(compare_val, (int, float)):
        return None
    if math.isnan(source_val) or math.isnan(compare_val):
        return None
    if source_val == 0:
        return None
    return abs(((compare_val - source_val) / abs(source_val)) * 100.0)


def _safe_abs_diff_points(compare_perc, source_perc) -> Optional[float]:
    if source_perc is None or compare_perc is None:
        return None
    if not isinstance(source_perc, (int, float)) or not isinstance(compare_perc, (int, float)):
        return None
    if math.isnan(source_perc) or math.isnan(compare_perc):
        return None
    return abs(compare_perc - source_perc)


def _compute_nwp_drift(source_nwp: NumWithPercent, compare_nwp: NumWithPercent) -> Dict:
    if source_nwp is None:
        s = {"number": None, "percentage": None}
    else:
        s = {"number": source_nwp.number, "percentage": source_nwp.perc}
    if compare_nwp is None:
        c = {"number": None, "percentage": None}
    else:
        c = {"number": compare_nwp.number, "percentage": compare_nwp.perc}

    diff_count = None
    if c["number"] is not None and s["number"] is not None:
        try:
            diff_count = c["number"] - s["number"]
        except Exception:
            pass

    diff_pct_points = None
    if c["percentage"] is not None and s["percentage"] is not None:
        try:
            diff_pct_points = c["percentage"] - s["percentage"]
        except Exception:
            pass

    return {
        "source": s,
        "compare": c,
        "diff_count": diff_count,
        "diff_pct_points": diff_pct_points,
    }


def _compute_numeric_stat_drift(source_stats: Dict, compare_stats: Dict) -> Dict:
    drift = {}
    for stat_key in ALL_NUMERIC_STATS:
        if stat_key in source_stats and stat_key in compare_stats:
            s_val = source_stats[stat_key]
            c_val = compare_stats[stat_key]

            s_serialized = s_val
            c_serialized = c_val
            if isinstance(s_val, float) and (math.isnan(s_val) or math.isinf(s_val)):
                s_serialized = None
            if isinstance(c_val, float) and (math.isnan(c_val) or math.isinf(c_val)):
                c_serialized = None

            diff = None
            diff_pct = None
            if s_serialized is not None and c_serialized is not None:
                try:
                    diff = c_serialized - s_serialized
                    if s_serialized != 0:
                        diff_pct = ((c_serialized - s_serialized) / abs(s_serialized)) * 100.0
                except Exception:
                    pass

            drift[stat_key] = {
                "source": s_serialized,
                "compare": c_serialized,
                "diff": diff,
                "diff_pct": diff_pct,
            }
    return drift


def _category_shifts(source_detail: Dict, compare_detail: Dict = None) -> List[Dict]:
    shifts = []
    full_count = source_detail.get("full_count", [])
    for item in full_count:
        if item.get("is_total"):
            continue
        s_cnt = item.get("count")
        c_cnt = item.get("count_compare")
        s_num = s_cnt.number if s_cnt is not None else None
        c_num = c_cnt.number if c_cnt is not None else None
        s_perc = s_cnt.perc if s_cnt is not None else None
        c_perc = c_cnt.perc if c_cnt is not None else None
        diff_count = None
        diff_pct_points = None
        if s_num is not None and c_num is not None:
            try:
                diff_count = c_num - s_num
            except Exception:
                pass
        if s_perc is not None and c_perc is not None:
            try:
                diff_pct_points = c_perc - s_perc
            except Exception:
                pass
        shifts.append({
            "name": item.get("name"),
            "source": {"number": s_num, "percentage": s_perc},
            "compare": {"number": c_num, "percentage": c_perc},
            "diff_count": diff_count,
            "diff_pct_points": diff_pct_points,
        })
    return shifts


def _score_numeric_drift(details: Dict) -> (float, List[str]):
    total_score = 0.0
    reasons = []
    base = details.get("base", {})

    for stat in ["num_missing", "num_distinct"]:
        entry = base.get(stat)
        if entry:
            diff_pts = entry.get("diff_pct_points")
            if diff_pts is not None:
                abs_diff = abs(diff_pts)
                total_score += abs_diff
                if abs_diff >= 2.0:
                    reasons.append(BASE_STAT_LABELS.get(stat, stat))

    num_drift = details.get("numeric_stats", {})
    checked = set()
    for stat in ["std", "mean", "perc95", "perc5", "median", "perc50"]:
        actual_key = stat
        if stat == "median":
            actual_key = "perc50"
        if actual_key in checked:
            continue
        checked.add(actual_key)
        entry = num_drift.get(actual_key)
        if entry and entry.get("diff_pct") is not None:
            abs_pct = abs(entry["diff_pct"])
            total_score += abs_pct * 0.5
            if abs_pct >= 5.0:
                label = NUMERIC_STAT_LABELS.get(actual_key, actual_key)
                if label not in reasons:
                    reasons.append(label)

    return total_score, reasons


def _score_categorical_drift(details: Dict) -> (float, List[str]):
    total_score = 0.0
    reasons = []
    base = details.get("base", {})

    for stat in ["num_missing", "num_distinct"]:
        entry = base.get(stat)
        if entry:
            diff_pts = entry.get("diff_pct_points")
            if diff_pts is not None:
                abs_diff = abs(diff_pts)
                total_score += abs_diff
                if abs_diff >= 2.0:
                    reasons.append(BASE_STAT_LABELS.get(stat, stat))

    shifts = details.get("category_shifts", [])
    top_changes = []
    for shift in shifts:
        diff_pts = shift.get("diff_pct_points")
        if diff_pts is not None:
            abs_diff = abs(diff_pts)
            total_score += abs_diff
            if abs_diff >= 3.0:
                top_changes.append((abs_diff, f"类别 '{shift['name']}' 占比差异"))
    top_changes.sort(reverse=True)
    for _, reason in top_changes[:3]:
        reasons.append(reason)

    return total_score, reasons


def compute_feature_drift(source_dict: Dict, compare_dict: Dict) -> Optional[Dict]:
    if compare_dict is None:
        return None

    feature_type = source_dict.get("type")
    details = {"base": {}}

    source_base = source_dict.get("base_stats", {})
    compare_base = compare_dict.get("base_stats", {})

    for stat_name in ["num_values", "num_missing", "num_distinct"]:
        details["base"][stat_name] = _compute_nwp_drift(
            source_base.get(stat_name), compare_base.get(stat_name)
        )

    if feature_type == FeatureType.TYPE_NUM:
        details["base"]["num_zeroes"] = _compute_nwp_drift(
            source_base.get("num_zeroes"), compare_base.get("num_zeroes")
        )
        details["numeric_stats"] = _compute_numeric_stat_drift(
            source_dict.get("stats", {}), compare_dict.get("stats", {})
        )
        score, reasons = _score_numeric_drift(details)
    elif feature_type in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL, FeatureType.TYPE_TEXT):
        details["category_shifts"] = _category_shifts(source_dict.get("detail", {}))
        score, reasons = _score_categorical_drift(details)
    else:
        score = 0.0
        reasons = []

    score = round(score, 1)
    severity = _severity_from_score(score)

    return {
        "score": score,
        "severity": severity,
        "top_reasons": reasons[:3],
        "details": details,
    }


def compute_report_drift(features: Dict[str, Dict], target: Dict = None) -> Dict:
    all_drifts = []

    if target is not None and target.get("drift") is not None:
        all_drifts.append((target["name"], target["drift"]))

    for feat_name, feat_dict in features.items():
        if feat_dict.get("drift") is not None:
            all_drifts.append((feat_name, feat_dict["drift"]))

    if not all_drifts:
        return None

    all_drifts.sort(key=lambda x: x[1]["score"], reverse=True)

    total_score = sum(d["score"] for _, d in all_drifts)
    avg_score = round(total_score / len(all_drifts), 1) if all_drifts else 0.0
    max_score = all_drifts[0][1]["score"] if all_drifts else 0.0

    severity_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for _, d in all_drifts:
        sev = d.get("severity", "none")
        if sev in severity_counts:
            severity_counts[sev] += 1

    top_features = []
    for feat_name, d in all_drifts:
        top_features.append({
            "feature_name": feat_name,
            "score": d["score"],
            "severity": d["severity"],
            "top_reasons": d["top_reasons"],
        })

    return {
        "num_features": len(all_drifts),
        "average_score": avg_score,
        "max_score": max_score,
        "severity_counts": severity_counts,
        "top_features": top_features,
    }
