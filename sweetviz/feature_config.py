from typing import Tuple, Dict, Optional, Union

from sweetviz.sv_types import FeatureType


class FeatureConfig:
    def __init__(self, skip: Tuple = None,
            force_cat: Tuple = None, force_text: Tuple = None,
            force_num: Tuple = None,
            feature_names: Optional[Dict[str, str]] = None):
        def make_list(param):
            if type(param) == list or type(param) == tuple:
                return param
            elif type(param) == str:
                return [param]
            elif param is None:
                return list()
            raise ValueError("Invalid value passed in for FeatureConfig")

        def rename_index(list_of_feature_names):
            return [x if x != "index" else "df_index" for x in list_of_feature_names]

        self.skip = rename_index(make_list(skip))
        self.force_cat = rename_index(make_list(force_cat))
        self.force_text = rename_index(make_list(force_text))
        self.force_num = rename_index(make_list(force_num))

        if feature_names is None:
            self.feature_names = {}
        else:
            self.feature_names = {}
            for k, v in feature_names.items():
                key = "df_index" if k == "index" else k
                self.feature_names[key] = v

    def get_display_name(self, feature_name: str) -> str:
        return self.feature_names.get(feature_name, feature_name)

    def get_predetermined_type(self, feature_name: str):
        if feature_name in self.skip:
            return FeatureType.TYPE_SKIPPED
        elif feature_name in self.force_cat:
            return FeatureType.TYPE_CAT
        elif feature_name in self.force_text:
            return FeatureType.TYPE_TEXT
        elif feature_name in self.force_num:
            return FeatureType.TYPE_NUM
        else:
            return FeatureType.TYPE_UNKNOWN

    def get_all_mentioned_features(self):
        returned = list()
        returned.extend(self.skip)
        returned.extend(self.force_cat)
        returned.extend(self.force_text)
        returned.extend(self.force_num)
        returned.extend(self.feature_names.keys())
        return returned