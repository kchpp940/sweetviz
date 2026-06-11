import pandas as pd
from typing import Optional
from sweetviz.sv_types import FeatureType
from sweetviz.from_profiling_pandas import is_boolean, is_numeric, is_categorical, could_be_numeric
from sweetviz.diagnostics import SweetvizInputError, ErrorCategory, warn, DiagnosticManager


def determine_feature_type(series: pd.Series, counts: dict,
        must_be_this_type: FeatureType, which_dataframe: str,
        diag: Optional[DiagnosticManager] = None) -> object:
    # Replace infinite values with NaNs to avoid issues with histograms
    # TODO: INFINITE VALUE HANDLING/WARNING
    # series.replace(to_replace=[np.inf, np.NINF, np.PINF], value=np.nan,
    #                inplace=True)
    if counts["value_counts_without_nan"].index.inferred_type.startswith("mixed"):
        raise SweetvizInputError(
            f"列 '{series.name}' 包含混合数据类型（Pandas 检测为 'mixed' 类型）。\n"
            f"当前不支持混合数据类型；列应该只包含一种数据类型（纯数值或纯字符串）。",
            resolution=(
                f"最佳方案 -> 确保列 '{series.name}' 只包含一种数据类型（数值或字符串）。\n"
                f"方案 2 -> 将列 '{series.name}' 转换为字符串类型（如果合理），将被识别为分类或文本类型。\n"
                f"     示例代码:\n"
                f"     df['{series.name}'] = df['{series.name}'].astype(str)\n"
                f"方案 3 -> 将列 '{series.name}' 转换为数值类型（如果合理）:\n"
                f"     示例代码:\n"
                f"     df['{series.name}'] = pd.to_numeric(df['{series.name}'], errors='coerce')\n"
                f"     # (errors='coerce' 会将无法转换的值变为 NaN，之后可以根据需要处理)"
            )
        )

    try:
        # TODO: must_be_this_type ENFORCING
        if counts["distinct_count_without_nan"] == 0:
            # Empty
            var_type = FeatureType.TYPE_ALL_NAN
            # var_type = FeatureType.TYPE_UNSUPPORTED
        elif is_boolean(series, counts):
            var_type = FeatureType.TYPE_BOOL
        elif is_numeric(series, counts):
            var_type = FeatureType.TYPE_NUM
        elif is_categorical(series, counts):
            var_type = FeatureType.TYPE_CAT
        else:
            var_type = FeatureType.TYPE_TEXT
    except TypeError:
        var_type = FeatureType.TYPE_UNSUPPORTED

    # COERCE: only supporting the following for now:
    # TEXT -> CAT
    # CAT/BOOL -> TEXT
    # CAT/BOOL -> NUM
    # NUM -> CAT
    # NUM -> TEXT
    if must_be_this_type != FeatureType.TYPE_UNKNOWN and \
                must_be_this_type != var_type and \
                must_be_this_type != FeatureType.TYPE_ALL_NAN and \
                var_type != FeatureType.TYPE_ALL_NAN:
        if var_type == FeatureType.TYPE_TEXT and must_be_this_type == FeatureType.TYPE_CAT:
            var_type = FeatureType.TYPE_CAT
        elif (var_type == FeatureType.TYPE_CAT or var_type == FeatureType.TYPE_BOOL ) and \
            must_be_this_type == FeatureType.TYPE_TEXT:
            var_type = FeatureType.TYPE_TEXT
        elif (var_type == FeatureType.TYPE_CAT or var_type == FeatureType.TYPE_BOOL) and \
             must_be_this_type == FeatureType.TYPE_NUM:
            # Trickiest: Coerce into numerical
            if could_be_numeric(series):
                var_type = FeatureType.TYPE_NUM
            else:
                raise SweetvizInputError(
                    f"无法将 {which_dataframe} 中的列 '{series.name}' 从 {var_type} 强制转换为 {must_be_this_type}。",
                    resolution=(
                        f"-> 使用 feat_cfg 参数来强制指定列的类型（效果取决于类型组合）\n"
                        f"-> 修改源数据，使其更明确地为单一类型\n"
                        f"-> 这也可能是由于源数据和对比数据的特征类型不匹配导致的，请确保两者兼容"
                    )
                )
        elif var_type == FeatureType.TYPE_NUM and must_be_this_type == FeatureType.TYPE_CAT:
            var_type = FeatureType.TYPE_CAT
        elif var_type == FeatureType.TYPE_BOOL and must_be_this_type == FeatureType.TYPE_CAT:
            var_type = FeatureType.TYPE_CAT
        elif var_type == FeatureType.TYPE_NUM and must_be_this_type == FeatureType.TYPE_TEXT:
            var_type = FeatureType.TYPE_TEXT
        else:
            raise SweetvizInputError(
                f"无法将 {which_dataframe} 中的列 '{series.name}' 从 {var_type} 转换为目标类型 {must_be_this_type}。",
                resolution=(
                    f"-> 使用 feat_cfg 参数来强制指定列的类型（效果取决于类型组合）\n"
                    f"-> 修改源数据，使其更明确地为单一类型\n"
                    f"-> 这也可能是由于源数据和对比数据的特征类型不匹配导致的，请确保两者兼容"
                )
            )
    return var_type
