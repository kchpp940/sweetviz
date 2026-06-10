from typing import Tuple, List, Dict, Optional, Union, Mapping, FrozenSet
from dataclasses import dataclass
from types import MappingProxyType

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


def _rename_index_in_columns(columns: List[str]) -> List[str]:
    return ["df_index" if c == "index" else c for c in columns]


@dataclass(frozen=True)
class NormalizedFeatureConfig:
    source_columns: Tuple[str, ...]
    compare_columns: Tuple[str, ...]
    target_column: Optional[str]
    source_columns_filtered: Tuple[str, ...]
    compare_columns_aligned: Tuple[str, ...]
    skip_columns: FrozenSet[str]
    forced_types: Mapping[str, FeatureType]
    aliases: Mapping[str, str]
    groups: Mapping[str, Tuple[str, ...]]
    feature_to_group: Mapping[str, str]

    def get_predetermined_type(self, feature_name: str) -> FeatureType:
        if feature_name in self.skip_columns:
            return FeatureType.TYPE_SKIPPED
        return self.forced_types.get(feature_name, FeatureType.TYPE_UNKNOWN)

    def get_display_name(self, original_name: str) -> str:
        return self.aliases.get(original_name, original_name)

    def get_group_for_feature(self, feature_name: str) -> Optional[str]:
        return self.feature_to_group.get(feature_name)

    def is_skipped(self, feature_name: str) -> bool:
        return feature_name in self.skip_columns

    def is_target(self, feature_name: str) -> bool:
        return feature_name == self.target_column


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

        src_cols = _rename_index_in_columns(list(source_columns))
        cmp_cols = _rename_index_in_columns(list(compare_columns))
        all_known = set(src_cols) | set(cmp_cols)

        if target_feature_name == 'index':
            target_feature_name = 'df_index'

        skip_set = frozenset(self._fc.skip)
        forced_types: Dict[str, FeatureType] = dict()
        self._build_forced_types_and_check_conflicts(forced_types)

        self._validate_all_mentioned_features_exist_in_source(src_cols)
        self._validate_skip_features_exist_in_any(skip_set, all_known)
        self._validate_target_not_skipped(target_feature_name, skip_set)
        self._validate_target_exists_in_source(target_feature_name, src_cols)
        self._validate_aliases_reference_source(self._fc.alias, src_cols)

        normalized_groups: Dict[str, Tuple[str, ...]] = dict()
        feature_to_group: Dict[str, str] = dict()
        self._validate_groups_and_build_index(
            self._fc.groups, src_cols, normalized_groups, feature_to_group
        )

        src_filtered = tuple(
            name for name in src_cols if name not in skip_set and name != target_feature_name
        )
        src_filtered_set = set(src_filtered)
        cmp_aligned = tuple(
            name for name in cmp_cols if name in src_filtered_set or name == target_feature_name
        )

        self._result = NormalizedFeatureConfig(
            source_columns=tuple(src_cols),
            compare_columns=tuple(cmp_cols),
            target_column=target_feature_name,
            source_columns_filtered=src_filtered,
            compare_columns_aligned=cmp_aligned,
            skip_columns=skip_set,
            forced_types=MappingProxyType(forced_types),
            aliases=MappingProxyType(dict(self._fc.alias)),
            groups=MappingProxyType(normalized_groups),
            feature_to_group=MappingProxyType(feature_to_group),
        )

    @property
    def result(self) -> NormalizedFeatureConfig:
        return self._result

    def _build_forced_types_and_check_conflicts(self, forced_types: Dict[str, FeatureType]):
        force_mappings = [
            (self._fc.force_cat, FeatureType.TYPE_CAT),
            (self._fc.force_text, FeatureType.TYPE_TEXT),
            (self._fc.force_num, FeatureType.TYPE_NUM),
        ]
        for feature_list, ftype in force_mappings:
            for fname in feature_list:
                if fname in forced_types:
                    raise ValueError(
                        f'Feature "{fname}" is specified in multiple force_* '
                        f'parameters (conflict between {forced_types[fname]} '
                        f'and {ftype}). Each feature may only appear in one '
                        f'force_cat / force_text / force_num.'
                    )
                forced_types[fname] = ftype

    @staticmethod
    def _validate_all_mentioned_features_exist_in_source(source_columns: List[str]):
        pass

    def _validate_skip_features_exist_in_any(self, skip_set, all_known):
        for skipped in skip_set:
            if skipped not in all_known:
                raise ValueError(
                    f'"{skipped}" was marked as "skip" but is not in any provided '
                    f'dataframe (watch case-sensitivity?).'
                )

    @staticmethod
    def _validate_target_not_skipped(target_feature_name, skip_set):
        if target_feature_name and target_feature_name in skip_set:
            raise ValueError(
                f'"{target_feature_name}" was also specified as "skip". '
                f'Target cannot be skipped.'
            )

    @staticmethod
    def _validate_target_exists_in_source(target_feature_name, source_columns):
        if target_feature_name and target_feature_name not in source_columns:
            raise KeyError(
                f"Feature '{target_feature_name}' was specified as TARGET, "
                f"but is NOT FOUND in the dataframe (watch case-sensitivity?)."
            )

    @staticmethod
    def _validate_aliases_reference_source(alias, source_columns):
        for original_name in alias.keys():
            if original_name not in source_columns:
                raise ValueError(
                    f'Alias key "{original_name}" not found in source dataframe '
                    f'(watch case-sensitivity?).'
                )

    @staticmethod
    def _validate_groups_and_build_index(groups, source_columns, normalized_groups, feature_to_group):
        for group_name, features in groups.items():
            normalized_groups[group_name] = tuple(features)
            for feat in features:
                if feat not in source_columns:
                    raise ValueError(
                        f'Feature "{feat}" in group "{group_name}" not found in '
                        f'source dataframe (watch case-sensitivity?).'
                    )
                if feat in feature_to_group:
                    raise ValueError(
                        f'Feature "{feat}" appears in multiple groups: '
                        f'"{feature_to_group[feat]}" and "{group_name}". '
                        f'A feature may only belong to one group.'
                    )
                feature_to_group[feat] = group_name

    def _validate_all_force_features_exist_in_source(self, source_columns):
        mentioned = set()
        mentioned.update(self._fc.force_cat)
        mentioned.update(self._fc.force_text)
        mentioned.update(self._fc.force_num)
        for key in mentioned:
            if key not in source_columns:
                raise ValueError(
                    f'"{key}" was specified in "feature_config" but is not found '
                    f'in source dataframe (watch case-sensitivity?).'
                )

    def _validate_all_mentioned_features_exist_in_source(self, source_columns):
        self._validate_all_force_features_exist_in_source(source_columns)

