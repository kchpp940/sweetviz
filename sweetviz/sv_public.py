from typing import Union, List, Tuple
import pandas as pd

import sweetviz.dataframe_report
from sweetviz.feature_config import FeatureConfig


def analyze(source: Union[pd.DataFrame, Tuple[pd.DataFrame, str]],
            target_feat: str = None,
            feat_cfg: FeatureConfig = None,
            pairwise_analysis: str = 'auto',
            verbosity: str = 'default'):
    report = sweetviz.DataframeReport(source, target_feat, None,
                                      pairwise_analysis, feat_cfg,
                                      verbosity=verbosity)
    return report


def compare(source: Union[pd.DataFrame, Tuple[pd.DataFrame, str]],
            compare: Union[pd.DataFrame, Tuple[pd.DataFrame, str]],
            target_feat: str = None,
            feat_cfg: FeatureConfig = None,
            pairwise_analysis: str = 'auto',
            verbosity: str = 'default'):
    report = sweetviz.DataframeReport(source, target_feat, compare,
                                      pairwise_analysis, feat_cfg,
                                      verbosity=verbosity)
    return report


def compare_intra(source_df: pd.DataFrame,
                  condition_series: pd.Series,
                  names: Tuple[str, str],
                  target_feat: str = None,
                  feat_cfg: FeatureConfig = None,
                  pairwise_analysis: str = 'auto',
                  verbosity: str = 'default'):
    from sweetviz.diagnostics import SweetvizInputError
    if len(source_df) != len(condition_series):
        raise SweetvizInputError(
            'compare_intra() 要求 source_df 和 condition_series 长度相同',
            resolution='请确保两个输入的行数一致'
        )
    if condition_series.dtypes != bool:
        raise SweetvizInputError(
            'compare_intra() 要求 condition_series 为布尔类型',
            resolution='请将 condition_series 转换为布尔类型 (bool)'
        )

    data_true = source_df[condition_series]
    data_false = source_df[condition_series == False]
    if len(data_false) == 0:
        raise SweetvizInputError(
            'compare_intra(): FALSE 数据集为空，无法进行比较',
            resolution='请确保 condition_series 中至少有一些 False 值'
        )
    if len(data_true) == 0:
        raise SweetvizInputError(
            'compare_intra(): TRUE 数据集为空，无法进行比较',
            resolution='请确保 condition_series 中至少有一些 True 值'
        )
    report = sweetviz.DataframeReport([data_true, names[0]], target_feat,
                                      [data_false, names[1]],
                                      pairwise_analysis, feat_cfg,
                                      verbosity=verbosity)
    return report

