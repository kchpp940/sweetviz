from typing import Tuple, Dict, List, Optional

from sweetviz.sv_types import FeatureType


class FeatureConfig:
    """
    Configuration for how features should be processed and displayed.

    Args:
        skip: Features to be excluded from the report entirely.
        force_cat: Features to be forced as categorical type.
        force_text: Features to be forced as text type.
        force_num: Features to be forced as numeric type.
        alias: Dictionary mapping original column names to display aliases
            (e.g., {"user_age": "用户年龄"}). Aliases are used only for display
            in HTML reports, detail pages, association graphs, compare reports,
            and notebook iframes. All data processing (stats, skip/force, target,
            compare matching) still uses original column names.
        groups: Dictionary mapping group names to lists of original column names
            (e.g., {"用户画像": ["user_age", "user_income"]}). Features in the
            summary area are displayed under their respective group headers.
            Features not assigned to any group appear after all defined groups.
    """
    def __init__(self, skip: Tuple = None,
            force_cat: Tuple = None, force_text: Tuple = None,
            force_num: Tuple = None,
            alias: Optional[Dict[str, str]] = None,
            groups: Optional[Dict[str, List[str]]] = None):
        def make_list(param):
            if type(param) == list or type(param) == tuple:
                return param
            elif type(param) == str:
                return [param]
            elif param is None:
                return list()
            raise ValueError("Invalid value passed in for FeatureConfig")

        # NEW (12-14-2020): rename "index" features
        def rename_index(list_of_feature_names):
            return [x if x != "index" else "df_index" for x in list_of_feature_names]

        self.skip = rename_index(make_list(skip))
        self.force_cat = rename_index(make_list(force_cat))
        self.force_text = rename_index(make_list(force_text))
        self.force_num = rename_index(make_list(force_num))

        # Alias: { original_col_name: display_name }
        if alias is None:
            self.alias = dict()
        else:
            self.alias = dict()
            for orig_name, disp_name in alias.items():
                renamed = orig_name if orig_name != "index" else "df_index"
                self.alias[renamed] = disp_name

        # Groups: { group_name: [original_col_name, ...] }
        if groups is None:
            self.groups = dict()
        else:
            self.groups = dict()
            for group_name, feature_list in groups.items():
                renamed_list = [x if x != "index" else "df_index" for x in make_list(feature_list)]
                self.groups[group_name] = renamed_list

    def get_alias(self, feature_name: str) -> str:
        return self.alias.get(feature_name, feature_name)

    def get_group(self, feature_name: str) -> Optional[str]:
        for group_name, feature_list in self.groups.items():
            if feature_name in feature_list:
                return group_name
        return None

    def get_ordered_groups(self) -> List[str]:
        return list(self.groups.keys())

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
        returned.extend(self.alias.keys())
        for feature_list in self.groups.values():
            returned.extend(feature_list)
        return returned