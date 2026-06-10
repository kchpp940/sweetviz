import html
import pandas as pd
import sweetviz.sv_html as sv_html
from sweetviz.sv_types import NumWithPercent, FeatureToProcess


def do_stats_text(series: pd.Series, counts: dict, updated_dict: dict):
    stats = dict()
    non_null = series.dropna()
    str_values = non_null.astype(str)

    lengths = str_values.str.len()
    num_values = counts["num_rows_with_data"]

    if len(lengths) > 0:
        stats["length_min"] = int(lengths.min())
        stats["length_max"] = int(lengths.max())
        stats["length_mean"] = float(lengths.mean())
        stats["length_median"] = float(lengths.median())
        stats["length_std"] = float(lengths.std()) if len(lengths) > 1 else 0.0
        stats["avg_length"] = float(lengths.mean())
        stats["total_characters"] = int(lengths.sum())
        stats["distinct_lengths"] = int(lengths.nunique())
    else:
        stats["length_min"] = 0
        stats["length_max"] = 0
        stats["length_mean"] = 0.0
        stats["length_median"] = 0.0
        stats["length_std"] = 0.0
        stats["avg_length"] = 0.0
        stats["total_characters"] = 0
        stats["distinct_lengths"] = 0

    stats["num_empty"] = int((str_values == "").sum())
    stats["num_whitespace_only"] = int(str_values.str.isspace().sum())
    stats["num_distinct"] = counts["distinct_count_without_nan"]

    updated_dict["text_stats"] = stats
    return


def do_detail_text(to_process: FeatureToProcess, updated_dict: dict):
    detail = dict()

    # Compute COUNT stats (i.e. below graph)
    # ----------------------------------------------------------------------------------------------
    detail["detail_count"] = []

    num_values = updated_dict["base_stats"]["num_values"].number
    if to_process.compare_counts is not None:
        num_values_compare = updated_dict["compare"]["base_stats"]["num_values"].number

    # Iterate through ALL VALUES and get stats
    for item in to_process.source_counts["value_counts_without_nan"].items():
        row = dict()
        row["name"] = html.escape(str(item[0]))
        row["count"] = NumWithPercent(item[1], num_values)
        # Defaults to no comparison or target
        row["count_compare"] = None
        row["target_stats"] = None
        row["target_stats_compare"] = None
        if to_process.compare_counts is not None:
            # HAS COMPARE...
            if row["name"] in to_process.compare_counts["value_counts_without_nan"].index:
                # ...and value exists in COMPARE
                matching = to_process.compare_counts["value_counts_without_nan"][row["name"]]
                row["count_compare"] = NumWithPercent(matching, num_values_compare)

        detail["detail_count"].append(row)

    updated_dict["detail"]["text"] = detail
    return


def analyze(to_process: FeatureToProcess, feature_dict: dict):
    compare_dict = feature_dict["compare"]

    do_stats_text(to_process.source, to_process.source_counts, feature_dict)
    if compare_dict is not None:
        do_stats_text(to_process.compare, to_process.compare_counts, compare_dict)

    do_detail_text(to_process, feature_dict)

    if to_process.is_target():
        raise ValueError
    else:
        feature_dict["html_summary"] = sv_html.generate_html_summary_text(feature_dict, compare_dict)
