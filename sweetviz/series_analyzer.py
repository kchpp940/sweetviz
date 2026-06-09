import pandas as pd
import numpy as np
from sweetviz.sv_types import NumWithPercent, FeatureType, FeatureToProcess
from sweetviz.type_detection import determine_feature_type
import sweetviz.series_analyzer_numeric
import sweetviz.series_analyzer_cat
import sweetviz.series_analyzer_text


MISSING_RATE_DRIFT_THRESHOLD = 5.0
DISTINCT_COUNT_DRIFT_THRESHOLD = 20.0
NUMERIC_QUANTILE_DRIFT_THRESHOLD = 15.0
CATEGORY_TOP_DRIFT_THRESHOLD = 10.0


def compute_relative_diff(source_val, compare_val):
    if source_val is None or compare_val is None:
        return None
    if source_val == 0 and compare_val == 0:
        return 0.0
    if source_val == 0:
        return float('inf') if compare_val > 0 else 0.0
    return abs(compare_val - source_val) / abs(source_val) * 100.0


def compute_absolute_diff_percent(source_val, compare_val):
    if source_val is None or compare_val is None:
        return None
    return abs(compare_val - source_val)


def detect_base_stats_drift(source_stats, compare_stats):
    drift_info = dict()
    drift_info["has_drift"] = False
    drift_info["drifts"] = list()

    source_missing_perc = source_stats["num_missing"].perc if source_stats["num_missing"].perc is not None else 0.0
    compare_missing_perc = compare_stats["num_missing"].perc if compare_stats["num_missing"].perc is not None else 0.0
    missing_diff = compute_absolute_diff_percent(source_missing_perc, compare_missing_perc)
    if missing_diff is not None and missing_diff >= MISSING_RATE_DRIFT_THRESHOLD:
        drift_info["drifts"].append({
            "type": "missing_rate",
            "label": "缺失率差异",
            "source": source_missing_perc,
            "compare": compare_missing_perc,
            "diff": missing_diff,
            "severity": "high" if missing_diff >= 20.0 else "medium"
        })

    source_distinct_perc = source_stats["num_distinct"].perc if source_stats["num_distinct"].perc is not None else 0.0
    compare_distinct_perc = compare_stats["num_distinct"].perc if compare_stats["num_distinct"].perc is not None else 0.0
    distinct_diff = compute_relative_diff(source_distinct_perc, compare_distinct_perc)
    if distinct_diff is not None and distinct_diff != float('inf') and distinct_diff >= DISTINCT_COUNT_DRIFT_THRESHOLD:
        drift_info["drifts"].append({
            "type": "distinct_count",
            "label": "唯一值数量差异",
            "source": source_distinct_perc,
            "compare": compare_distinct_perc,
            "diff": distinct_diff,
            "severity": "high" if distinct_diff >= 50.0 else "medium"
        })

    if len(drift_info["drifts"]) > 0:
        drift_info["has_drift"] = True
        drift_info["max_severity"] = "high" if any(d["severity"] == "high" for d in drift_info["drifts"]) else "medium"
    else:
        drift_info["max_severity"] = None

    return drift_info


def detect_numeric_stats_drift(source_stats, compare_stats):
    drift_info = dict()
    drift_info["has_drift"] = False
    drift_info["drifts"] = list()

    if source_stats is None or compare_stats is None:
        return drift_info

    quantiles_to_check = ["perc95", "perc75", "perc50", "perc25", "perc5", "mean", "std"]
    quantile_labels = {
        "perc95": "95%分位数",
        "perc75": "Q3",
        "perc50": "中位数",
        "perc25": "Q1",
        "perc5": "5%分位数",
        "mean": "均值",
        "std": "标准差"
    }

    for q in quantiles_to_check:
        source_val = source_stats.get(q)
        compare_val = compare_stats.get(q)
        if source_val is None or compare_val is None or np.isnan(source_val) or np.isnan(compare_val):
            continue
        if source_val == 0 and compare_val == 0:
            continue
        diff = compute_relative_diff(source_val, compare_val)
        if diff is not None and diff != float('inf') and diff >= NUMERIC_QUANTILE_DRIFT_THRESHOLD:
            drift_info["drifts"].append({
                "type": f"quantile_{q}",
                "label": quantile_labels.get(q, q),
                "source": source_val,
                "compare": compare_val,
                "diff": diff,
                "severity": "high" if diff >= 30.0 else "medium"
            })

    if len(drift_info["drifts"]) > 0:
        drift_info["has_drift"] = True
        drift_info["max_severity"] = "high" if any(d["severity"] == "high" for d in drift_info["drifts"]) else "medium"
    else:
        drift_info["max_severity"] = None

    return drift_info


def detect_category_top_drift(source_counts, compare_counts, source_total, compare_total, top_n=5):
    drift_info = dict()
    drift_info["has_drift"] = False
    drift_info["drifts"] = list()

    if source_counts is None or compare_counts is None:
        return drift_info

    source_value_counts = source_counts["value_counts_without_nan"]
    compare_value_counts = compare_counts["value_counts_without_nan"]

    if len(source_value_counts) == 0 or len(compare_value_counts) == 0:
        return drift_info

    source_top = source_value_counts.head(top_n)
    compare_top = compare_value_counts.head(top_n)

    source_top_set = set(source_top.index)
    compare_top_set = set(compare_top.index)
    new_in_source_only = source_top_set - compare_top_set
    new_in_compare_only = compare_top_set - source_top_set

    if len(new_in_source_only) > 0 or len(new_in_compare_only) > 0:
        drift_info["drifts"].append({
            "type": "top_category_membership",
            "label": f"Top类别成员变化",
            "source_only": list(new_in_source_only),
            "compare_only": list(new_in_compare_only),
            "diff": len(new_in_source_only) + len(new_in_compare_only),
            "severity": "high" if (len(new_in_source_only) + len(new_in_compare_only) >= 3) else "medium"
        })

    common_top = source_top_set & compare_top_set
    for cat in common_top:
        try:
            source_perc = source_value_counts.get(cat, 0) / source_total * 100.0 if source_total > 0 else 0
            compare_perc = compare_value_counts.get(cat, 0) / compare_total * 100.0 if compare_total > 0 else 0
            diff = compute_absolute_diff_percent(source_perc, compare_perc)
            if diff is not None and diff >= CATEGORY_TOP_DRIFT_THRESHOLD:
                drift_info["drifts"].append({
                    "type": f"category_{cat}",
                    "label": f"类别 '{cat}' 占比差异",
                    "source": source_perc,
                    "compare": compare_perc,
                    "diff": diff,
                    "severity": "high" if diff >= 20.0 else "medium"
                })
        except (TypeError, KeyError):
            continue

    if len(drift_info["drifts"]) > 0:
        drift_info["has_drift"] = True
        drift_info["max_severity"] = "high" if any(d["severity"] == "high" for d in drift_info["drifts"]) else "medium"
    else:
        drift_info["max_severity"] = None

    return drift_info


def get_counts(series: pd.Series) -> dict:
    # The value_counts() function is used to get a Series containing counts of unique values.
    value_counts_with_nan = series.value_counts(dropna=False)

    # Fix for data with only a single value; reset_index was flipping the data returned
    if len(value_counts_with_nan) == 1:
        if pd.isna(value_counts_with_nan.index[0]):
            value_counts_without_nan = pd.Series()
        else:
            value_counts_without_nan = value_counts_with_nan
    else:
        reset_value_counts = value_counts_with_nan.reset_index()
        # Force column naming behavior to be similar for value_counts() being reset between 1.x and 2.x.: make sure col 0 is "index" and 1 is series.name
        # -> This is a no-op in Pandas 1.x
        reset_value_counts.rename(columns={reset_value_counts.columns[0]: "index", reset_value_counts.columns[1]:series.name}, inplace=True)

        value_counts_without_nan = (reset_value_counts.dropna().set_index("index").iloc[:, 0])
    # print(value_counts_without_nan.index.dtype.name)

    # IGNORING NAN FOR NOW AS IT CAUSES ISSUES [FIX]
    # distinct_count_with_nan = value_counts_with_nan.count()

    distinct_count_without_nan = value_counts_without_nan.count()
    return {
        "value_counts_without_nan": value_counts_without_nan,
        "distinct_count_without_nan": distinct_count_without_nan,
        "num_rows_with_data": series.count(),
        "num_rows_total": len(series),
        # IGNORING NAN FOR NOW AS IT CAUSES ISSUES [FIX]:
        # "value_counts_with_nan": value_counts_with_nan,
        # "distinct_count_with_nan": distinct_count_with_nan,
    }


def fill_out_missing_counts_in_other_series(my_counts:dict, other_counts:dict):
    # IGNORING NAN FOR NOW AS IT CAUSES ISSUES [FIX]
    # to_fill_list = ["value_counts_with_nan", "value_counts_without_nan"]
    to_fill_list = ["value_counts_without_nan"]
    for to_fill in to_fill_list:
        fill_using_strings = True if my_counts[to_fill].index.dtype.name in ('category', 'object') else False
        for key, value in other_counts[to_fill].items():
            if key not in my_counts[to_fill]:
                # If categorical, must do this hack to add new value
                if my_counts[to_fill].index.dtype.name == 'category':
                    my_counts[to_fill] = my_counts[to_fill].reindex(my_counts[to_fill].index.add_categories(key))

                # Add empty value at new index, but make sure we are using the right index type
                if fill_using_strings:
                    my_counts[to_fill].at[str(key)] = 0
                else:
                    my_counts[to_fill].at[key] = 0

def add_series_base_stats_to_dict(series: pd.Series, counts: dict, updated_dict: dict) -> dict:
    updated_dict["stats"] = dict()
    updated_dict["base_stats"] = dict()
    base_stats = updated_dict["base_stats"]
    num_total = counts["num_rows_total"]
    try:
        num_zeros = series[series == 0].count()
    except TypeError:
        num_zeros = 0
    non_nan = counts["num_rows_with_data"]
    base_stats["total_rows"] = num_total
    base_stats["num_values"] = NumWithPercent(non_nan, num_total)
    base_stats["num_missing"] = NumWithPercent(num_total - non_nan, num_total)
    base_stats["num_zeroes"] = NumWithPercent(num_zeros, num_total)
    base_stats["num_distinct"] = NumWithPercent(counts["distinct_count_without_nan"], num_total)


# This generates everything EXCEPT the "detail pane"
def analyze_feature_to_dictionary(to_process: FeatureToProcess) -> dict:
    # start = time.perf_counter()

    # Validation: Make sure the targets are the same length as the series
    if to_process.source_target is not None and to_process.source is not None:
        if len(to_process.source_target) != len(to_process.source):
            raise ValueError
    if to_process.compare_target is not None and to_process.compare is not None:
        if len(to_process.compare_target) != len(to_process.compare):
            raise ValueError

    # Initialize some dictionary values
    returned_feature_dict = dict()
    returned_feature_dict["name"] = to_process.source.name
    returned_feature_dict["order_index"] = to_process.order
    returned_feature_dict["is_target"] = True if to_process.order == -1 else False

    # Determine SOURCE feature type
    to_process.source_counts = get_counts(to_process.source)
    returned_feature_dict["type"] = determine_feature_type(to_process.source, to_process.source_counts,
                                                           to_process.predetermined_type, "SOURCE")
    source_type = returned_feature_dict["type"]

    # Determine COMPARED feature type & initialize
    compare_dict = None
    if to_process.compare is not None:
        to_process.compare_counts = get_counts(to_process.compare)
        compare_type = determine_feature_type(to_process.compare,
                                              to_process.compare_counts,
                                              returned_feature_dict["type"], "COMPARED")
        if compare_type != FeatureType.TYPE_ALL_NAN and \
            source_type != FeatureType.TYPE_ALL_NAN:
            # Explicitly show missing categories on each set
            if compare_type == FeatureType.TYPE_CAT or compare_type == FeatureType.TYPE_BOOL:
                fill_out_missing_counts_in_other_series(to_process.compare_counts, to_process.source_counts)
                fill_out_missing_counts_in_other_series(to_process.source_counts, to_process.compare_counts)
        returned_feature_dict["compare"] = dict()
        compare_dict = returned_feature_dict["compare"]
        compare_dict["type"] = compare_type

    # Settle all-NaN series, depending on source versus compared
    if to_process.compare is not None:
        # Settle all-Nan WITH COMPARE: Must consider all cases between source and compare
        if compare_type == FeatureType.TYPE_ALL_NAN and source_type == FeatureType.TYPE_ALL_NAN:
            returned_feature_dict["type"] = FeatureType.TYPE_TEXT
            compare_dict["type"] = FeatureType.TYPE_TEXT
        elif compare_type == FeatureType.TYPE_ALL_NAN:
            compare_dict["type"] = source_type
        elif source_type == FeatureType.TYPE_ALL_NAN:
            returned_feature_dict["type"] = compare_type
    else:
        # Settle all-Nan WITHOUT COMPARE ( trivial: consider as TEXT )
        if source_type == FeatureType.TYPE_ALL_NAN:
            returned_feature_dict["type"] = FeatureType.TYPE_TEXT

    # Establish base stats
    add_series_base_stats_to_dict(to_process.source, to_process.source_counts, returned_feature_dict)
    if to_process.compare is not None:
        add_series_base_stats_to_dict(to_process.compare, to_process.compare_counts, compare_dict)

    # Perform full analysis on source/compare/target
    if returned_feature_dict["type"] == FeatureType.TYPE_NUM:
        sweetviz.series_analyzer_numeric.analyze(to_process, returned_feature_dict)
    elif returned_feature_dict["type"] == FeatureType.TYPE_CAT:
        sweetviz.series_analyzer_cat.analyze(to_process, returned_feature_dict)
    elif returned_feature_dict["type"] == FeatureType.TYPE_BOOL:
        sweetviz.series_analyzer_cat.analyze(to_process, returned_feature_dict)
    elif returned_feature_dict["type"] == FeatureType.TYPE_TEXT:
        sweetviz.series_analyzer_text.analyze(to_process, returned_feature_dict)
    else:
        raise ValueError

    # Perform drift detection if compare is present
    if compare_dict is not None:
        returned_feature_dict["drift"] = dict()
        all_drifts = list()

        base_drift = detect_base_stats_drift(returned_feature_dict["base_stats"], compare_dict["base_stats"])
        if base_drift["has_drift"]:
            all_drifts.extend(base_drift["drifts"])

        if returned_feature_dict["type"] == FeatureType.TYPE_NUM:
            num_drift = detect_numeric_stats_drift(returned_feature_dict.get("stats"), compare_dict.get("stats"))
            if num_drift["has_drift"]:
                all_drifts.extend(num_drift["drifts"])

        if returned_feature_dict["type"] in (FeatureType.TYPE_CAT, FeatureType.TYPE_BOOL, FeatureType.TYPE_TEXT):
            source_total = returned_feature_dict["base_stats"]["num_values"].number
            compare_total = compare_dict["base_stats"]["num_values"].number
            cat_drift = detect_category_top_drift(to_process.source_counts, to_process.compare_counts,
                                                  source_total, compare_total)
            if cat_drift["has_drift"]:
                all_drifts.extend(cat_drift["drifts"])

        returned_feature_dict["drift"]["has_drift"] = len(all_drifts) > 0
        returned_feature_dict["drift"]["drifts"] = all_drifts
        if len(all_drifts) > 0:
            returned_feature_dict["drift"]["max_severity"] = "high" if any(d["severity"] == "high" for d in all_drifts) else "medium"
        else:
            returned_feature_dict["drift"]["max_severity"] = None
    else:
        returned_feature_dict["drift"] = {"has_drift": False, "drifts": [], "max_severity": None}

    # print(f"{to_process.source.name} PROCESSED ------> "
    #       f" {time.perf_counter() - start}")

    return returned_feature_dict
