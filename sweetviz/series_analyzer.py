import pandas as pd
from sweetviz.sv_types import NumWithPercent, FeatureType, FeatureToProcess
from sweetviz.type_detection import determine_feature_type
from sweetviz.utils import clean_numeric_with_diagnostics
import sweetviz.series_analyzer_numeric
import sweetviz.series_analyzer_cat
import sweetviz.series_analyzer_text


def get_counts(series: pd.Series) -> dict:
    value_counts_with_nan = series.value_counts(dropna=False)

    if len(value_counts_with_nan) == 1:
        if pd.isna(value_counts_with_nan.index[0]):
            value_counts_without_nan = pd.Series(dtype=value_counts_with_nan.dtype)
        else:
            value_counts_without_nan = value_counts_with_nan
    else:
        reset_value_counts = value_counts_with_nan.reset_index()
        reset_value_counts.rename(columns={reset_value_counts.columns[0]: "index", reset_value_counts.columns[1]:series.name}, inplace=True)

        value_counts_without_nan = (reset_value_counts.dropna().set_index("index").iloc[:, 0])

    distinct_count_without_nan = value_counts_without_nan.count()
    return {
        "value_counts_without_nan": value_counts_without_nan,
        "distinct_count_without_nan": distinct_count_without_nan,
        "num_rows_with_data": series.count(),
        "num_rows_total": len(series),
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

def add_series_base_stats_to_dict(series: pd.Series, counts: dict, updated_dict: dict, diagnostics: dict) -> dict:
    updated_dict["stats"] = dict()
    updated_dict["base_stats"] = dict()
    updated_dict["diagnostics"] = diagnostics
    base_stats = updated_dict["base_stats"]
    num_total = counts["num_rows_total"]
    try:
        num_zeros = series[series == 0].count()
    except TypeError:
        num_zeros = 0
    non_nan = counts["num_rows_with_data"]
    num_infinite = diagnostics.get("num_inf", 0) + diagnostics.get("num_neg_inf", 0)
    base_stats["total_rows"] = num_total
    base_stats["num_values"] = NumWithPercent(non_nan, num_total)
    base_stats["num_missing"] = NumWithPercent(num_total - non_nan, num_total)
    base_stats["num_infinite"] = NumWithPercent(num_infinite, num_total)
    base_stats["num_zeroes"] = NumWithPercent(num_zeros, num_total)
    base_stats["num_distinct"] = NumWithPercent(counts["distinct_count_without_nan"], num_total)


# This generates everything EXCEPT the "detail pane"
def analyze_feature_to_dictionary(to_process: FeatureToProcess) -> dict:
    # start = time.perf_counter()

    # === UNIFIED ENTRY: clean numeric series once, all downstream consume the same cleaned data ===
    to_process.source, source_diagnostics = clean_numeric_with_diagnostics(to_process.source)
    compare_diagnostics = None
    if to_process.compare is not None:
        to_process.compare, compare_diagnostics = clean_numeric_with_diagnostics(to_process.compare)

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

    # Determine SOURCE feature type (consumes cleaned series via to_process.source)
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
            if compare_type == FeatureType.TYPE_CAT or compare_type == FeatureType.TYPE_BOOL:
                fill_out_missing_counts_in_other_series(to_process.compare_counts, to_process.source_counts)
                fill_out_missing_counts_in_other_series(to_process.source_counts, to_process.compare_counts)
        returned_feature_dict["compare"] = dict()
        compare_dict = returned_feature_dict["compare"]
        compare_dict["type"] = compare_type

    # Settle all-NaN series, depending on source versus compared
    if to_process.compare is not None:
        if compare_type == FeatureType.TYPE_ALL_NAN and source_type == FeatureType.TYPE_ALL_NAN:
            returned_feature_dict["type"] = FeatureType.TYPE_TEXT
            compare_dict["type"] = FeatureType.TYPE_TEXT
        elif compare_type == FeatureType.TYPE_ALL_NAN:
            compare_dict["type"] = source_type
        elif source_type == FeatureType.TYPE_ALL_NAN:
            returned_feature_dict["type"] = compare_type
    else:
        if source_type == FeatureType.TYPE_ALL_NAN:
            returned_feature_dict["type"] = FeatureType.TYPE_TEXT

    # Establish base stats (pass diagnostics for inf count reporting)
    add_series_base_stats_to_dict(to_process.source, to_process.source_counts, returned_feature_dict, source_diagnostics)
    if to_process.compare is not None and compare_diagnostics is not None:
        add_series_base_stats_to_dict(to_process.compare, to_process.compare_counts, compare_dict, compare_diagnostics)

    # Perform full analysis on source/compare/target (all numeric analyzers consume pre-cleaned series)
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

    # print(f"{to_process.source.name} PROCESSED ------> "
    #       f" {time.perf_counter() - start}")

    return returned_feature_dict
