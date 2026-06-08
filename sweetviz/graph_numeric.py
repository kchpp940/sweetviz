import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import warnings

from sweetviz.config import config
from sweetviz import sv_html_formatters
from sweetviz.sv_types import FeatureType, FeatureToProcess
import sweetviz.graph


class GraphNumeric(sweetviz.graph.Graph):
    def __init__(self, which_graph: str, to_process: FeatureToProcess):
        if to_process.is_target() and which_graph == "mini":
            styles = ["graph_base.mplstyle", "graph_target.mplstyle"]
        else:
            styles = ["graph_base.mplstyle"]
        self.set_style(styles, False)

        is_detail = which_graph.find("detail") != -1
        if which_graph == "mini":
            f, axs = plt.subplots(
                1,
                1,
                figsize=(
                    config["Graphs"].getfloat("num_summary_graph_width"),
                    config["Graphs"].getfloat("summary_graph_height"),
                ),
            )
            self.num_bins = None
        elif is_detail:
            f, axs = plt.subplots(
                1,
                1,
                figsize=(
                    config["Graphs"].getfloat("detail_graph_width"),
                    config["Graphs"].getfloat("detail_graph_height_numeric"),
                ),
            )
            split = which_graph.split("-")
            self.index_for_css = split[1]
            self.num_bins = int(split[1])
            self.button_name = self.index_for_css
            if self.num_bins == 0:
                self.num_bins = None
                self.button_name = "Auto"
        else:
            raise ValueError

        axs.tick_params(axis="x", direction="out", pad=2, labelsize=8, length=2)
        axs.tick_params(axis="y", direction="out", pad=2, labelsize=8, length=2)
        axs.xaxis.set_major_formatter(mtick.FuncFormatter(self.format_smart))
        axs.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))

        # Numeric series are pre-cleaned at analyze_feature_to_dictionary entry
        # (inf/-inf replaced with nan); here we extract finite values for histogram plotting
        source_all = to_process.source
        saved_err_dict = np.geterr()
        np.seterr(all='raise')
        finite_source = source_all[np.isfinite(source_all)]
        if len(finite_source):
            norm_source = np.full(len(finite_source), 1.0 / len(finite_source))
        else:
            norm_source = []
        if to_process.compare is not None:
            compare_all = to_process.compare
            finite_compare = compare_all[np.isfinite(compare_all)]
            plot_data = (finite_source, finite_compare)
            if len(finite_compare):
                norm_compare = np.full(len(finite_compare), 1.0 / len(finite_compare))
            else:
                norm_compare = []
            normalizing_weights = (norm_source, norm_compare)

        else:
            plot_data = finite_source
            normalizing_weights = norm_source

        gap_percent = config["Graphs"].getfloat("summary_graph_categorical_gap")

        warnings.filterwarnings(
            "ignore", category=np.exceptions.VisibleDeprecationWarning
        )
        self.hist_specs = axs.hist(
            plot_data,
            weights=normalizing_weights,
            bins=self.num_bins,
            rwidth=(100.0 - gap_percent) / 100.0,
        )
        warnings.filterwarnings(
            "once", category=np.exceptions.VisibleDeprecationWarning
        )

        bin_limits = self.hist_specs[1]
        num_bins = len(bin_limits) - 1
        bin_counts = self.hist_specs[0]

        # Format x ticks
        x_ticks = plt.xticks()
        new_labels = [
            sv_html_formatters.fmt_smart_range_tight(val, max(x_ticks[0]))
            for val in x_ticks[0]
        ]
        plt.xticks(x_ticks[0], new_labels)

        # TARGET
        # ---------------------------------------------
        if to_process.source_target is not None:
            if to_process.predetermined_type_target == FeatureType.TYPE_NUM:
                source_bins_series = pd.cut(
                    source_all, bins=bin_limits, labels=False, right=False
                )
                source_bins_series = source_bins_series.fillna(num_bins - 1)
                bin_averages = [None] * num_bins
                for b in range(0, num_bins):
                    bin_averages[b] = to_process.source_target[
                        source_bins_series == b
                    ].mean()

                bin_offset_x = (bin_limits[1] - bin_limits[0]) / 2.0
                ax2 = axs.twinx()
                ax2.yaxis.set_major_formatter(mtick.FuncFormatter(self.format_smart))
                ax2.plot(
                    bin_limits[:-1] + bin_offset_x,
                    bin_averages,
                    marker="o",
                    color=sweetviz.graph.COLOR_TARGET_SOURCE,
                )

                if (
                    to_process.compare is not None
                    and to_process.compare_target is not None
                ):
                    compare_bins_series = pd.cut(
                        compare_all, bins=bin_limits, labels=False, right=False
                    )
                    source_bins_series = source_bins_series.fillna(num_bins - 1)
                    bin_averages = [None] * num_bins
                    for b in range(0, num_bins):
                        bin_averages[b] = to_process.compare_target[
                            compare_bins_series == b
                        ].mean()
                    ax2.plot(
                        bin_limits[:-1] + bin_offset_x,
                        bin_averages,
                        marker="o",
                        color=sweetviz.graph.COLOR_TARGET_COMPARE,
                    )
            elif to_process.predetermined_type_target == FeatureType.TYPE_BOOL:
                source_true = source_all[to_process.source_target == 1]
                source_bins_series = pd.cut(
                    source_true, bins=bin_limits, labels=False, right=False
                )
                source_bins_series = source_bins_series.fillna(num_bins - 1)
                total_counts_source = (
                    bin_counts[0] if to_process.compare is not None else bin_counts
                )
                total_counts_source = total_counts_source * len(finite_source)
                bin_true_counts_source = [None] * num_bins
                for b in range(0, num_bins):
                    if total_counts_source[b] > 0:
                        bin_true_counts_source[b] = (
                            source_true[source_bins_series == b].count()
                            / total_counts_source[b]
                        )
                    else:
                        bin_true_counts_source[b] = None
                bin_offset_x = (bin_limits[1] - bin_limits[0]) / 2.0

                ax2 = axs
                ax2.yaxis.set_major_formatter(
                    mtick.PercentFormatter(xmax=1.0, decimals=0)
                )
                ax2.plot(
                    bin_limits[:-1] + bin_offset_x,
                    bin_true_counts_source,
                    marker="o",
                    color=sweetviz.graph.COLOR_TARGET_SOURCE,
                )

                if (
                    to_process.compare is not None
                    and to_process.compare_target is not None
                ):
                    compare_true = compare_all[to_process.compare_target == 1]

                    compare_bins_series = pd.cut(
                        compare_true, bins=bin_limits, labels=False, right=False
                    )
                    source_bins_series = source_bins_series.fillna(num_bins - 1)
                    total_counts_compare = bin_counts[1] * len(finite_compare)
                    bin_true_counts_compare = [None] * num_bins
                    for b in range(0, num_bins):
                        if total_counts_compare[b] > 0:
                            bin_true_counts_compare[b] = (
                                compare_true[compare_bins_series == b].count()
                                / total_counts_compare[b]
                            )
                        else:
                            bin_true_counts_compare[b] = None

                    ax2.plot(
                        bin_limits[:-1] + bin_offset_x,
                        bin_true_counts_compare,
                        marker="o",
                        color=sweetviz.graph.COLOR_TARGET_COMPARE,
                    )
                ax2.set_ylim([0, None])

            else:
                raise ValueError

        # Finalize Graph
        # -----------------------------
        self.size_in_inches = f.get_size_inches()
        if which_graph == "mini":
            needed_pixels_padding = [4.0, 32, 15, 45]  # TOP-LEFT-BOTTOM-RIGHT
        else:
            needed_pixels_padding = [5.0, 32, 15, 45]  # TOP-LEFT-BOTTOM-RIGHT
        self.apply_pixel_padding(f, needed_pixels_padding)
        self.graph_base64 = self.get_encoded_base64(f)
        plt.close("all")
        np.seterr(**saved_err_dict)
        return
