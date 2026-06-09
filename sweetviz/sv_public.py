from typing import Union, List, Tuple
import pandas as pd

import sweetviz.dataframe_report
from sweetviz.feature_config import FeatureConfig


def analyze(source: Union[pd.DataFrame, Tuple[pd.DataFrame, str]],
            target_feat: str = None,
            feat_cfg: FeatureConfig = None,
            pairwise_analysis: str = 'auto',
            verbosity: str = 'default'):
    """
    Analyze a single dataframe and generate a full EDA report.

    Args:
        source: Either a DataFrame, or a tuple/list of [DataFrame, display_name]
            (e.g. [train_df, "Training Data"]).
        target_feat: Original column name of the target feature to highlight.
            Only BOOLEAN and NUMERICAL features can be targets.
            **Must use the original column name, NOT an alias.**
        feat_cfg: A FeatureConfig object controlling skip, force_cat/force_num/force_text,
            display aliases, and feature grouping.
            All feature references inside FeatureConfig (skip, force_*, alias keys,
            groups lists) **must use original column names**.
        pairwise_analysis: 'auto', 'on', or 'off'. Controls correlation/association
            computation, which is O(n²) in the number of features.
        verbosity: 'default' (from config), 'full', 'progress_only', or 'off'.

    Returns:
        A DataframeReport object; call .show_html() or .show_notebook() on it to render.
    """
    report = sweetviz.dataframe_report.DataframeReport(source, target_feat, None,
                                                       pairwise_analysis, feat_cfg, verbosity)
    return report


def compare(source: Union[pd.DataFrame, Tuple[pd.DataFrame, str]],
            compare: Union[pd.DataFrame, Tuple[pd.DataFrame, str]],
            target_feat: str = None,
            feat_cfg: FeatureConfig = None,
            pairwise_analysis: str = 'auto',
            verbosity: str = 'default'):
    """
    Compare two dataframes side-by-side in a single report.

    Args:
        source: Base DataFrame (or [DataFrame, display_name]).
        compare: Comparison DataFrame (or [DataFrame, display_name]).
            Columns are matched against the source by **original column name**;
            aliases do not affect matching.
        target_feat: Original column name of the target feature.
            **Must use the original column name, NOT an alias.**
        feat_cfg: A FeatureConfig object. All feature references use original
            column names; aliases only affect display text.
        pairwise_analysis: 'auto', 'on', or 'off'.
        verbosity: 'default' (from config), 'full', 'progress_only', or 'off'.

    Returns:
        A DataframeReport object.
    """
    report = sweetviz.dataframe_report.DataframeReport(source, target_feat, compare,
                                                       pairwise_analysis, feat_cfg, verbosity)
    return report


def compare_intra(source_df: pd.DataFrame,
                  condition_series: pd.Series,
                  names: Tuple[str, str],
                  target_feat: str = None,
                  feat_cfg: FeatureConfig = None,
                  pairwise_analysis: str = 'auto',
                  verbosity: str = 'default'):
    """
    Split a single dataframe into two sub-populations by a boolean condition
    and compare them side-by-side.

    Args:
        source_df: The full source DataFrame.
        condition_series: Boolean Series (same length as source_df) used to
            split source_df into True/False sub-populations.
        names: A 2-tuple of (display_name_for_True, display_name_for_False).
        target_feat: Original column name of the target feature.
            **Must use the original column name, NOT an alias.**
        feat_cfg: A FeatureConfig object. All feature references use original
            column names; aliases only affect display text.
        pairwise_analysis: 'auto', 'on', or 'off'.
        verbosity: 'default' (from config), 'full', 'progress_only', or 'off'.

    Returns:
        A DataframeReport object.
    """
    if len(source_df) != len(condition_series):
        raise ValueError('compare_intra() expects source_df and '
                         'condition_series to be the same length')
    if condition_series.dtypes != bool:
        raise ValueError('compare_intra() requires condition_series '
                         'to be boolean length')

    data_true = source_df[condition_series]
    data_false = source_df[condition_series == False]
    if len(data_false) == 0:
        raise ValueError('compare_intra(): FALSE dataset is empty, nothing to compare!')
    if len(data_true) == 0:
        raise ValueError('compare_intra(): TRUE dataset is empty, nothing to compare!')
    report = sweetviz.dataframe_report.DataframeReport([data_true, names[0]], target_feat,
                                                       [data_false, names[1]],
                                                       pairwise_analysis, feat_cfg, verbosity)
    return report

