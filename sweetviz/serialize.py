import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from sweetviz.sv_types import NumWithPercent, FeatureType
from sweetviz.diagnostics import (
    SweetvizProcessingError, SweetvizResourceError, warn, ErrorCategory,
    DiagnosticManager, _resolve_diag
)


SCHEMA_VERSION = "1.0"

FEATURE_REQUIRED_FIELDS = ["name", "type", "base_stats"]
FEATURE_OPTIONAL_FIELDS = ["stats", "detail", "compare", "drift"]
COMPARE_REQUIRED_FIELDS = ["type", "base_stats"]
COMPARE_OPTIONAL_FIELDS = ["stats"]
TOP_LEVEL_REQUIRED_FIELDS = ["metadata", "source_summary", "features"]
TOP_LEVEL_CONDITIONAL_FIELDS = {
    "compare_summary": "当存在 compare_name 时必需",
    "target": "当存在 _target 时必需",
    "associations": "当存在 _associations 时必需",
    "associations_compare": "当存在 _associations_compare 时必需",
}

_SCHEMA_DOC = f"""
JSON Export Schema (v{SCHEMA_VERSION})
==========================
核心契约（缺失必抛 SweetvizProcessingError）：
  - 顶层: {TOP_LEVEL_REQUIRED_FIELDS}
  - 特征层: {FEATURE_REQUIRED_FIELDS}
  - compare 子结构: {COMPARE_REQUIRED_FIELDS}
条件必需（满足条件时缺失必抛）：
  {TOP_LEVEL_CONDITIONAL_FIELDS}
可选字段（失败仅 warn 降级，不中断）：
  - 特征层: {FEATURE_OPTIONAL_FIELDS}
  - compare 子结构: {COMPARE_OPTIONAL_FIELDS}
  - 顶层: drift_summary, drift 计算
"""


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


def _extract_compare(feature_dict: dict,
                     diag: Optional[DiagnosticManager] = None) -> Optional[dict]:
    """提取 compare 子结构。

    核心字段（type/base_stats）缺失必抛 SweetvizProcessingError；
    可选字段（stats）失败降级记录到 warning。
    """
    compare_dict = feature_dict.get("compare")
    if compare_dict is None:
        return None

    feature_name = feature_dict.get("name", "unknown")
    compare_type = compare_dict.get("type")
    if compare_type is None:
        raise SweetvizProcessingError(
            f"阶段: compare 结构提取 | 特征 '{feature_name}' 的 compare 缺少核心字段 'type'",
            resolution=f"compare 子结构必须包含 {COMPARE_REQUIRED_FIELDS} 字段，请重新生成报告"
        )
    if "base_stats" not in compare_dict:
        raise SweetvizProcessingError(
            f"阶段: compare 结构提取 | 特征 '{feature_name}' 的 compare 缺少核心字段 'base_stats'",
            resolution=f"compare 子结构必须包含 {COMPARE_REQUIRED_FIELDS} 字段，请重新生成报告"
        )

    result = {}
    result["type"] = _feature_type_to_string(compare_dict["type"])
    try:
        result["base_stats"] = _extract_base_stats(compare_dict)
    except Exception as e:
        raise SweetvizProcessingError(
            f"阶段: compare 结构提取 | 特征: '{feature_name}' | 提取 compare.base_stats 失败: {e}",
            resolution="请检查 compare 子结构的 base_stats 数据是否完整",
            original_error=e
        ) from e

    try:
        if "stats" in compare_dict and compare_dict.get("stats"):
            result["stats"] = _extract_stats(compare_dict)
    except Exception as e:
        _resolve_diag(diag).warn(
            f"阶段: compare 可选字段提取 | 特征 '{feature_name}' 提取 compare.stats 失败: {e}",
            category=ErrorCategory.PROCESSING,
            resolution="compare.stats 字段将被省略，不影响其他核心数据"
        )

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


def _extract_feature(feature_dict: dict, include_drift: bool = True,
                     diag: Optional[DiagnosticManager] = None) -> dict:
    """提取单个特征的数据。

    核心字段（name/type/is_target/base_stats）缺失必抛 SweetvizProcessingError；
    可选字段（stats/details/compare/drift）失败降级记录到 warning，不中断整体导出。
    """
    feature_name = feature_dict.get("name")
    feature_type = feature_dict.get("type")

    if feature_name is None:
        raise SweetvizProcessingError(
            "阶段: 核心字段提取 | 特征缺少核心字段 'name'",
            resolution=f"请检查报告数据结构，每个特征必须包含 {FEATURE_REQUIRED_FIELDS} 字段"
        )

    if feature_type is None:
        raise SweetvizProcessingError(
            f"阶段: 核心字段提取 | 特征 '{feature_name}' 缺少核心字段 'type'",
            resolution=f"请检查特征处理流程，{FEATURE_REQUIRED_FIELDS} 为必需字段"
        )

    if "base_stats" not in feature_dict:
        raise SweetvizProcessingError(
            f"阶段: 核心字段提取 | 特征 '{feature_name}' 缺少核心字段 'base_stats'",
            resolution=f"base_stats 是必需字段，包含 num_values/num_missing 等核心统计，请重新生成报告"
        )

    result = {
        "name": feature_name,
        "display_name": feature_dict.get("display_name", feature_name),
        "type": _feature_type_to_string(feature_type),
        "is_target": feature_dict.get("is_target", False),
    }

    try:
        result["base_stats"] = _extract_base_stats(feature_dict)
    except Exception as e:
        raise SweetvizProcessingError(
            f"阶段: 核心字段提取 | 特征: '{feature_name}' | 提取 base_stats 失败: {e}",
            resolution="请检查 base_stats 数据结构是否完整，num_values/num_missing 等字段是否存在",
            original_error=e
        ) from e

    try:
        stats = _extract_stats(feature_dict)
        if stats:
            result["stats"] = stats
    except Exception as e:
        _resolve_diag(diag).warn(
            f"阶段: 可选字段提取 | 特征 '{feature_name}' 提取 stats 失败: {e}",
            category=ErrorCategory.PROCESSING,
            resolution="stats 字段将被省略，不影响其他核心数据"
        )

    try:
        details = _extract_details(feature_dict, feature_type)
        if details:
            result["details"] = details
    except Exception as e:
        _resolve_diag(diag).warn(
            f"阶段: 可选字段提取 | 特征 '{feature_name}' 提取 details 失败: {e}",
            category=ErrorCategory.PROCESSING,
            resolution="details 字段将被省略，不影响其他核心数据"
        )

    try:
        compare = _extract_compare(feature_dict, diag=diag)
        if compare:
            result["compare"] = compare
    except SweetvizProcessingError:
        raise
    except Exception as e:
        _resolve_diag(diag).warn(
            f"阶段: 可选字段提取 | 特征 '{feature_name}' 提取 compare 失败: {e}",
            category=ErrorCategory.PROCESSING,
            resolution="compare 字段将被省略，不影响其他核心数据"
        )

    if include_drift and "drift" in feature_dict and feature_dict["drift"] is not None:
        try:
            result["drift"] = _convert_value(feature_dict["drift"])
        except Exception as e:
            _resolve_diag(diag).warn(
                f"阶段: 可选字段提取 | 特征 '{feature_name}' 提取 drift 失败: {e}",
                category=ErrorCategory.PROCESSING,
                resolution="drift 字段将被省略，不影响其他核心数据"
            )

    return result


def compute_all_drifts(report, diag: Optional[DiagnosticManager] = None) -> None:
    """计算所有特征的漂移。属于可选增强，单个失败不影响整体。"""
    actual_diag = diag if diag is not None else getattr(report, '_diag', None)
    if report.compare_name is None:
        return
    for fdict in report._features.values():
        if "drift" not in fdict or fdict["drift"] is None:
            try:
                fdict["drift"] = compute_drift(fdict)
            except Exception as e:
                _resolve_diag(actual_diag).warn(
                    f"计算特征 '{fdict.get('name', 'unknown')}' 的漂移时出错: {e}",
                    category=ErrorCategory.PROCESSING,
                    resolution="该特征的漂移数据将被跳过，不影响其他数据的导出"
                )
    if report._target is not None and "drift" not in report._target:
        try:
            report._target["drift"] = compute_drift(report._target)
        except Exception as e:
            _resolve_diag(actual_diag).warn(
                f"计算目标特征的漂移时出错: {e}",
                category=ErrorCategory.PROCESSING,
                resolution="目标特征的漂移数据将被跳过，不影响其他数据的导出"
            )


def build_report_data(report, include_drift: bool = True,
                      diag: Optional[DiagnosticManager] = None) -> dict:
    """构建报告数据。核心路径失败必须抛异常，可选路径失败降级。

    核心路径（失败抛 SweetvizProcessingError）：
    - metadata 生成
    - source_summary / compare_summary 提取
    - features 字典构建（整体）
    - target 特征提取（如果存在）
    - associations / associations_compare 提取

    可选路径（失败 warn 后降级）：
    - 单个特征的 drift 计算
    - drift_summary 生成
    """
    actual_diag = diag if diag is not None else getattr(report, '_diag', None)

    # ---- 核心路径 1: metadata ----
    try:
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
    except Exception as e:
        raise SweetvizProcessingError(
            f"阶段: metadata 生成 | 生成报告元数据失败: {e}",
            resolution="请检查系统时间和报告对象是否有效",
            original_error=e
        ) from e

    # ---- 核心路径 2: source_summary / compare_summary ----
    # source_summary 是必需字段
    if not hasattr(report, "summary_source") or report.summary_source is None:
        raise SweetvizProcessingError(
            "阶段: 摘要提取 | 缺少必需字段 'summary_source'",
            resolution="source_summary 是核心字段，请确保报告生成流程正常完成"
        )
    try:
        source_summary = _convert_value(report.summary_source)
    except Exception as e:
        raise SweetvizProcessingError(
            f"阶段: 摘要提取 | 提取 source_summary 失败: {e}",
            resolution="请检查报告生成流程是否正常完成，summary_source 字段是否存在",
            original_error=e
        ) from e

    # compare_summary 是 compare 报告的必需字段
    if report.compare_name is not None:
        if not hasattr(report, "summary_compare") or report.summary_compare is None:
            raise SweetvizProcessingError(
                "阶段: 摘要提取 | 比较报告缺少必需字段 'summary_compare'",
                resolution="compare_summary 是比较报告的核心字段，请确保比较报告生成流程正常完成"
            )
        try:
            compare_summary = _convert_value(report.summary_compare)
        except Exception as e:
            raise SweetvizProcessingError(
                f"阶段: 摘要提取 | 提取 compare_summary 失败: {e}",
                resolution="请检查比较报告生成流程是否正常完成",
                original_error=e
            ) from e
    else:
        compare_summary = None

    # ---- 可选路径: drift 计算（失败降级）----
    if include_drift and report.compare_name is not None:
        try:
            compute_all_drifts(report, diag=actual_diag)
        except Exception as e:
            _resolve_diag(actual_diag).warn(
                f"漂移计算整体失败: {e}",
                category=ErrorCategory.PROCESSING,
                resolution="所有漂移数据将被跳过，不影响其他数据的导出"
            )

    # ---- 核心路径 3: features 字典构建 ----
    features = {}
    for fname, fdict in report._features.items():
        try:
            features[fname] = _extract_feature(fdict, include_drift=include_drift, diag=actual_diag)
        except SweetvizProcessingError:
            raise
        except Exception as e:
            raise SweetvizProcessingError(
                f"阶段: 特征提取 | 特征: '{fname}' | 提取失败: {e}",
                resolution="请检查特征数据结构是否完整，必要时重新生成报告",
                original_error=e
            ) from e

    # ---- 核心路径 4: target 特征提取 ----
    target = None
    if report._target is not None:
        try:
            target = _extract_feature(report._target, include_drift=include_drift, diag=actual_diag)
        except SweetvizProcessingError as e:
            raise SweetvizProcessingError(
                f"阶段: 目标特征提取 | {e}",
                resolution=e.resolution,
                original_error=e
            ) from e
        except Exception as e:
            raise SweetvizProcessingError(
                f"阶段: 目标特征提取 | 提取目标特征失败: {e}",
                resolution="请检查目标特征数据结构是否完整，必要时重新生成报告",
                original_error=e
            ) from e

    # ---- 核心路径 5: associations 提取（条件必需）----
    # associations 如果存在则是必需字段，损坏必须抛异常
    associations = None
    if hasattr(report, "_associations") and report._associations is not None:
        try:
            associations = _convert_value(report._associations)
        except Exception as e:
            raise SweetvizProcessingError(
                f"阶段: 关联数据提取 | 提取 associations 失败: {e}",
                resolution="请检查关联分析流程是否正常完成",
                original_error=e
            ) from e

    associations_compare = None
    if hasattr(report, "_associations_compare") and report._associations_compare is not None:
        try:
            associations_compare = _convert_value(report._associations_compare)
        except Exception as e:
            raise SweetvizProcessingError(
                f"阶段: 关联数据提取 | 提取 associations_compare 失败: {e}",
                resolution="请检查比较报告的关联分析流程是否正常完成",
                original_error=e
            ) from e

    # ---- 可选路径: drift_summary（失败降级）----
    drift_summary = None
    if include_drift and report.compare_name is not None:
        try:
            all_features_for_summary = {}
            for fname, fdict in report._features.items():
                all_features_for_summary[fname] = fdict
            if report._target is not None:
                all_features_for_summary[report._target.get("name")] = report._target
            drift_summary = compute_drift_summary(all_features_for_summary)
        except Exception as e:
            _resolve_diag(actual_diag).warn(
                f"生成漂移摘要时出错: {e}",
                category=ErrorCategory.PROCESSING,
                resolution="漂移摘要将被省略，不影响其他数据的导出"
            )

    # ---- 组装结果 ----
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
            indent: int = 2, diag: Optional[DiagnosticManager] = None) -> str:
    """导出 JSON。核心路径失败抛异常，可选路径失败降级。"""
    actual_diag = diag if diag is not None else getattr(report, '_diag', None)
    try:
        data = build_report_data(report, include_drift=include_drift, diag=actual_diag)
        json_str = json.dumps(data, ensure_ascii=False, indent=indent, default=str)
    except SweetvizProcessingError:
        # 已经是包装好的核心路径异常，直接抛出
        raise
    except (TypeError, ValueError) as e:
        exc = SweetvizProcessingError(
            f"阶段: JSON 序列化 | 序列化失败: {e}",
            resolution="请检查报告数据是否包含无法序列化的类型",
            original_error=e
        )
        _resolve_diag(actual_diag).warn(
            f"JSON 序列化失败: {e}",
            category=ErrorCategory.PROCESSING,
            resolution=exc.resolution
        )
        raise exc from e
    except Exception as e:
        # 其他未预期的异常，包装后抛出
        exc = SweetvizProcessingError(
            f"阶段: JSON 导出 | 未预期错误: {e}",
            resolution="请检查报告对象是否完整，或尝试重新生成报告",
            original_error=e
        )
        _resolve_diag(actual_diag).warn(
            f"JSON 导出未预期错误: {e}",
            category=ErrorCategory.PROCESSING,
            resolution=exc.resolution
        )
        raise exc from e

    if filepath is not None:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_str)
        except IOError as e:
            exc = SweetvizResourceError(
                f"无法写入 JSON 文件: {filepath}",
                resolution="请检查文件路径是否正确，以及是否有写入权限",
                original_error=e
            )
            _resolve_diag(actual_diag).warn(
                f"JSON 文件写入失败: {filepath}: {e}",
                category=ErrorCategory.RESOURCE,
                resolution=exc.resolution
            )
            raise exc from e
    return json_str
