from typing import Tuple, List, Dict, Optional, Union

from sweetviz.sv_types import FeatureType


def _make_list(param):
    if type(param) == list or type(param) == tuple:
        return list(param)
    elif type(param) == str:
        return [param]
    elif param is None:
        return list()
    raise ValueError("Invalid value passed in for FeatureConfig")


def _rename_index(list_of_feature_names):
    return [x if x != "index" else "df_index" for x in list_of_feature_names]


class FeatureConfig:
    def __init__(self, skip: Union[List, Tuple, str] = None,
            force_cat: Union[List, Tuple, str] = None,
            force_text: Union[List, Tuple, str] = None,
            force_num: Union[List, Tuple, str] = None,
            alias: Dict[str, str] = None,
            groups: Dict[str, Union[List, Tuple]] = None):
        self.skip = _rename_index(_make_list(skip))
        self.force_cat = _rename_index(_make_list(force_cat))
        self.force_text = _rename_index(_make_list(force_text))
        self.force_num = _rename_index(_make_list(force_num))
        self.alias = alias if alias is not None else dict()
        self.groups = self._normalize_groups(groups)

    @staticmethod
    def _normalize_groups(groups):
        if groups is None:
            return dict()
        normalized = dict()
        for group_name, features in groups.items():
            normalized[group_name] = _rename_index(_make_list(features))
        return normalized

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
        for features in self.groups.values():
            returned.extend(features)
        return returned


class FeatureConfigContext:
    def __init__(self,
                 source_columns: List[str],
                 compare_columns: Optional[List[str]] = None,
                 target_feature_name: Optional[str] = None,
                 fc: Optional[FeatureConfig] = None):
        if fc is None:
            fc = FeatureConfig()
        self._fc = fc

        if compare_columns is None:
            compare_columns = []

        self.all_source_names = list(source_columns)
        self.all_compare_names = list(compare_columns)
        self.all_known_names = set(self.all_source_names) | set(self.all_compare_names)

        if target_feature_name == 'index':
            target_feature_name = 'df_index'
        self.target_feature_name = target_feature_name

        self.skip = set(self._fc.skip)
        self.alias = dict(self._fc.alias)
        self.groups = dict(self._fc.groups)

        self._forced_types: Dict[str, FeatureType] = dict()
        self._build_forced_types_and_check_conflicts()

        self._validate_all_mentioned_features_exist_in_source()
        self._validate_skip_features_exist_in_any()
        self._validate_target_not_skipped()
        self._validate_target_exists_in_source()
        self._validate_aliases_reference_source()
        self._validate_groups_no_duplicates_and_reference_source()

        self.filtered_source_names = [
            name for name in self.all_source_names if name not in self.skip
        ]

    def _build_forced_types_and_check_conflicts(self):
        force_mappings = [
            (self._fc.force_cat, FeatureType.TYPE_CAT),
            (self._fc.force_text, FeatureType.TYPE_TEXT),
            (self._fc.force_num, FeatureType.TYPE_NUM),
        ]
        for feature_list, ftype in force_mappings:
            for fname in feature_list:
                if fname in self._forced_types:
                    raise ValueError(
                        f'Feature "{fname}" is specified in multiple force_* '
                        f'parameters (conflict between {self._forced_types[fname]} '
                        f'and {ftype}). Each feature may only appear in one '
                        f'force_cat / force_text / force_num.'
                    )
                self._forced_types[fname] = ftype

    def _validate_all_mentioned_features_exist_in_source(self):
        mentioned = set()
        mentioned.update(self._fc.force_cat)
        mentioned.update(self._fc.force_text)
        mentioned.update(self._fc.force_num)
        for key in mentioned:
            if key not in self.all_source_names:
                raise ValueError(
                    f'"{key}" was specified in "feature_config" but is not found '
                    f'in source dataframe (watch case-sensitivity?).'
                )

    def _validate_skip_features_exist_in_any(self):
        for skipped in self._fc.skip:
            if skipped not in self.all_known_names:
                raise ValueError(
                    f'"{skipped}" was marked as "skip" but is not in any provided '
                    f'dataframe (watch case-sensitivity?).'
                )

    def _validate_target_not_skipped(self):
        if self.target_feature_name and self.target_feature_name in self.skip:
            raise ValueError(
                f'"{self.target_feature_name}" was also specified as "skip". '
                f'Target cannot be skipped.'
            )

    def _validate_target_exists_in_source(self):
        if self.target_feature_name and self.target_feature_name not in self.all_source_names:
            raise KeyError(
                f"Feature '{self.target_feature_name}' was specified as TARGET, "
                f"but is NOT FOUND in the dataframe (watch case-sensitivity?)."
            )

    def _validate_aliases_reference_source(self):
        for original_name in self.alias.keys():
            if original_name not in self.all_source_names:
                raise ValueError(
                    f'Alias key "{original_name}" not found in source dataframe '
                    f'(watch case-sensitivity?).'
                )

    def _validate_groups_no_duplicates_and_reference_source(self):
        seen_in_groups: Dict[str, str] = dict()
        for group_name, features in self.groups.items():
            for feat in features:
                if feat not in self.all_source_names:
                    raise ValueError(
                        f'Feature "{feat}" in group "{group_name}" not found in '
                        f'source dataframe (watch case-sensitivity?).'
                    )
                if feat in seen_in_groups:
                    raise ValueError(
                        f'Feature "{feat}" appears in multiple groups: '
                        f'"{seen_in_groups[feat]}" and "{group_name}". '
                        f'A feature may only belong to one group.'
                    )
                seen_in_groups[feat] = group_name

    def get_predetermined_type(self, feature_name: str) -> FeatureType:
        if feature_name in self.skip:
            return FeatureType.TYPE_SKIPPED
        return self._forced_types.get(feature_name, FeatureType.TYPE_UNKNOWN)

    def get_display_name(self, original_name: str) -> str:
        return self.alias.get(original_name, original_name)

    def get_group_for_feature(self, feature_name: str) -> Optional[str]:
        for group_name, features in self.groups.items():
            if feature_name in features:
                return group_name
        return None

    def get_all_groups(self) -> Dict[str, List[str]]:
        return self.groups

    def is_skipped(self, feature_name: str) -> bool:
        return feature_name in self.skip

    def is_target(self, feature_name: str) -> bool:
        return feature_name == self.target_feature_name

